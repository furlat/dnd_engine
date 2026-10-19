"""A discovered True Strike owns one real, identified weapon attack."""

import random
from uuid import uuid4

import pytest

from dnd.actions import AttackEvent, SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.base_object import BaseObject
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.player.capture import CompletedLineage, capture_lineages
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import register_true_strike


def true_strike_history(*, ranged: bool, miss: bool) -> tuple[CompletedLineage, ...]:
    """Cast a discovered True Strike with a shortsword, or a shortbow at 20 ft, and capture the caster's view."""
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        actors = {}
        weapon = "weapon.shortbow" if ranged else "weapon.shortsword"
        slot = WeaponSlot.RANGED_MAIN if ranged else WeaponSlot.MELEE_MAIN
        for role, position in (("caster", (3, 6)), ("recipient", (7 if ranged else 4, 6))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if role == "caster" else "enemies",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18),
                    strength=AbilityConfig(ability_score=10), dexterity=AbilityConfig(ability_score=10)),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=6, mode="maximums")]),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
                (build_authored_item(weapon, actor.uuid), slot),
            ))
            setup_standard_actions(actor)
            if role == "caster":
                register_true_strike(actor, caster_level=5)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors["caster"], actors["recipient"]
        encounter = Encounter(name="True Strike weapon delivery", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        choices = [(action, target) for action in get_available_actions(caster).all_actions
                   if action.behavior_id == "spell.true_strike"
                   for target in action.valid_targets if target.target_uuid == recipient.uuid]
        assert len(choices) == 1
        if ranged:
            assert choices[0][1].distance == 20
        actions = caster.action_economy.actions.normalized_score
        bonus_actions = caster.action_economy.bonus_actions.normalized_score
        original_extra = tuple(caster.equipment.extra_attack_damage_type)
        with fixed_dice_faces(*((1,) if miss else (15, 4, 4))):
            result = execute_available_action(caster, *choices[0])
        assert isinstance(result, SpellEvent) and result.phase is EventPhase.COMPLETION and not result.canceled
        assert caster.action_economy.actions.normalized_score == actions - 1
        assert caster.action_economy.bonus_actions.normalized_score == bonus_actions
        assert tuple(caster.equipment.extra_attack_damage_type) == original_extra
        attacks = [event for _, event in EventQueue.iter_events_since(baseline)
                   if isinstance(event, AttackEvent) and event.phase is EventPhase.COMPLETION]
        assert len(attacks) == 1 and attacks[0].attack_outcome is (
            AttackOutcome.CRIT_MISS if miss else AttackOutcome.HIT)
        assert recipient.get_hp() == 60 - (0 if miss else 12)
        roots = tuple(event for _, event in EventQueue.iter_events_since(baseline) if event.parent_lineage is None
                      and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
        return capture_lineages(roots, observer_uuid=caster.uuid)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)


@pytest.mark.parametrize("ranged", (False, True))
@pytest.mark.parametrize("miss", (False, True))
def test_discovered_true_strike_retains_weapon_attack_identity_damage_and_parent(ranged, miss):
    lineage, = [row for row in true_strike_history(ranged=ranged, miss=miss) if isinstance(row.root, SpellEvent)]
    spell = lineage.root
    assert isinstance(spell, SpellEvent) and spell.behavior_id == "spell.true_strike"
    attack, = [event for event in lineage.events if isinstance(event, AttackEvent)]
    assert attack.behavior_id == "action.attack"
    assert attack.provided_by_id == "spell.true_strike"
    assert attack.parent_lineage == spell.lineage_uuid
    assert attack.source_entity_uuid == spell.source_entity_uuid
    assert attack.target_entity_uuid == spell.target_entity_uuid
    assert attack.override_ability == "intelligence" and not attack.costs
    assert attack.weapon_slot is (WeaponSlot.RANGED_MAIN if ranged else WeaponSlot.MELEE_MAIN)
    assert attack.source_item_uuid is not None
    assert attack.source_item_presentation is not None
    assert attack.source_item_presentation.item_id == ("weapon.shortbow" if ranged else "weapon.shortsword")
    assert attack.attack_outcome is (AttackOutcome.CRIT_MISS if miss else AttackOutcome.HIT)
    assert [kind.value for kind in attack.damage_types] == ["Piercing", "Radiant"]
    damages = [event for event in lineage.events if isinstance(event, DamageAppliedEvent)]
    assert len(damages) == int(not miss)
    if not miss:
        damage, = damages
        assert damage.applied_damage == 12 and damage.resulting_normal_hp == 48
        assert damage.target_entity_uuid == attack.target_entity_uuid
        assert damage.resolution is not None
        assert [(part.damage_type.value, part.incoming_damage) for part in damage.resolution.components] == [
            ("Piercing", 8), ("Radiant", 4)]
        ancestors = {event.lineage_uuid: event for event in lineage.events}
        parent = damage.parent_lineage
        while parent is not None and parent != attack.lineage_uuid:
            parent = ancestors[parent].parent_lineage
        assert parent == attack.lineage_uuid
    # Captures remain useful after disposing of every native object/event.
    assert not BaseObject._registry and EventQueue.event_cursor() == 0
