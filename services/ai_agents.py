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
                system_prompt="""You are an expert travel accommodation advisor. 
                Your expertise includes hotels, hostels, vacation rentals, and unique stays.
                Consider factors like budget, location, amenities, and traveler preferences.
                Provide specific, actionable recommendations with brief explanations.""",
                expertise=["hotels", "hostels", "vacation rentals", "booking", "amenities"],
                temperature=0.7
            ),
            AgentRole.ACTIVITIES: Agent(
                role=AgentRole.ACTIVITIES,
                system_prompt="""You are a local activities and experiences expert.
                Recommend unique, engaging activities based on destination and traveler interests.
                Consider seasonal availability, cultural significance, and authentic experiences.
                Focus on creating memorable travel moments.""",
                expertise=["tours", "attractions", "local experiences", "cultural activities"],
                temperature=0.8
            ),
            AgentRole.ITINERARY: Agent(
                role=AgentRole.ITINERARY,
                system_prompt="""You are an expert travel itinerary planner.
                Create well-balanced, realistic travel schedules that maximize experiences.
                Consider travel times, opening hours, and logical flow between activities.
                Optimize for efficiency while maintaining flexibility.""",
                expertise=["scheduling", "route optimization", "time management"],
                temperature=0.6
            ),
            AgentRole.BUDGET: Agent(
                role=AgentRole.BUDGET,
                system_prompt="""You are a travel budget optimization expert.
                Provide cost-effective recommendations while maintaining quality experiences.
                Consider seasonal pricing, local costs, and value for money.
                Help travelers make informed financial decisions.""",
                expertise=["cost analysis", "budget optimization", "value assessment"],
                temperature=0.5
            ),
            AgentRole.LOCAL_EXPERT: Agent(
                role=AgentRole.LOCAL_EXPERT,
                system_prompt="""You are a knowledgeable local expert.
                Share insider tips, hidden gems, and authentic local experiences.
                Consider current local trends, cultural nuances, and off-the-beaten-path options.
                Help travelers experience destinations like a local.""",
                expertise=["local culture", "hidden gems", "authentic experiences"],
                temperature=0.8
            )
        }

    def get_agent(self, role: AgentRole) -> Optional[Agent]:
        return self.agents.get(role)

    def get_best_agent_for_query(self, query: str) -> Agent:
        # Simple keyword-based matching for now
        query_lower = query.lower()
        
        # Define keyword mappings
        role_keywords = {
            AgentRole.ACCOMMODATION: ["hotel", "stay", "hostel", "apartment", "booking", "room"],
            AgentRole.ACTIVITIES: ["activity", "tour", "visit", "see", "experience", "attraction"],
            AgentRole.ITINERARY: ["schedule", "plan", "itinerary", "timeline", "when", "order"],
            AgentRole.BUDGET: ["budget", "cost", "price", "expensive", "cheap", "afford"],
            AgentRole.LOCAL_EXPERT: ["local", "authentic", "traditional", "cultural", "hidden", "secret"]
        }

        # Score each agent based on keyword matches
        scores = {role: 0 for role in AgentRole}
        for role, keywords in role_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    scores[role] += 1

        # Default to itinerary agent if no clear match
        best_role = max(scores.items(), key=lambda x: x[1])[0]
        if scores[best_role] == 0:
            best_role = AgentRole.ITINERARY

        return self.agents[best_role]
