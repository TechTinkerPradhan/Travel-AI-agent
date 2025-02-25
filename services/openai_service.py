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

# Initialize OpenAI client with retry mechanism
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Configuration
MAX_RETRIES = 3
BACKOFF_FACTOR = 2
DEFAULT_MODEL = "gpt-3.5-turbo"

def generate_travel_plan(message, user_preferences=None):
    """Generate travel recommendations using OpenAI's API"""
    try:
        # Format preferences if they exist
        preferences_text = ""
        if user_preferences:
            preferences_text = "User preferences:\n" + "\n".join(
                f"- {k}: {v}" for k, v in user_preferences.items() if v
            )

        messages = [
            {
                "role": "system",
                "content": """You are a travel planning assistant. Create TWO distinct travel plans.
                Each plan should follow this format:

                Option 1: [Title]
                [Brief description]

                ## Itinerary
                Day 1:
                - 09:00: Activity at **Location** (duration)
                [Continue with more activities]

                ---

                Option 2: [Different Title]
                [Different description]
                [Same format as Option 1]"""
            },
            {
                "role": "user",
                "content": f"{preferences_text}\n\nPlease plan this trip: {message}"
            }
        ]

        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"Attempt {attempt + 1} to generate travel plan")
                response = client.chat.completions.create(
                    model=DEFAULT_MODEL,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000
                )

                content = response.choices[0].message.content
                plans = content.split('---')

                # Ensure we have two plans
                if len(plans) != 2:
                    if "Option 2:" in content:
                        plans = content.split("Option 2:")
                        plans[1] = "Option 2:" + plans[1]
                    else:
                        mid = len(content) // 2
                        plans = [content[:mid], content[mid:]]

                result = {
                    "status": "success",
                    "alternatives": [
                        {"id": "plan1", "content": plans[0].strip(), "type": "itinerary"},
                        {"id": "plan2", "content": plans[1].strip(), "type": "itinerary"}
                    ]
                }

                # Verify JSON serialization
                json.dumps(result)  # Will raise JSONDecodeError if invalid
                return result

            except RateLimitError:
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(BACKOFF_FACTOR ** attempt)
            except (APIError, APIConnectionError) as e:
                logger.error(f"OpenAI API error: {str(e)}")
                raise Exception("Failed to generate travel plan due to API error")

    except Exception as e:
        logger.error(f"Error in generate_travel_plan: {str(e)}")
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

#OpenAI Configuration
DEFAULT_MODEL = "gpt-3.5-turbo"  # Using gpt-3.5-turbo as specified
DEFAULT_TEMPERATURE = 0.7
MAX_TOKENS_ITINERARY = 2000
MAX_TOKENS_ANALYSIS = 1000

# Retry Configuration
MAX_RETRIES = 5
BASE_DELAY = 1  # Initial delay in seconds
MAX_DELAY = 32  # Maximum delay in seconds
JITTER = 0.1  # Random jitter factor

agent_registry = AgentRegistry()