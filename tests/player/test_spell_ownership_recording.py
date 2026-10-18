"""Native ownership admission facts retain terminal histories and old archives."""
from uuid import uuid4

import pytest

from dnd.actions import AttackEvent, MovementEvent, ShoveEvent, SpellEvent
from dnd.core.base_actions import ActionEvent
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.audience import PlayerAudience
from dnd.player.event_record import decode_event, encode_event
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.player.recorded import encode_sequence, decode_sequence
from dnd.player.facts import DamageResultFact, ConditionChangeFact
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.spells.necromancy import Harm
from tests.player.test_recorded_boundary import world as world
from tests.engine.test_high_level_spell_controls import cast, high_actor
from tests.manual.spell_regression_support import force_save_result


@pytest.mark.parametrize("kind,fields", [
    (ActionEvent, {}), (AttackEvent, {"weapon_slot": WeaponSlot.MELEE_MAIN}), (SpellEvent, {}), (ShoveEvent, {}),
    (MovementEvent, {"start_position": (1, 1), "end_position": (2, 1)}),
])
def test_previous_native_recordings_omit_new_optional_admission_facts(kind, fields):
    native = kind(source_entity_uuid=uuid4(),phase=EventPhase.COMPLETION,use_register=False,**fields)
    payload = encode_event(native)
    for field in ("application_intercepted_by", "magical_transfer", "authored_spell_id"):
        payload.pop(field, None)
    decoded = decode_event(payload)
    assert decoded.uuid == native.uuid and decoded.application_intercepted_by is None
    current = native.model_copy(update={"application_intercepted_by": uuid4()})
    decoded_current = decode_event(encode_event(current))
    assert decoded_current.application_intercepted_by == current.application_intercepted_by


def test_real_harm_cast_and_reduction_admission_capture_project_and_replay(world):
    game, built, _ = world
    caster = high_actor(game,position=(8, 8))
    target = high_actor(game, "Target", (9, 8), "foes")
    audience = PlayerAudience(controlled=(caster.uuid,target.uuid),observers=(caster.uuid,))
    native_initial = capture_interval(name="Ownership facts",start_cursor=0,
        end_cursor=EventQueue.event_cursor(),observer_uuid=caster.uuid,battlefield_id=built.definition.battlefield_id,audience=audience)
    session = SessionProjection()
    projection, initialization = begin_projection(session, native_initial)
    state = reduce_initialization(initialization)
    force_save_result(target, "constitution", succeeds=False)
    with fixed_dice_faces(*([2] * 40)):
        result = cast(Harm, caster, target)
    captured, = capture_lineages((result,),observer_uuid=caster.uuid,known_actor_uuids=frozenset(state.actors),audience=audience)
    _, (restored,) = decode_sequence(encode_sequence(native_initial,(captured,)))
    public = project_lineage(session, projection, restored)
    assert public is not None
    replayed = reduce_lineage(state, public)
    assert replayed.actors[target.uuid].normal_hp == target.get_normal_hp(), (replayed.actors[target.uuid].normal_hp,target.get_normal_hp())
    assert replayed.actors[target.uuid].maximum_hp == target.get_max_hp(), (replayed.actors[target.uuid].maximum_hp,target.get_max_hp())
    assert any(isinstance(node.fact,DamageResultFact) for node in public.events)
    assert any(isinstance(node.fact,ConditionChangeFact) for node in public.events)
