"""Ordinary Goblin fights replay through the shared body/attack boundary."""

from dataclasses import replace
from pathlib import Path

import pygame
import pytest

from dnd.core.equipment_types import WeaponSlot
from dnd.core.life_types import LifeState
from dnd.monsters.goblins import GOBLIN_DEFINITIONS
from game.animation import ActorContact, BodySample, CastApplication, CastInput, compile_cast, sample_cast
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands, load_actor_media
from game.animation_types import RigLayer
from game.attack import BoundAttack
from game.choreography import bind_choreography
from game.combat import BoundCast, actor_contact
from dnd.player.facts import ActionFact, AttackFact, SpellFact
from dnd.player.reduction import reduce_lineage
from game.presentation_group import presentation_groups, reduce_presentation_group
from game.projection import Camera
from tests.game.creature_scenarios import creature_history
from tests.game.player_helpers import player_history
from tests.game.interruption_scenarios import interruption_history
from tests.game.persistent_spell_scenarios import persistent_spell_history
from tests.game.web_scenarios import web_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data(rig_files=tuple(sorted(Path("game/data/rigs").glob("*.json"))))


@pytest.mark.parametrize("number,definition", tuple(enumerate(GOBLIN_DEFINITIONS, 1)))
def test_ordinary_goblin_moves_attacks_takes_damage_and_dies_with_its_original_body(data, number, definition):
    slot = WeaponSlot.RANGED_MAIN if number in (3, 9, 17) else WeaponSlot.MELEE_MAIN
    recorded = creature_history(f"content.neurodragon:creature:creature.{definition.key}@1", weapon_slot=slot)
    state, roots = player_history(recorded)
    identity = next(actor.uuid for actor in state.actors.values() if actor.uuid != state.observer_uuid)
    attacks = []
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, group.gaps
        if isinstance(root.root.fact, AttackFact) and root.root.fact.source_entity_uuid == identity:
            bound = group.nodes[0].bound
            assert isinstance(bound, BoundAttack)
            assert bound.timeline.source.rig_id == f"smallscale.goblin{number:02d}"
            assert not bound.timeline.missing_media
            attacks.append(bound.timeline)
        state = reduce_lineage(state, root)
    assert attacks and state.actors[identity].life_state is LifeState.DEAD
    if number in (3, 9, 17):
        assert attacks[0].projectile is not None
        assert attacks[0].release_ms == pytest.approx((5 if number == 17 else 11) * 1000 / 12)


@pytest.mark.parametrize("number", (2, 8))
def test_fixed_caster_keeps_shared_projectile_damage_but_uses_measured_cast_origin(data, number):
    caster = ActorContact("caster", (0, 0), "S", 1, rig_id=f"smallscale.goblin{number:02d}")
    target = ActorContact("target", (3, 0), "N", 1, hp=20)
    timeline = compile_cast(data, "spell.fire_bolt", CastInput("cast", caster, (
        CastApplication("hit", target, damage_applied=True, damage_total=7, resulting_hp=13),)))
    assert timeline.release_ms == 500
    assert sample_cast(timeline, timeline.release_ms).bodies[0].clip == "Attack2"
    assert timeline.recipe.projectile is not None and not timeline.recipe.projectile.prepare.enabled
    assert not [track for track in timeline.recipe.media if track.attachment == "source_hand"]
    assert timeline.recipe.projectile.sourceSockets == data.rigs[caster.rig_id].clips["Attack2"].source_sockets
    contact = timeline.applications[0].damage_start_ms
    assert contact is not None and contact > timeline.release_ms
    assert sample_cast(timeline, contact - .01).vitals[0].hp == 20
    assert sample_cast(timeline, timeline.complete_ms).vitals[0].hp == 13


@pytest.mark.parametrize("key", ("goblin_briarling", "goblin_gloomplate"))
def test_native_multiattack_selects_the_two_authored_hand_clips(data, key):
    state, roots = player_history(creature_history(
        f"content.neurodragon:creature:creature.{key}@1", multiattack=True))
    seen = 0
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, group.gaps
        fact = root.root.fact
        if isinstance(fact, ActionFact) and fact.behavior_id == "action.monster.multiattack":
            attacks = [node.bound.timeline for node in group.nodes if isinstance(node.bound, BoundAttack)]
            assert [attack.clip for attack in attacks] == ["Attack1", "Attack2"]
            seen += 1
        state = group.after
    assert seen


def test_pistol_original_flash_is_drawn_only_on_its_source_clip(data):
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        contact = ActorContact("gunner", (0, 0), "E", 1, rig_id="smallscale.goblin17")
        layers = (RigLayer("shadow", "Goblin17Shadow", alpha=.5), RigLayer("body", "Goblin17"))
        rows = load_actor_media(data, ((contact, layers, ("Idle", "Attack1", "Attack5")),), all_facings=True)
        camera = Camera(viewport=(600, 400), zoom=1).with_focus((0, 0))
        body = BodySample("gunner", "Attack5", 5, "E")
        commands = actor_draw_commands(data, body, contact, layers, rows, camera)
        assert commands
        # Removing just the original flash layer changes the sampled pixels.
        rig = data.rigs[contact.rig_id]
        # This comparison stays at the drawer boundary with the same original pixels.
        plain_clip = rig.clips["Attack5"].model_copy(update={"layers": ()})
        plain_rig = rig.model_copy(update={"clips": {**rig.clips, "Attack5": plain_clip}})
        plain_data = replace(data, rigs={**data.rigs, contact.rig_id: plain_rig})
        plain = actor_draw_commands(plain_data, body, contact, layers, rows, camera)
        assert [pygame.image.tobytes(c.surface, "RGBA") for c in commands] != [pygame.image.tobytes(c.surface, "RGBA") for c in plain]
        assert not rig.clips["Idle"].layers and not rig.clips["Attack1"].layers
    finally:
        pygame.quit()


@pytest.mark.parametrize("number", (2, 8))
@pytest.mark.parametrize("program", ("web", "shield", "counterspell"))
def test_original_caster_body_keeps_native_area_and_reaction_joins(data, number, program):
    # The input is a real native recording; only its rendering contact changes.
    history = (web_history() if program == "web" else
               persistent_spell_history(program="shield", shield_delivery="ranged") if program == "shield" else
               interruption_history(blocker="counterspell", spell="fireball"))
    state, roots = player_history(history, role="caster")
    caster_id = (next(identity for identity in state.actors if identity != state.observer_uuid)
                 if program == "counterspell" else state.observer_uuid)
    seen = 0
    gestures = []
    for presentation in presentation_groups(roots):
        actor = state.actors[caster_id]
        contacts = {str(caster_id): replace(actor_contact(state, actor, data),
                    rig_id=f"smallscale.goblin{number:02d}")}
        group = bind_choreography(state, presentation.primary, data,
            reactions=presentation.reactions, contacts=contacts)
        assert not group.gaps, group.gaps
        if program == "web":
            fact = presentation.primary.root.fact
            if isinstance(fact, SpellFact) and fact.behavior_id == "spell.web":
                cast = next(node for node in group.nodes if isinstance(node.bound, BoundCast))
                assert isinstance(cast.bound, BoundCast)
                timeline = cast.bound.timeline
                assert timeline.recipe.cast.actionClip == "Attack2" and timeline.release_ms == 500
                assert timeline.ground_delivery is not None
                creation = next(change for change in group.world_transitions if change.field == "creation")
                assert creation.start_ms == cast.start_ms + timeline.ground_delivery.travel_end_ms
                seen += 1
        else:
            for gesture in group.body_actions:
                gestures.append((gesture.recipe_id, gesture.clip, gesture.effect_ms - gesture.start_ms))
                if gesture.recipe_id not in ("spell.shield", "reaction.spell.shield", "reaction.spell.counterspell"):
                    continue
                assert gesture.clip == "Attack2" and not gesture.cast_layers
                assert gesture.effect_ms - gesture.start_ms == 500
                seen += 1
        assert group.after == reduce_presentation_group(state, presentation)
        state = group.after
    assert seen == 1, gestures
