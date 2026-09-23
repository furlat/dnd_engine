"""Named compatibility facts for archives written before explicit area policy."""

from typing import Any


LEGACY_AREA_PROPAGATION = {"spell.fireball": "connected"}


def recorded_area_policy(payload: dict[str, Any]) -> dict[str, Any]:
    if "area_propagation" in payload:
        return payload
    return {**payload, "area_propagation": LEGACY_AREA_PROPAGATION.get(
        payload.get("behavior_id", ""), "line_of_effect")}


def upgrade_player_fact(value: Any) -> Any:
    if isinstance(value, dict) and value.get("kind") == "spell":
        return recorded_area_policy(value)
    return value
