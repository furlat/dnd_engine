"""Incoming area geometry keeps its observation time when its own effect blinds.

Native actions and condition owners produce the records. Tests cross both saved
native and public packets, then bind playback without any native runtime.
"""

import random
from uuid import uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.conditions import Blinded
from dnd.controller import HumanController
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.enchantment import Sleep
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.combat import BoundCast
from game.player_facts import SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, capture_lineage, reduce_interval
from game.replay import RecordedSequence
from tests.game.device_scenarios import device_history


def saved_player(native):
    restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    return decode_player_sequence(encode_player_sequence(project_sequence(restored)))


@pytest.mark.parametrize("program", ("normal-sleep", "sleep-area"), ids=("actor", "device"))
def test_sleep_target_keeps_witnessed_incoming_area_and_loses_sight_at_contact(program) -> None:
    history = device_history(program=program)
    before, roots = saved_player(history.views["target"])
    data = load_animation_data()
    for root in roots:
        fact = root.root.fact
        if isinstance(fact, SpellFact) and fact.behavior_id == "spell.sleep":
            assert before.senses is not None and (8, 5) in before.senses.visible
            assert fact.aoe_position == (8, 5) and fact.area_geometry is not None
            assert fact.source_position == (3, 5)
            # Actual affected-cell observations retain their completion-time
            # filtering; knowing the cast shape does not grant a hidden result.
            assert fact.resolved_area_positions == ()
            bound = bind_choreography(before, root, data)
            assert not bound.gaps
            node, = bound.nodes
            assert isinstance(node.bound, BoundCast)
            delivery = node.bound.timeline.ground_delivery
            assert delivery is not None
            contact_ms = node.start_ms + delivery.travel_end_ms
            pending = sample_choreography(bound, contact_ms - 1)
            arrived = sample_choreography(bound, contact_ms)
            assert pending.displayed.senses is not None and pending.displayed.senses.visible
            assert arrived.displayed.senses is not None and not arrived.displayed.senses.visible
            after = reduce_lineage(before, root)
            assert after.senses is not None and after.senses.visual_access == 0 and not after.senses.visible
            assert any(row.name == "Sleep" for row in after.actors[after.observer_uuid].conditions)
            assert EventQueue.event_cursor() == 0
            return
        before = reduce_lineage(before, root)
    pytest.fail("Recorded Sleep root was not retained")


def unobserved_sleep(*, nested_blindness: bool = False, hidden_destination: bool = False):
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.visibility_doorway_open" if hidden_destination else "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        placements = (("Caster", (5, 7), 20), ("Observer", (5, 5), 20), ("Recipient", (8, 7), 1)) if hidden_destination else (
            ("Caster", (3, 5), 20), ("Observer", (8, 5), 1))
        actors = []
        for name, position, hp_dice in placements:
            actor = Entity.create(uuid4(), name, config=EntityConfig(position=position,
                action_economy=ActionEconomyConfig(spell_slots={1: 1}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=hp_dice, mode="maximums")]),
            ))
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors.append(actor)
        caster, observer = actors[:2]
        destination = actors[-1].position
        encounter = Encounter(name="Area observation timing", source_entity_uuid=caster.uuid)
        for actor in actors:
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10] * len(actors))):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        if not hidden_destination and not nested_blindness:
            observer.add_condition(Blinded(source_entity_uuid=caster.uuid, target_entity_uuid=observer.uuid))
        cursor = EventQueue.event_cursor()
        initial = capture_interval(name="Area observation timing", start_cursor=0, end_cursor=cursor,
            observer_uuid=observer.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        parent = None
        if nested_blindness:
            # A real technical parent groups two native child operations. The
            # later nested spell begins after the first child's sight loss.
            parent = Event(name="Blindness before nested Sleep", event_type=EventType.BASE_ACTION,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=observer.uuid).phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
            blinded = observer.add_condition(Blinded(source_entity_uuid=caster.uuid,
                target_entity_uuid=observer.uuid), parent_event=parent)
            assert blinded is not None and not blinded.canceled
        assert destination not in observer.senses.visible
        random.seed(0)
        result = Sleep(source_entity_uuid=caster.uuid, end_position=destination,
            cast_at_level=1).apply(parent_event=parent)
        assert isinstance(result, SpellEvent) and not result.canceled
        root = result if parent is None else parent.phase_to(EventPhase.COMPLETION)
        lineage = capture_lineage(root, observer_uuid=observer.uuid, known_actor_uuids=frozenset(before.actors))
        return RecordedSequence(initialization=initial, lineages=(lineage,)), result.lineage_uuid
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)


@pytest.mark.parametrize("case", ("initially-blind", "nested-after-blindness", "unseen-destination"))
def test_area_never_borrows_sight_from_before_it_was_declared(case) -> None:
    native, spell_lineage = unobserved_sleep(nested_blindness=case == "nested-after-blindness",
        hidden_destination=case == "unseen-destination")
    before, (root,) = saved_player(native)
    node = next(node for node in root.events if node.lineage_uuid == spell_lineage)
    if case in ("nested-after-blindness", "unseen-destination"):
        assert isinstance(node.fact, SpellFact), "The observed cast identity remains independent from its hidden geometry"
    if isinstance(node.fact, SpellFact):
        assert node.fact.aoe_position is None and node.fact.area_geometry is None
    after = reduce_lineage(before, root)
    if case != "unseen-destination":
        assert after.senses is not None and not after.senses.visible
    assert EventQueue.event_cursor() == 0
