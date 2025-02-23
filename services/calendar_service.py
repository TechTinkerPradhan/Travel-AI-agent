import os
import logging
import re
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from flask import url_for

# Configure logging
logger = logging.getLogger(__name__)

class CalendarService:
    def __init__(self):
        self.client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        self.replit_domain = os.environ.get('REPLIT_SLUG', '')  # Changed from REPLIT_DOMAIN

        if not all([self.client_id, self.client_secret]):
            raise ValueError("Google OAuth credentials are not properly configured")

        logger.debug(f"Calendar Service initialized with domain: {self.replit_domain}")
        self.SCOPES = ['https://www.googleapis.com/auth/calendar.events']

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

    def get_authorization_url(self):
        """Generate the authorization URL for Google OAuth2"""
        try:
            # Get the full domain including the .repl.co suffix
            full_domain = f"{self.replit_domain}.repl.co" if self.replit_domain else None
            logger.debug(f"Using redirect domain: {full_domain}")

            if not full_domain:
                raise ValueError("Replit domain not properly configured")

            # Create the flow using the client secrets
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [f"https://{full_domain}/api/calendar/oauth2callback"]
                    }
                },
                scopes=self.SCOPES
            )

            # Set the redirect URI to use HTTPS
            flow.redirect_uri = f"https://{full_domain}/api/calendar/oauth2callback"

            # Generate the authorization URL
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )

            logger.debug(f"Generated authorization URL: {authorization_url}")
            return authorization_url, state

        except Exception as e:
            logger.error(f"Error generating authorization URL: {str(e)}")
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