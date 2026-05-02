"""
FSM state groups for project management and task estimation flows.
"""
from aiogram.fsm.state import State, StatesGroup


class ProjectStates(StatesGroup):
    """
    States for the project creation and update conversation flow.
    """
    awaiting_file = State()
    awaiting_name = State()
    awaiting_update_file = State()


class EstimationStates(StatesGroup):
    """
    States for the task estimation conversation flow.
    """
    awaiting_task = State()
    clarifying = State()
    confirming = State()
    awaiting_actual_hours = State()
