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
                Provide specific, actionable recommendations with brief explanations.
                Format your response with clear headings and bullet points.""",
                expertise=["hotels", "hostels", "vacation rentals", "booking", "amenities"],
                temperature=0.7
            ),
            AgentRole.ACTIVITIES: Agent(
                role=AgentRole.ACTIVITIES,
                system_prompt="""You are a local activities and experiences expert.
                Recommend unique, engaging activities based on destination and interests.
                Consider seasonal availability, cultural significance, and authenticity.
                Focus on creating memorable travel moments.
                Format your response with clear headings and bullet points.""",
                expertise=["tours", "attractions", "local experiences", "cultural activities"],
                temperature=0.8
            ),
            AgentRole.ITINERARY: Agent(
                role=AgentRole.ITINERARY,
                system_prompt="""You are an expert travel itinerary planner.
                Create well-balanced, realistic travel schedules that maximize experiences.
                Consider travel times, opening hours, and logical flow between activities.
                Optimize for efficiency while maintaining flexibility.
                Format your response with clear headings and bullet points.""",
                expertise=["scheduling", "route optimization", "time management"],
                temperature=0.6
            ),
            AgentRole.BUDGET: Agent(
                role=AgentRole.BUDGET,
                system_prompt="""You are a travel budget optimization expert.
                Provide cost-effective recommendations while maintaining quality.
                Consider seasonal pricing, local costs, and value for money.
                Help travelers make informed financial decisions.
                Format your response with clear headings and bullet points.""",
                expertise=["cost analysis", "budget optimization", "value assessment"],
                temperature=0.5
            ),
            AgentRole.LOCAL_EXPERT: Agent(
                role=AgentRole.LOCAL_EXPERT,
                system_prompt="""You are a knowledgeable local expert.
                Share insider tips, hidden gems, and authentic local experiences.
                Consider current local trends, cultural nuances, and off-the-beaten-path options.
                Help travelers experience destinations like a local.
                Format your response with clear headings and bullet points.""",
                expertise=["local culture", "hidden gems", "authentic experiences"],
                temperature=0.8
            ),
            AgentRole.PREFERENCE_ANALYZER: Agent(
                role=AgentRole.PREFERENCE_ANALYZER,
                system_prompt="""You are an expert in analyzing travel preferences.
                Extract and categorize user preferences from travel-related conversations.
                Focus on identifying:
                1. Budget preferences (luxury, moderate, budget)
                2. Travel style (adventure, relaxation, cultural)
                3. Accommodation preferences (hotels, hostels, unique stays)
                4. Activity interests (outdoor, cultural, culinary)
                5. Time constraints and seasonality
                Provide your analysis in a structured JSON format.""",
                expertise=["preference analysis", "user profiling", "pattern recognition"],
                temperature=0.3
            )
        }

    def get_agent(self, role: AgentRole) -> Optional[Agent]:
        return self.agents.get(role)

    def get_best_agent_for_query(self, query: str) -> Agent:
        query_lower = query.lower()

        role_keywords = {
            AgentRole.ACCOMMODATION: ["hotel", "stay", "hostel", "apartment", "booking", "room"],
            AgentRole.ACTIVITIES: ["activity", "tour", "visit", "see", "experience", "attraction"],
            AgentRole.ITINERARY: ["schedule", "plan", "itinerary", "timeline", "when", "order"],
            AgentRole.BUDGET: ["budget", "cost", "price", "expensive", "cheap", "afford"],
            AgentRole.LOCAL_EXPERT: ["local", "authentic", "traditional", "cultural", "hidden", "secret"]
        }

        scores = {role: 0 for role in AgentRole if role != AgentRole.PREFERENCE_ANALYZER}
        for role, keywords in role_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    scores[role] += 1

        best_role = max(scores.items(), key=lambda x: x[1])[0]
        if scores[best_role] == 0:
            best_role = AgentRole.ITINERARY

        return self.agents[best_role]

    def analyze_preferences(self, query: str, selected_response: str) -> Dict:
        """Analyze user preferences based on their query and selected response"""
        analyzer = self.agents[AgentRole.PREFERENCE_ANALYZER]
        return {
            "agent_role": analyzer.role.value,
            "system_prompt": analyzer.system_prompt,
            "context": {
                "query": query,
                "selected_response": selected_response
            }
        }