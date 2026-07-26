"""Hosted workers prove the exact gateway-frozen content identity."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from server.hosted_worker import HostedWorkerError, HostedWorkerManager


def test_worker_readiness_matches_the_parent_content_set(tmp_path: Path) -> None:
    """A worker enters READY only after an exact content digest handshake."""

    async def exercise() -> None:
        expected = bootstrap_content_system().content_set_digest
        manager = HostedWorkerManager(
            tmp_path / "runtime",
            expected_content_set_digest=expected,
            startup_timeout_seconds=20.0,
        )
        game_id = uuid4()
        placement = await manager.start(
            game_id,
            public_game_base_url=f"http://gateway/games/{game_id}/runtime",
        )
        async with manager.client(game_id) as client:
            response = await client.get("/hosted/readiness")

        assert response.status_code == 200
        assert response.json()["content_set_digest"] == expected
        assert manager.expected_content_set_digest == expected
        assert placement.state.value == "ready"
        await manager.stop_all()

    asyncio.run(exercise())


def test_content_mismatch_never_enters_the_worker_pool(tmp_path: Path) -> None:
    """A mismatched worker is terminated instead of being advertised."""

    async def exercise() -> None:
        manager = HostedWorkerManager(
            tmp_path / "runtime",
            expected_content_set_digest="f" * 64,
            startup_timeout_seconds=20.0,
        )
        game_id = uuid4()
        with pytest.raises(
            HostedWorkerError,
            match="content set mismatch",
        ):
            await manager.start(
                game_id,
                public_game_base_url=(
                    f"http://gateway/games/{game_id}/runtime"
                ),
            )
        assert manager.active_game_ids() == ()
        assert manager.warm_worker_count() == 0
        await manager.stop_all()

    asyncio.run(exercise())
