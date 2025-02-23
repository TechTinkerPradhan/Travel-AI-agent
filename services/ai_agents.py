# ai_agents.py

from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
from enum import Enum

class AgentRole(Enum):
    ACCOMMODATION = "accommodation"
    ACTIVITIES = "activities"
    ITINERARY = "itinerary"
    BUDGET = "budget"
    LOCAL_EXPERT = "local_expert"
    PREFERENCE_ANALYZER = "preference_analyzer"
    SEASONALITY_EXPERT = "seasonality_expert"  # NEW agent

@dataclass
class Agent:
    role: AgentRole
    system_prompt: str
    expertise: List[str]
    temperature: float = 0.7

class AgentRegistry:
    def __init__(self):
        self.agents: Dict[AgentRole, Agent] = {
            AgentRole.ACCOMMODATION: Agent(
                role=AgentRole.ACCOMMODATION,
                system_prompt=(
                    "You are an expert travel accommodation advisor.\n"
                    "Consider budget, location, amenities, traveler preferences.\n"
                    "Provide specific, actionable recommendations with brief explanations.\n"
                    "Format with clear headings and bullet points."
                ),
                expertise=["hotels", "hostels", "vacation rentals", "booking", "amenities"],
                temperature=0.7
            ),
            AgentRole.ACTIVITIES: Agent(
                role=AgentRole.ACTIVITIES,
                system_prompt=(
                    "You are a local activities and experiences expert.\n"
                    "Recommend unique, engaging activities based on destination and interests.\n"
                    "Consider seasonal availability, cultural significance, and authenticity.\n"
                    "Format with clear headings and bullet points."
                ),
                expertise=["tours", "attractions", "local experiences", "cultural activities"],
                temperature=0.8
            ),
            AgentRole.ITINERARY: Agent(
                role=AgentRole.ITINERARY,
                system_prompt=(
                    "You are an expert travel itinerary planner.\n"
                    "Create well-balanced, realistic schedules that maximize experiences.\n"
                    "Consider travel times, opening hours, logical flow.\n"
                    "Format with clear headings and bullet points."
                ),
                expertise=["scheduling", "route optimization", "time management"],
                temperature=0.6
            ),
            AgentRole.BUDGET: Agent(
                role=AgentRole.BUDGET,
                system_prompt=(
                    "You are a travel budget optimization expert.\n"
                    "Consider seasonal pricing, local costs, and value for money.\n"
                    "Help travelers make cost-effective decisions.\n"
                    "Format with clear headings and bullet points."
                ),
                expertise=["cost analysis", "budget optimization", "value assessment"],
                temperature=0.5
            ),
            AgentRole.LOCAL_EXPERT: Agent(
                role=AgentRole.LOCAL_EXPERT,
                system_prompt=(
                    "You are a knowledgeable local expert.\n"
                    "Share insider tips, hidden gems, and authentic experiences.\n"
                    "Consider cultural nuances and off-the-beaten-path options.\n"
                    "Format with clear headings and bullet points."
                ),
                expertise=["local culture", "hidden gems", "authentic experiences"],
                temperature=0.8
            ),
            AgentRole.PREFERENCE_ANALYZER: Agent(
                role=AgentRole.PREFERENCE_ANALYZER,
                system_prompt=(
                    "You are an expert in analyzing travel preferences.\n"
                    "Extract and categorize user preferences from travel-related conversations.\n"
                    "Focus on budget, style, accommodation, activities, time constraints.\n"
                    "Provide analysis in structured JSON."
                ),
                expertise=["preference analysis", "user profiling", "pattern recognition"],
                temperature=0.3
            ),
            # NEW: SEASONALITY_EXPERT
            AgentRole.SEASONALITY_EXPERT: Agent(
                role=AgentRole.SEASONALITY_EXPERT,
                system_prompt=(
                    "You are an expert in travel timing, seasonality, and weather considerations.\n"
                    "Recommend best times of year or day to visit a place, factoring in climate,\n"
                    "peak vs. off-peak seasons, major local events, crowd levels, and pricing.\n"
                    "Format with clear headings and bullet points."
                ),
                expertise=["weather patterns", "peak/off-peak", "climate data", "special events"],
                temperature=0.7
            )
        }

    def get_agent(self, role: AgentRole) -> Optional[Agent]:
        return self.agents.get(role)

    def get_best_agent_for_query(self, query: str) -> Agent:
        query_lower = query.lower()

        # Add some keywords for Seasonality
        role_keywords = {
            AgentRole.ACCOMMODATION: ["hotel", "stay", "hostel", "apartment", "booking", "room"],
            AgentRole.ACTIVITIES: ["activity", "tour", "visit", "see", "experience", "attraction"],
            AgentRole.ITINERARY: ["schedule", "plan", "itinerary", "timeline", "when", "order"],
            AgentRole.BUDGET: ["budget", "cost", "price", "expensive", "cheap", "afford"],
            AgentRole.LOCAL_EXPERT: ["local", "authentic", "traditional", "cultural", "hidden", "secret"],
            AgentRole.SEASONALITY_EXPERT: ["best time", "season", "peak season", "off-peak", "weather", "climate", "rainy season"]
        }

        # Initialize scores for everything except PREFERENCE_ANALYZER
        scores = {role: 0 for role in self.agents if role != AgentRole.PREFERENCE_ANALYZER}
        for role, keywords in role_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    scores[role] += 1

        # Pick the role with the highest score; fallback to ITINERARY if no hits
        best_role = max(scores.items(), key=lambda x: x[1])[0]
        if scores[best_role] == 0:
            best_role = AgentRole.ITINERARY

        return self.agents[best_role]

    def analyze_preferences(self, query: str, selected_response: str) -> Dict:
        analyzer = self.agents[AgentRole.PREFERENCE_ANALYZER]
        return {
            "agent_role": analyzer.role.value,
            "system_prompt": analyzer.system_prompt,
            "context": {
                "query": query,
                "selected_response": selected_response
            }
        }
