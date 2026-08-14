"""Exact compose -> preview -> start helpers for active API regressions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from dnd.core.content.encounters import FixedRosterOpeningPolicy
from dnd.scenarios.encounter_catalog import (
    AUTHORED_DEPLOYMENTS_BY_ID,
    AUTHORED_ENCOUNTER_RECIPES_BY_ID,
)

def authored_compose_request(
    *,
    encounter_id: str = "encounter.standard_skeleton_doors",
    participant_names: Sequence[str] | None = None,
    opening_roster_index: int | None = 0,
) -> dict[str, object]:
    """Select one authored encounter through the public composition DTO."""
    source = AUTHORED_ENCOUNTER_RECIPES_BY_ID[encounter_id]
    deployment = AUTHORED_DEPLOYMENTS_BY_ID[
        f"neutral.{source.battlefield_id}"
    ]
    selected_participant_names = (
        tuple(participant_names)
        if participant_names is not None
        else tuple(
            f"{slot.roster.title} Participant"
            for slot in source.roster_slots
        )
    )
    if len(selected_participant_names) != len(source.roster_slots):
        raise ValueError("participant count must match authored roster slots")
    opening_policy = (
        source.opening_policy
        if opening_roster_index is None
        else FixedRosterOpeningPolicy(
            roster_slot_id=source.roster_slots[
                opening_roster_index
            ].roster_slot_id,
        )
    )
    return {
        "title": source.title,
        "roster_slots": [
            {
                "roster_slot_id": slot.roster_slot_id,
                "roster": {
                    "kind": "authored_roster",
                    "roster_id": slot.roster.roster_id,
                },
                "faction_id": slot.faction_id,
                "deployment_zone_id": slot.deployment_zone_id,
                "participant_name": participant_name,
            }
            for slot, participant_name in zip(
                source.roster_slots,
                selected_participant_names,
                strict=True,
            )
        ],
        "battlefield_id": source.battlefield_id,
        "deployment_id": deployment.deployment_id,
        "opening_policy": opening_policy.model_dump(mode="json"),
    }


def compose_and_preview(
    client: Any,
    *,
    compose_request: Mapping[str, object] | None = None,
    encounter_id: str = "encounter.standard_skeleton_doors",
    participant_names: Sequence[str] | None = None,
    opening_roster_index: int | None = 0,
    request_kwargs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize once and prove preview consumes that exact immutable recipe."""
    request = (
        dict(compose_request)
        if compose_request is not None
        else authored_compose_request(
            encounter_id=encounter_id,
            participant_names=participant_names,
            opening_roster_index=opening_roster_index,
        )
    )
    kwargs = dict(request_kwargs or {})
    composed = client.post(
        "/game-creation/compose",
        json=request,
        **kwargs,
    )
    assert composed.status_code == 200, composed.text
    payload = composed.json()
    assert isinstance(payload, dict)
    exact = {
        "expected_content_set_digest": payload["content_set_digest"],
        "expected_ruleset_digest": payload["ruleset_digest"],
        "recipe": payload["recipe"],
    }
    preview = client.post(
        "/game-creation/preview",
        json=exact,
        **kwargs,
    )
    assert preview.status_code == 200, preview.text
    preview_payload = preview.json()
    assert preview_payload == payload["preview"]
    assert (
        preview_payload["encounter_recipe_digest"]
        == payload["recipe"]["recipe_digest"]
    )
    payload["exact_start_request"] = exact
    return payload


def start_composed_game(
    client: Any,
    *,
    compose_request: Mapping[str, object] | None = None,
    encounter_id: str = "encounter.standard_skeleton_doors",
    participant_names: Sequence[str] | None = None,
    opening_roster_index: int | None = 0,
    request_kwargs: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Start only the exact normalized recipe returned by composition."""
    composition = compose_and_preview(
        client,
        compose_request=compose_request,
        encounter_id=encounter_id,
        participant_names=participant_names,
        opening_roster_index=opening_roster_index,
        request_kwargs=request_kwargs,
    )
    kwargs = dict(request_kwargs or {})
    started = client.post(
        "/game-creation/start",
        json=composition["exact_start_request"],
        **kwargs,
    )
    assert started.status_code == 200, started.text
    payload = started.json()
    assert payload["recipe_digest"] == composition["recipe"]["recipe_digest"]
    return composition, payload


def roster_result(
    start_payload: Mapping[str, Any],
    roster_slot_id: str,
) -> dict[str, Any]:
    """Resolve one public roster result without positional side assumptions."""
    return next(
        roster
        for roster in start_payload["rosters"]
        if roster["roster_slot_id"] == roster_slot_id
    )


__all__ = [
    "authored_compose_request",
    "compose_and_preview",
    "roster_result",
    "start_composed_game",
]
