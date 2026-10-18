"""Profile native finite-resource commit independently of unrelated history size."""

import cProfile
import json
from pathlib import Path
import platform
import sys
from uuid import uuid4

from dnd.actions_functional import setup_standard_actions
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.equipment_types import BodyPart
from dnd.core.events import Event, EventPhase, EventType
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


def sample(unrelated_events: int) -> dict:
    reset_engine_runtime(grid_size=(8, 8))
    game = Game()
    try:
        owner = Entity.create(uuid4(), "Resource owner")
        owner.compose_entity()
        game.deploy_entity(owner, (3, 3))
        setup_standard_actions(owner)
        pack = build_authored_item("gear.wayfarer_pack", owner.uuid)
        assert owner.loot_item(pack) and owner.equip_item(pack.uuid, BodyPart.BACKPACK)
        parent = Event(source_entity_uuid=owner.uuid, event_type=EventType.BASE_ACTION)
        prepared = pack.prepare_charge_consumption(1, owner.uuid, parent)
        for _ in range(unrelated_events):
            Event(source_entity_uuid=owner.uuid, event_type=EventType.BASE_ACTION,
                phase=EventPhase.COMPLETION)
        profile = cProfile.Profile()
        result = profile.runcall(pack.commit_prepared_charge, prepared)
        assert result.phase is EventPhase.COMPLETION and pack.charges == 0
        iterator_resumes = sum(row.callcount for row in profile.getstats()
            if not isinstance(row.code, str) and row.code.co_name == "iter_events_since")
        return {"case": "finite_item_commit", "unrelated_events_after_preparation": unrelated_events,
            "event_tail_iterator_resumes": iterator_resumes, "committed": True, "charges_after": pack.charges}
    finally:
        game.close()
        reset_engine_runtime()


def main() -> None:
    print(json.dumps({"source_root": str(Path.cwd()), "python": sys.executable,
        "python_version": platform.python_version(), "platform": platform.platform(),
        "scope": "profiled native commit only; setup and unrelated event creation excluded"}))
    for count in (0, 1000, 10000):
        print(json.dumps(sample(count)))


if __name__ == "__main__":
    main()
