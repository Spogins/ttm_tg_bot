from aiogram.fsm.state import State, StatesGroup


class ProjectStates(StatesGroup):
    awaiting_file = State()
    awaiting_name = State()


class EstimationStates(StatesGroup):
    awaiting_task = State()
    clarifying = State()
    confirming = State()
    awaiting_actual_hours = State()
