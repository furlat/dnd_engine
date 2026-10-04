"""Spell-owned attacks reuse actual weapon timing and exact authored charge poses."""

import pygame
import pytest
import numpy as np

from dnd.actions import AttackEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY, BaseObject
from dnd.core.events import EventQueue
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands, load_attack_media, load_cast_rows
from game.attack import BoundAttack, bind_attack, sample_attack
from game.choreography import bind_choreography, sample_choreography
from game.player_facts import AttackFact, SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, lineage_branch, reduce_lineage
from game.projection import Camera
from game.replay import RecordedSequence
from tests.game.true_strike_scenarios import true_strike_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.fixture(scope="module", autouse=True)
def display():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((1, 1))
        yield
        pygame.quit()


def player_cast(sequence):
    restored = RecordedSequence.model_validate_json(sequence.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    before, roots = decode_player_sequence(encode_player_sequence(project_sequence(restored)))
    for root in roots:
        if isinstance(root.root.fact, SpellFact):
            return before, root
        before = reduce_lineage(before, root)
    raise AssertionError("native capture has no True Strike root")


@pytest.mark.parametrize("ranged", (False, True))
@pytest.mark.parametrize("miss", (False, True))
def test_serialized_child_attack_keeps_weapon_and_outcome_with_one_authored_overlay(data, ranged, miss):
    history = true_strike_history(ranged=ranged, miss=miss)
    assert set(history.views) == {"caster", "recipient"}
    for role, sequence in history.views.items():
        before, root = player_cast(sequence)
        attack, = [node for node in root.events if isinstance(node.fact, AttackFact)]
        assert isinstance(attack.fact, AttackFact) and isinstance(root.root.fact, SpellFact)
        assert attack.parent_lineage == root.root.lineage_uuid
        assert attack.fact.behavior_id == "action.attack"
        assert attack.fact.source_item_id == ("weapon.shortbow" if ranged else "weapon.shortsword")
        native = next(event for row in sequence.lineages for event in row.events if event.uuid == attack.uuid)
        assert isinstance(native, AttackEvent)
        assert attack.fact.attack_outcome is native.attack_outcome
        ordinary = bind_attack(before, lineage_branch(root, attack), data)
        assert ordinary is not None
        choreography = bind_choreography(before, root, data)
        assert not choreography.gaps, (role, choreography.gaps)
        assert not choreography.body_actions
        node, = choreography.nodes
        assert node.event_uuid == attack.uuid and node.start_ms == 0
        assert isinstance(node.bound, BoundAttack)
        bound, baseline = node.bound, ordinary.timeline
        timeline = bound.timeline
        assert timeline.clip == baseline.clip == ("Attack3" if ranged else "Attack6")
        assert timeline.profile_id == baseline.profile_id
        assert (timeline.contact_ms, timeline.release_ms, timeline.complete_ms) == (
            baseline.contact_ms, baseline.release_ms, baseline.complete_ms)
        assert timeline.projectile == baseline.projectile
        assert bound.appearances == ordinary.appearances
        literal, = [layer for layer in timeline.layers if layer.sourceSheet is not None]
        assert literal.slot == "weaponGlow"
        assert literal.sourceSheet == "/support-spells/true_strike/" + (
            "Ranged1-Attack3-charge.png" if ranged else "Melee3-Attack6-charge.png")
        assert timeline.release_ms == (pytest.approx(10 * 1000 / 12) if ranged else None)
        if not ranged:
            assert timeline.contact_ms == pytest.approx(7 * 1000 / 12)
        target = root.root.fact.target_entity_uuid
        assert target is not None
        assert sample_choreography(choreography, timeline.contact_ms - .01).displayed.actors[target].normal_hp == 60
        assert sample_choreography(choreography, choreography.complete_ms).displayed.actors[target].normal_hp == (
            60 if miss else 48)
        initial = sample_attack(timeline, 0)
        sample_attack(timeline, timeline.complete_ms)
        assert sample_attack(timeline, 0) == initial
    assert not BaseObject._registry and EventQueue.event_cursor() == 0


@pytest.mark.parametrize("ranged", (False, True))
def test_literal_weapon_charge_draws_in_rig_slots_and_preserves_baked_on_off_frames(data, ranged):
    history = true_strike_history(ranged=ranged)
    before, root = player_cast(history.views["caster"])
    attack, = [node for node in root.events if isinstance(node.fact, AttackFact)]
    ordinary = bind_attack(before, lineage_branch(root, attack), data)
    assert ordinary is not None
    node, = bind_choreography(before, root, data).nodes
    assert isinstance(node.bound, BoundAttack)
    charged = node.bound
    rows = load_attack_media(charged.timeline, charged.appearances)
    plain_rows = load_attack_media(ordinary.timeline, ordinary.appearances)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.5).with_focus(charged.timeline.source.grid)
        for frame in (0, 1, 7, 10, 14):
            elapsed = (frame + .1) * 1000 / 12
            images = []
            for bound, media in ((charged, rows), (ordinary, plain_rows)):
                body = sample_attack(bound.timeline, elapsed).bodies[0]
                draws = actor_draw_commands(data, body, bound.timeline.source,
                    bound.appearances[body.actor_uuid], media, camera)
                actor, = [draw for draw in draws if draw.evidence[6] == "actor"]
                images.append((actor.destination, pygame.image.tobytes(actor.surface, "RGBA")))
            assert images[0][0] == images[1][0]
            assert (images[0][1] != images[1][1]) is (frame == 7), (ranged, quadrant, frame)


@pytest.mark.parametrize("miss", (False, True))
@pytest.mark.parametrize("weapon,ranged", (("weapon.longsword", False), ("weapon.heavy_crossbow", True)))
def test_other_weapons_keep_their_attack_with_spell_colored_hands(data, miss, weapon, ranged):
    history = true_strike_history(weapon=weapon, ranged=ranged, miss=miss)
    before, root = player_cast(history.views["caster"])
    attack, = [node for node in root.events if isinstance(node.fact, AttackFact)]
    ordinary = bind_attack(before, lineage_branch(root, attack), data)
    assert ordinary is not None
    choreography = bind_choreography(before, root, data)
    assert not choreography.gaps and not choreography.body_actions
    node, = choreography.nodes
    assert isinstance(node.bound, BoundAttack)
    charged = node.bound
    timeline, baseline = charged.timeline, ordinary.timeline
    assert (timeline.clip, timeline.profile_id, timeline.release_ms, timeline.contact_ms, timeline.complete_ms) == (
        baseline.clip, baseline.profile_id, baseline.release_ms, baseline.contact_ms, baseline.complete_ms)
    assert timeline.projectile == baseline.projectile and charged.appearances == ordinary.appearances
    layer, = [layer for layer in timeline.layers if layer.slot == "weaponGlow"]
    palette = data.drafts["spell.true_strike"].elementColors
    assert layer.palette is not None
    assert layer.palette.colors == (palette.tertiary, palette.primary, palette.secondary)
    rows = {}
    load_cast_rows(data, timeline.source, timeline.clip, timeline.facing, (layer,), rows)
    assert layer.sourceSheet is not None
    source = pygame.image.load(data.resources[layer.sourceSheet]).convert_alpha()
    rig = data.rigs[timeline.source.rig_id]
    expected = {((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in layer.palette.colors}
    for key, image in rows.items():
        raw = source.subsurface((0, key[3] * rig.cell_height, image.width, image.height))
        alpha = pygame.surfarray.array_alpha(image)
        assert np.array_equal(alpha, pygame.surfarray.array_alpha(raw))
        pixels = {tuple(pixel) for pixel in pygame.surfarray.array3d(image)[alpha > 0]}
        assert pixels and pixels <= expected
    charged_rows = load_attack_media(timeline, charged.appearances)
    plain_rows = load_attack_media(baseline, ordinary.appearances)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.5).with_focus(timeline.source.grid)
        differences = 0
        for frame in range(15):
            images = []
            for bound, media in ((charged, charged_rows), (ordinary, plain_rows)):
                body = sample_attack(bound.timeline, (frame + .1) * 1000 / 12).bodies[0]
                draws = actor_draw_commands(data, body, bound.timeline.source,
                    bound.appearances[body.actor_uuid], media, camera)
                actor, = [draw for draw in draws if draw.evidence[6] == "actor"]
                images.append((actor.destination, pygame.image.tobytes(actor.surface, "RGBA")))
            assert images[0][0] == images[1][0]
            differences += images[0][1] != images[1][1]
        assert differences, (weapon, miss, quadrant)
