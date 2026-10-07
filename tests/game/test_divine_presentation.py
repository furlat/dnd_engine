"""Native Holy outcomes survive passive replay and drive authored media clocks."""

from dataclasses import replace
from uuid import uuid4

import numpy as np
import pygame
import pytest

from dnd.core.condition_types import ConditionCategory
from dnd.player.actor_facts import ConditionFact
from game.animation import ActorContact, feedback_identity, sample_cast
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.cast_media import cast_media_draw_commands
from game.combat import BoundCast
from game.cast_media import cast_media_placement
from game.projection import Camera, project_screen
from game.condition_draw import compose_condition_layers
from game.condition_animation import resolve_condition_appearance
from game.condition_media_lifetime import ConditionMediaLifetime, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media
from dnd.player.recorded import project_sequence
from dnd.player.facts import SensoryFact, VersionRow
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from tests.game.divine_scenarios import divine_history


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize("program", ("beacon_of_hope", "daylight", "mass_healing_word", "divine_word"))
@pytest.mark.parametrize("observer", ("caster", "recipient"))
def test_native_selected_outcomes_are_replayable_with_no_missing_media(data, program, observer):
    history = divine_history(program=program, multiple_targets=program == "mass_healing_word")
    before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[observer])))
    native_targets = set()
    witnessed_conditions = set()
    witnessed_spatial = set()
    for root in roots:
        group = bind_choreography(before, root, data)
        assert not group.gaps
        for clip in group.nodes:
            if isinstance(clip.bound, BoundCast):
                timeline = clip.bound.timeline
                assert timeline.recipe.definitionRef.content_id == "spell." + program
                native_targets.update(feedback_identity(application.target) for application in timeline.source.applications)
                for track in timeline.recipe.media:
                    assert track.assetId in data.projectile_assets
                if program == "mass_healing_word":
                    assert len(timeline.source.applications) == 2
                    assert timeline.recipe.contact is not None
                    assert timeline.recipe.contact.delayMs == 21 * 1000 / 32
                if program == "divine_word":
                    assert timeline.recipe.contact is not None
                    assert timeline.recipe.contact.delayMs == 29 * 1000 / 32
        before = reduce_lineage(before, root)
        witnessed_conditions.update(condition.behavior_id for actor in before.actors.values()
            for condition in actor.conditions)
        if before.senses is not None:
            witnessed_spatial.update(effect.content_ref.content_id for effect in before.senses.spatial_effects.values())
    assert native_targets or program in ("daylight", "beacon_of_hope")
    if program == "beacon_of_hope":
        assert "condition.spell.beacon_of_hope" in witnessed_conditions
    if program == "daylight":
        assert "spatial_effect.spell.daylight" in witnessed_spatial
    actors = {actor.name.lower(): actor for actor in before.actors.values()}
    if program == "mass_healing_word":
        assert actors["recipient"].normal_hp > actors["bystander"].normal_hp
        assert actors["second"].normal_hp > actors["bystander"].normal_hp
    if program == "divine_word":
        assert {"condition.blinded", "condition.deafened"} <= {
            condition.behavior_id for condition in actors["recipient"].conditions}
        assert not actors["bystander"].conditions


def test_beacon_witnessed_formation_enters_hold_and_clear_preserves_current_frame(data):
    actor, owner = uuid4(), uuid4()
    fact = ConditionFact(condition_uuid=owner, category=ConditionCategory.CONDITION,
        behavior_id="condition.spell.beacon_of_hope", event_uuid=uuid4(), name="Beacon of Hope",
        resulting_max_hp=None, resulting_ac=None)
    appearance = resolve_condition_appearance((fact,), data.condition_recipes, data.condition_media)
    assert len(appearance.layers) == 2 and not appearance.unsupported
    records = {owner: ConditionMediaLifetime(actor, owner, "condition.spell.beacon_of_hope", applied_ms=0)}
    layers = sample_condition_lifetimes({str(actor): appearance}, records, data, 4000)[str(actor)].layers
    assert all(sample_condition_media(data, layer)[0].asset_id.startswith("divine.beacon_of_hope.hold") for layer in layers)
    removed = {owner: replace(records[owner], removed_ms=4100,
        removed_layers=tuple(layer.layer.assetId for layer in layers))}
    empty = resolve_condition_appearance((), data.condition_recipes, data.condition_media)
    tail = sample_condition_lifetimes({str(actor): empty}, removed, data, 4400)[str(actor)].layers
    assert len(tail) == 2
    assert all(sample_condition_media(data, layer)[0].alpha == pytest.approx(.5) for layer in tail)
    assert not sample_condition_lifetimes({str(actor): empty}, removed, data, 4700)[str(actor)].layers


@pytest.mark.parametrize("observer", ("caster", "recipient"))
@pytest.mark.parametrize("split_update", (False, True))
def test_daylight_lighting_clears_with_the_visible_field_not_before(data, observer, split_update):
    history = divine_history(program="daylight")
    before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[observer])))
    checked = False
    for root in roots:
        after = reduce_lineage(before, root)
        assert before.senses is not None and after.senses is not None
        removed = before.senses.spatial_effects.keys() - after.senses.spatial_effects.keys()
        if removed:
            if split_update:
                # Older public recordings deliver lighting and field removal
                # separately, under the same real removal ancestry. Preserve
                # all received values; only their packet grouping changes.
                source = next(node for node in root.events if isinstance(node.fact, SensoryFact)
                    and node.fact.effective_light_levels_changed and node.fact.spatial_effects_removed)
                fact = source.fact
                assert isinstance(fact, SensoryFact)
                lighting = replace(source, fact=replace(fact, spatial_effects_removed=frozenset()))
                field = replace(source, uuid=uuid4(), lineage_uuid=uuid4(),
                    fact=replace(fact, effective_light_levels_changed={}))
                events = tuple(lighting if node.uuid == source.uuid else
                    replace(node, children_lineages=(*node.children_lineages, field.lineage_uuid))
                    if node.lineage_uuid == source.parent_lineage else node for node in root.events)
                source_index = max(row.source_index for row in root.version_rows) + 1
                root = replace(root, events=(*events, field), end_cursor=max(root.end_cursor, source_index + 1),
                    version_rows=(*root.version_rows, VersionRow(event_uuid=field.uuid,
                        lineage_uuid=field.lineage_uuid,
                        source_index=source_index)))
                assert reduce_lineage(before, root).senses == after.senses
            group = bind_choreography(before, root, data)
            fade = data.spatial_media["spatial_effect.spell.daylight"].removalCommitMs
            assert fade > 0
            for at in (0., fade / 2, fade - .001):
                fading = sample_choreography(group, at).displayed
                assert fading.senses is not None
                assert removed <= fading.senses.spatial_effects.keys()
                assert fading.senses.effective_light_levels == before.senses.effective_light_levels
            cleared = sample_choreography(group, fade).displayed
            assert cleared.senses is not None
            assert cleared.senses.effective_light_levels == after.senses.effective_light_levels
            assert not removed & cleared.senses.spatial_effects.keys()
            assert sample_choreography(group, 0).displayed.senses == before.senses
            checked = True
        before = after
    assert checked


@pytest.mark.parametrize("program", ("mass_healing_word", "divine_word"))
def test_native_recipient_banks_share_the_recipients_ground_origin_in_every_camera(data, program):
    history = divine_history(program=program, multiple_targets=program == "mass_healing_word")
    before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views["caster"])))
    checked = 0
    for root in roots:
        group = bind_choreography(before, root, data)
        for clip in group.nodes:
            if not isinstance(clip.bound, BoundCast):
                continue
            timeline = clip.bound.timeline
            for application in timeline.source.applications:
                target = application.target
                for track in timeline.recipe.media:
                    if not track.attachment.startswith("target_"):
                        continue
                    for quadrant in range(4):
                        camera = Camera(quadrant=quadrant, zoom=.75)
                        placement = cast_media_placement(timeline, track, target, camera)
                        assert placement.anchor == project_screen(target.grid, camera,
                            elevation_steps=target.elevation_steps)
                        # Native exports are already calibrated to the 128px world tile.
                        assert placement.scale == pytest.approx(camera.zoom)
                        checked += 1
        before = reduce_lineage(before, root)
    assert checked == (16 if program == "mass_healing_word" else 8)


def test_global_gold_symbols_have_distinct_measured_head_tracks(data):
    members = tuple(ConditionFact(condition_uuid=uuid4(), category=ConditionCategory.CONDITION,
        behavior_id="condition." + name, event_uuid=uuid4(), name=name,
        resulting_max_hp=None, resulting_ac=None) for name in ("blinded", "deafened"))
    appearance = resolve_condition_appearance(members, data.condition_recipes, data.condition_media)
    assert not appearance.unsupported and len(appearance.layers) == 4
    for layer in appearance.layers:
        assert layer.layer.attachment == "head"
        assert layer.media.actor_top_clearance_px is None
        assert layer.media.removal_fade_ms == 600
        assert layer.layer.offsetY == (-11.5 if layer.layer.category == "deafened" else -4)
        first, = sample_condition_media(data, replace(layer, application=True, age_ms=0))
        repeated, = sample_condition_media(data, replace(layer, application=True, age_ms=2000))
        assert first.frame == repeated.frame == 0
        assert "divine_condition_" in first.asset_id


def test_one_blind_owner_clearing_cannot_fade_another_effective_owner(data):
    actor, first, second = uuid4(), uuid4(), uuid4()
    original = ConditionFact(condition_uuid=first, category=ConditionCategory.CONDITION,
        behavior_id="condition.blinded", event_uuid=uuid4(), name="Blinded",
        resulting_max_hp=None, resulting_ac=None)
    surviving = replace(original, condition_uuid=second)
    appearance = resolve_condition_appearance((surviving,), data.condition_recipes, data.condition_media)
    recipe = data.condition_recipes["condition.blinded"]
    records = {first: ConditionMediaLifetime(actor, first, "condition.blinded", applied_ms=0,
        removed_ms=2500, removed_layers=tuple(layer.assetId for layer in recipe.persistent.layers)),
        second: ConditionMediaLifetime(actor, second, "condition.blinded", applied_ms=500)}
    sampled = sample_condition_lifetimes({str(actor): appearance}, records, data, 2800)[str(actor)]
    assert len(sampled.layers) == 2
    assert all(layer.owner_uuid == second and layer.alpha == 1 for layer in sampled.layers)


def test_gold_head_mark_registration_is_independent_of_weapon_or_effect_envelope(data):
    fact = ConditionFact(condition_uuid=uuid4(), category=ConditionCategory.CONDITION,
        behavior_id="condition.blinded", event_uuid=uuid4(), name="Blinded",
        resulting_max_hp=None, resulting_ac=None)
    appearance = resolve_condition_appearance((fact,), data.condition_recipes, data.condition_media)
    layer = next(row for row in appearance.layers if row.layer.assetId.endswith(".front"))
    registered = []
    for top in (5, 25):
        body = pygame.Surface((128, 128), pygame.SRCALPHA)
        body.set_at((64, top), (255, 0, 0, 255))
        image, origin = compose_condition_layers(body, (0, 0), (64, 120), "E", 1, 1,
            (replace(layer, age_ms=500),), {}, data=data,
            attachment_anchors={"head": (64, 40)})
        rgb, alpha = pygame.surfarray.array3d(image), pygame.surfarray.array_alpha(image)
        x, y = np.where((rgb[:, :, 1] > 10) & (alpha > 0))
        assert len(x)
        registered.append((origin[0] + int(x.min()), origin[1] + int(y.min()),
            origin[0] + int(x.max()), origin[1] + int(y.max())))
    assert registered[0] == registered[1]


@pytest.mark.parametrize("observer", ("caster", "recipient"))
def test_flame_strike_native_cylinder_groups_recipients_before_injury(data, observer):
    history = divine_history(program="flame_strike")
    before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[observer])))
    selected = set()
    for root in roots:
        group = bind_choreography(before, root, data)
        assert not group.gaps
        for clip in group.nodes:
            if not isinstance(clip.bound, BoundCast):
                continue
            timeline = clip.bound.timeline
            assert timeline.source.area_radius_feet == 10
            assert timeline.source.ground_target is not None
            assert timeline.source.ground_target.grid == (5, 6)
            assert timeline.recipe.contact is not None
            assert timeline.recipe.contact.delayMs == 21 * 1000 / 32
            selected.update(feedback_identity(a.target) for a in timeline.source.applications)
            contact = min(a.damage_start_ms for a in timeline.applications if a.damage_start_ms is not None)
            before_contact = sample_choreography(group, contact - 1)
            at_contact = sample_choreography(group, contact)
            assert cast_media_draw_commands(timeline, sample_cast(timeline, contact - 1),
                Camera(), None, {}), "Native fire has formed before injury"
            for application in timeline.source.applications:
                assert isinstance(application.target, ActorContact)
                victim = application.target.actor_uuid
                from_uuid = next(identity for identity in group.before.actors if str(identity) == victim)
                assert before_contact.displayed.actors[from_uuid].normal_hp == group.before.actors[from_uuid].normal_hp
                assert at_contact.displayed.actors[from_uuid].normal_hp < group.before.actors[from_uuid].normal_hp
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, zoom=.75)
                for track in timeline.recipe.media:
                    placement = cast_media_placement(timeline, track, timeline.source.caster, camera)
                    assert placement.anchor == project_screen((5, 6), camera)
                    assert placement.scale == .75
        before = reduce_lineage(before, root)
    assert len(selected) == 2
    actors = {a.name.lower(): a for a in before.actors.values()}
    assert actors["recipient"].normal_hp == actors["second"].normal_hp < 120
    assert actors["caster"].normal_hp == actors["bystander"].normal_hp == 120
