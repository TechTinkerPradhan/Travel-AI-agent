# AI Travel Assistant Documentation

## Project Overview
The AI Travel Assistant is a sophisticated web application that helps users plan personalized travel itineraries through conversational AI and integrates with various services including Google Calendar and Airtable for a seamless travel planning experience.

## Core Features

### 1. Intelligent Travel Planning
The system uses OpenAI's GPT-4 model to generate detailed, personalized travel itineraries. Key features include:

```python
# Example of our travel plan generation system
def generate_travel_plan(message, user_preferences):
    """
    Generate travel recommendations using OpenAI's API with the following features:
    - Structured daily itineraries
    - Time-specific activities
    - Location information
    - Duration estimates
    """
    system_prompt = """You are a travel planning assistant. Provide responses in a well-formatted structure with:
    - Clear headings using markdown (##)
    - Each day's activities clearly marked with '## Day X: [Title]'
    - Time-specific activities in 24-hour format (e.g., 09:00)
    - Location information in bold text
    - Duration estimates in parentheses
    - Bullet points for individual activities
    """
```

### 2. Preference Management System
The application stores and learns from user preferences using Airtable:

```python
# Airtable integration for user preferences
def save_user_preferences(user_id: str, preferences: Dict) -> Dict:
    """
    Save or update user preferences in the 'User Preferences' table.
    - Stores budget preferences
    - Travel style preferences
    - Links to past itineraries
    """
    fields = {
        'User ID': user_id,
        'Budget Preference': preferences.get('budget'),
        'Travel Style': preferences.get('travelStyle')
    }
```

### 3. Google Calendar Integration
Seamless integration with Google Calendar for saving and managing travel itineraries:

```python
# Calendar integration features
def create_calendar_events(credentials_dict, itinerary_content, start_date=None):
    """
    Creates events in Google Calendar with:
    - Daily activities
    - Location information
    - Duration tracking
    - Timezone management
    """
```

## Unique Features

### 1. Temperature-Controlled AI Agents
Our system uses a sophisticated agent system with dynamic temperature control:

```python
class AgentRole(Enum):
    ITINERARY_PLANNER = "Itinerary Planner"
    CULTURAL_EXPERT = "Cultural Expert"
    BUDGET_OPTIMIZER = "Budget Optimizer"
    ADVENTURE_SPECIALIST = "Adventure Specialist"
    PREFERENCE_ANALYZER = "Preference Analyzer"

class TravelAgent:
    def __init__(self, role: AgentRole, temperature: float = 0.7):
        self.role = role
        self.temperature = temperature
        
    @property
    def system_prompt(self):
        """Returns role-specific system prompt"""
        prompts = {
            AgentRole.ITINERARY_PLANNER: "You are an expert travel itinerary planner...",
            AgentRole.CULTURAL_EXPERT: "You are a cultural expert with deep knowledge...",
            # ... other role-specific prompts
        }
        return prompts.get(self.role)
```

### 2. Intelligent Date Extraction
The system can intelligently extract and process dates from natural language:

```python
def extract_dates_from_itinerary(content: str) -> tuple:
    """
    Extracts start and end dates using:
    - Regular expressions for date patterns
    - Natural language processing for relative dates
    - Fallback mechanisms for implicit durations
    """
```

### 3. Progressive Enhancement
The application features a progressive enhancement system that:
- Analyzes user preferences from interactions
- Adjusts AI response temperature based on user engagement
- Stores and retrieves past successful itineraries

## Security Features
- Secure session management
- OAuth 2.0 implementation for Google Calendar
- Environment variable management for sensitive data
- Rate limiting and error handling

## Future Work

### 1. Enhanced AI Capabilities
- Implementation of multi-agent conversations
- Integration of location-aware services
- Real-time weather and event integration
- Sentiment analysis for user feedback

### 2. Technical Enhancements
- Integration with flight booking APIs
- Real-time pricing updates
- Mobile application development
- Offline mode support

### 3. User Experience Improvements
- Interactive map integration
- Real-time collaboration features
- Social sharing capabilities
- Customizable itinerary templates

### 4. Machine Learning Enhancements
- User preference learning
- Itinerary optimization based on past successes
- Automated temperature adjustment
- Context-aware recommendations

## API Integration Points

The system currently integrates with:
1. OpenAI API (GPT-4)
2. Google Calendar API
3. Airtable API

Future integrations planned:
1. Weather APIs
2. Booking.com API
3. TripAdvisor API
4. Local Events APIs

## Development Guidelines

### Temperature Control
- Base temperature: 0.7
- Adjustment range: ±0.1
- Context-specific adjustments based on:
  - User preferences
  - Query complexity
  - Required creativity level

### Agent Selection
Agents are selected based on:
- Query content analysis
- User preferences
- Previous successful interactions

## Installation and Setup

### Prerequisites
- Python 3.11+
- Required packages listed in pyproject.toml
- Environment variables:
  - OPENAI_API_KEY
  - GOOGLE_CLIENT_ID
  - GOOGLE_CLIENT_SECRET
  - AIRTABLE_ACCESS_TOKEN
  - AIRTABLE_BASE_ID

### Getting Started
1. Clone the repository
2. Install dependencies from pyproject.toml
3. Set up environment variables
4. Run the Flask application

## Contribution Guidelines
- Follow PEP 8 style guide
- Maintain comprehensive documentation
- Write unit tests for new features
- Use type hints for better code clarity
