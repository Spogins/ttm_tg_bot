# -*- coding: utf-8 -*-
from db.mongodb.models import Estimation
from services.estimation_indexer import _collection, _estimation_text, _point_id_from_estimation_id


class TestPointIdDerivation:
    def test_returns_positive_int(self):
        pid = _point_id_from_estimation_id("abc-123")
        assert isinstance(pid, int)
        assert pid >= 0

    def test_deterministic(self):
        pid1 = _point_id_from_estimation_id("abc-123")
        pid2 = _point_id_from_estimation_id("abc-123")
        assert pid1 == pid2

    def test_fits_int64(self):
        pid = _point_id_from_estimation_id("abc-123")
        assert pid < 2**63

    def test_different_ids_produce_different_points(self):
        pid1 = _point_id_from_estimation_id("aaa-111")
        pid2 = _point_id_from_estimation_id("bbb-222")
        assert pid1 != pid2


class TestCollection:
    def test_returns_prefixed_user_id(self):
        assert _collection(123) == "estimations_123"

    def test_different_users_different_collections(self):
        assert _collection(1) != _collection(2)

    def test_prefix_is_estimations(self):
        assert _collection(99).startswith("estimations_")


class TestEstimationText:
    def _make(self, **kwargs) -> Estimation:
        defaults = dict(
            estimation_id="e1",
            user_id=1,
            task="Fix login bug",
            total_hours=3.0,
            complexity=2,
            tech_stack=["Python", "FastAPI"],
            project_name="CRM",
        )
        return Estimation(**{**defaults, **kwargs})

    def test_contains_task(self):
        assert "Fix login bug" in _estimation_text(self._make())

    def test_contains_tech_stack_items(self):
        text = _estimation_text(self._make())
        assert "Python" in text
        assert "FastAPI" in text

    def test_contains_total_hours(self):
        assert "3.0" in _estimation_text(self._make())

    def test_contains_complexity(self):
        assert "2" in _estimation_text(self._make())

    def test_contains_project_name(self):
        assert "CRM" in _estimation_text(self._make())

    def test_empty_tech_stack_no_crash(self):
        text = _estimation_text(self._make(tech_stack=[]))
        assert "Fix login bug" in text
