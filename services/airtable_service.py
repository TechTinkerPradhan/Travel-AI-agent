# services/airtable_service.py

import os
import logging
import re
from typing import Dict, Optional
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
        self.ITINERARIES = "Travel Itineraries"  # The table for storing itineraries

        # Try to initialize and test the connection
        self._test_connection()

    def _test_connection(self):
        """Test connection to Airtable and print table information"""
        try:
            logging.info(f"Attempting to connect to tables in base {self.base_id}")
            self.preferences_table = Table(self.access_token, self.base_id, self.USER_PREFERENCES)
            self.itineraries_table = Table(self.access_token, self.base_id, self.ITINERARIES)

            # Quick test on Preferences table
            try:
                records = self.preferences_table.all(max_records=1)
                if records:
                    field_names = list(records[0]['fields'].keys())
                    logging.info(f"Fields in {self.USER_PREFERENCES}: {field_names}")
                else:
                    logging.info(f"No records found in {self.USER_PREFERENCES}")
            except Exception as e:
                logging.warning(f"Could not read from {self.USER_PREFERENCES} table: {str(e)}")

            # Quick test on Itineraries table
            try:
                itn_records = self.itineraries_table.all(max_records=1)
                if itn_records:
                    field_names = list(itn_records[0]['fields'].keys())
                    logging.info(f"Fields in {self.ITINERARIES}: {field_names}")
                else:
                    logging.info(f"No records found in {self.ITINERARIES}")
            except Exception as e:
                logging.error(f"Could not read from {self.ITINERARIES} table: {str(e)}")
                raise ValueError(
                    f"Please ensure '{self.ITINERARIES}' table exists with columns like: "
                    "'User ID', 'Destination', 'Status', 'Start Date', 'End Date', etc."
                )

        except Exception as e:
            logging.error(f"Airtable connection error: {str(e)}")
            raise ValueError(f"Failed to connect to Airtable: {str(e)}")

    def save_user_preferences(self, user_id: str, preferences: Dict) -> Dict:
        """Save or update user preferences in the 'User Preferences' table."""
        try:
            formula = "{User ID} = '" + user_id.replace("'", "\\'") + "'"
            logging.debug(f"Searching with formula: {formula}")

            existing_records = self.preferences_table.all(formula=formula)
            logging.debug(f"Found {len(existing_records)} existing records for user {user_id}")

            fields = {
                'User ID': user_id,
                'Budget Preference': preferences.get('budget'),
                'Travel Style': preferences.get('travelStyle')
            }

            if existing_records:
                record_id = existing_records[0]['id']
                logging.debug(f"Updating existing preferences record: {record_id}")
                return self.preferences_table.update(record_id, fields)
            else:
                logging.debug("Creating new preferences record")
                return self.preferences_table.create(fields)

        except Exception as e:
            logging.error(f"Error saving user preferences: {str(e)}")
            raise ValueError(f"Airtable Error: {str(e)}")

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

    def extract_destination_from_query(self, query: str) -> str:
        """Extract a destination from the user's original query."""
        try:
            # Common patterns: "trip to X", "travel to X", "vacation in X", etc.
            patterns = [
                r'trip to ([A-Za-z\s]+)',
                r'travel to ([A-Za-z\s]+)',
                r'vacation in ([A-Za-z\s]+)',
                r'visiting ([A-Za-z\s]+)',
                r'holiday in ([A-Za-z\s]+)',
                r'going to ([A-Za-z\s]+)'
            ]
            for pat in patterns:
                match = re.search(pat, query, re.IGNORECASE)
                if match:
                    raw_dest = match.group(1).strip()
                    return raw_dest.title()  # capitalizes each word
            return "Unknown"
        except Exception as e:
            logging.error(f"Error extracting destination: {str(e)}")
            return "Unknown"

    def save_user_itinerary(self, user_id: str, original_query: str, selected_itinerary: str, user_changes: str = '') -> Dict:
        """
        Save the final user itinerary to the 'Travel Itineraries' table. 
        Also link to the user's record in 'User Preferences'.
        """
        try:
            # 1) Extract destination
            destination = self.extract_destination_from_query(original_query)
            logging.debug(f"Extracted destination from query: {destination}")

            # 2) Extract date range
            start_date, end_date = self.extract_dates_from_itinerary(selected_itinerary)
            logging.debug(f"Extracted date range: {start_date} - {end_date}")

            # 3) Create the itinerary record
            itinerary_fields = {
                'User ID': user_id,
                'Destination': destination,
                'Status': 'Active',
                'Start Date': start_date,
                'End Date': end_date
                # Add other columns as needed (User Changes, Original Query, etc.)
            }

            new_record = self.itineraries_table.create(itinerary_fields)
            logging.debug(f"Created itinerary record with ID {new_record['id']}")

            # 4) Optionally link the new itinerary to the user’s preferences record
            try:
                formula = "{User ID} = '" + user_id.replace("'", "\\'") + "'"
                existing_user = self.preferences_table.all(formula=formula)
                if existing_user:
                    user_rec_id = existing_user[0]['id']
                    fields = existing_user[0]['fields']
                    existing_itns = fields.get('Travel Itineraries', [])
                    existing_itns.append(new_record['id'])
                    self.preferences_table.update(
                        user_rec_id,
                        {'Travel Itineraries': existing_itns}
                    )
            except Exception as update_err:
                logging.warning(f"Failed to update user preferences with itinerary reference: {update_err}")

            return new_record

        except Exception as e:
            logging.error(f"Error saving user itinerary: {str(e)}")
            raise ValueError(f"Failed to save itinerary: {str(e)}")

    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Retrieve user preferences from the 'User Preferences' table."""
        try:
            formula = "{User ID} = '" + user_id.replace("'", "\\'") + "'"
            records = self.preferences_table.all(formula=formula)
            if records:
                record = records[0]['fields']
                return {
                    'budget': record.get('Budget Preference'),
                    'travelStyle': record.get('Travel Style')
                }
            return None
        except Exception as e:
            logging.error(f"Error retrieving user preferences: {str(e)}")
            raise ValueError(f"Failed to retrieve preferences: {str(e)}")
