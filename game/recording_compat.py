"""Named compatibility facts for archives written before explicit area policy."""

from typing import Any
from uuid import UUID

from dnd.core.effect_types import EventResolutionRef, ResolutionRef


LEGACY_AREA_PROPAGATION = {"spell.fireball": "connected"}


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


def upgrade_player_sequence(value: object) -> object:
    """One passive archive boundary; never infer undisclosed damage causality."""
    if not isinstance(value, dict) or value.get("schema_version", 1) == 2:
        return value
    if value.get("schema_version", 1) != 1:
        return value
    def group_upgrade(nodes: list[dict[str, Any]], versions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        declarations: dict[str, str] = {}
        for row in sorted(versions, key=lambda row: row["source_index"]):
            declarations.setdefault(row["lineage_uuid"], row["event_uuid"])
        by_lineage = {node["lineage_uuid"]: node for node in nodes}
        upgraded: dict[str, dict[str, Any]] = {}

        def node_upgrade(node: dict[str, Any]) -> dict[str, Any]:
            identity = node["lineage_uuid"]
            if identity in upgraded:
                return upgraded[identity]
            fact = node.get("fact")
            if not isinstance(fact, dict):
                upgraded[identity] = node
                return node
            fact = dict(fact)
            if fact.get("kind") == "spatial" and "commit_event_uuid" not in fact:
                fact["commit_event_uuid"] = declarations.get(identity)
            parent = by_lineage.get(node.get("parent_lineage"))
            reference = node.get("resolution_ref")
            if fact.get("kind") == "spell":
                owner = parent
                while owner is not None and (owner.get("fact") or {}).get("kind") == "area_reach":
                    owner = by_lineage.get(owner.get("parent_lineage"))
                owner_lineage = owner["lineage_uuid"] if owner is not None else node.get("parent_lineage")
                fact = recorded_application({**fact, "parent_lineage": owner_lineage})
                fact.pop("parent_lineage", None)
            if "resolution_ref" not in node and fact.get("kind") in ("spell", "attack", "action"):
                application = fact.get("application")
                reference = ({"kind": "application", "lineage_uuid": application["lineage_uuid"],
                              "application_id": application["application_id"]} if application else
                             {"kind": "event", "lineage_uuid": identity})
            if fact.get("kind") == "damage":
                if "resolution_ref" not in node:
                    parent_fact = parent.get("fact") if parent is not None else None
                    request_owner = None
                    if (fact.get("stage") == "applied" and parent is not None
                            and isinstance(parent_fact, dict) and parent_fact.get("kind") == "damage"
                            and parent_fact.get("stage") == "taken"):
                        request_owner = node_upgrade(parent).get("resolution_ref")
                    if request_owner is not None:
                        reference = request_owner
                    else:
                        reference = legacy_damage_reference(UUID(node["uuid"]), UUID(identity),
                            UUID(node["parent_lineage"]) if node.get("parent_lineage") else None,
                            is_request=fact.get("stage") == "taken").model_dump(mode="json")
                if fact.get("stage") == "taken":
                    fact = {key: field for key, field in fact.items() if key in {
                        "kind", "stage", "source_entity_uuid", "target_entity_uuid", "intercepted_by_condition_uuid"}}
                else:
                    fact.pop("intercepted_by_condition_uuid", None)
            if "resolution_ref" not in node and reference is None and parent is not None and fact.get("kind") != "damage":
                reference = node_upgrade(parent).get("resolution_ref")
            result = {**node, "fact": fact, "resolution_ref": reference}
            upgraded[identity] = result
            return result
        return [node_upgrade(node) for node in nodes]

    initialization = value["initialization"]
    lineages = []
    for lineage in value["lineages"]:
        nodes = group_upgrade(lineage["events"], lineage["version_rows"])
        root = next(node for node in nodes if node["uuid"] == lineage["root"]["uuid"])
        lineages.append({**lineage, "root": root, "events": nodes})
    return {**value, "schema_version": 2,
        "initialization": {**initialization, "nodes": group_upgrade(initialization["nodes"], initialization["version_rows"])},
        "lineages": lineages}
