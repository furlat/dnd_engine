"""A witnessed area survives hidden occupants, with only granted recorded cells.

Boundary: native discovery and execution -> saved native events -> saved player
packets. Geometry and recipient assertions remain valid without a running game.
"""

from uuid import uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.controller import HumanController
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.base_block import BaseBlock
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue, EventPhase, EventType
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import Fireball
from dnd.types.world import CardinalDirection
from game.event_record import decode_event, encode_event
from game.player_facts import SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, capture_lineage, reduce_interval
from game.replay import RecordedSequence, ObserverCapture, capture_history


def _record_area(*, doorway: bool):
    reset_engine_runtime()
    battlefield = "battlefield.visibility_doorway_open" if doorway else "battlefield.open_floor_bright"
    built = build_battlefield(battlefield)
    game = Game()
    try:
        placements = {"caster": (4, 7), "observer": (5, 7)} if doorway else {
            "caster": (2, 2), "observer": (3, 2)}
        if doorway:
            placements.update({"visible": (8, 7), "hidden": (8, 4)})
        actors = {}
        for role, position in placements.items():
            actor = Entity.create(uuid4(), role, config=EntityConfig(position=position,
                action_economy=ActionEconomyConfig(spell_slots={3: 1}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(
                    hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
            ))
            if role == "caster":
                register_spell(actor, Fireball, caster_level=5)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        encounter = Encounter(name="Recorded area disclosure", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10] * len(actors))):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not actors["caster"]:
            encounter.next_turn()
        cursor = EventQueue.event_cursor()
        initials = {role: capture_interval(name="area initialization", start_cursor=0,
            end_cursor=cursor, observer_uuid=actors[role].uuid, battlefield_id=battlefield,
            door_uuid=built.object_uuids.get("door")) for role in ("caster", "observer")}
        visible = {role: frozenset(actors[role].senses.visible) for role in initials}
        if doorway:
            assert actors["hidden"].uuid not in actors["observer"].senses.entities
            assert actors["visible"].uuid in actors["observer"].senses.entities
        center = (8, 7) if doorway else (10, 10)
        available = get_available_actions(actors["caster"])
        choice, destination = next((action, target) for action in available.all_actions
            if action.behavior_id == "spell.fireball" for target in action.valid_targets
            if target.position == center)
        with fixed_dice_faces(*([10, 2, 2, 2, 2, 2, 2, 2, 2] * len(actors))):
            result = execute_available_action(actors["caster"], choice, destination)
        assert isinstance(result, SpellEvent) and not result.canceled
        sequences = {}
        for role, initial in initials.items():
            state, _ = reduce_interval(None, initial)
            lineage = capture_lineage(result, observer_uuid=actors[role].uuid,
                known_actor_uuids=frozenset(state.actors))
            sequences[role] = RecordedSequence(initialization=initial, lineages=(lineage,))
        return sequences, {role: actor.uuid for role, actor in actors.items()}, visible, center
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("doorway", (False, True), ids=("empty-area", "partially-observed-area"))
def test_saved_area_keeps_delivery_without_disclosing_hidden_recipients(doorway: bool) -> None:
    recordings, identities, visible, center = _record_area(doorway=doorway)
    for role, native in recordings.items():
        restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        payload = encode_player_sequence(project_sequence(restored))
        state, (lineage,) = decode_player_sequence(payload)
        fact = lineage.root.fact
        assert isinstance(fact, SpellFact), "An undisclosed occupant must not erase a witnessed area cast"
        assert fact.aoe_position == center
        assert fact.area_geometry == native.lineages[0].root.area_geometry
        resolved = native.lineages[0].root.resolved_area_positions
        assert resolved is not None
        assert fact.resolved_area_positions == tuple(point for point in resolved if point in visible[role])
        assert [(row.uuid, row.parent_lineage, row.children_lineages) for row in lineage.events] == [
            (row.uuid, row.parent_lineage, tuple(row.children_lineages)) for row in native.lineages[0].events]
        assert fact.application_id is None
        if doorway and role == "observer":
            hidden = identities["hidden"]
            assert hidden not in state.actors
            assert hidden not in fact.declared_target_entity_uuids
            assert str(hidden) not in payload.decode()
            assert fact.resolved_area_positions is not None
            assert len(fact.resolved_area_positions) < len(resolved)
            public_applications = [row.fact for row in lineage.events
                if isinstance(row.fact, SpellFact) and row.fact.application_id is not None]
            original_applications = {row.application_id: row for row in native.lineages[0].events
                if isinstance(row, SpellEvent) and row.application_id is not None}
            assert public_applications
            for application in public_applications:
                assert application.application_id is not None
                original = original_applications[application.application_id]
                assert application.application_index == original.application_index
                assert application.target_entity_uuid == original.target_entity_uuid != hidden
        elif not doorway:
            assert fact.declared_target_entity_uuids == ()
            assert not any(isinstance(row.fact, SpellFact) and row.fact.application_id is not None
                           for row in lineage.events)
    assert EventQueue.event_cursor() == 0, "Both replays run without native event creation"


def test_prior_native_spell_recordings_remain_readable_without_area_result() -> None:
    recordings, _, _, _ = _record_area(doorway=False)
    original = recordings["caster"].lineages[0].root
    payload = encode_event(original)
    del payload["resolved_area_positions"]
    restored = decode_event(payload)
    assert isinstance(restored, SpellEvent)
    assert restored.resolved_area_positions is None
    assert restored.area_geometry == original.area_geometry
    assert EventQueue.event_cursor() == 0


def _wall_memory_history():
    reset_engine_runtime()
    battlefield = "battlefield.visibility_doorway_open"
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = []
        for name, position in (("caster", (3, 6)), ("walker", (8, 6))):
            actor = Entity.create(uuid4(), name, config=EntityConfig(position=position,
                action_economy=ActionEconomyConfig(spell_slots={3: 1}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(
                    hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
            ))
            setup_standard_actions(actor)
            register_spell(actor, Fireball, caster_level=5)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors.append(actor)
        caster, walker = actors
        encounter = Encounter(name="Wall face memory", source_entity_uuid=uuid4())
        for actor in actors:
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        cursor = EventQueue.event_cursor()
        initial = capture_interval(name="Wall face memory", start_cursor=0, end_cursor=cursor,
            observer_uuid=walker.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        wall_uuid, = get_map().get_boundary_objects_at((7, 6), CardinalDirection.WEST)
        wall = BaseBlock.get(wall_uuid)
        assert wall is not None
        assert (6, 6) not in walker.senses.visible
        operations = {}

        def perform(actor, behavior, destination):
            encounter.next_turn()
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()
            available = get_available_actions(actor)
            action, target = next((action, target) for action in available.all_actions
                if action.behavior_id == behavior for target in action.valid_targets if target.position == destination)
            with fixed_dice_faces(*([1] * 80)):
                result = execute_available_action(actor, action, target)
            assert result is not None and not result.canceled
            return result.lineage_uuid

        operations["cast"] = perform(caster, "spell.fireball", (5, 6))
        snapshot = wall.snapshot_item_state()
        assert snapshot is not None and snapshot.surface_residues[0].faces == (CardinalDirection.WEST,)
        operations["first-sight"] = perform(walker, "action.move", (6, 7))
        assert (6, 6) in walker.senses.visible
        operations["other-side"] = perform(walker, "action.move", (8, 6))
        assert (6, 6) not in walker.senses.visible
        removal_cursor = EventQueue.event_cursor()
        assert wall.remove_condition("Ashen")
        removal = next(event for _, event in EventQueue.iter_events_since(removal_cursor)
            if event.event_type is EventType.CONDITION_REMOVAL and event.phase is EventPhase.COMPLETION)
        operations["hidden-removal"] = removal.lineage_uuid
        operations["reacquired"] = perform(walker, "action.move", (6, 7))
        history = capture_history(before, (), observers=(ObserverCapture("walker", walker.uuid, cursor),))
        return history.views["walker"], wall_uuid, operations
    finally:
        game.close()
        reset_engine_runtime()


def test_wall_faces_are_observed_independently_and_hidden_removal_waits_for_reacquisition() -> None:
    native, wall_uuid, operations = _wall_memory_history()
    restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    payload = encode_player_sequence(project_sequence(restored))
    state, roots = decode_player_sequence(payload)
    assert state.objects[wall_uuid].item.surface_residues == ()
    checkpoints = {}
    for root in roots:
        state = reduce_lineage(state, root)
        for label, identity in operations.items():
            if root.root.lineage_uuid == identity:
                checkpoints[label] = state.objects[wall_uuid].item.surface_residues
    assert checkpoints.get("cast", ()) == (), "Seeing the unburnt side must not disclose the scorched side"
    assert checkpoints["first-sight"][0].faces == (CardinalDirection.WEST,)
    assert checkpoints["other-side"] == checkpoints["first-sight"]
    assert checkpoints.get("hidden-removal", checkpoints["other-side"]) == checkpoints["other-side"]
    assert checkpoints["reacquired"] == ()
    assert EventQueue.event_cursor() == 0
