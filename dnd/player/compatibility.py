"""Named compatibility facts for archives written before explicit area policy."""

from typing import Any
from uuid import UUID

from dnd.core.effect_types import EventResolutionRef, ResolutionRef


LEGACY_AREA_PROPAGATION = {"spell.fireball": "connected"}


def recorded_combat_log(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """Upgrade archived log values once; never regenerate rolls or prose.

    Pre-typed archives carry the category and variant fields, but no discriminator.
    Their duplicate target summaries are replaced by references to the original
    ordered children, preserving repeated applications to the same target.
    """
    if entry is None:
        return None
    children = entry.get("sub_entries", [])
    data = dict(entry["data"])
    if "kind" not in data:
        category = entry["entry_type"]
        kind = category
        if not data:
            kind = "empty"
        elif category in ("turn_start", "turn_end"):
            kind = "turn"
        elif category == "movement":
            variant = data.get("type")
            if variant in ("step_movement", "forced_movement"):
                kind = variant
            elif "observed_path_segments" in data:
                kind = "observed_movement"
            elif variant == "movement" and data.get("observation_complete") is False:
                kind = "unlocated_movement"
            elif variant == "movement" and data.get("observed") is True:
                kind = "unknown_movement"
            elif data.get("movement_type") in ("jump", "connector"):
                kind = data["movement_type"] + "_movement"
        elif category == "saving_throw" and "successes" in data:
            kind = "death_save"
        elif category == "action" and data.get("action_type") == "shove":
            kind = "shove"
        elif category == "spatial_effect":
            kind = "spatial_change" if "content_identity" in data else "spatial_interaction"
        data["kind"] = kind
    if "per_target_logs" in data:
        targets = data.pop("per_target_logs")
        indices = []
        for target in targets:
            index = next((i for i, child in enumerate(children)
                          if i not in indices and child["data"] == target), None)
            if index is None:
                raise ValueError("Archived target summary has no original combat-log child")
            indices.append(index)
        data["target_entry_indices"] = indices
    return {**entry, "data": data,
            "sub_entries": [recorded_combat_log(child) for child in children]}


def recorded_area_policy(payload: dict[str, Any]) -> dict[str, Any]:
    if "area_propagation" in payload:
        return payload
    return {**payload, "area_propagation": LEGACY_AREA_PROPAGATION.get(
        payload.get("behavior_id", ""), "line_of_effect")}


def upgrade_spell_fact(value: object) -> object:
    if isinstance(value, dict):
        return recorded_area_policy(value)
    return value


def recorded_application(payload: dict[str, Any]) -> dict[str, Any]:
    """Replace the old pair only when its recorded parent identifies the owner."""
    if "application_id" not in payload and "application_index" not in payload:
        return payload
    payload = dict(payload)
    identity = payload.pop("application_id", None)
    index = payload.pop("application_index", None)
    if (identity is None) != (index is None):
        raise ValueError("Incomplete recorded application membership")
    if identity is None:
        payload["application"] = None
    else:
        owner = payload.get("parent_lineage")
        if owner is None:
            raise ValueError("Legacy application lacks its owning lineage; reproject the preserved native sequence")
        payload["application"] = dict(lineage_uuid=owner, application_id=identity, index=index)
    return payload


def legacy_damage_reference(event_uuid: UUID, lineage_uuid: UUID,
                            parent_lineage: UUID | None, *, is_request: bool) -> ResolutionRef:
    """Only a root damage request proves its ownership without an explicit link.

    A child of an attack/spell may be a triggered independent exposure. Ancestry
    alone cannot distinguish it from that operation's own damage.
    """
    if is_request and parent_lineage is None:
        return EventResolutionRef(lineage_uuid=lineage_uuid)
    raise ValueError(f"Legacy damage {event_uuid} lacks unambiguous resolution ownership; "
                     "preserve this recording and recapture this case with current producers")
