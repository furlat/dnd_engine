"""Both players replay complete native trap stories after engine reset."""

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue
from dnd.entity import Entity
from dnd.types.traps import TrapState
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.player_facts import ActionFact, MechanismActivationFact, SpatialEffectStateFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from tests.game.trap_expansion_scenarios import trap_expansion_history


@pytest.mark.parametrize("program,save,jump,expected_hp", (
    ("jaw", False, False, 72), ("jaw", True, False, 80),
    ("gas", False, False, 68),
    ("tripwire", False, False, 72), ("tripwire", False, True, 76),
    ("tripwire", True, False, 80),
))
def test_real_command_narratives_survive_native_and_public_serialization(program, save, jump, expected_hp):
    history = trap_expansion_history(program=program, save=save, jump=jump)
    animation_data = load_animation_data()
    assert set(history.views) == {"traveler", "witness"}
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    for role, recorded in history.views.items():
        native = RecordedSequence.model_validate_json(recorded.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        payload = encode_player_sequence(project_sequence(native))
        assert b"target_condition_uuid" not in payload and b"target_item_uuid" not in payload
        before, roots = decode_player_sequence(payload)
        traveler = next(actor.uuid for actor in before.actors.values() if actor.name == "Traveler")
        witness = next(actor.uuid for actor in before.actors.values() if actor.name == "Witness")
        state = before
        states = []
        for root in roots:
            if program != "gas":
                bound = bind_choreography(state, root, animation_data)
                assert not bound.gaps, (program, role, bound.gaps)
            state = reduce_lineage(state, root)
            states.append(state)
        assert state.actors[traveler].normal_hp == expected_hp, role
        assert state.actors[witness].normal_hp == 80, role
        assert before.actors[traveler].normal_hp == 80
        facts = [node.fact for root in roots for node in root.events]
        activations = [fact for fact in facts if isinstance(fact, MechanismActivationFact) and fact.committed]
        actions = [fact for fact in facts if isinstance(fact, ActionFact)]
        if program == "jaw":
            assert len(activations) == 2
            assert all(fact.mechanism_content_id == "spatial_effect.environment.jaw_trap" for fact in activations)
            assert any(action.name == "Reset Trap" for action in actions)
            assert any(action.name == "Force jaws open" for action in actions) is not save
            assert any(condition.name == "Restrained" for condition in state.actors[traveler].conditions) is not save
            # Walking back onto the already closed jaws produces no third snap.
            modes = [fact.state for fact in facts if isinstance(fact, SpatialEffectStateFact)
                     and fact.state is not None and fact.state != fact.previous_state]
            assert modes == [TrapState.ACTIVATED, TrapState.READY, TrapState.ACTIVATED]
        elif program == "gas":
            assert len(activations) == 1
            assert activations[0].mechanism_content_id == "spatial_effect.environment.gas_vent"
            assert any(action.name == "Deactivate Trap" for action in actions)
            coexist = False
            for step in states:
                assert step.senses is not None
                observed = tuple(step.senses.spatial_effects.values())
                disabled = any(effect.content_ref.content_id == "spatial_effect.environment.gas_vent"
                               and effect.trap_state is TrapState.DEACTIVATED for effect in observed)
                lingering = any(effect.content_ref.content_id == "spatial_effect.environment.poison_gas"
                                for effect in observed)
                coexist |= disabled and lingering
            assert coexist, "Disabling the vent must retain the previously released cloud."
            assert state.senses is not None
            assert not any(effect.content_ref.content_id == "spatial_effect.environment.poison_gas"
                           for effect in state.senses.spatial_effects.values())
            assert not any(condition.name == "Poisoned" for condition in state.actors[traveler].conditions)
        else:
            expected_crossings = 1 if jump else 3
            for content in ("tripwire", "dart_launcher"):
                assert sum(fact.mechanism_content_id == f"spatial_effect.environment.{content}"
                           for fact in activations) == expected_crossings
        assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
