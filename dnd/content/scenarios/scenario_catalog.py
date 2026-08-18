"""Direct authored scenario catalog loaded from renderer-neutral values."""

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from dnd.content.scenarios.scenario_definitions import (
    EncounterDefinition,
    EncounterDeploymentDefinition,
    EncounterRosterDefinition,
)


_CATALOG_PATH = Path(__file__).with_name("authored_scenarios.json")


def _load_payload() -> dict[str, Any]:
    payload = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("authored scenario catalog must be a JSON object")
    if payload.get("schema_version") != 3:
        raise ValueError(
            "unsupported authored scenario schema: "
            f"{payload.get('schema_version')!r}",
        )
    if set(payload) != {
        "schema_version",
        "rosters",
        "deployments",
        "encounters",
    }:
        raise ValueError("authored scenario catalog has unexpected sections")
    return payload


_PAYLOAD = _load_payload()

AUTHORED_ROSTERS = tuple(
    EncounterRosterDefinition.model_validate(row)
    for row in _PAYLOAD["rosters"]
)
AUTHORED_ROSTERS_BY_ID = MappingProxyType({
    roster.roster_id: roster for roster in AUTHORED_ROSTERS
})

AUTHORED_DEPLOYMENTS = tuple(
    EncounterDeploymentDefinition.model_validate(row)
    for row in _PAYLOAD["deployments"]
)
AUTHORED_DEPLOYMENTS_BY_ID = MappingProxyType({
    deployment.deployment_id: deployment
    for deployment in AUTHORED_DEPLOYMENTS
})

AUTHORED_ENCOUNTERS = tuple(
    EncounterDefinition.model_validate(row)
    for row in _PAYLOAD["encounters"]
)
AUTHORED_ENCOUNTERS_BY_ID = MappingProxyType({
    encounter.encounter_id: encounter
    for encounter in AUTHORED_ENCOUNTERS
})

del _PAYLOAD


def roster_definition(roster_id: str) -> EncounterRosterDefinition:
    """Return one exact authored roster."""
    try:
        return AUTHORED_ROSTERS_BY_ID[roster_id]
    except KeyError as exc:
        raise ValueError(f"unknown authored roster: {roster_id}") from exc


def encounter_definition(encounter_id: str) -> EncounterDefinition:
    """Return one exact authored encounter."""
    try:
        return AUTHORED_ENCOUNTERS_BY_ID[encounter_id]
    except KeyError as exc:
        raise ValueError(f"unknown authored encounter: {encounter_id}") from exc


__all__ = [
    "AUTHORED_DEPLOYMENTS",
    "AUTHORED_DEPLOYMENTS_BY_ID",
    "AUTHORED_ENCOUNTERS",
    "AUTHORED_ENCOUNTERS_BY_ID",
    "AUTHORED_ROSTERS",
    "AUTHORED_ROSTERS_BY_ID",
    "encounter_definition",
    "roster_definition",
]
