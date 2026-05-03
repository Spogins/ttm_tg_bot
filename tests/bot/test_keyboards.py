# -*- coding: utf-8 -*-
from bot.keyboards.common import (
    actual_hours_keyboard,
    confirm_delete_keyboard,
    projects_keyboard,
    sprint_result_keyboard,
    start_keyboard,
)


class TestActualHoursKeyboard:
    def test_returns_inline_keyboard(self):
        kb = actual_hours_keyboard("abc-123")
        assert kb is not None
        assert len(kb.inline_keyboard) == 1

    def test_has_one_button(self):
        kb = actual_hours_keyboard("abc-123")
        buttons = kb.inline_keyboard[0]
        assert len(buttons) == 1

    def test_callback_data_contains_estimation_id(self):
        kb = actual_hours_keyboard("abc-123")
        btn = kb.inline_keyboard[0][0]
        assert btn.callback_data == "actual:abc-123"

    def test_button_text_contains_pencil(self):
        kb = actual_hours_keyboard("abc-123")
        btn = kb.inline_keyboard[0][0]
        assert "✏️" in btn.text


class TestStartKeyboard:
    def test_has_two_rows(self):
        kb = start_keyboard()
        assert len(kb.inline_keyboard) == 2

    def test_first_row_is_add_project(self):
        kb = start_keyboard()
        assert kb.inline_keyboard[0][0].callback_data == "add_project"

    def test_second_row_is_instructions(self):
        kb = start_keyboard()
        assert kb.inline_keyboard[1][0].callback_data == "show_instructions"


class TestProjectsKeyboard:
    def _p(self, pid: str, name: str) -> dict:
        return {"project_id": pid, "name": name}

    def test_empty_projects_shows_only_add_button(self):
        kb = projects_keyboard([])
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].callback_data == "add_project"

    def test_one_project_creates_two_rows(self):
        kb = projects_keyboard([self._p("p1", "My Project")])
        assert len(kb.inline_keyboard) == 2

    def test_project_row_has_three_buttons(self):
        kb = projects_keyboard([self._p("p1", "My Project")])
        assert len(kb.inline_keyboard[0]) == 3

    def test_active_project_shows_checkmark(self):
        kb = projects_keyboard([self._p("p1", "My Project")], active_project_id="p1")
        assert "✅" in kb.inline_keyboard[0][0].text

    def test_inactive_project_shows_bullet(self):
        kb = projects_keyboard([self._p("p1", "My Project")], active_project_id="other")
        assert "●" in kb.inline_keyboard[0][0].text

    def test_select_callback_format(self):
        kb = projects_keyboard([self._p("p1", "My Project")])
        assert kb.inline_keyboard[0][0].callback_data == "select_project:p1"

    def test_update_callback_format(self):
        kb = projects_keyboard([self._p("p1", "My Project")])
        assert kb.inline_keyboard[0][1].callback_data == "update_project:p1"

    def test_delete_callback_format(self):
        kb = projects_keyboard([self._p("p1", "My Project")])
        assert kb.inline_keyboard[0][2].callback_data == "delete_project:p1"

    def test_multiple_projects_correct_row_count(self):
        projects = [self._p(f"p{i}", f"Project {i}") for i in range(3)]
        kb = projects_keyboard(projects)
        assert len(kb.inline_keyboard) == 4  # 3 projects + add button


class TestConfirmDeleteKeyboard:
    def test_has_two_buttons(self):
        kb = confirm_delete_keyboard("p123")
        assert len(kb.inline_keyboard[0]) == 2

    def test_confirm_callback_contains_project_id(self):
        kb = confirm_delete_keyboard("p123")
        assert kb.inline_keyboard[0][0].callback_data == "confirm_delete:p123"

    def test_cancel_callback(self):
        kb = confirm_delete_keyboard("p123")
        assert kb.inline_keyboard[0][1].callback_data == "cancel_delete"


class TestSprintResultKeyboard:
    def test_has_one_button(self):
        kb = sprint_result_keyboard()
        assert len(kb.inline_keyboard[0]) == 1

    def test_export_callback(self):
        assert sprint_result_keyboard().inline_keyboard[0][0].callback_data == "sprint:export"
