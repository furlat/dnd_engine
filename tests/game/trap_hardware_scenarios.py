"""Break an actual mechanism while its plate keeps a second one connected."""

import random

import pytest

from dnd.content.items.trap_hardware_builders import materialize_trap_hardware
from dnd.controller import HumanController
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, MechanismActivationEvent
from dnd.core.item_types import ItemIntegrity
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.mechanisms import TrapSave
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.types.controls import ActivationLink
from dnd.types.traps import TrapState
from game.player_facts import MechanismActivationFact, ObjectDamageFact, ObjectDestroyedFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, RecordedSequence, capture_history
from tests.game.door_destruction_scenarios import attack_object, review_actor, take_turn, walk


def trap_hardware_history(*, item_id: str = "environment.trap.swinging_blade.stone.workshop",
                          deployed: bool = False, late_snapshot: bool = False) -> CapturedHistory:
    """Two real attacks destroy hardware; subsequent real presses hit only its peer."""
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        hardware, mechanism = materialize_trap_hardware((5, 4), item_id=item_id,
            hit_points=12, avoidance=TrapSave(dc=12, retreat_on_success=False))
        peer_kind = "crusher" if ".swinging_blade." in item_id else "swinging_blade"
        peer_hardware, peer = materialize_trap_hardware((7, 4),
            item_id=f"environment.trap.{peer_kind}.stone.workshop", rearm_after_activation=True,
            avoidance=TrapSave(dc=12, retreat_on_success=False))
        plate = materialize_pressure_plate({(5, 4)}, (
            ActivationLink(target_condition_uuid=mechanism.uuid),
            ActivationLink(target_condition_uuid=peer.uuid),
        ))
        actors = {role: review_actor(game, role.title(), position)
                  for role, position in (("attacker", (4, 4)), ("witness", (7, 4)))}
        attacker, witness = actors["attacker"], actors["witness"]
        encounter = Encounter(name="Break one connected mechanism", source_entity_uuid=attacker.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(20, 1):
            encounter.start_encounter()
        encounter.start_turn()
        take_turn(encounter, attacker)
        Entity.update_all_entities_senses()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Two mechanisms and one plate", start_cursor=0, end_cursor=baseline,
            observer_uuid=attacker.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)

        if deployed:
            walk(attacker, (5, 4), dice=(1, 4, 1, 4))
            assert mechanism.trap_state is TrapState.ACTIVATED and plate.pressed
            assert attacker.get_hp() == 76 and witness.get_hp() == 76
            walk(attacker, (4, 4))
            assert not plate.pressed
        attack_object(attacker, hardware, 4)
        assert hardware.get_hp() == 8 and mechanism.is_active_spatial_condition()
        take_turn(encounter, attacker, fresh=True)
        attack_object(attacker, hardware, 8)
        assert hardware.get_hp() == 0 and hardware.get_position() == (5, 4)
        assert hardware.integrity is ItemIntegrity.DESTROYED
        assert not mechanism.is_active_spatial_condition()
        assert plate.is_active_spatial_condition() and peer.is_active_spatial_condition()
        after_break = EventQueue.event_cursor()
        hp = attacker.get_hp(), witness.get_hp()
        walk(attacker, (5, 4), dice=(1, 4))
        assert plate.pressed and attacker.get_hp() == hp[0] and witness.get_hp() == hp[1] - 4
        walk(attacker, (6, 4))  # The ordinary wreck has no invented collision.
        assert not plate.pressed
        walk(attacker, (5, 4), dice=(1, 4))
        assert plate.pressed and attacker.get_hp() == hp[0] and witness.get_hp() == hp[1] - 8
        assert peer_hardware.has_hp and peer.trap_state is TrapState.READY
        discharges = [event for _, event in EventQueue.iter_events_since(after_break)
            if isinstance(event, MechanismActivationEvent) and event.phase is EventPhase.COMPLETION and event.committed]
        assert [event.mechanism_uuid for event in discharges] == [peer.uuid, peer.uuid]
        if late_snapshot:
            baseline = EventQueue.event_cursor()
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["attacker"]
        if late_snapshot:
            before, _ = reduce_interval(None, primary.initialization)
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)


def check_saved_trap_hardware(history: CapturedHistory, *, item_id: str, deployed: bool) -> None:
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    for role, original in history.views.items():
        restored = RecordedSequence.model_validate_json(original.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        state, roots = decode_player_sequence(encode_player_sequence(project_sequence(restored)))
        original_object, = (obj for obj in state.objects.values()
                            if obj.item.item_id == item_id and obj.placement.position == (5, 4))
        identity = original_object.item.item_uuid
        assert state.senses is not None
        original_mechanism, = (uuid for uuid, effect in state.senses.spatial_effects.items()
                              if effect.anchor_item_uuid == identity)
        destructions = []
        damage_results = []
        after_break_activations = []
        destroyed = False
        for root in roots:
            for node in root.events:
                fact = node.fact
                if isinstance(fact, ObjectDamageFact) and fact.object_uuid == identity:
                    damage_results.append(fact.resulting_hp)
                if isinstance(fact, ObjectDestroyedFact) and fact.object_uuid == identity:
                    destructions.append(fact)
                    destroyed = True
                if isinstance(fact, MechanismActivationFact) and fact.committed and destroyed:
                    after_break_activations.append(fact)
            state = reduce_lineage(state, root)
        destruction, = destructions
        assert damage_results == [8, 0], role
        assert destruction.replacement_uuid is None
        wreck = state.objects[identity]
        assert wreck.item.integrity is ItemIntegrity.DESTROYED
        assert wreck.item.item_id == item_id
        assert wreck.placement.position == (5, 4) and wreck.item.boundary_structure is None
        assert wreck.item.remnant_state is not None
        assert wreck.item.remnant_state.mechanism_state is (TrapState.ACTIVATED if deployed else TrapState.READY)
        assert state.senses is not None and original_mechanism not in state.senses.spatial_effects
        assert len(after_break_activations) == 2
        assert all(fact.mechanism_uuid != original_mechanism for fact in after_break_activations)
        names = {actor.name: actor for actor in state.actors.values()}
        assert names["Attacker"].normal_hp == (76 if deployed else 80)
        assert names["Witness"].normal_hp == (68 if deployed else 72)
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


@pytest.mark.parametrize("item_id,deployed", (
    ("environment.trap.swinging_blade.stone.workshop", False),
    ("environment.trap.swinging_blade.wood.fortress", True),
    ("environment.trap.crusher.stone.brassbound", True),
    ("environment.trap.crusher.wood.workshop", False),
))
def test_broken_trap_replays_without_disabling_its_plate_or_surviving_peer(item_id, deployed) -> None:
    history = trap_hardware_history(item_id=item_id, deployed=deployed)
    check_saved_trap_hardware(history, item_id=item_id, deployed=deployed)
