"""One native experiment produces independent public views from the same event identities."""

from pathlib import Path

import pytest

from devtools.animation_review.cases import load_cases
from devtools.animation_review.produce import produce
from dnd.actions import MovementEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue, SensoryUpdateEvent
from dnd.entity import Entity
from game.player_facts import EquipmentFact, SensoryFact, StepFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from game.presentation import reduce_interval
from tests.game.visibility_scenarios import visibility_history


def test_doorway_crossing_records_both_observers_and_replays_only_authorized_steps(tmp_path: Path) -> None:
    captured = visibility_history()
    assert set(captured.views) == {"observer", "subject"}
    first, second = (captured.views[role] for role in ("observer", "subject"))
    assert first.initialization.generation == second.initialization.generation
    assert first.initialization.end_cursor == second.initialization.end_cursor
    assert [root.root.uuid for root in first.lineages] == [root.root.uuid for root in second.lineages]
    assert first.initialization.observer_uuid != second.initialization.observer_uuid
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    received = {}
    for role, native in captured.views.items():
        native_path = tmp_path / f"{role}.native.json"
        native_path.write_text(native.model_dump_json())
        restored = RecordedSequence.model_validate_json(native_path.read_bytes(), context=PASSIVE_EVENT_REPLAY)
        path = tmp_path / f"{role}.json"
        path.write_bytes(encode_player_sequence(project_sequence(restored)))
        before, lineages = decode_player_sequence(path.read_bytes())
        assert set(before.actors) == {before.observer_uuid}
        steps = [node.fact for lineage in lineages for node in lineage.events if isinstance(node.fact, StepFact)]
        received[role] = [(step.from_position, step.to_position) for step in steps]
        for lineage in lineages:
            before = reduce_lineage(before, lineage)
        assert before.senses is not None and not before.senses.entities
    assert received["observer"] == [((8, 6), (8, 7)), ((8, 7), (8, 8))]
    assert received["subject"] == [((8, y), (8, y + 1)) for y in range(4, 10)]
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_hidden_equipment_and_damage_are_seen_on_reacquisition_without_replaying_private_actions() -> None:
    captured = visibility_history(subject_position=(8, 7),
        route=(("subject", (8, 4)), ("subject", (8, 7))), hidden_change_after=0)
    observer = project_sequence(captured.views["observer"])
    subject = project_sequence(captured.views["subject"])
    actor_uuid = subject.initialization.observer_uuid
    private_equipment = [node for lineage in subject.lineages for node in lineage.events
                         if isinstance(node.fact, EquipmentFact)]
    assert private_equipment
    assert all(node.fact is None for lineage in observer.lineages for node in lineage.events
               if node.uuid in {row.uuid for row in private_equipment})
    before, lineages = decode_player_sequence(encode_player_sequence(observer))
    initial = before.actors[actor_uuid]
    assert initial.normal_hp == 40
    for lineage in lineages:
        before = reduce_lineage(before, lineage)
    final = before.actors[actor_uuid]
    assert final.normal_hp == 33
    assert final.controlled_items is None
    assert any(item.item_id == "weapon.dagger" for item in final.visual_loadout.layers)
    assert not any(item.item_id == "weapon.shortsword" for item in final.visual_loadout.layers)
    assert any(isinstance(node.fact, SensoryFact) and node.fact.entity_contacts_removed
               for lineage in observer.lineages for node in lineage.events)


@pytest.mark.parametrize("case_id, contact_pattern, moving_role", [
    ("sight-range-enter", (False, True), "subject"),
    ("sight-range-leave", (True, False), "subject"),
    ("sight-range-reenter", (True, False, True), "subject"),
    ("sight-doorway-cross", (False, True, False), "subject"),
    ("sight-doorway-reverse", (False, True, False), "subject"),
    ("sight-observer-cross", (False, True, False), "observer"),
    ("sight-observer-reverse", (False, True, False), "observer"),
    ("sight-doorway-stop", (False, True), "subject"),
    ("sight-doorway-reenter", (False, True, False, True, False), "subject"),
    ("sight-doorway-closed", (False,), "subject"),
    ("sight-hidden-gear-hp", (True, False, True), "subject"),
    ("sight-glimpse-paused", (False, True, False), "subject"),
    ("sight-first-point", (False, True), "subject"),
    ("sight-last-point", (True, False), "subject"),
    ("sight-two-runs", (False, True, False, True, False), "subject"),
])
def test_catalog_visibility_experiments_cross_their_actual_native_sight_boundaries(
    case_id: str, contact_pattern: tuple[bool, ...], moving_role: str,
) -> None:
    """Each clip label must describe actual senses, not merely successful moves."""
    case = next(row for row in load_cases() if row.id == case_id)
    captured = produce(case)
    moving_uuid = captured.views[moving_role].initialization.observer_uuid
    for role, original in captured.views.items():
        native = RecordedSequence.model_validate_json(original.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        other_uuid = next(view.initialization.observer_uuid for name, view in captured.views.items() if name != role)
        before, _ = reduce_interval(None, native.initialization)
        assert before.senses is not None
        contact = before.senses.entities.get(other_uuid)
        pattern = [contact is not None and contact.visual]
        position_changes = []
        movement_roots = []
        for lineage in native.lineages:
            if isinstance(lineage.root, MovementEvent):
                movement_roots.append(lineage.root)
                assert lineage.root.source_entity_uuid == moving_uuid
            for event in lineage.events:
                if not isinstance(event, SensoryUpdateEvent) or event.observer_uuid != before.observer_uuid:
                    continue
                if event.observer_position_changed:
                    position_changes.append(event.observer_position)
                visible = pattern[-1]
                if other_uuid in event.entity_contacts_removed:
                    visible = False
                if other_uuid in event.entity_contacts_changed:
                    visible = event.entity_contacts_changed[other_uuid].visual
                if visible != pattern[-1]:
                    pattern.append(visible)
        assert tuple(pattern) == contact_pattern, (case_id, role, pattern)
        assert bool(position_changes) == (role == moving_role), (case_id, role, position_changes)
        if case_id == "sight-two-runs":
            assert len(movement_roots) == 1
        if case_id.startswith("sight-range-"):
            seen_at = [event.entity_contacts_changed[other_uuid].position
                       for lineage in native.lineages for event in lineage.events
                       if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == before.observer_uuid
                       and other_uuid in event.entity_contacts_changed]
            if role == "observer":
                assert (20, 3) in seen_at
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
