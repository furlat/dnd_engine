"""Direct item builders kept separate from the cold definition ledger."""

from types import MappingProxyType
from typing import Callable, Mapping, Optional
from uuid import UUID

from pydantic import PrivateAttr

from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.blocks.equipment import (
    BodyArmor,
    Boots,
    Gauntlets,
    Helmet,
    Shield,
    Weapon,
)
from dnd.core.modifiers import (
    AdvantageModifier,
    ContextualNumericalModifier,
    NumericalModifier,
)
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventType,
    Trigger,
)
from dnd.core.events.resolution_events import (
    Damage,
    DamageRollResultEvent,
    Range,
    RangeType,
)
from dnd.core.values import ModifiableValue
from dnd.content.items.authored_item_definitions import (
    ACOLYTE_GEAR_DEFINITIONS,
    AUTHORED_WEAPON_DEFINITIONS,
    AUTHORED_WEARABLE_DEFINITIONS,
    STATIC_BLOCKER_DEFINITIONS,
    AuthoredItemDefinition,
    WeaponDefinition,
    WearableDefinition,
)
from dnd.content.items.environment_item_builders import (
    build_arcane_device,
    build_arcane_machine_gun,
    build_campfire,
)
from dnd.extensions.field_focus import build_field_kit
from dnd.items.consumables import (
    build_concentration_fire_weapon_coat,
    build_fire_weapon_coat,
    build_greater_invisibility_potion,
    build_haste_potion,
    build_healing_potion,
    build_lightning_weapon_coat,
    build_timed_fire_weapon_coat,
)
from dnd.items.spell_items import (
    build_acid_flask,
    build_fire_bolt_scroll,
    build_fireball_scroll,
    build_hold_person_scroll,
    build_invisibility_scroll,
    build_mage_armor_scroll,
    build_magic_missile_scroll,
    build_spike_growth_scroll,
    build_wand_of_fire,
    build_wand_of_magic_missiles,
)
from dnd.spells.conjuration import build_heroes_feast_object
from dnd.items.torches import build_torch
from dnd.entities.entity import Entity
from dnd.types.damage import DamageType
from dnd.types.equipment import EquipmentSlot, WeaponProperty
from dnd.types.rolls import AdvantageStatus


ItemBuilder = Callable[[UUID, int], BaseItem]


def _unseen_strike_processor(
    event: Event,
    source_entity_uuid: UUID,
) -> Optional[Event]:
    """Append Assassin's Dagger damage when the target cannot see its user."""
    if not isinstance(event, DamageRollResultEvent):
        return None
    if event.source_entity_uuid != source_entity_uuid:
        return None
    target = (
        Entity.get(event.target_entity_uuid)
        if event.target_entity_uuid is not None
        else None
    )
    contact = target.senses.entities.get(source_entity_uuid) if target is not None else None
    if target is None or (contact is not None and contact.visual):
        return None
    damage = Damage(
        name="Unseen Strike",
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=event.target_entity_uuid,
        damage_dice=6,
        dice_numbers=1,
        damage_bonus=ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=event.target_entity_uuid,
            base_value=0,
            value_name="Unseen Strike Damage Bonus",
        ),
        damage_type=DamageType.PIERCING,
    )
    return event.append_damage_roll(
        damage,
        damage.get_dice(event.attack_outcome).roll,
        "Unseen Strike",
        "1d6 piercing (unseen attacker)",
    )


class _DirectAssassinDagger(Weapon):
    """Dagger that owns its equip-scoped unseen-strike handler."""

    _handler_uuid: Optional[UUID] = PrivateAttr(default=None)

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        _ = slot
        entity = Entity.get(entity_uuid)
        if entity is None:
            return
        behavior_id = "handler.item.assassin_dagger.unseen_strike"
        handler = EventHandler(
            name="Unseen Strike",
            source_entity_uuid=entity_uuid,
            semantic_key=behavior_id,
            behavior_id=behavior_id,
            provided_by_id=self.get_semantic_key(),
            origin_root_id=self.get_semantic_key(),
            trigger_conditions=[Trigger(
                event_type=EventType.DAMAGE_ROLL_RESULT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=entity_uuid,
            )],
            event_processor=_unseen_strike_processor,
        )
        entity.add_event_handler(handler)
        self._handler_uuid = handler.uuid

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        _ = slot
        if self._handler_uuid is None:
            return
        entity = Entity.get(entity_uuid)
        handler = EventHandler.get(self._handler_uuid)
        if entity is not None and isinstance(handler, EventHandler):
            entity.remove_event_handler(handler)
        self._handler_uuid = None


def build_assassin_dagger(source_entity_uuid: UUID) -> Weapon:
    """Construct the hook-bearing Assassin's Dagger directly."""
    return _DirectAssassinDagger(
        source_entity_uuid=source_entity_uuid,
        semantic_key="weapon.assassin_dagger",
        name="Assassin's Dagger",
        description=(
            "A shadowy blade that deals 1d6 extra piercing damage when its "
            "target cannot see the wielder."
        ),
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            base_value=0,
            value_name="Attack Bonus",
        ),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[],
    )


def _heavy_armor_strength_penalty(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None,
) -> Optional[NumericalModifier]:
    _ = target_entity_uuid, context
    entity = Entity.get(source_entity_uuid)
    if entity is None:
        return None
    body_armor = entity.equipment.body_armor
    if body_armor is None or body_armor.strength_requirement is None:
        return None
    if (
        entity.ability_scores.strength.ability_score.score
        >= body_armor.strength_requirement
    ):
        return None
    return NumericalModifier(
        name=f"{body_armor.name} Strength Requirement",
        value=-10,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=source_entity_uuid,
    )


class _DirectStealthDisadvantageBodyArmor(BodyArmor):
    """Body armor retaining its equip hooks without authored presentation."""

    _stealth_modifier_uuid: Optional[UUID] = PrivateAttr(default=None)
    _movement_modifier_uuid: Optional[UUID] = PrivateAttr(default=None)

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        _ = slot
        entity = Entity.get(entity_uuid)
        if entity is None:
            return
        self._stealth_modifier_uuid = (
            entity.skill_set.stealth.skill_bonus.self_static
            .add_advantage_modifier(AdvantageModifier(
                name=f"{self.name} Stealth Disadvantage",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=entity_uuid,
            ))
        )
        if self.strength_requirement is not None:
            self._movement_modifier_uuid = (
                entity.action_economy.movement.self_contextual
                .add_value_modifier(ContextualNumericalModifier(
                    name=f"{self.name} Strength Requirement",
                    source_entity_uuid=entity_uuid,
                    target_entity_uuid=entity_uuid,
                    callable=_heavy_armor_strength_penalty,
                ))
            )

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        _ = slot
        entity = Entity.get(entity_uuid)
        if entity is not None and self._stealth_modifier_uuid is not None:
            entity.skill_set.stealth.skill_bonus.self_static.remove_modifier(
                self._stealth_modifier_uuid,
            )
        if entity is not None and self._movement_modifier_uuid is not None:
            entity.action_economy.movement.self_contextual.remove_value_modifier(
                self._movement_modifier_uuid,
            )
        self._stealth_modifier_uuid = None
        self._movement_modifier_uuid = None


class _DirectSpellbladeCrown(Helmet):
    """Premade crown's actual reversible Charisma mechanic."""

    _charisma_modifier_uuid: Optional[UUID] = PrivateAttr(default=None)

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        _ = slot
        entity = Entity.get(entity_uuid)
        if entity is None or self._charisma_modifier_uuid is not None:
            return
        self._charisma_modifier_uuid = (
            entity.ability_scores.charisma.ability_score.self_static
            .add_value_modifier(NumericalModifier(
                name="Spellblade Crown Charisma",
                value=3,
                source_entity_uuid=self.uuid,
                target_entity_uuid=entity_uuid,
            ))
        )

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        _ = slot
        entity = Entity.get(entity_uuid)
        if entity is not None and self._charisma_modifier_uuid is not None:
            entity.ability_scores.charisma.ability_score.self_static.remove_modifier(
                self._charisma_modifier_uuid,
            )
        self._charisma_modifier_uuid = None


class _DirectArcaneStaff(Weapon):
    """Arcane staff retaining only its renderer-independent equip mechanic."""

    _spell_attack_modifier_uuid: Optional[UUID] = PrivateAttr(default=None)

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        _ = slot
        entity = Entity.get(entity_uuid)
        if entity is None or self._spell_attack_modifier_uuid is not None:
            return
        modifier = NumericalModifier(
            name="Arcane Staff",
            value=1,
            source_entity_uuid=self.uuid,
            target_entity_uuid=entity_uuid,
        )
        self._spell_attack_modifier_uuid = (
            entity.spellcasting.spell_attack_bonus.self_static
            .add_value_modifier(modifier)
        )

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        _ = slot
        entity = Entity.get(entity_uuid)
        if entity is not None and self._spell_attack_modifier_uuid is not None:
            entity.spellcasting.spell_attack_bonus.self_static.remove_modifier(
                self._spell_attack_modifier_uuid,
            )
        self._spell_attack_modifier_uuid = None


def _build_fixed_item(
    definition: AuthoredItemDefinition,
    source_entity_uuid: UUID,
    stack_count: int,
) -> BaseItem:
    if not 1 <= stack_count <= definition.max_stack:
        raise ValueError(
            f"{definition.item_id} stack_count must be between 1 and "
            f"{definition.max_stack}",
        )
    return BaseItem(
        source_entity_uuid=source_entity_uuid,
        semantic_key=definition.item_id,
        name=definition.name,
        description=definition.description,
        tags=list(definition.tags),
        stack_id=definition.stack_id,
        stack_count=stack_count,
        max_stack=definition.max_stack,
    )


def _builder(item_id: str) -> ItemBuilder:
    definition = ACOLYTE_GEAR_DEFINITIONS[item_id]

    def build(source_entity_uuid: UUID, stack_count: int = 1) -> BaseItem:
        return _build_fixed_item(definition, source_entity_uuid, stack_count)

    return build


build_holy_symbol = _builder("gear.holy_symbol")
build_prayer_book = _builder("gear.prayer_book")
build_incense = _builder("gear.incense")
build_vestments = _builder("gear.vestments")
build_common_clothes = _builder("gear.common_clothes")

DIRECT_ACOLYTE_GEAR_BUILDERS: Mapping[str, ItemBuilder] = MappingProxyType({
    "gear.holy_symbol": build_holy_symbol,
    "gear.prayer_book": build_prayer_book,
    "gear.incense": build_incense,
    "gear.vestments": build_vestments,
    "gear.common_clothes": build_common_clothes,
})


def build_acolyte_gear(
    item_id: str,
    source_entity_uuid: UUID,
    *,
    stack_count: int = 1,
) -> BaseItem:
    """Build one Acolyte gear item directly from its domain identity."""
    try:
        builder = DIRECT_ACOLYTE_GEAR_BUILDERS[item_id]
    except KeyError as exc:
        raise KeyError(f"unknown Acolyte gear item {item_id!r}") from exc
    return builder(source_entity_uuid, stack_count)


def _build_weapon(
    definition: WeaponDefinition,
    source_entity_uuid: UUID,
) -> Weapon:
    weapon_type = (
        _DirectArcaneStaff
        if definition.item_id == "weapon.arcane_staff"
        else Weapon
    )
    weapon = weapon_type(
        source_entity_uuid=source_entity_uuid,
        semantic_key=definition.item_id,
        name=definition.name,
        description=definition.description,
        tags=list(definition.tags),
        damage_dice=definition.damage_die,
        dice_numbers=definition.damage_dice_count,
        damage_type=definition.damage_type,
        properties=list(definition.properties),
        range=Range(
            type=(
                RangeType.RANGE
                if definition.range_kind == "range"
                else RangeType.REACH
            ),
            normal=definition.normal_range_feet,
            long=definition.long_range_feet,
        ),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            base_value=definition.attack_bonus,
            value_name="Attack Bonus",
        ),
        damage_bonus=ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            base_value=definition.damage_bonus,
            value_name="Damage Bonus",
        ),
        extra_damage_dices=(
            [definition.extra_damage_die]
            if definition.extra_damage_die is not None
            else []
        ),
        extra_damage_dices_numbers=(
            [definition.extra_damage_dice_count]
            if definition.extra_damage_die is not None
            else []
        ),
        extra_damage_bonus=(
            [_armor_value(source_entity_uuid, "Extra Damage Bonus", 0)]
            if definition.extra_damage_die is not None
            else []
        ),
        extra_damage_type=(
            [definition.extra_damage_type]
            if definition.extra_damage_type is not None
            else []
        ),
    )
    if definition.attack_disadvantage:
        weapon.attack_bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                source_entity_uuid=source_entity_uuid,
                name="Rusty Blade",
                value=AdvantageStatus.DISADVANTAGE,
            ),
        )
    return weapon


def _armor_value(source_entity_uuid: UUID, name: str, value: int) -> ModifiableValue:
    return ModifiableValue.create(
        source_entity_uuid=source_entity_uuid,
        base_value=value,
        value_name=name,
    )


def _build_wearable(
    definition: WearableDefinition,
    source_entity_uuid: UUID,
) -> BaseItem:
    common = {
        "source_entity_uuid": source_entity_uuid,
        "semantic_key": definition.item_id,
        "name": definition.name,
        "description": definition.description,
        "tags": list(definition.tags),
    }
    if definition.wearable_kind == "shield":
        return Shield(
            **common,
            ac_bonus=_armor_value(
                source_entity_uuid,
                "Shield AC Bonus",
                definition.shield_armor_class_bonus,
            ),
        )
    item_type: type[BodyArmor | Boots | Gauntlets | Helmet]
    if definition.wearable_kind == "boots":
        item_type = Boots
    elif definition.wearable_kind == "gauntlets":
        item_type = Gauntlets
    elif definition.wearable_kind == "helmet":
        item_type = Helmet
    elif definition.wearable_kind == "spellblade_crown":
        item_type = _DirectSpellbladeCrown
    elif definition.stealth_disadvantage:
        item_type = _DirectStealthDisadvantageBodyArmor
    else:
        item_type = BodyArmor
    return item_type(
        **common,
        type=definition.armor_type,
        body_part=definition.body_part,
        ac=_armor_value(
            source_entity_uuid,
            "Armor Class",
            definition.armor_class,
        ),
        max_dex_bonus=_armor_value(
            source_entity_uuid,
            "Max Dex Bonus",
            definition.maximum_dexterity_bonus,
        ),
        strength_requirement=definition.strength_requirement,
        stealth_disadvantage=definition.stealth_disadvantage,
    )


def build_authored_item(
    item_id: str,
    source_entity_uuid: UUID,
    *,
    quantity: int = 1,
    parameters: Optional[Mapping[str, object]] = None,
) -> BaseItem:
    """Construct one migrated item by its direct domain identity."""
    parameter_values = dict(parameters or {})
    parameter_types_by_item: dict[str, dict[str, type[object]]] = {
        "consumable.healing_potion": {"heal_amount": int},
        "spell_item.scroll_fireball": {"cast_level": int},
        "spell_item.scroll_hold_person": {"cast_level": int},
        "spell_item.scroll_magic_missile": {"cast_level": int},
        "spell_item.scroll_spike_growth": {"cast_level": int},
        "spell_item.scroll_invisibility": {"cast_level": int},
        "spell_item.wand_fire": {"charges": int},
        "spell_item.wand_magic_missiles": {"charges": int},
        "consumable.weapon_coat.timed_fire": {"rounds": int},
        "environment.arcane_device": {"heal_amount": int},
        "gear.field_kit": {"charges": int},
        "spell_item.scroll_fire_bolt": {"caster_level": int},
        "spell_item.scroll_mage_armor": {"cast_level": int},
    }
    parameter_types = parameter_types_by_item.get(item_id, {})
    allowed_parameters = set(parameter_types)
    unexpected_parameters = set(parameter_values) - allowed_parameters
    if unexpected_parameters:
        raise ValueError(
            f"{item_id} does not accept parameters: "
            + ", ".join(sorted(unexpected_parameters)),
        )
    for parameter_name, value in parameter_values.items():
        expected_type = parameter_types[parameter_name]
        if type(value) is not expected_type:
            raise TypeError(
                f"{item_id} parameter {parameter_name!r} must be "
                f"{expected_type.__name__}",
            )
    if item_id in ACOLYTE_GEAR_DEFINITIONS:
        return build_acolyte_gear(
            item_id,
            source_entity_uuid,
            stack_count=quantity,
        )
    if quantity != 1 and item_id != "consumable.healing_potion":
        raise ValueError(f"{item_id} is not an authored stackable item")
    weapon = AUTHORED_WEAPON_DEFINITIONS.get(item_id)
    if weapon is not None:
        return _build_weapon(weapon, source_entity_uuid)
    wearable = AUTHORED_WEARABLE_DEFINITIONS.get(item_id)
    if wearable is not None:
        return _build_wearable(wearable, source_entity_uuid)
    blocker = STATIC_BLOCKER_DEFINITIONS.get(item_id)
    if blocker is not None:
        return WorldItem(
            source_entity_uuid=source_entity_uuid,
            semantic_key=blocker.item_id,
            name=blocker.name,
            description=blocker.description,
            tags=list(blocker.tags),
            is_pickable=False,
            is_targetable=True,
            health=BaseItem.create_item_health(
                source_entity_uuid,
                blocker.hit_points,
            ),
            blocks_movement=blocker.blocks_movement,
            blocks_optics_field=blocker.blocks_optics,
            blocks_propagation_field=blocker.blocks_propagation,
            world_placement_spec=blocker.placement_spec,
        )
    if item_id == "consumable.healing_potion":
        return build_healing_potion(
            source_entity_uuid,
            stack_count=quantity,
            heal_amount=int(parameter_values.get("heal_amount", 7)),
        )
    if item_id == "consumable.potion_haste":
        return build_haste_potion(source_entity_uuid)
    if item_id == "consumable.potion_greater_invisibility":
        return build_greater_invisibility_potion(source_entity_uuid)
    if item_id == "consumable.weapon_coat.fire":
        return build_fire_weapon_coat(source_entity_uuid)
    if item_id == "consumable.weapon_coat.lightning":
        return build_lightning_weapon_coat(source_entity_uuid)
    if item_id == "consumable.weapon_coat.concentration_fire":
        return build_concentration_fire_weapon_coat(source_entity_uuid)
    if item_id == "consumable.weapon_coat.timed_fire":
        return build_timed_fire_weapon_coat(
            source_entity_uuid,
            rounds=int(parameter_values.get("rounds", 3)),
        )
    if item_id == "consumable.acid_flask":
        return build_acid_flask(source_entity_uuid)
    if item_id == "spell_item.scroll_fireball":
        return build_fireball_scroll(
            source_entity_uuid,
            cast_level=int(parameter_values.get("cast_level", 3)),
        )
    if item_id == "spell_item.scroll_magic_missile":
        return build_magic_missile_scroll(
            source_entity_uuid,
            cast_level=int(parameter_values.get("cast_level", 1)),
        )
    if item_id == "spell_item.scroll_hold_person":
        return build_hold_person_scroll(
            source_entity_uuid,
            cast_level=int(parameter_values.get("cast_level", 2)),
        )
    if item_id == "spell_item.scroll_spike_growth":
        return build_spike_growth_scroll(
            source_entity_uuid,
            cast_level=int(parameter_values.get("cast_level", 2)),
        )
    if item_id == "spell_item.scroll_invisibility":
        return build_invisibility_scroll(
            source_entity_uuid,
            cast_level=int(parameter_values.get("cast_level", 2)),
        )
    if item_id == "spell_item.scroll_fire_bolt":
        return build_fire_bolt_scroll(
            source_entity_uuid,
            caster_level=int(parameter_values.get("caster_level", 5)),
        )
    if item_id == "spell_item.scroll_mage_armor":
        return build_mage_armor_scroll(
            source_entity_uuid,
            cast_level=int(parameter_values.get("cast_level", 1)),
        )
    if item_id == "spell_item.wand_magic_missiles":
        return build_wand_of_magic_missiles(
            source_entity_uuid,
            charges=int(parameter_values.get("charges", 3)),
        )
    if item_id == "spell_item.wand_fire":
        return build_wand_of_fire(
            source_entity_uuid,
            charges=int(parameter_values.get("charges", 7)),
        )
    if item_id == "equipment.portable_torch":
        return build_torch(source_entity_uuid)
    if item_id == "environment.campfire":
        return build_campfire(source_entity_uuid)
    if item_id == "environment.arcane_device":
        return build_arcane_device(
            source_entity_uuid,
            heal_amount=int(parameter_values.get("heal_amount", 5)),
        )
    if item_id == "environment.arcane_machine_gun":
        return build_arcane_machine_gun(source_entity_uuid)
    if item_id == "environment.spell_object.heroes_feast":
        return build_heroes_feast_object(source_entity_uuid)
    if item_id == "gear.field_kit":
        return build_field_kit(
            source_entity_uuid,
            charges=int(parameter_values.get("charges", 1)),
        )
    if item_id == "weapon.assassin_dagger":
        return build_assassin_dagger(source_entity_uuid)
    raise KeyError(f"unknown migrated item {item_id!r}")


__all__ = [
    "DIRECT_ACOLYTE_GEAR_BUILDERS",
    "ItemBuilder",
    "build_acolyte_gear",
    "build_authored_item",
    "build_common_clothes",
    "build_holy_symbol",
    "build_incense",
    "build_prayer_book",
    "build_vestments",
]
