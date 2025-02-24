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
    Generate travel recommendations using OpenAI's API
    """
    try:
        logger.debug("Starting travel plan generation")
        logger.debug(f"Message length: {len(message)}")
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

        Format requirements:
        1. Use '---' on its own line to separate the two plans
        2. Ensure each day's activities are properly spaced and formatted
        3. Include specific times and durations for all activities
        4. Use consistent markdown formatting throughout
        """

        # Check if this is a refinement request
        is_refinement = "refine" in message.lower() and "previous plan" in message.lower()

        if is_refinement:
            system_prompt += """
            For refinement requests:
            1. Carefully consider the feedback provided
            2. Maintain the same format and structure
            3. Provide two distinct alternatives
            4. Keep successful elements from the previous plan
            5. Clearly address the specific refinement requests
            """

        full_prompt = f"""User preferences: {preferences_context}
        User message: {message}

        Provide TWO distinct travel plans that cater to different aspects of the trip.
        Make each plan detailed and practical, with clear timings and locations.
        """

        logger.debug("Making OpenAI API call")
        max_retries = 3
        retry_count = 0
        last_error = None

        while retry_count < max_retries:
            try:
                logger.debug(f"Attempt {retry_count + 1} of {max_retries}")
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
                    # Try to find natural break points in the content
                    if "Option 2:" in content:
                        plans = content.split("Option 2:")
                        plans[1] = "Option 2:" + plans[1]
                    else:
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

                logger.debug("Successfully formatted response")
                return formatted_response

            except RateLimitError as e:
                last_error = e
                retry_count += 1
                if retry_count == max_retries:
                    logger.error("Rate limit reached, max retries exceeded")
                    raise Exception("Rate limit exceeded, please try again later")
                logger.warning(f"Rate limit hit, waiting {2 ** retry_count} seconds")
                time.sleep(2 ** retry_count)  # Exponential backoff

            except (APIError, APIConnectionError) as e:
                logger.error(f"OpenAI API error: {str(e)}", exc_info=True)
                raise Exception(f"Error communicating with OpenAI: {str(e)}")

            except Exception as e:
                logger.error(f"Unexpected error in travel plan generation: {str(e)}", exc_info=True)
                raise Exception(f"Failed to generate travel plan: {str(e)}")

    except Exception as e:
        logger.error(f"Error generating travel plan: {str(e)}", exc_info=True)
        if last_error:
            logger.error(f"Last error before failure: {str(last_error)}")
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