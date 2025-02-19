import json
import logging
from flask import jsonify, request, render_template, redirect, session, url_for
from services.openai_service import generate_travel_plan
from services.airtable_service import AirtableService
from services.calendar_service import CalendarService
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

# Initialize services
airtable_service = AirtableService()
calendar_service = CalendarService()

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
                    preferences = {}
            except ValueError as e:
                logging.error(f"Error fetching preferences: {str(e)}")
                preferences = {}

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

    @app.route('/api/calendar/auth')
    def calendar_auth():
        """Initiate the OAuth2 flow for Google Calendar"""
        try:
            authorization_url, state = calendar_service.get_authorization_url()
            session['oauth_state'] = state
            return redirect(authorization_url)
        except Exception as e:
            logging.error(f"Error initiating OAuth flow: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to initiate Google Calendar authorization'
            }), 500

    @app.route('/api/calendar/oauth2callback')
    def oauth2callback():
        """Handle the OAuth2 callback from Google"""
        try:
            state = session.get('oauth_state')
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": calendar_service.client_id,
                        "client_secret": calendar_service.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [f"https://{calendar_service.replit_domain}/api/calendar/oauth2callback"]
                    }
                },
                scopes=calendar_service.SCOPES,
                state=state
            )

            flow.redirect_uri = f"https://{calendar_service.replit_domain}/api/calendar/oauth2callback"
            authorization_response = request.url
            flow.fetch_token(authorization_response=authorization_response)

            credentials = flow.credentials
            session['google_credentials'] = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }

            return redirect(url_for('index'))

        except Exception as e:
            logging.error(f"Error in OAuth callback: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to complete Google Calendar authorization'
            }), 500

    @app.route('/api/calendar/event', methods=['POST'])
    def create_calendar_event():
        """Create a new calendar event"""
        try:
            if 'google_credentials' not in session:
                return jsonify({
                    'status': 'error',
                    'message': 'Not authenticated with Google Calendar'
                }), 401

            data = request.json
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No event data provided'
                }), 400

            event_id = calendar_service.create_event(
                session['google_credentials'],
                data
            )

            return jsonify({
                'status': 'success',
                'event_id': event_id
            })

        except Exception as e:
            logging.error(f"Error creating calendar event: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to create calendar event: {str(e)}'
            }), 500
    
    @app.route('/api/calendar/status')
    def calendar_status():
        """Check if user is authenticated with Google Calendar"""
        try:
            is_authenticated = 'google_credentials' in session
            return jsonify({
                'status': 'success',
                'authenticated': is_authenticated
            })
        except Exception as e:
            logging.error(f"Error checking calendar status: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to check calendar authentication status'
            }), 500

    @app.route('/api/calendar/logout')
    def calendar_logout():
        """Remove Google Calendar credentials from session"""
        try:
            if 'google_credentials' in session:
                del session['google_credentials']
            return redirect(url_for('index'))
        except Exception as e:
            logging.error(f"Error logging out of calendar: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to logout from Google Calendar'
            }), 500