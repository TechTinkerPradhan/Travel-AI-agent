import os
import time
import random
import logging
from openai import OpenAI, RateLimitError
from services.ai_agents import AgentRegistry, AgentRole

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-api-key")
client = OpenAI(api_key=OPENAI_API_KEY)
agent_registry = AgentRegistry()

def generate_travel_plan(message, user_preferences):
    """
    Generate multiple travel recommendations using OpenAI's API with specialized agents
    """
    max_retries = 5
    base_delay = 3

    for attempt in range(max_retries):
        try:
            # Get the most appropriate agent for the query
            agent = agent_registry.get_best_agent_for_query(message)
            logger.debug(f"Selected agent role: {agent.role.value}")
            logger.debug(f"Agent temperature: {agent.temperature}")

            # Prepare context with user preferences
            preferences_context = "\n".join([
                f"{key}: {value}" 
                for key, value in user_preferences.items()
                if value
            ])
            logger.debug(f"User preferences context: {preferences_context}")

            # Generate two alternative responses with slightly different temperatures
            responses = []
            for temp_adjustment in [-0.1, 0.1]:
                adjusted_temp = agent.temperature + temp_adjustment
                logger.debug(f"Generating response with temperature: {adjusted_temp}")

                system_prompt = f"""{agent.system_prompt}
                Additionally, provide your response in a well-formatted structure with:
                - Clear headings using markdown (##)
                - Each day's activities clearly marked with '## Day X: [Title]'
                - Time-specific activities in 24-hour format (e.g., 09:00)
                - Location information in bold text
                - Duration estimates in parentheses
                - Bullet points for individual activities
                """

                full_prompt = f"""User preferences: {preferences_context}
                User message: {message}

                Provide a unique travel recommendation as a {agent.role.value} specialist.
                Focus on a different aspect or approach than any previous response.
                Structure each day's activities with specific times and durations.
                Consider:
                1. User's specific request and preferences
                2. Your specialized domain knowledge
                3. Practical implementation details
                4. Cost considerations where applicable
                """

                logger.debug(f"Making OpenAI API call for response {len(responses) + 1}")
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": full_prompt}
                    ],
                    max_tokens=2000,
                    temperature=adjusted_temp
                )

                content = response.choices[0].message.content
                logger.debug(f"Received response {len(responses) + 1} (length: {len(content)})")
                logger.debug(f"Response content preview: {content[:200]}...")
                responses.append(content)

            # Format the responses for presentation
            formatted_response = {
                "status": "success",
                "agent_type": agent.role.value,
                "alternatives": [
                    {
                        "id": f"option_{i+1}",
                        "content": response,
                        "type": "itinerary"  # Mark as itinerary for frontend processing
                    }
                    for i, response in enumerate(responses)
                ]
            }
            logger.debug(f"Formatted final response with {len(formatted_response['alternatives'])} alternatives")
            logger.debug(f"Response structure: {formatted_response.keys()}")
            return formatted_response

        except RateLimitError as e:
            logger.error(f"Rate limit error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise Exception(
                    "We're experiencing high traffic. Please wait 30 seconds and try again. "
                    "This helps ensure a better response when you retry."
                )

            jitter = random.uniform(1, 3)
            delay = (base_delay * (2 ** attempt)) + jitter
            logger.info(f"Rate limit hit, waiting {delay:.2f} seconds before retry")
            time.sleep(delay)
            continue

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