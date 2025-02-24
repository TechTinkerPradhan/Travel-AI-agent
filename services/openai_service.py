import os
import time
import logging
import threading
from datetime import datetime, timedelta
from queue import Queue
from typing import Dict, Optional
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

# Request queue and rate limiting
request_queue = Queue()
last_request_time = datetime.now()
request_lock = threading.Lock()
MIN_REQUEST_INTERVAL = 0.1  # seconds between requests

# Response cache
response_cache: Dict[str, Dict] = {}
CACHE_DURATION = timedelta(minutes=5)

def get_cached_response(message: str) -> Optional[Dict]:
    """Get cached response if available and not expired"""
    if message in response_cache:
        timestamp, response = response_cache[message]
        if datetime.now() - timestamp < CACHE_DURATION:
            logger.debug("Using cached response")
            return response
        else:
            del response_cache[message]
    return None

def cache_response(message: str, response: Dict):
    """Cache a response with timestamp"""
    response_cache[message] = (datetime.now(), response)

def validate_and_format_plan(content: str) -> list:
    """Validate and format the travel plan content"""
    try:
        if not content or len(content.strip()) < 100:
            raise ValueError("Generated content is too short")

        # Split into plans
        plans = []
        if '---' in content:
            plans = content.split('---')
        elif 'Option 2:' in content:
            plans = content.split('Option 2:')
            plans[1] = 'Option 2:' + plans[1]
        else:
            lines = content.split('\n')
            current_plan = []
            current_plan_content = []

            for line in lines:
                if line.strip().startswith(('Option 1:', '## Day')):
                    if current_plan and not current_plan_content:
                        current_plan_content = current_plan
                        current_plan = []
                current_plan.append(line)

            if current_plan:
                if current_plan_content:
                    plans = ['\n'.join(current_plan_content), '\n'.join(current_plan)]
                else:
                    mid = len(lines) // 2
                    plans = ['\n'.join(lines[:mid]), '\n'.join(lines[mid:])]

        # Format and validate each plan
        formatted_plans = []
        for i, plan in enumerate(plans):
            plan = plan.strip()
            if not plan:
                continue

            if not any(plan.startswith(prefix) for prefix in ['Option', '#']):
                plan = f"Option {i+1}:\n{plan}"

            if '## Day' not in plan:
                lines = plan.split('\n')
                formatted_lines = []
                current_day = 1
                for line in lines:
                    if line.lower().startswith(('morning', 'afternoon', 'evening')):
                        formatted_lines.append(f"\n## Day {current_day}")
                        current_day += 1
                    formatted_lines.append(line)
                plan = '\n'.join(formatted_lines)

            formatted_plans.append(plan)

        if len(formatted_plans) < 2:
            raise ValueError("Failed to generate two distinct plans")

        return formatted_plans

    except Exception as e:
        logger.error(f"Error in validate_and_format_plan: {str(e)}")
        raise

def process_request():
    """Process requests from the queue with rate limiting"""
    global last_request_time

    while True:
        try:
            args = request_queue.get()
            if args is None:
                break

            message, user_preferences = args

            # Check cache first
            cached_response = get_cached_response(message)
            if cached_response:
                request_queue.task_done()
                return cached_response

            # Implement request spacing
            with request_lock:
                now = datetime.now()
                time_since_last = (now - last_request_time).total_seconds()
                if time_since_last < MIN_REQUEST_INTERVAL:
                    time.sleep(MIN_REQUEST_INTERVAL - time_since_last)
                last_request_time = datetime.now()

            # Generate the travel plan
            response = generate_travel_plan_internal(message, user_preferences)

            # Cache the successful response
            if response and response.get("status") == "success":
                cache_response(message, response)

            request_queue.task_done()
            return response

        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            request_queue.task_done()
            raise

# Start the request processing thread
request_thread = threading.Thread(target=process_request, daemon=True)
request_thread.start()

def generate_travel_plan_internal(message: str, user_preferences: Dict) -> Dict:
    """Internal function to generate travel plan with retries"""
    max_retries = 5
    base_delay = 0.5
    last_error = None

    system_prompt = """You are a travel planning assistant that provides TWO different travel plan options.
Each plan MUST include:
1. A descriptive title starting with 'Option 1:' or 'Option 2:'
2. Daily activities marked with '## Day X: [Title]'
3. Times in 24-hour format (e.g., 09:00)
4. Locations in **bold** text
5. Duration estimates in (parentheses)
6. Activities as bullet points with '-'

Separate the two plans with '---' on a new line."""

    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1}/{max_retries} to generate travel plan")

            preferences_str = ""
            if user_preferences:
                preferences_str = "\nConsider these preferences:\n" + "\n".join(
                    f"- {key}: {value}" 
                    for key, value in user_preferences.items() 
                    if value
                )

            user_prompt = f"{preferences_str}\n\nUser request: {message}\n\nProvide TWO distinct travel plans with detailed timings and locations."

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
            logger.debug(f"Received response of length: {len(content)}")

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
            delay = base_delay * (attempt + 1)
            logger.warning(f"Rate limit hit (attempt {attempt + 1}/{max_retries}). Waiting {delay:.1f} seconds...")

            if attempt == max_retries - 1:
                raise Exception("Service is experiencing high demand. Please try again in a few moments.")

            time.sleep(delay)
            continue

        except (APIError, APIConnectionError) as e:
            logger.error(f"OpenAI API error: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            raise Exception("Unable to connect to our service. Please try again.")

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise Exception("An error occurred while generating your travel plan. Please try again.")

    if last_error:
        raise last_error

def generate_travel_plan(message: str, user_preferences: Dict) -> Dict:
    """Public interface for travel plan generation with queue management"""
    try:
        # Add request to queue
        request_queue.put((message, user_preferences))
        return process_request()
    except Exception as e:
        logger.error(f"Error in generate_travel_plan: {str(e)}")
        raise Exception(str(e))

def analyze_user_preferences(query: str, selected_response: str) -> Optional[str]:
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