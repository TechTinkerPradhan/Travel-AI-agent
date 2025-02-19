import os
import time
import random
import logging
from openai import OpenAI, RateLimitError

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-api-key")
client = OpenAI(api_key=OPENAI_API_KEY)

def generate_travel_plan(message, user_preferences):
    """
    Generate travel recommendations using OpenAI's API with retry logic
    """
    max_retries = 5
    base_delay = 3

    for attempt in range(max_retries):
        try:
            system_prompt = """You are a knowledgeable travel assistant. Create personalized travel 
            recommendations based on user preferences. Focus on providing practical, detailed itineraries 
            that include activities, estimated costs, and timing."""

            # Prepare the message with user preferences context
            full_prompt = f"""User preferences: {user_preferences}
            User message: {message}
            Please provide a detailed travel recommendation that includes:
            1. Suggested duration
            2. Best time to visit
            3. Day-by-day itinerary
            4. Estimated costs
            5. Travel tips"""

            logging.debug(f"Attempt {attempt + 1} of {max_retries} to generate travel plan")
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )

            return response.choices[0].message.content

        except RateLimitError:
            if attempt == max_retries - 1:  # Last attempt
                raise Exception(
                    "We're experiencing high traffic. Please wait 30 seconds and try again. "
                    "This helps ensure a better response when you retry."
                )

            # Exponential backoff with jitter
            jitter = random.uniform(1, 3)
            delay = (base_delay * (2 ** attempt)) + jitter
            logging.debug(f"Rate limit hit, waiting {delay:.2f} seconds before retry")
            time.sleep(delay)
            continue

        except Exception as e:
            logging.error(f"Error generating travel plan: {str(e)}")
            raise Exception(f"Failed to generate travel plan: {str(e)}")