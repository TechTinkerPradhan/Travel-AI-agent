import logging
import os
from flask import request, jsonify, render_template
from services.airtable_service import AirtableService
from services.openai_service import generate_travel_plan

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def register_routes(app):
    """Register all routes with the Flask app"""
    logger.debug("Registering application routes...")

    # Initialize services
    airtable_service = AirtableService()

    @app.route("/")
    def index():
        """Show main app - bypassing auth for development"""
        return render_template("index.html")

    @app.route("/api/chat", methods=["POST"])
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

            # For development, using a fixed user_id
            user_id = "dev_user"
            logger.debug(
                f"Processing {'refinement' if is_refinement else 'chat'} request"
            )
            logger.debug(f"Message: {message[:100]}...")

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
                    if isinstance(
                            previous_response,
                            dict) and "alternatives" in previous_response:
                        prev_content = previous_response["alternatives"][0][
                            "content"]
                    else:
                        prev_content = str(previous_response)

                    message = f"""Modify this travel plan based on the following feedback:

Feedback: {message}

Original plan:
{prev_content}

Return TWO refined options incorporating this feedback."""

                logger.debug(
                    f"Calling OpenAI service with message length: {len(message)}"
                )
                plan_result = generate_travel_plan(message, prefs)

                if not isinstance(plan_result,
                                  dict) or "alternatives" not in plan_result:
                    logger.error(
                        f"Invalid plan result format: {type(plan_result)}")
                    return jsonify({
                        "status":
                        "error",
                        "message":
                        "Invalid response format from travel planner"
                    }), 500

                logger.debug("Successfully generated travel plan")
                return jsonify(plan_result)

            except Exception as e:
                logger.error(f"Error generating travel plan: {e}",
                             exc_info=True)
                return jsonify({"status": "error", "message": str(e)}), 500

        except Exception as e:
            logger.error(f"Unhandled error in chat endpoint: {e}",
                         exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    logger.debug("All routes registered successfully")
    return app
