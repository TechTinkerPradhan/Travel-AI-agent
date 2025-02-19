import os
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from flask import url_for

class CalendarService:
    def __init__(self):
        self.client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        self.replit_domain = os.environ.get('REPLIT_DOMAIN')

        if not all([self.client_id, self.client_secret]):
            raise ValueError("Google OAuth credentials are not properly configured")

        self.SCOPES = ['https://www.googleapis.com/auth/calendar.events']

    def get_authorization_url(self):
        """Generate the authorization URL for Google OAuth2"""
        try:
            # Create the flow using the client secrets
            flow = Flow.from_client_config(
                {
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

            # Set the redirect URI to use HTTPS
            flow.redirect_uri = f"https://{self.replit_domain}/api/calendar/oauth2callback"

            # Generate the authorization URL
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )

            return authorization_url, state

        except Exception as e:
            logging.error(f"Error generating authorization URL: {str(e)}")
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