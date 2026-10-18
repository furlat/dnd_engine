"""The schema-16 sensory golden vectors fold to their expected client states (plan §3.1, §3.2).

Each file of `sdk/protocol/fold-vectors/sensory/` is a seat's audience and a sequence of received groups with the
client state expected after each, written by hand (`devtools/fold_vectors_sensory.py`). Godot folds the same files.
"""

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter

from devtools.fold_vectors_sensory import DIRECTORY, documents
from dnd.core.cells import mask_positions, values_items
from dnd.player.audience import PlayerAudience
from dnd.player.facts import PlayerState, PlayerWorld
from dnd.player.reduction import composed_values, copy_target, fold_composed_sensory
from dnd.player.sensory_facts import SensoryFact, SensoryRows

ROWS, FACT = TypeAdapter(SensoryRows), TypeAdapter(SensoryFact)
VECTORS = sorted(DIRECTORY.glob("*.json"))


def _cells(cells) -> list[list[int]]:
    return [list(position) for position in sorted(cells)]


def client_sensory_view(state: PlayerState) -> dict:
    """What the client perceives now and remembers, in the vectors' expected shape."""
    senses = state.senses
    assert senses is not None
    return {
        "visible": _cells(mask_positions(senses.visible)),
        "seen": _cells(mask_positions(senses.seen)),
        "light": {f"{x},{y}": level for (x, y), level in values_items(senses.effective_light_levels)},
        "hazard": {f"{x},{y}": value for (x, y), value in values_items(senses.hazardous_cells) if value},
        "position": list(senses.position),
        "passive_perception": senses.passive_perception,
        "visual_access": senses.visual_access,
        "sense_modes": [[mode.sense_type.value, mode.range_feet] for mode in senses.sense_modes],
        "paths_dirty": senses.paths_dirty,
        "entities": {str(identity): {"position": list(contact.position), "visual": contact.visual,
                                     "members": state.entity_members[identity]}
                     for identity, contact in senses.entities.items()},
        "objects": {str(identity): {"position": list(contact.position), "visual": contact.visual,
                                    "members": state.object_contact_members[identity]}
                    for identity, contact in senses.objects.items()},
        "effects": {str(identity): {"name": effect.name, "positions": _cells(effect.positions),
                                    "volume": _cells(effect.visible_volume_positions),
                                    "apparent": effect.apparent_presence,
                                    "anchor_position": list(effect.anchor_position) if effect.anchor_position else None,
                                    "trap_state": effect.trap_state.value if effect.trap_state is not None else None,
                                    "members": state.effect_members[identity]}
                    for identity, effect in senses.spatial_effects.items()},
        "remembered": {str(identity): _cells(effect.positions) for identity, effect in state.remembered_effects.items()},
        "lights": {str(identity): {"position": list(source.position), "bright": source.bright_radius_feet,
                                   "dim": source.dim_radius_feet,
                                   "anchor_entity": str(source.anchor_entity_uuid)
                                       if source.anchor_entity_uuid is not None else None}
                   for identity, source in state.light_sources.items()},
    }


def _seat(observers: list[UUID]) -> PlayerState:
    return PlayerState(generation=uuid4(), observer_uuid=observers[0],
        world=PlayerWorld(battlefield_id="vectors", battlefield_name="Vectors", bounds=(0, 0, 15, 15), width=16,
                          height=16),
        audience=PlayerAudience(controlled=(), observers=tuple(observers)))


def _fold(state: PlayerState, step: dict) -> PlayerState:
    result = copy_target(state)
    fold_composed_sensory(result, FACT.validate_python(step["fact"]),
                          composed_values(ROWS.validate_python(step["sensory_rows"])))
    return result


def test_the_vector_files_are_their_written_source():
    assert {path.name: path.read_text() for path in VECTORS} == documents()


@pytest.mark.parametrize("path", VECTORS, ids=[path.stem for path in VECTORS])
def test_vector_folds_to_its_expected_states(path: Path):
    vector = json.loads(path.read_text())
    state = _seat([UUID(identity) for identity in vector["observers"]])
    for index, step in enumerate(vector["steps"]):
        state = _fold(state, step)
        assert client_sensory_view(state) == step["expected"], f"step {index}"


def test_a_seat_with_several_observers_must_name_each_rows_members():
    vector = json.loads((DIRECTORY / "v8_a_one_observer_seat_sends_no_member_columns.json").read_text())
    with pytest.raises(ValueError, match="names the members of each row"):
        _fold(_seat([uuid4(), uuid4()]), vector["steps"][0])


def test_a_change_to_a_record_the_seat_does_not_perceive_is_refused():
    vector = json.loads((DIRECTORY / "v4_an_apparent_effect_is_remembered_until_seen_without_it.json").read_text())
    state = _fold(_seat([UUID(identity) for identity in vector["observers"]]), vector["steps"][0])
    entering_again = {**vector["steps"][0]["fact"], "initial": False}
    with pytest.raises(ValueError, match="does not perceive"):
        _fold(state, {"fact": entering_again, "sensory_rows": vector["steps"][0]["sensory_rows"]})
    removed_twice = vector["steps"][3]
    state = _fold(_fold(state, vector["steps"][1]), vector["steps"][2])
    state = _fold(state, removed_twice)
    with pytest.raises(ValueError, match="one the seat perceives"):
        _fold(state, removed_twice)
