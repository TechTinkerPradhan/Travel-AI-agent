import os
import logging
import re
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pyairtable import Table

class AirtableService:
    def __init__(self):
        self.access_token = os.environ.get("AIRTABLE_ACCESS_TOKEN")
        self.base_id = os.environ.get("AIRTABLE_BASE_ID")

        logging.info("Initializing Airtable Service...")
        logging.info(f"Using base ID: {self.base_id}")

        if not self.access_token or not self.base_id:
            logging.error("Missing Airtable credentials")
            raise ValueError(
                "Airtable access token and base ID are required. "
                "Please ensure AIRTABLE_ACCESS_TOKEN and AIRTABLE_BASE_ID "
                "environment variables are set."
            )

        # Clean up base ID - remove any trailing paths or slashes
        self.base_id = self.base_id.split('/')[0].strip()

        # Define table names
        self.USER_PREFERENCES = "User Preferences"
        self.ITINERARIES = "Travel Itineraries"

        # Try to initialize and test the connection
        self._test_connection()

    def _test_connection(self):
        """Test connection to Airtable and print table information"""
        try:
            logging.info(f"Attempting to connect to tables in base {self.base_id}")
            self.preferences_table = Table(self.access_token, self.base_id, self.USER_PREFERENCES)
            self.itineraries_table = Table(self.access_token, self.base_id, self.ITINERARIES)

            # Test Preferences table
            try:
                records = self.preferences_table.all(max_records=1)
                if records:
                    field_names = list(records[0]['fields'].keys())
                    logging.info(f"Fields in {self.USER_PREFERENCES}: {field_names}")
            except Exception as e:
                logging.warning(f"Could not read from {self.USER_PREFERENCES} table: {str(e)}")

            # Test Itineraries table
            try:
                itn_records = self.itineraries_table.all(max_records=1)
                if itn_records:
                    field_names = list(itn_records[0]['fields'].keys())
                    logging.info(f"Fields in {self.ITINERARIES}: {field_names}")
            except Exception as e:
                logging.error(f"Could not read from {self.ITINERARIES} table: {str(e)}")
                raise ValueError(
                    f"Please ensure '{self.ITINERARIES}' table exists with columns: "
                    "'User ID', 'Original Query', 'Content', 'Destination', "
                    "'Start Date', 'End Date', 'Status'"
                )

        except Exception as e:
            logging.error(f"Airtable connection error: {str(e)}")
            raise ValueError(f"Failed to connect to Airtable: {str(e)}")

    def get_user_itinerary(self, user_id: str, plan_id: str) -> Optional[Dict]:
        """Retrieve a specific itinerary by ID for a user"""
        try:
            formula = f"AND({{User ID}} = '{user_id}', RECORD_ID() = '{plan_id}')"
            records = self.itineraries_table.all(formula=formula)
            if records:
                record = records[0]
                return {
                    'id': record['id'],
                    'content': record['fields'].get('Content', ''),
                    'start_date': record['fields'].get('Start Date', ''),
                    'end_date': record['fields'].get('End Date', ''),
                    'destination': record['fields'].get('Destination', '')
                }
            return None
        except Exception as e:
            logging.error(f"Error retrieving itinerary: {str(e)}")
            raise ValueError(f"Failed to retrieve itinerary: {str(e)}")

    def get_user_itineraries(self, user_id: str) -> List[Dict]:
        """Retrieve all itineraries for a user"""
        try:
            formula = f"{{User ID}} = '{user_id}'"
            records = self.itineraries_table.all(formula=formula)
            return [{
                'id': record['id'],
                'destination': record['fields'].get('Destination', ''),
                'start_date': record['fields'].get('Start Date', ''),
                'end_date': record['fields'].get('End Date', ''),
                'status': record['fields'].get('Status', 'Active')
            } for record in records]
        except Exception as e:
            logging.error(f"Error retrieving itineraries: {str(e)}")
            raise ValueError(f"Failed to retrieve itineraries: {str(e)}")

    def save_user_itinerary(self, user_id: str, original_query: str, selected_itinerary: str, start_date: str) -> Dict:
        """Save the user's selected itinerary with all necessary information"""
        try:
            # Extract destination from the query
            destination = self.extract_destination_from_query(original_query)

            # Calculate end date based on the itinerary content
            end_date = self.calculate_end_date(selected_itinerary, start_date)

            # Create the itinerary record
            itinerary_fields = {
                'User ID': user_id,
                'Original Query': original_query,
                'Content': selected_itinerary,
                'Destination': destination,
                'Start Date': start_date,
                'End Date': end_date,
                'Status': 'Active'
            }

            new_record = self.itineraries_table.create(itinerary_fields)
            logging.debug(f"Created itinerary record with ID {new_record['id']}")

            return new_record

        except Exception as e:
            logging.error(f"Error saving user itinerary: {str(e)}")
            raise ValueError(f"Failed to save itinerary: {str(e)}")

    def calculate_end_date(self, itinerary_content: str, start_date: str) -> str:
        """Calculate the end date based on the itinerary content"""
        try:
            # Convert start_date to datetime
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')

            # Find the highest day number in the itinerary
            day_pattern = r'Day\s+(\d+)'
            days = re.findall(day_pattern, itinerary_content, re.IGNORECASE)
            if days:
                num_days = max(map(int, days))
                end_dt = start_dt + timedelta(days=num_days - 1)  # -1 because Day 1 is the start date
            else:
                # Default to 7 days if no day numbers found
                end_dt = start_dt + timedelta(days=6)

            return end_dt.strftime('%Y-%m-%d')
        except Exception as e:
            logging.error(f"Error calculating end date: {str(e)}")
            # Fallback to 7 days from start
            return (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=6)).strftime('%Y-%m-%d')

    def extract_destination_from_query(self, query: str) -> str:
        """Extract the destination from the user's query"""
        try:
            patterns = [
                r'trip to ([A-Za-z\s]+)',
                r'travel to ([A-Za-z\s]+)',
                r'vacation in ([A-Za-z\s]+)',
                r'visiting ([A-Za-z\s]+)',
                r'holiday in ([A-Za-z\s]+)',
                r'going to ([A-Za-z\s]+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    destination = match.group(1).strip()
                    return destination.title()
            return "Unknown Destination"
        except Exception as e:
            logging.error(f"Error extracting destination: {str(e)}")
            return "Unknown Destination"

    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Retrieve user preferences from the User Preferences table"""
        try:
            formula = f"{{User ID}} = '{user_id}'"
            records = self.preferences_table.all(formula=formula)
            if records:
                fields = records[0]['fields']
                return {
                    'budget': fields.get('Budget Preference'),
                    'travel_style': fields.get('Travel Style')
                }
            return None
        except Exception as e:
            logging.error(f"Error retrieving user preferences: {str(e)}")
            raise ValueError(f"Failed to retrieve preferences: {str(e)}")

    def save_user_preferences(self, user_id: str, preferences: Dict) -> Dict:
        """Save or update user preferences"""
        try:
            formula = f"{{User ID}} = '{user_id}'"
            existing_records = self.preferences_table.all(formula=formula)

            fields = {
                'User ID': user_id,
                'Budget Preference': preferences.get('budget'),
                'Travel Style': preferences.get('travel_style'),
                'Last Updated Date': datetime.now().strftime('%Y-%m-%d')
            }

            if existing_records:
                record_id = existing_records[0]['id']
                return self.preferences_table.update(record_id, fields)
            else:
                return self.preferences_table.create(fields)

        except Exception as e:
            logging.error(f"Error saving user preferences: {str(e)}")
            raise ValueError(f"Failed to save preferences: {str(e)}")

    def extract_dates_from_itinerary(self, content: str) -> tuple:
        """Attempt to extract start and end dates from the itinerary text."""
        try:
            date_pattern = r'(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})'
            dates = re.findall(date_pattern, content)

            if dates:
                # Convert found dates to datetime objects
                parsed = []
                for d in dates:
                    if '-' in d:
                        parsed.append(datetime.strptime(d, '%Y-%m-%d'))
                    else:
                        parsed.append(datetime.strptime(d, '%m/%d/%Y'))
                start_date = min(parsed).strftime('%m/%d/%Y')
                end_date = max(parsed).strftime('%m/%d/%Y')
            else:
                # If no explicit date strings found, assume # of days from itinerary
                day_pattern = r'Day\s+(\d+)'
                days = re.findall(day_pattern, content, re.IGNORECASE)
                if days:
                    num_days = max(map(int, days))
                else:
                    num_days = 7  # default
                start_dt = datetime.now()
                end_dt = start_dt + timedelta(days=num_days)
                start_date = start_dt.strftime('%m/%d/%Y')
                end_date = end_dt.strftime('%m/%d/%Y')

            return start_date, end_date

        except Exception as e:
            logging.error(f"Error extracting dates from itinerary: {str(e)}")
            # fallback: current date + 7 days
            sd = datetime.now().strftime('%m/%d/%Y')
            ed = (datetime.now() + timedelta(days=7)).strftime('%m/%d/%Y')
            return (sd, ed)