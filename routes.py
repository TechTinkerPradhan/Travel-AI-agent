import json
from flask import jsonify, request, render_template
from services.openai_service import generate_travel_plan
from services.storage_service import save_user_preferences, get_user_preferences

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

            # Get user preferences
            preferences = get_user_preferences(user_id)

            # Generate response using OpenAI with retry logic
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

            save_user_preferences(user_id, preferences)

            return jsonify({
                'status': 'success',
                'message': 'Preferences updated successfully'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update preferences. Please try again.'
            }), 500