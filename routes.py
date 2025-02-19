import json
import logging
from flask import jsonify, request, render_template, redirect, session, url_for
from services.openai_service import generate_travel_plan
from services.airtable_service import AirtableService
from services.calendar_service import CalendarService
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize services
airtable_service = AirtableService()
calendar_service = CalendarService()

def analyze_user_preferences(original_query, selected_response):
    """Analyze user preferences using the OpenAI service"""
    from services.openai_service import analyze_user_preferences as ai_analyze_preferences
    try:
        logger.debug("Starting preference analysis")
        logger.debug(f"Original query: {original_query}")
        logger.debug(f"Selected response length: {len(selected_response)}")

        result = ai_analyze_preferences(original_query, selected_response)
        logger.debug(f"Analysis completed successfully")
        return result
    except Exception as e:
        logger.error(f"Error in preference analysis: {str(e)}", exc_info=True)
        return {
            "error": "Failed to analyze preferences",
            "details": str(e)
        }

def register_routes(app):
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/chat', methods=['POST'])
    def chat():
        try:
            logger.debug("Received chat request")
            data = request.json
            if not data:
                logger.error("No data provided in request")
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400

            message = data.get('message', '')
            if not message.strip():
                logger.error("Empty message provided")
                return jsonify({
                    'status': 'error',
                    'message': 'Please provide a message'
                }), 400

            user_id = data.get('user_id', 'default')
            logger.debug(f"Processing message for user_id: {user_id}")
            logger.debug(f"Message content: {message}")

            # Get user preferences from Airtable
            try:
                preferences = airtable_service.get_user_preferences(user_id)
                if preferences is None:
                    logger.debug("No preferences found, using empty dict")
                    preferences = {}
                else:
                    logger.debug(f"Retrieved preferences: {preferences}")
            except ValueError as e:
                logger.error(f"Error fetching preferences: {str(e)}")
                preferences = {}

            # Generate responses using OpenAI
            logger.debug("Generating travel plan responses")
            response = generate_travel_plan(message, preferences)
            logger.debug(f"Generated response: {response}")

            # Return the entire response object
            return jsonify(response)

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error in chat endpoint: {error_message}", exc_info=True)
            if "high traffic" in error_message.lower():
                return jsonify({
                    'status': 'error',
                    'message': error_message
                }), 429
            return jsonify({
                'status': 'error',
                'message': f'An error occurred: {error_message}'
            }), 500

    @app.route('/api/chat/select', methods=['POST'])
    def select_response():
        try:
            logger.debug("Received response selection request")
            data = request.json
            if not data:
                logger.error("No data provided in selection request")
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400

            original_query = data.get('original_query', '')
            selected_response = data.get('selected_response', '')
            user_id = data.get('user_id', 'default')

            logger.debug(f"Processing selection for user_id: {user_id}")
            logger.debug(f"Original query: {original_query}")
            logger.debug(f"Selected response length: {len(selected_response)}")

            if not all([original_query, selected_response]):
                logger.error("Missing required fields in selection request")
                return jsonify({
                    'status': 'error',
                    'message': 'Missing required fields'
                }), 400

            # Analyze preferences based on selection
            logger.debug("Starting preference analysis")
            preference_analysis = analyze_user_preferences(original_query, selected_response)
            logger.debug("Completed preference analysis")

            return jsonify({
                'status': 'success',
                'preference_analysis': preference_analysis
            })

        except Exception as e:
            logger.error(f"Error processing response selection: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': f'Failed to process selection: {str(e)}'
            }), 500

    @app.route('/api/preferences', methods=['POST'])
    def update_preferences():
        try:
            logger.debug("Received preferences update request")
            data = request.json
            if not data:
                logger.error("No data provided in preferences update request")
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400

            user_id = data.get('user_id')
            preferences = data.get('preferences', {})

            if not user_id:
                logger.error("Missing user ID in preferences update request")
                return jsonify({
                    'status': 'error',
                    'message': 'User ID is required'
                }), 400

            # Save preferences to Airtable
            try:
                logger.debug(f"Saving preferences for user_id: {user_id}")
                airtable_service.save_user_preferences(user_id, preferences)
                return jsonify({
                    'status': 'success',
                    'message': 'Preferences updated successfully'
                })
            except ValueError as e:
                logger.error(f"Airtable error: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to save preferences: {str(e)}'
                }), 500

        except Exception as e:
            logger.error(f"Unexpected error in update_preferences: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': f'An unexpected error occurred: {str(e)}'
            }), 500

    @app.route('/api/calendar/auth')
    def calendar_auth():
        """Initiate the OAuth2 flow for Google Calendar"""
        try:
            logger.debug("Initiating Google Calendar OAuth flow")
            authorization_url, state = calendar_service.get_authorization_url()
            session['oauth_state'] = state
            return redirect(authorization_url)
        except Exception as e:
            logger.error(f"Error initiating OAuth flow: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Failed to initiate Google Calendar authorization'
            }), 500

    @app.route('/api/calendar/oauth2callback')
    def oauth2callback():
        """Handle the OAuth2 callback from Google"""
        try:
            logger.debug("Handling Google Calendar OAuth callback")
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
            logger.debug("Google Calendar authentication successful")
            return redirect(url_for('index'))

        except Exception as e:
            logger.error(f"Error in OAuth callback: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Failed to complete Google Calendar authorization'
            }), 500

    @app.route('/api/calendar/event', methods=['POST'])
    def create_calendar_event():
        """Create a new calendar event"""
        try:
            logger.debug("Received calendar event creation request")
            if 'google_credentials' not in session:
                logger.error("Not authenticated with Google Calendar")
                return jsonify({
                    'status': 'error',
                    'message': 'Not authenticated with Google Calendar'
                }), 401

            data = request.json
            if not data:
                logger.error("No event data provided")
                return jsonify({
                    'status': 'error',
                    'message': 'No event data provided'
                }), 400

            event_id = calendar_service.create_event(
                session['google_credentials'],
                data
            )
            logger.debug(f"Calendar event created with ID: {event_id}")
            return jsonify({
                'status': 'success',
                'event_id': event_id
            })

        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': f'Failed to create calendar event: {str(e)}'
            }), 500

    @app.route('/api/calendar/status')
    def calendar_status():
        """Check if user is authenticated with Google Calendar"""
        try:
            logger.debug("Checking Google Calendar authentication status")
            is_authenticated = 'google_credentials' in session
            return jsonify({
                'status': 'success',
                'authenticated': is_authenticated
            })
        except Exception as e:
            logger.error(f"Error checking calendar status: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Failed to check calendar authentication status'
            }), 500

    @app.route('/api/calendar/logout')
    def calendar_logout():
        """Remove Google Calendar credentials from session"""
        try:
            logger.debug("Logging out of Google Calendar")
            if 'google_credentials' in session:
                del session['google_credentials']
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error logging out of calendar: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Failed to logout from Google Calendar'
            }), 500