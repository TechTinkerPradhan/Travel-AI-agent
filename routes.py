import logging
import os
from flask import request, jsonify, render_template, redirect, session, url_for
from services.airtable_service import AirtableService
from services.openai_service import generate_travel_plan
from services.calendar_service import CalendarService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def register_routes(app):
    """Register all routes with the Flask app"""
    logger.debug("Registering application routes...")

    # Initialize services
    airtable_service = AirtableService()
    calendar_service = CalendarService()

    @app.route("/")
    def index():
        """Show main page directly for development"""
        return render_template("index.html")

    @app.route("/api/calendar/status")
    def calendar_status():
        """Check Google Calendar connection status"""
        try:
            is_available = calendar_service.check_availability()
            is_authenticated = 'google_calendar_credentials' in session

            if not is_available:
                error_msg = calendar_service.get_configuration_error()
                logger.error(f"Calendar status error: {error_msg}")
                return jsonify({
                    "status": "error",
                    "available": False,
                    "message": error_msg,
                    "authenticated": False
                })

            return jsonify({
                "status": "success",
                "available": is_available,
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
    def chat():
        """Handle user chat message to generate itinerary plan"""
        try:
            print("=== Chat Request Debug ===")
            data = request.json
            print(f"Request data: {data}")

            if not data:
                print("Error: No data provided")
                return jsonify({
                    "status": "error",
                    "message": "No data provided"
                }), 400

            message = data.get("message", "").strip()
            print(f"Processing message: {message}")

            if not message:
                print("Error: Empty message")
                return jsonify({
                    "status": "error",
                    "message": "Message cannot be empty"
                }), 400

            user_id = data.get("user_id", "default_user")
            print(f"User ID: {user_id}")

            # Get user preferences (empty for development)
            prefs = {}

            # Generate travel plan
            try:
                print("Calling generate_travel_plan...")
                plan_result = generate_travel_plan(message, prefs)
                print(f"Plan result type: {type(plan_result)}")
                print(f"Plan result: {plan_result}")

                if not isinstance(plan_result, dict):
                    print(f"Invalid plan result format: {type(plan_result)}")
                    return jsonify({
                        "status": "error",
                        "message": "Invalid response format from travel planner"
                    }), 500

                print("Successfully generated travel plan")
                return jsonify(plan_result)

            except Exception as e:
                print(f"Error in generate_travel_plan: {str(e)}")
                logger.error(f"Error generating travel plan: {e}", exc_info=True)
                return jsonify({
                    "status": "error",
                    "message": f"Error generating travel plan: {str(e)}"
                }), 500

        except Exception as e:
            print(f"Unhandled error in chat endpoint: {str(e)}")
            logger.error(f"Unhandled error in chat endpoint: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": f"An unexpected error occurred: {str(e)}"
            }), 500

    logger.debug("All routes registered successfully")
    return app