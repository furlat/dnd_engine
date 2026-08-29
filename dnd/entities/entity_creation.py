"""The single low-level Entity constructor and composition transaction."""

from dataclasses import dataclass
from typing import Callable, Optional
from uuid import UUID

from dnd.blocks.abilities import AbilityScores
from dnd.blocks.action_economy import ActionEconomy
from dnd.blocks.appearance import Appearance
from dnd.blocks.creature_proficiencies import CreatureProficiencies
from dnd.blocks.equipment import Equipment
from dnd.blocks.health import Health, HealthConfig, HitDiceConfig
from dnd.blocks.inventory import Inventory
from dnd.blocks.base_item import BaseItem, EquippableItem
from dnd.blocks.saving_throws import SavingThrowSet
from dnd.blocks.sensory import Senses
from dnd.blocks.skills import SkillSet
from dnd.blocks.spellcasting import SpellcastingBlock
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import ModifiableValue
from dnd.core.events.entity_events import EntityCreatedEvent
from dnd.core.events.events_registry import EventPhase, EventQueue
from dnd.entities.creature_transforms import (
    EntityTransform,
    EntityTransformReceipt,
    apply_entity_transforms,
    rollback_entity_transforms,
)
from dnd.entities.entity import Entity, EntityConfig
from dnd.entities.entity_progression import (
    AppliedLevelReceipt,
    ResolvedLevelStep,
    _install_level,
    _uninstall_last_level,
    entity_terminal_state_fields,
)
from dnd.types.progression import AppliedOriginState
from dnd.types.damage import DamageType, ResistanceStatus
from dnd.types.equipment import (
    ArmorType,
    BodyPart,
    EquipmentSlot,
    RingSlot,
    WeaponProperty,
    WeaponSlot,
)


_CONCRETE_EQUIPMENT_SLOTS: tuple[EquipmentSlot, ...] = (
    *tuple(WeaponSlot),
    BodyPart.HEAD,
    BodyPart.BODY,
    BodyPart.HANDS,
    BodyPart.LEGS,
    BodyPart.FEET,
    BodyPart.AMULET,
    RingSlot.LEFT,
    RingSlot.RIGHT,
    BodyPart.CLOAK,
)


def _created_event(entity: Entity) -> EntityCreatedEvent:
    """Capture the complete committed initial state carried by entity birth."""
    terminal_state = entity_terminal_state_fields(entity)
    inventory_items = tuple(entity.inventory.items.values())
    equipped_by_slot = tuple(
        (slot, item)
        for slot in _CONCRETE_EQUIPMENT_SLOTS
        if (item := entity.equipment.get_item_by_slot(slot)) is not None
    )
    items_by_uuid = {
        item.uuid: item
        for item in (
            *inventory_items,
            *(item for _, item in equipped_by_slot),
        )
    }
    proficiencies = entity.creature_proficiencies
    weapon_proficiencies = []
    for category in (WeaponProperty.SIMPLE, WeaponProperty.MARTIAL):
        if proficiencies.is_weapon_proficient((category,)):
            weapon_proficiencies.append(f"weapon.{category.value.lower()}")
    weapon_proficiencies.extend(sorted(
        set(proficiencies.base_weapon_ids)
        | {
            key
            for key, sources in proficiencies.specific_weapon_sources.items()
            if sources.sources
        },
    ))
    armor_proficiencies = tuple(
        armor_type.value
        for armor_type in (ArmorType.LIGHT, ArmorType.MEDIUM, ArmorType.HEAVY)
        if proficiencies.is_armor_proficient(armor_type)
    )
    languages = tuple(sorted(
        set(proficiencies.base_languages)
        | {
            key
            for key, sources in proficiencies.language_sources.items()
            if sources.sources
        },
    ))
    tools = tuple(sorted(
        set(proficiencies.base_tools)
        | {
            key
            for key, sources in proficiencies.tool_sources.items()
            if sources.sources
        },
    ))
    damage_affinities = tuple(
        (damage_type, status)
        for damage_type in DamageType
        if (
            status := entity.health.get_resistance(damage_type)
        ) is not ResistanceStatus.NONE
    )
    return EntityCreatedEvent(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        use_register=False,
        phase=EventPhase.COMPLETION,
        entity_uuid=entity.uuid,
        entity_kind_id=entity.entity_kind_id,
        entity_name=entity.name,
        entity_description=entity.description,
        creature_type=entity.creature_type,
        size=entity.size,
        structural_base_size=entity.structural_base_size,
        weight=entity.weight,
        faction=entity.faction,
        species=entity.species,
        species_variant=entity.species_variant,
        background=entity.background,
        applied_origin_state=entity.applied_origin_state,
        applied_class_levels=tuple(entity.applied_class_levels),
        ability_scores=tuple(
            (ability.name, ability.ability_score.score)
            for ability in entity.ability_scores.abilities_list
        ),
        skill_proficiencies=tuple(
            skill.name for skill in entity.skill_set.proficiencies
        ),
        skill_expertise=tuple(
            skill.name for skill in entity.skill_set.expertise
        ),
        saving_throw_proficiencies=tuple(
            saving_throw.name for saving_throw in entity.saving_throws.proficiencies
        ),
        proficiency_bonus=entity.proficiency_bonus.normalized_score,
        initiative=entity.initiative.normalized_score,
        armor_class=entity.ac_bonus().normalized_score,
        life_state=entity.health.life_state,
        current_hit_points=max(0, entity.get_hp()),
        maximum_hit_points=max(0, entity.get_max_hp()),
        temporary_hit_points=max(
            0,
            entity.health.temporary_hit_points.normalized_score,
        ),
        damage_taken=entity.health.damage_taken,
        hit_dice=tuple(
            (
                hit_die.hit_dice_value.normalized_score,
                hit_die.hit_dice_count.normalized_score,
                hit_die.spent_hit_dice,
                hit_die.mode,
                hit_die.ignore_first_level,
            )
            for hit_die in entity.health.hit_dices
        ),
        damage_affinities=damage_affinities,
        walking_speed_feet=entity.action_economy.current_speed(),
        swimming_speed_feet=entity.swimming_speed,
        has_ordinary_sight=entity.has_ordinary_sight,
        sense_modes=tuple(entity.senses.get_sense_modes()),
        requires_breathing=entity.requires_breathing,
        uses_death_saves=entity.uses_death_saves,
        death_save_successes=entity.death_save_successes,
        death_save_failures=entity.death_save_failures,
        origin_capabilities=tuple(sorted(
            (
                capability
                for capability, sources in entity.origin_capability_sources.items()
                if sources
            ),
            key=lambda capability: capability.value,
        )),
        body_semantics=terminal_state["body_semantics"],
        feature_ids=tuple(sorted(entity.feature_sources)),
        weapon_proficiencies=tuple(weapon_proficiencies),
        armor_proficiencies=armor_proficiencies,
        shield_proficient=proficiencies.is_shield_proficient(),
        languages=languages,
        tools=tools,
        action_ids=tuple(sorted(
            action.get_semantic_key() for action in entity.registered_actions
        )),
        handler_ids=terminal_state["handler_ids"],
        condition_ids=tuple(sorted(
            condition.get_semantic_key()
            for condition in entity.active_conditions.values()
        )),
        condition_immunities=tuple(sorted({
            condition_name
            for condition_name, _source_name in entity.condition_immunities
        })),
        attacks_per_action=entity.action_economy.resolve_attacks_per_attack_action(),
        resources=tuple(
            (
                name,
                resource.current,
                resource.maximum,
                resource.recharge_type.value,
            )
            for name, resource in sorted(entity.action_economy.resources.items())
        ),
        resource_recoveries=terminal_state["resource_recoveries"],
        attack_multiplicity=terminal_state["attack_multiplicity"],
        spell_sources=terminal_state["spell_sources"],
        known_spell_ids=terminal_state["known_spell_ids"],
        reaction_spell_ids=terminal_state["reaction_spell_ids"],
        prepared_spell_ids=terminal_state["prepared_spell_ids"],
        feature_toggle_ids=terminal_state["feature_toggle_ids"],
        spell_slots=tuple(
            (
                rank,
                entity.action_economy.spell_slot_value(rank).normalized_score,
            )
            for rank in range(1, 10)
        ),
        armor_class_formulas=terminal_state["armor_class_formulas"],
        items=tuple(
            items_by_uuid[item_uuid].to_item_state()
            for item_uuid in sorted(items_by_uuid, key=str)
        ),
        inventory_item_uuids=tuple(sorted(
            entity.inventory.items,
            key=str,
        )),
        equipment=tuple(
            (slot.value, item.uuid)
            for slot, item in equipped_by_slot
        ),
    )


@dataclass(frozen=True, slots=True)
class EntityCompositionReceipt:
    """Exact live inverse state retained after initial composition."""

    entity_uuid: UUID
    transforms: tuple[EntityTransformReceipt, ...]
    levels: tuple[AppliedLevelReceipt, ...]


def initial_item_transform(
    *,
    transform_id: str,
    item: BaseItem,
    equipment_slot: Optional[EquipmentSlot] = None,
) -> EntityTransform:
    """Build the reversible starting-inventory operation for one item."""
    if not transform_id:
        raise ValueError("starting item transform_id cannot be empty")
    if equipment_slot is not None and not isinstance(item, EquippableItem):
        raise ValueError("only an equippable item may name an equipment slot")

    def apply(entity: Entity) -> Callable[[], None]:
        if entity.creation_committed or entity.is_deployed:
            raise ValueError(
                "starting items require an unpublished, undeployed entity",
            )
        undo_inventory = entity.inventory._install_initial_item(item)
        undo_equipment: Optional[Callable[[], None]] = None
        try:
            if equipment_slot is not None:
                assert isinstance(item, EquippableItem)
                undo_equipment = entity.equipment._install_initial_item(
                    entity.inventory,
                    item,
                    equipment_slot,
                )
        except Exception:
            undo_inventory()
            raise

        def undo() -> None:
            if undo_equipment is not None:
                undo_equipment()
            undo_inventory()

        return undo

    return EntityTransform(transform_id, apply)


def create_entity(
    source_entity_uuid: UUID,
    *,
    entity_kind_id: str,
    name: str = "Entity",
    description: Optional[str] = None,
    config: Optional[EntityConfig] = None,
) -> Entity:
    """Construct the universal block aggregate used by every creature kind."""
    if config is None:
        config = EntityConfig(
            health=HealthConfig(hit_dices=[HitDiceConfig()]),
            proficiency_bonus=2,
        )

    ability_scores = AbilityScores.create(
        source_entity_uuid=source_entity_uuid,
        config=config.ability_scores,
    )
    skill_set = SkillSet.create(
        source_entity_uuid=source_entity_uuid,
        config=config.skill_set,
    )
    saving_throws = SavingThrowSet.create(
        source_entity_uuid=source_entity_uuid,
        config=config.saving_throws,
    )
    health = Health.create(source_entity_uuid=source_entity_uuid, config=config.health)
    equipment = Equipment.create(
        source_entity_uuid=source_entity_uuid,
        config=config.equipment,
    )
    creature_proficiencies = CreatureProficiencies.create(
        source_entity_uuid=source_entity_uuid,
        config=config.creature_proficiencies,
    )
    senses = Senses.create(
        source_entity_uuid=source_entity_uuid,
        position=config.position,
    )
    appearance = Appearance.create(
        source_entity_uuid=source_entity_uuid,
        config=config.appearance,
    )
    action_economy = ActionEconomy.create(
        source_entity_uuid=source_entity_uuid,
        config=config.action_economy,
    )
    proficiency_bonus = ModifiableValue.create(
        source_entity_uuid=source_entity_uuid,
        base_value=config.proficiency_bonus,
    )
    for modifier_name, modifier_value in config.proficiency_bonus_modifiers:
        proficiency_bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=source_entity_uuid,
                name=modifier_name,
                value=modifier_value,
            ),
        )

    initiative = ModifiableValue.create(
        source_entity_uuid=source_entity_uuid,
        base_value=0,
        value_name="initiative",
    )
    for modifier_name, modifier_value in config.initiative_modifiers:
        initiative.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=source_entity_uuid,
                name=modifier_name,
                value=modifier_value,
            ),
        )

    spellcasting = SpellcastingBlock.create(
        source_entity_uuid=source_entity_uuid,
        config=config.spellcasting,
    )
    inventory = Inventory(source_entity_uuid=source_entity_uuid)

    return Entity(
        uuid=source_entity_uuid,
        source_entity_uuid=source_entity_uuid,
        entity_kind_id=entity_kind_id,
        name=name,
        description=description,
        ability_scores=ability_scores,
        skill_set=skill_set,
        saving_throws=saving_throws,
        health=health,
        equipment=equipment,
        creature_proficiencies=creature_proficiencies,
        senses=senses,
        inventory=inventory,
        appearance=appearance,
        action_economy=action_economy,
        proficiency_bonus=proficiency_bonus,
        initiative=initiative,
        spellcasting=spellcasting,
        position=config.position,
        sprite_name=config.sprite_name,
        faction=config.faction,
        weight=config.weight,
        creature_type=config.creature_type,
        size=config.size,
        structural_base_size=config.size,
        has_ordinary_sight=config.has_ordinary_sight,
        requires_breathing=config.requires_breathing,
        swimming_speed=config.swimming_speed,
        uses_death_saves=config.uses_death_saves,
        death_save_successes=config.death_save_successes,
        death_save_failures=config.death_save_failures,
    )


def compose_entity(
    entity: Entity,
    *,
    transforms: tuple[EntityTransform, ...] = (),
    applied_origin_state: Optional[AppliedOriginState] = None,
    initial_levels: tuple[ResolvedLevelStep, ...] = (),
    validate: Optional[Callable[[Entity], None]] = None,
) -> EntityCompositionReceipt:
    """Apply one ordered, reversible initial composition to an Entity."""
    if entity.creation_committed:
        raise ValueError("entity creation is already committed")
    if entity.is_deployed:
        raise ValueError("initial composition requires an undeployed entity")
    if entity.applied_class_levels or entity._progression_receipts:
        raise ValueError("initial composition requires an empty level ledger")
    if entity.applied_origin_state is not None:
        raise ValueError("initial composition requires empty origin state")

    transform_receipts: tuple[EntityTransformReceipt, ...] = ()
    level_receipts: list[AppliedLevelReceipt] = []
    try:
        transform_receipts = apply_entity_transforms(entity, transforms)
        entity.applied_origin_state = applied_origin_state
        for step in initial_levels:
            level_receipts.append(_install_level(entity, step))
        if validate is not None:
            validate(entity)
        entity.creation_committed = True
        EventQueue.publish_inert_terminal_fact(_created_event(entity))
    except Exception:
        while entity.applied_class_levels:
            _uninstall_last_level(entity)
        entity.applied_origin_state = None
        rollback_entity_transforms(transform_receipts)
        entity.creation_committed = False
        entity.discard_unpublished_runtime()
        raise

    return EntityCompositionReceipt(
        entity_uuid=entity.uuid,
        transforms=transform_receipts,
        levels=tuple(level_receipts),
    )


__all__ = [
    "EntityCompositionReceipt",
    "compose_entity",
    "create_entity",
    "initial_item_transform",
]
