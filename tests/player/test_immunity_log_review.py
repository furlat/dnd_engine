"""Native immunity outcomes keep their recorded causal event through replay."""

import random

import pytest

from dnd.conditions import Invisible, Poisoned
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.events import EventPhase, EventQueue
from dnd.entity import Entity
from dnd.player.application import capture_application_operation, initialize_audiences
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import PlayerUpdate
from dnd.player.reduction import reduce_operation
from dnd.player.session import Operation, close_session, create_session, snapshot_player_hud
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.enchantment import Bless


def immunity_logs(entry):
    return ([entry] if "**immune**" in entry.compact else []) + [
        found for child in entry.sub_entries for found in immunity_logs(child)]


@pytest.mark.parametrize("nested", [False, True])
def test_immunity_log_belongs_to_its_canceled_condition_event_and_replays(nested):
    random_state = random.getstate()
    random.seed(0)
    session = create_session()
    try:
        target, source = (session.game.entities[identity] for identity in session.player_uuids)
        target.add_condition_immunity("Bless" if nested else "Poisoned")
        catalog = ui_content_manifest()
        audiences, _ = initialize_audiences(session, catalog)
        before = audiences["party"].latest
        start = EventQueue.event_cursor()
        native_log_start = len(session.encounter.combat_log)
        if nested:
            outcome = Bless(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
                template=False).apply()
            assert outcome is not None and not outcome.canceled
        else:
            outcome = target.add_condition(Poisoned(source_entity_uuid=source.uuid,
                target_entity_uuid=target.uuid))
        recorded = tuple(event for _, event in EventQueue.iter_events_since(start))
        canceled = next(event for event in recorded
            if isinstance(event, ConditionApplicationEvent) and event.phase is EventPhase.CANCEL)
        assert canceled.combat_log is not None and "**immune**" in canceled.combat_log.compact
        assert not session.logs.log_appends
        originals = [found for entry in session.encounter.combat_log[native_log_start:]
            for found in immunity_logs(entry)]
        assert originals == [canceled.combat_log]
        operation = Operation(start_cursor=start, end_cursor=EventQueue.event_cursor(),
            roots=tuple(event for event in recorded if event.parent_lineage is None
                and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)),
            hud_by_seat=tuple((seat, snapshot_player_hud(session, audience=audience))
                for seat, audience in session.seats.items()))
        update = capture_application_operation(audiences, operation, catalog)["party"]
        assert update.combat_log_appends == ()
        node = next(node for lineage in update.lineages for node in lineage.events
            if node.uuid == canceled.uuid)
        assert node.canceled and node.combat_log is not None
        assert node.combat_log.compact == canceled.combat_log.compact
        assert node.combat_log.target_uuid == str(target.uuid)
        if nested:
            assert node.parent_lineage is not None
            assert any(parent.lineage_uuid == node.parent_lineage
                and node.lineage_uuid in parent.children_lineages
                for lineage in update.lineages for parent in lineage.events)
        expected = audiences["party"].latest
        detached = PlayerUpdate.model_validate_json(update.model_dump_json())
        close_session(session)
        reset_engine_runtime()
        assert reduce_operation(before, detached) == expected
        assert not any(condition.name == ("Bless" if nested else "Poisoned")
            for condition in expected.actors[target.uuid].conditions)
    finally:
        close_session(session)
        reset_engine_runtime()
        random.setstate(random_state)


@pytest.mark.parametrize("perceived", [False, True])
def test_unidentified_immunity_requires_native_occurrence_perception(perceived):
    random_state = random.getstate()
    session = create_session(encounter_id=None if perceived else "encounter.lantern_crypt")
    try:
        source = next(actor for identity, actor in session.game.entities.items()
            if identity not in session.player_uuids)
        if perceived:
            source.add_condition(Invisible(source_entity_uuid=source.uuid, target_entity_uuid=source.uuid))
            Entity.update_all_entities_senses()
        audience = next(iter(session.seats.values()))
        assert all(source.uuid not in session.game.entities[identity].senses.entities
            or not session.game.entities[identity].senses.entities[source.uuid].visual
            for identity in audience.observers)
        source.add_condition_immunity("Poisoned")
        catalog = ui_content_manifest()
        audiences, _ = initialize_audiences(session, catalog)
        seat = next(iter(audiences))
        before = audiences[seat].latest
        start = EventQueue.event_cursor()
        canceled = source.add_condition(Poisoned(source_entity_uuid=source.uuid, target_entity_uuid=source.uuid))
        assert canceled.canceled and canceled.combat_log is not None
        assert bool(canceled.combat_log.perceiver_uuids & set(map(str, audience.observers))) is perceived
        operation = Operation(start_cursor=start, end_cursor=EventQueue.event_cursor(), roots=(canceled,),
            hud_by_seat=tuple((identity, snapshot_player_hud(session, audience=view))
                for identity, view in session.seats.items()))
        update = capture_application_operation(audiences, operation, catalog)[seat]
        logs = tuple(node.combat_log for group in update.lineages for node in group.events
            if node.combat_log is not None)
        assert update.combat_log_appends == ()
        if perceived:
            assert len(logs) == 1 and logs[0].success is False
            assert logs[0].source_uuid == logs[0].target_uuid == ""
            assert source.name not in logs[0].compact
        else:
            assert update.lineages == ()
            assert audiences[seat].latest == before
        assert reduce_operation(before, PlayerUpdate.model_validate_json(update.model_dump_json())) == audiences[seat].latest
    finally:
        close_session(session)
        reset_engine_runtime()
        random.setstate(random_state)
