# routes.py

import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, session, url_for
from services.airtable_service import AirtableService
from services.calendar_service import CalendarService
from services.openai_service import generate_travel_plan, analyze_user_preferences

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "some_super_secret_key")

# Instantiate services
airtable_service = AirtableService()
calendar_service = CalendarService()

@app.route("/")
def index():
    """Main page with chat UI"""
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle user chat message to generate itinerary plan or refine it."""
    try:
        data = request.json
        if not data:
            return jsonify({"status":"error","message":"No data provided"}),400

        message = data.get("message","").strip()
        user_id = data.get("user_id","default")

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
def update_preferences():
    """Save user preferences in Airtable."""
    try:
        data = request.json
        user_id = data.get("user_id")
        prefs = data.get("preferences",{})
        if not user_id:
            return jsonify({"status":"error","message":"User ID is required"}),400

        airtable_service.save_user_preferences(user_id, prefs)
        return jsonify({"status":"success"})
    except Exception as e:
        logger.error(f"Error updating preferences: {e}", exc_info=True)
        return jsonify({"status":"error","message":str(e)}),500

@app.route("/api/itinerary/save", methods=["POST"])
def save_itinerary():
    """Save a chosen itinerary to Airtable's 'Travel Itineraries' table."""
    try:
        data = request.json
        if not data:
            return jsonify({"status":"error","message":"No data provided"}),400

        user_id = data.get("user_id")
        original_query = data.get("original_query","")
        selected_itinerary = data.get("selected_itinerary","")
        user_changes = data.get("user_changes","")

        if not user_id or not selected_itinerary:
            return jsonify({"status":"error","message":"Missing user_id or itinerary"}),400

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

@app.route("/api/calendar/status")
def calendar_status():
    """Check if we have Google credentials in session."""
    try:
        is_authed = "google_credentials" in session
        return jsonify({"status":"success","authenticated":is_authed})
    except Exception as e:
        logger.error(f"Error in calendar_status: {e}", exc_info=True)
        return jsonify({"status":"error","message":str(e)}),500

@app.route("/api/calendar/event", methods=["POST"])
def create_calendar_event():
    """Create the actual calendar events from the final itinerary."""
    try:
        if "google_credentials" not in session:
            return jsonify({"status":"error","message":"Not authenticated with Google Calendar"}),401

        data = request.json
        itinerary_content = data.get("itinerary_content","")
        start_date = data.get("start_date")

        created_ids = calendar_service.create_calendar_events(session["google_credentials"], itinerary_content, start_date)
        return jsonify({"status":"success","event_ids":created_ids})

    except Exception as e:
        logger.error(f"Error creating calendar events: {e}", exc_info=True)
        return jsonify({"status":"error","message":f"Failed to create calendar events: {e}"}),500

@app.route("/api/calendar/preview", methods=["POST"])
def preview_calendar_events():
    """Generate preview data for itinerary without creating them in Google Calendar."""
    try:
        data = request.json
        itinerary_content = data.get("itinerary_content","")
        start_date = data.get("start_date")

        # The calendar_service method might be async, so we do:
        preview_data = calendar_service.create_calendar_preview(itinerary_content, start_date)
        # If create_calendar_preview is defined async, we can do `preview_data = await ...`
        # but for simplicity, let's assume it's sync or we just omit 'async'.

        # If create_calendar_preview is truly async, rename method or remove async 
        # in the calendar_service or handle it differently.
        if hasattr(preview_data, '__await__'):
            import asyncio
            preview_data = asyncio.run(preview_data)

        return jsonify({"status":"success","preview":preview_data})
    except Exception as e:
        logger.error(f"Error previewing calendar events: {e}", exc_info=True)
        return jsonify({"status":"error","message":f"Failed to generate events preview: {e}"}),500

@app.route("/api/calendar/logout")
def calendar_logout():
    """Clear Google credentials from session."""
    try:
        if "google_credentials" in session:
            del session["google_credentials"]
        return redirect(url_for("index"))
    except Exception as e:
        logger.error(f"Error in calendar_logout: {e}", exc_info=True)
        return jsonify({"status":"error","message":str(e)}),500
