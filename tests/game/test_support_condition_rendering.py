"""Authored support materials preserve real rig pixels and finite event clocks."""

from dataclasses import replace

import numpy as np
import pygame
import pytest

from dnd.actions_functional import register_spell
from dnd.conditions import Poisoned
from dnd.core.condition_types import ConditionTag
from dnd.core.creature_types import DamageType
from dnd.core.events import EventType
from dnd.spells.abjuration import DeathWard, RemoveCurse, Stoneskin
from dnd.spells.necromancy import NoHealing, AbilityCurseEffect
from dnd.spells.transmutation import EnhanceAbility, Regenerate
from game.animation import ActorContact, BodySample, body_clip, media_track_duration, sample_cast
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands
from game.animation_types import RigLayer
from game.choreography import bind_choreography, sample_choreography
from game.cast_media import cast_media_draw_commands
from game.combat import bind_cast
from game.condition_animation import ConditionAppearance, resolve_condition_appearance
from game.condition_draw import compose_condition_layers
from game.condition_media_lifetime import register_condition_lifetimes, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media
from game.condition_types import ConditionBodyRamp, ConditionResponse
from game.player_facts import ConditionChangeFact, SpellFact
from game.player_reduction import reduce_lineage
from game.projection import Camera, TILE_WIDTH
from game.spell_palette import BODY_PALETTES
from tests.game.test_support_condition_facts import ABILITIES, arena as arena, baseline, cast, saved_views


RAMP = ConditionBodyRamp(colors=(0x44372C, 0x655039, 0x866A46, 0xA18355, 0xB99B6B), gain=1.35,
                         applicationMs=1200, removalMs=400)


@pytest.fixture(autouse=True)
def display():
    pygame.display.init()
    pygame.display.set_mode((1, 1))


@pytest.fixture(scope="module")
def rig_pixels():
    data = load_animation_data()
    contact = ActorContact("recipient", (3, 4), "S", data.rig.TILE_W / TILE_WIDTH)
    rig = data.rigs[contact.rig_id]
    layers = tuple(RigLayer(slot, slot) for slot in ("body", "chest", "weapon", "effect", "shadow"))
    frames = body_clip(data, contact, "Idle").frames
    rows = {}
    for row in rig.facing_rows.values():
        for index, layer in enumerate(layers):
            image = pygame.Surface((rig.cell_width * frames, rig.cell_height), pygame.SRCALPHA)
            for frame in range(frames):
                # Different real frame silhouettes, semitransparent edges and colors.
                for point, alpha in enumerate((63, 127, 255)):
                    image.set_at((frame * rig.cell_width + 3 + index * 5 + point, frame + 4),
                        (25 + index * 32 + frame * 3, 35 + row * 9, 12 + point * 15, alpha))
                if index < 2:
                    image.set_at((frame * rig.cell_width + 40, frame + 4),
                        (220 - index * 30, 12, 70, 80 + index * 40))
            rows[contact.rig_id, "Idle", layer.category, row] = image
    return data, contact, layers, rows


def draw(rig_pixels, frame, quadrant, *, strength=None, flash=None, layers=None):
    data, contact, original_layers, rows = rig_pixels
    appearance = None if strength is None else ConditionAppearance(body_ramp=RAMP, ramp_strength=strength)
    commands = actor_draw_commands(data, BodySample(contact.actor_uuid, "Idle", frame, "S"), contact,
        original_layers if layers is None else layers, rows, Camera(zoom=1, quadrant=quadrant),
        flash=flash, condition=appearance)
    return {command[4][6]: command[1] for command in commands}


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("frame", (0, 2))
def test_stone_ramp_preserves_frames_equipment_alpha_and_independent_effects(rig_pixels, quadrant, frame):
    plain = draw(rig_pixels, frame, quadrant)
    stone = draw(rig_pixels, frame, quadrant, strength=1.)
    partial = draw(rig_pixels, frame, quadrant, strength=.5)
    _, _, layers, _ = rig_pixels
    assert pygame.image.tobytes(stone["actor_shadow"], "RGBA") == pygame.image.tobytes(plain["actor_shadow"], "RGBA")
    assert np.array_equal(pygame.surfarray.array_alpha(stone["actor"]), pygame.surfarray.array_alpha(plain["actor"]))
    assert np.array_equal(pygame.surfarray.array_alpha(partial["actor"]), pygame.surfarray.array_alpha(plain["actor"]))
    source = plain["actor"]
    for index, layer in enumerate(layers[:-1]):
        for point in range(3):
            pixel = 3 + index * 5 + point, frame + 4
            original = source.get_at(pixel)
            ramp_index = min(4, int(min(1., max(original[:3]) / 255 * 1.35) * 5))
            color = RAMP.colors[ramp_index]
            mapped = (color >> 16, color >> 8 & 255, color & 255) if layer.slot != "effect" else tuple(original[:3])
            assert tuple(stone["actor"].get_at(pixel)) == (*mapped, original.a)
            blended = tuple(round((a + b) / 2) for a, b in zip(original[:3], mapped))
            assert tuple(partial["actor"].get_at(pixel)) == (*blended, original.a)
    overlap = source.get_at((40, frame + 4))
    index = min(4, int(min(1., max(overlap[:3]) / 255 * RAMP.gain) * 5))
    color = RAMP.colors[index]
    assert tuple(stone["actor"].get_at((40, frame + 4))) == (color >> 16, color >> 8 & 255, color & 255, overlap.a)
    # A temporary hit tint takes priority without destroying the original rows.
    flash = draw(rig_pixels, frame, quadrant, strength=1., flash=0x00FF00)
    ordinary_flash = draw(rig_pixels, frame, quadrant, flash=0x00FF00)
    assert pygame.image.tobytes(flash["actor"], "RGBA") == pygame.image.tobytes(ordinary_flash["actor"], "RGBA")
    assert pygame.image.tobytes(draw(rig_pixels, frame, quadrant)["actor"], "RGBA") == pygame.image.tobytes(source, "RGBA")
    # Removing a weapon during the condition retains the actual new equipment.
    unarmed = draw(rig_pixels, frame, quadrant, strength=1., layers=tuple(row for row in layers if row.slot != "weapon"))
    assert unarmed["actor"].get_at((13, frame + 4)).a == 0


def test_stone_blend_progress_does_not_grow_the_decoded_row_cache(rig_pixels):
    draw(rig_pixels, 0, 0, strength=1.)
    before = BODY_PALETTES.decoded_bytes
    for progress in range(1, 100):
        draw(rig_pixels, progress % 3, 0, strength=progress / 100)
    assert BODY_PALETTES.decoded_bytes == before
    assert BODY_PALETTES.decoded_bytes <= BODY_PALETTES.limit_bytes


def response_data(member, trigger):
    """Existing delivered strips stand in for any authored response's pixels."""
    data = load_animation_data()
    donor = data.condition_recipes["condition.spell.bless"]
    finite = data.condition_recipes["condition.blinded"].application.effects
    recipe = donor.model_copy(update={
        "definitionRef": data.condition_recipes[member.behavior_id].definitionRef,
        "responses": (ConditionResponse(trigger=trigger, effects=tuple(
            effect.model_copy(update={"durationMs": 500.}) for effect in finite)),),
        "application": donor.application.model_copy(update={"effects": ()}),
        "removal": donor.removal.model_copy(update={"effects": finite if trigger == "consumed" else ()}),
    })
    return replace(data, condition_recipes={**data.condition_recipes, member.behavior_id: recipe})


def appearances(state, data):
    return {str(actor.uuid): resolve_condition_appearance(actor.conditions, data.condition_recipes,
        data.condition_media) for actor in state.actors.values()}


@pytest.mark.parametrize("ending", ("lethal", "instant_death", "remove"))
@pytest.mark.parametrize("delivered", (False, True))
def test_consumption_plays_once_at_actual_contact_and_replaces_the_hold(arena, ending, delivered):
    game, caster, recipient, _ = arena
    register_spell(caster, DeathWard)
    cast(caster, recipient, "spell.death_ward")
    before, cursor = baseline(caster)
    member = next(row for row in before.actors[recipient.uuid].conditions if row.name == "Death Ward")
    assert member.behavior_id is not None
    data = load_animation_data() if delivered else response_data(member, "consumed")
    finite_ids = {effect.assetId for response in data.condition_recipes[member.behavior_id].responses
                  if response.trigger == "consumed" for effect in response.effects}
    assert finite_ids
    if ending == "lethal":
        recipient.receive_damage(200, DamageType.SLASHING, caster.uuid)
    elif ending == "instant_death":
        recipient.receive_instant_death(caster.uuid)
    else:
        recipient.remove_condition("Death Ward")
    total = 0
    for state, roots in saved_views(game, before, cursor, caster, recipient).values():
        records, clock = {}, 0.
        for root in roots:
            group = bind_choreography(state, root, data)
            records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                lineage=root, choreography=group)
            assert records == register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                lineage=root, choreography=group)
            after = reduce_lineage(state, root)
            for cue in group.condition_responses:
                total += 1
                assert cue.owner_uuid == member.condition_uuid and cue.trigger == "consumed"
                assert group.complete_ms >= cue.end_ms
                condition = next(row for row in group.conditions if row.event_uuid == cue.event_uuid)
                assert cue.start_ms == condition.start_ms
                current = sample_condition_lifetimes(appearances(after, data), records, data,
                    clock + cue.start_ms + 125)[str(recipient.uuid)]
                assert len(current.layers) == 2
                assert all(row.finite and row.layer.assetId in finite_ids for row in current.layers)
                assert not sample_condition_lifetimes(appearances(after, data), records, data,
                    clock + cue.end_ms)[str(recipient.uuid)].layers
            state, clock = after, clock + group.complete_ms + 25
        assert bool(total) is (ending != "remove")
    assert total == (0 if ending == "remove" else 2)


def test_disclosed_consumption_without_prior_membership_retains_only_its_finite_tail(arena):
    game, caster, recipient, _ = arena
    register_spell(caster, DeathWard)
    cast(caster, recipient, "spell.death_ward")
    before, cursor = baseline(caster)
    member = next(row for row in before.actors[recipient.uuid].conditions if row.name == "Death Ward")
    data = response_data(member, "consumed")
    recipient.receive_damage(200, DamageType.SLASHING, caster.uuid)
    state, roots = saved_views(game, before, cursor, caster)[caster.name]
    # The receiver can first learn the owner from its removal fact. Exercise
    # that public-state boundary with genuine saved consumption events.
    actor = state.actors[recipient.uuid]
    state = replace(state, actors={**state.actors, recipient.uuid: replace(actor,
        conditions=tuple(row for row in actor.conditions if row.condition_uuid != member.condition_uuid))})
    records, clock, seen = {}, 0., False
    for root in roots:
        group = bind_choreography(state, root, data)
        records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
            lineage=root, choreography=group)
        state = reduce_lineage(state, root)
        if group.condition_responses:
            seen = True
            cue, = group.condition_responses
            assert records[member.condition_uuid].removed_ms == clock + cue.start_ms
            sampled = sample_condition_lifetimes(appearances(state, data), records, data,
                clock + cue.start_ms + 125)[str(recipient.uuid)]
            assert len(sampled.layers) == 2
        clock += group.complete_ms + 25
    assert seen
    assert member.condition_uuid not in register_condition_lifetimes(
        records, state, data, absolute_start_ms=clock + 5000)


@pytest.mark.parametrize("mode", ("healed", "full_hp", "blocked"))
@pytest.mark.parametrize("delivered", (False, True))
def test_repeated_actual_heals_and_final_pulse_survive_expiry(arena, mode, delivered):
    game, caster, recipient, turns = arena
    register_spell(caster, Regenerate)
    if mode != "full_hp":
        recipient.receive_damage(90, DamageType.FORCE, caster.uuid)
    cast(caster, recipient, "spell.regenerate")
    if mode == "blocked":
        recipient.add_condition(NoHealing(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid))
    before, cursor = baseline(caster)
    member = next(row for row in before.actors[recipient.uuid].conditions if row.name == "Regenerating")
    assert member.behavior_id is not None
    data = load_animation_data() if delivered else response_data(member, "healed")
    finite_ids = {effect.assetId for response in data.condition_recipes[member.behavior_id].responses
                  if response.trigger == "healed" for effect in response.effects}
    assert finite_ids
    recipient.receive_healing(2, caster.uuid)  # An unrelated heal must not pulse the condition.
    for _ in range(10):
        turns.next_turn()
        while turns.get_current_entity() is not recipient:
            turns.next_turn()
    for state, roots in saved_views(game, before, cursor, caster, recipient).values():
        records, clock, pulses = {}, 0., []
        for root in roots:
            group = bind_choreography(state, root, data)
            records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                lineage=root, choreography=group)
            assert records == register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                lineage=root, choreography=group)
            for cue in group.condition_responses:
                assert len(records[cue.owner_uuid].responses) == 1, "Finished earlier pulses do not accumulate"
                pulses.append(cue.event_uuid)
                assert group.complete_ms >= cue.end_ms
                displayed = sample_choreography(group, cue.start_ms + 125).displayed
                sampled = sample_condition_lifetimes(appearances(displayed, data), records, data,
                    clock + cue.start_ms + 125)[str(recipient.uuid)]
                pulse = [row for row in sampled.layers if row.finite and row.layer.assetId in finite_ids]
                assert len(pulse) == 2
                for layer in pulse:
                    sample, = sample_condition_media(data, layer)
                    asset = data.projectile_assets[sample.asset_id]
                    assert asset.phases.impact is not None
                    assert sample.frame == int(.125 * (asset.phases.impact.fps or asset.fps))
                # Attached finite strips use the presented body contact, including movement.
                body = pygame.Surface((8, 8), pygame.SRCALPHA)
                first, first_at = compose_condition_layers(body, (0, 0), (4., 7.), "S", 1., 1., tuple(pulse), {},
                    data=data, activity="move")
                moved, moved_at = compose_condition_layers(body, (25, -12), (29., -5.), "S", 1., 1., tuple(pulse), {},
                    data=data, activity="move")
                assert moved_at == (first_at[0] + 25, first_at[1] - 12)
                assert pygame.image.tobytes(moved, "RGBA") == pygame.image.tobytes(first, "RGBA")
                if any(isinstance(node.fact, ConditionChangeFact)
                       and node.fact.condition.condition_uuid == member.condition_uuid
                       and node.fact.event_type is EventType.CONDITION_REMOVAL for node in root.events):
                    assert all(row.condition_uuid != member.condition_uuid for row in displayed.actors[recipient.uuid].conditions)
                    assert pulse, "The last genuine heal outlives membership removal"
            state, clock = reduce_lineage(state, root), clock + group.complete_ms + 25
        assert len(pulses) == len(set(pulses)) == (10 if mode == "healed" else 0)


@pytest.mark.parametrize("ability", ABILITIES)
def test_ability_layers_select_the_recorded_choice_including_late_observation(arena, ability):
    game, caster, recipient, _ = arena
    caster.register_action(EnhanceAbility(source_entity_uuid=caster.uuid, template=True, enhance_ability_type=ability))
    cast(caster, recipient, "spell.enhance_ability")
    before, cursor = baseline(caster)
    state, _ = saved_views(game, before, cursor, recipient)[recipient.name]
    member = next(row for row in state.actors[recipient.uuid].conditions if row.name == "Enhance Ability")
    data = load_animation_data()
    selected = resolve_condition_appearance((member,), data.condition_recipes, data.condition_media)
    assert len(selected.layers) == 2
    assert all(row.layer.whenAbility == ability for row in selected.layers)
    legacy = replace(member, state=member.state.model_copy(update={"enhanced_ability": None}))
    assert not resolve_condition_appearance((legacy,), data.condition_recipes, data.condition_media).layers


@pytest.mark.parametrize("curse_count", (0, 1, 2))
def test_remove_curse_target_media_requires_real_removal_and_deduplicates(arena, curse_count):
    game, caster, recipient, _ = arena
    caster.register_action(RemoveCurse(source_entity_uuid=caster.uuid, cast_at_level=4, template=True))
    recipient.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid))
    for index in range(curse_count):
        recipient.add_condition(AbilityCurseEffect(name=f"Curse {index}", source_entity_uuid=caster.uuid,
            target_entity_uuid=recipient.uuid, cursed_ability="strength"))
    before, cursor = baseline(caster)
    cast(caster, recipient, "spell.remove_curse")
    assert "Poisoned" in recipient.active_conditions
    data = load_animation_data()
    draft = data.drafts["spell.remove_curse"]
    assert all(track.requireRemovedConditionTag is ConditionTag.CURSE for track in draft.media)
    duration = max(track.startOffsetMs + media_track_duration(data, track) for track in draft.media)
    for state, roots in saved_views(game, before, cursor, caster, recipient).values():
        for root in roots:
            if isinstance(root.root.fact, SpellFact) and root.root.fact.behavior_id == "spell.remove_curse":
                bound = bind_cast(state, root, data)
                application, = bound.timeline.source.applications
                assert (ConditionTag.CURSE in application.removed_condition_tags) is bool(curse_count)
                sample = sample_cast(bound.timeline, bound.timeline.release_ms + 125)
                commands = cast_media_draw_commands(bound.timeline, sample, Camera(zoom=1), None, {})
                assert len(commands) == (2 if curse_count else 0)
                if curse_count:
                    assert bound.timeline.complete_ms >= bound.timeline.release_ms + duration
                else:
                    assert bound.timeline.complete_ms < bound.timeline.release_ms + duration
            state = reduce_lineage(state, root)


def test_stone_material_blends_on_application_removal_and_enters_quiet_when_observed_late(arena):
    game, caster, recipient, _ = arena
    register_spell(caster, Stoneskin)
    before, cursor = baseline(caster)
    cast(caster, recipient, "spell.stoneskin")
    member = recipient.active_conditions["Stoneskin"]
    owner = member.uuid
    caster.remove_condition("Concentrating")
    data = load_animation_data()
    identity = "condition.spell.stoneskin"
    recipe = data.condition_recipes[identity]
    recipe = recipe.model_copy(update={"persistent": recipe.persistent.model_copy(update={"bodyRamp": RAMP})})
    data = replace(data, condition_recipes={**data.condition_recipes, identity: recipe})
    for state, roots in saved_views(game, before, cursor, caster, recipient).values():
        records, clock, seen = {}, 0., set()
        for root in roots:
            group = bind_choreography(state, root, data)
            records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                lineage=root, choreography=group)
            after = reduce_lineage(state, root)
            record = records.get(owner)
            if record is not None and record.applied_ms is not None:
                if "apply" not in seen:
                    seen.add("apply")
                    appearance = sample_condition_lifetimes(appearances(after, data), records, data,
                        record.applied_ms + RAMP.applicationMs / 2)[str(recipient.uuid)]
                    assert appearance.body_ramp == RAMP and appearance.ramp_strength == pytest.approx(.5)
                    late = register_condition_lifetimes({}, after, data, absolute_start_ms=9000.)
                    quiet = sample_condition_lifetimes(appearances(after, data), late, data, 9000.)[str(recipient.uuid)]
                    assert quiet.body_ramp == RAMP and quiet.ramp_strength == 1.
                if record.removed_ms is not None and "remove" not in seen:
                    seen.add("remove")
                    fading = sample_condition_lifetimes(appearances(after, data), records, data,
                        record.removed_ms + RAMP.removalMs / 2)[str(recipient.uuid)]
                    assert fading.body_ramp == RAMP and fading.ramp_strength == pytest.approx(.5)
                    gone = sample_condition_lifetimes(appearances(after, data), records, data,
                        record.removed_ms + RAMP.removalMs)[str(recipient.uuid)]
                    assert gone.body_ramp is None
            state, clock = after, clock + group.complete_ms + 25
        assert seen == {"apply", "remove"}
