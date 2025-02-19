import os
import time
import random
import logging
from openai import OpenAI, RateLimitError
from services.ai_agents import AgentRegistry, AgentRole # Added import for AgentRole

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

            # Prepare context with user preferences
            preferences_context = "\n".join([
                f"{key}: {value}" 
                for key, value in user_preferences.items()
                if value
            ])

            # Generate two alternative responses with slightly different temperatures
            responses = []
            for temp_adjustment in [-0.1, 0.1]:
                system_prompt = f"""{agent.system_prompt}
                Additionally, provide your response in a well-formatted structure with:
                - Clear headings using markdown (##)
                - Bullet points for lists
                - Emphasis on key points using bold text
                - Short paragraphs for readability"""

                full_prompt = f"""User preferences: {preferences_context}
                User message: {message}

                Provide a unique travel recommendation as a {agent.role.value} specialist.
                Focus on a different aspect or approach than any previous response.
                Consider:
                1. User's specific request and preferences
                2. Your specialized domain knowledge
                3. Practical implementation details
                4. Cost considerations where applicable
                """

                logging.debug(f"Attempt {attempt + 1} of {max_retries} to generate travel plan")
                logging.debug(f"Using agent role: {agent.role.value}")

                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": full_prompt}
                    ],
                    max_tokens=2000,
                    temperature=agent.temperature + temp_adjustment
                )

                responses.append(response.choices[0].message.content)

            # Format the responses for presentation
            return {
                "status": "success",
                "agent_type": agent.role.value,
                "alternatives": [
                    {
                        "id": f"option_{i+1}",
                        "content": response
                    }
                    for i, response in enumerate(responses)
                ]
            }

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

def analyze_user_preferences(query: str, selected_response: str):
    """
    Analyze user preferences based on their query and selected response
    """
    try:
        # Get the preference analyzer agent
        analyzer = agent_registry.get_agent(AgentRole.PREFERENCE_ANALYZER)

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

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=1000,
            temperature=0.3
        )

        return response.choices[0].message.content

    except Exception as e:
        logging.error(f"Error analyzing preferences: {str(e)}")
        raise Exception(f"Failed to analyze preferences: {str(e)}")