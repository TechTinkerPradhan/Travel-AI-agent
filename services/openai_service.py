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

        # Handle refinement requests
        is_refinement = "refine" in message.lower() and "previous plan" in message.lower()
        if is_refinement:
            system_prompt += """
For refinement requests:
1. Keep successful elements from the previous plan
2. Address the specific refinement requests
3. Maintain the same format
4. Provide two distinct alternatives
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

        logger.debug("Making OpenAI API call")
        for attempt in range(3):  # 3 retries
            try:
                logger.debug(f"Attempt {attempt + 1} to call OpenAI API")
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
                logger.debug(f"Received response length: {len(content)}")

                # Split into two plans
                plans = content.split('---')
                if len(plans) != 2:
                    logger.warning("OpenAI response doesn't contain two plans, attempting to split")
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
                logger.warning(f"Rate limit hit on attempt {attempt + 1}: {str(e)}")
                if attempt == 2:  # Last attempt
                    raise Exception("Rate limit exceeded. Please try again later.")
                time.sleep(2 ** attempt)  # Exponential backoff

            except (APIError, APIConnectionError) as e:
                logger.error(f"OpenAI API error on attempt {attempt + 1}: {str(e)}")
                if attempt == 2:
                    raise Exception(f"Error communicating with OpenAI: {str(e)}")
                time.sleep(1)

            except Exception as e:
                logger.error(f"Unexpected error in travel plan generation: {str(e)}", exc_info=True)
                raise Exception(f"Failed to generate travel plan: {str(e)}")

    except Exception as e:
        logger.error(f"Error in generate_travel_plan: {str(e)}", exc_info=True)
        raise Exception(str(e))

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