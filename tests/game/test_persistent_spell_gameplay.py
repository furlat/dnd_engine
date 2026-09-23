"""Real maintained spell stories remain complete after public event serialization."""

import pygame
import pytest

from dnd.core.equipment_types import WeaponSet
from dnd.core.creature_types import DamageType
from dnd.core.events import EventType
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.player_facts import AttackFact, ConditionChangeFact, DamageFact, EquipmentFact, SpellFact, TurnFact
from game.player_reduction import reduce_lineage
from game.playback_frame import sample_playback_frame
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from tests.game.persistent_spell_scenarios import persistent_spell_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def animation_data():
    return load_animation_data()


def test_shield_bow_reaction_keeps_real_weapon_switch_and_draws_ranged_loadout(animation_data):
    history = persistent_spell_history(program="shield", shield_delivery="ranged")
    pygame.init()
    pygame.display.set_mode((640, 480))
    try:
        data, font = animation_data, pygame.font.Font(None, 16)
        for role in ("caster", "target"):
            state, heads = player_history(history, role=role)
            attacker = next(actor for actor in state.actors.values() if actor.name == "Target")
            assert attacker.visual_loadout.active_weapon_set is WeaponSet.MELEE
            for head in heads:
                attack = next((node.fact for node in head.events if isinstance(node.fact, AttackFact)), None)
                after = reduce_lineage(state, head)
                if attack is not None:
                    assert after.actors[attacker.uuid].visual_loadout.active_weapon_set is WeaponSet.RANGED
                    group = bind_choreography(state, head, data)
                    rows = {}
                    load_scene_media(scene_actors(state, data, {}), data, body_rows=rows)
                    media = load_choreography_media(group, body_rows=rows)
                    for quadrant in range(4):
                        for at in (0., group.complete_ms / 3, group.complete_ms * 2 / 3):
                            frame = sample_playback_frame(state, after, data, at, at,
                                Camera(quadrant=quadrant), {}, rows, font, font,
                                choreography=group, choreography_media=media)
                            assert any(command.evidence[0] == str(attacker.uuid) for command in frame.commands)
                    break
                state = after
            else:
                pytest.fail("The saved Shield story contains no bow attack")
    finally:
        pygame.quit()


@pytest.mark.parametrize("energy", ("Acid", "Cold", "Fire", "Lightning", "Thunder"))
def test_protection_reduces_matching_spell_damage_then_removal_restores_it_in_both_saved_views(energy, animation_data):
    history = persistent_spell_history(program="protection_from_energy", energy=energy)
    for role in ("caster", "target"):
        state, heads = player_history(history, role=role)
        caster = next(actor for actor in state.actors.values() if actor.name == "Caster")
        damages, removals, declarations = [], [], []
        for index, head in enumerate(heads):
            for node in head.events:
                fact = node.fact
                if isinstance(fact, SpellFact) and fact.behavior_id == "spell.protection_from_energy":
                    declarations.append(fact.effect_id)
                    assert fact.effect_id is not None
                    draft = animation_data.drafts[fact.effect_id]
                    group = bind_choreography(state, head, animation_data)
                    body = next(cue for cue in group.body_actions if cue.event_uuid == node.uuid)
                    assert body.recipe_id == fact.effect_id
                    assert draft.cast.weaponGlow is not None
                    assert draft.cast.weaponGlow in body.cast_layers
                if (isinstance(fact, ConditionChangeFact)
                        and fact.condition.behavior_id == "condition.spell.protection_from_energy"
                        and fact.event_type is EventType.CONDITION_REMOVAL):
                    removals.append(index)
                if isinstance(fact, DamageFact) and fact.stage == "applied" and fact.target_entity_uuid == caster.uuid:
                    assert fact.damage_type is DamageType(energy)
                    protected = any(member.behavior_id == "condition.spell.protection_from_energy"
                        for member in state.actors[caster.uuid].conditions)
                    damages.append((index, fact.applied_damage, protected))
            state = reduce_lineage(state, head)
        assert declarations and set(declarations) == {f"support.protection_from_energy.{energy.lower()}"}
        assert len(damages) == 2 and len(removals) == 1
        first, second = damages
        assert first[1] is not None and first[1] > 0 and second[1] == first[1] * 2
        assert first[2] and not second[2]
        assert first[0] < removals[0] < second[0]
        assert state.actors[caster.uuid].normal_hp == caster.normal_hp - first[1] - second[1]


def test_mage_armor_removed_by_equipping_armor_and_stays_removed_after_return_to_robes():
    history = persistent_spell_history(program="mage_armor")
    for role in ("caster", "target"):
        state, heads = player_history(history, role=role)
        caster = next(actor for actor in state.actors.values() if actor.name == "Caster")
        assert caster.armor_class == 12
        states, removal_heads = [], []
        for head in heads:
            state = reduce_lineage(state, head)
            actor = state.actors[caster.uuid]
            active = any(member.behavior_id == "condition.spell.mage_armor" for member in actor.conditions)
            states.append((actor.armor_class, active))
            if any(isinstance(node.fact, ConditionChangeFact)
                    and node.fact.condition.behavior_id == "condition.spell.mage_armor"
                    and node.fact.event_type is EventType.CONDITION_REMOVAL for node in head.events):
                removal_heads.append(head)
        assert (15, True) in states and (16, False) in states and states[-1] == (12, False)
        assert len(removal_heads) == 1
        assert any(isinstance(node.fact, EquipmentFact) for node in removal_heads[0].events)


def test_grease_failed_entry_retains_prone_until_next_turn_after_spending_movement():
    history = persistent_spell_history(program="grease", saved=False)
    for role in ("caster", "target"):
        state, heads = player_history(history, role=role)
        traveler = next(actor for actor in state.actors.values() if actor.name == "Target")
        applications, removals, prone_states = [], [], []
        ended_prone, next_turn_standing = False, False
        for index, head in enumerate(heads):
            for node in head.events:
                fact = node.fact
                if (isinstance(fact, ConditionChangeFact)
                        and fact.condition.behavior_id == "condition.prone"):
                    if fact.event_type is EventType.CONDITION_APPLICATION:
                        applications.append(index)
                    elif fact.event_type is EventType.CONDITION_REMOVAL:
                        removals.append(index)
            state = reduce_lineage(state, head)
            prone = any(member.behavior_id == "condition.prone" for member in state.actors[traveler.uuid].conditions)
            if prone:
                prone_states.append(index)
            for node in head.events:
                if isinstance(node.fact, TurnFact) and node.fact.entity_uuid == traveler.uuid:
                    if node.fact.event_type is EventType.TURN_END and prone:
                        ended_prone = True
                    if node.fact.event_type is EventType.TURN_START and ended_prone and not prone:
                        next_turn_standing = True
        assert len(applications) == len(removals) == 1
        assert applications[0] < removals[0] and prone_states
        assert ended_prone and next_turn_standing
        assert not any(member.behavior_id == "condition.prone" for member in state.actors[traveler.uuid].conditions)
        assert state.actors[traveler.uuid].normal_hp == traveler.normal_hp


@pytest.mark.parametrize("program", ("darkness", "fog_cloud", "stinking_cloud"))
def test_obscuring_area_walk_enters_field_loses_sight_and_recovers_before_spell_removal(program):
    history = persistent_spell_history(program=program)
    for role, other_name in (("target", "Caster"), ("caster", "Target")):
        state, heads = player_history(history, role=role)
        other = next(actor.uuid for actor in state.actors.values() if actor.name == other_name)
        assert state.senses is not None
        assert state.senses.entities[other].visual

        initial_position = state.senses.position
        obscured, recovered, entered = False, False, False
        for head in heads:
            state = reduce_lineage(state, head)
            senses = state.senses
            assert senses is not None
            field = next((effect for effect in senses.spatial_effects.values()
                if effect.content_ref.content_id == "spatial_effect.spell." + program), None)
            contact = senses.entities.get(other)
            visible = contact is not None and contact.visual
            if field is None:
                continue
            if role == "target" and senses.position in field.positions:
                entered = True
                assert not visible, "An ordinary observer inside the field must lose sight of the caster"
            if not visible:
                obscured = True
            elif obscured:
                recovered = True
                if role == "target":
                    assert senses.position not in field.positions
                    assert senses.position == initial_position
        assert obscured and recovered, (program, role, obscured, recovered)
        if role == "target":
            assert entered, "The review story must actually enter an affected cell"
        assert state.senses is not None
        assert not state.senses.spatial_effects
        assert state.senses.entities[other].visual


@pytest.mark.parametrize("program,energy,injured", (
    ("shield", "Fire", True),
    ("spike_growth", "Fire", True),
    ("cloudkill", "Fire", True),
    ("incendiary_cloud", "Fire", True),
    ("insect_plague", "Fire", True),
    ("enlarge_reduce", "Fire", True),
    *(("protection_from_energy", energy, True)
      for energy in ("Acid", "Cold", "Fire", "Lightning", "Thunder")),
    ("grease", "Fire", False),
    ("darkness", "Fire", False),
))
def test_review_humanoid_injuries_retain_real_blood_and_floor_residue(program, energy, injured):
    """Real commands -> saved subjective damage/material facts -> persistent floor state."""
    history = persistent_spell_history(program=program, energy=energy)
    injuries = 0
    for role in ("caster", "target"):
        state, heads = player_history(history, role=role)
        observer = next(actor.uuid for actor in state.actors.values() if actor.name == role.title())
        own_injuries = 0
        for head in heads:
            for node in head.events:
                fact = node.fact
                if (isinstance(fact, DamageFact) and fact.stage == "applied"
                        and fact.target_entity_uuid == observer
                        and fact.applied_damage is not None and fact.applied_damage > 0):
                    assert fact.body_release is not None, (program, role, fact.damage_type)
                    assert fact.body_release.release_id == "body.blood"
                    assert fact.body_release.primary_damage_type == fact.damage_type
                    assert fact.body_release.deposited_position is not None
                    own_injuries += 1
            state = reduce_lineage(state, head)
        injuries += own_injuries
        if own_injuries:
            assert any(residue.residue_id == "residue.blood"
                for tile in state.tiles.values() for residue in tile.residues), (program, role)
    assert bool(injuries) is injured
