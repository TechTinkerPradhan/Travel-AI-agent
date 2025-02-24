# services/calendar_service.py

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
        self.client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

        # HARD-CODE your Replit domain to match the one in Google OAuth
        # This way, your redirect URIs always match exactly:
        self.replit_domain = "ai-travel-buddy-bboyswagat.replit.app"

        logger.debug("CalendarService initialized with:")
        logger.debug(f" - Client ID: {bool(self.client_id)}")
        logger.debug(f" - Client Secret: {bool(self.client_secret)}")
        logger.debug(f" - Domain: {self.replit_domain}")

        if not all([self.client_id, self.client_secret]):
            raise ValueError(
                "Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET in env")

        self.SCOPES = ['https://www.googleapis.com/auth/calendar.events']

    def get_authorization_url(self):
        """Generate the Google OAuth2 authorization URL."""
        logger.debug("Generating Google Calendar auth URL...")

        redirect_uri = f"https://{self.replit_domain}/api/calendar/oauth2callback"
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
            prompt='consent')

        # Force HTTPS if needed (rarely needed, but kept for safety)
        if authorization_url.startswith('http://'):
            authorization_url = 'https://' + authorization_url[7:]

        return authorization_url, state

    def verify_oauth2_callback(self, request_url, session_state):
        """Handle the callback from Google with ?code=..."""
        logger.debug(
            f"Verifying OAuth callback. request_url={request_url}, state={session_state}"
        )

        redirect_uri = f"https://{self.replit_domain}/api/calendar/oauth2callback"
        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }

        flow = Flow.from_client_config(client_config,
                                       scopes=self.SCOPES,
                                       state=session_state)
        flow.redirect_uri = redirect_uri

        # Force https if needed
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

    def parse_itinerary(self, content):
        """
        Parse a Markdown-based itinerary with lines like:
          ## Day 1: Tokyo
          - 09:00 Visit Shibuya (2 hours)
        Return a list of {day_number, title, activities: [...]} 
        where each activity has {time, description, location, duration}.
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

            # Check for a new day
            day_match = re.search(day_pattern, line)
            if day_match:
                # If we already had a day in progress, save it
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

            # If it's an activity line
            if current_day and line.startswith('-'):
                match_time = re.search(time_pattern, line)
                if match_time:
                    t = match_time.group(1)
                    activity_text = line[line.index('-') + 1:].strip()

                    # Extract location if in **bold**
                    loc_match = re.search(r'\*\*([^*]+)\*\*', activity_text)
                    location = loc_match.group(1) if loc_match else None

                    # Extract duration (e.g., "(2 hours)" or "(45 min)")
                    duration = 60  # default
                    dur_match = re.search(
                        r'\((\d+)\s*(?:hour|hours|min|minutes)\)',
                        activity_text, re.IGNORECASE)
                    if dur_match:
                        val = int(dur_match.group(1))
                        if 'hour' in dur_match.group(0).lower():
                            duration = val * 60
                        else:
                            duration = val

                    # Clean up location and durations from text
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

        # Final day
        if current_day and current_activities:
            days.append({
                'day_number': current_day['number'],
                'title': current_day['title'],
                'activities': current_activities
            })

        return days

    async def create_calendar_preview(self,
                                      itinerary_content: str,
                                      start_date: str = None):
        """
        Return a list of events for preview. 
        Not actually adding them to Google Calendar, just letting the user see.
        """
        days = self.parse_itinerary(itinerary_content)
        preview_events = []

        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start_dt = datetime.now()

        for day in days:
            for activity in day['activities']:
                # Format the activity duration
                d = activity['duration']
                if d >= 60:
                    hrs = d // 60
                    mins = d % 60
                    duration_str = f"{hrs} hour{'s' if hrs>1 else ''}"
                    if mins:
                        duration_str += f" {mins} min"
                else:
                    duration_str = f"{d} min"

                preview_events.append({
                    'day_number': day['day_number'],
                    'day_title': day['title'],
                    'description': activity['description'],
                    'location': activity['location'],
                    'start_time': activity['time'],
                    'duration': duration_str
                })

        return preview_events

    def create_calendar_events(self,
                               credentials_dict,
                               itinerary_content,
                               start_date=None):
        """
        Actually create events in the user's Google Calendar. 
        Returns a list of created event IDs.
        """
        days = self.parse_itinerary(itinerary_content)
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_dt = datetime.now().date()

        creds = Credentials.from_authorized_user_info(credentials_dict,
                                                      self.SCOPES)
        service = build('calendar', 'v3', credentials=creds)

        created_ids = []
        for day in days:
            day_date = start_dt + timedelta(days=day['day_number'] - 1)
            for activity in day['activities']:
                # Convert the 'HH:MM' to integer hours & minutes
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