import logging
from flask import request, jsonify, render_template, redirect, session, url_for
from flask_login import login_required, current_user
from services.airtable_service import AirtableService
from services.openai_service import generate_travel_plan, analyze_user_preferences

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def register_routes(app):
    """Register all non-auth routes with the Flask app"""
    logger.debug("Registering main application routes...")

    # Initialize services
    airtable_service = AirtableService()
    from services.calendar_service import CalendarService
    calendar_service = CalendarService()

    @app.route("/")
    def index():
        """Redirect to login if not authenticated, otherwise show main page"""
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return render_template("index.html")

    @app.route("/api/chat", methods=["POST"])
    @login_required
    def chat():
        """Handle user chat message to generate itinerary plan or refine it."""
        try:
            data = request.json
            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            message = data.get("message", "").strip()
            user_id = str(current_user.id)

            # Retrieve user preferences from Airtable if they exist
            prefs = {}
            try:
                user_prefs = airtable_service.get_user_preferences(user_id)
                if user_prefs:
                    prefs = user_prefs
            except Exception as e:
                logging.warning(f"Could not fetch preferences for {user_id}: {e}")

            plan_result = generate_travel_plan(message, prefs)
            return jsonify(plan_result)

        except Exception as e:
            logger.error(f"Error in chat endpoint: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/chat/select", methods=["POST"])
    @login_required
    def select_response():
        """Save selected itinerary."""
        try:
            data = request.json
            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            content = data.get("content")
            original_query = data.get("original_query")

            if not content or not original_query:
                return jsonify({"status": "error", "message": "Missing content or original query"}), 400

            # Save to Airtable
            airtable_service.save_user_itinerary(
                user_id=str(current_user.id),
                original_query=original_query,
                selected_itinerary=content
            )

            return jsonify({"status": "success"})
        except Exception as e:
            logger.error(f"Error in select_response: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/calendar/status")
    @login_required
    def calendar_status():
        """Check if calendar integration is available and authenticated."""
        try:
            is_available = calendar_service.check_availability()
            is_authenticated = 'google_calendar_credentials' in session

            return jsonify({
                "status": "success",
                "available": is_available,
                "authenticated": is_authenticated
            })
        except Exception as e:
            logger.error(f"Error checking calendar status: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route("/api/calendar/auth")
    @login_required
    def calendar_auth():
        """Initiate Google Calendar OAuth flow."""
        try:
            if not calendar_service.check_availability():
                return jsonify({
                    "status": "error",
                    "message": "Calendar integration is not configured"
                }), 503

            authorization_url, state = calendar_service.get_authorization_url()
            session['calendar_oauth_state'] = state
            return redirect(authorization_url)
        except Exception as e:
            logger.error(f"Error initiating calendar auth: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route("/api/calendar/event", methods=["POST"])
    @login_required
    def create_calendar_event():
        """Create events in user's Google Calendar."""
        try:
            if not calendar_service.check_availability():
                return jsonify({
                    "status": "error",
                    "message": "Calendar integration is not configured"
                }), 503

            if 'google_calendar_credentials' not in session:
                return jsonify({
                    "status": "error",
                    "message": "Not authenticated with Google Calendar"
                }), 401

            data = request.json
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "No data provided"
                }), 400

            itinerary_content = data.get('itinerary_content')
            start_date = data.get('start_date')

            if not itinerary_content:
                return jsonify({
                    "status": "error",
                    "message": "No itinerary content provided"
                }), 400

            event_ids = calendar_service.create_calendar_events(
                session['google_calendar_credentials'],
                itinerary_content,
                start_date
            )

            return jsonify({
                "status": "success",
                "event_ids": event_ids
            })
        except Exception as e:
            logger.error(f"Error creating calendar events: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route("/api/calendar/preview", methods=["POST"])
    @login_required
    async def preview_calendar_events():
        """Preview calendar events before creation."""
        try:
            if not calendar_service.check_availability():
                return jsonify({
                    "status": "error",
                    "message": "Calendar integration is not configured"
                }), 503

            data = request.json
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "No data provided"
                }), 400

            itinerary_content = data.get('itinerary_content')
            start_date = data.get('start_date')

            if not itinerary_content:
                return jsonify({
                    "status": "error",
                    "message": "No itinerary content provided"
                }), 400

            preview = await calendar_service.create_calendar_preview(
                itinerary_content,
                start_date
            )

            return jsonify({
                "status": "success",
                "preview": preview
            })
        except Exception as e:
            logger.error(f"Error creating calendar preview: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route("/calendar_auth")
    @login_required
    def old_calendar_auth(): # Renamed to indicate it's the old route
        return redirect(url_for('api.calendar_auth')) # Redirect to the new API route


    @app.route("/api/preferences", methods=["POST"])
    @login_required
    def update_preferences():
        """Save user preferences in Airtable."""
        try:
            data = request.json
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

    logger.debug("All routes registered successfully")
    return app