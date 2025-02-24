# routes.py

import os
import logging
from datetime import datetime
from flask import request, jsonify, render_template, redirect, session, url_for
from flask_login import login_required, current_user
from services.airtable_service import AirtableService
from services.calendar_service import CalendarService
from services.openai_service import generate_travel_plan, analyze_user_preferences

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Instantiate services
airtable_service = AirtableService()
calendar_service = CalendarService()

def register_routes(app):
    """Register all routes with the Flask app"""

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
                return jsonify({"status":"error","message":"No data provided"}),400

            message = data.get("message","").strip()
            user_id = str(current_user.id)  # Use the logged-in user's ID

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
            return jsonify({"status":"error","message":f"Unexpected error: {e}"}),500

    @app.route("/api/chat/select", methods=["POST"])
    @login_required
    def select_response():
        """Optional: analyze user preference from selected plan, if needed."""
        try:
            data = request.json
            if not data:
                return jsonify({"status":"error","message":"No data provided"}),400

            original_query = data.get("original_query","")
            selected_response = data.get("selected_response","")

            analysis = analyze_user_preferences(original_query, selected_response)
            return jsonify({"status":"success", "preference_analysis":analysis})
        except Exception as e:
            logger.error(f"Error in select_response: {e}", exc_info=True)
            return jsonify({"status":"error","message":f"{e}"}),500

    @app.route("/api/preferences", methods=["POST"])
    @login_required
    def update_preferences():
        """Save user preferences in Airtable."""
        try:
            data = request.json
            user_id = str(current_user.id)  # Use the logged-in user's ID
            prefs = data.get("preferences",{})

            airtable_service.save_user_preferences(user_id, prefs)
            return jsonify({"status":"success"})
        except Exception as e:
            logger.error(f"Error updating preferences: {e}", exc_info=True)
            return jsonify({"status":"error","message":str(e)}),500

    @app.route("/api/itinerary/save", methods=["POST"])
    @login_required
    def save_itinerary():
        """Save a chosen itinerary to Airtable's 'Travel Itineraries' table."""
        try:
            data = request.json
            if not data:
                return jsonify({"status":"error","message":"No data provided"}),400

            user_id = str(current_user.id)  # Use the logged-in user's ID
            original_query = data.get("original_query","")
            selected_itinerary = data.get("selected_itinerary","")
            user_changes = data.get("user_changes","")

            if not selected_itinerary:
                return jsonify({"status":"error","message":"Missing itinerary"}),400

            record = airtable_service.save_user_itinerary(
                user_id=user_id,
                original_query=original_query,
                selected_itinerary=selected_itinerary,
                user_changes=user_changes
            )
            return jsonify({"status":"success","record_id":record.get("id")})

        except Exception as e:
            logger.error(f"Error saving itinerary: {e}", exc_info=True)
            return jsonify({"status":"error","message":str(e)}),500

    @app.route("/api/calendar/auth")
    @login_required
    def calendar_auth():
        """Initiate Google OAuth flow."""
        try:
            auth_url, state = calendar_service.get_authorization_url()
            session["oauth_state"] = state
            return redirect(auth_url)
        except Exception as e:
            logger.error(f"Error in calendar_auth: {e}", exc_info=True)
            return jsonify({"status":"error","message":str(e)}),500

    @app.route("/api/calendar/oauth2callback")
    @login_required
    def oauth2callback():
        """Handle Google's callback after user consents to Calendar access."""
        try:
            if "error" in request.args:
                error_msg = request.args.get("error_description","Unknown error")
                return jsonify({"status":"error","message":f"OAuth error: {error_msg}"}),400

            state = session.get("oauth_state")
            if not state:
                return jsonify({"status":"error","message":"Invalid OAuth state"}),400

            creds = calendar_service.verify_oauth2_callback(request.url, state)
            session["google_credentials"] = creds
            return redirect(url_for("index"))
        except Exception as e:
            logger.error(f"Error in oauth2callback: {e}", exc_info=True)
            return jsonify({"status":"error","message":str(e)}),500

    return app