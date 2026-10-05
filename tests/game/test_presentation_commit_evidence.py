"""Review traces identify the actual public causes of displayed HP changes."""

import json
from dataclasses import replace
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from devtools.animation_review.trace import group_trace, motion_trace, retained_trace
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, bind_motion, sample_choreography, sample_motion
from game.player_facts import DamageResultFact
from game.presentation_timing import PresentationDependencies, presentation_dependencies
from game.timing_evidence import validate_timing_evidence
from tests.game.construction_scenarios import construction_history
from game.condition_media_lifetime import ConditionMediaLifetime, register_condition_lifetimes
from game.condition_animation import ConditionAppearance, LiveCopyAppearance
from game.condition_media import ResolvedConditionLayer
from game.body_pose_types import ActorPose
from game.scene_actors import scene_actors
from game.animation import sample_idle_body
from game.player_reduction import reduce_lineage
from tests.game.player_helpers import player_history
from tests.game.projectile_life_scenarios import projectile_life_history
from tests.game.movement_scenarios import flight_history, movement_history
from tests.game.visibility_scenarios import visibility_history
from tests.game.pending_spell_scenarios import pending_spell_history
from tests.game.antimagic_scenarios import antimagic_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.mark.parametrize("role", ("caster", "recipient"))
def test_recorded_commit_identifies_damage_packet_at_actual_hp_boundary(data, role):
    before, (lineage,) = player_history(projectile_life_history(), role=role)
    bound = bind_choreography(before, lineage, data)
    trace = json.loads(json.dumps(group_trace(bound)))
    packets = {node.uuid: node for node in lineage.events if isinstance(node.fact, DamageResultFact)}
    assert packets
    witnessed = set()
    for commit in trace['state_commits']:
        at = commit['at_ms']
        for source in commit['nodes']:
            packet = next((row for identity, row in packets.items() if str(identity) == source['uuid']), None)
            if packet is None:
                continue
            witnessed.add(packet.uuid)
            fact = packet.fact
            assert isinstance(fact, DamageResultFact)
            assert source['resolution_ref'] is not None
            assert any(row['event_uuid'] == str(packet.uuid) for row in commit['version_rows'])
            assert source['fact']['stage'] == 'applied'
            earlier = sample_choreography(bound, max(0., at - .001)).displayed
            current = sample_choreography(bound, at).displayed
            # This lethal packet is followed by the native DYING transition at
            # the same boundary, which normalizes its negative HP to zero.
            assert current.actors[fact.target_entity_uuid].normal_hp == 0
            assert fact.resulting_normal_hp < 0
            if at > 0 and fact.applied_damage:
                assert earlier.actors[fact.target_entity_uuid].normal_hp > 0
    assert witnessed == set(packets)
    assert trace['trace_version'] == 2


def test_flight_trace_retains_selected_body_and_landing_clock(data):
    before, (lineage,) = player_history(flight_history(), role='caster')
    motion = bind_motion(before, lineage, data)
    assert motion is not None and motion.body_context is not None
    trace = json.loads(json.dumps(motion_trace(motion)))
    assert trace['body_context'] == motion.body_context.model_dump(mode='json')
    assert trace['recovery_start_ms'] == motion.recovery_start_ms
    assert trace['legs']
    landing = sample_motion(motion, data, trace['complete_ms'])
    assert landing.contact is not None
    assert tuple(trace['legs'][-1]['end']) == landing.contact.grid


def test_retained_trace_preserves_application_and_removal_across_heads(data):
    state, roots = player_history(pending_spell_history(program='bless'), role='caster')
    retained = {}
    now = 0.
    applications = {}
    removals = set()
    for lineage in roots:
        bound = bind_choreography(state, lineage, data)
        retained = register_condition_lifetimes(retained, state, data,
            absolute_start_ms=now, lineage=lineage, choreography=bound)
        rows = json.loads(json.dumps(retained_trace(conditions=retained, spatial={},
            construction={}, concentration={}, items={}, deposits={})))['conditions']
        for identity, row in rows.items():
            if row['applied_ms'] is not None:
                assert applications.setdefault(identity, row['applied_ms']) == row['applied_ms']
            if row['removed_ms'] is not None:
                assert row['removed_ms'] >= applications[identity]
                removals.add(identity)
        state = reduce_lineage(state, lineage)
        now += bound.complete_ms
    assert applications and removals


def test_retained_copy_poses_export_layer_identity_without_local_media(data):
    state, _ = player_history(projectile_life_history(), role='caster')
    actor = scene_actors(state, data, {})[0]
    copies = data.condition_recipes['condition.spell.mirror_image'].persistent.liveCopies
    assert copies is not None
    # A retained copy can carry another selected condition layer as well as
    # its own body. Exercise both ordinary and copied attachment branches.
    layer = next(layer for recipe in data.condition_recipes.values()
                 for layer in recipe.persistent.layers if layer.assetId in data.condition_media)
    resolved = ResolvedConditionLayer(layer, data.condition_media[layer.assetId])
    owner = UUID(actor.contact.actor_uuid)
    appearance = ConditionAppearance(layers=(resolved,),
        live_copies=LiveCopyAppearance(copies, owner, 1, layers=((0, (resolved,)),)))
    pose = ActorPose(replace(actor, condition=appearance),
        sample_idle_body(data, actor.contact, 0), appearance_override=appearance)
    record = ConditionMediaLifetime(owner, owner, 'condition.spell.mirror_image',
        absence_pose=pose, returned_pose=pose)
    trace = retained_trace(conditions={owner: record}, spatial={}, construction={},
        concentration={}, items={}, deposits={})
    serialized = json.dumps(trace)
    assert 'images_by_facing' not in serialized and '"media"' not in serialized
    assert layer.assetId in serialized


@pytest.mark.parametrize('mode', ('walk', 'jump', 'hidden'))
def test_motion_trace_explains_snapshots_without_inventing_native_edges(data, mode):
    if mode == 'hidden':
        state, roots = player_history(visibility_history(), role='observer')
    else:
        state, roots = player_history(movement_history(route=((3, 3), (5, 3)),
            behavior='action.jump' if mode == 'jump' else 'action.move'), role='mover')
    for root in roots:
        motion = bind_motion(state, root, data)
        assert motion is not None
        assert motion.root_uuid == root.root.uuid
        trace = json.loads(json.dumps(motion_trace(motion)))
        rows = trace['state_provenance']
        assert [(row['state_index'], row['at_ms']) for row in rows] == list(enumerate(
            at for at, _ in motion.states))
        assert rows[-1]['origin'] == 'root_reconciliation'
        permitted = {str(node.uuid) for node in root.events}
        for row in rows:
            for source in row['sources']:
                if source['kind'] == 'reduction':
                    assert set(source['event_uuids']) <= permitted
                else:
                    assert source['root_uuid'] in permitted
        if mode == 'jump':
            assert any(row['origin'] == 'jump_launch' for row in rows)
        state = reduce_lineage(state, root)


@pytest.fixture(scope='module')
def stone_history():
    return construction_history(material='stone', break_section=False)


@pytest.mark.parametrize('role', ('caster', 'recipient'))
def test_world_admission_explains_formation_and_clearance_without_early_sections(data, stone_history, role):
    # Public construction events are the input. The output must explain the
    # actual atomic world boundary, not merely report an arbitrary VFX time.
    before, roots = player_history(stone_history, role=role)
    authored = replace(data, construction_media={key: value.model_copy(update={
        'formationCommitMs': 500., 'removalCommitMs': 300.})
        for key, value in data.construction_media.items()})
    formed = cleared = False
    reasons = set()
    for root in roots:
        group = bind_choreography(before, root, authored)
        exported = presentation_dependencies(group)
        adapter = TypeAdapter(tuple[PresentationDependencies, ...])
        assert adapter.validate_json(adapter.dump_json(exported)) == exported
        if exported:
            invalid = json.loads(adapter.dump_json(exported))
            invalid[0]['evidence'][0]['inputs'][0]['reference']['unknown_clock'] = 0
            with pytest.raises(ValidationError, match='unknown_clock'):
                adapter.validate_json(json.dumps(invalid))
        assert not validate_timing_evidence(group.timing_evidence)
        known_objects = set(before.objects) | {obj.placement.object_uuid
            for update in root.world_updates for obj in update.objects}
        for owner in exported:
            assert not validate_timing_evidence(owner.evidence)
            reasons.update(row.reason for row in owner.evidence)
            for row in owner.evidence:
                if row.reason == 'clearance' and row.target.identity in known_objects:
                    assert row.target.kind == 'object'
                for operand in row.inputs:
                    if operand.authored_field and operand.authored_field.startswith('construction_media.'):
                        assert operand.contributor_object_uuid in known_objects
        for update in root.world_updates:
            added = {obj.placement.object_uuid for obj in update.objects} - set(before.objects)
            removed = set(update.objects_removed) & set(before.objects)
            if not added and not removed:
                continue
            commit = next(row for row in group.state_commits if update.event_uuid in row.world_event_uuids)
            floors = [row for row in group.timing_evidence
                if row.target.identity == update.event_uuid and row.reason == 'world_floor']
            assert floors
            assert all(row.at_ms <= commit.at_ms for row in floors)
            assert any(source.producer_index is not None for row in floors for source in row.inputs)
            prior = sample_choreography(group, commit.at_ms - .001).displayed
            current = sample_choreography(group, commit.at_ms).displayed
            if added:
                assert added.isdisjoint(prior.objects)
                assert added <= set(current.objects)
                formed = True
            if removed:
                assert removed <= set(prior.objects)
                assert removed.isdisjoint(current.objects)
                cleared = True
        assert group.after == reduce_lineage(before, root)
        before = group.after
    assert formed and cleared
    assert {'formation', 'clearance', 'world_floor', 'spatial_cause'} <= reasons


def test_dependency_export_rejects_corrupt_producer_instead_of_publishing_a_false_graph(data, stone_history):
    before, roots = player_history(stone_history, role='caster')
    groups = []
    for root in roots:
        group = bind_choreography(before, root, data)
        groups.append(group)
        before = group.after
    group = next(group for group in groups if any(source.producer_index is not None
        for row in group.timing_evidence for source in row.inputs))
    rows = list(group.timing_evidence)
    index = next(index for index, row in enumerate(rows)
                 if any(source.producer_index is not None for source in row.inputs))
    row = rows[index]
    sources = list(row.inputs)
    source_index = next(index for index, source in enumerate(sources) if source.producer_index is not None)
    sources[source_index] = replace(sources[source_index], producer_index=row.index)
    rows[index] = replace(row, inputs=tuple(sources))
    malformed = replace(group, timing_evidence=tuple(rows))
    with pytest.raises(ValueError, match='cyclic producer'):
        presentation_dependencies(malformed)


def test_condition_transition_export_keeps_actual_completion_and_public_owner(data):
    before, lineages = player_history(antimagic_history(), role='recipient')
    seen = []
    for lineage in lineages:
        bound = bind_choreography(before, lineage, data)
        exported = presentation_dependencies(bound)
        for condition in bound.conditions:
            if not condition.timing_evidence:
                continue
            tables = tuple(row for row in exported if row.scope == 'condition_transition'
                and row.owner_uuid == condition.event_uuid)
            assert len(tables) == 1
            table = tables[0]
            assert not validate_timing_evidence(table.evidence)
            assert table.evidence[-1].at_ms == condition.complete_ms
            seen.append(condition.event_uuid)
        before = reduce_lineage(before, lineage)
    assert seen
