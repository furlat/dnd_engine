"""
Performance benchmark for get_available_actions() in the sorcerer arena scenario.

Measures timing across 4 scenarios:
1. Door closed, enemies hidden behind wall
2. Door open, enemies visible
3. Door open, hero torch off (dark on hero side)
4. Door open, hero torch on again

Uses AoEProfiler to monkey-patch the real code path and collect per-call
timing without duplicating any logic.
"""

import time
import statistics
from uuid import uuid4
from typing import List, Tuple, Dict, Any

from dnd.core.gridmap import reset_map, get_map, GridMap
from dnd.core.events import EventQueue
from dnd.core.base_block import LightLevel
from dnd.core.base_actions import TargetType
from dnd.core.aoe import AoEShape
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
# AoE Profiler — monkey-patches the real code path, no duplicate logic
# ──────────────────────────────────────────────────────────────────────

class AoEProfiler:
    """Wraps AoEShape.compute_subjective and GridMap.compute_fov to collect
    per-call timing from the real get_available_actions code path."""

    def __init__(self) -> None:
        self.cs_calls: List[Dict[str, Any]] = []
        self.fov_calls: List[Dict[str, Any]] = []
        self._orig_cs = AoEShape.compute_subjective
        self._orig_fov = GridMap.compute_fov

    def __enter__(self) -> "AoEProfiler":
        profiler = self

        def timed_cs(shape_self: AoEShape, caster_pos: Any, senses: Any,
                     fov_cache: Any = None, barrier_positions: Any = None, caster_uuid: Any = None) -> AoEShape:
            t = time.perf_counter()
            result = profiler._orig_cs(shape_self, caster_pos, senses, fov_cache=fov_cache, barrier_positions=barrier_positions, caster_uuid=caster_uuid)
            elapsed = (time.perf_counter() - t) * 1000
            profiler.cs_calls.append({
                "shape": shape_self.name,
                "elapsed_ms": elapsed,
                "needs_fov": shape_self.computed_origin != caster_pos,
                "has_cache": fov_cache is not None,
            })
            return result

        def timed_fov(grid_self: GridMap, origin: Any, max_distance: Any = None,
                      observer_uuid: Any = None) -> Any:
            t = time.perf_counter()
            result = profiler._orig_fov(grid_self, origin, max_distance, observer_uuid)
            elapsed = (time.perf_counter() - t) * 1000
            profiler.fov_calls.append({
                "origin": origin,
                "radius": max_distance,
                "elapsed_ms": elapsed,
            })
            return result

        AoEShape.compute_subjective = timed_cs  # type: ignore[assignment]
        GridMap.compute_fov = timed_fov  # type: ignore[assignment]
        return self

    def __exit__(self, *args: Any) -> None:
        AoEShape.compute_subjective = self._orig_cs  # type: ignore[assignment]
        GridMap.compute_fov = self._orig_fov  # type: ignore[method-assign]

    def print_report(self) -> None:
        if not self.cs_calls:
            print("\n  --- AoE Profile: no compute_subjective calls ---")
            return

        total_cs_ms = sum(c["elapsed_ms"] for c in self.cs_calls)

        # Group by shape
        by_shape: Dict[str, Dict[str, Any]] = {}
        for call in self.cs_calls:
            shape = call["shape"]
            if shape not in by_shape:
                by_shape[shape] = {"count": 0, "total_ms": 0.0, "needs_fov": 0}
            by_shape[shape]["count"] += 1
            by_shape[shape]["total_ms"] += call["elapsed_ms"]
            if call["needs_fov"]:
                by_shape[shape]["needs_fov"] += 1

        print(f"\n  --- AoE Profile ---")
        print(f"  compute_subjective: {len(self.cs_calls)} calls, {total_cs_ms:.1f}ms total")
        print(f"  {'Shape':<12} {'Calls':>6} {'Total':>8} {'Avg':>7} {'NeedFOV':>8}")
        for shape, info in sorted(by_shape.items()):
            avg = info["total_ms"] / info["count"]
            print(f"  {shape:<12} {info['count']:>6} {info['total_ms']:>7.1f}ms {avg:>6.2f}ms {info['needs_fov']:>8}")

        # FOV cache analysis
        total_fov_needed = sum(1 for c in self.cs_calls if c["needs_fov"])
        actual_fov_calls = len(self.fov_calls)
        cache_hits = total_fov_needed - actual_fov_calls
        total_fov_ms = sum(c["elapsed_ms"] for c in self.fov_calls)

        if total_fov_needed > 0:
            hit_rate = cache_hits / total_fov_needed * 100
            print(f"\n  FOV cache: {cache_hits} hits / {total_fov_needed} needed ({hit_rate:.0f}% hit rate)")
            print(f"  compute_fov: {actual_fov_calls} calls, {total_fov_ms:.1f}ms total", end="")
            if actual_fov_calls > 0:
                avg_fov = total_fov_ms / actual_fov_calls
                saved_ms = cache_hits * avg_fov
                print(f" (avg {avg_fov:.2f}ms, cache saved ~{saved_ms:.0f}ms)")
            else:
                print()

            # FOV by radius
            fov_by_radius: Dict[int, Dict[str, Any]] = {}
            for call in self.fov_calls:
                r = call["radius"] or 0
                if r not in fov_by_radius:
                    fov_by_radius[r] = {"count": 0, "total_ms": 0.0}
                fov_by_radius[r]["count"] += 1
                fov_by_radius[r]["total_ms"] += call["elapsed_ms"]
            if len(fov_by_radius) > 1:
                print(f"  FOV by radius:")
                for r, info in sorted(fov_by_radius.items()):
                    avg = info["total_ms"] / info["count"]
                    print(f"    r={r}: {info['count']} calls, {info['total_ms']:.1f}ms total, {avg:.2f}ms avg")

        # Non-FOV overhead (geometry + filtering + model_copy)
        non_fov_ms = total_cs_ms - total_fov_ms
        print(f"\n  Non-FOV overhead: {non_fov_ms:.1f}ms "
              f"({non_fov_ms / len(self.cs_calls):.3f}ms avg per call)")


# ──────────────────────────────────────────────────────────────────────
# Main Test
# ──────────────────────────────────────────────────────────────────────

def run_profiled(hero: Entity) -> None:
    """Run get_available_actions with AoE profiling and print report."""
    with AoEProfiler() as profiler:
        start = time.perf_counter()
        result = get_available_actions(hero)
        elapsed = (time.perf_counter() - start) * 1000
    print(f"\n  Profiled run: {elapsed:.1f}ms")
    profiler.print_report()
    return result


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
    run_profiled(hero)

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
    run_profiled(hero)

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
    run_profiled(hero)

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
