import os
import time
import random
import logging
import json
from openai import OpenAI, RateLimitError, APIError, APIConnectionError
from services.ai_agents import AgentRegistry, AgentRole

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY is not set")
    raise ValueError("OPENAI_API_KEY environment variable is required")

# OpenAI Configuration
DEFAULT_MODEL = "gpt-3.5-turbo"  # Using gpt-3.5-turbo as specified
DEFAULT_TEMPERATURE = 0.7
MAX_TOKENS_ITINERARY = 2000
MAX_TOKENS_ANALYSIS = 1000

# Retry Configuration
MAX_RETRIES = 5
BASE_DELAY = 1  # Initial delay in seconds
MAX_DELAY = 32  # Maximum delay in seconds
JITTER = 0.1  # Random jitter factor

client = OpenAI(api_key=OPENAI_API_KEY)
agent_registry = AgentRegistry()

def validate_openai_response(response):
    """Validate OpenAI response format"""
    if not response or not hasattr(response, 'choices'):
        raise ValueError("Invalid OpenAI response format")
    if not response.choices:
        raise ValueError("No choices in OpenAI response")
    if not hasattr(response.choices[0], 'message'):
        raise ValueError("No message in OpenAI response")
    if not hasattr(response.choices[0].message, 'content'):
        raise ValueError("No content in OpenAI response message")
    return response.choices[0].message.content

def make_api_call_with_retry(func, *args, **kwargs):
    """
    Generic retry mechanism for OpenAI API calls with exponential backoff
    """
    retry_count = 0
    while True:
        try:
            response = func(*args, **kwargs)
            content = validate_openai_response(response)
            return content
        except RateLimitError as e:
            retry_count += 1
            if retry_count > MAX_RETRIES:
                logger.error(f"Max retries ({MAX_RETRIES}) exceeded for rate limit")
                raise Exception("Service is experiencing high traffic. Please try again in a few minutes.")

            delay = min(BASE_DELAY * (2 ** (retry_count - 1)), MAX_DELAY)
            jitter_amount = random.uniform(-JITTER * delay, JITTER * delay)
            final_delay = delay + jitter_amount

            logger.warning(f"Rate limit hit, attempt {retry_count}/{MAX_RETRIES}. Retrying in {final_delay:.2f} seconds...")
            time.sleep(final_delay)
        except (APIError, APIConnectionError) as e:
            retry_count += 1
            if retry_count > MAX_RETRIES:
                logger.error(f"Max retries ({MAX_RETRIES}) exceeded for API error")
                raise Exception("API service error. Please try again later.")

            delay = min(BASE_DELAY * (2 ** (retry_count - 1)), MAX_DELAY)
            logger.warning(f"API error, attempt {retry_count}/{MAX_RETRIES}. Retrying in {delay} seconds... Error: {str(e)}")
            time.sleep(delay)

def generate_travel_plan(message, user_preferences):
    """
    Generate travel recommendations using OpenAI's API with retry mechanism
    """
    try:
        logger.debug("Starting travel plan generation")

        # Format user preferences
        preferences_context = "\n".join([
            f"{key}: {value}" for key, value in user_preferences.items()
            if value
        ])

        system_prompt = """You are a travel planning assistant. Create TWO distinct travel plans.
        Each plan must follow this exact format:

        Option 1: [Brief Title]
        [General description of this option's focus]

        ## Day-by-Day Itinerary:

        ## Day 1
        - 09:00: [Activity] at **[Location]** (Duration)
        - 12:00: [Activity] at **[Location]** (Duration)
        [etc...]

        [Repeat day structure for each day]

        ---

        Option 2: [Different Title]
        [Different general description]

        [Same day-by-day structure as Option 1]
        """

        full_prompt = f"""User preferences:\n{preferences_context}\n\nUser message: {message}

        Please create two distinct travel plans based on this request. 
        Make sure each plan has:
        1. A clear title and description
        2. Detailed daily schedules with times
        3. Location names in **bold**
        4. Duration estimates in parentheses
        """

        logger.debug("Making OpenAI API call")
        content = make_api_call_with_retry(
            client.chat.completions.create,
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=MAX_TOKENS_ITINERARY,
            temperature=DEFAULT_TEMPERATURE
        )

        logger.debug(f"Received response of length: {len(content)}")

        # Split into two plans
        plans = content.split('---')
        if len(plans) != 2:
            logger.warning("Response doesn't contain expected '---' separator, attempting fallback split")
            # Fallback: Try to split at "Option 2:"
            if "Option 2:" in content:
                plans = content.split("Option 2:")
                plans[1] = "Option 2:" + plans[1]
            else:
                # Last resort: split in half
                mid = len(content) // 2
                plans = [content[:mid], content[mid:]]

        # Format the response
        formatted_response = {
            "status": "success",
            "alternatives": [
                {
                    "id": "option_1",
                    "content": plans[0].strip(),
                    "type": "itinerary"
                },
                {
                    "id": "option_2",
                    "content": plans[1].strip(),
                    "type": "itinerary"
                }
            ]
        }

        # Validate JSON serialization
        try:
            json.dumps(formatted_response)
            return formatted_response
        except Exception as e:
            logger.error(f"JSON serialization error: {e}")
            raise ValueError("Failed to create valid JSON response")

    except Exception as e:
        logger.error(f"Error generating travel plan: {str(e)}", exc_info=True)
        raise Exception(f"Failed to generate travel plan: {str(e)}")

def analyze_user_preferences(query: str, selected_response: str):
    """
    Analyze user preferences based on their query and selected response
    """
    logger.debug("Starting preference analysis")
    logger.debug(f"Using model: {DEFAULT_MODEL}")
    logger.debug(f"Query: {query}")
    logger.debug(f"Selected response length: {len(selected_response)}")

    try:
        # Get the preference analyzer agent
        analyzer = agent_registry.get_agent(AgentRole.PREFERENCE_ANALYZER)
        if not analyzer:
            logger.error("Preference analyzer agent not found")
            raise ValueError("Preference analyzer agent not found")

        system_prompt = analyzer.system_prompt
        analysis_prompt = f"""
        Analyze the following user interaction and extract travel preferences:

        User Query: {query}
        Selected Response: {selected_response}

        Provide the analysis in JSON format with the following structure:
        {{
            "budget_preference": string,
            "travel_style": string,
            "accommodation_preference": string,
            "activity_interests": [string],
            "time_related_preferences": {{
                "duration": string,
                "season": string,
                "pace": string
            }},
            "confidence_score": float
        }}
        """

        logger.debug(
            "Making OpenAI API call for preference analysis with retry mechanism"
        )
        response = make_api_call_with_retry(
            client.chat.completions.create,
            model=DEFAULT_MODEL,
            messages=[{
                "role": "system",
                "content": system_prompt
            }, {
                "role": "user",
                "content": analysis_prompt
            }],
            max_tokens=MAX_TOKENS_ANALYSIS,
            temperature=0.3  # Lower temperature for more consistent analysis
        )

        analysis_result = response.choices[0].message.content
        logger.debug(
            f"Received preference analysis (length: {len(analysis_result)})")
        return analysis_result

    except Exception as e:
        logger.error(f"Error analyzing preferences: {str(e)}", exc_info=True)
        raise Exception(f"Failed to analyze preferences: {str(e)}")