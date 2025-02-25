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

        # Define table names and required fields
        self.USER_PREFERENCES = "User Preferences"
        self.ITINERARIES = "Travel Itineraries"

        self.REQUIRED_PREFERENCE_FIELDS = [
            'User ID',
            'Budget Preference',
            'Travel Style',
            'Last Updated Date'
        ]

        self.REQUIRED_ITINERARY_FIELDS = [
            'User ID',
            'Original Query',
            'Content',
            'Destination',
            'Start Date',
            'End Date',
            'Status'
        ]

        # Initialize and verify tables
        self._initialize_tables()

    def _initialize_tables(self):
        """Initialize and verify tables and their required fields"""
        try:
            logging.info(f"Attempting to connect to tables in base {self.base_id}")
            self.preferences_table = Table(self.access_token, self.base_id, self.USER_PREFERENCES)
            self.itineraries_table = Table(self.access_token, self.base_id, self.ITINERARIES)

            # Verify and update preferences table fields
            try:
                prefs_records = self.preferences_table.all(max_records=1)
                if prefs_records:
                    existing_pref_fields = list(prefs_records[0]['fields'].keys())
                    logging.info(f"Fields in {self.USER_PREFERENCES}: {existing_pref_fields}")
                    # Note: We can't create fields via API, log missing fields
                    missing_pref_fields = set(self.REQUIRED_PREFERENCE_FIELDS) - set(existing_pref_fields)
                    if missing_pref_fields:
                        logging.warning(f"Missing fields in {self.USER_PREFERENCES}: {missing_pref_fields}")
            except Exception as e:
                logging.warning(f"Could not read from {self.USER_PREFERENCES} table: {str(e)}")

            # Verify and update itineraries table fields
            try:
                itn_records = self.itineraries_table.all(max_records=1)
                if itn_records:
                    existing_itn_fields = list(itn_records[0]['fields'].keys())
                    logging.info(f"Fields in {self.ITINERARIES}: {existing_itn_fields}")
                    # Note: We can't create fields via API, log missing fields
                    missing_itn_fields = set(self.REQUIRED_ITINERARY_FIELDS) - set(existing_itn_fields)
                    if missing_itn_fields:
                        logging.warning(f"Missing fields in {self.ITINERARIES}: {missing_itn_fields}")
            except Exception as e:
                logging.error(f"Could not read from {self.ITINERARIES} table: {str(e)}")
                raise ValueError(
                    f"Please ensure '{self.ITINERARIES}' table exists with fields: {', '.join(self.REQUIRED_ITINERARY_FIELDS)}"
                )

        except Exception as e:
            logging.error(f"Airtable connection error: {str(e)}")
            raise ValueError(f"Failed to connect to Airtable: {str(e)}")

    def _verify_itinerary_fields(self, fields: Dict) -> Dict:
        """Verify and clean fields before saving to itinerary table"""
        verified_fields = {}
        for field in self.REQUIRED_ITINERARY_FIELDS:
            if field in fields:
                verified_fields[field] = fields[field]
        return verified_fields

    def save_user_itinerary(self, user_id: str, original_query: str, selected_itinerary: str, start_date: str) -> Dict:
        """Save the user's selected itinerary with all necessary information"""
        try:
            # Extract destination from the query
            destination = self.extract_destination_from_query(original_query)

            # Calculate end date based on the itinerary content
            end_date = self.calculate_end_date(selected_itinerary, start_date)

            # Create basic fields that should exist in any table
            itinerary_fields = {
                'User ID': user_id,
                'Destination': destination,
                'Start Date': start_date,
                'End Date': end_date,
                'Status': 'Active'
            }

            # Try to add additional fields if they exist
            try:
                # Test if we can add these fields by checking if they exist
                test_record = self.itineraries_table.all(max_records=1)
                if test_record and 'Original Query' in test_record[0]['fields']:
                    itinerary_fields['Original Query'] = original_query
                if test_record and 'Content' in test_record[0]['fields']:
                    itinerary_fields['Content'] = selected_itinerary
            except Exception as field_error:
                logging.warning(f"Some fields could not be added: {str(field_error)}")

            new_record = self.itineraries_table.create(itinerary_fields)
            logging.debug(f"Created itinerary record with ID {new_record['id']}")

            return new_record

        except Exception as e:
            logging.error(f"Error saving user itinerary: {str(e)}")
            raise ValueError(f"Failed to save itinerary: {str(e)}")

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

    def calculate_end_date(self, itinerary_content: str, start_date: str) -> str:
        """Calculate the end date based on the itinerary content"""
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            day_pattern = r'Day\s+(\d+)'
            days = re.findall(day_pattern, itinerary_content, re.IGNORECASE)
            if days:
                num_days = max(map(int, days))
                end_dt = start_dt + timedelta(days=num_days - 1)
            else:
                end_dt = start_dt + timedelta(days=6)
            return end_dt.strftime('%Y-%m-%d')
        except Exception as e:
            logging.error(f"Error calculating end date: {str(e)}")
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

            fields = self._verify_itinerary_fields({
                'User ID': user_id,
                'Budget Preference': preferences.get('budget'),
                'Travel Style': preferences.get('travel_style'),
                'Last Updated Date': datetime.now().strftime('%Y-%m-%d')
            })

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