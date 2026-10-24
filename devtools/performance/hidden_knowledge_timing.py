"""Hidden-knowledge timing: hidden traps and packed rooms, base against new, interleaved under load.

Each sample runs in its own process, so one copy of this script times two checkouts:

    PYTHONPATH=. .venv/bin/python devtools/performance/hidden_knowledge_timing.py \
        --base .runtime/hidden-knowledge-baseline --rounds 5

Without --base it times only this checkout. Rows (milliseconds unless noted):

- traps: N hidden traps (half spike, half finite, DC 11-18) on a 40x40 map with six observers
  (passive Perception 9-15), all in one faction or each in its own. First full refresh (every
  notice happens here), a second (routes the notices invalidated are rebuilt) and a third (steady),
  a 4-cell move, an action listing, a search, one firing, and the remembered pairs.
- dense_search: a searcher ringed by 24 hidden traps it cannot notice, searching with a high roll.
- room: a Fireball through 64 packed cells of props, containers, locks and needle traps, the
  looting round before it and the senses refresh after it.
"""
import argparse
import gc
import json
import os
import random
import statistics
import subprocess
import sys
import time
from uuid import uuid4

from dnd.actions import Move
from dnd.actions_functional import execute_available_action, setup_standard_actions
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_storage_chest
from dnd.content.items.world_prop_builders import build_display_prop, build_searchable_prop
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.entity import Entity
from dnd.items.container_traps import install_container_trap
from dnd.items.environment_interactables import StorageChest
from dnd.items.locks import install_lock
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.spatial.mechanisms import AreaGeometry, materialize_finite_trap
from dnd.spells.evocation import Fireball
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_sample(rows: list[str], counts: list[int], factions: str, seed: int) -> dict:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())

    def ms(fn) -> float:
        gc.collect()
        start = time.perf_counter()
        fn()
        return (time.perf_counter() - start) * 1000

    def search(entity) -> None:
        entity.action_economy.reset_all_costs()
        for info in entity.get_available_actions().all_actions:
            if info.template_name.split("__")[0] in ("Search for Traps", "Search") and info.valid_targets:
                execute_available_action(entity, info, info.valid_targets[0])
                return
        raise AssertionError("no area search row")

    out: dict = {}
    size = 40
    spots = (((2, 20), 8), ((37, 20), 12), ((20, 2), 14), ((20, 37), 16), ((10, 10), 18), ((30, 30), 20))
    path = [(2, 20), (3, 20), (4, 20), (5, 20), (6, 20)]
    free = {position for position, _ in spots} | set(path) | {(x, 20) for x in range(size)}

    if "traps" in rows:
        for count in counts:
            reset_spell_regression_arena(size, size)
            rng = random.Random(seed)
            cells = [(x, y) for x in range(size) for y in range(size) if (x, y) not in free]
            rng.shuffle(cells)
            finite = []
            for index, cell in enumerate(cells[:count]):
                if index % 2:
                    materialize_spike_trap_condition({cell}, stealth_dc=rng.randint(11, 18))
                else:
                    finite.append(materialize_finite_trap(cell, geometry=AreaGeometry(), stealth_dc=rng.randint(11, 18),
                                                          rearm_after_activation=False))
            observers = []
            for index, (position, wisdom) in enumerate(spots):
                faction = "heroes" if factions == "one" else f"faction{index}"
                entity = create_spell_regression_actor(f"O{index}", position, faction, wisdom=wisdom)
                setup_standard_actions(entity)
                observers.append(entity)
            row = {"refresh_first": ms(lambda: Entity.update_all_entities_senses(max_distance=200)),
                   "refresh_again": ms(lambda: Entity.update_all_entities_senses(max_distance=200)),
                   "refresh_steady": ms(lambda: Entity.update_all_entities_senses(max_distance=200))}
            mover = observers[0]
            mover.action_economy.reset_all_costs()
            row["move_4"] = ms(lambda: Move(source_entity_uuid=mover.uuid, path=list(path), end_position=path[-1]).apply())
            row["listing"] = ms(lambda: observers[4].get_available_actions())
            with fixed_dice_faces(*([10] * 4)):
                row["search"] = ms(lambda: search(observers[4]))
            if finite:
                cause = EventQueue.publish_declaration(Event(name="pulse", source_entity_uuid=finite[0].uuid,
                    event_type=EventType.BASE_ACTION, use_register=False))
                for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
                    cause = cause.phase_to(phase)
                row["fire_one"] = ms(lambda: finite[0].fire(parent_event=cause))
            row["remembered"] = sum(len(o.senses.spatial_effects) for o in observers)
            out[f"traps/{factions}/{count}"] = row

    if "dense_search" in rows:
        reset_spell_regression_arena(20, 20)
        ring = [(10 + dx, 10 + dy) for dx in range(-2, 3) for dy in range(-2, 3) if (dx, dy) != (0, 0)]
        for cell in ring:
            materialize_spike_trap_condition({cell}, stealth_dc=15)
        searcher = create_spell_regression_actor("Searcher", (10, 10), "heroes", wisdom=8)
        setup_standard_actions(searcher)
        Entity.update_all_entities_senses(max_distance=60)
        with fixed_dice_faces(*([20] * 4)):
            out["dense_search"] = {"search": ms(lambda: search(searcher))}

    if "room" in rows:
        cells = [(x, y) for x in range(6, 14) for y in range(6, 14)]
        reset_spell_regression_arena(20, 20)
        for index, cell in enumerate(cells):
            kind = index % 6
            if kind == 0:
                rack = build_display_prop("environment.furniture.wall_rack", look="swords", capacity=2)
                rack.place_on_grid(cell)
                for _ in range(2):
                    rack.chest_inventory.add_item(build_authored_item("weapon.longsword", rack.uuid))
            elif kind == 1:
                desk = build_searchable_prop("environment.furniture.writing_desk")
                desk.place_on_grid(cell)
                desk.chest_inventory.add_item(build_authored_item("tool.key", desk.uuid))
            elif kind == 2:
                chest = build_authored_item("environment.container.footlocker", uuid4())
                chest.place_on_grid(cell)
                chest.chest_inventory.add_item(build_authored_item("tool.key", chest.uuid))
                install_lock(chest)
            elif kind == 3:
                chest = build_authored_item("environment.container.iron_bound_chest", uuid4())
                assert isinstance(chest, StorageChest)
                chest.place_on_grid(cell)
                install_container_trap(chest)
            elif kind == 4:
                build_authored_item("environment.furniture.couch" if cell[0] < 13 else "environment.furniture.padded_chair",
                                    uuid4()).place_on_grid(cell)
            else:
                build_authored_item("environment.furniture.cabinet", uuid4()).place_on_grid(cell)
        chest = build_storage_chest("Chest", include_loot_all_action=True)
        chest.place_on_grid((3, 3))
        caster = create_spell_regression_actor("Caster", (1, 1), "heroes", spell_slots={5: 1})
        looters = [create_spell_regression_actor(f"L{i}", position, "heroes")
                   for i, position in enumerate(((5, 6), (5, 9), (14, 7), (14, 12)))]
        Entity.update_all_entities_senses(max_distance=120)

        def looting() -> None:
            for looter in looters:
                looter.update_entity_senses()
                for info in looter.get_available_actions().all_actions:
                    if info.template_name.split("__")[0] == "Loot All" and info.valid_targets:
                        looter.action_economy.reset_all_costs()
                        execute_available_action(looter, info, info.valid_targets[0])
        row = {"looting": ms(looting)}
        caster.action_economy.reset_all_costs()
        with fixed_dice_faces(*([4] * 400)):
            row["fireball"] = ms(lambda: Fireball(source_entity_uuid=caster.uuid, end_position=(10, 10),
                                                  cast_at_level=5).apply())
        row["senses_after"] = ms(lambda: Entity.update_all_entities_senses(max_distance=120))
        out["room"] = row
    return out


def sample_in_process(root: str, args: argparse.Namespace, factions: str, seed: int) -> dict:
    command = [sys.executable, os.path.abspath(__file__), "--sample", "--rows", args.rows,
               "--counts", args.counts, "--factions", factions, "--seed", str(seed)]
    env = dict(os.environ, PYTHONPATH=root)
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"sample failed in {root}:\n{result.stderr[-3000:]}")
    return json.loads(result.stdout.strip().splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", default="traps,dense_search,room")
    parser.add_argument("--counts", default="0,10,50,100,200,400")
    parser.add_argument("--factions", default="one,six", help="traps rows: one shared faction, six factions, or both")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--base", default=None, help="a second checkout to time, interleaved with this one")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sample", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    rows, counts = args.rows.split(","), [int(value) for value in args.counts.split(",")]
    if args.sample:
        print(json.dumps(run_sample(rows, counts, args.factions, args.seed)))
        return
    roots = {"new": ROOT} | ({"base": os.path.abspath(args.base)} if args.base else {})
    samples: dict[str, list[dict]] = {name: [] for name in roots}
    for round_index in range(args.rounds):
        for name, root in roots.items():
            merged: dict = {}
            for factions in args.factions.split(","):
                merged |= sample_in_process(root, args, factions, round_index)
            samples[name].append(merged)
    print(f"load {os.getloadavg()[0]:.1f}, {args.rounds} rounds, medians")
    for key in samples["new"][0]:
        for name in roots:
            data = [sample[key] for sample in samples[name] if key in sample]
            if not data:
                continue
            summary = {field: statistics.median(row.get(field, 0.0) for row in data) for field in data[0]}
            print(f"{key:22s} {name:4s} " + ", ".join(
                f"{field} {value:.0f}" if field == "remembered" else f"{field} {value:.1f}"
                for field, value in summary.items()))


if __name__ == "__main__":
    main()
