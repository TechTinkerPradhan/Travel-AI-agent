import os
import logging
from typing import Dict, List, Optional
from pyairtable import Table

class AirtableService:
    def __init__(self):
        self.access_token = os.environ.get("AIRTABLE_ACCESS_TOKEN")
        self.base_id = os.environ.get("AIRTABLE_BASE_ID")

        if not self.access_token or not self.base_id:
            logging.error("Missing Airtable credentials")
            raise ValueError(
                "Airtable access token and base ID are required. "
                "Please ensure AIRTABLE_ACCESS_TOKEN and AIRTABLE_BASE_ID "
                "environment variables are set."
            )

        # Define table names
        self.USER_PREFERENCES = "User Preferences"
        self.TRAVEL_ITINERARIES = "Travel Itineraries"
        self.TRAVEL_ACTIVITIES = "Travel Activities"

        try:
            # Initialize tables with personal access token
            self.preferences_table = Table(self.access_token, self.base_id, self.USER_PREFERENCES)
            self.itineraries_table = Table(self.access_token, self.base_id, self.TRAVEL_ITINERARIES)
            self.activities_table = Table(self.access_token, self.base_id, self.TRAVEL_ACTIVITIES)
        except Exception as e:
            logging.error(f"Failed to initialize Airtable tables: {str(e)}")
            raise

    def save_user_preferences(self, user_id: str, preferences: Dict) -> Dict:
        """
        Save or update user preferences in Airtable
        """
        try:
            # Check if user already exists
            existing_records = self.preferences_table.all(formula=f"{{UserID}} = '{user_id}'")

            if existing_records:
                # Update existing record
                record_id = existing_records[0]['id']
                return self.preferences_table.update(record_id, {
                    'UserID': user_id,
                    'Budget': preferences.get('budget'),
                    'TravelStyle': preferences.get('travelStyle'),
                    'LastUpdated': 'NOW()'
                })
            else:
                # Create new record
                return self.preferences_table.create({
                    'UserID': user_id,
                    'Budget': preferences.get('budget'),
                    'TravelStyle': preferences.get('travelStyle'),
                    'LastUpdated': 'NOW()'
                })
        except Exception as e:
            logging.error(f"Error saving user preferences: {str(e)}")
            raise

    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """
        Retrieve user preferences from Airtable
        """
        try:
            records = self.preferences_table.all(formula=f"{{UserID}} = '{user_id}'")
            if records:
                record = records[0]['fields']
                return {
                    'budget': record.get('Budget'),
                    'travelStyle': record.get('TravelStyle')
                }
            return None
        except Exception as e:
            logging.error(f"Error retrieving user preferences: {str(e)}")
            raise

    def save_travel_itinerary(self, user_id: str, itinerary_data: Dict) -> Dict:
        """
        Save a travel itinerary and its associated activities
        """
        try:
            # Create the main itinerary record
            itinerary = self.itineraries_table.create({
                'UserID': user_id,
                'Destination': itinerary_data.get('destination'),
                'StartDate': itinerary_data.get('startDate'),
                'EndDate': itinerary_data.get('endDate'),
                'Status': 'Active'
            })

            # Create associated activities
            activities = itinerary_data.get('activities', [])
            for activity in activities:
                self.activities_table.create({
                    'ItineraryID': [itinerary['id']],  # Link to parent record
                    'Name': activity.get('name'),
                    'Description': activity.get('description'),
                    'Date': activity.get('date'),
                    'EstimatedCost': activity.get('cost')
                })

            return itinerary
        except Exception as e:
            logging.error(f"Error saving travel itinerary: {str(e)}")
            raise

    def get_user_itineraries(self, user_id: str) -> List[Dict]:
        """
        Retrieve all itineraries for a user
        """
        try:
            itineraries = self.itineraries_table.all(formula=f"{{UserID}} = '{user_id}'")
            result = []

            for itinerary in itineraries:
                itinerary_id = itinerary['id']
                activities = self.activities_table.all(
                    formula=f"{{ItineraryID}} = '{itinerary_id}'"
                )

                result.append({
                    **itinerary['fields'],
                    'activities': [activity['fields'] for activity in activities]
                })

            return result
        except Exception as e:
            logging.error(f"Error retrieving user itineraries: {str(e)}")
            raise