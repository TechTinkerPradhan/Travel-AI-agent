import os
import time
import random
import logging
from openai import OpenAI, RateLimitError
from services.ai_agents import AgentRegistry

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-api-key")
client = OpenAI(api_key=OPENAI_API_KEY)
agent_registry = AgentRegistry()

def generate_travel_plan(message, user_preferences):
    """
    Generate travel recommendations using OpenAI's API with specialized agents
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

            # Use the agent's specialized system prompt
            system_prompt = agent.system_prompt

            # Prepare the full prompt with context
            full_prompt = f"""User preferences: {preferences_context}
            User message: {message}

            Provide recommendations based on your expertise as a {agent.role.value} specialist.
            Consider the following aspects:
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
                temperature=agent.temperature
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