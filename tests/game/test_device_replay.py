"""Device operation survives native and public event serialization without a game."""

import pytest

from devtools.animation_review.cases import DeviceCase, load_cases
from devtools.animation_review.produce import produce
from devtools.animation_review.trace import timeline_trace
from dnd.actions import SpellEvent
from dnd.blocks.base_item import ItemChargeConsumptionEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventPhase, EventQueue, TakeDamageEvent
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity
from game.animation_data import load_animation_data
from game.combat import bind_cast
from game.choreography import bind_choreography, sample_choreography
from game.player_facts import DamageFact, ItemChargeFact, MovementFact, ObjectDestroyedFact, SpellFact, StepFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence


CASES = tuple(case for case in load_cases() if isinstance(case.scenario, DeviceCase))


@pytest.fixture(scope="module")
def animation_data():
    return load_animation_data()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_device_turns_replay_from_both_players_saved_events(case, animation_data) -> None:
    captured = produce(case)
    program = case.scenario.program
    assert set(captured.views) == {"operator", "target"}
    native = captured.views["operator"]
    spells = [root for root in native.lineages if isinstance(root.root, SpellEvent)]
    successful = [root for root in spells if not root.root.canceled]
    spell_events = []
    for root in successful:
        event = root.root
        assert isinstance(event, SpellEvent)
        spell_events.append(event)
    expected_spells = {
        "mixed-spells": ["spell.fireball", "spell.sleep", "spell.fire_bolt"],
        "sleep-area": ["spell.sleep", "spell.fire_bolt"],
        "normal-sleep": ["spell.sleep", "spell.fire_bolt"],
        "reposition": ["spell.fireball"],
        "break-cannon": ["spell.sleep", "spell.fire_bolt"],
        "break-projector": ["spell.sleep", "spell.fire_bolt"],
        "break-fireball": ["spell.fireball"],
    }[program]
    assert [event.behavior_id for event in spell_events] == expected_spells
    device_uuid = spell_events[0].source_item_uuid
    assert (device_uuid is None) == (program == "normal-sleep")
    for event in spell_events:
        uses_device = program != "normal-sleep" and event.behavior_id != "spell.fire_bolt"
        assert event.source_item_uuid == (device_uuid if uses_device else None)
        assert event.cast_origin == ("source_item" if uses_device else "actor")
    assert all(event.source_position == ((4, 4) if program == "reposition" else (3, 5))
        for event in spell_events), "The device origin must not overwrite the responsible actor's recorded position"
    canceled = [root for root in spells if root.root.canceled]
    assert len(canceled) == (1 if program == "reposition" else 0)
    expected_charges = [1, 0] if program == "mixed-spells" else [] if program == "normal-sleep" else [0]
    charges = [event for root in successful for event in root.events
               if isinstance(event, ItemChargeConsumptionEvent)]
    assert [event.charges_after for event in charges] == expected_charges
    assert all(event.item_uuid == device_uuid and event.charges_before == event.charges_after + 1
               and not event.item_destroyed for event in charges)
    for root in successful:
        assert isinstance(root.root, SpellEvent)
        if root.root.behavior_id == "spell.sleep":
            applications = [event for event in root.events
                if isinstance(event, SpellEvent) and event.application_id is not None]
            assert [event.application_index for event in applications] == [0, 1]
            assert len({event.application_id for event in applications}) == 2
            assert len({event.target_entity_uuid for event in applications}) == 2
            assert not any(event.total_damage for event in applications)
            assert root.root.aoe_position is not None and root.root.area_geometry is not None
            assert root.root.resolved_area_positions is not None

    expected_losses = {"mixed-spells": (18, 16), "sleep-area": (2, 0),
                       "normal-sleep": (2, 0), "reposition": (16, 16),
                       "break-cannon": (2, 0), "break-projector": (2, 0),
                       "break-fireball": (16, 16)}[program]
    if program not in ("reposition", "break-fireball"):
        expected_losses = (expected_losses[0] - 2 + case.scenario.wake_damage, expected_losses[1])
    breaking = program in ("break-cannon", "break-projector", "break-fireball")
    if breaking:
        hits = [event for root in native.lineages for event in root.events
                if isinstance(event, TakeDamageEvent) and event.target_entity_uuid == device_uuid]
        assert [event.resulting_hp for event in hits] == [8, 0]
    for role, original in captured.views.items():
        restored = RecordedSequence.model_validate_json(original.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        packet = encode_player_sequence(project_sequence(restored))
        state, roots = decode_player_sequence(packet)
        actors = {actor.name: actor for actor in state.actors.values()}
        starting_hp = {name: actor.normal_hp for name, actor in actors.items()}
        device = state.objects[device_uuid] if device_uuid is not None else None
        if device is not None:
            assert device.placement.position == (4, 5)
            assert device.item.item_id == ("environment.arcane_machine_gun"
                if program in ("sleep-area", "break-projector") else "environment.fireball_cannon")
        witnessed = []
        movements = []
        received_charges = [event.fact.charges_after for root in roots for event in root.events
                            if isinstance(event.fact, ItemChargeFact) and event.fact.item_uuid == device_uuid]
        assert received_charges == (expected_charges if role == "operator" else [])
        for root in roots:
            nodes = {event.lineage_uuid for event in root.events}
            assert all(event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL) for event in root.events)
            assert all(child in nodes for event in root.events for child in event.children_lineages)
            fact = root.root.fact
            if root.root.canceled:
                assert not any(isinstance(event.fact, DamageFact) for event in root.events)
                canceled_sample = sample_choreography(bind_choreography(state, root, animation_data), 0)
                assert not canceled_sample.clips and not canceled_sample.bodies
            elif isinstance(fact, SpellFact):
                witnessed.append(fact.behavior_id)
                # A sleeping observer need not see the source of the later hit.
                if fact.behavior_id != "spell.fire_bolt":
                    bound = bind_cast(state, root, animation_data)
                    emitter = bound.timeline.source.emitter
                    trace = timeline_trace(bound.timeline)
                    if device is not None:
                        assert fact.cast_origin == "source_item" and fact.source_item_uuid == device_uuid
                        assert emitter is not None and emitter.item_uuid == str(device_uuid)
                        assert trace["source"]["emitter"]["item_uuid"] == str(device_uuid)
                        assert trace["source"]["emitter"]["body_asset"] == emitter.art.identity
                        assert "art" not in trace["source"]["emitter"]
                        assert "bank" not in trace["source"]["emitter"]
                        assert emitter.grid == (4, 5) and emitter.elevation_steps == device.placement.base_height_steps
                        assert emitter.facing == ("S" if program == "reposition" else "E")
                        assert emitter.art.identity == ("arcane" if program in ("sleep-area", "break-projector") else "cannon")
                        assert bound.timeline.source.caster.grid != emitter.grid
                    else:
                        assert emitter is None and fact.cast_origin == "actor"
                    assert bound.timeline.source.caster.actor_uuid == str(actors["Operator"].uuid)
                    assert bound.timeline.source.caster.grid == fact.source_position
                    assert bound.timeline.recipe.definitionRef.content_id == fact.behavior_id
            elif isinstance(fact, MovementFact):
                movements.extend(event.fact.to_position for event in root.events
                    if isinstance(event.fact, StepFact) and event.fact.committed)
            state = reduce_lineage(state, root)
        # A lethal hit does not restore this sleeping observer's sight of the
        # caster. Its received damage/life facts still settle its own outcome.
        expected_witnessed = (expected_spells[:-1] if role == "target"
                              and case.scenario.wake_damage >= starting_hp["Target"]
                              and program == "normal-sleep" else expected_spells)
        assert witnessed == expected_witnessed, role
        final = {actor.name: actor for actor in state.actors.values()}
        assert final["Operator"].normal_hp == starting_hp["Operator"]
        assert (starting_hp["Target"] - final["Target"].normal_hp,
                starting_hp["Second"] - final["Second"].normal_hp) == expected_losses
        if device_uuid is not None:
            if breaking:
                destroyed = [event.fact for root in roots for event in root.events
                             if isinstance(event.fact, ObjectDestroyedFact)]
                assert len(destroyed) == 1
                assert state.objects[device_uuid].item.integrity is ItemIntegrity.DESTROYED
                wrecks = [obj for obj in state.objects.values() if obj.item.integrity is ItemIntegrity.DESTROYED]
                assert len(wrecks) == 1 and wrecks[0].placement.position == (4, 5)
                assert not wrecks[0].item.concentration_slots
            else:
                assert state.objects[device_uuid].placement.position == (4, 5)
        if program not in ("reposition", "break-fireball"):
            assert not any(row.behavior_id == "condition.spell.sleep" for row in final["Target"].conditions)
            assert any(row.behavior_id == "condition.spell.sleep" for row in final["Second"].conditions)
        if program == "reposition":
            assert movements == [(3, 4), (4, 4)]
        assert "objective_rows" not in packet.decode()
        assert "identified_entity_observer_uuids" not in packet.decode()
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
