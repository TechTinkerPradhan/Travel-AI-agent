import os
import logging
import re
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CalendarService:
    def __init__(self):
        """Initialize Google Calendar OAuth configuration"""
        # Explicitly set domain to match Google Cloud Console configuration
        self.replit_domain = "ai-travel-buddy-bboyswagat.replit.app"

        logger.debug("=== Calendar Service Initialization ===")
        logger.debug(f"Using domain: {self.replit_domain}")

        # Use .get() with empty string defaults for safety
        self.client_id = os.environ.get('GOOGLE_CALENDAR_CLIENT_ID', '').strip()
        self.client_secret = os.environ.get('GOOGLE_CALENDAR_CLIENT_SECRET', '').strip()

        # Log credential information safely (only lengths)
        logger.debug(f"Client ID length: {len(self.client_id)}")
        logger.debug(f"Client Secret length: {len(self.client_secret)}")

        # Enhanced credential validation
        self.validate_credentials()

        # Define Google Calendar scopes
        self.SCOPES = ['https://www.googleapis.com/auth/calendar.events']

    def validate_credentials(self):
        """Validate the format and presence of credentials"""
        logger.debug("Starting credential validation...")

        # Check credential presence
        if not self.client_id:
            logger.error("GOOGLE_CALENDAR_CLIENT_ID is missing or empty")
            self.is_available = False
            return

        if not self.client_secret:
            logger.error("GOOGLE_CALENDAR_CLIENT_SECRET is missing or empty")
            self.is_available = False
            return

        # Validate Client ID format
        if not self.client_id.endswith('.apps.googleusercontent.com'):
            logger.error(f"Invalid Client ID format - must end with .apps.googleusercontent.com")
            logger.debug(f"Client ID ending: ...{self.client_id[-30:] if len(self.client_id) > 30 else self.client_id}")
            self.is_available = False
            return

        logger.info("✓ Calendar credentials validated successfully")
        self.is_available = True

    def check_availability(self):
        """Check if Google Calendar service is available"""
        if not self.is_available:
            logger.error("Calendar service unavailable - invalid or missing credentials")
            return False
        return True

    def get_authorization_url(self):
        """Generate the Google OAuth2 authorization URL."""
        if not self.check_availability():
            raise ValueError("Calendar service is not configured - invalid or missing credentials")

        redirect_uri = f"https://{self.replit_domain}/auth/google_callback"
        logger.debug(f"Using redirect URI: {redirect_uri}")

        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }

        try:
            flow = Flow.from_client_config(client_config, scopes=self.SCOPES)
            flow.redirect_uri = redirect_uri

            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='false',
                prompt='consent'
            )

            logger.info("✓ Successfully generated authorization URL")
            return authorization_url, state
        except Exception as e:
            logger.error(f"Error generating authorization URL: {str(e)}")
            raise

    def verify_oauth2_callback(self, request_url, session_state):
        """Handle the callback from Google with authorization code"""
        if not self.check_availability():
            raise ValueError("Calendar service is not configured - missing credentials")

        redirect_uri = f"https://{self.replit_domain}/auth/google_callback"
        logger.debug(f"Processing OAuth callback with redirect URI: {redirect_uri}")

        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }

        try:
            flow = Flow.from_client_config(
                client_config,
                scopes=self.SCOPES,
                state=session_state
            )
            flow.redirect_uri = redirect_uri

            # Ensure request URL is properly formatted
            if request_url.startswith('http://'):
                request_url = 'https://' + request_url[7:]

            logger.debug(f"Fetching token with authorization response URL")
            flow.fetch_token(authorization_response=request_url)
            creds = flow.credentials

            logger.info("Successfully obtained OAuth credentials")
            return {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            }
        except Exception as e:
            logger.error(f"Error in OAuth callback: {str(e)}")
            raise

    def create_calendar_events(self,
                               credentials_dict,
                               itinerary_content,
                               start_date=None):
        """Create Google Calendar events from an itinerary"""
        if not self.is_available:
            raise ValueError(
                "Calendar service is not configured - missing credentials")

        # Parse the itinerary
        days = self.parse_itinerary(itinerary_content)

        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_dt = datetime.now().date()

        # Authenticate with Google Calendar
        creds = Credentials.from_authorized_user_info(credentials_dict,
                                                      self.SCOPES)
        service = build('calendar', 'v3', credentials=creds)

        created_ids = []
        for day in days:
            day_date = start_dt + timedelta(days=day['day_number'] - 1)
            for activity in day['activities']:
                hh, mm = map(int, activity['time'].split(':'))
                event_start = datetime(day_date.year, day_date.month,
                                       day_date.day, hh, mm)
                event_end = event_start + timedelta(
                    minutes=activity['duration'])

                event_body = {
                    'summary':
                    f"Day {day['day_number']}: {activity['description']}",
                    'location': activity['location'] or '',
                    'description':
                    f"Part of Day {day['day_number']}: {day['title']}",
                    'start': {
                        'dateTime': event_start.isoformat(),
                        'timeZone': 'UTC'
                    },
                    'end': {
                        'dateTime': event_end.isoformat(),
                        'timeZone': 'UTC'
                    }
                }

                created_event = service.events().insert(
                    calendarId='primary', body=event_body).execute()
                created_ids.append(created_event['id'])

        return created_ids

    def parse_itinerary(self, content):
        """
        Parses a Markdown itinerary with lines like:
          ## Day 1: Tokyo
          - 09:00 Visit Shibuya (2 hours)
        Returns structured event data.
        """
        days = []
        current_day = None
        current_activities = []

        lines = content.split('\n')
        day_pattern = r'##\s*Day\s*(\d+):\s*(.+)'
        time_pattern = r'(\d{1,2}:\d{2})'

        for line in lines:
            line = line.strip()
            if not line:
                continue

            day_match = re.search(day_pattern, line)
            if day_match:
                if current_day and current_activities:
                    days.append({
                        'day_number': current_day['number'],
                        'title': current_day['title'],
                        'activities': current_activities.copy()
                    })
                current_day = {
                    'number': int(day_match.group(1)),
                    'title': day_match.group(2).strip()
                }
                current_activities = []
                continue

            if current_day and line.startswith('-'):
                match_time = re.search(time_pattern, line)
                if match_time:
                    t = match_time.group(1)
                    activity_text = line[line.index('-') + 1:].strip()
                    location_match = re.search(r'\*\*([^*]+)\*\*',
                                               activity_text)
                    location = location_match.group(
                        1) if location_match else None
                    duration = 60  # Default

                    duration_match = re.search(
                        r'\((\d+)\s*(?:hour|hours|min|minutes)\)',
                        activity_text, re.IGNORECASE)
                    if duration_match:
                        val = int(duration_match.group(1))
                        duration = val * 60 if 'hour' in duration_match.group(
                            0).lower() else val

                    if location:
                        activity_text = activity_text.replace(
                            f"**{location}**", "").strip()
                    activity_text = re.sub(r'\([^)]*\)', '',
                                           activity_text).strip()

                    current_activities.append({
                        'time': t,
                        'description': activity_text,
                        'location': location,
                        'duration': duration
                    })

        if current_day and current_activities:
            days.append({
                'day_number': current_day['number'],
                'title': current_day['title'],
                'activities': current_activities
            })

        return days

    def get_configuration_error(self):
        """Get detailed error message about configuration issues"""
        if not self.client_id:
            return "Google Calendar Client ID is missing"
        if not self.client_secret:
            return "Google Calendar Client Secret is missing"
        if not self.client_id.endswith('.apps.googleusercontent.com'):
            return "Invalid Google Calendar Client ID format"
        return "Unknown configuration error"