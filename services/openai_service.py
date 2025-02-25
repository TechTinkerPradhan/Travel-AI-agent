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

client = OpenAI(api_key=OPENAI_API_KEY)
agent_registry = AgentRegistry()

def generate_travel_plan(message, user_preferences):
    """
    Generate multiple travel recommendations using OpenAI's API
    """
    max_retries = 5
    base_delay = 3

    try:
        logger.debug("Starting travel plan generation")
        logger.debug(f"Message: {message}")
        logger.debug(f"User preferences: {user_preferences}")

        # Prepare context with user preferences
        preferences_context = "\n".join([
            f"{key}: {value}" 
            for key, value in user_preferences.items()
            if value
        ])
        logger.debug(f"User preferences context: {preferences_context}")

        system_prompt = """You are a travel planning assistant. You will provide TWO different travel plans.
        Each plan should be well-formatted with:
        - A clear title for each plan (e.g., 'Option 1: Cultural Focus' and 'Option 2: Adventure Focus')
        - Clear headings using markdown (##)
        - Each day's activities clearly marked with '## Day X: [Title]'
        - Time-specific activities in 24-hour format (e.g., 09:00)
        - Location information in **bold** text
        - Duration estimates in parentheses
        - Bullet points using '-' for individual activities

        Separate the two plans with '---' on its own line.
        """

        full_prompt = f"""User preferences: {preferences_context}
        User message: {message}

        Provide TWO distinct travel plans that cater to different aspects of the trip.
        Structure each day's activities with specific times and durations.
        Make the plans different enough to give the user a real choice.
        Consider:
        1. User's specific request and preferences
        2. Practical implementation details
        3. Cost considerations where applicable
        """

        logger.debug("Making OpenAI API call")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=2000,
            temperature=0.7
        )

        content = response.choices[0].message.content
        logger.debug(f"Received response (length: {len(content)})")

        # Split into two plans
        plans = content.split('---')
        if len(plans) != 2:
            logger.warning("OpenAI didn't return two plans, attempting to split content")
            # Fallback: split content in half
            mid = len(content) // 2
            plans = [content[:mid], content[mid:]]

        # Format the response as JSON
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

        # Verify JSON serialization
        json.dumps(formatted_response)  # This will raise an error if not JSON serializable
        return formatted_response

    except RateLimitError as e:
        logger.error(f"Rate limit error: {str(e)}")
        raise Exception(
            "We're experiencing high traffic. Please wait 30 seconds and try again."
        )
    except (APIError, APIConnectionError) as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise Exception(f"Failed to generate travel plan: {str(e)}")
    except Exception as e:
        logger.error(f"Error generating travel plan: {str(e)}", exc_info=True)
        raise Exception(f"Failed to generate travel plan: {str(e)}")

def analyze_user_preferences(query: str, selected_response: str):
    """
    Analyze user preferences based on their query and selected response
    """
    logger.debug("Starting preference analysis")
    logger.debug(f"Query: {query}")
    logger.debug(f"Selected response length: {len(selected_response)}")

    try:
        # Get the preference analyzer agent
        analyzer = agent_registry.get_agent(AgentRole.PREFERENCE_ANALYZER)
        if not analyzer:
            logger.error("Preference analyzer agent not found")
            raise ValueError("Preference analyzer agent not found")

        logger.debug("Successfully retrieved preference analyzer agent")

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

        logger.debug("Making OpenAI API call for preference analysis")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=1000,
            temperature=0.3
        )

        analysis_result = response.choices[0].message.content
        logger.debug(f"Received preference analysis (length: {len(analysis_result)})")
        return analysis_result

    except Exception as e:
        logger.error(f"Error analyzing preferences: {str(e)}", exc_info=True)
        raise Exception(f"Failed to analyze preferences: {str(e)}")