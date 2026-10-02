"""Public gameplay regressions for intrinsic gear and item-owned enhancements."""
from uuid import uuid4

import pytest

from dnd.actions import Attack
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.controller import PassController
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.encounter import Encounter
from dnd.spells.transmutation import Disintegrate
from dnd.actions_functional import execute_use_action
from dnd.conditions import Blinded, Concentrating
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.core import dice as dice_module
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.consumables import build_timed_fire_weapon_coat
from dnd.runtime_reset import reset_engine_runtime
from dnd.core.modifiers import NumericalModifier


@pytest.fixture(autouse=True)
def fresh_runtime():
    reset_engine_runtime(grid_size=(8, 5))
    bootstrap_content_system()


def actor(game, name, position, *, slots=None):
    entity = Entity.create(source_entity_uuid=uuid4(), name=name,
                           config=EntityConfig(faction=name, action_economy=ActionEconomyConfig(spell_slots=slots or {})))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def equip(entity, item_id, slot):
    item = build_authored_item(item_id, entity.uuid)
    assert entity.loot_item(item)
    assert entity.equip_item(item.uuid, slot)
    return item


def coat(entity, coating, name="Coat Main Hand"):
    entity.action_economy.reset_all_costs()
    assert entity.loot_item(coating)
    result = execute_use_action(entity, coating.uuid, name)
    assert result is not None and not result.canceled


@pytest.mark.parametrize("item_id,slot", [
    ("weapon.creature.wolf_bite", WeaponSlot.MELEE_MAIN),
    ("armor.creature.wolf_natural", BodyPart.BODY),
])
def test_anatomy_cannot_be_removed_replaced_or_looted(item_id, slot):
    game = Game()
    wolf = Entity.create(source_entity_uuid=uuid4(), name="Wolf")
    anatomy = build_authored_item(item_id, wolf.uuid)
    wolf.install_initial_items(((anatomy, slot),))
    wolf.compose_entity()
    game.deploy_entity(wolf, (1, 1))
    other = actor(game, "Other", (2, 1))
    assert wolf.unequip_item(slot) is None
    assert wolf.equipment.get_item_by_slot(slot) is anatomy
    replacement = build_authored_item("weapon.dagger" if slot == WeaponSlot.MELEE_MAIN
                                     else "armor.leather", wolf.uuid)
    assert wolf.loot_item(replacement)
    assert not wolf.equip_item(replacement.uuid, slot)
    assert wolf.inventory.has_item(replacement.uuid)
    assert not other.loot_item(anatomy)
    assert anatomy.owner_uuid == wolf.uuid
    game.remove_entity(wolf.uuid)
    assert wolf.equipment.get_item_by_slot(slot) is anatomy
    game.deploy_entity(wolf, (1, 1))
    assert wolf.equipment.get_item_by_slot(slot) is anatomy


def test_unseen_dagger_bonus_does_not_leak_to_a_bow(monkeypatch):
    game = Game()
    attacker = actor(game, "Attacker", (1, 1))
    target = actor(game, "Target", (2, 1))
    equip(attacker, "weapon.assassin_dagger", WeaponSlot.MELEE_MAIN)
    equip(attacker, "weapon.shortbow", WeaponSlot.RANGED_MAIN)
    target.add_condition(Blinded(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    Entity.update_all_entities_senses()
    monkeypatch.setattr(dice_module.random, "randint", lambda low, high: high)
    result = Attack(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid,
                    weapon_slot=WeaponSlot.RANGED_MAIN).apply()
    assert result is not None and not result.canceled
    roll = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)[-1]
    assert len(roll.damage_packets) == 1


def test_coating_is_owned_by_weapon_and_survives_transfer_and_expiry(monkeypatch):
    game = Game()
    original = actor(game, "Original", (1, 1))
    recipient = actor(game, "Recipient", (2, 1))
    weapon = equip(original, "weapon.circus.flaming_scimitar", WeaponSlot.MELEE_MAIN)
    coat(original, build_timed_fire_weapon_coat(original.uuid, rounds=2))
    assert "Flaming Coat" in weapon.active_conditions
    assert len(weapon.get_extra_damages()) == 2
    encounter_uuid = uuid4()
    original.on_turn_start(encounter_uuid, round_number=1)
    assert original.unequip_item(WeaponSlot.MELEE_MAIN) is weapon
    assert original.drop_item(weapon.uuid) is weapon
    assert recipient.loot_item(weapon)
    assert recipient.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    recipient.on_turn_start(encounter_uuid, round_number=1)
    assert "Flaming Coat" in weapon.active_conditions
    recipient.on_turn_start(encounter_uuid, round_number=2)
    assert "Flaming Coat" not in weapon.active_conditions
    assert [d.damage_type for d in weapon.get_extra_damages()] == [DamageType.FIRE]
    target = actor(game, "Target", (3, 1))
    Entity.update_all_entities_senses()
    monkeypatch.setattr(dice_module.random, "randint", lambda low, high: high)
    result = Attack(source_entity_uuid=recipient.uuid, target_entity_uuid=target.uuid,
                    weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    assert result is not None and not result.canceled
    roll = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)[-1]
    assert len(roll.damage_packets) == 2  # weapon damage plus surviving authored fire


def test_magical_crown_identity_and_modifier_cleanup():
    game = Game()
    wearer = actor(game, "Wearer", (1, 1))
    crown = build_authored_item("apparel.spellblade_crown", wearer.uuid)
    ordinary = build_authored_item("apparel.crown", wearer.uuid)
    assert crown.is_magical
    assert not ordinary.is_magical
    base = wearer.ability_scores.charisma.ability_score.normalized_score
    assert wearer.loot_item(crown)
    for _ in range(2):
        assert wearer.equip_item(crown.uuid, BodyPart.HEAD)
        assert wearer.ability_scores.charisma.ability_score.normalized_score == base + 3
        assert wearer.unequip_item(BodyPart.HEAD) is crown
        assert wearer.ability_scores.charisma.ability_score.normalized_score == base


@pytest.mark.parametrize("slot", [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF])
@pytest.mark.parametrize("unseen", [False, True])
def test_dagger_bonus_applies_only_to_its_own_eligible_hit(monkeypatch, slot, unseen):
    game = Game()
    attacker = actor(game, "Attacker", (1, 1))
    target = actor(game, "Target", (2, 1))
    if slot == WeaponSlot.MELEE_OFF:
        equip(attacker, "weapon.shortsword", WeaponSlot.MELEE_MAIN)
    dagger = equip(attacker, "weapon.assassin_dagger", slot)
    assert attacker.unequip_item(slot) is dagger
    assert attacker.equip_item(dagger.uuid, slot)
    if unseen:
        target.add_condition(Blinded(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    Entity.update_all_entities_senses()
    monkeypatch.setattr(dice_module.random, "randint", lambda low, high: high)
    result = Attack(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid,
                    weapon_slot=slot).apply()
    assert result is not None and not result.canceled
    roll = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)[-1]
    assert len(roll.damage_packets) == (2 if unseen else 1)


def test_ordinary_gear_remains_removable_and_lootable():
    game = Game()
    first = actor(game, "First", (1, 1))
    second = actor(game, "Second", (2, 1))
    for identity, slot in [("weapon.dagger", WeaponSlot.MELEE_MAIN), ("armor.leather", BodyPart.BODY)]:
        item = equip(first, identity, slot)
        assert first.unequip_item(slot) is item
        assert first.drop_item(item.uuid) is item
        assert second.loot_item(item)
        assert second.equip_item(item.uuid, slot)


def test_separate_weapons_keep_independent_coatings():
    game = Game()
    owner = actor(game, "Owner", (1, 1))
    main = equip(owner, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    off = equip(owner, "weapon.shortsword", WeaponSlot.MELEE_OFF)
    coat(owner, build_authored_item("consumable.weapon_coat.fire", owner.uuid))
    coat(owner, build_authored_item("consumable.weapon_coat.fire", owner.uuid), "Coat Off Hand")
    assert len(main.get_extra_damages()) == len(off.get_extra_damages()) == 1
    assert main.remove_condition("Flaming Coat")
    assert not main.get_extra_damages()
    assert len(off.get_extra_damages()) == 1


def test_same_weapon_reapplication_replaces_only_the_previous_coat():
    game = Game()
    owner = actor(game, "Owner", (1, 1))
    weapon = equip(owner, "weapon.circus.flaming_scimitar", WeaponSlot.MELEE_MAIN)
    coat(owner, build_timed_fire_weapon_coat(owner.uuid, rounds=1))
    coat(owner, build_authored_item("consumable.weapon_coat.fire", owner.uuid))
    assert len(weapon.get_extra_damages()) == 2
    owner.on_turn_start(uuid4(), round_number=1)
    assert len(weapon.get_extra_damages()) == 2  # permanent replacement didn't inherit timed expiry
    assert weapon.remove_condition("Flaming Coat")
    assert len(weapon.get_extra_damages()) == 1  # authored flame survives


def test_transferred_concentration_coat_keeps_original_sustainer():
    game = Game()
    original = actor(game, "Original", (1, 1))
    recipient = actor(game, "Recipient", (2, 1))
    weapon = equip(original, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    coat(original, build_authored_item("consumable.weapon_coat.concentration_fire", original.uuid))
    assert "Concentrating" in original.active_conditions
    assert original.unequip_item(WeaponSlot.MELEE_MAIN) is weapon
    assert original.drop_item(weapon.uuid) is weapon
    assert recipient.loot_item(weapon)
    assert recipient.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    assert "Concentrating" not in recipient.active_conditions
    assert len(weapon.get_extra_damages()) == 1
    assert original.remove_condition("Concentrating")
    assert not weapon.active_conditions
    assert not weapon.get_extra_damages()


def test_weapon_retirement_cleans_coat_and_concentration():
    game = Game()
    original = actor(game, "Original", (1, 1))
    weapon = equip(original, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    coat(original, build_authored_item("consumable.weapon_coat.concentration_fire", original.uuid))
    weapon.retire()
    assert not weapon.active_conditions
    assert not weapon.get_extra_damages()
    assert "Concentrating" not in original.active_conditions


def test_drop_and_transfer_do_not_consume_the_application_round():
    game = Game()
    original = actor(game, "Original", (1, 1))
    recipient = actor(game, "Recipient", (2, 1))
    weapon = equip(original, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    interval = uuid4()
    original.on_turn_start(interval, round_number=1)
    coat(original, build_timed_fire_weapon_coat(original.uuid, rounds=1))
    assert original.unequip_item(WeaponSlot.MELEE_MAIN) is weapon
    assert original.drop_item(weapon.uuid) is weapon
    assert recipient.loot_item(weapon)
    assert recipient.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    recipient.on_turn_start(interval, round_number=1)
    assert len(weapon.get_extra_damages()) == 1
    recipient.on_turn_start(interval, round_number=2)
    assert not weapon.get_extra_damages()


def test_vetoed_coat_replacement_leaves_no_provisional_damage():
    game = Game()
    owner = actor(game, "Owner", (1, 1))
    weapon = equip(owner, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    coat(owner, build_authored_item("consumable.weapon_coat.fire", owner.uuid))
    previous = weapon.active_conditions["Flaming Coat"]

    def veto(event, source):
        if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == previous.uuid:
            return event.cancel(status_message="Keep original coating")
        return None

    handler = EventHandler(name="Keep original coating", source_entity_uuid=owner.uuid,
                           event_processor=veto, trigger_conditions=[Trigger(
                               event_type=EventType.CONDITION_REMOVAL,
                               event_phase=EventPhase.DECLARATION)])
    weapon.add_event_handler(handler)
    replacement = build_timed_fire_weapon_coat(owner.uuid, rounds=1)
    assert owner.loot_item(replacement)
    owner.action_economy.reset_all_costs()
    result = execute_use_action(owner, replacement.uuid, "Coat Main Hand")
    assert result is not None and result.canceled
    assert weapon.active_conditions["Flaming Coat"].uuid == previous.uuid
    assert len(weapon.get_extra_damages()) == 1
    handler.enabled = False
    assert weapon.remove_condition("Flaming Coat")
    assert not weapon.get_extra_damages()


def test_floor_round_boundary_preserves_coat_duration_through_pickup():
    game = Game()
    first = actor(game, "First", (1, 1))
    second = actor(game, "Second", (2, 1))
    encounter = Encounter(source_entity_uuid=uuid4())
    for participant in (first, second):
        encounter.add_combatant(participant, PassController(source_entity_uuid=participant.uuid))
    encounter.start_encounter()
    encounter.start_turn()
    original = encounter.get_current_entity()
    recipient = second if original is first else first
    assert original is not None
    weapon = equip(original, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    coat(original, build_timed_fire_weapon_coat(original.uuid, rounds=1))
    assert original.unequip_item(WeaponSlot.MELEE_MAIN) is weapon
    assert original.drop_item(weapon.uuid) is weapon
    encounter.next_turn()  # second turn in application round
    encounter.next_turn()  # floor tick at end of application round
    assert encounter.round_number == 2
    assert len(weapon.get_extra_damages()) == 1
    assert recipient.loot_item(weapon)
    assert recipient.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    encounter.next_turn()  # recipient's round-2 tick
    assert not weapon.get_extra_damages()


@pytest.mark.parametrize("identity,protected", [
    ("apparel.spellblade_crown", True), ("apparel.crown", False),
])
def test_disintegrate_observes_explicit_wearable_magic(identity, protected):
    game = Game()
    caster = actor(game, "Caster", (1, 1), slots={6: 1})
    item = build_authored_item(identity, caster.uuid)
    item.place_on_grid((2, 1))
    Entity.update_all_entities_senses()
    result = Disintegrate(source_entity_uuid=caster.uuid, target_entity_uuid=item.uuid).apply()
    assert result is not None
    assert result.canceled is protected
    assert (BaseBlock.get(item.uuid) is item) is protected


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("phase", [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT])
def test_rejected_concentration_preserves_previous_physical_coat(existing, phase):
    game = Game()
    owner = actor(game, "Owner", (1, 1))
    weapon = equip(owner, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    if existing:
        coat(owner, build_authored_item("consumable.weapon_coat.fire", owner.uuid))
    previous = weapon.active_conditions.get("Flaming Coat")

    def veto(event, source):
        if isinstance(event, ConditionApplicationEvent) and event.condition.name == "Concentrating":
            return event.cancel(status_message="Concentration unavailable")
        if isinstance(event, ConditionRemovalEvent):
            return event.cancel(status_message="Removal unavailable")
        return None

    owner.add_event_handler(EventHandler(name="Reject concentration", source_entity_uuid=owner.uuid,
        event_processor=veto, trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION,
                                                          event_phase=phase)]))
    # No prior coat: prove rollback bypasses vetoable removal of provisional state.
    if not existing:
        weapon.add_event_handler(EventHandler(name="Reject removal", source_entity_uuid=owner.uuid,
            event_processor=veto, trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,
                                                              event_phase=EventPhase.DECLARATION)]))
    replacement = build_authored_item("consumable.weapon_coat.concentration_fire", owner.uuid)
    assert owner.loot_item(replacement)
    owner.action_economy.reset_all_costs()
    result = execute_use_action(owner, replacement.uuid, "Coat Main Hand")
    assert result is not None and result.canceled
    assert weapon.active_conditions.get("Flaming Coat") is previous
    assert len(weapon.get_extra_damages()) == int(existing)
    assert "Concentrating" not in owner.active_conditions
    assert replacement.charges == 0  # native execution already committed the item cost


def test_rejected_existing_concentration_removal_preserves_coated_weapon():
    game = Game()
    owner = actor(game, "Owner", (1, 1))
    weapon = equip(owner, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    coat(owner, build_authored_item("consumable.weapon_coat.concentration_fire", owner.uuid))
    previous = weapon.active_conditions["Flaming Coat"]
    concentration = owner.active_conditions["Concentrating"]

    def veto(event, source):
        if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == concentration.uuid:
            return event.cancel(status_message="Keep concentration")
        return None

    owner.add_event_handler(EventHandler(name="Keep concentration", source_entity_uuid=owner.uuid,
        event_processor=veto, trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,
                                                          event_phase=EventPhase.DECLARATION)]))
    replacement = build_authored_item("consumable.weapon_coat.concentration_fire", owner.uuid)
    assert owner.loot_item(replacement)
    owner.action_economy.reset_all_costs()
    result = execute_use_action(owner, replacement.uuid, "Coat Main Hand")
    assert result is not None and result.canceled
    assert weapon.active_conditions["Flaming Coat"] is previous
    assert owner.active_conditions["Concentrating"] is concentration
    assert len(weapon.get_extra_damages()) == 1
    assert replacement.charges == 0  # native execution already committed the item cost


@pytest.mark.parametrize("slots", [1, 2])
def test_concentration_coat_replacement_removes_each_old_condition_once(slots):
    game = Game()
    owner = actor(game, "Owner", (1, 1))
    weapon = equip(owner, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    if slots == 2:
        owner.max_concentration_slots.self_static.add_value_modifier(NumericalModifier(
            name="Second concentration slot", value=1,
            source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid))
        owner.add_condition(Concentrating(source_entity_uuid=owner.uuid,
                                        target_entity_uuid=owner.uuid, spell_name="Other effect"))
        child = Blinded(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid)
        owner.add_condition(child)
        owner.active_conditions["Concentrating"].add_linked_condition(owner.uuid, child.uuid)
    coat(owner, build_authored_item("consumable.weapon_coat.concentration_fire", owner.uuid))
    previous = weapon.active_conditions["Flaming Coat"]
    concentration = owner.active_conditions["Concentrating"]
    coat(owner, build_authored_item("consumable.weapon_coat.concentration_fire", owner.uuid))
    assert len(weapon.get_extra_damages()) == 1
    assert weapon.active_conditions["Flaming Coat"] is not previous
    for old in (previous, concentration):
        removals = [event for event in EventQueue.get_events_by_type(EventType.CONDITION_REMOVAL)
                    if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == old.uuid]
        assert sum(event.phase == EventPhase.EFFECT and not event.canceled for event in removals) == 1
        assert sum(event.phase == EventPhase.COMPLETION and not event.canceled for event in removals) == 1
    if slots == 2:
        assert "Blinded" in owner.active_conditions
        assert len(owner.active_conditions["Concentrating"].concentration_slots) == 2


def test_coat_reapplication_preserves_a_pending_unused_concentration_slot():
    game = Game()
    owner = actor(game, "Owner", (1, 1))
    owner.max_concentration_slots.self_static.add_value_modifier(NumericalModifier(
        name="Second slot", value=1, source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid))
    weapon = equip(owner, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    for _ in range(2):
        coat(owner, build_authored_item("consumable.weapon_coat.concentration_fire", owner.uuid))
        assert len(owner.active_conditions["Concentrating"].concentration_slots) == 1
    assert owner.remove_condition("Concentrating")
    assert not weapon.get_extra_damages()


def test_rejected_multislot_concentration_replacement_preserves_all_children():
    game = Game()
    owner = actor(game, "Owner", (1, 1))
    owner.max_concentration_slots.self_static.add_value_modifier(NumericalModifier(
        name="Second slot", value=1, source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid))
    weapon = equip(owner, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    coat(owner, build_authored_item("consumable.weapon_coat.concentration_fire", owner.uuid))
    owner.add_condition(Concentrating(source_entity_uuid=owner.uuid,
                                    target_entity_uuid=owner.uuid, spell_name="Other effect"))
    child = Blinded(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid)
    owner.add_condition(child)
    concentration = owner.active_conditions["Concentrating"]
    concentration.add_linked_condition(owner.uuid, child.uuid)
    previous = weapon.active_conditions["Flaming Coat"]

    def veto(event, source):
        if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == concentration.uuid:
            return event.cancel(status_message="Keep both spells")
        return None

    owner.add_event_handler(EventHandler(name="Keep both spells", source_entity_uuid=owner.uuid,
        event_processor=veto, trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,
                                                          event_phase=EventPhase.DECLARATION)]))
    replacement = build_authored_item("consumable.weapon_coat.concentration_fire", owner.uuid)
    assert owner.loot_item(replacement)
    owner.action_economy.reset_all_costs()
    result = execute_use_action(owner, replacement.uuid, "Coat Main Hand")
    assert result is not None and result.canceled
    assert weapon.active_conditions["Flaming Coat"] is previous
    assert owner.active_conditions["Blinded"] is child
    assert owner.active_conditions["Concentrating"] is concentration
    assert len(concentration.concentration_slots) == 2
    assert len(weapon.get_extra_damages()) == 1


@pytest.mark.parametrize("phase", [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT])
def test_rejected_concentration_reapplication_preserves_original_coat(phase):
    game = Game()
    owner = actor(game, "Owner", (1, 1))
    weapon = equip(owner, "weapon.dagger", WeaponSlot.MELEE_MAIN)
    coat(owner, build_authored_item("consumable.weapon_coat.concentration_fire", owner.uuid))
    previous = weapon.active_conditions["Flaming Coat"]
    concentration = owner.active_conditions["Concentrating"]

    def veto(event, source):
        if isinstance(event, ConditionApplicationEvent) and event.condition.name == "Concentrating":
            return event.cancel(status_message="New concentration rejected")
        return None

    owner.add_event_handler(EventHandler(name="Reject replacement", source_entity_uuid=owner.uuid,
        event_processor=veto, trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION,
                                                          event_phase=phase)]))
    replacement = build_authored_item("consumable.weapon_coat.concentration_fire", owner.uuid)
    assert owner.loot_item(replacement)
    owner.action_economy.reset_all_costs()
    result = execute_use_action(owner, replacement.uuid, "Coat Main Hand")
    assert result is not None and result.canceled
    assert weapon.active_conditions["Flaming Coat"] is previous
    assert owner.active_conditions["Concentrating"] is concentration
    assert len(weapon.get_extra_damages()) == 1
    assert len(concentration.concentration_slots) == 1
