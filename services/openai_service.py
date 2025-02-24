import os
import time
import logging
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

def generate_travel_plan(message, user_preferences):
    """
    Generate travel recommendations using OpenAI's API with rate limit handling
    """
    max_retries = 3
    base_delay = 2  # Base delay in seconds

    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1}/{max_retries} to generate travel plan")

            system_prompt = """You are a travel planning assistant that provides TWO different travel plan options.
Each plan should include:
- A descriptive title (e.g., 'Option 1: Cultural Focus')
- Daily activities with '## Day X: [Title]'
- Times in 24-hour format (09:00)
- Locations in **bold**
- Duration estimates in (parentheses)
- Activities as bullet points with '-'

Use '---' to separate the two plans.
"""

            # Format user preferences if any
            preferences_str = ""
            if user_preferences:
                preferences_str = "\nConsider these preferences:\n" + "\n".join(
                    f"- {key}: {value}" 
                    for key, value in user_preferences.items() 
                    if value
                )

            user_prompt = f"{preferences_str}\n\nUser request: {message}\n\nProvide TWO distinct travel plans with detailed timings and locations."

            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            content = response.choices[0].message.content
            logger.debug(f"Successfully received response of length: {len(content)}")

            # Split into two plans
            plans = content.split('---')
            if len(plans) != 2:
                logger.warning("Response doesn't contain expected separator, attempting alternative split")
                if "Option 2:" in content:
                    plans = content.split("Option 2:")
                    plans[1] = "Option 2:" + plans[1]
                else:
                    mid = len(content) // 2
                    plans = [content[:mid], content[mid:]]

            return {
                "status": "success",
                "alternatives": [
                    {
                        "id": f"option_{i+1}",
                        "content": plan.strip(),
                        "type": "itinerary"
                    }
                    for i, plan in enumerate(plans)
                ]
            }

        except RateLimitError as e:
            delay = (base_delay ** attempt) + (attempt * 0.1)  # Exponential backoff with jitter
            logger.warning(f"Rate limit hit (attempt {attempt + 1}/{max_retries}). Waiting {delay:.1f} seconds...")

            if attempt == max_retries - 1:
                raise Exception("Rate limit exceeded. Please wait a few moments and try again.")

            time.sleep(delay)
            continue

        except APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise Exception("Error connecting to AI service. Please try again.")

        except APIConnectionError as e:
            logger.error(f"OpenAI connection error: {str(e)}")
            if attempt == max_retries - 1:
                raise Exception("Unable to connect to AI service. Please try again later.")
            time.sleep(1)
            continue

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise Exception(f"An unexpected error occurred: {str(e)}")

def analyze_user_preferences(query: str, selected_response: str):
    """Analyze user preferences from the query and selected response"""
    try:
        system_prompt = """Analyze the user's travel preferences from their query and selected plan.
Focus on understanding:
- Budget level (budget, moderate, luxury)
- Travel style (adventure, relaxation, cultural)
- Accommodation preferences
- Activity interests
- Time-related preferences
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {query}\n\nSelected Plan: {selected_response}"}
            ],
            temperature=0.3,
            max_tokens=500
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Error analyzing preferences: {str(e)}", exc_info=True)
        return None