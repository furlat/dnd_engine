"""Direct item builders kept separate from the cold definition ledger."""

from types import MappingProxyType
from typing import Callable, Mapping
from uuid import UUID


from dnd.core.item_properties import AdditionalDamage, ArmorPenalties
from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.blocks.equipment import (
    Armor,
    BodyArmor,
    Boots,
    Cloak,
    Gauntlets,
    Helmet,
    Shield,
    Weapon,
)
from dnd.core.modifiers import (
    AdvantageModifier,
)
from dnd.core.events import (
    Range,
    RangeType,
)
from dnd.core.values import ModifiableValue
from dnd.content.items.authored_item_definitions import (
    ACOLYTE_GEAR_DEFINITIONS,
    CHEST_DEFINITIONS,
    AUTHORED_WEAPON_DEFINITIONS,
    AUTHORED_WEARABLE_DEFINITIONS,
    STATIC_BLOCKER_DEFINITIONS,
    AuthoredItemDefinition,
    StaticBlockerDefinition,
    WeaponDefinition,
    WearableDefinition,
)
from dnd.content.items.environment_item_builders import (
    LIQUID_BARREL_PROFILES,
    build_authored_door,
    build_arcane_device,
    build_arcane_machine_gun,
    build_campfire,
    build_cliff_face,
    build_directional_door,
    build_directional_wall,
    build_fireball_cannon,
    build_liquid_barrel,
    build_storage_chest,
    build_trap_lever,
    build_wall_torch,
)
from dnd.content.items.door_profiles import DOOR_PROFILES
from dnd.items.roster_carried_powers import PACK_POWERS, ARROW_PAYLOADS, build_powered_backpack, build_special_arrow
from dnd.content.items.roster_item_definitions import ROSTER_EMBER_DEFINITIONS, ROSTER_MAUL_DEFINITION, ROSTER_WEAPON_DEFINITIONS, ROSTER_GEAR_DEFINITIONS, ROSTER_CARRIED_DEFINITIONS, ROSTER_INVENTORY_DEFINITIONS
from dnd.content.items.window_definitions import WINDOW_DEFINITIONS
from dnd.content.items.window_builders import build_window_component
from dnd.content.items.trap_hardware_builders import TRAP_HARDWARE_PROFILES, build_trap_hardware
from dnd.content.items.ground_hardware_builders import GROUND_HARDWARE_PROFILES, build_ground_hardware
from dnd.content.items.world_prop_builders import WORLD_PROP_PROFILES, build_world_prop
from dnd.extensions.field_focus import build_field_kit
from dnd.items.consumables import (
    build_basic_poison_weapon_coat,
    build_concentration_fire_weapon_coat,
    build_fire_weapon_coat,
    build_greater_invisibility_potion,
    build_true_seeing_potion,
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
from dnd.core.modifiers import AdvantageStatus


ItemBuilder = Callable[[UUID, int], BaseItem]


def build_assassin_dagger(source_entity_uuid: UUID) -> Weapon:
    """Materialize the dagger through the shared conditional-property composer."""
    return _build_weapon(AUTHORED_WEAPON_DEFINITIONS["weapon.assassin_dagger"], source_entity_uuid)


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
    packets = definition.additional_damage
    if definition.extra_damage_die is not None and definition.extra_damage_type is not None:
        packets = (AdditionalDamage(definition.extra_damage_die,
            definition.extra_damage_dice_count, definition.extra_damage_type), *packets)
    weapon = Weapon(
        item_properties=definition.item_properties,
        source_entity_uuid=source_entity_uuid,
        item_id=definition.item_id,
        is_magical=definition.is_magical,
        intrinsic_owner_uuid=source_entity_uuid if definition.intrinsic else None,
        is_pickable=not definition.intrinsic,
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
        supports_arrow_payload=definition.supports_arrow_payload,
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
        extra_damage_dices=[packet.die for packet in packets],
        extra_damage_dices_numbers=[packet.count for packet in packets],
        extra_damage_bonus=[_armor_value(source_entity_uuid, "Extra Damage Bonus", 0) for _packet in packets],
        extra_damage_type=[packet.damage_type for packet in packets],
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
) -> Armor | Shield:
    properties = definition.item_properties
    if definition.stealth_disadvantage and not any(isinstance(value, ArmorPenalties) for value in properties):
        properties = (*properties, ArmorPenalties(True, definition.strength_requirement))
    common = {
        "item_properties": properties,
        "source_entity_uuid": source_entity_uuid,
        "item_id": definition.item_id,
        "is_magical": definition.is_magical,
        "intrinsic_owner_uuid": source_entity_uuid if definition.intrinsic else None,
        "is_pickable": not definition.intrinsic,
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
    item_type: type[Armor | BodyArmor | Boots | Cloak | Gauntlets | Helmet]
    if definition.wearable_kind == "boots":
        item_type = Boots
    elif definition.wearable_kind == "gauntlets":
        item_type = Gauntlets
    elif definition.wearable_kind == "helmet":
        item_type = Helmet
    elif definition.wearable_kind == "cloak":
        item_type = Cloak
    elif definition.wearable_kind == "accessory":
        item_type = Armor
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


def materialize_item_definition(
    definition: WeaponDefinition | WearableDefinition,
    source_entity_uuid: UUID,
    *, quantity: int = 1,
) -> Weapon | Armor | Shield:
    """Create a physical copy through the same native materializers as named content.

    Pure definition composition does not install another content registry. Named
    definitions remain deliberately dispatched by DIRECT_ITEM_BUILDERS.
    """
    if quantity != 1:
        raise ValueError(f"{definition.item_id} is not a stackable item")
    if isinstance(definition, WeaponDefinition):
        return _build_weapon(definition, source_entity_uuid)
    return _build_wearable(definition, source_entity_uuid)


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
        return materialize_item_definition(definition, source_entity_uuid, quantity=quantity)

    return build


def _wearable_definition_builder(definition: WearableDefinition) -> ItemBuilder:
    def build(source_entity_uuid: UUID, quantity: int = 1) -> BaseItem:
        if quantity != 1:
            raise ValueError(f"{definition.item_id} is not a stackable item")
        return materialize_item_definition(definition, source_entity_uuid, quantity=quantity)

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
            destruction_profile=definition.destruction_profile,
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


def _door_profile_builder(item_id: str) -> ItemBuilder:
    return _single_item_builder(item_id, lambda source: build_authored_door(
        item_id, source_entity_uuid=source))


def _chest_definition_builder(definition: AuthoredItemDefinition) -> ItemBuilder:
    def build(source_entity_uuid: UUID) -> BaseItem:
        chest = build_storage_chest(definition.name, item_id=definition.item_id,
            source_entity_uuid=source_entity_uuid, include_loot_all_action=True)
        chest.description = definition.description
        chest.tags = list(definition.tags)
        return chest
    return _single_item_builder(definition.item_id, build)


def _trap_hardware_builder(item_id: str) -> ItemBuilder:
    return _single_item_builder(item_id, lambda source: build_trap_hardware(
        item_id, source_entity_uuid=source))


def _ground_hardware_builder(item_id: str) -> ItemBuilder:
    return _single_item_builder(item_id, lambda source: build_ground_hardware(
        item_id, source_entity_uuid=source))


def _world_prop_builder(item_id: str) -> ItemBuilder:
    return _single_item_builder(item_id, lambda source: build_world_prop(
        item_id, source_entity_uuid=source))


def _liquid_barrel_builder(item_id: str) -> ItemBuilder:
    return _single_item_builder(item_id, lambda source: build_liquid_barrel(item_id, source))


def _build_wall_torch(_source_entity_uuid: UUID) -> BaseItem:
    return build_wall_torch()


def _build_trap_lever(_source_entity_uuid: UUID) -> BaseItem:
    return build_trap_lever()


def _build_storage_chest(_source_entity_uuid: UUID) -> BaseItem:
    return build_storage_chest("Chest", include_loot_all_action=False)


def _build_fireball_cannon(_source_entity_uuid: UUID) -> BaseItem:
    return build_fireball_cannon()


def _window_component_builder(family: str, *, insert: bool) -> ItemBuilder:
    definition = WINDOW_DEFINITIONS[family].insert if insert else WINDOW_DEFINITIONS[family].wall
    assert definition is not None
    return _single_item_builder(definition.item_id, lambda source: build_window_component(
        family, insert=insert, source_entity_uuid=source))


def _carried_power_builder(item_id: str, *, arrow: bool) -> ItemBuilder:
    def build(actor_uuid: UUID, quantity: int = 1) -> BaseItem:
        return build_special_arrow(item_id,actor_uuid,quantity) if arrow else build_powered_backpack(item_id,actor_uuid,quantity)
    return build


DIRECT_ITEM_BUILDERS: Mapping[str, ItemBuilder] = MappingProxyType({
    **{item_id:_carried_power_builder(item_id,arrow=False) for item_id in PACK_POWERS},
    **{item_id:_carried_power_builder(item_id,arrow=True) for item_id in ARROW_PAYLOADS},
    **{p.wall.item_id: _window_component_builder(family, insert=False) for family, p in WINDOW_DEFINITIONS.items()},
    **{p.insert.item_id: _window_component_builder(family, insert=True) for family, p in WINDOW_DEFINITIONS.items() if p.insert is not None},
    **{item_id: _chest_definition_builder(definition) for item_id, definition in CHEST_DEFINITIONS.items()},
    **{item_id: _door_profile_builder(item_id) for item_id in DOOR_PROFILES},
    **{item_id: _trap_hardware_builder(item_id) for item_id in TRAP_HARDWARE_PROFILES},
    **{item_id: _ground_hardware_builder(item_id) for item_id in GROUND_HARDWARE_PROFILES},
    **{item_id: _world_prop_builder(item_id) for item_id in WORLD_PROP_PROFILES},
    **{item_id: _liquid_barrel_builder(item_id) for item_id in LIQUID_BARREL_PROFILES},
    **{
        item_id: _fixed_definition_builder(definition)
        for item_id, definition in ACOLYTE_GEAR_DEFINITIONS.items()
    },
    **{
        item_id: _weapon_definition_builder(definition)
        for item_id, definition in AUTHORED_WEAPON_DEFINITIONS.items()
    },
    **{item_id: _weapon_definition_builder(definition)
       for item_id, definition in {**ROSTER_WEAPON_DEFINITIONS, **ROSTER_EMBER_DEFINITIONS}.items()},
    **{item_id: _weapon_definition_builder(definition)
       for item_id, definition in ROSTER_CARRIED_DEFINITIONS.items()},
    **{item_id: _wearable_definition_builder(definition)
       for item_id, definition in ROSTER_GEAR_DEFINITIONS.items()},
    **{item_id: _fixed_definition_builder(definition)
       for item_id, definition in ROSTER_INVENTORY_DEFINITIONS.items()},
    ROSTER_MAUL_DEFINITION.item_id: _weapon_definition_builder(ROSTER_MAUL_DEFINITION),
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
    "consumable.potion_true_seeing": _single_item_builder(
        "consumable.potion_true_seeing", build_true_seeing_potion,
    ),
    "consumable.weapon_coat.basic_poison": _single_item_builder(
        "consumable.weapon_coat.basic_poison", build_basic_poison_weapon_coat,
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
    "environment.spell_object.heroes_feast": _single_item_builder(
        "environment.spell_object.heroes_feast", build_heroes_feast_object,
    ),
    "gear.field_kit": _single_item_builder(
        "gear.field_kit", build_field_kit,
    ),
})

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
    "materialize_item_definition",
]
