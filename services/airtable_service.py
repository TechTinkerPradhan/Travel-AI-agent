import os
import logging
from typing import Dict, Optional
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

        # Try to initialize and test the connection
        self._test_connection()

    def _test_connection(self):
        """Test connection to Airtable and print table information"""
        try:
            # Initialize table
            logging.info(f"Attempting to connect to table: {self.USER_PREFERENCES}")
            self.preferences_table = Table(self.access_token, self.base_id, self.USER_PREFERENCES)

            # Try to list records and print schema information
            logging.info("Attempting to list records and get schema...")
            records = self.preferences_table.all(max_records=1)

            if records:
                # Print field names from the first record
                field_names = list(records[0]['fields'].keys())
                logging.info(f"Available fields in table: {field_names}")
                logging.info(f"Total records found: {len(records)}")
                logging.info(f"Sample record (fields only): {records[0]['fields']}")
            else:
                logging.info("Table exists but no records found")

        except Exception as e:
            logging.error(f"Airtable connection error: {str(e)}")
            logging.error(f"Connection attempted with: base_id={self.base_id}, table={self.USER_PREFERENCES}")
            raise ValueError(f"Failed to connect to Airtable: {str(e)}")

    def save_user_preferences(self, user_id: str, preferences: Dict) -> Dict:
        """Save user preferences to Airtable"""
        try:
            # Properly escape field name with curly braces for the formula
            formula = "{User ID} = '" + user_id.replace("'", "\\'") + "'"
            logging.debug(f"Searching with formula: {formula}")

            existing_records = self.preferences_table.all(formula=formula)
            logging.debug(f"Found {len(existing_records)} existing records")

            fields = {
                'User ID': user_id,
                'Budget Preference': preferences.get('budget'),
                'Travel Style': preferences.get('travelStyle')
            }

            logging.debug(f"Preparing to save fields: {fields}")

            if existing_records:
                record_id = existing_records[0]['id']
                logging.debug(f"Updating existing record: {record_id}")
                return self.preferences_table.update(record_id, fields)
            else:
                logging.debug("Creating new record")
                return self.preferences_table.create(fields)

        except Exception as e:
            logging.error(f"Error saving user preferences: {str(e)}")
            error_context = f"Failed to save preferences for user {user_id} with fields {preferences}"
            logging.error(error_context)
            raise ValueError(f"Airtable Error: {str(e)}\nContext: {error_context}")

    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Retrieve user preferences from Airtable"""
        try:
            formula = "{User ID} = '" + user_id.replace("'", "\\'") + "'"
            logging.debug(f"Fetching preferences with formula: {formula}")

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

    def save_user_itinerary(self, user_id: str, original_query: str, selected_itinerary: str, user_changes: str = '') -> Dict:
        """Save user itinerary to Airtable"""
        try:
            # Initialize Itineraries table
            itineraries_table = Table(self.access_token, self.base_id, "Itineraries")

            fields = {
                'User ID': user_id,
                'Original Query': original_query,
                'Selected Itinerary': selected_itinerary,
                'User Changes': user_changes,
                'Created Date': datetime.now().isoformat()
            }

            logging.debug(f"Creating itinerary record for user: {user_id}")
            record = itineraries_table.create(fields)

            # Update User Preferences table with reference to itinerary
            existing_user = self.preferences_table.all(
                formula="{User ID} = '" + user_id.replace("'", "\\'") + "'"
            )

            if existing_user:
                user_record = existing_user[0]
                existing_itineraries = user_record['fields'].get('Travel Itineraries', [])
                existing_itineraries.append(record['id'])
                
                self.preferences_table.update(
                    user_record['id'],
                    {'Travel Itineraries': existing_itineraries}
                )

            return record

        except Exception as e:
            logging.error(f"Error saving user itinerary: {str(e)}")
            raise ValueError(f"Failed to save itinerary: {str(e)}")
