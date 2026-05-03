# -*- coding: utf-8 -*-
"""
LangGraph StateGraph assembly for the estimation agent.

Entry point: input_processor
Exit point:  response_formatter → END
"""
from langgraph.graph import END, StateGraph

from agent.graph.state import AgentState
from agent.nodes.clarification import clarification_node
from agent.nodes.estimation import estimation_node
from agent.nodes.fallback import fallback_node
from agent.nodes.input_processor import input_processor
from agent.nodes.intent_classifier import intent_classifier
from agent.nodes.project_context import project_context_node
from agent.nodes.project_manager import project_manager_node
from agent.nodes.response_formatter import response_formatter
from agent.nodes.risk import risk_node
from agent.nodes.similar_tasks import similar_tasks_node
from agent.nodes.sprint_planner import sprint_planner_node

# ── routing functions ──────────────────────────────────────────────────────────


def _route_intent(state: AgentState) -> str:
    """
    Map intent to the next node name after intent_classifier.

    Sprint is detected by the presence of pre-loaded sprint_tasks rather than
    the intent field, because run_sprint_agent passes an empty user_input which
    would cause intent_classifier to return 'unknown'.

    :param state: Current agent state with intent already set.
    :return: Node name string for the conditional edge.
    """
    if state.get("sprint_tasks"):
        return "sprint_planner"
    intent = state.get("intent", "unknown")
    if intent == "estimate":
        return "project_context"
    if intent in ("project_add", "project_switch"):
        return "project_manager"
    if intent == "sprint":
        return "sprint_planner"
    return "fallback"


def _route_clarification(state: AgentState) -> str:
    """
    Route to estimation or directly to formatter depending on clarification flag.

    :param state: Current agent state after clarification_node has run.
    :return: Node name string for the conditional edge.
    """
    if state.get("clarification_needed"):
        return "response_formatter"  # skip estimation; ask user first
    return "estimation"


# ── graph definition ───────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """
    Construct and return the compiled estimation StateGraph.

    :return: Compiled LangGraph application ready to invoke.
    """
    g = StateGraph(AgentState)

    # register nodes
    g.add_node("input_processor", input_processor)
    g.add_node("intent_classifier", intent_classifier)
    g.add_node("project_context", project_context_node)
    g.add_node("similar_tasks", similar_tasks_node)
    g.add_node("clarification", clarification_node)
    g.add_node("estimation", estimation_node)
    g.add_node("risk", risk_node)
    g.add_node("project_manager", project_manager_node)
    g.add_node("sprint_planner", sprint_planner_node)
    g.add_node("fallback", fallback_node)
    g.add_node("response_formatter", response_formatter)

    # entry point
    g.set_entry_point("input_processor")

    # linear edges
    g.add_edge("input_processor", "intent_classifier")
    g.add_edge("project_context", "similar_tasks")
    g.add_edge("similar_tasks", "clarification")
    g.add_edge("estimation", "risk")
    g.add_edge("risk", "response_formatter")
    g.add_edge("project_manager", "response_formatter")
    g.add_edge("sprint_planner", "response_formatter")
    g.add_edge("fallback", "response_formatter")
    g.add_edge("response_formatter", END)

    # conditional: after intent_classifier
    g.add_conditional_edges(
        "intent_classifier",
        _route_intent,
        {
            "project_context": "project_context",
            "project_manager": "project_manager",
            "sprint_planner": "sprint_planner",
            "fallback": "fallback",
        },
    )

    # conditional: after clarification_node
    g.add_conditional_edges(
        "clarification",
        _route_clarification,
        {
            "response_formatter": "response_formatter",
            "estimation": "estimation",
        },
    )

    return g.compile()


# module-level compiled graph — import this to invoke the agent
graph = build_graph()
