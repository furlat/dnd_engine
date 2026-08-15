"""Exact dispositions for the final small legacy architecture slice."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Literal, cast
from uuid import uuid4

from fastapi.responses import Response
from starlette.requests import Request

from dnd.actions.operations import setup_standard_actions
from dnd.conditions import Prone
from dnd.core.events.events_registry import (
    EventQueue,
)
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from server.event_server import (
    get_objective_diagnostics_events,
    sim,
    subscribe_objective_diagnostics,
)
from server.event_stream import event_stream
from tests.engine.test_standard_conditions import (
    configured_entity,
    reset_condition_state,
)
from tests.engine.test_encounter_apis import (
    reset_chapter_18_state,
)


CoverageStatus = Literal["active", "strengthened", "stale", "retired"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived case's exact maintained disposition."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_149_remaining_legacy_contract.py"
DIRECTIONAL_SELECTOR = (
    f"{THIS_FILE}::"
    "test_objective_http_and_sse_preserve_directional_spatial_fields"
)
PRONE_TURN_SELECTOR = (
    f"{THIS_FILE}::test_prone_auto_stand_is_owner_turn_scoped"
)
PRONE_APPLICATION_SELECTOR = (
    f"{THIS_FILE}::test_prone_application_during_owner_turn_respects_movement"
)
SPATIAL_INDEX_SELECTOR = (
    "tests/manual/test_06_reactions_to_events.py::"
    "test_spatial_handler_uses_position_index_and_can_move"
)
SPATIAL_COEXIST_SELECTOR = (
    "tests/manual/test_aoe_shape_legacy_contract.py::"
    "test_spatial_registry_dispatches_multiple_indexed_and_global_handlers"
)
SPATIAL_CLEANUP_SELECTOR = (
    "tests/engine/test_grid_pathfinding.py::"
    "test_eb_11_020_zone_removal_cleans_spatial_handlers_terrain_and_markers"
)
TURN_START_ZONE_SELECTOR = (
    "tests/engine/test_spell_families.py::"
    "test_eb_15_021_zone_spell_family_entry_turn_start_and_cleanup_edges"
)


DIRECTIONAL_EVENT_STREAM_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_event_history_endpoint_directional_fields": LegacyCoverage(
        "strengthened",
        DIRECTIONAL_SELECTOR,
        "The canonical objective diagnostics window preserves every directional field; the removed raw /events route is not restored.",
    ),
    "test_sse_game_event_directional_fields": LegacyCoverage(
        "strengthened",
        DIRECTIONAL_SELECTOR,
        "The canonical objective diagnostics SSE emits the same cold directional event without a compatibility stream.",
    ),
}


PRONE_AUTO_STAND_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_prone_auto_stand": LegacyCoverage(
        "strengthened",
        PRONE_TURN_SELECTOR,
        "The maintained test proves owner-turn removal and exact half-movement cost.",
    ),
    "test_prone_not_auto_stand_on_other_turn": LegacyCoverage(
        "strengthened",
        PRONE_TURN_SELECTOR,
        "An unrelated creature's turn cannot consume movement or remove Prone.",
    ),
    "test_stand_up_no_longer_registered": LegacyCoverage(
        "active",
        PRONE_TURN_SELECTOR,
        "Standard action setup explicitly excludes the obsolete voluntary Stand Up template.",
    ),
    "test_prone_during_own_turn_with_movement": LegacyCoverage(
        "strengthened",
        PRONE_APPLICATION_SELECTOR,
        "Mid-turn application immediately stands only when the exact movement cost is affordable.",
    ),
    "test_prone_during_own_turn_no_movement": LegacyCoverage(
        "strengthened",
        PRONE_APPLICATION_SELECTOR,
        "Mid-turn application remains indexed when the creature cannot afford standing.",
    ),
}


LEGACY_SPATIAL_MIGRATION_CASES: dict[str, LegacyCoverage] = {
    "test_tile_effect_entry_fires_only_at_correct_position": LegacyCoverage(
        "strengthened",
        SPATIAL_INDEX_SELECTOR,
        "The maintained spatial-event test dispatches only at the indexed cell and proves the index can move.",
    ),
    "test_multiple_tile_effects_efficient": LegacyCoverage(
        "strengthened",
        SPATIAL_COEXIST_SELECTOR,
        "Multiple indexed handlers share one position and dispatch exactly once each.",
    ),
    "test_tile_effect_and_zone_coexist": LegacyCoverage(
        "strengthened",
        SPATIAL_COEXIST_SELECTOR,
        "Indexed zone handlers and global spatial observers coexist in the same dispatch.",
    ),
    "test_tile_effect_cleanup_removes_spatial_handler": LegacyCoverage(
        "strengthened",
        SPATIAL_CLEANUP_SELECTOR,
        "Real AreaSpatialEffectController removal clears handler indexes and terrain.",
    ),
    "test_turn_start_damage_still_works": LegacyCoverage(
        "strengthened",
        TURN_START_ZONE_SELECTOR,
        "Real Grease, Web, Cloudkill, and Spirit Guardians zones exercise entry and turn-start handlers together.",
    ),
    "test_backward_compatibility_legacy_handlers": LegacyCoverage(
        "active",
        SPATIAL_COEXIST_SELECTOR,
        "Global EventHandler observation of spatial events remains a deliberate supported capability, not an alias.",
    ),
}


def _request(path: str) -> Request:
    """Build a local standalone request for direct route validation."""
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 80),
        }
    )


def _parse_sse(frame: str) -> tuple[str, dict[str, object]]:
    """Decode one canonical objective diagnostics frame."""
    event_name = next(
        line.removeprefix("event: ")
        for line in frame.splitlines()
        if line.startswith("event: ")
    )
    data = "\n".join(
        line.removeprefix("data: ")
        for line in frame.splitlines()
        if line.startswith("data: ")
    )
    return event_name, json.loads(data)


def test_remaining_legacy_manifests_account_for_all_13_cases() -> None:
    """The three ledgers cover the complete final root-owned slice."""
    assert len(DIRECTIONAL_EVENT_STREAM_LEGACY_CASES) == 2
    assert len(PRONE_AUTO_STAND_LEGACY_CASES) == 5
    assert len(LEGACY_SPATIAL_MIGRATION_CASES) == 6
    assert all(
        case.startswith("test_")
        and row.selector.startswith("tests/")
        and "::test_" in row.selector
        and row.rationale
        for ledger in (
            DIRECTIONAL_EVENT_STREAM_LEGACY_CASES,
            PRONE_AUTO_STAND_LEGACY_CASES,
            LEGACY_SPATIAL_MIGRATION_CASES,
        )
        for case, row in ledger.items()
    )


def test_objective_http_and_sse_preserve_directional_spatial_fields() -> None:
    """The sole objective event transport keeps directional tile metadata."""
    reset_chapter_18_state(width=4, height=4)
    encounter = Encounter(
        name="Directional objective transport",
        source_entity_uuid=uuid4(),
    )
    sim.encounter = encounter
    Encounter._active_encounter = encounter
    event_stream.ensure_attached()
    cursor = EventQueue.event_cursor()

    assert get_map().set_tile_directional_border(
        (1, 1),
        "vision",
        "east",
        False,
    )

    async def collect() -> tuple[dict[str, object], list[tuple[str, dict[str, object]]]]:
        window = await get_objective_diagnostics_events(
            request=_request("/diagnostics/objective/events"),
            response=Response(),
            from_cursor=cursor,
            through_cursor=None,
            limit=None,
            expected_source_stream_id=None,
            expected_generation_id=None,
        )
        response = await subscribe_objective_diagnostics(
            request=_request("/diagnostics/objective/subscribe"),
            since_event=cursor,
            since_log=0,
            expected_source_stream_id=window.source_stream_id,
            expected_generation_id=window.generation_id,
        )
        iterator = cast(AsyncGenerator[str, None], response.body_iterator)
        raw_frames: list[str] = []
        try:
            raw_frames.append(await anext(iterator))
            raw_frames.append(await anext(iterator))
        finally:
            await iterator.aclose()
        return window.model_dump(mode="json"), [
            _parse_sse(frame) for frame in raw_frames
        ]

    window, frames = asyncio.run(collect())
    http_event = cast(
        dict[str, object],
        cast(list[dict[str, object]], window["frames"])[0]["event"],
    )
    assert [event_name for event_name, _payload in frames] == [
        "sync",
        "game_event",
    ]
    sse_event = cast(
        dict[str, object],
        frames[1][1]["event"],
    )
    for payload in (http_event, sse_event):
        assert payload["event_type"] == "spatial_tile_changed"
        assert payload["directional_position"] == [1, 1]
        assert payload["directional_directions"] == ["east"]
        assert payload["directional_channels"] == ["vision"]
        assert cast(dict[str, bool], payload["directional_blocks_vision"])[
            "east"
        ] is True


def test_prone_auto_stand_is_owner_turn_scoped() -> None:
    """Only the owner's turn removes Prone and spends half its movement."""
    reset_condition_state()
    owner = configured_entity("Prone owner", (2, 1), "heroes")
    other = configured_entity("Other actor", (3, 1), "monsters")
    setup_standard_actions(owner)
    owner.add_condition(
        Prone(source_entity_uuid=other.uuid, target_entity_uuid=owner.uuid)
    )

    assert "Stand Up" not in {
        action.name for action in owner.registered_actions
    }
    assert "Prone" in owner.active_conditions
    other.on_turn_start()
    assert "Prone" in owner.active_conditions
    assert owner.action_economy.movement.normalized_score == 30

    owner.on_turn_start()
    assert "Prone" not in owner.active_conditions
    assert owner.action_economy.movement.normalized_score == 15


def test_prone_application_during_owner_turn_respects_movement() -> None:
    """Immediate stand is affordable-only and leaves no stale condition."""
    reset_condition_state()
    mobile = configured_entity("Mobile actor", (2, 1), "heroes")
    mobile.on_turn_start()
    condition = Prone(
        source_entity_uuid=mobile.uuid,
        target_entity_uuid=mobile.uuid,
    )

    completion = mobile.add_condition(condition)

    assert completion is not None
    assert completion.canceled is True
    assert condition.applied is False
    assert "Prone" not in mobile.active_conditions
    assert mobile.action_economy.movement.normalized_score == 15

    reset_condition_state()
    immobile = configured_entity("Immobile actor", (2, 1), "heroes")
    immobile.on_turn_start()
    immobile.action_economy.consume("movement", 30)

    completion = immobile.add_condition(
        Prone(
            source_entity_uuid=immobile.uuid,
            target_entity_uuid=immobile.uuid,
        )
    )

    assert completion is not None
    assert completion.canceled is False
    assert "Prone" in immobile.active_conditions
    assert immobile.action_economy.movement.normalized_score == 0
