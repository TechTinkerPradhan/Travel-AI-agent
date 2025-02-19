import json
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
            preferences = airtable_service.get_user_preferences(user_id)
            if preferences is None:
                preferences = {}  # Default empty preferences if user not found

            # Generate response using OpenAI
            response = generate_travel_plan(message, preferences)

            return jsonify({
                'status': 'success',
                'response': response
            })
        except Exception as e:
            error_message = str(e)
            if "high traffic" in error_message:
                return jsonify({
                    'status': 'error',
                    'message': error_message
                }), 429
            return jsonify({
                'status': 'error',
                'message': 'An error occurred while processing your request. Please try again.'
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

            user_id = data.get('user_id', 'default')
            preferences = data.get('preferences', {})

            # Save preferences to Airtable
            airtable_service.save_user_preferences(user_id, preferences)

            return jsonify({
                'status': 'success',
                'message': 'Preferences updated successfully'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Failed to update preferences: {str(e)}'
            }), 500