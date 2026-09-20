"""Saved subjective injuries and observed tiles remain distinct after teardown."""

import json

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue
from dnd.entity import Entity
from dnd.types.world import OccupancyLayer
from game.player_facts import AttackFact, DamageFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import reduce_interval, reduce_lineage as reduce_native_lineage
from game.replay import RecordedSequence
from tests.game.body_residue_scenarios import body_residue_history, hidden_residue_history


@pytest.mark.parametrize("weapon,pattern", (("weapon.dagger", "piercing"), ("weapon.longsword", "slashing"), ("weapon.mace", "blunt")))
@pytest.mark.parametrize("critical", (False, True))
def test_real_weapon_hits_retain_pattern_critical_and_floor_geometry_after_teardown(weapon, pattern, critical):
    history = body_residue_history(weapon=weapon, critical=critical, hits=1)
    for role in ("walker", "donor"):
        _, state, roots = saved_public(history.views[role])
        releases = [node.fact.body_release for root in roots for node in root.events
                    if isinstance(node.fact, DamageFact) and node.fact.body_release is not None]
        assert len(releases) == 1
        release = releases[0]
        assert release.pattern == pattern and release.critical_hit is critical
        for root in roots:
            state = reduce_lineage(state, root)
        for cell in {cell for region in release.regions for cell in region.positions}:
            residue, = state.tiles[cell].residues
            assert residue.amount == 1 and residue.contributions
            assert sum(row.amount for row in residue.contributions) == 1
    assert EventQueue.event_cursor() == 0


@pytest.fixture(scope="module", params=("blood", "bone", "corrosive"))
def injury_history(request):
    return body_residue_history(profile=request.param), request.param


def saved_public(native: RecordedSequence):
    restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    payload = encode_player_sequence(project_sequence(restored))
    return payload, *decode_player_sequence(payload)


@pytest.mark.parametrize("options,identity,release_id,residue_id", (
    ({"profile": "bone", "fixed_skeleton": True},
     "content.neurodragon:creature:creature.skeleton_archer@1", "body.bone", "residue.bone_fragments"),
    ({"profile": "corrosive", "creature_identity": "content.srd_5_1_cc:creature:creature.orc@1"},
     "content.srd_5_1_cc:creature:creature.orc@1", "body.corrosive_blood", "residue.corrosive_demonic_blood"),
))
def test_review_creatures_retain_real_identity_and_material_after_seven_attacks(options, identity, release_id, residue_id):
    history = body_residue_history(**options, hits=7, crossings=False)
    donor = history.views["donor"].initialization.observer_uuid
    for native in history.views.values():
        _, before, roots = saved_public(native)
        assert before.actors[donor].creature_content_ref == identity
        injuries = [node.fact for root in roots for node in root.events
                    if isinstance(node.fact, DamageFact) and node.fact.body_release is not None]
        assert len(injuries) == 7
        assert all(injury.body_release.release_id == release_id for injury in injuries)
        after = before
        for root in roots:
            after = reduce_lineage(after, root)
        residue, = after.tiles[(5, 3)].residues
        assert residue.residue_id == residue_id and residue.amount == 1
        assert after.actors[donor].normal_hp == before.actors[donor].normal_hp - 14
    assert EventQueue.event_cursor() == 0


@pytest.mark.parametrize("role", ("donor", "walker"))
def test_repeated_native_injuries_leave_one_persistent_residue_and_replay_crossings(injury_history, role):
    history, profile = injury_history
    native = history.views[role]
    _, before, roots = saved_public(native)
    donor = history.views["donor"].initialization.observer_uuid
    walker = history.views["walker"].initialization.observer_uuid
    assert before.tiles[(5, 3)].residues == ()
    expected_release = {"blood": "body.blood", "bone": "body.bone", "corrosive": "body.corrosive_blood"}[profile]
    expected_residue = {"blood": "residue.blood", "bone": "residue.bone_fragments",
                        "corrosive": "residue.corrosive_demonic_blood"}[profile]
    injuries = [node.fact for root in roots for node in root.events
                if isinstance(node.fact, DamageFact) and node.fact.body_release is not None]
    assert len(injuries) == 2
    assert all(row.target_entity_uuid == donor and row.body_release is not None
               and row.body_release.release_id == expected_release
               and row.body_release.position == row.body_release.deposited_position == (5, 3)
               and row.body_release.occupancy_layer is OccupancyLayer.GROUND for row in injuries)
    state = before
    memberships = []
    for root in roots:
        state = reduce_lineage(state, root)
        if state.tiles[(5, 3)].residues:
            residue, = state.tiles[(5, 3)].residues
            assert residue.residue_id == expected_residue and residue.description
            memberships.append(residue.condition_uuid)
    assert memberships and len(set(memberships)) == 1
    assert state.actors[donor].last_visual_position == (6, 3)
    assert state.actors[walker].normal_hp == before.actors[walker].normal_hp - (4 if profile == "corrosive" else 0)
    crossing_damage = [node.fact for root in roots for node in root.events
                       if isinstance(node.fact, DamageFact) and node.fact.stage == "applied"
                       and node.fact.target_entity_uuid == walker]
    assert len(crossing_damage) == (2 if profile == "corrosive" else 0)
    reference, _ = reduce_interval(None, native.initialization)
    for root in native.lineages:
        reference = reduce_native_lineage(reference, root)
    assert state.tiles[(5, 3)] == reference.tiles[(5, 3)]
    assert state.tiles[(5, 3)].residues[0].amount == (2 if profile == "blood" else 1)
    assert before.tiles[(5, 3)].residues == ()
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_seven_recorded_hits_saturate_blood_for_both_observers_without_reapplying_condition():
    history = body_residue_history(hits=7)
    for native in history.views.values():
        _, state, roots = saved_public(native)
        amounts, identities = [], set()
        for root in roots:
            state = reduce_lineage(state, root)
            if isinstance(root.root.fact, AttackFact):
                residue, = state.tiles[(5, 3)].residues
                amounts.append(residue.amount)
                identities.add(residue.condition_uuid)
        assert amounts == [1, 2, 3, 4, 5, 5, 5]
        assert len(identities) == 1
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_blood_and_bone_coexist_with_the_same_observed_spike_fixture():
    history = body_residue_history(mixed=True)
    _, before, roots = saved_public(history.views["walker"])
    assert before.senses is not None
    fixture_ids = set(before.senses.spatial_effects)
    assert len(fixture_ids) == 1
    state = before
    releases = []
    for root in roots:
        releases.extend(node.fact.body_release.release_id for node in root.events
                        if isinstance(node.fact, DamageFact) and node.fact.body_release is not None)
        state = reduce_lineage(state, root)
    assert sorted(releases) == ["body.blood", "body.blood", "body.bone"]
    assert {row.residue_id for row in state.tiles[(5, 3)].residues} == {
        "residue.blood", "residue.bone_fragments"}
    assert state.senses is not None and set(state.senses.spatial_effects) == fixture_ids
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


@pytest.mark.parametrize("first_sight", (False, True), ids=("visible-stain", "later-sight"))
def test_hidden_donor_never_leaks_through_a_visible_or_later_observed_residue(first_sight):
    history = hidden_residue_history(first_sight=first_sight)
    donor = history.views["donor"].initialization.observer_uuid
    payload, before, roots = saved_public(history.views["witness"])
    assert str(donor).encode() not in payload and b"Unseen donor" not in payload
    assert donor not in before.actors and before.tiles[(5, 3)].residues == ()
    assert before.senses is not None and not before.senses.spatial_effects
    state = before
    observed_residue = False
    for root in roots:
        assert not any(isinstance(node.fact, DamageFact) for node in root.events)
        previous = state
        state = reduce_lineage(state, root)
        assert donor not in state.actors
        assert state.senses is not None and not state.senses.spatial_effects
        if state.tiles[(5, 3)].residues:
            observed_residue = True
            assert (5, 3) in state.senses.visible
            if first_sight and not previous.tiles[(5, 3)].residues:
                assert previous.senses is not None and (5, 3) not in previous.senses.visible
    assert observed_residue
    assert [row.residue_id for row in state.tiles[(5, 3)].residues] == ["residue.blood"]
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_recordings_without_release_and_residue_fields_remain_readable(injury_history):
    history, _ = injury_history
    payload = json.loads(history.views["walker"].model_dump_json())
    pending = [payload]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            value.pop("body_release", None)
            value.pop("residues", None)
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    native = RecordedSequence.model_validate_json(json.dumps(payload), context=PASSIVE_EVENT_REPLAY)
    _, state, roots = saved_public(native)
    for root in roots:
        assert all(node.fact.body_release is None for node in root.events if isinstance(node.fact, DamageFact))
        state = reduce_lineage(state, root)
    assert all(tile.residues == () for tile in state.tiles.values())
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


@pytest.mark.parametrize("layout,forward,origin_height", (
    ("closed-door", False, 0), ("open-door", True, 0),
    ("raised", True, 2), ("ledge", False, 2),
))
def test_receiving_regions_match_authored_supports_and_doors_for_both_saved_views(layout, forward, origin_height):
    history = body_residue_history(layout=layout, crossings=False, hits=1)
    for native in history.views.values():
        _, state, roots = saved_public(native)
        origin = (16, 21) if layout == "raised" else (18, 21) if layout == "ledge" else (5, 3)
        forward_cell = (origin[0] + 1, origin[1])
        assert state.tiles[origin].elevation_steps == origin_height
        if layout == "raised":
            assert all(state.tiles[cell].elevation_steps == 2 for cell in ((15, 21), (16, 21), (17, 21)))
        if layout in ("closed-door", "open-door"):
            door, = [obj for obj in state.objects.values() if obj.item.item_id == "environment.directional_door"]
            assert door.item.is_open is (layout == "open-door")
        release, = [node.fact.body_release for root in roots for node in root.events
                    if isinstance(node.fact, DamageFact) and node.fact.body_release is not None]
        assert (forward_cell in {cell for region in release.regions for cell in region.positions}) is forward
        assert {region.elevation_steps for region in release.regions} == {origin_height}
