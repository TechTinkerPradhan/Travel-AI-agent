import os
import logging
from typing import Dict, Optional
from pyairtable import Table

class AirtableService:
    def __init__(self):
        self.access_token = os.environ.get("AIRTABLE_ACCESS_TOKEN")
        self.base_id = os.environ.get("AIRTABLE_BASE_ID")

        logging.info("Initializing Airtable Service...")

        if not self.access_token or not self.base_id:
            logging.error("Missing Airtable credentials")
            raise ValueError(
                "Airtable access token and base ID are required. "
                "Please ensure AIRTABLE_ACCESS_TOKEN and AIRTABLE_BASE_ID "
                "environment variables are set."
            )

        # Clean up base ID - remove any trailing paths or slashes
        self.base_id = self.base_id.split('/')[0].strip()
        logging.info(f"Using base ID: {self.base_id}")

        # Define table names
        self.USER_PREFERENCES = "User Preferences"

        # Try to initialize and test the connection
        self._test_connection()

    def _test_connection(self):
        """Test connection to Airtable"""
        try:
            # Initialize table
            logging.info(f"Attempting to connect to table: {self.USER_PREFERENCES}")
            self.preferences_table = Table(self.access_token, self.base_id, self.USER_PREFERENCES)

            # Try to list records
            logging.info("Attempting to list records...")
            records = self.preferences_table.all(max_records=1)

            # Log success
            logging.info(f"Successfully connected to table. Found {len(records)} records.")

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
                'Budget': preferences.get('budget'),
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
            # Include more context in the error message
            error_context = f"Failed to save preferences for user {user_id} with fields {preferences}"
            logging.error(error_context)
            raise ValueError(f"Airtable Error: {str(e)}\nContext: {error_context}")

    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Retrieve user preferences from Airtable"""
        try:
            # Use the same formula format as in save
            formula = "{User ID} = '" + user_id.replace("'", "\\'") + "'"
            logging.debug(f"Fetching preferences with formula: {formula}")

            records = self.preferences_table.all(formula=formula)
            if records:
                record = records[0]['fields']
                return {
                    'budget': record.get('Budget'),
                    'travelStyle': record.get('Travel Style')
                }
            return None
        except Exception as e:
            logging.error(f"Error retrieving user preferences: {str(e)}")
            raise ValueError(f"Failed to retrieve preferences: {str(e)}")