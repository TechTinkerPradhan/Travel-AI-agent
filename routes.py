import json
import logging
import os # Added to access environment variables
from datetime import datetime
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
            logger.debug("Starting Google Calendar authentication")
            logger.debug(f"Session contents before auth: {session}")

            # Check if we have the required environment variables
            if not all([os.environ.get('GOOGLE_CLIENT_ID'), os.environ.get('GOOGLE_CLIENT_SECRET')]):
                logger.error("Missing Google OAuth credentials in environment")
                return jsonify({
                    'status': 'error',
                    'message': 'Google Calendar is not properly configured.'
                }), 500

            # Get the authorization URL
            authorization_url, state = calendar_service.get_authorization_url()
            logger.debug(f"Generated authorization URL (truncated): {authorization_url[:100]}...")
            logger.debug(f"Generated state: {state}")

            # Store the state in the session
            session['oauth_state'] = state
            logger.debug("Stored OAuth state in session")
            logger.debug(f"Session after storing state: {session}")

            # Ensure we're using HTTPS for the redirect
            if authorization_url.startswith('http://'):
                authorization_url = 'https://' + authorization_url[7:]

            return redirect(authorization_url)

        except Exception as e:
            logger.error(f"Error initiating OAuth flow: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Failed to initiate Google Calendar authorization. Please try again.'
            }), 500

    @app.route('/api/calendar/oauth2callback')
    def oauth2callback():
        """Handle the OAuth2 callback from Google"""
        try:
            logger.debug("Received OAuth2 callback")
            logger.debug(f"Full request URL: {request.url}")
            logger.debug(f"Request args: {request.args}")
            logger.debug(f"Current session contents: {session}")

            # Check for OAuth errors
            if 'error' in request.args:
                error = request.args.get('error')
                error_description = request.args.get('error_description', '')
                logger.error(f"OAuth error received: {error} - {error_description}")

                if error == 'access_denied':
                    if 'verification' in error_description.lower():
                        return jsonify({
                            'status': 'error',
                            'message': 'This application is pending verification by Google. Please try again later. ' +
                                     'During the development phase, you can still test the application by using a Google account ' +
                                     'that is added as a test user in the Google Cloud Console.'
                        }), 403
                    return jsonify({
                        'status': 'error',
                        'message': 'Access was denied to Google Calendar. Please try again and make sure to grant the required permissions.'
                    }), 403

                return jsonify({
                    'status': 'error',
                    'message': f'Failed to authenticate with Google Calendar: {error}'
                }), 400

            # Verify state
            state = session.get('oauth_state')
            if not state:
                logger.error("No OAuth state found in session")
                logger.debug(f"Available session keys: {list(session.keys())}")
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid authentication state. Please try again.'
                }), 400

            logger.debug("Verifying OAuth2 callback")
            credentials_dict = calendar_service.verify_oauth2_callback(request.url, state)
            logger.debug("Successfully verified OAuth2 callback")

            # Store credentials in session
            session['google_credentials'] = credentials_dict
            logger.debug("Stored Google credentials in session")
            logger.debug("Authentication successful, redirecting to index")

            return redirect(url_for('index'))

        except Exception as e:
            logger.error(f"Error in OAuth callback: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Failed to complete Google Calendar authorization. Please try again.'
            }), 500

    @app.route('/api/calendar/event', methods=['POST'])
    def create_calendar_event():
        """Create calendar events from itinerary"""
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

            # Get the itinerary content and start date
            itinerary_content = data.get('itinerary_content')
            start_date = data.get('start_date')

            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()

            # Create the calendar events
            event_ids = calendar_service.create_calendar_events(
                session['google_credentials'],
                itinerary_content,
                start_date
            )

            logger.debug(f"Created {len(event_ids)} calendar events")
            return jsonify({
                'status': 'success',
                'event_ids': event_ids
            })

        except Exception as e:
            logger.error(f"Error creating calendar events: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': f'Failed to create calendar events: {str(e)}'
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

    @app.route('/api/calendar/oauth2callback/test', methods=['GET'])
    def test_oauth_callback():
        """Test endpoint to verify OAuth callback URL is accessible"""
        logger.debug("OAuth callback test endpoint accessed")
        return jsonify({
            'status': 'success',
            'message': 'OAuth callback URL is accessible',
            'timestamp': datetime.now().isoformat()
        })