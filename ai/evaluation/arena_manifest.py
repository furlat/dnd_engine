"""Arena manifest extraction for Elo evaluator evidence."""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
import json
import random
from typing import Any, Iterator, Mapping, Optional

from ai.evaluation.elo_contract import ArenaManifest, EntityRosterRow
from dnd.controller import Controller
from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import get_map
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.modifiers import DamageType, ResistanceStatus
from dnd.entity import Entity
from dnd.scenarios.ai_validation_arenas import ValidationArena, create_ai_validation_arena
from server.arena_mode import reset_standard_arena_runtime


ABILITY_NAMES: tuple[str, ...] = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)


def capture_arena_manifest_for_id(
    arena_id: str,
    *,
    random_seed: Optional[int] = None,
) -> ArenaManifest:
    """Construct an arena and return its stable measurement manifest.

    Args:
        arena_id: Validation arena id.
        random_seed: Optional seed used to make construction deterministic.

    Returns:
        Stable manifest for evaluator evidence.
    """
    with _preserved_random_seed(random_seed):
        reset_standard_arena_runtime()
        arena = create_ai_validation_arena(arena_id)
        return build_arena_manifest(arena)


def build_arena_manifest(arena: ValidationArena) -> ArenaManifest:
    """Build a stable manifest from one constructed validation arena.

    Args:
        arena: Constructed validation arena bundle.

    Returns:
        Arena manifest whose hashes ignore volatile UUIDs.
    """
    grid = get_map()
    tiles = grid.get_all_tiles()
    entity_rosters = _entity_rosters(arena)
    roster_hash_by_side = {
        side: roster_identity_hash(rows)
        for side, rows in sorted(entity_rosters.items())
    }
    initiative_order = _initiative_order(arena)
    manifest = ArenaManifest(
        arena_id=arena.spec.arena_id,
        title=arena.spec.title,
        hero_role=arena.spec.hero_role,
        tags=tuple(arena.spec.tags),
        expected_pressure=tuple(arena.spec.expected_pressure),
        map_notes=tuple(arena.spec.map_notes),
        notable_positions=dict(sorted(arena.notable_positions.items())),
        map_size=grid.size,
        map_bounds=grid.bounds,
        opening_faction=(initiative_order[0].get("faction") if initiative_order else None),
        initiative_order=initiative_order,
        terrain_summary=_terrain_summary(tiles),
        object_summary=_object_summary(grid),
        entity_rosters=entity_rosters,
        roster_hash_by_side=roster_hash_by_side,
        manifest_hash="",
    )
    return manifest.model_copy(update={"manifest_hash": _manifest_hash(manifest)})


def _entity_rosters(arena: ValidationArena) -> dict[str, list[EntityRosterRow]]:
    combatant_uuids = set(arena.encounter.combatants)
    rows_by_side: dict[str, list[EntityRosterRow]] = {}
    for entity in Entity.get_all_entities():
        if entity.uuid not in combatant_uuids:
            continue
        side = entity.faction or "unfactioned"
        combatant = arena.encounter.combatants.get(entity.uuid)
        controller = combatant.controller if combatant is not None else None
        rows_by_side.setdefault(side, []).append(_entity_roster_row(entity, controller))
    return {
        side: sorted(rows, key=lambda row: (row.stable_name, row.position or (9999, 9999), row.class_or_monster))
        for side, rows in sorted(rows_by_side.items())
    }


def _entity_roster_row(entity: Entity, controller: Optional[Controller]) -> EntityRosterRow:
    con_modifier = entity.ability_scores.constitution.get_combined_values().normalized_score
    max_hp = entity.health.get_max_hit_dices_points(con_modifier) + entity.health.max_hit_points_bonus.normalized_score
    return EntityRosterRow(
        stable_name=entity.name,
        faction=entity.faction,
        controller_type=(controller.controller_type if controller is not None else None),
        position=entity.position,
        class_or_monster=_class_or_monster(entity),
        level_or_cr=_level_or_cr(entity),
        max_hp=max_hp,
        current_hp=entity.get_hp(),
        ac=_safe_int(lambda: entity.ac_bonus().normalized_score),
        speed=_safe_int(lambda: entity.action_economy.current_speed()),
        senses=_senses_summary(entity),
        ability_summary=_ability_summary(entity),
        saving_throw_summary=_saving_throw_summary(entity),
        resistances=_damage_affinities(entity, ResistanceStatus.RESISTANCE),
        immunities=_damage_affinities(entity, ResistanceStatus.IMMUNITY),
        vulnerabilities=_damage_affinities(entity, ResistanceStatus.VULNERABILITY),
        conditions_at_start=sorted(entity.active_conditions),
        condition_summary=_condition_summary(entity),
        equipment_summary=_equipment_summary(entity),
        inventory_summary=_inventory_summary(entity),
        spell_summary=_spell_summary(entity),
        action_template_summary=_action_template_summary(entity),
        trait_summary=_trait_summary(entity),
        handler_summary=_handler_summary(entity),
    )


def _class_or_monster(entity: Entity) -> str:
    raw = getattr(entity, "monster_name", None) or getattr(entity, "class_name", None)
    if raw:
        return str(raw)
    return type(entity).__name__


def _level_or_cr(entity: Entity) -> Optional[str]:
    for attr in ("level", "character_level", "cr", "challenge_rating"):
        value = getattr(entity, attr, None)
        if value is not None:
            return str(value)
    hit_dice_count = getattr(entity.health, "total_hit_dices_number", None)
    return f"hd:{hit_dice_count}" if hit_dice_count is not None else None


def _senses_summary(entity: Entity) -> dict[str, Any]:
    senses = entity.senses
    special_modes = []
    for mode in getattr(senses, "special_senses", []) or []:
        special_modes.append(_jsonable(mode))
    return {
        "position": entity.position,
        "has_ordinary_sight": entity.has_ordinary_sight,
        "visible_cell_count": len(getattr(senses, "visible", {}) or {}),
        "seen_cell_count": len(getattr(senses, "seen", set()) or set()),
        "visible_entity_count": len(getattr(senses, "entities", {}) or {}),
        "visible_object_count": len(getattr(senses, "objects", {}) or {}),
        "special_senses": special_modes,
    }


def _ability_summary(entity: Entity) -> dict[str, int]:
    return {
        name: getattr(entity.ability_scores, name).ability_score.normalized_score
        for name in ABILITY_NAMES
    }


def _saving_throw_summary(entity: Entity) -> dict[str, int]:
    out: dict[str, int] = {}
    for ability_name in ABILITY_NAMES:
        attr = f"{ability_name}_saving_throw"
        save = getattr(entity.saving_throws, attr, None)
        if save is None:
            continue
        try:
            ability_modifier = getattr(entity.ability_scores, ability_name).get_combined_values().normalized_score
            out[ability_name] = ability_modifier + save.get_bonus(entity.proficiency_bonus.normalized_score)
        except Exception:
            continue
    return out


def _damage_affinities(entity: Entity, status: ResistanceStatus) -> list[str]:
    names: list[str] = []
    for damage_type in DamageType:
        try:
            if entity.health.get_resistance(damage_type) == status:
                names.append(str(damage_type.value))
        except Exception:
            continue
    return sorted(names)


def _equipment_summary(entity: Entity) -> list[dict[str, Any]]:
    rows = []
    for item in entity.equipment.get_all_equipped_items():
        rows.append(_item_summary(item, equipped=True))
    return sorted(rows, key=lambda row: (str(row.get("slot")), str(row.get("name"))))


def _inventory_summary(entity: Entity) -> list[dict[str, Any]]:
    rows = [_item_summary(item, equipped=False) for item in entity.inventory.items.values()]
    return sorted(rows, key=lambda row: (str(row.get("name")), int(row.get("stack_count", 1))))


def _item_summary(item: Any, *, equipped: bool) -> dict[str, Any]:
    properties = [str(getattr(prop, "value", prop)) for prop in getattr(item, "properties", []) or []]
    provided_spell_semantic_keys = sorted({
        action.get_semantic_key()
        for action in getattr(item, "use_action_templates", []) or []
        if getattr(action, "is_spell", False)
    })
    provided_action_semantic_keys = sorted({
        action.get_semantic_key()
        for action in getattr(item, "use_action_templates", []) or []
    })
    return {
        "name": getattr(item, "name", type(item).__name__),
        "class": type(item).__name__,
        "semantic_key": (
            item.get_semantic_key()
            if callable(getattr(item, "get_semantic_key", None))
            else f"{type(item).__module__}.{type(item).__name__}"
        ),
        "content_kind": str(
            getattr(
                getattr(item, "content_kind", RuntimeBehaviorKind.ITEM),
                "value",
                RuntimeBehaviorKind.ITEM.value,
            )
        ),
        "equipped": equipped,
        "slot": getattr(item, "equipped_slot", None),
        "stack_count": getattr(item, "stack_count", 1),
        "is_usable": bool(getattr(item, "is_usable", False)),
        "is_equippable": bool(getattr(item, "is_equippable", False)),
        "properties": sorted(properties),
        "provided_spell_semantic_keys": provided_spell_semantic_keys,
        "provided_action_semantic_keys": provided_action_semantic_keys,
        "damage": _jsonable(getattr(item, "damage", None)),
        "range": _jsonable(getattr(item, "range", None)),
    }


def _spell_summary(entity: Entity) -> list[str]:
    return sorted({
        str(action.name)
        for action in entity.registered_actions
        if getattr(action, "is_spell", False) and action.name is not None
    })


def _action_template_summary(entity: Entity) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for action in entity.registered_actions:
        rows.append({
            "name": action.name,
            "class": type(action).__name__,
            "semantic_key": action.get_semantic_key(),
            "target_type": str(getattr(action.effective_target_type, "value", action.effective_target_type)),
            "category": str(getattr(action.action_category, "value", action.action_category)),
            "costs": [_cost_summary(cost) for cost in action.effective_costs],
            "requires_concentration": action.requires_concentration,
            "allow_same_target": action.allow_same_target,
            "valid_target_filter": action.valid_target_filter,
            "source_item_uuid_present": action.source_item_uuid is not None,
        })
    return sorted(rows, key=lambda row: (row["category"], row["name"], row["semantic_key"]))


def _cost_summary(cost: Any) -> dict[str, Any]:
    return {
        "cost_type": str(getattr(cost, "cost_type", "")),
        "cost": getattr(cost, "cost", None),
        "resource_name": getattr(cost, "resource_name", None),
        "resource_cost": getattr(cost, "resource_cost", None),
    }


def _trait_summary(entity: Entity) -> list[str]:
    handler_names = [handler.name for handler in entity.event_handlers.values()]
    condition_immunities = [f"immune:{name}" for name, _source in entity.condition_immunities]
    contextual = [f"contextual_immune:{name}" for name in entity.contextual_condition_immunities]
    return sorted(set(handler_names + condition_immunities + contextual))


def _condition_summary(entity: Entity) -> list[dict[str, Any]]:
    """Return stable typed identities for active rules conditions and features."""
    rows: list[dict[str, Any]] = []
    for condition in entity.active_conditions.values():
        kind = condition.get_content_kind()
        rows.append({
            "name": condition.name,
            "class": type(condition).__name__,
            "semantic_key": condition.get_semantic_key(),
            "content_kind": kind.value,
            "condition_category": str(
                getattr(getattr(condition, "condition_category", None), "value", "condition")
            ),
            "tags": sorted(
                str(getattr(tag, "value", tag))
                for tag in getattr(condition, "tags", set())
            ),
        })
    return sorted(rows, key=lambda row: (row["content_kind"], row["name"], row["semantic_key"]))


def _handler_summary(entity: Entity) -> list[dict[str, Any]]:
    """Return stable handler identities and trigger contracts for one actor."""
    rows: list[dict[str, Any]] = []
    for handler in entity.event_handlers.values():
        triggers = [
            {
                "event_type": trigger.event_type.value,
                "event_phase": trigger.event_phase.value,
                "filters_source": trigger.event_source_entity_uuid is not None,
                "filters_target": trigger.event_target_entity_uuid is not None,
            }
            for trigger in getattr(handler, "trigger_conditions", [])
        ]
        rows.append({
            "name": handler.name,
            "class": type(handler).__name__,
            "semantic_key": handler.get_semantic_key(),
            "content_kind": handler.content_kind.value,
            "enabled": handler.enabled,
            "player_toggleable": handler.player_toggleable,
            "triggers": triggers,
        })
    return sorted(rows, key=lambda row: (row["content_kind"], row["name"], row["semantic_key"]))


def _terrain_summary(tiles: Mapping[tuple[int, int], BaseBlock]) -> dict[str, Any]:
    names = Counter(getattr(tile, "name", "Tile") for tile in tiles.values())
    default_lights = Counter(
        getattr(getattr(tile, "default_light", None), "name", str(getattr(tile, "default_light", "unknown")))
        for tile in tiles.values()
    )
    walkable = sum(1 for tile in tiles.values() if getattr(tile, "walkable", False))
    visible = sum(1 for tile in tiles.values() if getattr(tile, "visible", False))
    conditioned = sum(1 for tile in tiles.values() if getattr(tile, "active_conditions", {}))
    return {
        "tile_count": len(tiles),
        "walkable_count": walkable,
        "visible_count": visible,
        "conditioned_count": conditioned,
        "by_name": dict(sorted(names.items())),
        "by_default_light": dict(sorted(default_lights.items())),
    }


def _object_summary(grid: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for object_uuid, position in sorted(grid._object_positions.items(), key=lambda row: (row[1], str(row[0]))):
        block = BaseBlock.get(object_uuid)
        if block is None:
            continue
        rows.append({
            "name": block.name,
            "class": type(block).__name__,
            "semantic_key": _content_semantic_key(block),
            "content_kind": RuntimeBehaviorKind.ENVIRONMENT_INTERACTION.value,
            "position": position,
            "blocks_walking": bool(block.blocks_walking()),
            "blocks_vision": bool(block.blocks_vision()),
            "open_state": block.get_spatial_open_state(),
            "conditions": sorted(block.active_conditions),
            "provided_action_semantic_keys": sorted({
                action.get_semantic_key()
                for action in getattr(block, "use_action_templates", []) or []
            }),
        })
    return rows


def _manifest_hash(manifest: ArenaManifest) -> str:
    payload = manifest.model_dump(mode="json", exclude={"manifest_hash"})
    return _stable_hash(payload)


def _content_semantic_key(content: Any) -> str:
    """Return a declared semantic key or stable class identity."""
    get_semantic_key = getattr(content, "get_semantic_key", None)
    if callable(get_semantic_key):
        key = get_semantic_key()
        if isinstance(key, str):
            return key
    return f"{type(content).__module__}.{type(content).__name__}"


def _initiative_order(arena: ValidationArena) -> list[dict[str, Any]]:
    """Return stable initiative rows from the actual precombat encounter."""
    rows: list[dict[str, Any]] = []
    for entity_uuid in arena.encounter.initiative_order:
        combatant = arena.encounter.combatants.get(entity_uuid)
        entity = Entity.get(entity_uuid)
        if combatant is None or entity is None:
            continue
        rows.append({
            "name": entity.name,
            "faction": entity.faction,
            "initiative_roll": combatant.initiative_roll,
            "initiative_bonus": combatant.initiative_bonus,
            "initiative_total": combatant.initiative_total,
        })
    return rows


def _roster_identity_payload(row: EntityRosterRow) -> dict[str, Any]:
    """Return mechanical identity without runtime presentation or ownership."""
    payload = row.model_dump(
        mode="json",
        exclude={"stable_name", "faction", "position", "controller_type"},
    )
    senses = dict(payload.get("senses", {}))
    payload["senses"] = {
        "has_ordinary_sight": senses.get("has_ordinary_sight"),
        "special_senses": senses.get("special_senses", []),
    }
    return payload


def roster_identity_hash(rows: list[EntityRosterRow]) -> str:
    """Hash a side roster as an order-independent mechanical multiset.

    Args:
        rows: Runtime roster rows for one side.

    Returns:
        Stable hash that ignores names, factions, placement, controllers, and
        volatile perception caches.
    """
    payloads = [_roster_identity_payload(row) for row in rows]
    payloads.sort(key=lambda payload: json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":")))
    return _stable_hash(payloads)


def _stable_hash(payload: object) -> str:
    raw = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(inner) for inner in value]
    if hasattr(value, "value"):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _safe_int(fn: Any) -> Optional[int]:
    try:
        value = fn()
        return int(value) if value is not None else None
    except Exception:
        return None


@contextmanager
def _preserved_random_seed(random_seed: Optional[int]) -> Iterator[None]:
    if random_seed is None:
        yield
        return
    state = random.getstate()
    random.seed(random_seed)
    try:
        yield
    finally:
        random.setstate(state)
