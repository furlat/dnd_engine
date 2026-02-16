"""
Performance benchmark for get_available_actions() in the sorcerer arena scenario.

Measures timing across 4 scenarios:
1. Door closed, enemies hidden behind wall
2. Door open, enemies visible
3. Door open, hero torch off (dark on hero side)
4. Door open, hero torch on again

Reports macro timing (full call), micro benchmarks (isolated bottlenecks),
and AoE loop isolation to pinpoint where time is spent.
"""

import time
import statistics
from uuid import uuid4
from typing import List, Tuple, Dict, Any

from dnd.core.gridmap import reset_map, get_map
from dnd.core.events import EventQueue
from dnd.core.base_block import LightLevel
from dnd.core.base_actions import TargetType
from dnd.entity import Entity
from dnd.encounter import Encounter
from dnd.controller import HumanController, MeleeAIController, Controller
from dnd.monsters.bestiary import create_sorcerer, create_skeleton
from dnd.items.test_items import (
    TestDoorA, Torch, create_torch, create_wall_torch,
    create_scroll_of_magic_missile, create_scroll_of_fireball,
    create_healing_potion, create_potion_of_greater_invisibility,
    TrapLever, PullLeverAction,
)
from dnd.tiles import create_spike_zone
from dnd.core.base_tiles import difficult_terrain_factory
from dnd.actions_functional import get_available_actions, execute_by_index, execute_use_action
from dnd.reactions import add_opportunity_attack_handler


# ──────────────────────────────────────────────────────────────────────
# Arena Setup (replicated from server/event_server.py:setup_arena_combat)
# ──────────────────────────────────────────────────────────────────────

def setup_sorcerer_arena() -> Tuple[Entity, List[Entity], "Encounter", "Torch", "TestDoorA"]:
    """Set up the sorcerer arena matching the server's setup_arena_combat(character_class='sorcerer').

    Returns (hero, skeletons, encounter, hero_torch, door).
    """
    # Reset all state
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    Controller._controller_registry.clear()
    EventQueue.reset()

    # Create grid
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Vertical wall at x=7, y=3-11 (gap at y=7 for door)
    for y in range(3, 12):
        if y != 7:
            grid.set_tile(7, y, walkable=False, visible=False)

    # Closed door at wall gap
    door = TestDoorA(source_entity_uuid=uuid4())
    grid.place_object(door.uuid, (7, 7))

    # Water island in top-left
    for y in range(4):
        grid.set_tile(2, y, walkable=False, visible=True, name="Water")
    for x in range(2):
        grid.set_tile(x, 3, walkable=False, visible=True, name="Water")

    # Spike zone in bottom-left
    spike_positions = {(x, y) for x in range(5) for y in range(11, 15)}
    spike_tiles, spike_handler = create_spike_zone(spike_positions)
    for tile in spike_tiles:
        grid._tiles[tile.position] = tile
        grid._tiles_by_uuid[tile.uuid] = tile.position

    # Difficult terrain at wall ends
    for x in range(6, 9):
        for y in range(0, 3):
            tile = difficult_terrain_factory((x, y))
            grid._tiles[tile.position] = tile
            grid._tiles_by_uuid[tile.uuid] = tile.position
    for x in range(6, 9):
        for y in range(12, 15):
            tile = difficult_terrain_factory((x, y))
            grid._tiles[tile.position] = tile
            grid._tiles_by_uuid[tile.uuid] = tile.position

    # Dark arena
    for pos, tile in grid._tiles.items():
        tile.default_light = LightLevel.DARKNESS

    # Wall torches on far side
    create_wall_torch(position=(14, 1), owner_uuid=uuid4(), lit=True)
    create_wall_torch(position=(14, 13), owner_uuid=uuid4(), lit=True)

    # Create sorcerer hero
    player = create_sorcerer(name="Hero", position=(2, 7), faction="heroes")

    # Give hero a lit torch
    torch = create_torch(player.uuid)
    player.loot_item(torch)
    torch.ignite(player.uuid)

    # Greater Invisibility potion
    potion = create_potion_of_greater_invisibility(player.uuid)
    player.loot_item(potion)

    # Spell scrolls
    scroll_mm1 = create_scroll_of_magic_missile(player.uuid, cast_level=1)
    scroll_mm2 = create_scroll_of_magic_missile(player.uuid, cast_level=1)
    scroll_fb3 = create_scroll_of_fireball(player.uuid, cast_level=3)
    scroll_fb5 = create_scroll_of_fireball(player.uuid, cast_level=5)
    player.loot_item(scroll_mm1)
    player.loot_item(scroll_mm2)
    player.loot_item(scroll_fb3)
    player.loot_item(scroll_fb5)

    # Healing potions on floor in spike zone
    for pot_pos in [(1, 12), (3, 13)]:
        healing_pot = create_healing_potion(uuid4(), heal_amount=10)
        grid.place_object(healing_pot.uuid, pot_pos)

    # Trap lever
    lever_action = PullLeverAction(
        source_entity_uuid=uuid4(), trap_handler_uuid=spike_handler.uuid, template=True
    )
    lever = TrapLever(
        source_entity_uuid=uuid4(), use_action_templates=[lever_action], charges=1
    )
    grid.place_object(lever.uuid, (5, 12))

    # Create skeletons
    skeleton_positions = [(12, 5), (12, 7), (12, 9)]
    skeletons = []
    for i, pos in enumerate(skeleton_positions):
        skeleton = create_skeleton(
            name=f"Skeleton {i+1}",
            position=pos,
            faction="monsters",
            darkvision=True
        )
        skeletons.append(skeleton)

    # Opportunity attack handlers
    add_opportunity_attack_handler(player)
    for skeleton in skeletons:
        add_opportunity_attack_handler(skeleton)

    Entity.update_all_entities_senses(max_distance=20)

    # Create encounter
    encounter = Encounter(name="Perf Test Arena", source_entity_uuid=uuid4())
    encounter.add_combatant(player, HumanController(source_entity_uuid=player.uuid))
    for skeleton in skeletons:
        encounter.add_combatant(skeleton, MeleeAIController(source_entity_uuid=skeleton.uuid))

    return player, skeletons, encounter, torch, door


# ──────────────────────────────────────────────────────────────────────
# Measurement Utilities
# ──────────────────────────────────────────────────────────────────────

def find_hero_torch(hero: Entity) -> Torch:
    """Find the torch in the hero's inventory."""
    items = hero.inventory.find_items_by_name("Torch")
    assert len(items) > 0, "Hero has no torch"
    torch = items[0]
    assert isinstance(torch, Torch)
    return torch


def measure_get_available_actions(hero: Entity, iterations: int = 3) -> Tuple[List[float], Any]:
    """Run get_available_actions N times, return (times_ms, last_result)."""
    times: List[float] = []
    result = None
    for _ in range(iterations):
        start = time.perf_counter()
        result = get_available_actions(hero)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    return times, result


def summarize_result(result: Any) -> Dict[str, Any]:
    """Extract summary stats from AvailableActionsResult."""
    summary: Dict[str, Any] = {}
    summary["entity_actions"] = len(result.entity_actions)
    summary["self_actions"] = len(result.self_actions)
    summary["object_actions"] = len(result.object_actions)
    summary["remaining_movement"] = result.remaining_movement

    # Position actions breakdown
    pos_breakdown: Dict[str, Dict[str, int]] = {}
    for action_info in result.position_actions:
        name = action_info.template_name
        total_positions = len(action_info.valid_targets)
        positions_with_targets = 0
        if action_info.target_type == TargetType.POSITION_AOE:
            positions_with_targets = sum(
                1 for t in action_info.valid_targets
                if t.affected_count and t.affected_count > 0
            )
        pos_breakdown[name] = {
            "valid_positions": total_positions,
            "with_targets": positions_with_targets,
        }
    summary["position_actions"] = pos_breakdown
    return summary


def print_timing(label: str, times: List[float]) -> None:
    """Print min/avg/max timing for a measurement."""
    mn = min(times)
    avg = statistics.mean(times)
    mx = max(times)
    print(f"  {label}: min={mn:.1f}ms  avg={avg:.1f}ms  max={mx:.1f}ms")


def print_summary(summary: Dict[str, Any]) -> None:
    """Print action counts summary."""
    print(f"  entity_actions: {summary['entity_actions']}")
    print(f"  self_actions: {summary['self_actions']}")
    print(f"  object_actions: {summary['object_actions']}")
    print(f"  remaining_movement: {summary['remaining_movement']}ft")
    print(f"  position_actions:")
    for name, info in summary["position_actions"].items():
        vp = info["valid_positions"]
        wt = info["with_targets"]
        if wt > 0:
            print(f"    {name}: {vp} positions ({wt} with targets)")
        else:
            print(f"    {name}: {vp} positions")


# ──────────────────────────────────────────────────────────────────────
# Internal Instrumentation — times each phase inside get_available_actions
# ──────────────────────────────────────────────────────────────────────

from dnd.core.base_actions import AvailableTarget, AvailableActionInfo
from dnd.core.base_block import BaseBlock
from dnd.blocks.base_item import UsableItem
from dnd.blocks.equipment import WeaponSlot


def instrumented_get_available_actions(
    entity: Entity,
    target_filter: str = "enemies",
    include_dead: bool = False,
) -> Tuple[Any, Dict[str, float]]:
    """Run get_available_actions logic with per-phase timing.

    Returns (AvailableActionsResult, phase_timings_dict).
    Phase timings keys:
      self_actions, entity_actions, paths_refresh, position_path, position_los,
      aoe_registered, use_actions_discovery, use_self, use_entity, use_aoe,
      use_position_los, use_position_path, object_actions, total
    Also per-AoE-spell keys like "aoe:Fireball" with sub-dict {get_valid_positions, pre_validate, compute_subjective, filtering, total, n_positions, n_valid}.
    """
    timings: Dict[str, float] = {}
    aoe_details: Dict[str, Dict[str, Any]] = {}  # per-spell AoE breakdown
    t_total_start = time.perf_counter()

    from dnd.core.base_actions import AvailableActionsResult

    result = AvailableActionsResult(
        entity_uuid=entity.uuid,
        remaining_movement=entity.action_economy.movement.normalized_score
    )

    # ── SELF actions ──
    t0 = time.perf_counter()
    for template in entity.self_actions:
        template_name = template.name or "Unknown"
        can_afford = template.check_costs()
        is_valid = can_afford and template.pre_validate()
        if is_valid or not can_afford:
            result.self_actions.append(AvailableActionInfo(
                template_name=template_name, target_type=TargetType.SELF,
                valid_targets=[AvailableTarget(index=0)] if is_valid else [],
                can_afford=can_afford, display_name=template_name,
                description=template.description,
                cost_type=template.costs[0].cost_type if template.costs else "actions",
                cost_amount=template.costs[0].cost if template.costs else 0,
                action_category=template.action_category,
            ))
    timings["self_actions"] = (time.perf_counter() - t0) * 1000

    # ── ENTITY actions ──
    t0 = time.perf_counter()
    if target_filter == "enemies":
        potential_targets = entity.get_visible_enemies(include_dead=include_dead)
    elif target_filter == "allies":
        potential_targets = entity.get_visible_allies(include_dead=include_dead)
    else:
        potential_targets = {}
        for k, v in entity.senses.entities.items():
            if k == entity.uuid:
                continue
            if not include_dead:
                other = Entity.get(k)
                if other and not other.has_hp:
                    continue
            potential_targets[k] = v

    for template in entity.entity_actions:
        valid_targets: list = []
        idx = 0
        action_filter = template.valid_target_filter
        if action_filter == "all" or action_filter == "self_or_allies":
            template_targets: Dict = {}
            if action_filter == "all":
                for k, v in entity.senses.entities.items():
                    if k == entity.uuid:
                        continue
                    if not include_dead:
                        other = Entity.get(k)
                        if other and not other.has_hp:
                            continue
                    template_targets[k] = v
            elif action_filter == "self_or_allies":
                for k, v in entity.get_visible_allies(include_dead=include_dead).items():
                    template_targets[k] = v
        else:
            template_targets = dict(potential_targets)

        if template.include_self:
            template_targets[entity.uuid] = entity.position

        for target_uuid, target_pos in template_targets.items():
            template.set_target_entity(target_uuid)
            if template.pre_validate():
                target_entity = Entity.get(target_uuid)
                valid_targets.append(AvailableTarget(
                    index=idx, target_uuid=target_uuid,
                    target_name=target_entity.name if target_entity else None,
                    distance=entity.senses.get_feet_distance(target_pos)
                ))
                idx += 1

        if valid_targets:
            template_name = template.name or "Unknown"
            weapon_name = None
            weapon_slot_str = None
            display_name = template_name
            weapon_slot_attr = getattr(template, 'weapon_slot', None)
            if weapon_slot_attr is not None:
                weapon_slot_str = weapon_slot_attr.value if isinstance(weapon_slot_attr, WeaponSlot) else str(weapon_slot_attr)
                weapon = entity.equipment._get_weapon_by_slot(weapon_slot_attr)
                if weapon:
                    weapon_name = weapon.name
                    display_name = weapon_name

            result.entity_actions.append(AvailableActionInfo(
                template_name=template_name, target_type=template.target_type,
                valid_targets=valid_targets, can_afford=template.check_costs(),
                display_name=display_name, description=template.description,
                cost_type=template.costs[0].cost_type if template.costs else "actions",
                cost_amount=template.costs[0].cost if template.costs else 0,
                weapon_slot=weapon_slot_str, weapon_name=weapon_name,
                action_category=template.action_category,
            ))
    timings["entity_actions"] = (time.perf_counter() - t0) * 1000

    # ── Paths refresh ──
    t0 = time.perf_counter()
    if entity.senses._paths_dirty:
        entity.update_entity_senses(max_distance=20)
    timings["paths_refresh"] = (time.perf_counter() - t0) * 1000

    # ── POSITION_PATH (Move) ──
    t0 = time.perf_counter()
    for template in entity.position_actions:
        if template.target_type not in (TargetType.POSITION, TargetType.POSITION_PATH):
            continue
        valid_positions: list = []
        idx = 0
        for pos, _ in entity.senses.paths.items():
            if pos == entity.senses.position:
                continue
            template.set_target_position(pos)
            if template.pre_validate():
                path_cost = 0
                for cost in template.costs:
                    if cost.cost_type == "movement":
                        path_cost = cost.cost
                        break
                valid_positions.append(AvailableTarget(
                    index=idx, position=pos,
                    distance=entity.senses.get_feet_distance(pos), path_cost=path_cost
                ))
                idx += 1
        if valid_positions:
            template_name = template.name or "Unknown"
            result.position_actions.append(AvailableActionInfo(
                template_name=template_name, target_type=template.target_type,
                valid_targets=valid_positions, can_afford=True,
                display_name=template_name,
                description=f"{result.remaining_movement}ft remaining",
                cost_type="movement", cost_amount=0,
                action_category=template.action_category,
            ))
    timings["position_path"] = (time.perf_counter() - t0) * 1000

    # ── POSITION_LOS (Jump) ──
    t0 = time.perf_counter()
    for template in entity.position_actions:
        if template.target_type != TargetType.POSITION_LOS:
            continue
        valid_pos_list = template.get_valid_positions()
        valid_positions = []
        idx = 0
        for pos in valid_pos_list:
            template.set_target_position(pos)
            if template.pre_validate():
                valid_positions.append(AvailableTarget(
                    index=idx, position=pos,
                    distance=entity.senses.get_feet_distance(pos), path_cost=None
                ))
                idx += 1
        if valid_positions:
            template_name = template.name or "Unknown"
            cost_type = template.costs[0].cost_type if template.costs else "bonus_actions"
            cost_amount = template.costs[0].cost if template.costs else 1
            result.position_actions.append(AvailableActionInfo(
                template_name=template_name, target_type=TargetType.POSITION_LOS,
                valid_targets=valid_positions, can_afford=template.check_costs(),
                display_name=template_name, description=template.description,
                cost_type=cost_type, cost_amount=cost_amount,
                action_category=template.action_category,
            ))
    timings["position_los"] = (time.perf_counter() - t0) * 1000

    # ── POSITION_AOE (registered spells) — per-spell breakdown ──
    t0 = time.perf_counter()
    for template in entity.position_actions:
        if template.target_type != TargetType.POSITION_AOE:
            continue
        shape_template = template.aoe_shape
        if shape_template is None:
            continue

        spell_name = template.name or "Unknown"
        spell_t: Dict[str, Any] = {"get_valid_positions": 0.0, "pre_validate": 0.0,
                                    "compute_subjective": 0.0, "filtering": 0.0,
                                    "total": 0.0, "n_positions": 0, "n_valid": 0}
        spell_start = time.perf_counter()

        t_gvp = time.perf_counter()
        valid_pos_list = template.get_valid_positions()
        spell_t["get_valid_positions"] = (time.perf_counter() - t_gvp) * 1000
        spell_t["n_positions"] = len(valid_pos_list)

        valid_positions = []
        idx = 0
        pv_time = 0.0
        cs_time = 0.0
        filt_time = 0.0

        for pos in valid_pos_list:
            t_pv = time.perf_counter()
            template.set_target_position(pos)
            passed = template.pre_validate()
            pv_time += (time.perf_counter() - t_pv) * 1000

            if not passed:
                continue

            t_cs = time.perf_counter()
            shape = shape_template.model_copy(update={'target': pos})
            shape.compute_subjective(entity.position, entity.senses)
            cs_time += (time.perf_counter() - t_cs) * 1000

            t_filt = time.perf_counter()
            affected_uuids = list(shape.affected_entity_uuids)
            if not template.include_self:
                affected_uuids = [uid for uid in affected_uuids if uid != entity.uuid]
            tf = template.valid_target_filter
            if tf != "all":
                filtered = []
                for uid in affected_uuids:
                    ent = Entity.get(uid)
                    if ent:
                        if tf == "enemies" and entity.is_enemy(ent):
                            filtered.append(uid)
                        elif tf == "allies" and entity.is_ally(ent):
                            filtered.append(uid)
                        elif tf == "self_or_allies":
                            if uid == entity.uuid or entity.is_ally(ent):
                                filtered.append(uid)
                affected_uuids = filtered
            if not template.include_dead and not include_dead:
                affected_uuids = [
                    uid for uid in affected_uuids
                    if (ent := Entity.get(uid)) and ent.has_hp
                ]
            affected_names = []
            for uid in affected_uuids:
                ent = Entity.get(uid)
                if ent:
                    affected_names.append(ent.name or "Unknown")
            filt_time += (time.perf_counter() - t_filt) * 1000

            valid_positions.append(AvailableTarget(
                index=idx, position=pos,
                distance=entity.senses.get_feet_distance(pos),
                affected_entity_uuids=affected_uuids,
                affected_entity_names=affected_names,
                affected_count=len(affected_uuids),
                affected_positions=list(shape.affected_positions)
            ))
            idx += 1

        spell_t["pre_validate"] = pv_time
        spell_t["compute_subjective"] = cs_time
        spell_t["filtering"] = filt_time
        spell_t["n_valid"] = len(valid_positions)
        spell_t["total"] = (time.perf_counter() - spell_start) * 1000
        aoe_details[spell_name] = spell_t

        if valid_positions:
            template_name = template.name or "Unknown"
            cost_type = template.costs[0].cost_type if template.costs else "actions"
            result.position_actions.append(AvailableActionInfo(
                template_name=template_name, target_type=TargetType.POSITION_AOE,
                valid_targets=valid_positions, can_afford=template.check_costs(),
                display_name=template_name, description=template.description,
                cost_type=cost_type,
                cost_amount=template.costs[0].cost if template.costs else 1,
                action_category=template.action_category,
            ))
    timings["aoe_registered"] = (time.perf_counter() - t0) * 1000

    # ── OBJECT actions ──
    t0 = time.perf_counter()
    for template in entity.object_actions:
        valid_targets = []
        idx = 0
        can_afford = template.check_costs()
        for obj_uuid, obj_pos in entity.senses.objects.items():
            template.set_target_entity(obj_uuid)
            if template.pre_validate():
                obj_block = BaseBlock.get(obj_uuid)
                obj_name = obj_block.name if obj_block else "Object"
                valid_targets.append(AvailableTarget(
                    index=idx, target_uuid=obj_uuid, position=obj_pos,
                    target_name=obj_name,
                    distance=entity.senses.get_feet_distance(obj_pos)
                ))
                idx += 1
        if valid_targets:
            template_name = template.name or "Unknown"
            result.object_actions.append(AvailableActionInfo(
                template_name=template_name, target_type=TargetType.OBJECT,
                valid_targets=valid_targets, can_afford=can_afford,
                display_name=template_name, description=template.description,
                cost_type=template.costs[0].cost_type if template.costs else "actions",
                cost_amount=template.costs[0].cost if template.costs else 0,
                action_category=template.action_category,
            ))
    timings["object_actions"] = (time.perf_counter() - t0) * 1000

    # ── USE ACTIONS (inventory + environment) ──
    t0 = time.perf_counter()
    use_sources: list = []
    for use_template in entity.inventory.get_all_use_actions(entity.uuid):
        item_uuid = use_template.source_item_uuid
        item = BaseBlock.get(item_uuid) if item_uuid else None
        item_name = item.name if item else "Item"
        item_stack = getattr(item, 'stack_count', None) if item else None
        use_sources.append((use_template, item_uuid, item_name, item_stack))
    for obj_uuid, obj_pos in entity.senses.objects.items():
        obj = BaseBlock.get(obj_uuid)
        if not isinstance(obj, UsableItem):
            continue
        if entity.senses.get_feet_distance(obj_pos) > 5:
            continue
        for use_template in obj.get_use_actions(entity.uuid):
            use_sources.append((use_template, obj_uuid, obj.name, None))
    timings["use_actions_discovery"] = (time.perf_counter() - t0) * 1000

    t_use_self = 0.0
    t_use_entity = 0.0
    t_use_aoe = 0.0
    t_use_pos_los = 0.0
    t_use_pos_path = 0.0

    for use_template, item_uuid, item_name, item_stack in use_sources:
        base_name = use_template.name or "Use"
        template_name = f"{base_name}__item_{item_uuid}"
        stack_suffix = f" x{item_stack}" if item_stack and item_stack > 1 else ""
        display_name = f"{base_name} ({item_name}{stack_suffix})"
        stack_count_field = item_stack if item_stack and item_stack > 1 else None
        can_afford = use_template.check_costs()
        cost_type = use_template.costs[0].cost_type if use_template.costs else "actions"
        cost_amount = use_template.costs[0].cost if use_template.costs else 0

        if use_template.target_type == TargetType.SELF:
            t_s = time.perf_counter()
            if use_template.pre_validate():
                result.self_actions.append(AvailableActionInfo(
                    template_name=template_name, target_type=TargetType.SELF,
                    valid_targets=[AvailableTarget(index=0)], can_afford=can_afford,
                    display_name=display_name, description=use_template.description,
                    cost_type=cost_type, cost_amount=cost_amount,
                    is_item_use=True, source_item_uuid=item_uuid,
                    action_category=use_template.action_category,
                    item_stack_count=stack_count_field,
                ))
            t_use_self += (time.perf_counter() - t_s) * 1000

        elif use_template.target_type in (TargetType.ENTITY, TargetType.MULTI_ENTITY):
            t_s = time.perf_counter()
            use_valid_targets: list = []
            use_idx = 0
            use_target_pool = dict(potential_targets)
            if use_template.include_self:
                use_target_pool[entity.uuid] = entity.position
            for target_uuid, target_pos in use_target_pool.items():
                use_template.set_target_entity(target_uuid)
                if use_template.pre_validate():
                    target_entity = Entity.get(target_uuid)
                    use_valid_targets.append(AvailableTarget(
                        index=use_idx, target_uuid=target_uuid,
                        target_name=target_entity.name if target_entity else None,
                        distance=entity.senses.get_feet_distance(target_pos)
                    ))
                    use_idx += 1
            if use_valid_targets:
                result.entity_actions.append(AvailableActionInfo(
                    template_name=template_name, target_type=use_template.target_type,
                    valid_targets=use_valid_targets, can_afford=can_afford,
                    display_name=display_name, description=use_template.description,
                    cost_type=cost_type, cost_amount=cost_amount,
                    is_item_use=True, source_item_uuid=item_uuid,
                    action_category=use_template.action_category,
                    item_stack_count=stack_count_field,
                ))
            t_use_entity += (time.perf_counter() - t_s) * 1000

        elif use_template.target_type == TargetType.POSITION_AOE:
            t_s = time.perf_counter()
            use_shape_template = use_template.aoe_shape
            if use_shape_template is None:
                continue

            spell_name = f"{base_name}__item"
            spell_t_item: Dict[str, Any] = {"get_valid_positions": 0.0, "pre_validate": 0.0,
                                             "compute_subjective": 0.0, "filtering": 0.0,
                                             "total": 0.0, "n_positions": 0, "n_valid": 0}
            item_spell_start = time.perf_counter()

            t_gvp = time.perf_counter()
            use_valid_pos_list = use_template.get_valid_positions()
            spell_t_item["get_valid_positions"] = (time.perf_counter() - t_gvp) * 1000
            spell_t_item["n_positions"] = len(use_valid_pos_list)

            use_valid_positions: list = []
            use_idx = 0
            item_pv = 0.0
            item_cs = 0.0
            item_filt = 0.0

            for pos in use_valid_pos_list:
                t_pv = time.perf_counter()
                use_template.set_target_position(pos)
                passed = use_template.pre_validate()
                item_pv += (time.perf_counter() - t_pv) * 1000

                if not passed:
                    continue

                t_cs = time.perf_counter()
                shape = use_shape_template.model_copy(update={'target': pos})
                shape.compute_subjective(entity.position, entity.senses)
                item_cs += (time.perf_counter() - t_cs) * 1000

                t_filt = time.perf_counter()
                affected_uuids = list(shape.affected_entity_uuids)
                if not use_template.include_self:
                    affected_uuids = [uid for uid in affected_uuids if uid != entity.uuid]
                vtf = use_template.valid_target_filter
                if vtf != "all":
                    filtered = []
                    for uid in affected_uuids:
                        ent = Entity.get(uid)
                        if ent:
                            if vtf == "enemies" and entity.is_enemy(ent):
                                filtered.append(uid)
                            elif vtf == "allies" and entity.is_ally(ent):
                                filtered.append(uid)
                            elif vtf == "self_or_allies":
                                if uid == entity.uuid or entity.is_ally(ent):
                                    filtered.append(uid)
                    affected_uuids = filtered
                if not use_template.include_dead and not include_dead:
                    affected_uuids = [
                        uid for uid in affected_uuids
                        if (ent := Entity.get(uid)) and ent.has_hp
                    ]
                affected_names = []
                for uid in affected_uuids:
                    ent = Entity.get(uid)
                    if ent:
                        affected_names.append(ent.name or "Unknown")
                item_filt += (time.perf_counter() - t_filt) * 1000

                use_valid_positions.append(AvailableTarget(
                    index=use_idx, position=pos,
                    distance=entity.senses.get_feet_distance(pos),
                    affected_entity_uuids=affected_uuids,
                    affected_entity_names=affected_names,
                    affected_count=len(affected_uuids),
                    affected_positions=list(shape.affected_positions)
                ))
                use_idx += 1

            spell_t_item["pre_validate"] = item_pv
            spell_t_item["compute_subjective"] = item_cs
            spell_t_item["filtering"] = item_filt
            spell_t_item["n_valid"] = len(use_valid_positions)
            spell_t_item["total"] = (time.perf_counter() - item_spell_start) * 1000
            aoe_details[f"[item] {base_name}"] = spell_t_item

            if use_valid_positions:
                result.position_actions.append(AvailableActionInfo(
                    template_name=template_name, target_type=TargetType.POSITION_AOE,
                    valid_targets=use_valid_positions, can_afford=can_afford,
                    display_name=display_name, description=use_template.description,
                    cost_type=cost_type, cost_amount=cost_amount,
                    is_item_use=True, source_item_uuid=item_uuid,
                    action_category=use_template.action_category,
                    item_stack_count=stack_count_field,
                ))
            t_use_aoe += (time.perf_counter() - t_s) * 1000

        elif use_template.target_type == TargetType.POSITION_LOS:
            t_s = time.perf_counter()
            use_valid_pos_list = use_template.get_valid_positions()
            use_valid_positions = []
            use_idx = 0
            for pos in use_valid_pos_list:
                use_template.set_target_position(pos)
                if use_template.pre_validate():
                    use_valid_positions.append(AvailableTarget(
                        index=use_idx, position=pos,
                        distance=entity.senses.get_feet_distance(pos),
                    ))
                    use_idx += 1
            if use_valid_positions:
                result.position_actions.append(AvailableActionInfo(
                    template_name=template_name, target_type=TargetType.POSITION_LOS,
                    valid_targets=use_valid_positions, can_afford=can_afford,
                    display_name=display_name, description=use_template.description,
                    cost_type=cost_type, cost_amount=cost_amount,
                    is_item_use=True, source_item_uuid=item_uuid,
                    action_category=use_template.action_category,
                    item_stack_count=stack_count_field,
                ))
            t_use_pos_los += (time.perf_counter() - t_s) * 1000

    timings["use_self"] = t_use_self
    timings["use_entity"] = t_use_entity
    timings["use_aoe"] = t_use_aoe
    timings["use_position_los"] = t_use_pos_los
    timings["use_position_path"] = t_use_pos_path

    timings["total"] = (time.perf_counter() - t_total_start) * 1000
    timings["_aoe_details"] = aoe_details  # type: ignore[assignment]

    return result, timings


def print_instrumented(timings: Dict[str, Any]) -> None:
    """Print the phase breakdown from instrumented_get_available_actions."""
    total = timings["total"]
    print(f"\n  --- Phase Breakdown (total: {total:.1f}ms) ---")

    phases = [
        ("self_actions", "Self actions"),
        ("entity_actions", "Entity actions"),
        ("paths_refresh", "Paths refresh"),
        ("position_path", "Position/path (Move)"),
        ("position_los", "Position/LOS (Jump)"),
        ("aoe_registered", "AoE registered spells"),
        ("object_actions", "Object actions"),
        ("use_actions_discovery", "Use actions discovery"),
        ("use_self", "Use self actions"),
        ("use_entity", "Use entity actions"),
        ("use_aoe", "Use AoE (scroll spells)"),
        ("use_position_los", "Use position/LOS"),
    ]
    for key, label in phases:
        val = timings.get(key, 0.0)
        pct = val / total * 100 if total > 0 else 0
        if val >= 0.1:
            print(f"  {label:<30} {val:>8.1f}ms  ({pct:>5.1f}%)")

    # AoE per-spell details
    aoe_details = timings.get("_aoe_details", {})
    if aoe_details:
        print(f"\n  --- AoE Per-Spell Breakdown ---")
        print(f"  {'Spell':<25} {'Pos':>5} {'Valid':>5} {'GVP':>7} {'PreVal':>8} {'CompSub':>8} {'Filt':>6} {'Total':>8}")
        for spell_name, d in aoe_details.items():
            print(f"  {spell_name:<25} {d['n_positions']:>5} {d['n_valid']:>5} "
                  f"{d['get_valid_positions']:>6.1f} {d['pre_validate']:>7.1f} "
                  f"{d['compute_subjective']:>7.1f} {d['filtering']:>5.1f} {d['total']:>7.1f}")


# ──────────────────────────────────────────────────────────────────────
# Main Test
# ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("get_available_actions() Performance Benchmark — Sorcerer Arena")
    print("=" * 70)

    # Collect scenario timings for summary table
    all_timings: Dict[str, List[float]] = {}

    # ── Setup ──
    hero, _skeletons, encounter, _hero_torch, door = setup_sorcerer_arena()

    encounter.roll_initiative()
    encounter.start_encounter()

    # Force hero to go first
    if encounter.initiative_order[0] != hero.uuid:
        encounter.initiative_order.remove(hero.uuid)
        encounter.initiative_order.insert(0, hero.uuid)
        encounter.current_turn_index = 0

    encounter.start_turn()

    # ── Move hero from (2,7) to (6,7) — next to door ──
    print("\n[Setup] Moving hero from (2,7) to (6,7)...")
    result = get_available_actions(hero)
    for action_info in result.position_actions:
        if action_info.template_name == "Move":
            for target in action_info.valid_targets:
                if target.position == (6, 7):
                    execute_by_index(hero, "Move", target.index, available=result)
                    break
            break

    hero.update_entity_senses(max_distance=20)
    print(f"  Hero at {hero.position}, remaining movement: {hero.action_economy.movement.normalized_score}ft")

    # ══════════════════════════════════════════════════════════════════
    # Scenario 1: Door closed, enemies hidden
    # ══════════════════════════════════════════════════════════════════
    scenario = "1: Door closed, enemies hidden"
    print("\n" + "=" * 70)
    print(f"SCENARIO {scenario}")
    print("=" * 70)

    times, result = measure_get_available_actions(hero)
    all_timings[scenario] = times
    print_timing("get_available_actions", times)
    print_summary(summarize_result(result))

    # Instrumented run for scenario 1
    print("\n  --- Instrumented Run ---")
    _, inst_timings = instrumented_get_available_actions(hero)
    print_instrumented(inst_timings)

    # ══════════════════════════════════════════════════════════════════
    # Scenario 2: Open door, enemies visible
    # ══════════════════════════════════════════════════════════════════
    scenario = "2: Door open, enemies visible"
    print("\n" + "=" * 70)
    print(f"SCENARIO {scenario}")
    print("=" * 70)

    print("  Opening door...")
    execute_use_action(hero, door.uuid, "Open Door")
    Entity.update_all_entities_senses(max_distance=20)
    print(f"  Visible entities: {len(hero.senses.entities)}")

    times, result = measure_get_available_actions(hero)
    all_timings[scenario] = times
    print_timing("get_available_actions", times)
    print_summary(summarize_result(result))

    # Run instrumented version for detailed phase breakdown
    print("\n  --- Instrumented Run ---")
    _, inst_timings = instrumented_get_available_actions(hero)
    print_instrumented(inst_timings)

    # ══════════════════════════════════════════════════════════════════
    # Scenario 3: Door open, hero torch OFF (dark on hero side)
    # ══════════════════════════════════════════════════════════════════
    scenario = "3: Door open, torch OFF"
    print("\n" + "=" * 70)
    print(f"SCENARIO {scenario}")
    print("=" * 70)

    torch = find_hero_torch(hero)
    print(f"  Torch is_lit before: {torch.is_lit}")
    torch.extinguish()
    Entity.update_all_entities_senses(max_distance=20)
    print(f"  Torch is_lit after: {torch.is_lit}")
    print(f"  Visible entities: {len(hero.senses.entities)}")

    times, result = measure_get_available_actions(hero)
    all_timings[scenario] = times
    print_timing("get_available_actions", times)
    print_summary(summarize_result(result))

    # ══════════════════════════════════════════════════════════════════
    # Scenario 4: Door open, hero torch ON again
    # ══════════════════════════════════════════════════════════════════
    scenario = "4: Door open, torch ON"
    print("\n" + "=" * 70)
    print(f"SCENARIO {scenario}")
    print("=" * 70)

    torch.ignite(hero.uuid)
    Entity.update_all_entities_senses(max_distance=20)
    print(f"  Torch is_lit: {torch.is_lit}")
    print(f"  Visible entities: {len(hero.senses.entities)}")

    times, result = measure_get_available_actions(hero)
    all_timings[scenario] = times
    print_timing("get_available_actions", times)
    print_summary(summarize_result(result))

    # Instrumented run for scenario 4 (same as 2 but after torch cycle)
    print("\n  --- Instrumented Run ---")
    _, inst_timings = instrumented_get_available_actions(hero)
    print_instrumented(inst_timings)

    # ══════════════════════════════════════════════════════════════════
    # Summary Table
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TIMING SUMMARY (ms)")
    print("=" * 70)
    print(f"  {'Scenario':<40} {'Min':>8} {'Avg':>8} {'Max':>8}")
    print(f"  {'-' * 64}")
    for name, t in all_timings.items():
        mn = min(t)
        avg = statistics.mean(t)
        mx = max(t)
        print(f"  {name:<40} {mn:>7.1f} {avg:>7.1f} {mx:>7.1f}")

    print("\nDone.")


if __name__ == "__main__":
    main()
