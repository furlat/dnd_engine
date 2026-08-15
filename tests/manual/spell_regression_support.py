"""Small, legal fixtures for the spell suites displaced by the d80 test rework."""

from uuid import uuid4

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.types.abilities import AbilityName
from dnd.core.gridmap import get_map
from dnd.types.creatures import CreatureType
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, EntityConfig
from tests.engine.support import reset_combat_state


def reset_spell_regression_arena(width: int, height: int) -> None:
    """Reset every runtime registry and create one rectangular floor map."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, width, height)


def create_spell_regression_actor(
    name: str,
    position: tuple[int, int],
    faction: str,
    *,
    spell_slots: dict[int, int] | None = None,
    creature_type: CreatureType = CreatureType.HUMANOID,
    strength: int = 10,
    wisdom: int = 10,
    charisma: int = 10,
    intelligence: int = 18,
    constitution: int = 10,
    dexterity: int = 10,
    hit_die_count: int = 20,
    proficiency_bonus: int = 4,
    spellcasting_ability: str = "intelligence",
) -> Entity:
    """Create a durable actor with an explicit, legal spell-slot budget.

    These regression tests exercise spell rules directly rather than a class
    factory, so the slot map is the authoritative caster-level fixture. This
    avoids the archived suites' mismatch where a level-5 bestiary caster was
    asked to spend sixth-, eighth-, or ninth-level slots.
    """
    actor_uuid = uuid4()
    return Entity.create(
        source_entity_uuid=actor_uuid,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=strength),
                dexterity=AbilityConfig(ability_score=dexterity),
                constitution=AbilityConfig(ability_score=constitution),
                intelligence=AbilityConfig(ability_score=intelligence),
                wisdom=AbilityConfig(ability_score=wisdom),
                charisma=AbilityConfig(ability_score=charisma),
            ),
            action_economy=ActionEconomyConfig(
                spell_slots=dict(spell_slots or {}),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=12,
                        hit_dice_count=hit_die_count,
                        mode="maximums",
                    )
                ],
            ),
            spellcasting=SpellcastingConfig(
                spellcasting_ability=spellcasting_ability,
            ),
            proficiency_bonus=proficiency_bonus,
            position=position,
            faction=faction,
            creature_type=creature_type,
        ),
    )


def force_save_result(
    entity: Entity,
    ability_name: AbilityName,
    *,
    succeeds: bool,
) -> None:
    """Give one save a deterministic noncritical pass or failure margin."""
    modifier = NumericalModifier.create(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        name=f"Spell regression {ability_name} save",
        value=100 if succeeds else -100,
    )
    saving_throw = entity.saving_throws.get_saving_throw(ability_name)
    saving_throw.bonus.self_static.add_value_modifier(modifier)
