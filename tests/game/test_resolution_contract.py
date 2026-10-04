"""Saved player facts preserve exact damage ownership without live rule objects."""

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from dnd.core.effect_types import EventResolutionRef
from dnd.core.events import EventQueue
from game.player_facts import DamageRequestFact, DamageResultFact, PlayerSequence, SensoryFact, SpatialFact
from game.player_projection import project_sequence
from game.animation_data import load_animation_data
from game.attack import bind_attack
from game.combat import BoundCast
from game.presentation import reduce_interval, reduce_lineage as reduce_native_lineage
from dnd.core.events import TakeDamageEvent
from tests.game.damage_resolution_scenarios import resolution_history
from game.choreography import BoundChoreography, bind_choreography, sample_choreography, walk_bound_timelines
from game.event_record import decode_event, encode_event
from game.player_reduction import decode_player_sequence, encode_player_sequence, index_player_lineage, reduce_lineage
from tests.game.scenarios import attack_history


@pytest.fixture(scope="module")
def received_attack():
    history = attack_history("weapon.longsword", 17)
    return project_sequence(history.views["hero"])


def test_current_player_archive_preserves_ordered_native_result_ownership(received_attack):
    payload = encode_player_sequence(received_attack)
    before, (lineage,) = decode_player_sequence(payload)
    assert EventQueue.event_cursor() == 0
    index = index_player_lineage(lineage)
    reference = EventResolutionRef(lineage_uuid=lineage.root.lineage_uuid)
    results = index.results[reference]
    assert results
    assert all(isinstance(row.fact, DamageResultFact) for row in results)
    assert [index.source_order[row.uuid] for row in results] == sorted(index.source_order[row.uuid] for row in results)
    assert all(row.resolution_ref == reference for row in lineage.events
               if isinstance(row.fact, (DamageRequestFact, DamageResultFact)))
    assert PlayerSequence.model_validate_json(payload) == received_attack
    assert before.observer_uuid == received_attack.initialization.observer_uuid


def test_player_v1_does_not_infer_damage_ownership_from_an_attack_parent(received_attack):
    document = received_attack.model_dump(mode="json")
    document["schema_version"] = 1
    for node in document["initialization"]["nodes"]:
        node.pop("resolution_ref", None)
    for lineage in document["lineages"]:
        for node in [lineage["root"], *lineage["events"]]:
            node.pop("resolution_ref", None)
    with pytest.raises(ValueError, match="lacks unambiguous resolution ownership"):
        decode_player_sequence(json.dumps(document).encode())
    assert EventQueue.event_cursor() == 0


def test_ambiguous_legacy_callback_reports_the_exact_missing_owner(received_attack):
    document = received_attack.model_dump(mode="json")
    document["schema_version"] = 1
    for lineage in document["lineages"]:
        for node in lineage["events"]:
            if node["fact"] and node["fact"]["kind"] == "damage":
                node.pop("resolution_ref", None)
                if node["fact"]["stage"] == "taken":
                    # The old packet did not disclose its immediate cause.
                    node["parent_lineage"] = "00000000-0000-0000-0000-000000000001"
    with pytest.raises(ValueError, match="lacks unambiguous resolution ownership"):
        decode_player_sequence(json.dumps(document).encode())


def test_observation_references_only_name_disclosed_operations(received_attack):
    disclosed = {node.lineage_uuid for node in received_attack.initialization.nodes if node.fact is not None}
    for lineage in received_attack.lineages:
        disclosed.update(node.lineage_uuid for node in lineage.events if node.fact is not None)
        versions = {row.event_uuid: row for row in lineage.version_rows}
        for node in lineage.events:
            if node.resolution_ref is not None:
                assert node.resolution_ref.lineage_uuid in disclosed
            if isinstance(node.fact, SensoryFact):
                for reference in node.fact.observed_changes:
                    source = versions[reference.source_event_uuid]
                    assert source.source_index == reference.source_index
                    assert source.lineage_uuid in disclosed
                    if reference.resolution_ref is not None:
                        assert reference.resolution_ref.lineage_uuid in disclosed


def test_movement_commit_versions_survive_current_and_legacy_player_archives():
    history = attack_history("weapon.longsword", 17, opportunity=True, whole_movement=True)
    sequence = project_sequence(history.views["hero"])
    before, roots = decode_player_sequence(encode_player_sequence(sequence))
    state = before
    commits = []
    for lineage in roots:
        versions = {row.event_uuid: row for row in lineage.version_rows}
        for node in lineage.events:
            if isinstance(node.fact, SpatialFact) and node.fact.entity_uuid is not None:
                assert node.fact.commit_event_uuid in versions
                assert versions[node.fact.commit_event_uuid].source_index <= versions[node.uuid].source_index
                commits.append(node.fact.commit_event_uuid)
        state = reduce_lineage(state, lineage)
    assert commits
    legacy = sequence.model_dump(mode="json")
    legacy["schema_version"] = 1
    for group in (legacy["initialization"], *legacy["lineages"]):
        nodes = group.get("events", group.get("nodes", []))
        for node in nodes:
            if node["fact"] and node["fact"]["kind"] == "spatial":
                node["fact"].pop("commit_event_uuid", None)
    restored, migrated = decode_player_sequence(json.dumps(legacy).encode())
    for lineage in migrated:
        restored = reduce_lineage(restored, lineage)
    assert restored == state
    assert EventQueue.event_cursor() == 0


def test_one_attack_retains_multiple_results_without_duplicate_injury():
    # Keep this public multi-result fixture nonlethal. Seed 17 now kills the
    # canonical 7 HP Goblin; its retained life commit would contradict an added
    # later damage packet carrying a different final HP.
    history = attack_history("weapon.longsword", 10)
    before, (original,) = decode_player_sequence(encode_player_sequence(project_sequence(history.views["hero"])))
    first = next(node for node in original.events if isinstance(node.fact, DamageResultFact))
    packet = first.fact
    assert isinstance(packet, DamageResultFact)
    assert packet.applied_damage == 1 and packet.resulting_normal_hp == 6
    extra = replace(first, uuid=uuid4(), lineage_uuid=uuid4(), fact=replace(packet,
        applied_damage=1, resulting_normal_hp=packet.resulting_normal_hp-1))
    events = []
    for node in original.events:
        if node.lineage_uuid == first.parent_lineage:
            node = replace(node, children_lineages=(*node.children_lineages, extra.lineage_uuid))
        events.append(node)
        if node.uuid == first.uuid:
            events.append(extra)
    first_version = next(row for row in original.version_rows if row.event_uuid == first.uuid)
    versions = [replace(row, source_index=row.source_index+1)
                if row.source_index > first_version.source_index else row for row in original.version_rows]
    versions.append(replace(first_version, source_index=first_version.source_index+1,
                            event_uuid=extra.uuid, lineage_uuid=extra.lineage_uuid))
    lineage = replace(original, events=tuple(events), end_cursor=original.end_cursor+1,
                      version_rows=tuple(sorted(versions, key=lambda row: row.source_index)))
    data = load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))
    bound = bind_attack(before, lineage, data)
    assert bound is not None
    assert [node.uuid for node in bound.timeline.results] == [first.uuid, extra.uuid]
    group = bind_choreography(before, lineage, data)
    assert len(group.nodes) == 1 and not group.damage
    assert bound.timeline.damage_timing is not None
    displayed = sample_choreography(group, bound.timeline.damage_timing.hp_ms).displayed
    assert displayed.actors[packet.target_entity_uuid].normal_hp == packet.resulting_normal_hp-1
    assert displayed == sample_choreography(group, bound.timeline.damage_timing.hp_ms).displayed


def test_legacy_native_attack_reprojects_without_live_runtime():
    history = attack_history("weapon.longsword", 17)
    native = history.views["hero"]
    current = project_sequence(native)
    old_lineages = []
    for lineage in native.lineages:
        events = []
        for event in lineage.events:
            payload = encode_event(event)
            payload.pop("resolution_ref", None)
            events.append(decode_event(payload))
        old_lineages.append(replace(lineage,
            events=tuple(events), root=next(row for row in events if row.uuid == lineage.root.uuid)))
    with pytest.raises(ValueError, match="lacks unambiguous resolution ownership"):
        project_sequence(native.model_copy(update={"lineages": tuple(old_lineages)}))
    assert EventQueue.event_cursor() == 0


def test_real_retaliation_keeps_its_own_results_and_ambiguous_archives_diagnose():
    native = resolution_history('retaliation')
    public = project_sequence(native)
    before, (lineage,) = decode_player_sequence(encode_player_sequence(public))
    requests = [node for node in lineage.events if isinstance(node.fact, DamageRequestFact)]
    assert len(requests) == 2 and len({node.resolution_ref for node in requests}) == 2
    retaliation, = (node for node in requests if node.resolution_ref != lineage.root.resolution_ref)
    assert retaliation.parent_lineage == lineage.root.lineage_uuid
    assert retaliation.resolution_ref == EventResolutionRef(lineage_uuid=retaliation.lineage_uuid)
    group = bind_choreography(before, lineage, load_animation_data())
    assert not group.gaps and len(group.nodes) == 1 and len(group.damage) == 1
    assert group.damage[0].applied_damage == 5
    assert sample_choreography(group, group.complete_ms).displayed.actors == reduce_lineage(before, lineage).actors
    old = public.model_dump(mode='json')
    old['schema_version'] = 1
    for row in old['lineages']:
        for node in [row['root'], *row['events']]:
            node.pop('resolution_ref', None)
    with pytest.raises(ValueError, match='lacks unambiguous resolution ownership'):
        decode_player_sequence(json.dumps(old).encode())
    old_events = tuple(decode_event({key: value for key, value in encode_event(event).items()
                                    if key != 'resolution_ref'}) for event in native.lineages[0].events)
    old_root = replace(native.lineages[0], events=old_events,
        root=next(event for event in old_events if event.uuid == native.lineages[0].root.uuid))
    with pytest.raises(ValueError, match='lacks unambiguous resolution ownership'):
        project_sequence(native.model_copy(update={'lineages': (old_root,)}))
    # Native state reduction does not require invented presentation causality.
    original_before, _ = reduce_interval(None, native.initialization)
    assert reduce_native_lineage(original_before, old_root) == reduce_native_lineage(original_before, native.lineages[0])
    assert EventQueue.event_cursor() == 0


@pytest.mark.parametrize('kind', ['push', 'walk'])
@pytest.mark.parametrize('number_frame', [0, 3])
def test_spike_growth_entries_have_independent_owners_and_present_each_result_once(kind, number_frame):
    native = resolution_history(kind)
    requests = [event for event in native.lineages[0].events if isinstance(event, TakeDamageEvent)]
    assert sorted(event.final_damage for event in requests) == ([2, 2, 2] if kind == 'push' else [2, 2])
    exposures = [event for event in requests if event.resolution_ref == EventResolutionRef(lineage_uuid=event.lineage_uuid)]
    assert len(exposures) == 2
    assert all(event.effect_origin is not None for event in exposures)
    assert exposures[0].effect_origin == exposures[1].effect_origin
    before, (lineage,) = decode_player_sequence(encode_player_sequence(project_sequence(native)))
    data = load_animation_data()
    data = replace(data, damage_context=data.damage_context.model_copy(update={'numberFrame': number_frame}))
    group = bind_choreography(before, lineage, data)
    assert not group.gaps
    cues = [cue for visit in walk_bound_timelines(choreography=group)
            if isinstance(visit.timeline, BoundChoreography) for cue in visit.timeline.damage]
    assert [cue.applied_damage for cue in cues] == [2, 2]
    if kind == 'push':
        cast = next(row.bound for row in group.nodes if isinstance(row.bound, BoundCast))
        assert sum(application.source.damage_total or 0 for application in cast.timeline.applications) == 2
    index = index_player_lineage(lineage)
    owned_results = [result.uuid for results in index.results.values() for result in results]
    assert len(owned_results) == len(set(owned_results)) == len(requests)
    final = sample_choreography(group, group.complete_ms)
    assert final.displayed.actors == reduce_lineage(before, lineage).actors
    commits = [(visit.offset_ms + cue.timing.hp_ms, cue.resulting_hp)
               for visit in walk_bound_timelines(choreography=group)
               if isinstance(visit.timeline, BoundChoreography) for cue in visit.timeline.damage]
    if kind == 'push':
        node = next(row for row in group.nodes if isinstance(row.bound, BoundCast))
        application, = node.bound.timeline.applications
        assert application.hp_ms is not None
        commits.insert(0, (node.start_ms + application.hp_ms, 18))
        displacement, = group.forced_movement
        assert displacement.start_ms >= commits[0][0]
        for when in (0., node.start_ms + application.travel_end_ms,
                     commits[0][0]-.001, displacement.start_ms, displacement.travel_start_ms):
            sample = sample_choreography(group, when)
            assert sample.displayed.actors[exposures[0].target_entity_uuid].last_visual_position == (4, 3)
            contact = next((row for row in sample.contacts
                            if row.actor_uuid == str(exposures[0].target_entity_uuid)), None)
            assert contact is None or contact.grid == (4, 3)
    assert all(first[0] < second[0] for first, second in zip(commits, commits[1:]))
    target_uuid = exposures[0].target_entity_uuid
    previous = before.actors[target_uuid].normal_hp
    for when, hp in commits:
        if when > 0:
            assert sample_choreography(group, when-.001).displayed.actors[target_uuid].normal_hp == previous
        # Nested timeline subtraction can round the exact global boundary down.
        assert sample_choreography(group, when+1e-7).displayed.actors[target_uuid].normal_hp == hp
        previous = hp
    for when, hp in reversed(commits):
        assert sample_choreography(group, when+1e-7).displayed.actors[target_uuid].normal_hp == hp
    assert sample_choreography(group, group.complete_ms) == final
