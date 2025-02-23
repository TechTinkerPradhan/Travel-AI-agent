import os
import logging
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from flask import url_for

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CalendarService:
    def __init__(self):
        self.client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

        # Get domain from environment
        replit_slug = os.environ.get('REPLIT_SLUG')
        replit_id = os.environ.get('REPL_ID')
        if replit_slug and replit_id:
            self.replit_domain = f"{replit_slug}.{replit_id}.repl.co"
        else:
            self.replit_domain = '0.0.0.0:5000'

        logger.debug(f"Calendar Service initialized with:")
        logger.debug(f"- Client ID exists: {bool(self.client_id)}")
        logger.debug(f"- Client Secret exists: {bool(self.client_secret)}")
        logger.debug(f"- Replit domain: {self.replit_domain}")

        if not all([self.client_id, self.client_secret]):
            error_msg = "Missing required Google OAuth configuration: "
            if not self.client_id: error_msg += "GOOGLE_CLIENT_ID "
            if not self.client_secret: error_msg += "GOOGLE_CLIENT_SECRET "
            raise ValueError(error_msg.strip())

        self.SCOPES = ['https://www.googleapis.com/auth/calendar.events']

    def get_authorization_url(self):
        """Generate the authorization URL for Google OAuth2"""
        try:
            logger.debug("Starting Google Calendar authorization URL generation")
            logger.debug(f"Using Replit domain: {self.replit_domain}")

            # Create the flow instance
            flow = Flow.from_client_config(
                client_config={
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [f"https://{self.replit_domain}/api/calendar/oauth2callback"]
                    }
                },
                scopes=self.SCOPES
            )

            # Set the redirect URI
            redirect_uri = f"https://{self.replit_domain}/api/calendar/oauth2callback"
            logger.debug(f"Setting redirect URI: {redirect_uri}")
            flow.redirect_uri = redirect_uri

            # Generate authorization URL with offline access for refresh token
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'  # Force consent screen to always appear
            )

            logger.debug(f"Generated authorization URL: {authorization_url}")
            logger.debug(f"Generated state: {state}")
            return authorization_url, state

        except Exception as e:
            logger.error(f"Error generating authorization URL: {str(e)}", exc_info=True)
            raise

    def verify_oauth2_callback(self, request_url, session_state):
        """Verify and process the OAuth2 callback"""
        try:
            logger.debug("Processing OAuth2 callback")
            logger.debug(f"Request URL: {request_url}")
            logger.debug(f"Session state: {session_state}")

            # Create flow instance for verification
            flow = Flow.from_client_config(
                client_config={
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [f"https://{self.replit_domain}/api/calendar/oauth2callback"]
                    }
                },
                scopes=self.SCOPES,
                state=session_state
            )

            flow.redirect_uri = f"https://{self.replit_domain}/api/calendar/oauth2callback"
            authorization_response = request_url.replace('http://', 'https://')

            logger.debug("Fetching token from authorization response")
            flow.fetch_token(authorization_response=authorization_response)

            credentials = flow.credentials
            logger.debug("Successfully obtained credentials")

            return {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }

        except Exception as e:
            logger.error(f"Error processing OAuth callback: {str(e)}", exc_info=True)
            raise

    def parse_itinerary(self, content):
        """Parse markdown itinerary into structured day events"""
        logger.debug("Parsing itinerary content")
        days = []
        current_day = None
        current_activities = []

        # Split content into lines
        lines = content.split('\n')

        # Regular expressions for parsing
        day_pattern = r'##\s*Day\s*(\d+):\s*(.+)'
        time_pattern = r'(\d{1,2}:\d{2})'

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for new day
            day_match = re.search(day_pattern, line)
            if day_match:
                # Save previous day if exists
                if current_day and current_activities:
                    days.append({
                        'day_number': current_day['number'],
                        'title': current_day['title'],
                        'activities': current_activities.copy()
                    })

                # Start new day
                current_day = {
                    'number': int(day_match.group(1)),
                    'title': day_match.group(2).strip()
                }
                current_activities = []
                continue

            # Look for activities with times
            if current_day and line.startswith('-'):
                time_match = re.search(time_pattern, line)
                if time_match:
                    time = time_match.group(1)
                    activity = line[line.index('-')+1:].strip()
                    if time_match.start() > 0:
                        activity = line[line.index('-')+1:time_match.start()].strip()

                    # Extract location if in bold
                    location = None
                    location_match = re.search(r'\*\*(.+?)\*\*', activity)
                    if location_match:
                        location = location_match.group(1)

                    # Extract duration if in parentheses
                    duration = 60  # default duration in minutes
                    duration_match = re.search(r'\((\d+)\s*(?:min|hour)s?\)', activity)
                    if duration_match:
                        duration_str = duration_match.group(1)
                        if 'hour' in duration_match.group(0):
                            duration = int(duration_str) * 60
                        else:
                            duration = int(duration_str)

                    current_activities.append({
                        'time': time,
                        'description': activity,
                        'location': location,
                        'duration': duration
                    })

        # Add last day
        if current_day and current_activities:
            days.append({
                'day_number': current_day['number'],
                'title': current_day['title'],
                'activities': current_activities
            })

        logger.debug(f"Parsed {len(days)} days from itinerary")
        return days

    def create_calendar_events(self, credentials_dict, itinerary_content, start_date=None):
        """Create calendar events for each day in the itinerary"""
        try:
            # Parse the itinerary
            days = self.parse_itinerary(itinerary_content)

            # If no start date provided, use tomorrow
            if not start_date:
                start_date = datetime.now().date() + timedelta(days=1)

            # Create credentials and build service
            credentials = Credentials.from_authorized_user_info(credentials_dict, self.SCOPES)
            service = build('calendar', 'v3', credentials=credentials)

            created_events = []
            for day in days:
                day_date = start_date + timedelta(days=day['day_number'] - 1)

                for activity in day['activities']:
                    # Parse time and create datetime
                    time_parts = activity['time'].split(':')
                    start_datetime = datetime.combine(
                        day_date,
                        datetime.strptime(activity['time'], '%H:%M').time()
                    )

                    # Calculate end time based on duration
                    end_datetime = start_datetime + timedelta(minutes=activity['duration'])

                    # Create event
                    event = {
                        'summary': f"Day {day['day_number']}: {activity['description']}",
                        'location': activity['location'],
                        'description': f"Part of Day {day['day_number']}: {day['title']}\n\n{activity['description']}",
                        'start': {
                            'dateTime': start_datetime.isoformat(),
                            'timeZone': 'UTC'
                        },
                        'end': {
                            'dateTime': end_datetime.isoformat(),
                            'timeZone': 'UTC'
                        }
                    }

                    created_event = service.events().insert(calendarId='primary', body=event).execute()
                    created_events.append(created_event['id'])
                    logger.debug(f"Created calendar event: {created_event['id']}")

            return created_events

        except Exception as e:
            logger.error(f"Error creating calendar events: {str(e)}", exc_info=True)
            raise

    def create_event(self, credentials_dict, event_details):
        """Create a calendar event using the provided credentials and event details"""
        try:
            credentials = Credentials.from_authorized_user_info(credentials_dict, self.SCOPES)
            service = build('calendar', 'v3', credentials=credentials)

            event = {
                'summary': event_details.get('summary', 'Travel Itinerary'),
                'location': event_details.get('location', ''),
                'description': event_details.get('description', ''),
                'start': {
                    'dateTime': event_details['start']['dateTime'],
                    'timeZone': event_details['start']['timeZone'],
                },
                'end': {
                    'dateTime': event_details['end']['dateTime'],
                    'timeZone': event_details['end']['timeZone'],
                }
            }

            event = service.events().insert(calendarId='primary', body=event).execute()
            return event.get('id')

        except Exception as e:
            logging.error(f"Error creating calendar event: {str(e)}")
            raise