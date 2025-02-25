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

    @app.route("/")
    def index():
        """Redirect to login if not authenticated, otherwise show main page"""
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return render_template("index.html")

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

    @app.route("/api/chat", methods=["POST"])
    @login_required
    def chat():
        """Handle user chat message to generate itinerary plan or refine it."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            message = data.get("message", "").strip()
            if not message:
                return jsonify({"status": "error", "message": "Message cannot be empty"}), 400

            user_id = str(current_user.id)

            # Retrieve user preferences from Airtable if they exist
            prefs = {}
            try:
                user_prefs = airtable_service.get_user_preferences(user_id)
                if user_prefs:
                    prefs = user_prefs
            except Exception as e:
                logging.warning(f"Could not fetch preferences for {user_id}: {e}")

            try:
                plan_result = generate_travel_plan(message, prefs)
                return jsonify(plan_result)
            except Exception as e:
                logger.error(f"Error generating travel plan: {e}", exc_info=True)
                error_msg = str(e)
                if '<html>' in error_msg:
                    error_msg = "Server encountered an unexpected error. Please try again."
                return jsonify({
                    "status": "error",
                    "message": error_msg
                }), 500

        except Exception as e:
            logger.error(f"Error in chat endpoint: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": "An unexpected error occurred. Please try again."
            }), 500

    @app.route("/api/chat/select", methods=["POST"])
    @login_required
    def select_response():
        """Save selected itinerary."""
        try:
            data = request.get_json()
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

    logger.debug("All routes registered successfully")
    return app