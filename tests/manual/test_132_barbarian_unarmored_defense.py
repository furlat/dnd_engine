"""Restore the seven displaced Barbarian Unarmored Defense regressions.

Maintained replacement for
``to_archive/examples/test_barbarian_unarmored_defense.py``. Slot and AC enums
come from the dependency-neutral equipment type module, not the old event or
component re-export paths.
"""

from uuid import uuid4

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.equipment import BodyArmor, Shield
from dnd.blocks.health import HealthConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.characters.barbarian_grants import apply_barbarian_level
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.entity import Entity, EntityConfig
from dnd.types.character_progression import (
    AppliedClassLevel,
    CharacterClass,
    ClassChoiceSelection,
)
from tests.engine.support import reset_combat_state


def _create_test_barbarian(
    *,
    dexterity: int = 14,
    constitution: int = 16,
) -> Entity:
    """Create a level-one-equivalent actor with the Barbarian AC formula."""
    actor_uuid = uuid4()
    entity = Entity.create(
        source_entity_uuid=actor_uuid,
        name="Unarmored Defense Barbarian",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=16),
                dexterity=AbilityConfig(ability_score=dexterity),
                constitution=AbilityConfig(ability_score=constitution),
                intelligence=AbilityConfig(ability_score=8),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=10),
            ),
            health=HealthConfig(),
            proficiency_bonus=2,
            position=(0, 0),
            faction="heroes",
        ),
    )
    apply_barbarian_level(
        entity,
        AppliedClassLevel(
            step_id="class.barbarian.level_1",
            character_level=1,
            class_id=CharacterClass.BARBARIAN,
            resulting_class_level=1,
            choices=(
                ClassChoiceSelection(
                    choice_id="class.barbarian.first_class.starting_equipment",
                    values=("starting_equipment.barbarian.greataxe",),
                ),
                ClassChoiceSelection(
                    choice_id="class.barbarian.proficiencies.skills",
                    values=("athletics", "perception"),
                ),
            ),
        ),
    )
    return entity


def test_unarmored_defense_basic() -> None:
    """Old group 1: AC is ten plus Dexterity plus Constitution."""
    reset_combat_state()
    barbarian = _create_test_barbarian(dexterity=14, constitution=16)

    assert barbarian.equipment.is_unarmored()
    assert barbarian.ac_bonus().normalized_score == 15


def test_unarmored_defense_disabled_by_armor() -> None:
    """Old group 2: real body armor replaces, rather than competes with, UD."""
    reset_combat_state()
    barbarian = _create_test_barbarian(dexterity=14, constitution=16)
    assert barbarian.ac_bonus().normalized_score == 15

    leather = build_authored_item("armor.leather", barbarian.uuid)
    assert isinstance(leather, BodyArmor)
    barbarian.equipment.equip(leather)

    assert not barbarian.equipment.is_unarmored()
    assert barbarian.equipment.body_armor is leather
    assert barbarian.ac_bonus().normalized_score == 13


def test_unarmored_defense_with_shield() -> None:
    """Old group 3: a shield's +2 stacks with Barbarian UD."""
    reset_combat_state()
    barbarian = _create_test_barbarian(dexterity=14, constitution=16)
    shield = build_authored_item("shield.shield", barbarian.uuid)
    assert isinstance(shield, Shield)

    barbarian.equipment.equip(shield, WeaponSlot.MELEE_OFF)

    assert barbarian.equipment.is_unarmored()
    assert barbarian.equipment.weapon_melee_off is shield
    assert barbarian.ac_bonus().normalized_score == 17


def test_removing_armor_restores_unarmored() -> None:
    """Old group 4: unequipping body armor immediately restores the UD formula."""
    reset_combat_state()
    barbarian = _create_test_barbarian(dexterity=14, constitution=16)
    initial_ac = barbarian.ac_bonus().normalized_score
    chain_shirt = build_authored_item("armor.chain_shirt", barbarian.uuid)
    assert isinstance(chain_shirt, BodyArmor)
    barbarian.equipment.equip(chain_shirt)

    assert barbarian.ac_bonus().normalized_score == 15
    assert not barbarian.equipment.is_unarmored()

    removed = barbarian.equipment.unequip(BodyPart.BODY)

    assert removed is chain_shirt
    assert barbarian.equipment.is_unarmored()
    assert barbarian.ac_bonus().normalized_score == initial_ac == 15


def test_unarmored_defense_high_con() -> None:
    """Old group 5: high Dexterity and Constitution both scale the formula."""
    reset_combat_state()
    barbarian = _create_test_barbarian(dexterity=16, constitution=20)

    assert barbarian.ac_bonus().normalized_score == 18


def test_unarmored_defense_low_con() -> None:
    """Old group 6: zero Constitution modifier adds no phantom AC."""
    reset_combat_state()
    barbarian = _create_test_barbarian(dexterity=14, constitution=10)

    assert barbarian.ac_bonus().normalized_score == 12


def test_unarmored_defense_with_cloth_armor() -> None:
    """Old group 7: cloth retains unarmored status and the Constitution bonus."""
    reset_combat_state()
    barbarian = _create_test_barbarian(dexterity=14, constitution=16)
    cloth = build_authored_item("armor.cloth", barbarian.uuid)
    assert isinstance(cloth, BodyArmor)

    barbarian.equipment.equip(cloth)

    assert barbarian.equipment.body_armor is cloth
    assert barbarian.equipment.is_unarmored()
    assert barbarian.ac_bonus().normalized_score == 15
