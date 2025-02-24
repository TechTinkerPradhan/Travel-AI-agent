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
        # Use environment variables without default values to ensure they are required
        self.client_id = os.environ['GOOGLE_CALENDAR_CLIENT_ID']
        self.client_secret = os.environ['GOOGLE_CALENDAR_CLIENT_SECRET']
        self.replit_domain = "ai-travel-buddy-bboyswagat.replit.app"

        # Check if credentials exist and log more details for debugging
        logger.debug("CalendarService initialization attempt:")
        logger.debug(f" - Calendar Client ID length: {len(self.client_id)}")
        logger.debug(f" - Calendar Secret length: {len(self.client_secret)}")
        logger.debug(f" - Domain: {self.replit_domain}")

        # Validate credentials
        self.is_available = bool(self.client_id and self.client_secret)
        if not self.is_available:
            missing = []
            if not self.client_id:
                missing.append("GOOGLE_CALENDAR_CLIENT_ID")
            if not self.client_secret:
                missing.append("GOOGLE_CALENDAR_CLIENT_SECRET")
            logger.error(f"Missing credentials: {', '.join(missing)}")
        else:
            logger.info("Calendar service initialized successfully")

        # Define Google Calendar scopes
        self.SCOPES = ['https://www.googleapis.com/auth/calendar.events']

    def check_availability(self):
        """Check if Google Calendar service is available"""
        logger.debug("Checking calendar service availability")
        if not self.is_available:
            logger.error("Calendar service unavailable - missing credentials")
            return False
        return True

    def get_authorization_url(self):
        """Generate the Google OAuth2 authorization URL."""
        if not self.check_availability():
            raise ValueError("Calendar service is not configured - missing credentials")

        logger.debug("Generating Google Calendar OAuth URL...")

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
                include_granted_scopes='true',
                prompt='consent'
            )

            logger.debug("Successfully generated authorization URL")
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