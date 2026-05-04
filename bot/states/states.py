# -*- coding: utf-8 -*-
"""
FSM state groups for project management and task estimation flows.
"""
from aiogram.fsm.state import State, StatesGroup


class ProjectStates(StatesGroup):
    """
    States for the project creation and update conversation flow.
    """

    awaiting_name = State()
    awaiting_description = State()
    awaiting_stack = State()
    awaiting_update_description = State()
    awaiting_update_stack = State()
    awaiting_template_name = State()  # user types a short label before saving a template


class EstimationStates(StatesGroup):
    """
    States for the task estimation conversation flow.
    """

    selecting_scope = State()
    awaiting_task_name = State()
    awaiting_task = State()
    clarifying = State()
    selecting_mode = State()
    confirming_breakdown = State()
    awaiting_actual_hours = State()


class SprintStates(StatesGroup):
    """
    States for the sprint planning conversation flow.
    """

    awaiting_hours = State()
    awaiting_tasks = State()
