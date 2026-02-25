"""Tests for SELF-range AOE spells appearing in available actions even with no visible enemies.

Burning Hands, Thunderwave, Lightning Bolt (SELF-range AOE) should still be
castable when no enemies are visible — the AI can target any visible position.
"""
from uuid import uuid4
from typing import Tuple

# Reset state FIRST
from dnd.utils import reset_combat_state
reset_combat_state()

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.gridmap import get_map

from dnd.spells.evocation import BurningHands, Thunderwave, LightningBolt
from dnd.actions_functional import setup_standard_actions, register_spell
import pytest


def create_solo_caster(
    name: str = "Caster",
    position: Tuple[int, int] = (5, 5),
    faction: str = "heroes",
) -> Entity:
    """Create a spellcaster with no enemies nearby."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            intelligence=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 2}
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(name=name, source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(entity)
    return entity


# --- Tests ---

class TestSelfRangeAoeAvailability:
    """SELF-range AOE spells must appear in available actions even with no visible enemies."""

    def setup_method(self) -> None:
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

    def test_burning_hands_available_no_enemies(self) -> None:
        """Burning Hands (SELF cone) appears in actions when alone."""
        caster = create_solo_caster()
        register_spell(caster, BurningHands, caster_level=5)
        Entity.update_all_entities_senses()

        result = caster.get_available_actions()
        spell_names = [a.template_name for a in result.position_actions]
        assert "Burning Hands" in spell_names, (
            f"Burning Hands should appear in position_actions, got: {spell_names}"
        )

        # Should have 0 valid targets (no enemies to precompute against)
        bh_action = next(a for a in result.position_actions if a.template_name == "Burning Hands")
        assert len(bh_action.valid_targets) == 0
        assert bh_action.can_afford is True

    def test_thunderwave_available_no_enemies(self) -> None:
        """Thunderwave (SELF cube) appears in actions when alone."""
        caster = create_solo_caster()
        register_spell(caster, Thunderwave, caster_level=5)
        Entity.update_all_entities_senses()

        result = caster.get_available_actions()
        spell_names = [a.template_name for a in result.position_actions]
        assert "Thunderwave" in spell_names, (
            f"Thunderwave should appear in position_actions, got: {spell_names}"
        )

    def test_lightning_bolt_available_no_enemies(self) -> None:
        """Lightning Bolt (SELF line) appears in actions when alone."""
        caster = create_solo_caster()
        register_spell(caster, LightningBolt, caster_level=5)
        Entity.update_all_entities_senses()

        result = caster.get_available_actions()
        spell_names = [a.template_name for a in result.position_actions]
        assert "Lightning Bolt" in spell_names, (
            f"Lightning Bolt should appear in position_actions, got: {spell_names}"
        )

    def test_self_range_aoe_with_enemies_still_has_targets(self) -> None:
        """When enemies ARE visible, SELF-range AOE still computes positions normally."""
        caster = create_solo_caster(position=(5, 5))
        register_spell(caster, BurningHands, caster_level=5)

        # Create an enemy nearby
        enemy_config = EntityConfig(
            ability_scores=AbilityScoresConfig(
                dexterity=AbilityConfig(ability_score=10),
            ),
            health=HealthConfig(
                hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="maximums")]
            ),
            proficiency_bonus=2,
            position=(5, 7),  # 2 tiles away = 10ft, within cone range
            faction="enemies",
        )
        enemy = Entity.create(name="Target", source_entity_uuid=uuid4(), config=enemy_config)
        setup_standard_actions(enemy)
        Entity.update_all_entities_senses()

        result = caster.get_available_actions()
        spell_names = [a.template_name for a in result.position_actions]
        assert "Burning Hands" in spell_names

        bh_action = next(a for a in result.position_actions if a.template_name == "Burning Hands")
        assert len(bh_action.valid_targets) > 0, "Should have valid targets when enemy is nearby"

    def test_non_self_range_aoe_still_filtered(self) -> None:
        """Non-SELF-range AOE (like Fireball, RangeType.RANGE) still works normally."""
        from dnd.spells.evocation import Fireball

        caster = create_solo_caster()
        register_spell(caster, Fireball, caster_level=5)
        Entity.update_all_entities_senses()

        result = caster.get_available_actions()
        spell_names = [a.template_name for a in result.position_actions]
        # Fireball has include_self=True so it always has caster position as prefilter
        # This test just verifies it doesn't break
        assert "Fireball" in spell_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
