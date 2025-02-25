import os
import time
import logging
from queue import Queue
from typing import Dict
from openai import OpenAI, RateLimitError, APIError, APIConnectionError

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY is not set")
    raise ValueError("OPENAI_API_KEY environment variable is required")

client = OpenAI(api_key=OPENAI_API_KEY)

# Request queue and rate limiting
request_queue = Queue()
MIN_REQUEST_INTERVAL = 0.1  # seconds between requests


def generate_travel_plan_internal(message: str,
                                  user_preferences: Dict) -> Dict:
    """Generate travel plan with retries"""
    max_retries = 5
    base_delay = 0.5

    system_prompt = """You are a travel planning assistant that provides TWO different travel plan options.
Each plan MUST include:
1. A descriptive title starting with 'Option 1:' or 'Option 2:'
2. Daily activities marked with '## Day X: [Title]'
3. Times in 24-hour format (e.g., 09:00)
4. Locations in **bold** text
5. Duration estimates in (parentheses)
6. Activities as bullet points with '-'

Separate the two plans with '---' on a new line."""

    for attempt in range(max_retries):
        try:
            preferences_str = "\n".join(
                f"- {key}: {value}" for key, value in user_preferences.items()
                if value)

            user_prompt = f"""{preferences_str}

User request: {message}

Provide TWO distinct travel plans with detailed timings and locations."""

            response = client.chat.completions.create(model="gpt-4",
                                                      messages=[{
                                                          "role":
                                                          "system",
                                                          "content":
                                                          system_prompt
                                                      }, {
                                                          "role":
                                                          "user",
                                                          "content":
                                                          user_prompt
                                                      }],
                                                      temperature=0.7,
                                                      max_tokens=2000)

            if not response or not response.choices or not response.choices[
                    0].message or not response.choices[0].message.content:
                logger.error("OpenAI returned an empty response.")
                return {
                    "status": "error",
                    "message": "AI service returned an empty response."
                }

            content = response.choices[0].message.content.strip()
            logger.debug(f"Received response: {content[:100]}...")

            formatted_plans = content.split('---')

            return {
                "status":
                "success",
                "alternatives": [{
                    "id": f"option_{i+1}",
                    "content": plan.strip(),
                    "type": "itinerary"
                } for i, plan in enumerate(formatted_plans) if plan.strip()]
            }

        except RateLimitError as e:
            delay = base_delay * (attempt + 1)
            logger.warning(
                f"Rate limit hit (attempt {attempt + 1}/{max_retries}). Waiting {delay:.1f} seconds..."
            )
            time.sleep(delay)

        except (APIError, APIConnectionError) as e:
            logger.error(f"OpenAI API error: {str(e)}")
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)

    return {
        "status": "error",
        "message": "AI service failed after multiple attempts."
    }


def generate_travel_plan(message: str, user_preferences: Dict) -> Dict:
    """Directly generate travel plan without caching"""
    return generate_travel_plan_internal(message, user_preferences)
