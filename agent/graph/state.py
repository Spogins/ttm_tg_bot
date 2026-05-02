# -*- coding: utf-8 -*-
"""
LangGraph state types for the estimation agent: intent aliases, EstimationResult, and AgentState.
"""
import operator
from typing import Annotated, Literal

from typing_extensions import TypedDict

# Possible routing outcomes from intent_classifier
Intent = Literal["estimate", "project_add", "project_switch", "sprint", "history", "unknown"]

# Confidence level returned by estimation_node alongside the hours estimate
Confidence = Literal["high", "medium", "low"]


class Subtask(TypedDict):
    """
    A single decomposed unit of work with its estimated duration.
    """

    name: str
    hours: float


class EstimationResult(TypedDict):
    """
    Structured output produced by estimation_node after a Claude call.
    """

    subtasks: list[Subtask]
    total_hours: float
    complexity: int  # 1–5
    confidence: Confidence


class AgentState(TypedDict):
    """
    Shared state passed between every node of the estimation graph.
    """

    user_id: int
    project_id: str | None
    user_input: str
    intent: Intent
    project_context: list[str]  # top-k chunks from Qdrant project collection
    similar_tasks: list[dict]  # top-k past estimations from estimations_{user_id}
    clarification_needed: bool
    clarification_question: str
    estimation: EstimationResult | None
    risks: list[str]
    formatted_response: str
    tokens_used: Annotated[int, operator.add]  # accumulated across all nodes via reducer
    conversation_history: list[dict]  # last 5 messages loaded from MongoDB
