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
from dnd.core.content.runtime import (
    RuntimeBehaviorKind,
    bind_runtime_behavior_child,
)
from dnd.core.events import (
    Damage,
    DamageRollResultEvent,
    Event,
    EventHandler,
    EventPhase,
    EventType,
    Range,
    RangeType,
    Trigger,
)
from dnd.core.values import ModifiableValue
from dnd.content.items.authored_item_definitions import (
    ACOLYTE_GEAR_DEFINITIONS,
    AUTHORED_WEAPON_DEFINITIONS,
    AUTHORED_WEARABLE_DEFINITIONS,
    STATIC_BLOCKER_DEFINITIONS,
    AuthoredItemDefinition,
    StaticBlockerDefinition,
    WeaponDefinition,
    WearableDefinition,
)
from dnd.content.items.environment_item_builders import (
    build_arcane_device,
    build_arcane_machine_gun,
    build_campfire,
    build_cliff_face,
    build_directional_door,
    build_directional_wall,
    build_fireball_cannon,
    build_oil_barrel,
    build_storage_chest,
    build_trap_lever,
    build_wall_torch,
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
from dnd.entity import Entity
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import EquipmentSlot, WeaponProperty
from dnd.core.modifiers import AdvantageStatus


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
            content_kind=RuntimeBehaviorKind.ITEM,
            source_entity_uuid=entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.DAMAGE_ROLL_RESULT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=entity_uuid,
            )],
            event_processor=_unseen_strike_processor,
        )
        bind_runtime_behavior_child(
            handler,
            provided_by_id=self.item_id,
            origin_root_id=self.item_id,
            runtime_owner_uuid=entity_uuid,
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
        item_id="weapon.assassin_dagger",
        name="Assassin's Dagger",
        description=(
            "A shadowy blade that deals 1d6 extra piercing damage when its "
            "target cannot see the wielder."
        ),
        visual_item_name="Dagger",
        visual_variant_id="10000004",
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
        item_id=definition.item_id,
        name=definition.name,
        description=definition.description,
        tags=list(definition.tags),
        stack_id=definition.stack_id,
        stack_count=stack_count,
        max_stack=definition.max_stack,
        visual_item_name=definition.visual_item_name,
        visual_variant_id=definition.visual_variant_id,
        equipped_visual_policy=definition.equipped_visual_policy,
    )


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
        item_id=definition.item_id,
        name=definition.name,
        description=definition.description,
        tags=list(definition.tags),
        visual_item_name=definition.visual_item_name,
        visual_variant_id=definition.visual_variant_id,
        equipped_visual_policy=definition.equipped_visual_policy,
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
        "item_id": definition.item_id,
        "name": definition.name,
        "description": definition.description,
        "tags": list(definition.tags),
        "visual_item_name": definition.visual_item_name,
        "visual_variant_id": definition.visual_variant_id,
        "equipped_visual_policy": definition.equipped_visual_policy,
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


def _fixed_definition_builder(
    definition: AuthoredItemDefinition,
) -> ItemBuilder:
    def build(source_entity_uuid: UUID, quantity: int = 1) -> BaseItem:
        return _build_fixed_item(definition, source_entity_uuid, quantity)

    return build


def _weapon_definition_builder(definition: WeaponDefinition) -> ItemBuilder:
    def build(source_entity_uuid: UUID, quantity: int = 1) -> BaseItem:
        if quantity != 1:
            raise ValueError(f"{definition.item_id} is not a stackable item")
        return _build_weapon(definition, source_entity_uuid)

    return build


def _wearable_definition_builder(definition: WearableDefinition) -> ItemBuilder:
    def build(source_entity_uuid: UUID, quantity: int = 1) -> BaseItem:
        if quantity != 1:
            raise ValueError(f"{definition.item_id} is not a stackable item")
        return _build_wearable(definition, source_entity_uuid)

    return build


def _static_blocker_definition_builder(
    definition: StaticBlockerDefinition,
) -> ItemBuilder:
    def build(source_entity_uuid: UUID, quantity: int = 1) -> BaseItem:
        if quantity != 1:
            raise ValueError(f"{definition.item_id} is not a stackable item")
        return WorldItem(
            source_entity_uuid=source_entity_uuid,
            item_id=definition.item_id,
            name=definition.name,
            description=definition.description,
            tags=list(definition.tags),
            visual_item_name=definition.visual_item_name,
            visual_variant_id=definition.visual_variant_id,
            equipped_visual_policy=definition.equipped_visual_policy,
            is_pickable=False,
            is_targetable=True,
            health=BaseItem.create_item_health(
                source_entity_uuid,
                definition.hit_points,
            ),
            blocks_movement=definition.blocks_movement,
            blocks_optics_field=definition.blocks_optics,
            blocks_propagation_field=definition.blocks_propagation,
            world_placement_spec=definition.placement_spec,
        )

    return build


def _single_item_builder(
    item_id: str,
    builder: Callable[[UUID], BaseItem],
) -> ItemBuilder:
    def build(source_entity_uuid: UUID, quantity: int = 1) -> BaseItem:
        if quantity != 1:
            raise ValueError(f"{item_id} is not a stackable item")
        return builder(source_entity_uuid)

    return build


def _build_healing_potion(
    source_entity_uuid: UUID,
    quantity: int = 1,
) -> BaseItem:
    return build_healing_potion(
        source_entity_uuid,
        stack_count=quantity,
    )


def _build_directional_wall(_source_entity_uuid: UUID) -> BaseItem:
    return build_directional_wall()


def _build_cliff_face(_source_entity_uuid: UUID) -> BaseItem:
    return build_cliff_face()


def _build_directional_door(_source_entity_uuid: UUID) -> BaseItem:
    return build_directional_door()


def _build_wall_torch(_source_entity_uuid: UUID) -> BaseItem:
    return build_wall_torch()


def _build_trap_lever(_source_entity_uuid: UUID) -> BaseItem:
    return build_trap_lever()


def _build_storage_chest(_source_entity_uuid: UUID) -> BaseItem:
    return build_storage_chest("Chest", include_loot_all_action=False)


def _build_fireball_cannon(_source_entity_uuid: UUID) -> BaseItem:
    return build_fireball_cannon()


DIRECT_ITEM_BUILDERS: Mapping[str, ItemBuilder] = MappingProxyType({
    **{
        item_id: _fixed_definition_builder(definition)
        for item_id, definition in ACOLYTE_GEAR_DEFINITIONS.items()
    },
    **{
        item_id: _weapon_definition_builder(definition)
        for item_id, definition in AUTHORED_WEAPON_DEFINITIONS.items()
    },
    **{
        item_id: _wearable_definition_builder(definition)
        for item_id, definition in AUTHORED_WEARABLE_DEFINITIONS.items()
    },
    **{
        item_id: _static_blocker_definition_builder(definition)
        for item_id, definition in STATIC_BLOCKER_DEFINITIONS.items()
    },
    "consumable.healing_potion": _build_healing_potion,
    "consumable.potion_haste": _single_item_builder(
        "consumable.potion_haste", build_haste_potion,
    ),
    "consumable.potion_greater_invisibility": _single_item_builder(
        "consumable.potion_greater_invisibility",
        build_greater_invisibility_potion,
    ),
    "consumable.weapon_coat.fire": _single_item_builder(
        "consumable.weapon_coat.fire", build_fire_weapon_coat,
    ),
    "consumable.weapon_coat.lightning": _single_item_builder(
        "consumable.weapon_coat.lightning", build_lightning_weapon_coat,
    ),
    "consumable.weapon_coat.concentration_fire": _single_item_builder(
        "consumable.weapon_coat.concentration_fire",
        build_concentration_fire_weapon_coat,
    ),
    "consumable.weapon_coat.timed_fire": _single_item_builder(
        "consumable.weapon_coat.timed_fire", build_timed_fire_weapon_coat,
    ),
    "consumable.acid_flask": _single_item_builder(
        "consumable.acid_flask", build_acid_flask,
    ),
    "spell_item.scroll_fireball": _single_item_builder(
        "spell_item.scroll_fireball", build_fireball_scroll,
    ),
    "spell_item.scroll_magic_missile": _single_item_builder(
        "spell_item.scroll_magic_missile", build_magic_missile_scroll,
    ),
    "spell_item.scroll_hold_person": _single_item_builder(
        "spell_item.scroll_hold_person", build_hold_person_scroll,
    ),
    "spell_item.scroll_mage_armor": _single_item_builder(
        "spell_item.scroll_mage_armor", build_mage_armor_scroll,
    ),
    "spell_item.scroll_spike_growth": _single_item_builder(
        "spell_item.scroll_spike_growth", build_spike_growth_scroll,
    ),
    "spell_item.scroll_invisibility": _single_item_builder(
        "spell_item.scroll_invisibility", build_invisibility_scroll,
    ),
    "spell_item.scroll_fire_bolt": _single_item_builder(
        "spell_item.scroll_fire_bolt", build_fire_bolt_scroll,
    ),
    "spell_item.wand_magic_missiles": _single_item_builder(
        "spell_item.wand_magic_missiles", build_wand_of_magic_missiles,
    ),
    "spell_item.wand_fire": _single_item_builder(
        "spell_item.wand_fire", build_wand_of_fire,
    ),
    "equipment.portable_torch": _single_item_builder(
        "equipment.portable_torch", build_torch,
    ),
    "environment.campfire": _single_item_builder(
        "environment.campfire", build_campfire,
    ),
    "environment.arcane_device": _single_item_builder(
        "environment.arcane_device", build_arcane_device,
    ),
    "environment.arcane_machine_gun": _single_item_builder(
        "environment.arcane_machine_gun", build_arcane_machine_gun,
    ),
    "environment.directional_wall": _single_item_builder(
        "environment.directional_wall", _build_directional_wall,
    ),
    "environment.cliff_face": _single_item_builder(
        "environment.cliff_face", _build_cliff_face,
    ),
    "environment.directional_door": _single_item_builder(
        "environment.directional_door", _build_directional_door,
    ),
    "environment.wall_torch": _single_item_builder(
        "environment.wall_torch", _build_wall_torch,
    ),
    "environment.trap_lever": _single_item_builder(
        "environment.trap_lever", _build_trap_lever,
    ),
    "environment.storage_chest": _single_item_builder(
        "environment.storage_chest", _build_storage_chest,
    ),
    "environment.fireball_cannon": _single_item_builder(
        "environment.fireball_cannon", _build_fireball_cannon,
    ),
    "environment.blocker.oil_barrel": _single_item_builder(
        "environment.blocker.oil_barrel", build_oil_barrel,
    ),
    "environment.spell_object.heroes_feast": _single_item_builder(
        "environment.spell_object.heroes_feast", build_heroes_feast_object,
    ),
    "gear.field_kit": _single_item_builder(
        "gear.field_kit", build_field_kit,
    ),
    "weapon.assassin_dagger": _single_item_builder(
        "weapon.assassin_dagger", build_assassin_dagger,
    ),
})

if len(DIRECT_ITEM_BUILDERS) != 147:
    raise ValueError("direct item builder table must contain exactly 147 IDs")


def build_authored_item(
    item_id: str,
    source_entity_uuid: UUID,
    *,
    quantity: int = 1,
) -> BaseItem:
    """Construct one migrated item through the sole direct builder table."""
    try:
        builder = DIRECT_ITEM_BUILDERS[item_id]
    except KeyError as exc:
        raise KeyError(f"unknown migrated item {item_id!r}") from exc
    return builder(source_entity_uuid, quantity)


__all__ = [
    "DIRECT_ITEM_BUILDERS",
    "ItemBuilder",
    "build_authored_item",
]
