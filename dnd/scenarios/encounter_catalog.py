"""Direct canonical authored roster, deployment, and encounter catalog.

The checked-in payload contains only the dependency-neutral models consumed by
the product assembler.  There is deliberately no hero/monster blueprint,
evaluation configuration, legacy recipe, or conversion layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from dnd.core.content.encounters import (
    EncounterDeploymentSpec,
    EncounterRecipe,
    EncounterRosterRecipe,
)


_CATALOG_SCHEMA_VERSION = 2
_CATALOG_PATH = Path(__file__).with_name("authored_catalog.json")


def _load_payload() -> dict[str, Any]:
    payload = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("Authored encounter catalog must be a JSON object")
    if payload.get("schema_version") != _CATALOG_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported authored encounter catalog schema: "
            f"{payload.get('schema_version')!r}",
        )
    if set(payload) != {
        "schema_version",
        "rosters",
        "deployments",
        "encounters",
    }:
        raise ValueError("Authored encounter catalog has unexpected sections")
    return payload


_PAYLOAD = _load_payload()

AUTHORED_ROSTER_RECIPES: tuple[EncounterRosterRecipe, ...] = tuple(
    EncounterRosterRecipe.model_validate(payload)
    for payload in _PAYLOAD["rosters"]
)
AUTHORED_ROSTER_RECIPES_BY_ID = MappingProxyType({
    roster.roster_id: roster for roster in AUTHORED_ROSTER_RECIPES
})

# Only reusable formations are public catalog entries.  Exact scenario
# formations remain owned by the corresponding EncounterRecipe.
AUTHORED_DEPLOYMENTS: tuple[EncounterDeploymentSpec, ...] = tuple(
    EncounterDeploymentSpec.model_validate(payload)
    for payload in _PAYLOAD["deployments"]
)
AUTHORED_DEPLOYMENTS_BY_ID = MappingProxyType({
    deployment.deployment_id: deployment
    for deployment in AUTHORED_DEPLOYMENTS
})

AUTHORED_ENCOUNTER_RECIPES: tuple[EncounterRecipe, ...] = tuple(
    EncounterRecipe.model_validate(payload)
    for payload in _PAYLOAD["encounters"]
)
AUTHORED_ENCOUNTER_RECIPES_BY_ID = MappingProxyType({
    encounter.encounter_id: encounter
    for encounter in AUTHORED_ENCOUNTER_RECIPES
})

del _PAYLOAD


def roster_recipe(roster_id: str) -> EncounterRosterRecipe:
    """Return one exact authored roster recipe."""
    try:
        return AUTHORED_ROSTER_RECIPES_BY_ID[roster_id]
    except KeyError as exc:
        raise ValueError(f"Unknown authored roster: {roster_id}") from exc


def encounter_recipe(encounter_id: str) -> EncounterRecipe:
    """Return one exact authored encounter recipe."""
    try:
        return AUTHORED_ENCOUNTER_RECIPES_BY_ID[encounter_id]
    except KeyError as exc:
        raise ValueError(
            f"Unknown authored encounter: {encounter_id}",
        ) from exc


__all__ = [
    "AUTHORED_DEPLOYMENTS",
    "AUTHORED_DEPLOYMENTS_BY_ID",
    "AUTHORED_ENCOUNTER_RECIPES",
    "AUTHORED_ENCOUNTER_RECIPES_BY_ID",
    "AUTHORED_ROSTER_RECIPES",
    "AUTHORED_ROSTER_RECIPES_BY_ID",
    "encounter_recipe",
    "roster_recipe",
]
