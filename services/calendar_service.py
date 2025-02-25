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
        self.replit_domain = "ai-travel-buddy-bboyswagat.replit.app"
        self.client_id = os.environ.get('GOOGLE_CALENDAR_CLIENT_ID', '').strip()
        self.client_secret = os.environ.get('GOOGLE_CALENDAR_CLIENT_SECRET', '').strip()
        self.SCOPES = ['https://www.googleapis.com/auth/calendar.events']
        self.is_available = bool(self.client_id and self.client_secret)

    def create_events_from_plan(self, itinerary_content: str, start_date: str, user_email: str) -> list:
        """Create calendar events from an itinerary"""
        try:
            logger.debug("Starting calendar event creation")
            logger.debug(f"Processing itinerary for start date: {start_date}")

            # Get credentials from session
            if 'google_calendar_credentials' not in session:
                raise ValueError("Google Calendar credentials not found in session")

            credentials = session['google_calendar_credentials']
            creds = Credentials.from_authorized_user_info(credentials, self.SCOPES)
            service = build('calendar', 'v3', credentials=creds)

            # Parse days and events
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            events = []

            # Split content into days
            days = itinerary_content.split('## Day')
            for day_content in days[1:]:  # Skip first empty split
                try:
                    # Extract day number
                    day_num = int(day_content.split(':')[0].strip())
                    current_date = start_dt + timedelta(days=day_num - 1)

                    # Find all time-based activities
                    activities = re.findall(r'-\s*(\d{1,2}:\d{2}):\s*(.+?)(?=(?:-\s*\d{1,2}:\d{2}:|$))', day_content, re.DOTALL)

                    for time_str, activity_desc in activities:
                        try:
                            # Parse time
                            hour, minute = map(int, time_str.split(':'))

                            # Create event start time
                            event_time = datetime(
                                current_date.year,
                                current_date.month,
                                current_date.day,
                                hour,
                                minute
                            )

                            # Default duration 1 hour
                            duration = 60
                            if '(' in activity_desc and ')' in activity_desc:
                                duration_match = re.search(r'\((\d+)\s*(hour|min|minutes)?s?\)', activity_desc)
                                if duration_match:
                                    amount = int(duration_match.group(1))
                                    unit = duration_match.group(2) or 'min'
                                    duration = amount * 60 if 'hour' in unit else amount

                            # Clean up description
                            description = re.sub(r'\([^)]*\)', '', activity_desc).strip()

                            # Extract location if present
                            location = ''
                            loc_match = re.search(r'\*\*([^*]+)\*\*', description)
                            if loc_match:
                                location = loc_match.group(1)
                                description = description.replace(f"**{location}**", "").strip()

                            # Create calendar event
                            event = {
                                'summary': description,
                                'location': location,
                                'description': f"Day {day_num} activity",
                                'start': {
                                    'dateTime': event_time.isoformat(),
                                    'timeZone': 'UTC',
                                },
                                'end': {
                                    'dateTime': (event_time + timedelta(minutes=duration)).isoformat(),
                                    'timeZone': 'UTC',
                                },
                                'attendees': [{'email': user_email}],
                                'reminders': {'useDefault': True}
                            }

                            logger.debug(f"Creating event: {event['summary']} at {event['start']['dateTime']}")
                            created_event = service.events().insert(
                                calendarId='primary',
                                body=event,
                                sendUpdates='all'
                            ).execute()

                            events.append({
                                'id': created_event['id'],
                                'summary': created_event['summary'],
                                'start': created_event['start']['dateTime'],
                                'end': created_event['end']['dateTime']
                            })

                        except Exception as activity_error:
                            logger.error(f"Error creating event: {str(activity_error)}")
                            continue

                except Exception as day_error:
                    logger.error(f"Error processing day: {str(day_error)}")
                    continue

            logger.debug(f"Successfully created {len(events)} calendar events")
            return events

        except Exception as e:
            logger.error(f"Error in create_events_from_plan: {str(e)}")
            raise ValueError(f"Failed to create calendar events: {str(e)}")

    def check_availability(self):
        """Check if Google Calendar service is available"""
        return self.is_available

    def get_authorization_url(self):
        """Generate the Google OAuth2 authorization URL."""
        if not self.check_availability():
            raise ValueError("Calendar service is not configured")

        redirect_uri = f"https://{self.replit_domain}/auth/google_callback"
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

        return authorization_url, state

    def verify_oauth2_callback(self, request_url, session_state):
        """Handle the callback from Google with authorization code"""
        if not self.check_availability():
            raise ValueError("Calendar service is not configured")

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

    def get_configuration_error(self):
        """Get error message about configuration issues"""
        if not self.client_id:
            return "Google Calendar Client ID is missing"
        if not self.client_secret:
            return "Google Calendar Client Secret is missing"
        return "Unknown configuration error"