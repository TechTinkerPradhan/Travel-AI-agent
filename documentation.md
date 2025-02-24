# AI Travel Assistant Documentation

## System Architecture Overview

The AI Travel Assistant represents a sophisticated multi-agent system designed for personalized travel planning through natural language processing and intelligent preference management.

### Core Philosophy

Our system takes a unique approach to travel planning by leveraging:

1. **Natural Language Preference Processing**: Instead of rigid dropdown selections, we allow users to express preferences naturally:

```text
Traditional: "Country: Japan, Budget: Low, Style: Adventure"
Our Approach: "Looking for hidden gems in Japan, budget-conscious backpacker style, love hiking and local food"
```

This approach, implemented in `services/openai_service.py`, allows for richer preference extraction:

```python
def analyze_user_preferences(query: str, selected_response: str):
    """
    Extract rich preferences from natural language input
    Returns structured data including:
    - budget_preference
    - travel_style
    - activity_interests
    - time_related_preferences
    """
```

2. **Temperature-Controlled Multi-Agent System**: As seen in `services/ai_agents.py`, each agent has specific temperature settings:

```python
AgentRole.ACTIVITIES: Agent(
    temperature=0.8,  # Higher for creative activity suggestions
    expertise=["tours", "attractions", "local experiences"]
),
AgentRole.BUDGET: Agent(
    temperature=0.5,  # Lower for precise budget calculations
    expertise=["cost analysis", "budget optimization"]
),
AgentRole.PREFERENCE_ANALYZER: Agent(
    temperature=0.3,  # Lowest for accurate preference extraction
    expertise=["preference analysis", "pattern recognition"]
)
```

## Intelligent Agent System

### Agent Temperature Control
The system uses varying temperature settings for different tasks:
- Creative Tasks (0.7-0.8): Activity planning, local recommendations
- Analytical Tasks (0.3-0.5): Budget analysis, preference extraction
- Balanced Tasks (0.6): Itinerary scheduling

From `services/ai_agents.py`:
```python
class AgentRegistry:
    def __init__(self):
        self.agents: Dict[AgentRole, Agent] = {
            AgentRole.ACCOMMODATION: Agent(
                temperature=0.7,
                expertise=["hotels", "hostels", "vacation rentals"]
            ),
            # Other agents...
        }
```

### Preference Management

The system uses Airtable for preference storage and retrieval:

```python
# From services/airtable_service.py
def save_user_preferences(user_id: str, preferences: Dict):
    fields = {
        'User ID': user_id,
        'Preferences': preferences,
        'Last Updated': datetime.now().isoformat()
    }
```

### Security Features

1. **Input Validation**: 
```python
# Token limit implementation in routes.py
MAX_TOKEN_LENGTH = 500  # Configurable token limit
def validate_input(user_input: str) -> bool:
    return len(user_input.split()) <= MAX_TOKEN_LENGTH
```

2. **Itinerary Storage Flow**:
```javascript
// From static/js/chat.js
async function saveItinerary(itineraryText) {
    const response = await fetch('/api/save_itinerary', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            itinerary: itineraryText,
            userId: getCurrentUserId()
        })
    });
}
```

## Advanced Features

### Tree of Thought Planning
From `services/treeofthought.py`, our system implements a sophisticated planning approach:

```python
class Orchestrator:
    def plan_trip(self, user_prompt, user_profile):
        # 1) Explore multiple destinations
        branches = self.destination_agent.explore(user_prompt)
        # 2) Budget analysis
        branches = self.budget_agent.check_budget(branches)
        # 3) Preference scoring
        branches = self.preference_agent.score(branches)
```

### Calendar Integration
Seamless Google Calendar integration for saving itineraries:

```python
# From services/calendar_service.py
def create_calendar_events(credentials_dict, itinerary_content):
    """Creates events in Google Calendar with location and duration tracking"""
```

## Future Development

1. **Dynamic Agent Assignment**:
```python
def get_best_agent_for_query(query: str) -> Agent:
    # Implemented in services/ai_agents.py
    query_lower = query.lower()
    scores = {role: 0 for role in self.agents}
    for role, keywords in role_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                scores[role] += 1
```

2. **Business Hours Integration**:
- Future integration with Google Places API
- Real-time availability checking
- Dynamic itinerary adjustment

## Disclaimers

- Travel times are approximations based on typical conditions
- Business hours and availability should be verified independently
- Budgets are estimates and may vary based on seasons and availability
- Recommendations are AI-generated and should be validated against current information

## Technical Requirements

- Python 3.11+
- OpenAI API access
- Google Calendar API integration
- Airtable for data storage

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