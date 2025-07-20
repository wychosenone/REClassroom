"""
Defines the state object for the LangGraph multi-agent system.
"""
from typing import List, Dict, TypedDict

class GraphState(TypedDict):
    """
    Represents the state of our conversation graph.

    Attributes:
        project_context: The overarching context of the project scenario.
        stakeholders: A list of stakeholder configurations.
        dialogue_history: The full history of the conversation.
        turn_roster: A list of stakeholder roles scheduled to speak in the current turn.
        is_concluding_turn: A flag to indicate if the conversation is in a summary/conclusion phase.
        ai_response_style: The desired verbosity of the AI agents ('Normal', 'Concise', 'Detailed').
        negotiation_status: A dictionary tracking the status of key topics (e.g., {"Feature X": "Disputed"}).
        elicited_requirements: A list of requirements elicited during the conversation.
        current_ambiguity_score: The current ambiguity score.
        ambiguity_score_reason: The reason for the current ambiguity score.
        ambiguity_history: A list of past ambiguity scores.
        difficulty_level: The difficulty setting for the current session.
    """
    project_context: str
    stakeholders: List[Dict]
    dialogue_history: List[Dict]
    turn_roster: List[str]
    is_concluding_turn: bool
    ai_response_style: str
    negotiation_status: Dict[str, str]
    elicited_requirements: List[Dict]
    current_ambiguity_score: int
    ambiguity_score_reason: str
    ambiguity_history: List[int]
    difficulty_level: str 