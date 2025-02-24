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

def validate_and_format_plan(content):
    """Validate and format the travel plan content"""
    try:
        # Basic validation
        if not content or len(content.strip()) < 100:
            raise ValueError("Generated content is too short or empty")

        # Split into plans
        plans = []
        if '---' in content:
            plans = content.split('---')
        elif 'Option 2:' in content:
            plans = content.split('Option 2:')
            plans[1] = 'Option 2:' + plans[1]
        else:
            # Try to identify natural breaks in the content
            lines = content.split('\n')
            current_plan = []
            current_plan_content = []

            for line in lines:
                if line.strip().startswith('Option 1:') or line.strip().startswith('## Day'):
                    if current_plan and not current_plan_content:
                        current_plan_content = current_plan
                        current_plan = []
                current_plan.append(line)

            if current_plan:
                if current_plan_content:
                    plans = ['\n'.join(current_plan_content), '\n'.join(current_plan)]
                else:
                    # If no clear break found, split roughly in half
                    mid = len(lines) // 2
                    plans = ['\n'.join(lines[:mid]), '\n'.join(lines[mid:])]

        # Validate each plan
        formatted_plans = []
        for i, plan in enumerate(plans):
            plan = plan.strip()
            if not plan:
                continue

            # Ensure plan has a title
            if not any(plan.startswith(prefix) for prefix in ['Option', '#']):
                plan = f"Option {i+1}:\n{plan}"

            # Ensure each plan has day markers
            if '## Day' not in plan:
                logger.warning(f"Plan {i+1} missing day markers, attempting to format")
                lines = plan.split('\n')
                formatted_lines = []
                current_day = 1
                for line in lines:
                    if line.lower().startswith(('morning', 'afternoon', 'evening')) and not any(l.startswith('## Day') for l in formatted_lines[-5:] if formatted_lines):
                        formatted_lines.append(f"\n## Day {current_day}")
                        current_day += 1
                    formatted_lines.append(line)
                plan = '\n'.join(formatted_lines)

            formatted_plans.append(plan)

        if len(formatted_plans) < 2:
            raise ValueError("Failed to generate two distinct travel plans")

        return formatted_plans
    except Exception as e:
        logger.error(f"Error in validate_and_format_plan: {str(e)}")
        raise

def generate_travel_plan(message, user_preferences):
    """Generate travel recommendations using OpenAI's API with robust error handling"""
    max_retries = 3
    base_delay = 2  # Base delay in seconds
    last_error = None

    system_prompt = """You are a travel planning assistant that provides TWO different travel plan options.
Each plan MUST include:
1. A descriptive title starting with 'Option 1:' or 'Option 2:'
2. Daily activities marked with '## Day X: [Title]'
3. Times in 24-hour format (e.g., 09:00)
4. Locations in **bold** text
5. Duration estimates in (parentheses)
6. Activities as bullet points with '-'

Separate the two plans with '---' on a new line.

Example format:
Option 1: Cultural Exploration
## Day 1: City Discovery
09:00 - Visit **Central Museum** (2 hours)
- Guided tour of historical artifacts
- Special exhibition on local culture

[Continue with more days...]
---
Option 2: Adventure Journey
[Second plan in same format...]"""

    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1}/{max_retries} to generate travel plan")

            # Format user preferences
            preferences_str = ""
            if user_preferences:
                preferences_str = "\nConsider these preferences:\n" + "\n".join(
                    f"- {key}: {value}" 
                    for key, value in user_preferences.items() 
                    if value
                )

            user_prompt = f"{preferences_str}\n\nUser request: {message}\n\nProvide TWO distinct travel plans with detailed timings and locations."

            # Make API call
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            # Get and validate content
            content = response.choices[0].message.content
            logger.debug(f"Received response of length: {len(content)}")

            # Validate and format the plans
            formatted_plans = validate_and_format_plan(content)

            return {
                "status": "success",
                "alternatives": [
                    {
                        "id": f"option_{i+1}",
                        "content": plan.strip(),
                        "type": "itinerary"
                    }
                    for i, plan in enumerate(formatted_plans)
                ]
            }

        except RateLimitError as e:
            last_error = e
            delay = (base_delay ** attempt) + (attempt * 0.1)
            logger.warning(f"Rate limit hit (attempt {attempt + 1}/{max_retries}). Waiting {delay:.1f} seconds...")

            if attempt == max_retries - 1:
                raise Exception("Our AI service is currently busy. Please wait a moment and try again.")

            time.sleep(delay)
            continue

        except APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise Exception("There was an issue connecting to our AI service. Please try again.")

        except APIConnectionError as e:
            logger.error(f"OpenAI connection error: {str(e)}")
            if attempt == max_retries - 1:
                raise Exception("We're having trouble connecting to our AI service. Please try again later.")
            time.sleep(1)
            continue

        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            if attempt == max_retries - 1:
                raise Exception("We couldn't generate a valid travel plan. Please try rephrasing your request.")
            continue

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise Exception("Something went wrong while planning your trip. Please try again.")

    if last_error:
        raise last_error

def analyze_user_preferences(query: str, selected_response: str):
    """Analyze user preferences from query and selected response"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """Analyze the user's travel preferences from their query and selected plan.
Focus on:
- Budget level (budget, moderate, luxury)
- Travel style (adventure, relaxation, cultural)
- Activity interests
- Time-related preferences"""
                },
                {"role": "user", "content": f"Query: {query}\n\nSelected Plan: {selected_response}"}
            ],
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error analyzing preferences: {str(e)}", exc_info=True)
        return None