from langgraph.graph import StateGraph, END
from reclassroom.core.graph_state import GraphState
from reclassroom.core.agent_utils import (
    generate_agent_response, 
    get_routing_choice, 
    conflict_check_agent,
    ambiguity_scorer_agent
)

# --- Graph Nodes ---

def ambiguity_check_node(state: GraphState):
    """
    Calls the ambiguity scorer agent to analyze the student's latest message.
    This node updates the state with the score and reason.
    """
    return ambiguity_scorer_agent(state)

def router_node(state: GraphState):
    """
    Determines the upcoming roster of speakers and if the turn is concluding.
    """
    routing_decision = get_routing_choice(state)
    return {
        "turn_roster": routing_decision.get("roster", []),
        "is_concluding_turn": routing_decision.get("is_concluding", False)
    }

def agent_node(state: GraphState):
    """
    Invokes the agent response generation for the speaker at the front of the roster.
    The response function itself will shorten the roster.
    """
    response = generate_agent_response(state)
    return {
        "dialogue_history": response['dialogue_history'],
        "turn_roster": response['turn_roster'] # The roster is now one shorter
    }

def conflict_check_node(state: GraphState):
    """
    Calls the conflict check agent to analyze the latest turn and update the negotiation status.
    This node's output will be the *update* to the negotiation status.
    """
    update = conflict_check_agent(state)
    return {"negotiation_status": update["negotiation_status"]}

# --- Conditional Edges ---

def conditional_router(state: GraphState):
    """
    This is the core of the discussion loop. It checks the turn_roster to decide
    if the conversation should continue with another agent or if the turn is over.
    """
    if not state['turn_roster'] or state['turn_roster'][0] == "END":
        return END # End the graph execution for this turn
    else:
        return "agent_turn" # Continue the discussion loop

def conditional_entry_router(state: GraphState):
    """
    Routes the graph to the appropriate starting node based on difficulty.
    """
    if state.get('difficulty_level') == 'Hard (Expert Mode)':
        return "router" # Skip ambiguity check for experts
    else:
        return "ambiguity_check" # Start with ambiguity check for others

# --- Build the Graph ---

def build_graph():
    """
    Builds the stateful graph for multi-agent negotiation.
    """
    workflow = StateGraph(GraphState)

    # Add the nodes
    workflow.add_node("ambiguity_check", ambiguity_check_node)
    workflow.add_node("router", router_node)
    workflow.add_node("agent_turn", agent_node)
    workflow.add_node("conflict_check", conflict_check_node)
    # A dummy node to host the main conditional loop, preventing the router from being re-run.
    workflow.add_node("main_loop_router", lambda state: {})

    # Set the conditional entry point based on difficulty
    workflow.set_conditional_entry_point(
        conditional_entry_router,
        {
            "ambiguity_check": "ambiguity_check",
            "router": "router",
        }
    )
    
    # The ambiguity check (if run) leads to the single roster-setting step.
    workflow.add_edge("ambiguity_check", "router")
    
    # After the roster is set once, we enter the main conditional loop.
    workflow.add_edge("router", "main_loop_router")

    # The main loop's decision point: does another agent speak, or does the turn end?
    workflow.add_conditional_edges(
        "main_loop_router",
        conditional_router, # This function checks the roster.
        {
            "agent_turn": "agent_turn",
            END: END
        }
    )
    
    # After an agent speaks, we decide whether to check for conflicts or go back to the loop.
    workflow.add_conditional_edges(
        "agent_turn",
        # This lambda function directs the flow after an agent turn.
        lambda state: "conflict_check" if state.get('difficulty_level') != 'Hard (Expert Mode)' else "main_loop_router",
        {
            "conflict_check": "conflict_check",
            "main_loop_router": "main_loop_router"
        }
    )

    # After the conflict checker runs, it always goes back to the main loop controller.
    workflow.add_edge("conflict_check", "main_loop_router")

    return workflow.compile()

# A single global instance of the compiled graph
conversation_graph = build_graph() 