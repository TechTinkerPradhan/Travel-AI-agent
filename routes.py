import json
import logging
from flask import jsonify, request, render_template
from services.openai_service import generate_travel_plan
from services.airtable_service import AirtableService

# Initialize Airtable service
airtable_service = AirtableService()

def register_routes(app):
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/chat', methods=['POST'])
    def chat():
        try:
            data = request.json
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400

            message = data.get('message', '')
            if not message.strip():
                return jsonify({
                    'status': 'error',
                    'message': 'Please provide a message'
                }), 400

            user_id = data.get('user_id', 'default')

            # Get user preferences from Airtable
            try:
                preferences = airtable_service.get_user_preferences(user_id)
                if preferences is None:
                    preferences = {}  # Default empty preferences if user not found
            except ValueError as e:
                logging.error(f"Error fetching preferences: {str(e)}")
                preferences = {}  # Continue with empty preferences on error

            # Generate response using OpenAI
            response = generate_travel_plan(message, preferences)

            return jsonify({
                'status': 'success',
                'response': response
            })
        except Exception as e:
            error_message = str(e)
            if "high traffic" in error_message.lower():
                return jsonify({
                    'status': 'error',
                    'message': error_message
                }), 429
            return jsonify({
                'status': 'error',
                'message': f'An error occurred: {error_message}'
            }), 500

    @app.route('/api/preferences', methods=['POST'])
    def update_preferences():
        try:
            data = request.json
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400

            user_id = data.get('user_id')
            preferences = data.get('preferences', {})

            if not user_id:
                return jsonify({
                    'status': 'error',
                    'message': 'User ID is required'
                }), 400

            # Save preferences to Airtable
            try:
                airtable_service.save_user_preferences(user_id, preferences)
                return jsonify({
                    'status': 'success',
                    'message': 'Preferences updated successfully'
                })
            except ValueError as e:
                # Log the full error for debugging
                logging.error(f"Airtable error: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to save preferences: {str(e)}'
                }), 500

        except Exception as e:
            logging.error(f"Unexpected error in update_preferences: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'An unexpected error occurred: {str(e)}'
            }), 500