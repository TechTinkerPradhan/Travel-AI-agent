import os
from openai import OpenAI

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-api-key")
client = OpenAI(api_key=OPENAI_API_KEY)

def generate_travel_plan(message, user_preferences):
    """
    Generate travel recommendations using OpenAI's API
    """
    try:
        system_prompt = """You are a knowledgeable travel assistant. Create personalized travel 
        recommendations based on user preferences. Focus on providing practical, detailed itineraries 
        that include activities, estimated costs, and timing."""
        
        # Prepare the message with user preferences context
        full_prompt = f"""User preferences: {user_preferences}
        User message: {message}
        Please provide a detailed travel recommendation."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"Failed to generate travel plan: {str(e)}")
