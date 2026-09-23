"""Real received owners keep one visual phase across actions, views and seeks."""

from dataclasses import replace
from uuid import uuid4

import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography, bind_motion, sample_choreography
from game.condition_animation import resolve_condition_appearance
from game.condition_draw import compose_condition_layers
from game.condition_types import Activity
from game.condition_media_lifetime import (
    extra_media_members, register_condition_lifetimes, sample_condition_lifetimes,
)
from game.player_facts import ConditionChangeFact, SpellFact, TemporaryHitPointsFact
from game.playback_frame import sample_playback_frame
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from game.player_reduction import reduce_lineage
from tests.game.pending_spell_scenarios import pending_spell_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.fixture(scope="module", params=("bless", "bane", "false_life"))
def captured(request):
    return request.param, pending_spell_history(program=request.param)


def appearances(state, data):
    return {str(actor.uuid): resolve_condition_appearance(actor.conditions, data.condition_recipes,
        data.condition_media, extra_members=extra_media_members(actor)) for actor in state.actors.values()}


@pytest.mark.parametrize("role", ("caster", "target"))
def test_actual_membership_contact_later_heads_removal_and_seek(data, captured, role):
    program, history = captured
    before, roots = player_history(history, role=role)
    records, clock, starts, removed = {}, 500., {}, set()
    applied = False
    for root in roots:
        after = reduce_lineage(before, root)
        motion = bind_motion(before, root, data)
        group = None if motion else bind_choreography(before, root, data)
        records = register_condition_lifetimes(records, before, data, absolute_start_ms=clock,
            lineage=root, choreography=group, motion=motion)
        # Registering the same head or repeating a received instance is not a new application.
        assert records == register_condition_lifetimes(records, before, data, absolute_start_ms=clock,
            lineage=root, choreography=group, motion=motion)
        if isinstance(root.root.fact, SpellFact) and root.root.fact.behavior_id == f"spell.{program}":
            applied = True
            assert group is not None and not group.gaps
            if program in ("bless", "bane"):
                entries = [cue for cue in group.conditions
                    if any(member.behavior_id == f"condition.spell.{program}" for member in cue.after_membership)]
                assert len(entries) == (3 if program == "bless" else 2)
                for cue in entries:
                    owner = next(member.condition_uuid for member in cue.after_membership
                                 if member.behavior_id == f"condition.spell.{program}")
                    assert records[owner].applied_ms == clock + cue.start_ms
                    early = sample_choreography(group, cue.start_ms - .001).displayed
                    actual = sample_choreography(group, cue.start_ms).displayed
                    assert not appearances(early, data)[str(cue.target_uuid)].layers
                    layer = sample_condition_lifetimes(appearances(actual, data), records, data,
                        clock + cue.start_ms)[str(cue.target_uuid)].layers[0]
                    assert layer.owner_uuid == owner and layer.age_ms == 0 and layer.application
            else:
                grants = [node.fact for node in root.events if isinstance(node.fact, TemporaryHitPointsFact)
                          and node.fact.grant is not None and node.fact.grant.source_id == "spell.false_life"]
                assert len(grants) == 1 and grants[0].grant is not None
                owner = grants[0].grant.instance_uuid
                applied_ms = records[owner].applied_ms
                assert applied_ms is not None
                entry = applied_ms - clock
                early = sample_choreography(group, entry - .001).displayed
                actual = sample_choreography(group, entry).displayed
                identity = str(grants[0].entity_uuid)
                assert not appearances(early, data)[identity].layers
                assert len(appearances(actual, data)[identity].layers) == 2
        for owner, record in records.items():
            assert record.applied_ms is not None, "Witnessed applications cannot become quiet initial admissions"
            starts.setdefault(owner, record.applied_ms)
            assert record.applied_ms == starts[owner]
            if record.removed_ms is not None and owner not in removed:
                removed.add(owner)
                at = record.removed_ms
                faded = sample_condition_lifetimes(appearances(after, data), records, data, at + 175)
                layers = [layer for layer in faded[str(record.actor_uuid)].layers if layer.owner_uuid == owner]
                assert len(layers) == 2 and all(layer.alpha == .5 for layer in layers)
                gone = sample_condition_lifetimes(appearances(after, data), records, data, at + 350)
                assert all(layer.owner_uuid != owner for layer in gone[str(record.actor_uuid)].layers)
                assert sample_condition_lifetimes(appearances(after, data), records, data, at + 175) == faded
        assert motion is not None or group is not None
        duration = motion.complete_ms if motion is not None else group.complete_ms if group is not None else 0
        clock += duration + 25
        before = after
    assert applied and starts and removed == set(starts)
    assert not any(appearance.layers for appearance in appearances(before, data).values())


@pytest.mark.parametrize("replacement", ("same_spell", "unrelated"))
def test_real_temporary_hp_replacement_ends_only_old_grant(data, replacement):
    history = pending_spell_history(program="false_life", replace_grant=replacement == "same_spell",
                                    unrelated_grant=replacement == "unrelated")
    before, roots = player_history(history, role="caster")
    records, clock, first, first_removal = {}, 0., None, None
    for root in roots:
        group = bind_choreography(before, root, data)
        records = register_condition_lifetimes(records, before, data, absolute_start_ms=clock,
            lineage=root, choreography=group)
        after = reduce_lineage(before, root)
        if first is not None and first in records and records[first].removed_ms is not None:
            first_removal = records[first].removed_ms
        caster = next(actor for actor in after.actors.values() if actor.name == "Caster")
        if caster.temporary_hp_grant is not None and first is None:
            first = caster.temporary_hp_grant.instance_uuid
        if caster.temporary_hp == 3:
            assert first is not None and records[first].removed_ms is None
        before = after
        clock += group.complete_ms + 25
    assert first is not None and first_removal is not None
    layers = sample_condition_lifetimes(appearances(before, data), records, data, clock + 350)[str(caster.uuid)].layers
    if replacement == "same_spell":
        assert caster.temporary_hp_grant is not None
        assert caster.temporary_hp_grant.instance_uuid != first
        assert len(layers) == 2 and {layer.owner_uuid for layer in layers} == {caster.temporary_hp_grant.instance_uuid}
    else:
        assert caster.temporary_hp_grant is not None
        assert caster.temporary_hp > 0 and caster.temporary_hp_grant.source_id is None
        assert not layers


def active_bless(data):
    state, roots = player_history(pending_spell_history(program="bless"), role="caster")
    for root in roots:
        group = bind_choreography(state, root, data)
        if isinstance(root.root.fact, SpellFact):
            dates = register_condition_lifetimes({}, state, data, absolute_start_ms=1000, lineage=root, choreography=group)
            return reduce_lineage(state, root), dates
        state = reduce_lineage(state, root)
    pytest.fail("Real Bless cast missing")


def test_already_present_and_same_uuid_refresh_do_not_replay_application(data):
    state, dates = active_bless(data)
    quiet = register_condition_lifetimes({}, state, data, absolute_start_ms=9000)
    assert quiet and all(record.applied_ms is None for record in quiet.values())
    selected = sample_condition_lifetimes(appearances(state, data), quiet, data, 9100)
    assert all(not layer.application for appearance in selected.values() for layer in appearance.layers)
    refreshed = replace(state, actors={identity: replace(actor, conditions=tuple(
        replace(condition, event_uuid=uuid4()) for condition in actor.conditions)) for identity, actor in state.actors.items()})
    assert register_condition_lifetimes(dates, refreshed, data, absolute_start_ms=9000) == dates


def test_paged_pair_registration_activity_and_absolute_seek(data):
    pygame.init()
    pygame.display.set_mode((32, 32))
    try:
        state, dates = active_bless(data)
        target = next(actor for actor in state.actors.values() if actor.name == "Target")
        owner = next(record for record in dates.values() if record.actor_uuid == target.uuid)
        assert owner.applied_ms is not None
        body = pygame.Surface((14, 22), pygame.SRCALPHA)
        body.fill((220, 30, 40, 255))
        destination, ground = (73, 82), (80., 104.)
        for quadrant in range(4):
            def pixels(at, facing="N", activity: Activity="idle", selected=None):
                layers = (sample_condition_lifetimes(appearances(state, data), dates, data, at)
                          [str(target.uuid)].layers if selected is None else selected)
                image, point = compose_condition_layers(body, destination, ground, facing, 1, 1,
                    layers, {}, data=data, quadrant=quadrant, floor_ground=ground, activity=activity)
                return pygame.image.tobytes(image, "RGBA"), image.size, point
            application = pixels(owner.applied_ms + 650)
            quiet = pixels(owner.applied_ms + 2600)
            assert application != quiet and quiet[0] != pygame.image.tobytes(body, "RGBA")
            assert pixels(owner.applied_ms + 2600, facing="S") == quiet, "World orbit must not rotate with wearer facing"
            assert pixels(owner.applied_ms + 650) == application
            layers = sample_condition_lifetimes(appearances(state, data), dates, data,
                owner.applied_ms + 2600)[str(target.uuid)].layers
            selective = tuple(replace(layer, layer=layer.layer.model_copy(update={"activeDuring": ("idle",)})) for layer in layers)
            assert pixels(owner.applied_ms + 2600, selected=selective) == quiet
            assert pixels(owner.applied_ms + 2600, activity="jump", selected=selective) == (
                pygame.image.tobytes(body, "RGBA"), body.size, destination)
    finally:
        pygame.quit()


def test_real_frame_compositor_uses_shared_owner_dates_in_all_cameras(data):
    # The app path must receive the clock; testing the phase sampler alone would
    # miss an omitted caller argument and quietly show sustain from the start.
    pygame.init()
    pygame.display.set_mode((640, 480))
    try:
        state, dates = active_bless(data)
        target = next(actor for actor in state.actors.values() if actor.name == "Target")
        record = next(row for row in dates.values() if row.actor_uuid == target.uuid)
        assert record.applied_ms is not None
        rows = {}
        media = load_scene_media(scene_actors(state, data, {}), data, body_rows=rows)
        assert not any(key[0] == "condition" for key in rows), "Paged loops must not enter the body-row cache"
        font = pygame.font.Font(None, 16)
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((4, 6))
            def frame(dates, at):
                return sample_playback_frame(state, None, data, 0, at, camera, {}, media, font, font,
                    condition_lifetimes=dates)
            def actor_pixels(frame):
                command = next(command for command in frame.commands
                    if command.evidence[0] == str(target.uuid) and command.evidence[6] == "actor")
                return pygame.image.tobytes(command.surface, "RGBA"), command.destination
            at = record.applied_ms + 650
            actual = actor_pixels(frame(dates, at))
            quiet = actor_pixels(frame({}, at))
            assert actual != quiet
            actor_pixels(frame(dates, at + 1900))
            assert actor_pixels(frame(dates, at)) == actual
    finally:
        pygame.quit()


def test_registered_ground_layers_do_not_follow_airborne_body_lift(data):
    pygame.init()
    pygame.display.set_mode((32, 32))
    try:
        state, dates = active_bless(data)
        target = next(actor for actor in state.actors.values() if actor.name == "Target")
        record = next(row for row in dates.values() if row.actor_uuid == target.uuid)
        assert record.applied_ms is not None
        layers = sample_condition_lifetimes(appearances(state, data), dates, data,
            record.applied_ms + 2600)[str(target.uuid)].layers
        empty_body = pygame.Surface((14, 22), pygame.SRCALPHA)
        floor = (160., 240.)
        for quadrant in range(4):
            def drawn(lift, attachment):
                selected = tuple(replace(layer, layer=layer.layer.model_copy(update={"attachment": attachment}))
                                 for layer in layers)
                body_anchor = floor[0], floor[1] - lift
                image, point = compose_condition_layers(empty_body, (153, 218 - lift), body_anchor, "SE", 1, 1,
                    selected, {}, data=data, quadrant=quadrant, floor_ground=floor)
                canvas = pygame.Surface((320, 320), pygame.SRCALPHA)
                canvas.blit(image, point)
                return pygame.image.tobytes(canvas, "RGBA")
            assert drawn(0, "ground") == drawn(64, "ground")
            assert drawn(0, "body") != drawn(64, "body")
    finally:
        pygame.quit()


def test_head_admission_prunes_expired_fades_without_mutating_old_seek_clocks(data):
    state, dates = active_bless(data)
    owner, record = next(iter(dates.items()))
    actor = state.actors[record.actor_uuid]
    removed_layers = tuple(layer.layer.assetId for layer in appearances(state, data)[str(actor.uuid)].layers)
    old = {**dates, owner: replace(record, removed_ms=5000, removed_layers=removed_layers)}
    after = replace(state, actors={**state.actors, actor.uuid: replace(actor,
        conditions=tuple(member for member in actor.conditions if member.condition_uuid != owner))})
    previous_sample = sample_condition_lifetimes(appearances(after, data), old, data, 5175)
    assert len(previous_sample[str(actor.uuid)].layers) == 2
    assert all(layer.alpha == .5 for layer in previous_sample[str(actor.uuid)].layers)
    before_end = register_condition_lifetimes(old, after, data, absolute_start_ms=5349.999)
    assert before_end == old
    expired = register_condition_lifetimes(old, after, data, absolute_start_ms=5350)
    assert set(expired) == set(old) - {owner}
    assert old[owner].removed_ms == 5000
    assert sample_condition_lifetimes(appearances(after, data), old, data, 5175) == previous_sample
    # An unknown application age is still an active owner, not an expired tail.
    active = {identity: replace(value, applied_ms=None) for identity, value in expired.items()}
    assert register_condition_lifetimes(active, after, data, absolute_start_ms=9000) == active
    # The map can include this head's future removal before it is sampled.
    pending = {**active, owner: replace(record, removed_ms=10000, removed_layers=removed_layers)}
    assert register_condition_lifetimes(pending, after, data, absolute_start_ms=9000) == pending


@pytest.mark.parametrize("role", ("caster", "target"))
def test_real_haste_recorded_ac_commits_with_condition_contact_and_removal(data, role):
    state, roots = player_history(pending_spell_history(program="haste"), role=role)
    seen = []
    for root in roots:
        relevant = {node.uuid: node.fact for node in root.events if isinstance(node.fact, ConditionChangeFact)
                    and node.fact.condition.behavior_id == "condition.spell.haste"}
        after = reduce_lineage(state, root)
        if relevant:
            group = bind_choreography(state, root, data)
            assert not group.gaps
            for cue in group.conditions:
                fact = relevant.get(cue.event_uuid)
                if fact is None:
                    continue
                expected_ac = fact.condition.resulting_ac
                expected_hp = fact.condition.resulting_max_hp
                assert expected_ac is not None
                prior = (sample_choreography(group, cue.start_ms - .001).displayed
                         if cue.start_ms > 0 else group.before)
                current = sample_choreography(group, cue.start_ms).displayed
                assert prior.actors[cue.target_uuid].armor_class == (10 if expected_ac == 12 else 12)
                assert current.actors[cue.target_uuid].armor_class == expected_ac
                assert current.actors[cue.target_uuid].maximum_hp == (
                    prior.actors[cue.target_uuid].maximum_hp if expected_hp is None else expected_hp)
                assert current.actors[cue.target_uuid].conditions == cue.after_membership
                settled = sample_choreography(group, group.complete_ms).displayed
                assert settled.actors[cue.target_uuid].armor_class == after.actors[cue.target_uuid].armor_class
                assert settled.actors[cue.target_uuid].maximum_hp == after.actors[cue.target_uuid].maximum_hp
                assert sample_choreography(group, cue.start_ms).displayed == current
                seen.append(expected_ac)
        state = after
    assert seen == [12, 10], "Real Haste and concentration loss must both preserve recorded AC"
