"""Server-owned normalization of catalog selections into exact recipes."""

from __future__ import annotations

import hashlib
import json
from dnd.core.content.encounters import (
    EncounterCompatibilityReport,
    EncounterRecipe,
    EncounterRosterSlot,
)
from dnd.scenarios.encounter_catalog import (
    AUTHORED_DEPLOYMENTS_BY_ID,
    AUTHORED_ROSTER_RECIPES_BY_ID,
)
from dnd.scenarios.encounter_compatibility import (
    check_encounter_compatibility,
)
from dnd.scenarios.battlefield_catalog import get_battlefield
from server.api_models import (
    GameCreationComposeRequest,
)


class GameCreationCompositionError(ValueError):
    """One exact normalization failure suitable for public route mapping."""


def normalize_encounter_recipe(
    request: GameCreationComposeRequest,
) -> tuple[EncounterRecipe, EncounterCompatibilityReport]:
    """Resolve authored catalog ids into an exact launch recipe."""
    try:
        deployment = AUTHORED_DEPLOYMENTS_BY_ID[request.deployment_id]
        battlefield = get_battlefield(request.battlefield_id)
    except (KeyError, ValueError) as exc:
        raise GameCreationCompositionError(str(exc)) from exc
    if deployment.battlefield_id != battlefield.battlefield_id:
        raise GameCreationCompositionError(
            "selected deployment belongs to another battlefield",
        )

    roster_slots: list[EncounterRosterSlot] = []
    for selection in request.roster_slots:
        roster_selection = selection.roster
        try:
            roster = AUTHORED_ROSTER_RECIPES_BY_ID[
                roster_selection.roster_id
            ]
        except KeyError as exc:
            raise GameCreationCompositionError(
                f"unknown authored roster {roster_selection.roster_id!r}",
            ) from exc
        roster_slots.append(EncounterRosterSlot(
            roster_slot_id=selection.roster_slot_id,
            roster=roster,
            faction_id=selection.faction_id,
            deployment_zone_id=selection.deployment_zone_id,
            participant_name=selection.participant_name,
        ))

    request_identity = request.model_dump(mode="json")
    request_identity["roster_slots"] = [
        slot.model_dump(mode="json") for slot in roster_slots
    ]
    recipe_seed = hashlib.sha256(
        json.dumps(
            request_identity,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
    ).hexdigest()
    recipe = EncounterRecipe.create(
        encounter_id=f"encounter.composed.{recipe_seed[:24]}",
        title=request.title,
        roster_slots=tuple(roster_slots),
        battlefield_id=request.battlefield_id,
        deployment=deployment,
        opening_policy=request.opening_policy,
        tags=("composed",),
    )
    compatibility = check_encounter_compatibility(
        recipe,
        battlefield,
    )
    return recipe, compatibility


__all__ = [
    "GameCreationCompositionError",
    "normalize_encounter_recipe",
]
