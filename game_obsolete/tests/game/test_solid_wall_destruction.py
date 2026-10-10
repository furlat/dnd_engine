"""Native wall replay retains its geometry and finite authored debris for clients."""

import pytest

from dnd.content.items.environment_item_builders import SOLID_WALL_MATERIALS
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity
from dnd.player.facts import ObjectDamageFact, ObjectDestroyedFact
from dnd.player.recorded import RecordedSequence, project_sequence
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from dnd.types.materials import Material
from dnd.types.world import CardinalDirection
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.environment_art import load_environment_art
from tests.game.solid_wall_scenarios import solid_wall_history


WALL_CASES = (("environment.directional_wall", Material.STONE),
              ("environment.directional_wall", Material.WOOD), *SOLID_WALL_MATERIALS.items())


@pytest.mark.parametrize("item_id,material", WALL_CASES)
def test_saved_attacks_and_passage_retain_native_clearance_and_authored_debris(item_id, material):
    history = solid_wall_history(item_id, material=material, raised=True,
        corner=item_id == "environment.directional_wall")
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    for role, native in history.views.items():
        saved = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        state, roots = decode_player_sequence(encode_player_sequence(project_sequence(saved)))
        wall = next(obj for obj in state.objects.values()
            if obj.item.item_id == item_id and obj.placement.boundary_direction is CardinalDirection.EAST)
        damages, destructions = [], []
        for root in roots:
            damages.extend(node.fact for node in root.events if isinstance(node.fact, ObjectDamageFact)
                and node.fact.object_uuid == wall.item.item_uuid)
            destructions.extend(node.fact for node in root.events if isinstance(node.fact, ObjectDestroyedFact)
                and node.fact.object_uuid == wall.item.item_uuid)
            if any(isinstance(node.fact, ObjectDestroyedFact) for node in root.events):
                group = bind_choreography(state, root, load_animation_data())
                assert not group.gaps
                transition, = (change for change in group.world_transitions if change.destruction is not None
                    and change.identity == wall.item.item_uuid)
                assert transition.destruction.bank_id is not None
                bank = load_environment_art().banks[transition.destruction.bank_id]
                assert bank.clear_at_end and bank.duration_ms == 1300 and bank.frame_count == 16
                assert transition.destruction.position == wall.placement.position
                assert transition.destruction.elevation_steps == wall.placement.base_height_steps
                assert group.complete_ms >= transition.start_ms + bank.duration_ms
                assert set(bank.frames_by_pose) == set("eswn")
                assert len({bank.frames_by_pose[pose] for pose in "eswn"}) == 1
            state = reduce_lineage(state, root)
        assert len(damages) >= 2 and len(destructions) == 1
        remnant = state.objects[wall.item.item_uuid]
        assert remnant.item.integrity is ItemIntegrity.DESTROYED
        assert remnant.placement.position == (5, 4) and remnant.placement.base_height_steps == 2
        assert remnant.item.boundary_structure.blocked_channels == ()
        if item_id == "environment.directional_wall":
            survivor = next(obj for obj in state.objects.values()
                if obj.placement.boundary_direction is CardinalDirection.NORTH)
            assert survivor.item.integrity is ItemIntegrity.INTACT
            assert survivor.item.boundary_structure.blocked_channels
        assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


def test_late_snapshot_keeps_clear_boundary_without_replaying_debris():
    history = solid_wall_history(late_snapshot=True)
    saved = RecordedSequence.model_validate_json(history.views["attacker"].model_dump_json(),
        context=PASSIVE_EVENT_REPLAY)
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(saved)))
    assert not roots
    remnant = next(obj for obj in state.objects.values() if obj.item.item_id == "environment.directional_wall")
    assert remnant.item.integrity is ItemIntegrity.DESTROYED
    assert remnant.item.boundary_structure.blocked_channels == ()
