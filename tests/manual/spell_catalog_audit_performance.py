"""Manual native diagnostics for the October 2026 spell catalog audit.

Run from the repository root:
    uv run --no-sync python -m tests.manual.spell_catalog_audit_performance

This is a profiler benchmark, not a gameplay test or a timing gate. It records
work after setup for remote item changes, unrelated turn-end
dispatch, and an unchanged concentration publication after synthetic history.
No engine methods are replaced. Optional .prof files allow deeper inspection.
Counts identify the current implementation; they are deliberately not asserted.
The Hold Person load admits real native conditions directly, so it measures
dispatch routing rather than claiming that one caster can hold forty targets.
"""

import argparse
import cProfile
import json
import platform
import pstats
import sys
from collections import Counter
from collections.abc import Callable
from functools import partial
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from dnd.actions import SpellAction
from dnd.blocks.base_item import BaseItem
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.content.runtime import HandlerDispatchEvidence
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemLocation
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import AntilifeShell
from dnd.spells.enchantment import HoldPersonEffect
from dnd.spells.transmutation import Goodberry, Haste
from tests.manual.spell_regression_support import create_spell_regression_actor

PROFILE_FUNCTIONS = frozenset({
    "get_all_items", "get_all_entities", "_occupants_at",
    "to_item_presentation_state",
    "allows_contribution_at", "_area_shape",
    "publish_owner_state", "get_events_by_target", "repeat_save_processor",
})


def measure(
    case: str,
    operation: Callable[[], object],
    profile_directory: Path | None,
) -> dict:
    """Observe one native operation without changing its handler behavior."""
    dispatches: Counter = Counter()

    def observe(evidence: HandlerDispatchEvidence) -> None:
        # Native handler names may contain an encounter-local recipient UUID.
        name = evidence.handler_name.split(" (", 1)[0]
        dispatches[(name, evidence.event_type, evidence.event_phase,
                    evidence.outcome.value)] += 1

    profiler = cProfile.Profile()
    EventQueue.add_on_handler_dispatch_callback(observe)
    started = perf_counter()
    try:
        profiler.enable()
        operation()
    finally:
        profiler.disable()
        elapsed = perf_counter() - started
        EventQueue.remove_on_handler_dispatch_callback(observe)
    if profile_directory is not None:
        profiler.dump_stats(profile_directory / f"{case}.prof")
    counters: Counter = Counter()
    for (_filename, _line, function), (_primitive, calls, _own, _total, _callers) in pstats.Stats(profiler).stats.items():
        if function in PROFILE_FUNCTIONS or function == "<built-in method builtins.isinstance>":
            counters[function] += calls
    return {
        "case": case,
        "instrumented_operation_ms": round(elapsed * 1000, 3),
        "profile_calls": dict(sorted(counters.items())),
        "handler_dispatches": [
            {"handler": key[0], "event_type": key[1], "phase": key[2],
             "outcome": key[3], "count": count}
            for key, count in sorted(dispatches.items())
        ],
    }


def cast(spell: type[SpellAction], caster: Entity, target: Entity | None = None) -> None:
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result = spell(source_entity_uuid=caster.uuid,
                   target_entity_uuid=(target or caster).uuid).apply()
    assert result is not None and not result.canceled, result


def ordinary_item_samples(profile_directory: Path | None) -> list[dict]:
    samples = []
    for item_count in (1, 25, 100):
        reset_engine_runtime(grid_size=(40, 10))
        game = Game()
        try:
            remote = create_spell_regression_actor("Item owner", (30, 2), "heroes")
            items = [build_authored_item("weapon.dagger", remote.uuid) for _ in range(item_count)]
            for item in items:
                assert remote.inventory.add_item(item)
            assert remote.drop_item(items[-1].uuid, (30, 3)) is items[-1]
            sample = measure(f"ordinary_remote_object_move_{item_count}",
                partial(get_map().move_object, items[-1].uuid, (31, 3)), profile_directory)
            assert get_map().get_object_placement(items[-1].uuid).position == (31, 3)
            sample["registered_items"] = len(BaseItem.get_all_items())
            samples.append(sample)
        finally:
            game.close()
    return samples


def unrelated_turn_samples(profile_directory: Path | None) -> list[dict]:
    samples = []
    for condition_count in (1, 10, 40):
        reset_engine_runtime(grid_size=(18, 8))
        game = Game()
        try:
            unrelated = create_spell_regression_actor("Unrelated actor", (2, 2), "heroes")
            for _ in range(condition_count):
                held = Entity.create(uuid4(), "Held target", config=EntityConfig(faction="foes"))
                held.compose_entity()
                result = held.add_condition(HoldPersonEffect(source_entity_uuid=unrelated.uuid,
                    target_entity_uuid=held.uuid, caster_uuid=unrelated.uuid, spell_dc=15))
                assert not result.canceled
            sample = measure(f"unrelated_turn_{condition_count}", unrelated.on_turn_end, profile_directory)
            sample["active_held_recipients"] = condition_count
            samples.append(sample)
        finally:
            game.close()
    return samples


def ordinary_creation_samples(profile_directory: Path | None) -> list[dict]:
    samples = []
    for batches in (1, 4):
        reset_engine_runtime(grid_size=(40, 10))
        game = Game()
        try:
            caster = create_spell_regression_actor("Berry caster", (30, 2), "heroes", spell_slots={1: batches})
            for _ in range(batches):
                cast(Goodberry, caster)
            sample = measure(f"ordinary_berry_move_{batches * 4}",
                partial(Entity.commit_position_transfers, ((caster, (31, 2), None),)), profile_directory)
            assert caster.position == (31, 2)
            sample["created_berries"] = batches * 4
            samples.append(sample)
        finally:
            game.close()
    return samples


def concentration_samples(profile_directory: Path | None) -> list[dict]:
    samples = []
    for history_count in (0, 1000, 10000):
        reset_engine_runtime(grid_size=(18, 8))
        game = Game()
        try:
            caster = create_spell_regression_actor("Caster", (2, 2), "heroes", spell_slots={3: 1})
            ally = create_spell_regression_actor("Ally", (3, 2), "heroes")
            cast(Haste, caster, ally)
            # Native event storage provides unrelated load, not extra turns or
            # spell effects. No observer mutates this synthetic completed fact.
            for _ in range(history_count):
                Event(event_type=EventType.BASE_ACTION, source_entity_uuid=caster.uuid,
                      target_entity_uuid=caster.uuid, phase=EventPhase.COMPLETION)
            concentration = caster.active_conditions["Concentrating"]
            sample = measure(f"unchanged_concentration_{history_count}",
                             partial(concentration.publish_owner_state, None), profile_directory)
            sample["synthetic_unrelated_target_events"] = history_count
            sample["actor_target_history_length"] = len(EventQueue.get_events_by_target(caster.uuid))
            samples.append(sample)
        finally:
            game.close()
    return samples


def antilife_samples(profile_directory: Path | None) -> list[dict]:
    samples = []
    for remote_count in (1, 25, 100):
        reset_engine_runtime(grid_size=(45, 18))
        game = Game()
        try:
            caster = create_spell_regression_actor("Shell caster", (2, 2), "heroes", spell_slots={5: 1})
            for index in range(remote_count):
                create_spell_regression_actor("Remote actor", (20 + index % 20, 8 + index // 20), "foes")
            cast(AntilifeShell, caster)
            sample = measure(f"antilife_one_cell_move_{remote_count}",
                partial(Entity.commit_position_transfers, ((caster, (3, 2), None),)), profile_directory)
            sample["remote_actors"] = remote_count
            sample["registered_entities"] = len(Entity.get_all_entities())
            samples.append(sample)
            assert caster.position == (3, 2) and "Concentrating" in caster.active_conditions
        finally:
            game.close()
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", "items", "creations", "unrelated-turn", "concentration", "antilife"), default="all")
    parser.add_argument("--profile-directory", type=Path)
    args = parser.parse_args()
    if args.profile_directory is not None:
        args.profile_directory.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"source_root": str(Path(__file__).resolve().parents[2]),
        "python": sys.executable, "python_version": platform.python_version(),
        "platform": platform.platform(), "timing_scope": "profiled operation only; excludes imports and setup"}), flush=True)
    try:
        for name, run in (("items", ordinary_item_samples), ("creations", ordinary_creation_samples),
                          ("unrelated-turn", unrelated_turn_samples),
                          ("concentration", concentration_samples), ("antilife", antilife_samples)):
            if args.case in ("all", name):
                for sample in run(args.profile_directory):
                    print(json.dumps(sample), flush=True)
    finally:
        reset_engine_runtime(grid_size=(18, 8))


if __name__ == "__main__":
    main()
