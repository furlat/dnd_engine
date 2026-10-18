"""The schema-16 bodies golden vectors fold to their expected client bodies and items (plan §3.3-§3.5).

Each file of `sdk/protocol/fold-vectors/bodies/` is a seat's audience and a sequence of received records with the
bodies and items expected after each, written by hand (`devtools/fold_vectors_bodies.py`). Godot folds the same
files. Expected entries name the bodies and items they check.
"""

from dataclasses import replace
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter

from devtools.fold_vectors_bodies import DIRECTORY, documents
from dnd.core.cells import mask_from_positions
from dnd.player.audience import PlayerAudience
from dnd.player.facts import (ActorChangeFact, BodyRecord, PlayerActor, PlayerItem, PlayerState,
    PlayerWorld, SpatialFact)
from dnd.player.reduction import (apply_actor_change_fact, apply_record_fact, clear_unseen_positions, copy_target,
    enter_body)
from dnd.types.cells import EMPTY_VALUES
from dnd.types.senses import PerceivedContact, SensesSnapshot

BODY, CHANGE, SPATIAL = TypeAdapter(BodyRecord), TypeAdapter(ActorChangeFact), TypeAdapter(SpatialFact)
VECTORS = sorted(DIRECTORY.glob("*.json"))


def body_view(actor: PlayerActor) -> dict:
    """A held body in the vectors' expected shape."""
    loadout = actor.visual_loadout
    return {"name": actor.name, "hp": [actor.normal_hp, actor.maximum_hp, actor.temporary_hp],
            "grant": str(actor.temporary_hp_grant.instance_uuid) if actor.temporary_hp_grant is not None else None,
            "armor_class": actor.armor_class, "life": actor.life_state.value, "present": actor.present,
            "position": list(actor.last_visual_position) if actor.last_visual_position is not None else None,
            "conditions": [[str(row.condition_uuid), row.name, row.state.duration.remaining_rounds
                            if row.state is not None and row.state.duration is not None else None]
                           for row in actor.conditions],
            "weapon_set": loadout.active_weapon_set.value,
            "layers": [[row.slot, str(row.item_uuid), row.is_lit] for row in loadout.layers],
            "inventory": [str(item) for item in actor.controlled_items] if actor.controlled_items is not None else None,
            "size": actor.resolved_size.value if actor.resolved_size is not None else None,
            "disposition": actor.spatial_disposition.value}


def item_view(item: PlayerItem) -> dict:
    """A held item in the vectors' expected shape."""
    state = item.state
    return {"item_id": item.look.item_id, "profile": item.profile is not None,
            "state": {"charges": state.charges, "stack_count": state.stack_count, "is_lit": state.is_lit}
                if state is not None else None,
            "effects": [[str(row.effect_uuid), row.duration.remaining_rounds if row.duration is not None else None]
                        for row in item.effects]}


def _seen(state: PlayerState, step: dict) -> None:
    """The composed view after a sensory fold: its cells and contacts; a visual contact places its body."""
    contacts = {UUID(identity): PerceivedContact(position=tuple(row["position"]), visual=row["visual"])
                for identity, row in step["contacts"].items()}
    visible = mask_from_positions(tuple(tuple(position) for position in step["visible"]))
    state.senses = SensesSnapshot(position=(0, 0), visible=visible, seen=visible, entities=contacts, objects={},
        effective_light_levels=EMPTY_VALUES, paths_dirty=False, passive_perception=10, sense_modes_key=(),
        sense_modes=(), visual_access=1)
    clear_unseen_positions(state)
    for identity, contact in contacts.items():
        actor = state.actors.get(identity)
        if contact.visual and actor is not None and actor.present:
            state.actors[identity] = replace(actor, last_visual_position=contact.position)


def _fold(state: PlayerState, step: dict) -> PlayerState:
    result = copy_target(state)
    if "body" in step:
        enter_body(result, BODY.validate_python(step["body"]))
    elif "change" in step:
        apply_actor_change_fact(result, CHANGE.validate_python(step["change"]))
    elif "spatial" in step:
        apply_record_fact(result, SPATIAL.validate_python(step["spatial"]))
    else:
        _seen(result, step["seen"])
    return result


def _seat(document: dict) -> PlayerState:
    observers = tuple(UUID(identity) for identity in document["observers"])
    return PlayerState(generation=uuid4(), observer_uuid=observers[0],
        world=PlayerWorld(battlefield_id="vectors", battlefield_name="Vectors", bounds=(0, 0, 15, 15), width=16,
                          height=16),
        audience=PlayerAudience(observers=observers, controlled=tuple(UUID(row) for row in document["controlled"])))


def test_the_vector_files_are_their_written_source():
    assert {path.name: path.read_text() for path in VECTORS} == documents()


@pytest.mark.parametrize("path", VECTORS, ids=lambda path: path.stem)
def test_the_reference_fold_reaches_each_expected_state(path: Path):
    document = json.loads(path.read_text())
    state = _seat(document)
    for index, step in enumerate(document["steps"]):
        state = _fold(state, step)
        expected = step["expected"]
        held = {"actors": {identity: body_view(state.actors[UUID(identity)]) for identity in expected["actors"]},
                "items": {identity: item_view(state.items[UUID(identity)]) for identity in expected["items"]}}
        assert held == expected, f"{path.stem} step {index}"
