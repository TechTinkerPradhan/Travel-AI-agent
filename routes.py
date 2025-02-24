import logging
import os
from flask import request, jsonify, render_template, redirect, session, url_for
from flask_login import login_required, current_user
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
        """Show login page if not authenticated, otherwise show main app"""
        if not current_user.is_authenticated:
            return render_template("login.html")
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
    @login_required
    def chat():
        """Handle user chat message to generate itinerary plan"""
        try:
            data = request.json
            if not data:
                logger.error("No data provided in chat request")
                return jsonify({
                    "status": "error",
                    "message": "No data provided"
                }), 400

            message = data.get("message", "").strip()
            is_refinement = data.get("is_refinement", False)
            previous_response = data.get("previous_response", "")

            if not message:
                logger.error("Empty message in chat request")
                return jsonify({
                    "status": "error",
                    "message": "Message cannot be empty"
                }), 400

            user_id = str(current_user.id)
            logger.debug(f"Processing {'refinement' if is_refinement else 'chat'} request for user {user_id}")
            logger.debug(f"Message: {message[:100]}...")
            if is_refinement:
                logger.debug(f"Previous response length: {len(str(previous_response))}")

            # Get user preferences from Airtable
            try:
                prefs = airtable_service.get_user_preferences(user_id) or {}
                logger.debug(f"Retrieved user preferences: {prefs}")
            except Exception as e:
                logger.warning(f"Failed to get user preferences: {e}")
                prefs = {}

            # Generate travel plan
            try:
                # If this is a refinement, include the previous response in the context
                if is_refinement and previous_response:
                    logger.debug("Processing refinement request")
                    # Extract content from previous response if it's in the alternatives format
                    if isinstance(previous_response, dict) and "alternatives" in previous_response:
                        prev_content = previous_response["alternatives"][0]["content"]
                    else:
                        prev_content = str(previous_response)

                    message = f"""Refine this travel plan based on the following feedback:

Feedback: {message}

Previous plan:
{prev_content}

Please provide TWO alternative plans with similar format but incorporating the feedback."""

                logger.debug(f"Calling OpenAI service with message length: {len(message)}")
                plan_result = generate_travel_plan(message, prefs)

                if not isinstance(plan_result, dict) or "alternatives" not in plan_result:
                    logger.error(f"Invalid plan result format: {type(plan_result)}")
                    return jsonify({
                        "status": "error",
                        "message": "Invalid response format from travel planner"
                    }), 500

                logger.debug("Successfully generated travel plan")
                return jsonify(plan_result)

            except Exception as e:
                logger.error(f"Error generating travel plan: {e}", exc_info=True)
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        except Exception as e:
            logger.error(f"Unhandled error in chat endpoint: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route("/preferences", methods=["GET", "POST"])
    @login_required
    def preferences():
        """Handle user preferences page"""
        try:
            if request.method == "POST":
                data = request.json
                if not data or "preferences" not in data:
                    return jsonify({
                        "status": "error",
                        "message": "Invalid preferences data"
                    }), 400

                user_prefs = data["preferences"]
                user_id = str(current_user.id)

                # Update preferences in Airtable
                try:
                    airtable_service.update_user_preferences(user_id, user_prefs)
                    return jsonify({
                        "status": "success",
                        "message": "Preferences updated successfully"
                    })
                except Exception as e:
                    logger.error(f"Error updating preferences: {e}", exc_info=True)
                    return jsonify({
                        "status": "error",
                        "message": f"Error updating preferences: {str(e)}"
                    }), 500

            # GET request - fetch current preferences
            user_id = str(current_user.id)
            try:
                current_prefs = airtable_service.get_user_preferences(user_id) or {}
                return render_template("preferences.html", preferences=current_prefs)
            except Exception as e:
                logger.error(f"Error fetching preferences: {e}", exc_info=True)
                return render_template("preferences.html", preferences={})

        except Exception as e:
            logger.error(f"Unhandled error in preferences: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": f"An unexpected error occurred: {str(e)}"
            }), 500

    logger.debug("All routes registered successfully")
    return app