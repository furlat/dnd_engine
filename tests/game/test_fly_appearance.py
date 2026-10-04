"""Actual Fly membership and sampled source layers share the ordinary compositor."""

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

import numpy as np
import pygame
import pytest

from dnd.actions_functional import register_spell
from dnd.core.events import EventQueue
from dnd.spells.transmutation import Fly
from game.animation import ActorContact, BodySample
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands, condition_rig_layers, load_actor_media
from game.animation_types import RigLayer
from game.choreography import bind_choreography
from game.condition_animation import compile_condition, resolve_condition_appearance, sample_condition
from game.condition_media_lifetime import register_condition_lifetimes, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media
from game.player_facts import ConditionChangeFact
from game.player_reduction import reduce_lineage
from game.projection import Camera
from game.replay import ObserverCapture, capture_history
from tests.game.player_helpers import player_history
from tests.game.scenarios import _healing_encounter
from tests.game.test_condition_animation import header


@pytest.fixture(scope="module")
def data():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((1, 1))
        root = Path(__file__).resolve().parents[2] / "game/data/rigs"
        yield load_animation_data(rig_files=tuple(root / name for name in
            ("demonbeast04.json", "demonbeast05.json", "greywolf.json")))
        pygame.quit()


@pytest.fixture(scope="module")
def history():
    with _healing_encounter() as (before, caster, _, _):
        baseline = EventQueue.event_cursor()
        register_spell(caster, Fly, caster_level=7)
        event = next(row for row in caster.registered_actions if isinstance(row, Fly)).instantiate(
            target_entity_uuid=caster.uuid, alt_skip_slot=True).apply()
        assert event is not None and not event.canceled
        assert caster.remove_condition("Concentrating")
        return capture_history(before, (), observers=(ObserverCapture("caster", caster.uuid, baseline),))


@pytest.fixture(scope="module")
def member(history):
    _, roots = player_history(history, role="caster")
    return next(node.fact.condition for root in roots for node in root.events
        if isinstance(node.fact, ConditionChangeFact)
        and node.fact.condition.behavior_id == "condition.spell.fly")


def appearance(data, members):
    return resolve_condition_appearance(members, data.condition_recipes, data.condition_media)


def test_native_grant_and_concentration_removal_control_temporary_appearance(data, history):
    before, roots = player_history(history, role="caster")
    seen = []
    for root in roots:
        after = reduce_lineage(before, root)
        actor = next(actor for actor in after.actors.values() if actor.name == "Healer")
        count = sum(row.behavior_id == "condition.spell.fly" for row in actor.conditions)
        shown = appearance(data, actor.conditions)
        assert len(shown.rig_layers) == bool(count)
        assert len(shown.layers) == (2 if count else 0)
        assert not shown.unsupported
        assert shown.alpha == 1 and shown.body_pose is None
        seen.append(count)
        before = after
    assert 1 in seen and seen[-1] == 0


def test_received_overlapping_memberships_preserve_wings_until_last_owner(data, member):
    # Public visual input coverage only: current native same-spell application
    # replaces its previous source instead of retaining two Fly memberships.
    other = replace(member, condition_uuid=uuid4(), event_uuid=uuid4())
    shown = appearance(data, (member, other))
    assert len(shown.rig_layers) == 1 and len(shown.layers) == 2
    removed = replace(member, event_uuid=uuid4())
    first = compile_condition(data.condition_recipes, header(removed, applied=False), removed,
        (member, other), start_ms=0, badge_style=data.badge_style, media=data.condition_media)
    assert first.after_membership == (other,)
    assert sample_condition(first, 0).appearance.rig_layers[0].alpha == 1
    last = replace(other, event_uuid=uuid4())
    final = compile_condition(data.condition_recipes, header(last, applied=False), last,
        first.after_membership, start_ms=100, badge_style=data.badge_style, media=data.condition_media)
    assert not sample_condition(final, final.complete_ms).appearance.rig_layers


def test_wing_transitions_fade_only_extra_layer_and_seek_deterministically(data, history):
    before, roots = player_history(history, role="caster")
    for root in roots:
        for node in root.events:
            fact = node.fact
            if not isinstance(fact, ConditionChangeFact) or fact.condition.behavior_id != "condition.spell.fly":
                continue
            prior = before.actors[fact.target_entity_uuid].conditions
            cue = compile_condition(data.condition_recipes, node, fact.condition, prior,
                start_ms=100, badge_style=data.badge_style, media=data.condition_media)
            old, new = bool(cue.before_appearance.rig_layers), bool(cue.after_appearance.rig_layers)
            if old != new:
                sample = sample_condition(cue, (cue.start_ms + cue.complete_ms) / 2)
                assert sample.appearance.alpha == 1
                assert sample.appearance.rig_layers[0].alpha == pytest.approx(.5)
                assert sample_condition(cue, (cue.start_ms + cue.complete_ms) / 2) == sample
            elif old:
                assert sample_condition(cue, 100).appearance.rig_layers[0].alpha == 1
        before = reduce_lineage(before, root)


def test_wind_uses_received_owner_clock_and_original_finite_release(data, history):
    before, roots = player_history(history, role="caster")
    retained, clock, started, removed = {}, 0., {}, set()
    for root in roots:
        group = bind_choreography(before, root, data)
        retained = register_condition_lifetimes(retained, before, data, absolute_start_ms=clock,
            lineage=root, choreography=group)
        after = reduce_lineage(before, root)
        shown = {str(actor.uuid): appearance(data, actor.conditions) for actor in after.actors.values()}
        for owner, record in retained.items():
            if record.behavior_id != "condition.spell.fly":
                continue
            assert record.applied_ms is not None
            started.setdefault(owner, record.applied_ms)
            assert started[owner] == record.applied_ms
            if record.removed_ms is not None and record.removed_layers:
                removed.add(owner)
                layers = sample_condition_lifetimes(shown, retained, data, record.removed_ms + 200)[str(record.actor_uuid)].layers
                selected = [layer for layer in layers if layer.owner_uuid == owner]
                assert len(selected) == 2
                assert all(".release." in sample_condition_media(data, layer)[-1].asset_id for layer in selected)
                assert sample_condition_lifetimes(shown, retained, data, record.removed_ms + 200)[str(record.actor_uuid)].layers == layers
                gone = sample_condition_lifetimes(shown, retained, data, record.removed_ms + 1200)[str(record.actor_uuid)].layers
                assert not any(layer.owner_uuid == owner for layer in gone)
        before = after
        clock += group.complete_ms + 1500
    assert len(started) == len(removed) == 1


def commands(data, contact, layers, body, rows, condition):
    return {row.role: row for row in actor_draw_commands(data, body, contact, layers, rows,
        Camera(viewport=(700, 500)), condition=condition)}


@pytest.mark.parametrize("clip,frame", (("Idle", 3), ("Attack5", 8), ("TakeDamage", 5), ("Die", 14), ("AttackRun", 7)))
def test_wings_share_source_frame_facing_and_preserve_backpack_and_shadow(data, member, clip, frame):
    contact = ActorContact("actor", (0, 0), "S", 1.)
    layers = (RigLayer("body", "NakedBody"), RigLayer("backpack", "Bag2"),
              RigLayer("shadow", "Shadow", alpha=.5))
    rows = load_actor_media(data, ((contact, layers, (clip,)),), all_facings=True)
    condition = replace(appearance(data, (member,)), layers=())
    for facing in data.rig.FACING_ROW:
        body = BodySample("actor", clip, frame, facing)
        plain = commands(data, contact, layers, body, rows, None)
        fly = commands(data, contact, layers, body, rows, condition)
        assert plain["actor"].destination == fly["actor"].destination
        assert pygame.image.tobytes(plain["actor_shadow"].surface, "RGBA") == pygame.image.tobytes(fly["actor_shadow"].surface, "RGBA")
        original = pygame.surfarray.array3d(plain["actor"].surface)
        actual = pygame.surfarray.array3d(fly["actor"].surface)
        assert np.any(original != actual)
        # The original backpack is drawn at its normal slot, over the added
        # wing roots. Its opaque pixels remain exactly the ordinary result.
        sheet = rows[contact.rig_id, clip, "Bag2", data.rig.FACING_ROW[facing]]
        bag = pygame.transform.scale(sheet.subsurface((frame * 128, 0, 128, 128)), plain["actor"].surface.size)
        opaque = pygame.surfarray.array_alpha(bag) == 255
        assert np.array_equal(actual[opaque], original[opaque])
        changed = np.any(original != actual, axis=2)
        assert np.any(actual[..., 2][changed] > actual[..., 0][changed]), "cyan palette replacement is visible"
        assert pygame.image.tobytes(commands(data, contact, layers, body, rows, condition)["actor"].surface, "RGBA") == pygame.image.tobytes(fly["actor"].surface, "RGBA")


@pytest.mark.parametrize("rig_id", ("smallscale.demonbeast04", "smallscale.demonbeast05", "smallscale.greywolf"))
def test_native_wings_and_fixed_nonwinged_anatomy_do_not_receive_modular_bag(data, member, rig_id):
    rig = data.rigs[rig_id]
    layers = tuple(RigLayer(slot, categories[0], alpha=rig.shadow_alpha if slot == "shadow" else 1)
        for slot, categories in rig.slot_categories.items() if slot in ("body", "shadow"))
    condition = appearance(data, (member,))
    assert not condition_rig_layers(rig, layers, condition)
    assert len(condition.layers) == 2, "magical wind remains on an anatomy-compatible contact"


def test_equipped_wings_are_not_duplicated_or_recolored_by_temporary_fly(data, member):
    contact = ActorContact("actor", (0, 0), "S", 1.)
    layers = (RigLayer("body", "NakedBody"), RigLayer("backpack", "Bag8"))
    body = BodySample("actor", "Idle", 3, "S")
    rows = load_actor_media(data, ((contact, layers, ("Idle",)),))
    condition = replace(appearance(data, (member,)), layers=())
    assert not condition_rig_layers(data.rigs[contact.rig_id], layers, condition)
    original = commands(data, contact, layers, body, rows, None)["actor"]
    fly = commands(data, contact, layers, body, rows, condition)["actor"]
    assert pygame.image.tobytes(fly.surface, "RGBA") == pygame.image.tobytes(original.surface, "RGBA")


def test_preloaded_wing_layer_survives_source_removal_and_seek(data, member, tmp_path):
    contact = ActorContact("actor", (0, 0), "S", 1.)
    layers = (RigLayer("body", "NakedBody"), RigLayer("backpack", "Bag2"))
    resource = data.rigs[contact.rig_id].clips["Idle"].sheets["Bag8"]
    source = tmp_path / "wings.png"
    source.symlink_to(data.resources[resource])
    relocated = replace(data, resources=MappingProxyType({**data.resources, resource: source}))
    rows = load_actor_media(relocated, ((contact, layers, ("Idle",)),))
    source.unlink()
    condition = replace(appearance(data, (member,)), layers=())
    body = BodySample("actor", "Idle", 3, "S")
    original = commands(relocated, contact, layers, body, rows, condition)["actor"]
    commands(relocated, contact, layers, replace(body, frame=9), rows, condition)
    again = commands(relocated, contact, layers, body, rows, condition)["actor"]
    assert pygame.image.tobytes(again.surface, "RGBA") == pygame.image.tobytes(original.surface, "RGBA")


def test_original_wind_pixels_follow_body_contact_but_shadow_stays_grounded(data, member):
    contact = ActorContact("actor", (0, 0), "S", 1.)
    layers = (RigLayer("body", "NakedBody"), RigLayer("shadow", "Shadow", alpha=.5))
    rows = load_actor_media(data, ((contact, layers, ("Idle",)),))
    body = BodySample("actor", "Idle", 3, "S")
    condition = appearance(data, (member,))
    condition = replace(condition, layers=tuple(replace(layer, age_ms=700) for layer in condition.layers))
    grounded = commands(data, contact, layers, body, rows, condition)
    wings_only = commands(data, contact, layers, body, rows, replace(condition, layers=()))
    assert pygame.image.tobytes(grounded["actor"].surface, "RGBA") != pygame.image.tobytes(wings_only["actor"].surface, "RGBA")
    lifted = commands(data, replace(contact, body_lift_px=12), layers, body, rows, condition)
    assert pygame.image.tobytes(lifted["actor"].surface, "RGBA") == pygame.image.tobytes(grounded["actor"].surface, "RGBA")
    assert lifted["actor"].destination == (grounded["actor"].destination[0], grounded["actor"].destination[1] - 12)
    assert lifted["actor_shadow"].destination == grounded["actor_shadow"].destination
    assert pygame.image.tobytes(lifted["actor_shadow"].surface, "RGBA") == pygame.image.tobytes(grounded["actor_shadow"].surface, "RGBA")
