# -*- coding: utf-8 -*-
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_delete_estimation_from_index_calls_delete():
    mock_client = AsyncMock()

    with patch("services.estimation_indexer.get_client", return_value=mock_client):
        from services.estimation_indexer import _point_id_from_estimation_id, delete_estimation_from_index

        await delete_estimation_from_index("some-uuid", user_id=42)

    mock_client.delete.assert_awaited_once()
    call_kwargs = mock_client.delete.call_args
    assert call_kwargs.kwargs["collection_name"] == "estimations_42"
    expected_point_id = _point_id_from_estimation_id("some-uuid")
    assert call_kwargs.kwargs["points_selector"] == [expected_point_id]


@pytest.mark.asyncio
async def test_delete_estimation_from_index_swallows_qdrant_error():
    mock_client = AsyncMock()
    mock_client.delete.side_effect = Exception("qdrant down")

    with patch("services.estimation_indexer.get_client", return_value=mock_client):
        from services.estimation_indexer import delete_estimation_from_index

        # must not raise
        await delete_estimation_from_index("some-uuid", user_id=42)
