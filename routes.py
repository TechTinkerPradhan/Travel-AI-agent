import logging
from flask import request, jsonify, render_template, redirect, session, url_for
from flask_login import login_required, current_user
from services.airtable_service import AirtableService
from services.openai_service import generate_travel_plan, analyze_user_preferences
from services.calendar_service import CalendarService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def register_routes(app):
    """Register all non-auth routes with the Flask app"""
    logger.debug("Registering main application routes...")

    # Initialize services
    airtable_service = AirtableService()
    calendar_service = CalendarService()

    @app.errorhandler(404)
    def not_found(e):
        """Return JSON for HTTP 404 errors."""
        logger.error(f"404 error: {request.url}")
        return jsonify({"status": "error", "message": "Resource not found"}), 404

    @app.errorhandler(Exception)
    def handle_exception(e):
        """Return JSON instead of HTML for any error."""
        logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/chat", methods=["POST"])
    @login_required
    def chat():
        """Handle user chat message to generate itinerary plan."""
        try:
            logger.debug("Received chat request")

            if not request.is_json:
                return jsonify({
                    "status": "error",
                    "message": "Request must be JSON"
                }), 400

            data = request.get_json()
            message = data.get("message", "").strip()

            if not message:
                return jsonify({
                    "status": "error",
                    "message": "Message cannot be empty"
                }), 400

            # Get user preferences
            prefs = {}
            try:
                user_prefs = airtable_service.get_user_preferences(str(current_user.id))
                if user_prefs:
                    prefs = user_prefs
            except Exception as e:
                logger.warning(f"Failed to fetch preferences: {e}")

            # Generate travel plan
            try:
                result = generate_travel_plan(message, prefs)
                return jsonify(result)
            except Exception as e:
                logger.error(f"Travel plan generation error: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        except Exception as e:
            logger.error(f"Chat endpoint error: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "An unexpected error occurred"
            }), 500

    @app.route("/api/calendar/status")
    @login_required
    def calendar_status():
        """Check Google Calendar connection status"""
        try:
            is_available = calendar_service.check_availability()
            is_authenticated = 'google_calendar_credentials' in session

            if not is_available:
                error_msg = calendar_service.get_configuration_error()
                logger.error(f"Calendar status check failed: {error_msg}")
                return jsonify({
                    "status": "error",
                    "available": False,
                    "message": error_msg,
                    "authenticated": False
                })

            return jsonify({
                "status": "success",
                "available": True,
                "authenticated": is_authenticated
            })
        except Exception as e:
            error_msg = f"Error checking calendar status: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return jsonify({
                "status": "error",
                "message": error_msg,
                "available": False,
                "authenticated": False
            }), 500

    @app.route("/api/calendar/auth")
    @login_required
    def calendar_auth():
        """Initiate Google Calendar OAuth flow"""
        try:
            if not calendar_service.check_availability():
                error_msg = calendar_service.get_configuration_error()
                logger.error(f"Calendar auth failed: {error_msg}")
                return jsonify({
                    "status": "error",
                    "message": error_msg
                }), 503

            authorization_url, state = calendar_service.get_authorization_url()
            session['calendar_oauth_state'] = state
            logger.debug(f"Redirecting to authorization URL: {authorization_url}")
            return redirect(authorization_url)
        except Exception as e:
            error_msg = f"Error in calendar auth: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return jsonify({"status": "error", "message": error_msg}), 500

    @app.route("/api/chat/select", methods=["POST"])
    @login_required
    def select_plan():
        """Handle plan selection and save to database."""
        try:
            logger.debug("Received plan selection request")
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            # Validate required fields
            if not all(key in data for key in ['start_date', 'content', 'original_query']):
                return jsonify({
                    "status": "error",
                    "message": "Missing required data. Please provide start_date, content, and original_query."
                }), 400

            try:
                # Save to Airtable with basic required fields
                saved_plan = airtable_service.save_user_itinerary(
                    user_id=str(current_user.id),
                    original_query=data['original_query'],
                    selected_itinerary=data['content'],
                    start_date=data['start_date']
                )

                logger.debug(f"Successfully saved plan: {saved_plan['id']}")
                return jsonify({
                    "status": "success",
                    "plan_id": saved_plan['id']
                })

            except Exception as e:
                logger.error(f"Airtable save error: {str(e)}")
                # Return a more user-friendly error message
                error_msg = "Unable to save your travel plan. Please try again or contact support if the issue persists."
                return jsonify({
                    "status": "error",
                    "message": error_msg
                }), 500

        except Exception as e:
            logger.error(f"Error in select_plan: {str(e)}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "An unexpected error occurred while saving the plan"
            }), 500

    @app.route("/api/calendar/add", methods=["POST"])
    @login_required
    def add_to_calendar():
        """Add selected plan to Google Calendar."""
        try:
            if not calendar_service.check_availability():
                return jsonify({
                    "status": "error",
                    "message": "Calendar service is not available"
                }), 503

            if 'google_calendar_credentials' not in session:
                return jsonify({
                    "status": "error",
                    "message": "Please connect your Google Calendar first"
                }), 401

            data = request.get_json()
            if not data or 'plan_id' not in data or 'start_date' not in data:
                return jsonify({
                    "status": "error",
                    "message": "Missing required data"
                }), 400

            # Get the plan from Airtable
            try:
                plan = airtable_service.get_user_itinerary(
                    user_id=str(current_user.id),
                    plan_id=data['plan_id']
                )

                if not plan:
                    logger.error(f"Plan not found for ID: {data['plan_id']}")
                    return jsonify({
                        "status": "error",
                        "message": "Plan not found"
                    }), 404

                # Create calendar events
                events = calendar_service.create_events_from_plan(
                    itinerary_content=plan['content'],
                    start_date=data['start_date'],
                    user_email=current_user.email
                )

                return jsonify({
                    "status": "success",
                    "message": "Successfully added to calendar",
                    "events": events
                })

            except Exception as e:
                logger.error(f"Error retrieving plan or creating events: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": "Failed to create calendar events. Please try again."
                }), 500

        except Exception as e:
            logger.error(f"Error adding to calendar: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "An unexpected error occurred. Please try again."
            }), 500

    @app.route("/api/plans", methods=["GET"])
    @login_required
    def get_user_plans():
        """Get all travel plans for the current user."""
        try:
            plans = airtable_service.get_user_itineraries(str(current_user.id))
            return jsonify({
                "status": "success",
                "plans": plans
            })
        except Exception as e:
            logger.error(f"Error fetching user plans: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/preferences", methods=["POST"])
    @login_required
    def update_preferences():
        """Save user preferences in Airtable."""
        try:
            data = request.get_json()
            user_id = str(current_user.id)
            prefs = data.get("preferences", {})

            airtable_service.save_user_preferences(user_id, prefs)
            return jsonify({"status": "success"})
        except Exception as e:
            logger.error(f"Error updating preferences: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/preferences")
    @login_required
    def preferences():
        """Show user preferences management page"""
        try:
            user_id = str(current_user.id)
            user_prefs = airtable_service.get_user_preferences(user_id) or {}
            return render_template("preferences.html", preferences=user_prefs)
        except Exception as e:
            logger.error(f"Error fetching preferences: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/")
    def index():
        """Redirect to login if not authenticated, otherwise show main page"""
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return render_template("index.html")

    logger.debug("All routes registered successfully")
    return app