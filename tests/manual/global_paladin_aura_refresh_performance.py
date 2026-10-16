"""Measure GA-P1 native aura refresh work, outside the default pytest lane.

Run: python -m tests.manual.global_paladin_aura_refresh_performance
Emits JSONL. cProfile observes existing
native operations without monkeypatching dispatch or asserting private calls.
These are work counts, not a claim about whole-engine elapsed-time improvements.
"""

import cProfile
import json
import platform
import sys
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from dnd.conditions import Poisoned
from dnd.content.characters.builds import create_character
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.character_progression import CharacterClass
from tests.progression.prepared_class_support import prepared_build


def main():
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    print(json.dumps({
        "kind": "environment", "python": sys.version.split()[0],
        "platform": platform.platform(), "source": str(Path.cwd()),
    }), flush=True)
    for count in (1, 25, 100):
        reset_engine_runtime(grid_size=(150, 12))
        game = Game()
        try:
            actor = create_character(replace(prepared_build(CharacterClass.PALADIN, 10), faction="heroes"))
            game.deploy_entity(actor, (2, 2))
            remote = []
            for index in range(count):
                other = Entity.create(uuid4(), f"Remote {index}")
                other.compose_entity()
                game.deploy_entity(other, (30 + index, 2))
                remote.append(other)
            operations = [
                ("owner_membership", lambda actor=actor: actor.add_condition(Poisoned(
                    source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid,
                ))),
                ("remote_faction", lambda remote_actor=remote[0]: remote_actor.set_faction("foes")),
                ("owner_move", lambda actor=actor: Entity.update_entity_position(actor, (3, 2))),
                ("remote_move_control", lambda remote_actor=remote[0]: Entity.update_entity_position(remote_actor, (30, 3))),
                ("owner_turn_control", actor.on_turn_start),
                ("remote_turn_control", remote[0].on_turn_start),
            ]
            for label, operation in operations:
                profile = cProfile.Profile()
                profile.runcall(operation)
                counts = {
                    name: sum(
                        entry.callcount for entry in profile.getstats()
                        if not isinstance(entry.code, str) and entry.code.co_name == name
                    )
                    for name in ("get_all_entities", "remove_membership", "apply_membership", "_occupants_at")
                }
                print(json.dumps({"kind": "operation", "remote_actors": count,
                                  "operation": label, **counts}), flush=True)
            assert "Poisoned" in actor.active_conditions
            assert actor.position == (3, 2)
            assert remote[0].faction == "foes" and remote[0].position == (30, 3)
        finally:
            game.close()
            reset_engine_runtime()


if __name__ == "__main__":
    main()
