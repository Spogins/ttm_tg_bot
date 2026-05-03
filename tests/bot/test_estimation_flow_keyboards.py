# -*- coding: utf-8 -*-
from bot.keyboards.estimation_flow import breakdown_keyboard, mode_keyboard, scope_keyboard
from services.estimation_breakdown import DEFAULT_TOGGLES


class TestScopeKeyboard:
    def test_has_continue_button(self):
        kb = scope_keyboard(selected_main=None, selected_extras=[])
        all_cb = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert "scope:continue" in all_cb

    def test_selected_main_marked_with_checkmark(self):
        kb = scope_keyboard(selected_main="backend", selected_extras=[])
        texts = [b.text for row in kb.inline_keyboard for b in row]
        assert any("✅" in t and "Backend" in t for t in texts)

    def test_unselected_main_not_marked(self):
        kb = scope_keyboard(selected_main="backend", selected_extras=[])
        texts = [b.text for row in kb.inline_keyboard for b in row]
        assert any("Frontend" in t and "✅" not in t for t in texts)

    def test_selected_extra_marked(self):
        kb = scope_keyboard(selected_main=None, selected_extras=["qa"])
        texts = [b.text for row in kb.inline_keyboard for b in row]
        assert any("✅" in t and "QA" in t for t in texts)


class TestModeKeyboard:
    def test_has_all_three_modes(self):
        kb = mode_keyboard()
        all_cb = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert {"mode:optimistic", "mode:realistic", "mode:pessimistic"} <= set(all_cb)


class TestBreakdownKeyboard:
    def _bd(self):
        return {"implementation": 8.0, "tests": 2.0, "bugfix": 1.0, "code_review": 0.5, "documentation": 0.5}

    def test_has_confirm_button(self):
        kb = breakdown_keyboard(self._bd(), DEFAULT_TOGGLES)
        all_cb = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert "breakdown:confirm" in all_cb

    def test_enabled_shows_checkmark(self):
        kb = breakdown_keyboard(self._bd(), DEFAULT_TOGGLES)
        texts = [b.text for row in kb.inline_keyboard for b in row]
        assert any("✅" in t and "Реализация" in t for t in texts)

    def test_disabled_shows_checkbox(self):
        toggles = {**DEFAULT_TOGGLES, "tests": False}
        kb = breakdown_keyboard(self._bd(), toggles)
        texts = [b.text for row in kb.inline_keyboard for b in row]
        assert any("☐" in t and "Тест" in t for t in texts)

    def test_total_line_shown(self):
        kb = breakdown_keyboard(self._bd(), DEFAULT_TOGGLES)
        texts = [b.text for row in kb.inline_keyboard for b in row]
        assert any("Итого" in t for t in texts)

    def test_zero_hour_category_hidden(self):
        bd = {**self._bd(), "tests": 0.0}
        kb = breakdown_keyboard(bd, DEFAULT_TOGGLES)
        texts = [b.text for row in kb.inline_keyboard for b in row]
        assert not any("Тест" in t for t in texts)
