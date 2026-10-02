"""Creation-time composition produces transferable gear through native gameplay."""
from uuid import uuid4
from dataclasses import replace

import pytest

from dnd.blocks.health import HealthConfig
from dnd.actions import Attack
from dnd.content.items.authored_item_builders import build_authored_item, materialize_item_definition
from dnd.content.items.authored_item_definitions import AUTHORED_WEAPON_DEFINITIONS, AUTHORED_WEARABLE_DEFINITIONS
from dnd.content.items.item_composition import named_item, with_extra_damage, with_weapon_bonus, with_wearer_bonus, with_unseen_strike
from dnd.conditions import Blinded
from dnd.core import dice as dice_module
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventQueue, EventType
from dnd.core.item_properties import AdditionalDamage, UnseenStrike, WearerValue
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def fresh_runtime():
    reset_engine_runtime(grid_size=(8, 5))


def actor(game, name, position):
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=EntityConfig(faction=name, health=HealthConfig(max_hit_points_bonus=100)))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def test_definition_bonus_replaces_and_packets_coexist_in_combat(monkeypatch):
    base = AUTHORED_WEAPON_DEFINITIONS["weapon.longsword"]
    definition = named_item(with_weapon_bonus(with_weapon_bonus(base, bonus=1), bonus=2),
                            item_id="weapon.test_elemental_longsword", name="Elemental Longsword")
    definition = with_extra_damage(definition, packet=AdditionalDamage(6, 1, DamageType.FIRE))
    definition = with_extra_damage(definition, packet=AdditionalDamage(4, 1, DamageType.COLD))
    assert base.attack_bonus == 0 and not base.additional_damage
    assert definition.attack_bonus == definition.damage_bonus == 2
    game = Game()
    attacker = actor(game, "Attacker", (1, 1))
    target = actor(game, "Target", (2, 1))
    item = materialize_item_definition(definition, attacker.uuid)
    assert attacker.loot_item(item) and attacker.equip_item(item.uuid, WeaponSlot.MELEE_MAIN)
    Entity.update_all_entities_senses()
    monkeypatch.setattr(dice_module.random, "randint", lambda low, high: high)
    result = Attack(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid,
                    weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    assert result is not None and not result.canceled
    roll = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)[-1]
    assert [packet.damage.damage_type for packet in roll.damage_packets] == [DamageType.SLASHING, DamageType.FIRE, DamageType.COLD]
    with pytest.raises(ValueError, match="Duplicate"):
        with_extra_damage(definition, packet=AdditionalDamage(6, 1, DamageType.FIRE))


@pytest.mark.parametrize("definition", [
    AUTHORED_WEAPON_DEFINITIONS["weapon.longsword"],
    AUTHORED_WEARABLE_DEFINITIONS["apparel.crown"],
])
def test_equipment_stacking_is_rejected_in_authoring_instead_of_erased(definition):
    with pytest.raises(ValueError, match="equipment stacks are unsupported"):
        replace(definition, stack_id="copies", max_stack=5)
    with pytest.raises(ValueError, match="not a stackable item"):
        materialize_item_definition(definition, uuid4(), quantity=2)


@pytest.mark.parametrize("base_id,slot,target,bonus", [
    ("apparel.crown", BodyPart.HEAD, WearerValue.CHARISMA, 3),
    ("weapon.quarterstaff", WeaponSlot.MELEE_MAIN, WearerValue.SPELL_ATTACK, 1),
])
def test_composed_wearer_property_moves_and_retires_exactly(base_id, slot, target, bonus):
    game = Game()
    first = actor(game, "First", (1, 1))
    second = actor(game, "Second", (2, 1))
    base = (AUTHORED_WEAPON_DEFINITIONS if base_id.startswith("weapon.") else AUTHORED_WEARABLE_DEFINITIONS)[base_id]
    definition = named_item(with_wearer_bonus(base, target=target, bonus=bonus, name="Shared Bonus"),
                            item_id="test.transferable_bonus", name="Transferable Bonus")
    item = materialize_item_definition(definition, first.uuid)
    def score(entity):
        values = entity.get_item_wearer_values()
        return (values.charisma if target is WearerValue.CHARISMA else values.spell_attack).normalized_score
    baseline = score(first), score(second)
    assert first.loot_item(item)
    for _ in range(2):
        assert first.equip_item(item.uuid, slot)
        assert score(first) == baseline[0] + bonus
        assert first.unequip_item(slot) is item
        assert score(first) == baseline[0]
    assert first.drop_item(item.uuid) is item
    assert second.loot_item(item) and second.equip_item(item.uuid, slot)
    assert (score(first), score(second)) == (baseline[0], baseline[1] + bonus)
    item.retire()
    assert score(second) == baseline[1]


def test_conditional_damage_composes_on_a_different_base_and_keeps_weapon_scope(monkeypatch):
    game = Game()
    attacker = actor(game, "Attacker", (1, 1))
    target = actor(game, "Target", (2, 1))
    definition = named_item(with_unseen_strike(AUTHORED_WEAPON_DEFINITIONS["weapon.shortsword"],
        property=UnseenStrike(die=4, damage_type=DamageType.COLD)),
        item_id="weapon.test_unseen_shortsword", name="Unseen Shortsword")
    item = materialize_item_definition(definition, attacker.uuid)
    assert attacker.loot_item(item) and attacker.equip_item(item.uuid, WeaponSlot.MELEE_MAIN)
    bow = build_authored_item("weapon.shortbow", attacker.uuid)
    assert attacker.loot_item(bow) and attacker.equip_item(bow.uuid, WeaponSlot.RANGED_MAIN)
    target.add_condition(Blinded(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    Entity.update_all_entities_senses()
    monkeypatch.setattr(dice_module.random, "randint", lambda low, high: high)
    for slot, expected in [(WeaponSlot.MELEE_MAIN, 2), (WeaponSlot.RANGED_MAIN, 1)]:
        attacker.action_economy.reset_all_costs()
        result = Attack(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid, weapon_slot=slot).apply()
        assert result is not None and not result.canceled
        assert len(EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)[-1].damage_packets) == expected
