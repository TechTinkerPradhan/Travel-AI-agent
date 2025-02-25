import os
import time
import logging
from openai import OpenAI, RateLimitError, APIError, APIConnectionError
from services.ai_agents import AgentRegistry, AgentRole

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY is not set")
    logger.error("OPENAI_API_KEY is not set")
    raise ValueError("OPENAI_API_KEY environment variable is required")

print(f"Using OpenAI API key starting with: {OPENAI_API_KEY[:8]}...")
client = OpenAI(api_key=OPENAI_API_KEY)
agent_registry = AgentRegistry()

def generate_travel_plan(message, user_preferences):
    """
    Generate travel recommendations using OpenAI's API with enhanced error handling
    """
    try:
        print("=== OpenAI Service Debug ===")
        print(f"Message: {message}")
        print(f"User preferences: {user_preferences}")

        # Prepare context with user preferences
        preferences_context = "\n".join([
            f"{key}: {value}" 
            for key, value in user_preferences.items()
            if value
        ])
        print(f"Preferences context: {preferences_context}")

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

        print("Making OpenAI API call...")
        print(f"System prompt length: {len(system_prompt)}")
        print(f"Full prompt length: {len(full_prompt)}")

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            print("OpenAI API call successful")
            print(f"Response type: {type(response)}")
            print(f"Response: {response}")

        except Exception as api_error:
            print(f"OpenAI API call failed: {str(api_error)}")
            raise

        content = response.choices[0].message.content
        print(f"Content length: {len(content)}")
        print(f"Content preview: {content[:200]}...")

        # Split into two plans
        plans = content.split('---')
        if len(plans) != 2:
            print("Warning: Content not properly split into two plans")
            print(f"Number of plans found: {len(plans)}")
            # Fallback: split content in half
            mid = len(content) // 2
            plans = [content[:mid], content[mid:]]

        # Format the response
        formatted_response = {
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

        print("Final response formatted successfully")
        print(f"Response structure: {formatted_response.keys()}")
        return formatted_response

    except RateLimitError as e:
        print(f"OpenAI Rate limit error: {str(e)}")
        logger.error(f"OpenAI Rate limit error: {str(e)}")
        raise Exception("Rate limit reached. Please try again in a few moments.")

    except APIError as e:
        print(f"OpenAI API error: {str(e)}")
        logger.error(f"OpenAI API error: {str(e)}")
        raise Exception(f"API Error: {str(e)}")

    except APIConnectionError as e:
        print(f"OpenAI Connection error: {str(e)}")
        logger.error(f"OpenAI Connection error: {str(e)}")
        raise Exception("Could not connect to OpenAI. Please check your internet connection.")

    except Exception as e:
        print(f"Unexpected error in generate_travel_plan: {str(e)}")
        logger.error(f"Unexpected error in generate_travel_plan: {str(e)}", exc_info=True)
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