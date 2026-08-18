"""The class- and origin-neutral player character body."""

from typing import Optional
from uuid import UUID

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.creature_proficiencies import CreatureProficienciesConfig
from dnd.blocks.health import HealthConfig
from dnd.entities.entity import Entity, EntityConfig
from dnd.entities.entity_creation import create_entity
from dnd.types.creatures import CreatureType, Size


def create_player_body(
    entity_uuid: UUID,
    *,
    name: str,
    description: Optional[str] = None,
    faction: Optional[str] = None,
) -> Entity:
    """Construct an undeployed neutral body for later authored composition."""
    zero = AbilityConfig(ability_score=0)
    entity = create_entity(
        entity_uuid,
        entity_kind_id="player.humanoid_body",
        name=name,
        description=(
            description
            if description is not None
            else "Class-neutral persistent player character"
        ),
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=zero,
                dexterity=zero,
                constitution=zero,
                intelligence=zero,
                wisdom=zero,
                charisma=zero,
            ),
            health=HealthConfig(hit_dices=[]),
            creature_proficiencies=CreatureProficienciesConfig(
                base_simple_weapons=False,
                base_martial_weapons=False,
                base_weapon_ids=(),
                base_armor_types=(),
                base_shields=False,
            ),
            proficiency_bonus=0,
            faction=faction,
            creature_type=CreatureType.HUMANOID,
            size=Size.MEDIUM,
            uses_death_saves=False,
        ),
    )
    return entity


__all__ = ["create_player_body"]
