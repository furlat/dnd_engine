"""Native observations cross saved public bytes without private engine state."""

import json
from uuid import UUID, uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.conditions import Blinded
from dnd.core.base_object import BaseObject, PASSIVE_EVENT_REPLAY
from dnd.core.dice import DiceRoll
from dnd.core.creature_types import DamageType
from dnd.core.events import EventPhase, EventQueue, SensoryUpdateEvent, SpatialChangeEvent, TakeDamageEvent
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment import CloseDirectionalDoorAction, OpenDirectionalDoorAction
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.player_facts import DamageFact, EquipmentFact, MovementFact, ObjectDestroyedFact, SensoryFact, SpellFact, StepFact
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, capture_lineage, reduce_interval
from game.replay import ObserverCapture, RecordedSequence, capture_history
from tests.game.visibility_scenarios import visibility_history
from tests.game.concealment_scenarios import concealment_history
from tests.game.scenarios import movement_with_paralysis
from tests.game.prop_destruction_scenarios import prop_destruction_history


def _saved_public(native: RecordedSequence):
    # The projector receives restored native values; the receiver sees only its
    # saved public bytes. Both steps happen after the producer reset its runtime.
    restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    sequence = project_sequence(restored)
    payload = encode_player_sequence(sequence)
    before, roots = decode_player_sequence(payload)
    assert EventQueue.event_cursor() == 0
    return payload, before, roots


def test_fresh_destruction_public_bytes_retain_strict_placement_and_world_updates() -> None:
    history = prop_destruction_history(item_id="environment.blocker.crate")
    rolls = dict(DiceRoll._registry)
    for native in history.views.values():
        expected = project_sequence(native)
        payload = encode_player_sequence(expected)
        reset_engine_runtime()
        state, roots = decode_player_sequence(payload)
        assert roots == expected.lineages
        destruction = [node.fact for root in roots for node in root.events
                       if isinstance(node.fact, ObjectDestroyedFact)]
        assert len(destruction) == 1
        destroyed = destruction[0]
        assert destroyed.placement == next(node.fact.placement for root in expected.lineages
            for node in root.events if isinstance(node.fact, ObjectDestroyedFact))
        for root in roots:
            state = reduce_lineage(state, root)
        assert state.objects[destroyed.object_uuid].placement.position == destroyed.placement.position
        assert EventQueue.event_cursor() == 0 and BaseObject._registry == {}
        assert DiceRoll._registry == rolls


def test_witnessed_invisibility_keeps_cast_when_terminal_coordinate_is_withheld() -> None:
    history = concealment_history(reveal="none")
    _, state, roots = _saved_public(history.views["perceiver"])
    subject = history.views["subject"].initialization.observer_uuid
    cast_uuid = next(root.root.uuid for root in history.views["perceiver"].lineages
                     if isinstance(root.root, SpellEvent) and root.root.behavior_id == "spell.invisibility")
    for root in roots:
        if root.root.uuid == cast_uuid:
            assert state.senses is not None and state.senses.entities[subject].position == (7, 3)
            fact = root.root.fact
            assert isinstance(fact, SpellFact), "disappearance must not erase the witnessed cast"
            assert fact.source_entity_uuid == subject and fact.source_position is None
            after = reduce_lineage(state, root)
            assert after.senses is not None and subject not in after.senses.entities
            return
        state = reduce_lineage(state, root)
    raise AssertionError("native Invisibility root is missing")


def test_one_native_doorway_crossing_produces_two_distinct_player_packets() -> None:
    history = visibility_history()
    packets = {role: _saved_public(native) for role, native in history.views.items()}
    _, observer, observer_roots = packets["observer"]
    _, subject, subject_roots = packets["subject"]
    assert observer.observer_uuid != subject.observer_uuid
    assert [root.root.uuid for root in observer_roots] == [root.root.uuid for root in subject_roots]
    observed_edges = [(node.fact.from_position, node.fact.to_position)
                      for root in observer_roots for node in root.events if isinstance(node.fact, StepFact)]
    owned_edges = [(node.fact.from_position, node.fact.to_position)
                  for root in subject_roots for node in root.events if isinstance(node.fact, StepFact)]
    assert observed_edges == [((8, 6), (8, 7)), ((8, 7), (8, 8))]
    assert owned_edges == [((8, y), (8, y + 1)) for y in range(4, 10)]
    assert subject.observer_uuid not in observer.actors
    root, = observer_roots
    assert isinstance(root.root.fact, MovementFact)
    assert root.root.fact.path == () and root.root.fact.start_position is None
    # Losing sight at the endpoint does not erase the complete causal root.
    source = history.views["observer"].lineages[0]
    assert [(node.uuid, node.lineage_uuid, node.parent_lineage, node.children_lineages) for node in root.events] == [
        (event.uuid, event.lineage_uuid, event.parent_lineage, tuple(event.children_lineages)) for event in source.events]
    native_updates = [event for event in source.events if isinstance(event, SensoryUpdateEvent)
                      and event.observer_uuid == observer.observer_uuid]
    delivered_updates = [node.fact for node in root.events if isinstance(node.fact, SensoryFact)]
    assert [row.entity_contacts_changed for row in delivered_updates] == [row.entity_contacts_changed for row in native_updates]
    assert [row.entity_contacts_removed for row in delivered_updates] == [row.entity_contacts_removed for row in native_updates]
    after = reduce_lineage(observer, root)
    assert after.senses is not None and subject.observer_uuid not in after.senses.entities
    assert after.actors[subject.observer_uuid].last_visual_position == (8, 8)

    for role, (payload, before, roots) in packets.items():
        wire = json.loads(payload)
        assert "objective_rows" not in payload.decode()
        assert "source_entity_name" not in payload.decode()
        assert "identified_entity_observer_uuids" not in payload.decode()
        assert "contained_items" not in payload.decode()
        for admission in wire["initialization"]["observations"] + [
                row for lineage in wire["lineages"] for row in lineage["observations"]]:
            actor = admission["actor"]
            assert (actor["controlled_items"] is not None) == (actor["uuid"] == str(before.observer_uuid))
        assert all(node.fact.observer_uuid == before.observer_uuid for root in roots
                   for node in root.events if isinstance(node.fact, SensoryFact)), role


def test_hidden_damage_and_gear_are_received_only_when_the_actor_is_reacquired() -> None:
    history = visibility_history(subject_position=(8, 7),
        route=(("subject", (8, 10)), ("subject", (8, 7))), hidden_change_after=0)
    _, before, roots = _saved_public(history.views["observer"])
    subject_uuid = history.views["subject"].initialization.observer_uuid
    assert before.actors[subject_uuid].normal_hp == 40
    assert next(row for row in before.actors[subject_uuid].visual_loadout.layers if row.slot == "MELEE_MAIN").item_id == "weapon.shortsword"
    state = before
    witnessed = []
    for root in roots:
        # The unseen mutation produces neither a combat cue nor inventory data.
        assert not any(isinstance(node.fact, (DamageFact, EquipmentFact)) for node in root.events)
        state = reduce_lineage(state, root)
        witnessed.append(state.actors[subject_uuid].normal_hp)
    assert witnessed[0] == 40 and witnessed[-1] == 33
    actor = state.actors[subject_uuid]
    assert actor.controlled_items is None
    assert next(row for row in actor.visual_loadout.layers if row.slot == "MELEE_MAIN").item_id == "weapon.dagger"
    assert before.actors[subject_uuid].normal_hp == 40
    assert before.senses is not None and state.senses is not None
    assert before.senses.seen <= state.senses.seen


def _unseen_source_damage() -> tuple[RecordedSequence, UUID]:
    reset_engine_runtime()
    build_battlefield("battlefield.visibility_doorway_closed")
    game = Game()
    try:
        observer = Entity.create(uuid4(), "Observed recipient", config=EntityConfig(
            position=(5, 7), health=HealthConfig(hit_dices=[
                HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")]),
        ))
        hidden = Entity.create(uuid4(), "Unseen private source", config=EntityConfig(position=(8, 4)))
        for actor in (observer, hidden):
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        assert hidden.uuid not in observer.senses.entities
        cursor = EventQueue.event_cursor()
        initialization = capture_interval(name="hidden damage source", start_cursor=0, end_cursor=cursor,
            observer_uuid=observer.uuid, battlefield_id="battlefield.visibility_doorway_closed")
        observer.receive_damage(7, DamageType.FORCE, source_entity_uuid=hidden.uuid)
        root, = (event for _, event in EventQueue.iter_events_since(cursor)
                 if isinstance(event, TakeDamageEvent) and event.parent_lineage is None
                 and event.phase is EventPhase.COMPLETION)
        assert observer.get_hp() == 33 and hidden.uuid not in observer.senses.entities
        lineage = capture_lineage(root, observer_uuid=observer.uuid, known_actor_uuids=frozenset({observer.uuid}))
        return RecordedSequence(initialization=initialization, lineages=(lineage,)), hidden.uuid
    finally:
        game.close()
        reset_engine_runtime()


def test_known_recipient_keeps_damage_when_its_source_is_not_disclosed() -> None:
    native, hidden_uuid = _unseen_source_damage()
    payload, before, (root,) = _saved_public(native)
    damage = [node.fact for node in root.events if isinstance(node.fact, DamageFact)]
    assert [row.stage for row in damage] == ["applied", "taken"]
    assert all(row.source_entity_uuid is None for row in damage)
    assert str(hidden_uuid) not in payload.decode()
    assert "Unseen private source" not in payload.decode()
    after = reduce_lineage(before, root)
    assert after.actors[before.observer_uuid].normal_hp == 33
    assert before.actors[before.observer_uuid].normal_hp == 40
    group = bind_choreography(before, root, load_animation_data())
    assert group.gaps == () and len(group.damage) == 1
    hit = sample_choreography(group, group.damage[0].timing.hp_ms)
    assert hit.displayed.actors[before.observer_uuid].normal_hp == 33
    assert {row.actor_uuid for row in hit.bodies} == {str(before.observer_uuid)}


def _door_memory_history() -> tuple[dict[str, RecordedSequence], UUID]:
    reset_engine_runtime()
    built = build_battlefield("battlefield.visibility_doorway_closed")
    game = Game()
    try:
        observer = Entity.create(uuid4(), "Observer", config=EntityConfig(position=(5, 7)))
        operator = Entity.create(uuid4(), "Door operator", config=EntityConfig(position=(8, 7)))
        for actor in (observer, operator):
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        door_uuid = built.object_uuids["door"]
        cursor = EventQueue.event_cursor()
        startup = capture_interval(name="door memory", start_cursor=0, end_cursor=cursor,
            observer_uuid=observer.uuid, battlefield_id="battlefield.visibility_doorway_closed", door_uuid=door_uuid)
        before, _ = reduce_interval(None, startup)
        assert (8, 7) not in observer.senses.visible or not observer.senses.visible[(8, 7)]
        opened = OpenDirectionalDoorAction(source_entity_uuid=operator.uuid,
            source_item_uuid=door_uuid, template=False).apply()
        assert opened is not None and not opened.canceled
        assert observer.senses.visible[(8, 7)]
        blindness = Blinded(source_entity_uuid=operator.uuid, target_entity_uuid=observer.uuid)
        blinded = observer.add_condition(blindness)
        assert blinded is not None and not blinded.canceled
        assert not any(observer.senses.visible.values())
        closed = CloseDirectionalDoorAction(source_entity_uuid=operator.uuid,
            source_item_uuid=door_uuid, template=False).apply()
        assert closed is not None and not closed.canceled
        assert not any(observer.senses.visible.values())
        observer.remove_condition_by_uuid(blindness.uuid)
        assert any(observer.senses.visible.values())
        history = capture_history(before, (), observers=(
            ObserverCapture("observer", observer.uuid, cursor), ObserverCapture("operator", operator.uuid, cursor)))
        return history.views, door_uuid
    finally:
        game.close()
        reset_engine_runtime()


def test_door_after_value_is_observed_causally_and_remembered_while_unseen() -> None:
    views, door_uuid = _door_memory_history()
    _, before, roots = _saved_public(views["observer"])
    assert before.objects[door_uuid].item.is_open is False
    original_tiles = set(before.tiles)
    states = []
    state = before
    for root in roots:
        state = reduce_lineage(state, root)
        states.append(state)
    # The observer learns open, keeps open while blind and during the hidden
    # close operation, then learns closed when the native sensory owner returns.
    assert [row.objects[door_uuid].item.is_open for row in states] == [True, True, False]
    assert states[0].objects[door_uuid].item.boundary_structure is not None
    assert states[0].objects[door_uuid].item.boundary_structure.blocked_channels == ()
    assert state.objects[door_uuid].item.boundary_structure == before.objects[door_uuid].item.boundary_structure
    assert original_tiles < set(states[0].tiles)
    assert set(states[0].tiles) == set(states[1].tiles)
    assert views["observer"].lineages[2].root.uuid not in {root.root.uuid for root in roots}
    assert before.senses is not None and state.senses is not None
    assert before.senses.seen < state.senses.seen
    assert (8, 7) not in state.senses.visible and (8, 7) in state.senses.seen
    assert (14, 14) not in state.tiles, "a never-observed cell must not arrive with the authored full world"

    # The operator witnessed the close immediately; this is a second projection
    # of the same native commands, not a second simulated game.
    _, operator_state, operator_roots = _saved_public(views["operator"])
    operator_states = []
    for root in operator_roots:
        operator_state = reduce_lineage(operator_state, root)
        operator_states.append(operator_state.objects[door_uuid].item.is_open)
    assert operator_states == [True, True, False, False]

    opening = roots[0]
    native_opening = views["observer"].lineages[0]
    spatial = next(event for event in native_opening.events if isinstance(event, SpatialChangeEvent)
                   and event.object_uuid == door_uuid)
    source_indexes = {row.event_uuid: row.source_index for row in native_opening.objective_rows}
    update = next(row for row in opening.world_updates
                  if any(obj.item.item_uuid == door_uuid and obj.item.is_open for obj in row.objects))
    assert source_indexes[update.event_uuid] < source_indexes[spatial.uuid]
    assert any(node.uuid == update.event_uuid and isinstance(node.fact, SensoryFact) for node in opening.events)


def test_predeployment_trait_does_not_apply_to_an_unadmitted_actor() -> None:
    history = movement_with_paralysis(17, 80)
    native = RecordedSequence(initialization=history.initialization, lineages=history.lineages)
    _, before, (root,) = _saved_public(native)
    reactor = before.actors[before.observer_uuid]
    assert reactor.conditions == history.before.actors[before.observer_uuid].conditions
    assert native.initialization.conditions, "the real source trait was installed before deployment"
    after = reduce_lineage(before, root)
    mover = next(actor for actor in after.actors.values() if actor.uuid != before.observer_uuid)
    assert mover.normal_hp == 73 and not mover.conditions
    reaction = next(node for node in root.events
                    if any(row.behavior_id == "reaction.opportunity_attack" for row in node.content_attributions))
    assert reaction.fact is not None
    assert reaction.combat_log is not None


@pytest.mark.parametrize("select_first_door", (True, False), ids=("another-door-selected", "no-door-selected"))
def test_initialization_keeps_a_second_door_changed_before_the_baseline(select_first_door: bool) -> None:
    reset_engine_runtime()
    built = build_battlefield("battlefield.visibility_two_doors_open")
    game = Game()
    try:
        observer = Entity.create(uuid4(), "Door operator", config=EntityConfig(position=(6, 9)))
        observer.compose_entity()
        game.deploy_entity(observer, observer.position)
        first_door = built.object_uuids["door-5"]
        second_door = built.object_uuids["door-9"]
        closed = CloseDirectionalDoorAction(source_entity_uuid=observer.uuid,
            source_item_uuid=second_door, template=False).apply()
        assert closed is not None and not closed.canceled
        change, = (event for _, event in EventQueue.iter_events_since(0)
                   if isinstance(event, SpatialChangeEvent) and event.phase is EventPhase.COMPLETION
                   and event.object_uuid == second_door)
        assert change.object_is_open is False
        assert change.object_boundary_structure is not None and change.object_boundary_structure.blocked_channels
        initialization = capture_interval(name="second aperture closed before baseline", start_cursor=0,
            end_cursor=EventQueue.event_cursor(), observer_uuid=observer.uuid,
            battlefield_id=built.definition.battlefield_id,
            door_uuid=first_door if select_first_door else None)
        recorded = RecordedSequence(initialization=initialization, lineages=())
        expected_boundary = change.object_boundary_structure
    finally:
        game.close()
        reset_engine_runtime()

    _, public, roots = _saved_public(recorded)
    assert not roots
    assert public.objects[first_door].item.is_open is True
    assert public.objects[second_door].item.is_open is False
    assert public.objects[second_door].item.boundary_structure == expected_boundary


def test_initialization_keeps_unnamed_authored_torch_after_values() -> None:
    reset_engine_runtime()
    built = build_battlefield("battlefield.standard_hazards_open")
    game = Game()
    try:
        observer = Entity.create(uuid4(), "Torch observer", config=EntityConfig(position=(14, 2)))
        observer.compose_entity()
        game.deploy_entity(observer, observer.position)
        # The actual battlefield settles cold-authored fixtures through native
        # ignition plus floor-item after-values before any participant starts.
        torch_facts = tuple(event for _, event in EventQueue.iter_events_since(0)
                            if isinstance(event, ItemLocationStateEvent)
                            and event.phase is EventPhase.COMPLETION
                            and event.item_state.item_id == "environment.wall_torch")
        assert len(torch_facts) == 2 and all(event.item_state.is_lit for event in torch_facts)
        observed = tuple(event for event in torch_facts if event.item_state.item_uuid in observer.senses.objects)
        assert observed
        initialization = capture_interval(name="unnamed torch startup", start_cursor=0,
            end_cursor=EventQueue.event_cursor(), observer_uuid=observer.uuid,
            battlefield_id=built.definition.battlefield_id)
        recorded = RecordedSequence(initialization=initialization, lineages=())
    finally:
        game.close()
        reset_engine_runtime()

    _, public, roots = _saved_public(recorded)
    assert not roots
    for fact in observed:
        torch = public.objects[fact.item_state.item_uuid]
        assert torch.placement == fact.world_placement
        assert torch.item.is_lit is True
