"""Hidden-object timing: N keys whose presence is hidden against N plain keys, interleaved under load.

    PYTHONPATH=. .venv/bin/python devtools/performance/hidden_objects_timing.py --rounds 5

Rows (milliseconds): a 40x40 map with six observers (passive Perception 9-15, all in one faction or each in its
own) and N keys on random cells, hidden (DC 11-18) or plain: a first full refresh (every notice happens here), a
second, a third, a 4-cell move and an action listing, and the objects the observers perceive.
"""
import argparse
import gc
import os
import random
import statistics
import time
from uuid import uuid4

from dnd.actions import Move
from dnd.actions_functional import setup_standard_actions
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.concealment_types import ConcealedAspect
from dnd.entity import Entity
from dnd.items.concealment import install_concealment
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena

SIZE = 40
SPOTS = (((2, 20), 8), ((37, 20), 12), ((20, 2), 14), ((20, 37), 16), ((10, 10), 18), ((30, 30), 20))
PATH = [(2, 20), (3, 20), (4, 20), (5, 20), (6, 20)]
FREE = {position for position, _ in SPOTS} | set(PATH) | {(x, 20) for x in range(SIZE)}


def ms(fn) -> float:
    gc.collect()
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000


def sample(count: int, hidden: bool, factions: str, seed: int) -> dict[str, float]:
    reset_spell_regression_arena(SIZE, SIZE)
    rng = random.Random(seed)
    cells = [(x, y) for x in range(SIZE) for y in range(SIZE) if (x, y) not in FREE]
    rng.shuffle(cells)
    for cell in cells[:count]:
        key = build_authored_item("tool.key", uuid4())
        if hidden:
            install_concealment(key, ConcealedAspect.PRESENCE, rng.randint(11, 18))
        key.place_on_grid(cell)
    observers = []
    for index, (position, wisdom) in enumerate(SPOTS):
        entity = create_spell_regression_actor(f"O{index}", position, "heroes" if factions == "one" else f"faction{index}",
                                               wisdom=wisdom)
        setup_standard_actions(entity)
        observers.append(entity)
    row = {"refresh_first": ms(lambda: Entity.update_all_entities_senses(max_distance=200)),
           "refresh_again": ms(lambda: Entity.update_all_entities_senses(max_distance=200)),
           "refresh_steady": ms(lambda: Entity.update_all_entities_senses(max_distance=200))}
    mover = observers[0]
    mover.action_economy.reset_all_costs()
    row["move_4"] = ms(lambda: Move(source_entity_uuid=mover.uuid, path=list(PATH), end_position=PATH[-1]).apply())
    row["listing"] = ms(lambda: observers[4].get_available_actions())
    row["perceived"] = sum(len(observer.senses.objects) for observer in observers)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--counts", default="0,10,50,100,200")
    parser.add_argument("--factions", default="one,six")
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    counts, factions = [int(value) for value in args.counts.split(",")], args.factions.split(",")
    rows: dict[tuple[str, int, bool], list[dict[str, float]]] = {}
    for round_index in range(args.rounds):
        for mode in factions:
            for count in counts:
                for hidden in (False, True):
                    rows.setdefault((mode, count, hidden), []).append(sample(count, hidden, mode, round_index))
    print(f"load {os.getloadavg()[0]:.1f}, {args.rounds} rounds, medians")
    for (mode, count, hidden), data in rows.items():
        summary = {field: statistics.median(row[field] for row in data) for field in data[0]}
        print(f"objects/{mode}/{count:<4d} {'hidden' if hidden else 'plain ':6s} " + ", ".join(
            f"{field} {value:.0f}" if field == "perceived" else f"{field} {value:.1f}" for field, value in summary.items()))


if __name__ == "__main__":
    main()
