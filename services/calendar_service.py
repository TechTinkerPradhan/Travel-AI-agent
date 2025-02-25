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
            logger.debug(f"Starting calendar event creation for user: {user_email}")
            logger.debug(f"Raw itinerary content: {itinerary_content[:100]}...")  # Log first 100 chars

            if 'google_calendar_credentials' not in session:
                raise ValueError("Google Calendar credentials not found in session")

            creds = Credentials.from_authorized_user_info(session['google_calendar_credentials'], self.SCOPES)
            service = build('calendar', 'v3', credentials=creds)

            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            events = []

            # Split by day markers and remove empty strings
            days = [day.strip() for day in itinerary_content.split('## Day') if day.strip()]
            logger.debug(f"Found {len(days)} days in itinerary")

            for day_content in days:
                try:
                    # Extract day number
                    day_match = re.match(r'(\d+):', day_content)
                    if not day_match:
                        logger.warning(f"Could not find day number in: {day_content[:50]}...")
                        continue

                    day_num = int(day_match.group(1))
                    current_date = start_dt + timedelta(days=day_num - 1)
                    logger.debug(f"Processing Day {day_num}")

                    # Find all activities (lines starting with dash and containing time)
                    activity_lines = [line.strip() for line in day_content.split('\n') 
                                   if line.strip().startswith('-') and re.search(r'\d{1,2}:\d{2}', line)]

                    logger.debug(f"Found {len(activity_lines)} activities for Day {day_num}")
                    for activity_line in activity_lines:
                        try:
                            # Extract time
                            time_match = re.search(r'(\d{1,2}):(\d{2})', activity_line)
                            if not time_match:
                                continue

                            hour = int(time_match.group(1))
                            minute = int(time_match.group(2))

                            # Get the description (everything after the time)
                            desc_start = activity_line.find(':') + 1
                            activity_desc = activity_line[desc_start:].strip()

                            # Create event datetime
                            event_time = datetime(
                                current_date.year,
                                current_date.month,
                                current_date.day,
                                hour,
                                minute
                            )

                            # Parse duration if present
                            duration = 60  # Default 1 hour
                            duration_match = re.search(r'\((\d+)\s*(hour|min|minutes?)?s?\)', activity_desc)
                            if duration_match:
                                amount = int(duration_match.group(1))
                                unit = duration_match.group(2) or 'min'
                                duration = amount * 60 if 'hour' in unit else amount
                                activity_desc = re.sub(r'\([^)]*\)', '', activity_desc)

                            # Extract location if present
                            location = ''
                            loc_match = re.search(r'\*\*([^*]+)\*\*', activity_desc)
                            if loc_match:
                                location = loc_match.group(1)
                                activity_desc = activity_desc.replace(f"**{location}**", "")

                            # Format title as shown in screenshot
                            time_str = f"{hour:02d}:{minute:02d}"
                            event_title = f"Day {day_num}: {time_str}: {activity_desc.strip()}"

                            event = {
                                'summary': event_title,
                                'location': location,
                                'description': f"Part of Day {day_num}",
                                'start': {
                                    'dateTime': event_time.isoformat(),
                                    'timeZone': 'UTC'
                                },
                                'end': {
                                    'dateTime': (event_time + timedelta(minutes=duration)).isoformat(),
                                    'timeZone': 'UTC'
                                },
                                'attendees': [{'email': user_email}],
                                'reminders': {
                                    'useDefault': False,
                                    'overrides': [
                                        {'method': 'popup', 'minutes': 30}
                                    ]
                                },
                                'transparency': 'transparent'
                            }

                            created_event = service.events().insert(
                                calendarId='primary',
                                body=event,
                                sendUpdates='none'
                            ).execute()

                            logger.debug(f"Created event: {event_title}")
                            events.append({
                                'id': created_event['id'],
                                'summary': created_event['summary'],
                                'start': created_event['start']['dateTime'],
                                'end': created_event['end']['dateTime']
                            })

                        except Exception as e:
                            logger.error(f"Error processing activity: {str(e)}")
                            continue

                except Exception as e:
                    logger.error(f"Error processing day: {str(e)}")
                    continue

            if not events:
                raise ValueError("No events could be created. Please check the itinerary format.")

            logger.debug(f"Successfully created {len(events)} calendar events")
            return events

        except Exception as e:
            logger.error(f"Error in create_events_from_plan: {str(e)}")
            raise ValueError(str(e))

    def check_availability(self):
        return self.is_available

    def get_authorization_url(self):
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

        try:
            flow = Flow.from_client_config(
                client_config,
                scopes=self.SCOPES,
                state=session_state
            )
            flow.redirect_uri = redirect_uri

            if request_url.startswith('http://'):
                request_url = 'https://' + request_url[7:]

            flow.fetch_token(authorization_response=request_url)
            creds = flow.credentials

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
        if not self.client_id:
            return "Google Calendar Client ID is missing"
        if not self.client_secret:
            return "Google Calendar Client Secret is missing"
        return "Unknown configuration error"