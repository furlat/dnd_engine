"""Reckless Attack in a real weapon attack: advantage on Strength melee attack rolls only."""

from dataclasses import dataclass, replace
from uuid import uuid4

import pytest

from dnd.actions import Attack
from dnd.blocks.health import HealthConfig
from dnd.content.characters.builds import create_character
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.modifiers import AdvantageStatus
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.abilities import AbilityName
from dnd.types.character_progression import CharacterClass
from tests.progression.prepared_class_support import prepared_build


@dataclass(frozen=True)
class RecklessCase:
    name: str
    reckless: bool
    weapon_id: str
    slot: WeaponSlot
    foe_position: tuple[int, int]
    expected: AdvantageStatus
    ability: AbilityName | None = None


CASES = (
    RecklessCase("strength melee", False, "weapon.greataxe", WeaponSlot.MELEE_MAIN, (3, 2), AdvantageStatus.NONE),
    RecklessCase("reckless strength melee", True, "weapon.greataxe", WeaponSlot.MELEE_MAIN, (3, 2),
                 AdvantageStatus.ADVANTAGE),
    RecklessCase("reckless dexterity melee", True, "weapon.dagger", WeaponSlot.MELEE_MAIN, (3, 2), AdvantageStatus.NONE,
                 "dexterity"),
    RecklessCase("reckless ranged", True, "weapon.shortbow", WeaponSlot.RANGED_MAIN, (6, 2), AdvantageStatus.NONE),
)


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(10, 6))
    result = Game()
    yield result
    result.close()
    reset_engine_runtime()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_reckless_attack_rolls_strength_melee_weapon_attacks_with_advantage(game, case):
    barbarian = create_character(replace(prepared_build(CharacterClass.BARBARIAN, 2), faction="heroes"))
    game.deploy_entity(barbarian, (2, 2))
    foe = Entity.create(uuid4(), "Foe", config=EntityConfig(faction="foes", health=HealthConfig(max_hit_points_bonus=100)))
    foe.compose_entity()
    game.deploy_entity(foe, case.foe_position)
    weapon = build_authored_item(case.weapon_id, barbarian.uuid)
    assert barbarian.loot_item(weapon) and barbarian.equip_item(weapon.uuid, case.slot)
    Entity.update_all_entities_senses()
    if case.reckless:
        template = barbarian.get_action_template("Reckless Attack")
        assert template is not None, case.name
        activation = template.instantiate().apply()
        assert activation is not None and not activation.canceled, case.name

    with fixed_dice_faces(5, 5, 5, 5):
        result = Attack(source_entity_uuid=barbarian.uuid, target_entity_uuid=foe.uuid, weapon_slot=case.slot,
                        override_ability=case.ability).apply()

    assert result is not None and not result.canceled, (case.name, result and result.status_message)
    assert result.dice_roll is not None
    assert result.dice_roll.advantage_status is case.expected, case.name
