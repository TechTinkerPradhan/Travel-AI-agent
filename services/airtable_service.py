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

        # Define table names and schemas
        self.USER_PREFERENCES = "User Preferences"
        self.ITINERARIES = "Travel Itineraries"  # Changed table name to be more descriptive

        # Try to initialize and test the connection
        self._test_connection()

    def _test_connection(self):
        """Test connection to Airtable and print table information"""
        try:
            # Initialize tables
            logging.info(f"Attempting to connect to tables")
            self.preferences_table = Table(self.access_token, self.base_id, self.USER_PREFERENCES)
            self.itineraries_table = Table(self.access_token, self.base_id, self.ITINERARIES)

            # Try to list records from preferences table
            logging.info("Attempting to list records and get schema...")
            try:
                records = self.preferences_table.all(max_records=1)
                if records:
                    field_names = list(records[0]['fields'].keys())
                    logging.info(f"Available fields in preferences table: {field_names}")
                    logging.info(f"Total records found: {len(records)}")
                    logging.info(f"Sample record (fields only): {records[0]['fields']}")
                else:
                    logging.info("Preferences table exists but no records found")
            except Exception as e:
                logging.warning(f"Could not read from preferences table: {str(e)}")

            # Try to list records from itineraries table
            try:
                itinerary_records = self.itineraries_table.all(max_records=1)
                if itinerary_records:
                    field_names = list(itinerary_records[0]['fields'].keys())
                    logging.info(f"Available fields in itineraries table: {field_names}")
                else:
                    logging.info("Itineraries table exists but no records found")
            except Exception as e:
                logging.error(f"Could not read from itineraries table: {str(e)}")
                raise ValueError(
                    "Please ensure the 'Travel Itineraries' table exists in your Airtable base "
                    "with the following columns: 'User ID', 'Destination', 'Status', 'Start Date', "
                    "'End Date', 'Related User Preferences', 'Related Travel Activities'"
                )

        except Exception as e:
            logging.error(f"Airtable connection error: {str(e)}")
            logging.error(f"Connection attempted with: base_id={self.base_id}")
            raise ValueError(f"Failed to connect to Airtable: {str(e)}")

    def save_user_preferences(self, user_id: str, preferences: Dict) -> Dict:
        """Save user preferences to Airtable"""
        try:
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

    def extract_dates_from_itinerary(self, content: str) -> tuple:
        """Extract start and end dates from itinerary content"""
        try:
            # First try to find explicit dates in the content
            date_pattern = r'(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})'
            dates = re.findall(date_pattern, content)

            if dates:
                # Convert found dates to datetime objects
                parsed_dates = [datetime.strptime(d, '%Y-%m-%d' if '-' in d else '%m/%d/%Y') for d in dates]
                start_date = min(parsed_dates).strftime('%Y-%m-%d')
                end_date = max(parsed_dates).strftime('%Y-%m-%d')
            else:
                # If no explicit dates found, count the number of days in the itinerary
                day_pattern = r'Day\s+(\d+)'
                days = re.findall(day_pattern, content)
                num_days = max(map(int, days)) if days else 7  # Default to 7 days if no days found

                # Use current date as start date
                start_date = datetime.now().strftime('%Y-%m-%d')
                end_date = (datetime.now() + timedelta(days=num_days)).strftime('%Y-%m-%d')

            return start_date, end_date

        except Exception as e:
            logging.error(f"Error extracting dates from itinerary: {str(e)}")
            # Return default dates if extraction fails
            return (
                datetime.now().strftime('%Y-%m-%d'),
                (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            )

    def extract_destination_from_query(self, query: str) -> str:
        """Extract destination from the original query"""
        try:
            # Look for patterns like "trip to [destination]" or "travel to [destination]"
            destination_patterns = [
                r'trip to ([A-Za-z\s]+)',
                r'travel to ([A-Za-z\s]+)',
                r'visiting ([A-Za-z\s]+)',
                r'holiday in ([A-Za-z\s]+)',
                r'vacation in ([A-Za-z\s]+)',
                r'in ([A-Za-z\s]+)'
            ]

            for pattern in destination_patterns:
                match = re.search(pattern, query.lower())
                if match:
                    destination = match.group(1).strip()
                    # Capitalize the first letter of each word
                    return ' '.join(word.capitalize() for word in destination.split())

            # If no destination found in patterns, try to find location markers in the itinerary
            locations = re.findall(r'\*\*([^*]+)\*\*', query)
            if locations:
                return locations[0].strip()

            return "Unknown"

        except Exception as e:
            logging.error(f"Error extracting destination: {str(e)}")
            return "Unknown"

    def save_user_itinerary(self, user_id: str, original_query: str, selected_itinerary: str, user_changes: str = '') -> Dict:
        """Save user itinerary to Airtable"""
        try:
            logging.debug(f"Creating itinerary record for user: {user_id}")

            # Extract destination
            destination = self.extract_destination_from_query(original_query)
            logging.debug(f"Extracted destination: {destination}")

            # Extract dates
            start_date, end_date = self.extract_dates_from_itinerary(selected_itinerary)
            logging.debug(f"Extracted dates: {start_date} to {end_date}")

            # Prepare fields for the itinerary record
            itinerary_fields = {
                'User ID': user_id,
                'Destination': destination,
                'Status': 'Active',
                'Start Date': start_date,
                'End Date': end_date
            }

            # Create itinerary record
            record = self.itineraries_table.create(itinerary_fields)
            logging.debug(f"Created itinerary record with ID: {record['id']}")

            # Update User Preferences table with reference to itinerary
            try:
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
                    logging.debug(f"Updated user preferences with new itinerary reference")

            except Exception as user_update_error:
                logging.warning(f"Failed to update user preferences with itinerary reference: {str(user_update_error)}")
                # Don't raise error here as the itinerary was still saved successfully

            return record

        except Exception as e:
            logging.error(f"Error saving user itinerary: {str(e)}")
            raise ValueError(f"Failed to save itinerary: {str(e)}")

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