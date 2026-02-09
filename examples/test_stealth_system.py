"""
Test stealth/perceivability system (Layer 1).

Tests:
1. BaseBlock perceivability defaults
2. Invisible flag + bypass senses
3. Stealth DC flag + passive perception
4. Senses filtering (Hidden entity not visible to low-perception observer)
5. Hidden removal on attack
6. Hidden removal on damage
7. Hidden removal on incapacitated
8. Unseen attacker advantage
9. Hide action
10. Invisible senses integration
11. Armor stealth disadvantage
12. Object perceivability
"""

from uuid import uuid4
from dnd.utils import (
    reset_combat_state,
    deal_damage_to,
    force_attack_hit, remove_attack_modifier,
    has_condition,
)
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity
from dnd.core.gridmap import get_map
from dnd.core.base_block import BaseBlock
from dnd.conditions import Invisible, Hidden, Incapacitated
from dnd.blocks.sensory import SensesType
from dnd.actions_functional import setup_standard_actions, get_available_actions, execute_by_index
from dnd.actions import Hide
from dnd.items.armors import create_chain_mail, create_leather_armor
from dnd.core.events import BodyPart
from dnd.core.modifiers import DamageType


passed = 0
failed = 0


def check(test_name: str, condition: bool):
    global passed, failed
    if condition:
        print(f"  [PASS] {test_name}")
        passed += 1
    else:
        print(f"  [FAIL] {test_name}")
        failed += 1


def test_baseblock_perceivability_defaults():
    """BaseBlock perceivability defaults to True."""
    print("\n" + "=" * 60)
    print("TEST: BaseBlock Perceivability Defaults")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    grid.set_tile(0, 0, walkable=True, name="Floor")

    entity = create_skeleton(name="Test", position=(0, 0))

    check("stealth_dc is None by default", entity.stealth_dc is None)
    check("is_invisible is False by default", entity.is_invisible is False)
    check("is_perceivable_by(None) returns True", entity.is_perceivable_by(None) is True)
    check("is_perceivable_by(some_uuid) returns True", entity.is_perceivable_by(uuid4()) is True)


def test_invisible_flag():
    """Setting is_invisible makes entity not perceivable unless observer has bypass."""
    print("\n" + "=" * 60)
    print("TEST: Invisible Flag")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    target = create_skeleton(name="Target", position=(2, 0))
    observer = create_skeleton(name="Observer", position=(0, 0))
    truesight_observer = create_skeleton(name="Truesight Observer", position=(4, 0))
    truesight_observer.senses.extra_senses = [SensesType.TRUESIGHT]

    # Set invisible directly via flag
    target.set_invisible(True)
    check("is_invisible is True after set_invisible(True)", target.is_invisible is True)
    check("Not perceivable by normal observer", target.is_perceivable_by(observer.uuid) is False)
    check("Perceivable by TRUESIGHT observer", target.is_perceivable_by(truesight_observer.uuid) is True)

    # Test BLINDSIGHT bypass
    blindsight_observer = create_skeleton(name="Blindsight Observer", position=(3, 0))
    blindsight_observer.senses.extra_senses = [SensesType.BLINDSIGHT]
    check("Perceivable by BLINDSIGHT observer", target.is_perceivable_by(blindsight_observer.uuid) is True)

    # Test TREMORSENSE bypass
    tremorsense_observer = create_skeleton(name="Tremorsense Observer", position=(1, 0))
    tremorsense_observer.senses.extra_senses = [SensesType.TREMORSENSE]
    check("Perceivable by TREMORSENSE observer", target.is_perceivable_by(tremorsense_observer.uuid) is True)

    # Clear flag
    target.set_invisible(False)
    check("Perceivable again after set_invisible(False)", target.is_perceivable_by(observer.uuid) is True)


def test_stealth_dc_flag():
    """Setting stealth_dc makes entity not perceivable by low-perception observers."""
    print("\n" + "=" * 60)
    print("TEST: Stealth DC Flag")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    target = create_skeleton(name="Hidden Target", position=(2, 0))
    low_perception = create_skeleton(name="Low Perception", position=(0, 0))
    high_perception = create_skeleton(name="High Perception", position=(4, 0))

    Entity.update_all_entities_senses()

    # Get passive perceptions
    low_pp = low_perception.get_passive_perception()
    high_pp = high_perception.get_passive_perception()
    print(f"  Low perception passive: {low_pp}")
    print(f"  High perception passive: {high_pp}")

    # Set stealth DC above low but below a very high number
    stealth_dc = low_pp + 5  # Above low perception
    target.set_stealth_dc(stealth_dc)
    print(f"  Stealth DC set to: {stealth_dc}")

    check("Not perceivable by low passive perception", target.is_perceivable_by(low_perception.uuid) is False)

    # Set stealth DC very low
    target.set_stealth_dc(1)
    check("Perceivable when stealth DC is 1", target.is_perceivable_by(low_perception.uuid) is True)

    # Clear
    target.set_stealth_dc(None)
    check("Perceivable after clearing stealth DC", target.is_perceivable_by(low_perception.uuid) is True)


def test_senses_filtering_hidden():
    """Hidden entity is filtered from observer's senses.entities."""
    print("\n" + "=" * 60)
    print("TEST: Senses Filtering (Hidden)")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    observer = create_skeleton(name="Observer", position=(0, 0))
    target = create_skeleton(name="Hidden Target", position=(2, 0))

    Entity.update_all_entities_senses()

    # Initially visible
    check("Target visible before hiding", target.uuid in observer.senses.entities)

    # Set high stealth DC so observer can't perceive
    observer_pp = observer.get_passive_perception()
    target.set_stealth_dc(observer_pp + 10)

    # Re-update senses (the perceivability event should trigger this automatically,
    # but let's also do a manual update to be sure)
    Entity.update_all_entities_senses()

    check("Target NOT visible after high stealth DC", target.uuid not in observer.senses.entities)

    # Clear stealth DC
    target.set_stealth_dc(None)
    Entity.update_all_entities_senses()

    check("Target visible again after clearing stealth DC", target.uuid in observer.senses.entities)


def test_invisible_condition_senses():
    """Invisible condition makes entity disappear from observer's senses."""
    print("\n" + "=" * 60)
    print("TEST: Invisible Condition Senses Integration")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    observer = create_skeleton(name="Observer", position=(0, 0))
    target = create_skeleton(name="Invisible Target", position=(2, 0))

    Entity.update_all_entities_senses()
    check("Target visible before Invisible", target.uuid in observer.senses.entities)

    # Apply Invisible condition
    invisible = Invisible(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid
    )
    target.add_condition(invisible)

    check("Invisible condition applied", has_condition(target, "Invisible"))
    check("is_invisible flag set", target.is_invisible is True)

    # Update senses
    Entity.update_all_entities_senses()
    check("Target NOT visible to normal observer", target.uuid not in observer.senses.entities)

    # Observer with TRUESIGHT should still see target
    observer.senses.extra_senses = [SensesType.TRUESIGHT]
    Entity.update_all_entities_senses()
    check("Target visible to TRUESIGHT observer", target.uuid in observer.senses.entities)

    # Remove Invisible
    observer.senses.extra_senses = []
    target.remove_condition("Invisible")
    check("is_invisible flag cleared", target.is_invisible is False)

    Entity.update_all_entities_senses()
    check("Target visible again after Invisible removed", target.uuid in observer.senses.entities)


def test_hidden_condition():
    """Hidden condition sets stealth DC and is removed on attack."""
    print("\n" + "=" * 60)
    print("TEST: Hidden Condition + Removal on Attack")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    attacker = create_skeleton(name="Hidden Attacker", position=(1, 0))
    target = create_skeleton(name="Target", position=(2, 0))

    setup_standard_actions(attacker)
    setup_standard_actions(target)
    Entity.update_all_entities_senses()

    # Apply Hidden with high stealth DC
    hidden = Hidden(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=attacker.uuid,
        stealth_result=30
    )
    attacker.add_condition(hidden)

    check("Hidden condition applied", has_condition(attacker, "Hidden"))
    check("stealth_dc set", attacker.stealth_dc == 30)

    # Set up encounter for attack
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(attacker, HumanController(source_entity_uuid=attacker.uuid))
    encounter.add_combatant(target, HumanController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    # Force attacker's turn
    encounter.start_turn()

    # Force hit and attack
    mod_uuid = force_attack_hit(attacker)

    # Find Attack action and get target index
    available = get_available_actions(attacker)
    attack_action = None
    target_idx = None
    for action_info in available.entity_actions:
        if "Attack" in action_info.template_name:
            attack_action = action_info
            for i, t in enumerate(action_info.valid_targets):
                if t.target_uuid == target.uuid:
                    target_idx = i
                    break
            if target_idx is not None:
                break

    if attack_action and target_idx is not None:
        execute_by_index(attacker, attack_action.template_name, target_idx)
        check("Hidden removed after attack", not has_condition(attacker, "Hidden"))
        check("stealth_dc cleared", attacker.stealth_dc is None)
    else:
        print("  [SKIP] Could not find attack action with valid target")

    remove_attack_modifier(attacker, mod_uuid)


def test_hidden_removal_on_damage():
    """Hidden is removed when entity takes damage."""
    print("\n" + "=" * 60)
    print("TEST: Hidden Removal on Damage")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    entity = create_skeleton(name="Hidden Entity", position=(0, 0))
    attacker = create_skeleton(name="Attacker", position=(1, 0))
    setup_standard_actions(entity)
    setup_standard_actions(attacker)
    Entity.update_all_entities_senses()

    # Apply Hidden
    hidden = Hidden(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        stealth_result=25
    )
    entity.add_condition(hidden)
    check("Hidden applied", has_condition(entity, "Hidden"))

    # Deal damage
    deal_damage_to(entity, 5, DamageType.SLASHING, attacker.uuid)

    check("Hidden removed after taking damage", not has_condition(entity, "Hidden"))
    check("stealth_dc cleared", entity.stealth_dc is None)


def test_hidden_removal_on_incapacitated():
    """Hidden is removed when entity becomes incapacitated."""
    print("\n" + "=" * 60)
    print("TEST: Hidden Removal on Incapacitated")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    grid.set_tile(0, 0, walkable=True, name="Floor")

    entity = create_skeleton(name="Hidden Entity", position=(0, 0))
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()

    # Apply Hidden
    hidden = Hidden(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        stealth_result=25
    )
    entity.add_condition(hidden)
    check("Hidden applied", has_condition(entity, "Hidden"))

    # Apply Incapacitated
    incap = Incapacitated(
        source_entity_uuid=uuid4(),
        target_entity_uuid=entity.uuid
    )
    entity.add_condition(incap)

    check("Hidden removed after Incapacitated", not has_condition(entity, "Hidden"))
    check("stealth_dc cleared", entity.stealth_dc is None)


def test_hide_action():
    """Hide action rolls stealth and applies Hidden condition."""
    print("\n" + "=" * 60)
    print("TEST: Hide Action")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    entity = create_skeleton(name="Sneaky Skeleton", position=(0, 0))
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()

    # Check Hide is in available actions
    available = get_available_actions(entity)
    hide_found = False
    for action_info in available.self_actions:
        if action_info.template_name == "Hide":
            hide_found = True
            break

    check("Hide action available", hide_found)

    # Set up encounter so action economy works
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Execute Hide
    hide_action = Hide(source_entity_uuid=entity.uuid)
    result = hide_action.apply()

    check("Hide action completed", result is not None and not result.canceled)
    check("Hidden condition applied", has_condition(entity, "Hidden"))

    if entity.stealth_dc is not None:
        print(f"  Stealth DC = {entity.stealth_dc}")
        check("stealth_dc is a positive number", entity.stealth_dc > 0)
    else:
        check("stealth_dc is set", False)


def test_armor_stealth_disadvantage():
    """Armor with stealth_disadvantage imposes disadvantage on stealth checks."""
    print("\n" + "=" * 60)
    print("TEST: Armor Stealth Disadvantage")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    grid.set_tile(0, 0, walkable=True, name="Floor")

    entity = create_skeleton(name="Heavy Armor", position=(0, 0))
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()

    # Check stealth bonus before armor
    stealth_before = entity.skill_bonus(target_entity_uuid=None, skill_name="stealth")
    print(f"  Stealth advantage before armor: {stealth_before.advantage}")

    from dnd.core.values import AdvantageStatus
    check("No stealth disadvantage before armor", stealth_before.advantage != AdvantageStatus.DISADVANTAGE)

    # Equip chain mail (has stealth_disadvantage=True)
    chain_mail = create_chain_mail(entity.uuid)
    entity.loot_item(chain_mail)
    entity.equip_item(chain_mail.uuid, BodyPart.BODY)

    # Check stealth bonus after armor
    stealth_after = entity.skill_bonus(target_entity_uuid=None, skill_name="stealth")
    print(f"  Stealth advantage after chain mail: {stealth_after.advantage}")
    check("Stealth disadvantage with chain mail", stealth_after.advantage == AdvantageStatus.DISADVANTAGE)

    # Unequip armor
    entity.unequip_item(BodyPart.BODY)

    stealth_unequipped = entity.skill_bonus(target_entity_uuid=None, skill_name="stealth")
    print(f"  Stealth advantage after unequip: {stealth_unequipped.advantage}")
    check("No stealth disadvantage after unequip", stealth_unequipped.advantage != AdvantageStatus.DISADVANTAGE)


def test_armor_no_stealth_disadvantage():
    """Armor without stealth_disadvantage does not affect stealth."""
    print("\n" + "=" * 60)
    print("TEST: Armor Without Stealth Disadvantage")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    grid.set_tile(0, 0, walkable=True, name="Floor")

    entity = create_skeleton(name="Light Armor", position=(0, 0))
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()

    # Equip leather armor (no stealth disadvantage)
    leather = create_leather_armor(entity.uuid)
    entity.loot_item(leather)
    entity.equip_item(leather.uuid, BodyPart.BODY)

    stealth_after = entity.skill_bonus(target_entity_uuid=None, skill_name="stealth")
    from dnd.core.values import AdvantageStatus
    check("No stealth disadvantage with leather armor", stealth_after.advantage != AdvantageStatus.DISADVANTAGE)


def test_object_perceivability():
    """Objects with stealth_dc are filtered from senses.objects."""
    print("\n" + "=" * 60)
    print("TEST: Object Perceivability")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    observer = create_skeleton(name="Observer", position=(0, 0))

    # Create a BaseItem on the ground
    from dnd.blocks.base_item import BaseItem
    item = BaseItem(
        source_entity_uuid=uuid4(),
        name="Hidden Chest",
        position=(2, 0)
    )
    grid.place_object(item.uuid, (2, 0))

    Entity.update_all_entities_senses()

    check("Item visible before hiding", item.uuid in observer.senses.objects)

    # Set stealth DC on the item
    observer_pp = observer.get_passive_perception()
    item.set_stealth_dc(observer_pp + 10)

    Entity.update_all_entities_senses()
    check("Item NOT visible after high stealth DC", item.uuid not in observer.senses.objects)

    # Clear
    item.set_stealth_dc(None)
    Entity.update_all_entities_senses()
    check("Item visible again after clearing stealth DC", item.uuid in observer.senses.objects)


if __name__ == "__main__":
    print("=" * 60)
    print("STEALTH SYSTEM TESTS (Layer 1)")
    print("=" * 60)

    test_baseblock_perceivability_defaults()
    test_invisible_flag()
    test_stealth_dc_flag()
    test_senses_filtering_hidden()
    test_invisible_condition_senses()
    test_hidden_condition()
    test_hidden_removal_on_damage()
    test_hidden_removal_on_incapacitated()
    test_hide_action()
    test_armor_stealth_disadvantage()
    test_armor_no_stealth_disadvantage()
    test_object_perceivability()

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
    print("=" * 60)

    if failed > 0:
        exit(1)
    else:
        print("ALL TESTS PASSED!")
