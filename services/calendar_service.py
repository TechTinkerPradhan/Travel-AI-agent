import os
import logging
import re
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from flask import session

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CalendarService:
    def __init__(self):
        """Initialize Google Calendar OAuth configuration"""
        self.replit_domain = "ai-travel-buddy-bboyswagat.replit.app"

        logger.debug("=== Calendar Service Initialization ===")
        logger.debug(f"Using domain: {self.replit_domain}")

        try:
            self.client_id = os.environ.get('GOOGLE_CALENDAR_CLIENT_ID', '').strip()
            self.client_secret = os.environ.get('GOOGLE_CALENDAR_CLIENT_SECRET', '').strip()

            logger.debug(f"Client ID length: {len(self.client_id)}")
            logger.debug(f"Client Secret length: {len(self.client_secret)}")

            self.validate_credentials()

            self.SCOPES = [
                'https://www.googleapis.com/auth/calendar.events',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile',
                'openid'
            ]
        except Exception as e:
            logger.error(f"Error initializing calendar service: {str(e)}")
            self.is_available = False

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

    def create_events_from_plan(self, itinerary_content: str, start_date: str, user_email: str) -> list:
        """Create calendar events from an itinerary"""
        if not self.is_available:
            raise ValueError("Calendar service is not configured - missing credentials")

        try:
            # Parse the itinerary into days and activities
            days = self.parse_itinerary(itinerary_content)
            if not days:
                raise ValueError("No valid itinerary days found in content")

            # Convert start_date to datetime
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()

            # Get credentials from session
            if 'google_calendar_credentials' not in session:
                raise ValueError("Google Calendar credentials not found in session")

            creds = Credentials.from_authorized_user_info(
                session['google_calendar_credentials'],
                self.SCOPES
            )

            # Initialize Calendar API service
            service = build('calendar', 'v3', credentials=creds)

            created_events = []

            # Create events for each activity
            for day in days:
                current_date = start_dt + timedelta(days=day['day_number'] - 1)

                for activity in day['activities']:
                    try:
                        # Parse time
                        time_parts = activity['time'].split(':')
                        hours = int(time_parts[0])
                        minutes = int(time_parts[1])

                        # Create event start time
                        event_start = datetime(
                            current_date.year,
                            current_date.month,
                            current_date.day,
                            hours,
                            minutes
                        )

                        # Calculate event end time based on duration
                        duration_minutes = activity.get('duration', 60)  # Default 1 hour
                        event_end = event_start + timedelta(minutes=duration_minutes)

                        # Create event
                        event = {
                            'summary': activity['description'],
                            'location': activity.get('location', ''),
                            'description': f"Day {day['day_number']} of your trip\n{activity['description']}",
                            'start': {
                                'dateTime': event_start.isoformat(),
                                'timeZone': 'UTC'
                            },
                            'end': {
                                'dateTime': event_end.isoformat(),
                                'timeZone': 'UTC'
                            },
                            'attendees': [{'email': user_email}],
                            'reminders': {
                                'useDefault': True
                            }
                        }

                        # Insert event
                        created_event = service.events().insert(
                            calendarId='primary',
                            body=event,
                            sendUpdates='all'
                        ).execute()

                        created_events.append({
                            'id': created_event['id'],
                            'summary': created_event['summary'],
                            'start': created_event['start']['dateTime'],
                            'end': created_event['end']['dateTime']
                        })

                        logger.debug(f"Created event: {created_event['summary']}")

                    except Exception as event_error:
                        logger.error(f"Error creating event: {str(event_error)}")
                        continue

            return created_events

        except Exception as e:
            logger.error(f"Error creating calendar events: {str(e)}")
            raise ValueError(f"Failed to create calendar events: {str(e)}")

    def parse_itinerary(self, content: str) -> list:
        """Parse a markdown itinerary into structured data"""
        try:
            days = []
            current_day = None
            current_activities = []

            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue

                # Match day header
                day_match = re.search(r'##\s*Day\s*(\d+):', line)
                if day_match:
                    if current_day and current_activities:
                        days.append({
                            'day_number': current_day,
                            'activities': current_activities.copy()
                        })
                    current_day = int(day_match.group(1))
                    current_activities = []
                    continue

                # Match activity line
                if current_day and line.startswith('-'):
                    # Extract time
                    time_match = re.search(r'(\d{1,2}:\d{2})', line)
                    if time_match:
                        time = time_match.group(1)

                        # Extract activity text
                        activity_text = line[line.index('-') + 1:].strip()

                        # Extract location (if any)
                        location = None
                        location_match = re.search(r'\*\*([^*]+)\*\*', activity_text)
                        if location_match:
                            location = location_match.group(1)
                            activity_text = activity_text.replace(f"**{location}**", "")

                        # Extract duration
                        duration = 60  # Default 1 hour
                        duration_match = re.search(r'\((\d+)\s*(?:hour|hours|min|minutes)\)', activity_text)
                        if duration_match:
                            duration_value = int(duration_match.group(1))
                            if 'hour' in duration_match.group(0).lower():
                                duration = duration_value * 60
                            else:
                                duration = duration_value
                            activity_text = re.sub(r'\([^)]*\)', '', activity_text)

                        activity = {
                            'time': time,
                            'description': activity_text.strip(),
                            'location': location,
                            'duration': duration
                        }
                        current_activities.append(activity)

            # Add the last day
            if current_day and current_activities:
                days.append({
                    'day_number': current_day,
                    'activities': current_activities
                })

            return days

        except Exception as e:
            logger.error(f"Error parsing itinerary: {str(e)}")
            return []

    def get_authorization_url(self):
        """Generate the Google OAuth2 authorization URL."""
        if not self.check_availability():
            raise ValueError("Calendar service is not configured - invalid or missing credentials")

        redirect_uri = f"https://{self.replit_domain}/auth/google_callback"
        logger.debug(f"Using redirect URI: {redirect_uri}")

        try:
            client_config = {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            }

            flow = Flow.from_client_config(client_config, scopes=self.SCOPES)
            flow.redirect_uri = redirect_uri

            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
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

    def get_configuration_error(self):
        """Get detailed error message about configuration issues"""
        if not self.client_id:
            return "Google Calendar Client ID is missing"
        if not self.client_secret:
            return "Google Calendar Client Secret is missing"
        if not self.client_id.endswith('.apps.googleusercontent.com'):
            return "Invalid Google Calendar Client ID format"
        return "Unknown configuration error"