"""Recorded wall contacts survive replay without disclosing unseen origins."""

import pytest

from dnd.conditions import Blinded
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, EventQueue, TakeDamageEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.walls import WallOfFire, WallOfFireZone
from dnd.player.event_record import decode_event, encode_event
from dnd.player.facts import DamageFact
from dnd.player.recorded import project_sequence
from dnd.player.reduction import decode_player_sequence, encode_player_sequence
from dnd.player.capture import capture_interval, capture_lineage
from dnd.player.recorded import RecordedSequence
from tests.manual.spell_regression_support import create_spell_regression_actor


@pytest.mark.parametrize("blinded", (False, True))
def test_saved_heat_damage_keeps_only_currently_witnessed_wall_source(blinded):
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    try:
        caster = create_spell_regression_actor("Caster", (1, 1), "heroes", spell_slots={4: 1})
        target = create_spell_regression_actor("Target", (7, 6), "enemies")
        Entity.update_all_entities_senses(max_distance=120)
        with fixed_dice_faces(*([4] * 200)):
            cast = WallOfFire(source_entity_uuid=caster.uuid, end_position=(5, 5),
                extra_target_positions=[(9, 5)]).apply()
        assert cast is not None and not cast.canceled
        wall = next(row for row in get_map().get_spatial_conditions() if isinstance(row, WallOfFireZone))
        Entity.update_all_entities_senses(max_distance=120)
        assert wall.uuid in target.senses.spatial_effects
        # Capture a known wall, then let real sensory changes revoke its sight.
        if blinded:
            target.add_condition(Blinded(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
            Entity.update_all_entities_senses(max_distance=120)
        initial = capture_interval(name="Known wall", start_cursor=0, end_cursor=EventQueue.event_cursor(),
            observer_uuid=target.uuid, battlefield_id=battlefield)
        with fixed_dice_faces(*([4] * 100)):
            turn = target.on_turn_end()
        sequence = RecordedSequence(initialization=initial, lineages=(capture_lineage(turn, observer_uuid=target.uuid),))
        payload = sequence.model_dump_json()
    finally:
        reset_engine_runtime()
    recorded = RecordedSequence.model_validate_json(payload, context=PASSIVE_EVENT_REPLAY)
    _, lineages = decode_player_sequence(encode_player_sequence(project_sequence(recorded)))
    damages = [node.fact for lineage in lineages for node in lineage.events
               if isinstance(node.fact, DamageFact) and node.fact.stage == "applied"]
    assert len(damages) == 1 and damages[0].applied_damage == 20
    source = damages[0].spatial_source
    if blinded:
        assert source is None, "Damage must not reveal a currently unseen wall"
    else:
        assert source is not None and source.spatial_effect_uuid == wall.uuid
        assert source.position == (7, 5) and source.target_position == (7, 6)
        assert source.exposure == "radiated_heat"
    # Old native-v2 damage records remain readable without inventing contacts.
    for event in recorded.lineages[0].events:
        if isinstance(event, (DamageAppliedEvent, TakeDamageEvent)):
            old = encode_event(event)
            old.pop("spatial_source")
            assert decode_event(old).spatial_source is None
    assert EventQueue.event_cursor() == 0
