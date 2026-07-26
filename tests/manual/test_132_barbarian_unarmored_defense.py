"""Restore the seven displaced Barbarian Unarmored Defense regressions.

Maintained replacement for
``to_archive/examples/test_barbarian_unarmored_defense.py``. Slot and AC enums
come from the dependency-neutral equipment type module, not the old event or
component re-export paths.
"""

from uuid import uuid4

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.equipment import BodyArmor, EquipmentConfig, Shield
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.equipment_types import BodyPart, UnarmoredAc, WeaponSlot
from dnd.entity import Entity, EntityConfig
from dnd.items.armors import (
    CHAIN_SHIRT_RECIPE,
    CLOTH_ARMOR_RECIPE,
    LEATHER_ARMOR_RECIPE,
    SHIELD_RECIPE,
)
from dnd.utils import reset_combat_state


def _create_test_barbarian(
    *,
    dexterity: int = 14,
    constitution: int = 16,
) -> Entity:
    """Create a level-one-equivalent actor with the Barbarian AC formula."""
    actor_uuid = uuid4()
    return Entity.create(
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
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=12,
                        hit_dice_count=1,
                        mode="maximums",
                    )
                ],
            ),
            equipment=EquipmentConfig(
                unarmored_ac_type=UnarmoredAc.BARBARIAN,
            ),
            proficiency_bonus=2,
            position=(0, 0),
            faction="heroes",
        ),
    )


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

    leather = materialize_item(
        LEATHER_ARMOR_RECIPE,
        barbarian.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
    barbarian.equipment.equip(leather)

    assert not barbarian.equipment.is_unarmored()
    assert barbarian.equipment.body_armor is leather
    assert barbarian.ac_bonus().normalized_score == 13


def test_unarmored_defense_with_shield() -> None:
    """Old group 3: a shield's +2 stacks with Barbarian UD."""
    reset_combat_state()
    barbarian = _create_test_barbarian(dexterity=14, constitution=16)
    shield = materialize_item(
        SHIELD_RECIPE,
        barbarian.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )

    barbarian.equipment.equip(shield, WeaponSlot.MELEE_OFF)

    assert barbarian.equipment.is_unarmored()
    assert barbarian.equipment.weapon_melee_off is shield
    assert barbarian.ac_bonus().normalized_score == 17


def test_removing_armor_restores_unarmored() -> None:
    """Old group 4: unequipping body armor immediately restores the UD formula."""
    reset_combat_state()
    barbarian = _create_test_barbarian(dexterity=14, constitution=16)
    initial_ac = barbarian.ac_bonus().normalized_score
    chain_shirt = materialize_item(
        CHAIN_SHIRT_RECIPE,
        barbarian.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
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
    cloth = materialize_item(
        CLOTH_ARMOR_RECIPE,
        barbarian.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )

    barbarian.equipment.equip(cloth)

    assert barbarian.equipment.body_armor is cloth
    assert barbarian.equipment.is_unarmored()
    assert barbarian.ac_bonus().normalized_score == 15
