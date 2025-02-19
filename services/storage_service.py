import json
import os
from pathlib import Path

# Create data directory if it doesn't exist
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def save_user_preferences(user_id, preferences):
    """
    Save user preferences to a JSON file
    """
    try:
        file_path = DATA_DIR / f"user_{user_id}.json"
        with open(file_path, 'w') as f:
            json.dump(preferences, f)
    except Exception as e:
        raise Exception(f"Failed to save preferences: {str(e)}")

def get_user_preferences(user_id):
    """
    Retrieve user preferences from JSON file
    """
    try:
        file_path = DATA_DIR / f"user_{user_id}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        raise Exception(f"Failed to retrieve preferences: {str(e)}")
