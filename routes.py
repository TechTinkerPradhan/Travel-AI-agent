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
        """Analyze user preference from selected plan."""
        try:
            data = request.json
            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            original_query = data.get("original_query", "")
            selected_response = data.get("selected_response", "")

            analysis = analyze_user_preferences(original_query, selected_response)
            return jsonify({"status": "success", "preference_analysis": analysis})
        except Exception as e:
            logger.error(f"Error in select_response: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/calendar_auth")
    @login_required
    def calendar_auth():
        """Initiate Google Calendar OAuth flow."""
        try:
            authorization_url, state = calendar_service.get_authorization_url()
            session['calendar_oauth_state'] = state
            return redirect(authorization_url)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

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