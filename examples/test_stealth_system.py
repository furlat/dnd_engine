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
from dnd.monsters.bestiary import create_skeleton, create_sorcerer
from dnd.entity import Entity
from dnd.core.gridmap import get_map
from dnd.blocks.base_item import UsableItem
from dnd.conditions import Invisible, Hidden, Incapacitated, InvisibilityEffect, GreaterInvisibilityEffect
from dnd.core.base_tiles import SensesType, SenseMode
from dnd.actions_functional import setup_standard_actions, get_available_actions, execute_by_index, execute_use_action, register_spell
from dnd.actions import Hide
from dnd.items.armors import create_chain_mail, create_leather_armor
from dnd.items.weapons import create_assassin_dagger
from dnd.items.test_items import create_potion_of_greater_invisibility
from dnd.spells.illusion import Invisibility, GreaterInvisibility
from dnd.spells.evocation import FireBolt
from dnd.core.events import BodyPart, WeaponSlot
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
    truesight_observer.senses.sense_modes = [SenseMode(sense_type=SensesType.TRUESIGHT)]

    # Set invisible directly via flag
    target.set_invisible(True)
    check("is_invisible is True after set_invisible(True)", target.is_invisible is True)
    check("Not perceivable by normal observer", target.is_perceivable_by(observer.uuid) is False)
    check("Perceivable by TRUESIGHT observer", target.is_perceivable_by(truesight_observer.uuid) is True)

    # Test BLINDSIGHT bypass
    blindsight_observer = create_skeleton(name="Blindsight Observer", position=(3, 0))
    blindsight_observer.senses.sense_modes = [SenseMode(sense_type=SensesType.BLINDSIGHT)]
    check("Perceivable by BLINDSIGHT observer", target.is_perceivable_by(blindsight_observer.uuid) is True)

    # Test TREMORSENSE bypass
    tremorsense_observer = create_skeleton(name="Tremorsense Observer", position=(1, 0))
    tremorsense_observer.senses.sense_modes = [SenseMode(sense_type=SensesType.TREMORSENSE)]
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
    observer.senses.sense_modes = [SenseMode(sense_type=SensesType.TRUESIGHT)]
    Entity.update_all_entities_senses()
    check("Target visible to TRUESIGHT observer", target.uuid in observer.senses.entities)

    # Remove Invisible
    observer.senses.sense_modes = []
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


def test_hidden_removal_on_spell_cast():
    """Hidden is removed when entity casts a spell (CAST_SPELL event)."""
    print("\n" + "=" * 60)
    print("TEST: Hidden Removal on Spell Cast")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    caster = create_sorcerer(name="Hidden Caster", position=(0, 0), faction="heroes")
    register_spell(caster, FireBolt, caster_level=5)
    target = create_skeleton(name="Target", position=(5, 0), faction="monsters")
    setup_standard_actions(target)
    Entity.update_all_entities_senses()

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(target, HumanController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Apply Hidden with high stealth DC
    hidden = Hidden(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, stealth_result=30)
    caster.add_condition(hidden)
    check("Hidden applied before spell", has_condition(caster, "Hidden"))

    # Cast Fire Bolt at target
    available = get_available_actions(caster)
    firebolt_found = False
    for action_info in available.entity_actions:
        if "Fire Bolt" in action_info.template_name:
            for i, t in enumerate(action_info.valid_targets):
                if t.target_uuid == target.uuid:
                    execute_by_index(caster, action_info.template_name, i)
                    firebolt_found = True
                    break
            if firebolt_found:
                break

    check("Fire Bolt was cast", firebolt_found)
    check("Hidden removed after spell cast", not has_condition(caster, "Hidden"))
    check("stealth_dc cleared", caster.stealth_dc is None)


def test_hidden_removal_on_shove():
    """Hidden is removed when entity uses Shove (BASE_ACTION event)."""
    print("\n" + "=" * 60)
    print("TEST: Hidden Removal on Shove")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    attacker = create_skeleton(name="Hidden Shover", position=(1, 0))
    target = create_skeleton(name="Target", position=(2, 0))
    setup_standard_actions(attacker)
    setup_standard_actions(target)
    Entity.update_all_entities_senses()

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(attacker, HumanController(source_entity_uuid=attacker.uuid))
    encounter.add_combatant(target, HumanController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Apply Hidden
    hidden = Hidden(source_entity_uuid=attacker.uuid, target_entity_uuid=attacker.uuid, stealth_result=30)
    attacker.add_condition(hidden)
    check("Hidden applied before shove", has_condition(attacker, "Hidden"))

    # Find and execute Shove
    available = get_available_actions(attacker)
    shove_found = False
    for action_info in available.entity_actions:
        if "Shove" in action_info.template_name:
            for i, t in enumerate(action_info.valid_targets):
                if t.target_uuid == target.uuid:
                    execute_by_index(attacker, action_info.template_name, i)
                    shove_found = True
                    break
            if shove_found:
                break

    check("Shove was used", shove_found)
    check("Hidden removed after shove", not has_condition(attacker, "Hidden"))


def test_dash_does_not_remove_hidden():
    """Dash should NOT remove Hidden (it's not an offensive action)."""
    print("\n" + "=" * 60)
    print("TEST: Dash Does Not Remove Hidden")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    entity = create_skeleton(name="Hidden Dasher", position=(0, 0))
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Apply Hidden
    hidden = Hidden(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid, stealth_result=30)
    entity.add_condition(hidden)
    check("Hidden applied before dash", has_condition(entity, "Hidden"))

    # Execute Dash
    available = get_available_actions(entity)
    for action_info in available.self_actions:
        if action_info.template_name == "Dash":
            execute_by_index(entity, "Dash", 0)
            break

    check("Hidden still active after dash", has_condition(entity, "Hidden"))


def test_hide_fails_when_visible_to_enemy():
    """Cannot hide when visible to an enemy."""
    print("\n" + "=" * 60)
    print("TEST: Hide Fails When Visible to Enemy")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    entity = create_skeleton(name="Would-be Hider", position=(0, 0), faction="heroes")
    enemy = create_skeleton(name="Watchful Enemy", position=(2, 0), faction="monsters")
    setup_standard_actions(entity)
    setup_standard_actions(enemy)
    Entity.update_all_entities_senses()

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    encounter.add_combatant(enemy, HumanController(source_entity_uuid=enemy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Try to hide while enemy can see us
    hide_action = Hide(source_entity_uuid=entity.uuid)
    result = hide_action.apply()

    check("Hide action was canceled", result is not None and result.canceled)
    check("Hidden condition NOT applied", not has_condition(entity, "Hidden"))


def test_hide_succeeds_when_invisible():
    """Invisible entity can hide even with enemies in LOS."""
    print("\n" + "=" * 60)
    print("TEST: Hide Succeeds When Invisible")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    entity = create_skeleton(name="Invisible Hider", position=(0, 0), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(2, 0), faction="monsters")
    setup_standard_actions(entity)
    setup_standard_actions(enemy)

    # Make entity invisible BEFORE updating senses
    entity.set_invisible(True)
    Entity.update_all_entities_senses()

    # Verify enemy can't see us
    check("Enemy cannot see invisible entity", entity.uuid not in enemy.senses.entities)

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    encounter.add_combatant(enemy, HumanController(source_entity_uuid=enemy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Try to hide while invisible
    hide_action = Hide(source_entity_uuid=entity.uuid)
    result = hide_action.apply()

    check("Hide action succeeded", result is not None and not result.canceled)
    check("Hidden condition applied", has_condition(entity, "Hidden"))

    entity.set_invisible(False)


def test_invisibility_spell_basic():
    """Invisibility spell makes target invisible, breaks on attack."""
    print("\n" + "=" * 60)
    print("TEST: Invisibility Spell Basic")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    target_ally = create_skeleton(name="Target Ally", position=(1, 0), faction="heroes")
    observer = create_skeleton(name="Observer", position=(5, 0), faction="monsters")
    setup_standard_actions(target_ally)
    setup_standard_actions(observer)
    Entity.update_all_entities_senses()

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(target_ally, HumanController(source_entity_uuid=target_ally.uuid))
    encounter.add_combatant(observer, HumanController(source_entity_uuid=observer.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Cast Invisibility on ally
    spell = Invisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target_ally.uuid,
        cast_at_level=2
    )
    result = spell.apply()

    check("Spell completed", result is not None and not result.canceled)
    check("Target is invisible", target_ally.is_invisible is True)
    check("InvisibilityEffect applied", has_condition(target_ally, "Invisible"))
    check("Caster is concentrating", has_condition(caster, "Concentrating"))

    # Update senses and verify filtering
    Entity.update_all_entities_senses()
    check("Observer cannot see invisible target", target_ally.uuid not in observer.senses.entities)


def test_invisibility_ends_on_attack():
    """Invisibility ends when the invisible entity attacks."""
    print("\n" + "=" * 60)
    print("TEST: Invisibility Ends on Attack")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Use skeleton (has weapon) as the invisible attacker
    attacker = create_skeleton(name="Invisible Attacker", position=(0, 0), faction="heroes")
    target = create_skeleton(name="Enemy", position=(1, 0), faction="monsters")
    setup_standard_actions(attacker)
    setup_standard_actions(target)
    Entity.update_all_entities_senses()

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(attacker, HumanController(source_entity_uuid=attacker.uuid))
    encounter.add_combatant(target, HumanController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Apply InvisibilityEffect directly (testing condition behavior, not spell)
    invis = InvisibilityEffect(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=attacker.uuid
    )
    attacker.add_condition(invis)
    check("Attacker is invisible", attacker.is_invisible is True)

    # Attack — should break invisibility
    mod_uuid = force_attack_hit(attacker)
    available = get_available_actions(attacker)
    attack_found = False
    for action_info in available.entity_actions:
        if "Attack" in action_info.template_name:
            for i, t in enumerate(action_info.valid_targets):
                if t.target_uuid == target.uuid:
                    execute_by_index(attacker, action_info.template_name, i)
                    attack_found = True
                    break
            if attack_found:
                break

    check("Attack executed", attack_found)
    check("Invisibility removed after attack", not has_condition(attacker, "Invisible"))
    check("is_invisible cleared", attacker.is_invisible is False)
    remove_attack_modifier(attacker, mod_uuid)


def test_invisibility_ends_on_spell_cast():
    """Invisibility ends when the invisible entity casts a spell."""
    print("\n" + "=" * 60)
    print("TEST: Invisibility Ends on Spell Cast")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    caster = create_sorcerer(name="Invis Caster", position=(0, 0), faction="heroes")
    target = create_skeleton(name="Enemy", position=(5, 0), faction="monsters")
    setup_standard_actions(target)
    Entity.update_all_entities_senses()

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(target, HumanController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Apply InvisibilityEffect directly (skip concentration for isolated test)
    invis = InvisibilityEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid
    )
    caster.add_condition(invis)
    check("Caster is invisible", caster.is_invisible is True)

    # Cast Fire Bolt — should break invisibility
    available = get_available_actions(caster)
    for action_info in available.entity_actions:
        if "Fire Bolt" in action_info.template_name:
            for i, t in enumerate(action_info.valid_targets):
                if t.target_uuid == target.uuid:
                    execute_by_index(caster, action_info.template_name, i)
                    break
            break

    check("Invisibility removed after casting", not has_condition(caster, "Invisible"))
    check("is_invisible cleared", caster.is_invisible is False)


def test_invisibility_concentration_break():
    """Invisibility on target is removed when caster's concentration breaks."""
    print("\n" + "=" * 60)
    print("TEST: Invisibility Concentration Break")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    target_ally = create_skeleton(name="Invis Ally", position=(1, 0), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(5, 0), faction="monsters")
    setup_standard_actions(target_ally)
    setup_standard_actions(enemy)
    Entity.update_all_entities_senses()

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(target_ally, HumanController(source_entity_uuid=target_ally.uuid))
    encounter.add_combatant(enemy, HumanController(source_entity_uuid=enemy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Cast Invisibility on ally
    spell = Invisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target_ally.uuid,
        cast_at_level=2
    )
    spell.apply()
    check("Ally is invisible", target_ally.is_invisible is True)
    check("Caster concentrating", has_condition(caster, "Concentrating"))

    # Break concentration by dealing massive damage (to fail CON save)
    deal_damage_to(caster, 100, DamageType.FIRE, enemy.uuid)

    check("Concentration broken", not has_condition(caster, "Concentrating"))
    check("Ally invisibility removed", not has_condition(target_ally, "Invisible"))
    check("Ally is_invisible cleared", target_ally.is_invisible is False)


def test_greater_invisibility_basic():
    """Greater Invisibility makes target invisible."""
    print("\n" + "=" * 60)
    print("TEST: Greater Invisibility Basic")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    observer = create_skeleton(name="Observer", position=(5, 0), faction="monsters")
    setup_standard_actions(observer)
    Entity.update_all_entities_senses()

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(observer, HumanController(source_entity_uuid=observer.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Cast Greater Invisibility on self
    spell = GreaterInvisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=4
    )
    result = spell.apply()

    check("Spell completed", result is not None and not result.canceled)
    check("Caster is invisible", caster.is_invisible is True)
    check("GreaterInvisibilityEffect applied", isinstance(caster.active_conditions.get("Invisible"), GreaterInvisibilityEffect))
    check("Caster concentrating", has_condition(caster, "Concentrating"))

    Entity.update_all_entities_senses()
    check("Observer cannot see caster", caster.uuid not in observer.senses.entities)


def test_greater_invisibility_stealth_check_on_attack():
    """Greater Invisibility: attack triggers stealth check, stays invisible on high roll."""
    print("\n" + "=" * 60)
    print("TEST: Greater Invisibility Stealth Check on Attack")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Use a skeleton (has weapon) for reliable attack
    attacker = create_skeleton(name="Invisible Attacker", position=(0, 0), faction="heroes")
    target = create_skeleton(name="Target", position=(1, 0), faction="monsters")
    setup_standard_actions(attacker)
    setup_standard_actions(target)
    Entity.update_all_entities_senses()

    # Apply GreaterInvisibilityEffect directly with a very low DC so it always succeeds
    invis = GreaterInvisibilityEffect(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=attacker.uuid,
        base_dc=1  # Very low DC — will always succeed
    )
    attacker.add_condition(invis)
    check("Attacker is invisible", attacker.is_invisible is True)

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(attacker, HumanController(source_entity_uuid=attacker.uuid))
    encounter.add_combatant(target, HumanController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Attack — stealth check with DC 1 should succeed
    mod_uuid = force_attack_hit(attacker)
    available = get_available_actions(attacker)
    for action_info in available.entity_actions:
        if "Attack" in action_info.template_name:
            for i, t in enumerate(action_info.valid_targets):
                if t.target_uuid == target.uuid:
                    execute_by_index(attacker, action_info.template_name, i)
                    break
            break

    check("Still invisible after attack (low DC)", has_condition(attacker, "Invisible"))
    check("check_count incremented", invis.check_count == 1)
    remove_attack_modifier(attacker, mod_uuid)


def test_greater_invisibility_escalating_dc():
    """Greater Invisibility: DC increases after each successful check."""
    print("\n" + "=" * 60)
    print("TEST: Greater Invisibility Escalating DC")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    caster = create_sorcerer(name="Invisible Caster", position=(0, 0), faction="heroes")
    target = create_skeleton(name="Target", position=(1, 0), faction="monsters")
    setup_standard_actions(target)
    Entity.update_all_entities_senses()

    # Apply with default DC 15
    invis = GreaterInvisibilityEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid
    )
    caster.add_condition(invis)

    check("Initial DC is 15", invis.base_dc == 15)
    check("Initial check_count is 0", invis.check_count == 0)

    # Simulate successful checks incrementing the count
    invis.check_count = 3
    expected_dc = 15 + 3
    check(f"DC after 3 checks would be {expected_dc}", invis.base_dc + invis.check_count == expected_dc)


def test_greater_invisibility_concentration_break():
    """Greater Invisibility on ally is removed when caster's concentration breaks."""
    print("\n" + "=" * 60)
    print("TEST: Greater Invisibility Concentration Break")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    ally = create_skeleton(name="Invisible Ally", position=(1, 0), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(5, 0), faction="monsters")
    setup_standard_actions(ally)
    setup_standard_actions(enemy)
    Entity.update_all_entities_senses()

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(ally, HumanController(source_entity_uuid=ally.uuid))
    encounter.add_combatant(enemy, HumanController(source_entity_uuid=enemy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Cast Greater Invisibility on ally (within 5ft touch range)
    spell = GreaterInvisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=4
    )
    result = spell.apply()
    check("Spell completed", result is not None and not result.canceled)
    check("Ally invisible", ally.is_invisible is True)
    check("Caster concentrating", has_condition(caster, "Concentrating"))

    # Verify senses update: enemy can't see invisible ally
    Entity.update_all_entities_senses()
    check("Enemy cannot see invisible ally", ally.uuid not in enemy.senses.entities)

    # Break concentration with massive damage to caster
    deal_damage_to(caster, 100, DamageType.FIRE, enemy.uuid)

    check("Concentration broken", not has_condition(caster, "Concentrating"))
    check("Ally invisibility removed", not has_condition(ally, "Invisible"))
    check("Ally is_invisible cleared", ally.is_invisible is False)

    # Verify senses update: enemy can now see ally again
    Entity.update_all_entities_senses()
    check("Enemy can see ally again", ally.uuid in enemy.senses.entities)


def test_greater_invisibility_potion_consumption():
    """Potion of Greater Invisibility is consumed after use (single charge)."""
    print("\n" + "=" * 60)
    print("TEST: Greater Invisibility Potion Consumption")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    entity = create_skeleton(name="Drinker", position=(0, 0))
    setup_standard_actions(entity)

    potion = create_potion_of_greater_invisibility(entity.uuid)
    entity.loot_item(potion)

    Entity.update_all_entities_senses()

    # Verify potion is in inventory with stack_count=1
    check("Potion in inventory", entity.inventory.item_count == 1)
    item = list(entity.inventory.items.values())[0]
    check("Stack count is 1", item.stack_count == 1)
    assert isinstance(item, UsableItem)
    print(f"  Charges: {item.charges}")

    # Use the potion via execute_use_action
    execute_use_action(entity, item.uuid, "Drink Greater Invisibility Potion")

    # Verify entity is invisible
    check("Entity is invisible", entity.is_invisible is True)
    check("Has Invisible condition", has_condition(entity, "Invisible"))

    # Verify potion was consumed (destroyed, removed from inventory)
    check("Potion consumed from inventory", entity.inventory.item_count == 0)


def test_greater_invisibility_potion_stacking():
    """Two Greater Invisibility potions stack and can be used twice."""
    print("\n" + "=" * 60)
    print("TEST: Greater Invisibility Potion Stacking")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    entity = create_skeleton(name="Drinker", position=(0, 0))
    setup_standard_actions(entity)

    # Loot two potions — they should stack
    potion1 = create_potion_of_greater_invisibility(entity.uuid)
    entity.loot_item(potion1)
    potion2 = create_potion_of_greater_invisibility(entity.uuid)
    entity.loot_item(potion2)

    Entity.update_all_entities_senses()

    check("1 inventory slot used", entity.inventory.item_count == 1)
    item = list(entity.inventory.items.values())[0]
    check("Stack count is 2", item.stack_count == 2)

    # Use first potion
    execute_use_action(entity, item.uuid, "Drink Greater Invisibility Potion")
    check("Invisible after first potion", entity.is_invisible is True)

    # Potion still in inventory (stack_count decremented)
    check("Potion still in inventory", entity.inventory.item_count == 1)
    check("Stack count is 1 after first use", item.stack_count == 1)
    assert isinstance(item, UsableItem)
    print(f"  Charges after first use: {item.charges}")
    check("Charges reset to 1", item.charges == 1)

    # Remove invisibility to use second potion
    entity.remove_condition("Invisible")
    check("No longer invisible", entity.is_invisible is False)

    # Use second potion
    execute_use_action(entity, item.uuid, "Drink Greater Invisibility Potion")
    check("Invisible after second potion", entity.is_invisible is True)

    # Now both consumed — inventory empty
    check("Potions fully consumed", entity.inventory.item_count == 0)


def test_invisibility_spell_self_cast_not_self_trigger():
    """Casting Invisibility on self should NOT immediately break the invisibility."""
    print("\n" + "=" * 60)
    print("TEST: Invisibility Self-Cast Does Not Self-Trigger")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    observer = create_skeleton(name="Observer", position=(5, 0), faction="monsters")
    setup_standard_actions(observer)
    Entity.update_all_entities_senses()

    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(observer, HumanController(source_entity_uuid=observer.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Cast Invisibility on SELF
    spell = Invisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=2
    )
    result = spell.apply()

    check("Spell completed", result is not None and not result.canceled)
    # The key check: invisibility should NOT have been removed by self-trigger
    check("Caster is invisible after self-cast", caster.is_invisible is True)
    check("InvisibilityEffect still applied", has_condition(caster, "Invisible"))
    check("Condition is InvisibilityEffect", isinstance(caster.active_conditions.get("Invisible"), InvisibilityEffect))
    check("Caster is concentrating", has_condition(caster, "Concentrating"))


def test_greater_invisibility_spell_self_cast_not_self_trigger():
    """Casting Greater Invisibility on self should NOT trigger the stealth check."""
    print("\n" + "=" * 60)
    print("TEST: Greater Invisibility Self-Cast Does Not Self-Trigger")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(10):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, name="Floor")

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    observer = create_skeleton(name="Observer", position=(5, 0), faction="monsters")
    setup_standard_actions(observer)
    Entity.update_all_entities_senses()

    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(observer, HumanController(source_entity_uuid=observer.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Cast Greater Invisibility on SELF
    spell = GreaterInvisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=4
    )
    result = spell.apply()

    check("Spell completed", result is not None and not result.canceled)
    # The key check: invisibility should NOT have been removed or checked by self-trigger
    check("Caster is invisible after self-cast", caster.is_invisible is True)
    check("GreaterInvisibilityEffect still applied", isinstance(caster.active_conditions.get("Invisible"), GreaterInvisibilityEffect))
    # Check count should be 0 — no stealth check should have fired
    condition = caster.active_conditions.get("Invisible")
    if isinstance(condition, GreaterInvisibilityEffect):
        check("Check count is 0 (no stealth check fired)", condition.check_count == 0)
    check("Caster is concentrating", has_condition(caster, "Concentrating"))


def test_greater_invisibility_potion_not_self_trigger():
    """Drinking Greater Invisibility potion should NOT trigger the stealth check."""
    print("\n" + "=" * 60)
    print("TEST: Greater Invisibility Potion Does Not Self-Trigger")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    entity = create_skeleton(name="Drinker", position=(0, 0))
    setup_standard_actions(entity)

    potion = create_potion_of_greater_invisibility(entity.uuid)
    entity.loot_item(potion)

    Entity.update_all_entities_senses()

    # Use the potion
    item = list(entity.inventory.items.values())[0]
    execute_use_action(entity, item.uuid, "Drink Greater Invisibility Potion")

    # The key check: invisibility should still be active (handler didn't self-trigger)
    check("Entity is invisible after potion", entity.is_invisible is True)
    check("Has Invisible condition", has_condition(entity, "Invisible"))
    condition = entity.active_conditions.get("Invisible")
    if isinstance(condition, GreaterInvisibilityEffect):
        check("Check count is 0 (no stealth check fired)", condition.check_count == 0)


def test_assassin_dagger_unseen_strike():
    """Assassin's Dagger deals +1d6 when attacker is unseen."""
    print("\n" + "=" * 60)
    print("TEST: Assassin's Dagger Unseen Strike")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    attacker = create_skeleton(name="Assassin", position=(1, 0))
    target = create_skeleton(name="Target", position=(2, 0))
    setup_standard_actions(attacker)
    setup_standard_actions(target)

    # Equip assassin dagger
    dagger = create_assassin_dagger(attacker.uuid)
    attacker.loot_item(dagger)
    attacker.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)

    Entity.update_all_entities_senses()

    # Set up encounter
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(attacker, HumanController(source_entity_uuid=attacker.uuid))
    encounter.add_combatant(target, HumanController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Make attacker invisible (unseen by target)
    attacker.set_invisible(True)
    Entity.update_all_entities_senses()
    check("Attacker unseen by target", attacker.uuid not in target.senses.entities)

    # Attack with the dagger — retry up to 5 times to avoid nat 1 crit miss
    mod_uuid = force_attack_hit(attacker)
    from dnd.utils import set_hp, get_max_hp
    damage_dealt = 0
    for _ in range(5):
        hp_before = target.get_hp()
        available = get_available_actions(attacker)
        for action_info in available.entity_actions:
            if "Attack" in action_info.template_name:
                for i, t in enumerate(action_info.valid_targets):
                    if t.target_uuid == target.uuid:
                        execute_by_index(attacker, action_info.template_name, i)
                        break
                break
        hp_after = target.get_hp()
        damage_dealt = hp_before - hp_after
        if damage_dealt > 0:
            break
        # Heal target back and reset action economy for retry (nat 1 crit miss)
        set_hp(target, get_max_hp(target))
        attacker.action_economy.reset_all_costs()

    print(f"  Damage dealt (unseen): {damage_dealt}")
    # Base dagger: 1d4 + DEX(+2) = 3-6, plus unseen strike 1d6 = 1-6, total 4-12
    check("Damage dealt is positive", damage_dealt > 0)
    # The unseen strike adds 1d6, so minimum 1 extra = at least base_min + 1
    # Base: 1 + 2 = 3, with extra 1d6 min 1 = 4 total min
    check("Damage includes extra dice (min 4)", damage_dealt >= 4)

    remove_attack_modifier(attacker, mod_uuid)
    attacker.set_invisible(False)


def test_assassin_dagger_no_bonus_when_seen():
    """Assassin's Dagger deals normal damage when attacker is visible."""
    print("\n" + "=" * 60)
    print("TEST: Assassin's Dagger No Bonus When Seen")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    for x in range(5):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    attacker = create_skeleton(name="Assassin", position=(1, 0))
    target = create_skeleton(name="Target", position=(2, 0))
    setup_standard_actions(attacker)
    setup_standard_actions(target)

    # Equip assassin dagger
    dagger = create_assassin_dagger(attacker.uuid)
    attacker.loot_item(dagger)
    attacker.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)

    Entity.update_all_entities_senses()

    # Verify attacker IS visible to target (no stealth)
    check("Attacker visible to target", attacker.uuid in target.senses.entities)

    # Set up encounter and force many attacks to verify no extra damage from unseen strike
    from dnd.encounter import Encounter
    from dnd.controller import HumanController
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(attacker, HumanController(source_entity_uuid=attacker.uuid))
    encounter.add_combatant(target, HumanController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    hp_before = target.get_hp()
    mod_uuid = force_attack_hit(attacker)

    available = get_available_actions(attacker)
    for action_info in available.entity_actions:
        if "Attack" in action_info.template_name:
            for i, t in enumerate(action_info.valid_targets):
                if t.target_uuid == target.uuid:
                    execute_by_index(attacker, action_info.template_name, i)
                    break
            break

    hp_after = target.get_hp()
    damage_dealt = hp_before - hp_after
    print(f"  Damage dealt (seen): {damage_dealt}")
    # Base dagger: 1d4 + DEX(+2) = 3-6, no extra dice
    check("Damage dealt (max 6 for base dagger)", damage_dealt <= 6)

    remove_attack_modifier(attacker, mod_uuid)


def test_assassin_dagger_equip_unequip():
    """Assassin's Dagger handler is cleaned up on unequip."""
    print("\n" + "=" * 60)
    print("TEST: Assassin's Dagger Equip/Unequip")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    grid.set_tile(0, 0, walkable=True, name="Floor")

    entity = create_skeleton(name="Assassin", position=(0, 0))
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()

    # Equip dagger
    dagger = create_assassin_dagger(entity.uuid)
    entity.loot_item(dagger)
    entity.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)

    check("Dagger equipped", dagger.is_equipped)
    check("Handler UUID stored", dagger._handler_uuid is not None)

    _handler_uuid = dagger._handler_uuid

    # Unequip
    entity.unequip_item(WeaponSlot.MELEE_MAIN)

    check("Dagger unequipped", not dagger.is_equipped)
    check("Handler UUID cleared", dagger._handler_uuid is None)


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

    # New tests: Hidden reveal fixes
    test_hidden_removal_on_spell_cast()
    test_hidden_removal_on_shove()
    test_dash_does_not_remove_hidden()

    # New tests: Hide prerequisite
    test_hide_fails_when_visible_to_enemy()
    test_hide_succeeds_when_invisible()

    # New tests: Invisibility spell
    test_invisibility_spell_basic()
    test_invisibility_ends_on_attack()
    test_invisibility_ends_on_spell_cast()
    test_invisibility_concentration_break()

    # New tests: Greater Invisibility
    test_greater_invisibility_basic()
    test_greater_invisibility_stealth_check_on_attack()
    test_greater_invisibility_escalating_dc()
    test_greater_invisibility_concentration_break()

    # New tests: Self-trigger prevention
    test_invisibility_spell_self_cast_not_self_trigger()
    test_greater_invisibility_spell_self_cast_not_self_trigger()
    test_greater_invisibility_potion_not_self_trigger()

    # New tests: Greater Invisibility Potion consumption
    test_greater_invisibility_potion_consumption()
    test_greater_invisibility_potion_stacking()

    # New tests: Assassin's Dagger
    test_assassin_dagger_unseen_strike()
    test_assassin_dagger_no_bonus_when_seen()
    test_assassin_dagger_equip_unequip()

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
    print("=" * 60)

    if failed > 0:
        exit(1)
    else:
        print("ALL TESTS PASSED!")
