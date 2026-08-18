"""Resolve authored character origins into ordinary entity transforms."""

from functools import partial
from typing import Any
from uuid import uuid5

from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.core.aoe import Cone, Line
from dnd.core.base_actions import Cost, block_action_resource_cost_evaluator
from dnd.content.characters.character_definitions import (
    BACKGROUND_DEFINITIONS,
    SPECIES_DEFINITIONS,
    get_species_variant_definition,
)
from dnd.content.characters.dragonborn_definitions import (
    DRAGONBORN_ANCESTRY_DEFINITIONS,
)
from dnd.core.modifiers import (
    AdvantageModifier,
    ContextualAdvantageModifier,
    NumericalModifier,
    ResistanceModifier,
)
from dnd.core.events.events_registry import (
    EventHandler,
    EventPhase,
    EventType,
    Trigger,
)
from dnd.entities.creature_transforms import EntityTransform
from dnd.entities.entity import Entity
from dnd.origins.half_orc import (
    HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
    half_orc_relentless_endurance_processor,
)
from dnd.origins.dragonborn import (
    DRAGONBORN_BREATH_RESOURCE,
    DragonbornBreathWeapon,
)
from dnd.origins.halfling import halfling_lucky_processor
from dnd.spells.infernal import (
    Thaumaturgy,
    create_hellish_rebuke_reaction_handler,
)
from dnd.spells.spell_builders import SPELL_ACTION_TYPES_BY_ID
from dnd.types.abilities import AbilityName, SkillName
from dnd.types.creatures import Background, Species, SpeciesVariant
from dnd.types.damage import DamageType, ResistanceStatus
from dnd.types.dragonborn import (
    DragonbornAncestry,
    DragonbornBreathGeometry,
)
from dnd.types.proficiency import ProficiencyMode
from dnd.types.progression import AppliedOriginState
from dnd.types.rolls import AdvantageStatus
from dnd.types.saving_throws import (
    SAVING_THROW_CONTEXT_KEY,
    SavingThrowContext,
    SavingThrowEffectTag,
)
from dnd.types.senses import SenseMode, SensesType


_SUPPORTED_FEATURE_IDS = frozenset({
    "sense.darkvision.60",
    "species.dragonborn.ancestry_resistance",
    "species.dragonborn.breath_weapon",
    "species.dwarf.combat_training",
    "species.dwarf.poison_resilience",
    "species.elf.fey_ancestry",
    "species.gnome.cunning",
    "species.half_orc.relentless_endurance",
    "species.half_orc.savage_attacks",
    "species.halfling.brave",
    "species.halfling.lucky",
    "species_variant.high_elf.weapon_training",
    "species_variant.high_elf.wizard_cantrip",
    "species_variant.rock_gnome.tinkers_tools",
    "species.tiefling.fire_resistance",
    "species.tiefling.infernal_legacy",
})
_SEPARATELY_COMPOSED_FEATURE_IDS = frozenset({
    "background.acolyte.starting_holdings",
    "species_variant.hill_dwarf.dwarven_toughness",
})

_DRAGONBORN_DAMAGE_TYPES = {
    "black": DamageType.ACID,
    "blue": DamageType.LIGHTNING,
    "brass": DamageType.FIRE,
    "bronze": DamageType.LIGHTNING,
    "copper": DamageType.ACID,
    "gold": DamageType.FIRE,
    "green": DamageType.POISON,
    "red": DamageType.FIRE,
    "silver": DamageType.COLD,
    "white": DamageType.COLD,
}

_DWARF_WEAPON_IDS = (
    "weapon.battleaxe",
    "weapon.handaxe",
    "weapon.light_hammer",
    "weapon.warhammer",
)

_HIGH_ELF_WEAPON_IDS = (
    "weapon.longbow",
    "weapon.longsword",
    "weapon.shortbow",
    "weapon.shortsword",
)


def _source_id(entity: Entity, transform_id: str):
    return uuid5(entity.uuid, f"entity-origin:{transform_id}")


def _validate_origin_state(
    *,
    species: Species,
    species_variant: SpeciesVariant | None,
    background: Background,
    state: AppliedOriginState,
) -> None:
    species_definition = SPECIES_DEFINITIONS[species]
    variant_definition = get_species_variant_definition(species_variant)
    background_definition = BACKGROUND_DEFINITIONS[background]
    if (
        variant_definition is not None
        and variant_definition.parent_species is not species
    ):
        raise ValueError("species variant does not belong to species")

    ability_order = tuple(AbilityName)
    if tuple(name for name, _ in state.base_ability_scores) != ability_order:
        raise ValueError("base ability scores must contain all six abilities in order")
    if any(not 1 <= score <= 20 for _, score in state.base_ability_scores):
        raise ValueError("base ability scores must be between 1 and 20")
    if tuple(sorted(
        state.flexible_ability_bonuses,
        key=lambda row: ability_order.index(row[0]),
    )) != state.flexible_ability_bonuses:
        raise ValueError("flexible ability bonuses must use ability order")
    if sorted(amount for _, amount in state.flexible_ability_bonuses) != [1, 2]:
        raise ValueError("character creation requires one +2 and one +1 bonus")

    requirements = (
        *species_definition.choices,
        *(variant_definition.choices if variant_definition is not None else ()),
        *background_definition.choices,
    )
    selections = {choice.choice_id: choice for choice in state.choices}
    expected_ids = tuple(requirement.choice_id for requirement in requirements)
    if tuple(choice.choice_id for choice in state.choices) != expected_ids:
        raise ValueError("origin choices must exactly follow authored choice order")
    for requirement in requirements:
        selection = selections[requirement.choice_id]
        if not (
            requirement.minimum_selections
            <= len(selection.values)
            <= requirement.maximum_selections
        ):
            raise ValueError(
                f"origin choice {requirement.choice_id} has wrong cardinality",
            )
        unsupported = set(selection.values) - set(requirement.allowed_values)
        if unsupported:
            values = ", ".join(sorted(unsupported))
            raise ValueError(
                f"origin choice {requirement.choice_id} contains: {values}",
            )


def _identity_transform(
    species: Species,
    species_variant: SpeciesVariant | None,
    background: Background,
) -> EntityTransform:
    def apply(entity: Entity):
        entity.set_origin_identity(
            species=species,
            species_variant=species_variant,
            background=background,
        )
        return entity.clear_origin_identity

    return EntityTransform("origin.identity", apply)


def _ability_scores_transform(state: AppliedOriginState) -> EntityTransform:
    def apply(entity: Entity):
        previous_base_values: list[tuple[NumericalModifier, int]] = []
        modifiers: list[tuple[object, NumericalModifier]] = []
        bonuses = dict(state.flexible_ability_bonuses)
        try:
            for ability_name, score in state.base_ability_scores:
                value = entity.ability_scores.get_ability(
                    ability_name,
                ).ability_score
                base_modifier = value.get_base_modifier()
                if base_modifier is None:
                    raise RuntimeError(
                        f"{ability_name.value} ability has no base modifier",
                    )
                previous_base_values.append(
                    (base_modifier, base_modifier.value),
                )
                base_modifier.value = score
                bonus = bonuses.get(ability_name)
                if bonus is None:
                    continue
                modifier = NumericalModifier(
                    uuid=_source_id(entity, f"ability.{ability_name.value}"),
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    name=f"Character creation {ability_name.value} bonus",
                    value=bonus,
                )
                value.self_static.add_value_modifier(modifier)
                modifiers.append((value, modifier))
        except Exception:
            for value, modifier in reversed(modifiers):
                value.remove_modifier(modifier.uuid)
                modifier.remove_from_register()
            for base_modifier, previous in reversed(previous_base_values):
                base_modifier.value = previous
            raise

        def undo() -> None:
            for value, modifier in reversed(modifiers):
                value.remove_modifier(modifier.uuid)
                modifier.remove_from_register()
            for base_modifier, previous in reversed(previous_base_values):
                base_modifier.value = previous

        return undo

    return EntityTransform("origin.ability_scores", apply)


def _physical_transform(species: Species) -> EntityTransform:
    definition = SPECIES_DEFINITIONS[species]

    def apply(entity: Entity):
        size_source = _source_id(entity, "physical.size")
        speed_modifier = None
        entity.add_structural_size_source(size_source, definition.size)
        try:
            base_speed = entity.action_economy.get_base_value("movement")
            speed_delta = definition.walking_speed_feet - base_speed
            if speed_delta:
                speed_modifier = NumericalModifier(
                    uuid=_source_id(entity, "physical.walking_speed"),
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    name=f"{definition.display_name} walking speed",
                    value=speed_delta,
                )
                entity.action_economy.movement.self_static.add_value_modifier(
                    speed_modifier,
                )
        except Exception:
            entity.remove_structural_size_source(size_source)
            raise

        def undo() -> None:
            if speed_modifier is not None:
                entity.action_economy.movement.remove_modifier(
                    speed_modifier.uuid,
                )
                speed_modifier.remove_from_register()
            entity.remove_structural_size_source(size_source)

        return undo

    return EntityTransform("origin.physical", apply)


def _language_transform(language_ids: tuple[str, ...]) -> EntityTransform:
    def apply(entity: Entity):
        source_ids = []
        try:
            for language_id in language_ids:
                source_id = _source_id(entity, f"language.{language_id}")
                entity.creature_proficiencies.add_language_source(
                    source_id,
                    language_id,
                )
                source_ids.append(source_id)
        except Exception:
            for source_id in reversed(source_ids):
                entity.creature_proficiencies.remove_source(source_id)
            raise

        def undo() -> None:
            for source_id in reversed(source_ids):
                entity.creature_proficiencies.remove_source(source_id)

        return undo

    return EntityTransform("origin.languages", apply)


def _skill_transform(skills: tuple[SkillName, ...]) -> EntityTransform:
    def apply(entity: Entity):
        sources = []
        try:
            for skill_name in skills:
                source_id = _source_id(entity, f"skill.{skill_name.value}")
                entity.skill_set.get_skill(skill_name).add_proficiency_source(
                    source_id,
                    ProficiencyMode.FULL,
                )
                sources.append((skill_name, source_id))
        except Exception:
            for skill_name, source_id in reversed(sources):
                entity.skill_set.get_skill(skill_name).remove_proficiency_source(
                    source_id,
                )
            raise

        def undo() -> None:
            for skill_name, source_id in reversed(sources):
                entity.skill_set.get_skill(skill_name).remove_proficiency_source(
                    source_id,
                )

        return undo

    return EntityTransform("origin.skills", apply)


def _tool_transform(tool_ids: tuple[str, ...]) -> EntityTransform:
    """Grant exact tool identities with independently removable sources."""
    def apply(entity: Entity):
        source_ids = []
        try:
            for tool_id in tool_ids:
                source_id = _source_id(entity, f"tool.{tool_id}")
                entity.creature_proficiencies.add_tool_source(
                    source_id,
                    tool_id,
                )
                source_ids.append(source_id)
        except Exception:
            for source_id in reversed(source_ids):
                entity.creature_proficiencies.remove_source(source_id)
            raise

        def undo() -> None:
            for source_id in reversed(source_ids):
                entity.creature_proficiencies.remove_source(source_id)

        return undo

    return EntityTransform("origin.tools", apply)


def _weapon_training_transform(
    feature_id: str,
    weapon_ids: tuple[str, ...],
) -> EntityTransform:
    """Grant exact semantic weapon identities without content references."""
    def apply(entity: Entity):
        source_ids = []
        try:
            for weapon_id in weapon_ids:
                source_id = _source_id(entity, f"{feature_id}.{weapon_id}")
                entity.creature_proficiencies.add_specific_weapon_source(
                    source_id,
                    weapon_id,
                )
                source_ids.append(source_id)
        except Exception:
            for source_id in reversed(source_ids):
                entity.creature_proficiencies.remove_source(source_id)
            raise

        def undo() -> None:
            for source_id in reversed(source_ids):
                entity.creature_proficiencies.remove_source(source_id)

        return undo

    return EntityTransform(feature_id, apply)


def _poison_saving_throw_advantage(
    source_entity_uuid,
    target_entity_uuid,
    modifier_context: dict[str, Any] | None,
    *,
    modifier_name: str,
) -> AdvantageModifier | None:
    """Return advantage only for a save explicitly tagged as poison."""
    context = (
        modifier_context.get(SAVING_THROW_CONTEXT_KEY)
        if modifier_context is not None
        else None
    )
    if not isinstance(context, SavingThrowContext):
        return None
    if SavingThrowEffectTag.POISON not in context.effect_tags:
        return None
    return AdvantageModifier(
        name=modifier_name,
        value=AdvantageStatus.ADVANTAGE,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid,
    )


def _resistance_transform(
    feature_id: str,
    damage_type: DamageType,
    *,
    name: str,
) -> EntityTransform:
    """Grant one exact damage resistance and retain its inverse."""
    def apply(entity: Entity):
        modifier = ResistanceModifier(
            uuid=_source_id(entity, f"{feature_id}.{damage_type.value}"),
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=name,
            value=ResistanceStatus.RESISTANCE,
            damage_type=damage_type,
        )
        entity.health.damage_reduction.self_static.add_resistance_modifier(
            modifier,
        )

        def undo() -> None:
            entity.health.damage_reduction.remove_modifier(modifier.uuid)
            modifier.remove_from_register()

        return undo

    return EntityTransform(feature_id, apply)


def _dwarf_poison_resilience_transform() -> EntityTransform:
    """Install both halves of Dwarven Resilience as one reversible grant."""
    feature_id = "species.dwarf.poison_resilience"

    def apply(entity: Entity):
        resistance = ResistanceModifier(
            uuid=_source_id(entity, f"{feature_id}.resistance"),
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name="Dwarven Resilience poison resistance",
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.POISON,
        )
        contextual_modifiers = []
        entity.health.damage_reduction.self_static.add_resistance_modifier(
            resistance,
        )
        try:
            for ability in AbilityName:
                value = entity.saving_throws.get_saving_throw(ability).bonus
                modifier_name = (
                    "Dwarven Resilience "
                    f"{ability.value} poison saving throw advantage"
                )
                modifier = ContextualAdvantageModifier(
                    uuid=_source_id(
                        entity,
                        f"{feature_id}.saving_throw.{ability.value}",
                    ),
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    name=modifier_name,
                    callable=partial(
                        _poison_saving_throw_advantage,
                        modifier_name=modifier_name,
                    ),
                )
                value.self_contextual.add_advantage_modifier(modifier)
                contextual_modifiers.append((value, modifier))
        except Exception:
            for value, modifier in reversed(contextual_modifiers):
                value.remove_modifier(modifier.uuid)
                modifier.remove_from_register()
            entity.health.damage_reduction.remove_modifier(resistance.uuid)
            resistance.remove_from_register()
            raise

        def undo() -> None:
            for value, modifier in reversed(contextual_modifiers):
                value.remove_modifier(modifier.uuid)
                modifier.remove_from_register()
            entity.health.damage_reduction.remove_modifier(resistance.uuid)
            resistance.remove_from_register()

        return undo

    return EntityTransform(feature_id, apply)


def _saving_throw_advantage_transform(
    feature_id: str,
    *,
    abilities: tuple[AbilityName, ...] = tuple(AbilityName),
    effect_tag: SavingThrowEffectTag | None = None,
    requires_magical: bool | None = None,
) -> EntityTransform:
    """Install one contextual origin saving-throw rule with an exact inverse."""
    def resolve_advantage(
        source_entity_uuid,
        target_entity_uuid,
        modifier_context: dict[str, Any] | None,
        *,
        modifier_name: str,
    ) -> AdvantageModifier | None:
        context = (
            modifier_context.get(SAVING_THROW_CONTEXT_KEY)
            if modifier_context is not None
            else None
        )
        if not isinstance(context, SavingThrowContext):
            return None
        if requires_magical is not None and context.is_magical is not requires_magical:
            return None
        if effect_tag is not None and effect_tag not in context.effect_tags:
            return None
        return AdvantageModifier(
            name=modifier_name,
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=target_entity_uuid,
        )

    def apply(entity: Entity):
        installed = []
        try:
            for ability in abilities:
                value = entity.saving_throws.get_saving_throw(ability).bonus
                modifier_name = (
                    f"{feature_id} {ability.value} saving throw advantage"
                )
                modifier = ContextualAdvantageModifier(
                    uuid=_source_id(
                        entity,
                        f"{feature_id}.saving_throw.{ability.value}",
                    ),
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    name=modifier_name,
                    callable=partial(
                        resolve_advantage,
                        modifier_name=modifier_name,
                    ),
                )
                value.self_contextual.add_advantage_modifier(modifier)
                installed.append((value, modifier))
        except Exception:
            for value, modifier in reversed(installed):
                value.remove_modifier(modifier.uuid)
                modifier.remove_from_register()
            raise

        def undo() -> None:
            for value, modifier in reversed(installed):
                value.remove_modifier(modifier.uuid)
                modifier.remove_from_register()

        return undo

    return EntityTransform(feature_id, apply)


def _innate_spell_source_transform(
    feature_id: str,
    *,
    ability: AbilityName,
    maximum_spell_rank: int,
    initial_spell_ids: tuple[str, ...],
    origin_root_id: str,
) -> EntityTransform:
    """Install one direct innate casting source and its birth-time spells."""
    def apply(entity: Entity):
        source_id = _source_id(entity, f"{feature_id}.spellcasting_source")
        actions = []
        entity.spellcasting.add_innate_source(
            source_id,
            ability,
            provider_id=feature_id,
            provider_level=1,
            maximum_spell_rank=maximum_spell_rank,
        )
        try:
            for spell_id in initial_spell_ids:
                spell_type = (
                    Thaumaturgy
                    if spell_id == "spell.thaumaturgy"
                    else SPELL_ACTION_TYPES_BY_ID[spell_id]
                )
                action = spell_type(
                    source_entity_uuid=entity.uuid,
                    caster_level=1,
                    cast_at_level=0,
                    spellcasting_source_id=source_id,
                    template=True,
                    semantic_key=spell_id,
                    behavior_id=spell_id,
                    provided_by_id=feature_id,
                    origin_root_id=origin_root_id,
                )
                action.bind_behavior_owner(origin_root_id=origin_root_id)
                entity.register_action(action)
                actions.append(action)
        except Exception:
            for action in reversed(actions):
                entity.unregister_action_by_uuid(action.uuid)
                action.remove_from_register()
            entity.spellcasting.remove_source(source_id)
            raise

        def undo() -> None:
            for action in reversed(actions):
                entity.unregister_action_by_uuid(action.uuid)
                action.remove_from_register()
            entity.spellcasting.remove_source(source_id)

        return undo

    return EntityTransform(feature_id, apply)


def _dragonborn_breath_weapon_transform(
    ancestry_value: str,
) -> EntityTransform:
    feature_id = "species.dragonborn.breath_weapon"
    definition = DRAGONBORN_ANCESTRY_DEFINITIONS[
        DragonbornAncestry(ancestry_value)
    ]

    def apply(entity: Entity):
        source_id = _source_id(entity, feature_id)
        action = DragonbornBreathWeapon(
            source_entity_uuid=entity.uuid,
            ancestry=definition.ancestry,
            damage_type=definition.damage_type,
            breath_geometry=definition.breath_geometry,
            save_ability=definition.save_ability,
            character_level=1,
            aoe_shape=(
                Line(
                    source_entity_uuid=entity.uuid,
                    target=(1, 0),
                    length_feet=definition.line_length_feet or 30,
                    width_feet=definition.line_width_feet or 5,
                )
                if definition.breath_geometry
                is DragonbornBreathGeometry.LINE
                else Cone(
                    source_entity_uuid=entity.uuid,
                    target=(1, 0),
                    length_feet=definition.cone_length_feet or 15,
                )
            ),
            template=True,
            semantic_key="action.origin.dragonborn.breath_weapon",
            behavior_id="action.origin.dragonborn.breath_weapon",
            provided_by_id=feature_id,
            origin_root_id="species.dragonborn",
        )
        action.bind_behavior_owner(origin_root_id="species.dragonborn")
        entity.action_economy.add_resource_contribution(
            DRAGONBORN_BREATH_RESOURCE,
            source_id,
            maximum=1,
            recharge_type=RechargeType.SHORT_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        try:
            entity.register_action(action)
        except Exception:
            entity.action_economy.remove_resource_contribution(
                DRAGONBORN_BREATH_RESOURCE,
                source_id,
            )
            action.remove_from_register()
            raise

        def undo() -> None:
            entity.unregister_action_by_uuid(action.uuid)
            action.remove_from_register()
            entity.action_economy.remove_resource_contribution(
                DRAGONBORN_BREATH_RESOURCE,
                source_id,
            )

        return undo

    return EntityTransform(feature_id, apply)


def _dragonborn_breath_level_transform(
    character_level: int,
) -> EntityTransform:
    feature_id = "species.dragonborn.breath_weapon"

    def apply(entity: Entity):
        candidates = tuple(
            action
            for action in entity.registered_actions
            if action.provided_by_id == feature_id
        )
        if len(candidates) != 1 or not isinstance(
            candidates[0],
            DragonbornBreathWeapon,
        ):
            raise RuntimeError("Dragonborn breath action ownership is inconsistent")
        action = candidates[0]
        previous_level = action.character_level
        action.character_level = character_level
        return lambda: setattr(action, "character_level", previous_level)

    return EntityTransform(
        f"{feature_id}.character_level.{character_level}",
        apply,
    )


def _high_elf_cantrip_level_transform(
    character_level: int,
) -> EntityTransform:
    feature_id = "species_variant.high_elf.wizard_cantrip"

    def apply(entity: Entity):
        candidates = tuple(
            action
            for action in entity.registered_actions
            if action.provided_by_id == feature_id
        )
        if len(candidates) != 1:
            raise RuntimeError("High Elf cantrip action ownership is inconsistent")
        action = candidates[0]
        previous_level = action.caster_level
        action.caster_level = character_level
        return lambda: setattr(action, "caster_level", previous_level)

    return EntityTransform(
        f"{feature_id}.character_level.{character_level}",
        apply,
    )


def _tiefling_hellish_rebuke_transform() -> EntityTransform:
    feature_id = "species.tiefling.infernal_legacy"
    spell_id = "spell.hellish_rebuke"
    resource_name = "origin_innate_spell:tiefling:hellish_rebuke"

    def apply(entity: Entity):
        source_id = _source_id(entity, f"{feature_id}.spellcasting_source")
        grant_id = _source_id(entity, f"{feature_id}.hellish_rebuke")
        handler = create_hellish_rebuke_reaction_handler(
            entity.uuid,
            spellcasting_source_id=source_id,
            fixed_cast_rank=2,
            resource_name=resource_name,
        )
        handler.behavior_id = "reaction.spell.hellish_rebuke"
        handler.provided_by_id = feature_id
        handler.origin_root_id = "species.tiefling"
        entity.action_economy.add_resource_contribution(
            resource_name,
            grant_id,
            maximum=1,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        try:
            entity.add_event_handler(handler)
            entity.spellcasting.add_learned_reaction_spell_source(
                spell_id=spell_id,
                source_id=source_id,
                handler_uuid=handler.uuid,
            )
        except Exception:
            if handler.uuid in entity.event_handlers:
                entity.remove_event_handler(handler)
            entity.action_economy.remove_resource_contribution(
                resource_name,
                grant_id,
            )
            handler.remove_from_register()
            raise

        def undo() -> None:
            remove_handler = (
                entity.spellcasting.remove_learned_reaction_spell_source(
                    spell_id=spell_id,
                    source_id=source_id,
                    handler_uuid=handler.uuid,
                )
            )
            if remove_handler:
                entity.remove_event_handler(handler)
                handler.remove_from_register()
            entity.action_economy.remove_resource_contribution(
                resource_name,
                grant_id,
            )

        return undo

    return EntityTransform(f"{feature_id}.character_level.3", apply)


def _tiefling_darkness_transform() -> EntityTransform:
    feature_id = "species.tiefling.infernal_legacy"
    spell_id = "spell.darkness"
    resource_name = "origin_innate_spell:tiefling:darkness"

    def apply(entity: Entity):
        source_id = _source_id(entity, f"{feature_id}.spellcasting_source")
        grant_id = _source_id(entity, f"{feature_id}.darkness")
        action = SPELL_ACTION_TYPES_BY_ID[spell_id](
            source_entity_uuid=entity.uuid,
            caster_level=5,
            cast_at_level=2,
            spellcasting_source_id=source_id,
            alt_skip_slot=True,
            alt_extra_costs=[Cost(
                name="Tiefling Darkness long-rest use",
                cost_type="actions",
                cost=0,
                resource_name=resource_name,
                resource_cost=1,
                resource_evaluator=block_action_resource_cost_evaluator,
            )],
            template=True,
            semantic_key=spell_id,
            behavior_id=spell_id,
            provided_by_id=feature_id,
            origin_root_id="species.tiefling",
        )
        action.bind_behavior_owner(origin_root_id="species.tiefling")
        entity.action_economy.add_resource_contribution(
            resource_name,
            grant_id,
            maximum=1,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        try:
            entity.register_action(action)
        except Exception:
            entity.action_economy.remove_resource_contribution(
                resource_name,
                grant_id,
            )
            action.remove_from_register()
            raise

        def undo() -> None:
            entity.unregister_action_by_uuid(action.uuid)
            action.remove_from_register()
            entity.action_economy.remove_resource_contribution(
                resource_name,
                grant_id,
            )

        return undo

    return EntityTransform(f"{feature_id}.character_level.5", apply)


def resolve_origin_level_transforms(
    species: Species | None,
    species_variant: SpeciesVariant | None,
    character_level: int,
) -> tuple[EntityTransform, ...]:
    """Resolve origin mechanics owned by one concrete character level."""
    if character_level < 1:
        raise ValueError("origin character level must be positive")
    transforms: list[EntityTransform] = []
    if species is Species.DRAGONBORN:
        transforms.append(_dragonborn_breath_level_transform(character_level))
    if species_variant is SpeciesVariant.HIGH_ELF:
        transforms.append(_high_elf_cantrip_level_transform(character_level))
    if species is Species.TIEFLING and character_level == 3:
        transforms.append(_tiefling_hellish_rebuke_transform())
    if species is Species.TIEFLING and character_level == 5:
        transforms.append(_tiefling_darkness_transform())
    if species_variant is not SpeciesVariant.HILL_DWARF:
        return tuple(transforms)
    feature_id = "species_variant.hill_dwarf.dwarven_toughness"

    def apply(entity: Entity):
        modifier = NumericalModifier(
            uuid=_source_id(entity, f"{feature_id}.level.{character_level}"),
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=f"Dwarven Toughness character level {character_level}",
            value=1,
        )
        value = entity.health.max_hit_points_bonus
        value.self_static.add_value_modifier(modifier)

        def undo() -> None:
            value.remove_modifier(modifier.uuid)
            modifier.remove_from_register()

        return undo

    transforms.append(
        EntityTransform(f"{feature_id}.level.{character_level}", apply),
    )
    return tuple(transforms)


def _capability_transform(capabilities) -> EntityTransform:
    def apply(entity: Entity):
        sources = []
        try:
            for capability in capabilities:
                source_id = _source_id(entity, f"capability.{capability.value}")
                entity.add_origin_capability_source(capability, source_id)
                sources.append((capability, source_id))
        except Exception:
            for capability, source_id in reversed(sources):
                entity.remove_origin_capability_source(capability, source_id)
            raise

        def undo() -> None:
            for capability, source_id in reversed(sources):
                entity.remove_origin_capability_source(capability, source_id)

        return undo

    return EntityTransform("origin.capabilities", apply)


def _feature_identities_transform(
    feature_ids: tuple[str, ...],
) -> EntityTransform:
    """Persist exact origin feature identities beside their mechanics."""
    def apply(entity: Entity):
        installed = []
        try:
            for feature_id in feature_ids:
                source_id = _source_id(entity, f"feature.{feature_id}")
                entity.add_feature_source(feature_id, source_id)
                installed.append((feature_id, source_id))
        except Exception:
            for feature_id, source_id in reversed(installed):
                entity.remove_feature_source(feature_id, source_id)
            raise

        def undo() -> None:
            for feature_id, source_id in reversed(installed):
                entity.remove_feature_source(feature_id, source_id)

        return undo

    return EntityTransform("origin.feature_identities", apply)


def _halfling_lucky_transform() -> EntityTransform:
    feature_id = "species.halfling.lucky"

    def apply(entity: Entity):
        handler = EventHandler(
            name="Halfling Lucky",
            source_entity_uuid=entity.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=event_type,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=entity.uuid,
                )
                for event_type in (
                    EventType.ATTACK_D20_ROLL_RESULT,
                    EventType.SAVE_D20_ROLL_RESULT,
                    EventType.CHECK_D20_ROLL_RESULT,
                )
            ],
            event_processor=halfling_lucky_processor,
            semantic_key=feature_id,
            behavior_id=feature_id,
            provided_by_id=feature_id,
            origin_root_id="species.halfling",
        )
        entity.add_event_handler(handler)

        def undo() -> None:
            entity.remove_event_handler(handler)
            handler.remove_from_register()

        return undo

    return EntityTransform(feature_id, apply)


def _half_orc_relentless_endurance_transform() -> EntityTransform:
    feature_id = "species.half_orc.relentless_endurance"

    def apply(entity: Entity):
        source_id = _source_id(entity, feature_id)
        handler = EventHandler(
            name="Relentless Endurance",
            source_entity_uuid=entity.uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TAKE_DAMAGE,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=entity.uuid,
            )],
            event_processor=half_orc_relentless_endurance_processor,
            semantic_key=feature_id,
            behavior_id=feature_id,
            provided_by_id=feature_id,
            origin_root_id="species.half_orc",
        )
        entity.action_economy.add_resource_contribution(
            HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
            source_id,
            maximum=1,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        try:
            entity.add_event_handler(handler)
        except Exception:
            entity.action_economy.remove_resource_contribution(
                HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
                source_id,
            )
            handler.remove_from_register()
            raise

        def undo() -> None:
            entity.remove_event_handler(handler)
            handler.remove_from_register()
            entity.action_economy.remove_resource_contribution(
                HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
                source_id,
            )

        return undo

    return EntityTransform(feature_id, apply)


def _feature_transform(
    feature_id: str,
    choices: dict[str, tuple[str, ...]],
) -> EntityTransform:
    if feature_id == "species.dragonborn.ancestry_resistance":
        ancestry = choices["species.dragonborn.draconic_ancestry"][0]
        return _resistance_transform(
            feature_id,
            _DRAGONBORN_DAMAGE_TYPES[ancestry],
            name=f"{ancestry.title()} Draconic Ancestry",
        )
    if feature_id == "species.dragonborn.breath_weapon":
        return _dragonborn_breath_weapon_transform(
            choices["species.dragonborn.draconic_ancestry"][0],
        )
    if feature_id == "species.dwarf.combat_training":
        return _weapon_training_transform(feature_id, _DWARF_WEAPON_IDS)
    if feature_id == "species.dwarf.poison_resilience":
        return _dwarf_poison_resilience_transform()
    if feature_id == "species_variant.high_elf.weapon_training":
        return _weapon_training_transform(feature_id, _HIGH_ELF_WEAPON_IDS)
    if feature_id == "species_variant.rock_gnome.tinkers_tools":
        return _tool_transform(("tool.tinkers_tools",))
    if feature_id == "species_variant.high_elf.wizard_cantrip":
        spell_id = choices[
            "species_variant.high_elf.wizard_cantrip"
        ][0]
        return _innate_spell_source_transform(
            feature_id,
            ability=AbilityName.INTELLIGENCE,
            maximum_spell_rank=0,
            initial_spell_ids=(spell_id,),
            origin_root_id="species_variant.high_elf",
        )
    if feature_id == "species.tiefling.infernal_legacy":
        return _innate_spell_source_transform(
            feature_id,
            ability=AbilityName.CHARISMA,
            maximum_spell_rank=2,
            initial_spell_ids=("spell.thaumaturgy",),
            origin_root_id="species.tiefling",
        )
    if feature_id == "species.elf.fey_ancestry":
        return _saving_throw_advantage_transform(
            feature_id,
            effect_tag=SavingThrowEffectTag.CHARM,
        )
    if feature_id == "species.gnome.cunning":
        return _saving_throw_advantage_transform(
            feature_id,
            abilities=(
                AbilityName.INTELLIGENCE,
                AbilityName.WISDOM,
                AbilityName.CHARISMA,
            ),
            requires_magical=True,
        )
    if feature_id == "species.halfling.brave":
        return _saving_throw_advantage_transform(
            feature_id,
            effect_tag=SavingThrowEffectTag.FEAR,
        )
    if feature_id == "species.halfling.lucky":
        return _halfling_lucky_transform()
    if feature_id == "species.half_orc.relentless_endurance":
        return _half_orc_relentless_endurance_transform()

    def apply(entity: Entity):
        source_id = _source_id(entity, feature_id)
        if feature_id == "sense.darkvision.60":
            entity.senses.add_sense_mode_source(
                source_id,
                SenseMode(sense_type=SensesType.DARKVISION, range_feet=60),
            )
            return lambda: entity.senses.remove_sense_mode_source(source_id)
        if feature_id == "species.half_orc.savage_attacks":
            value = entity.equipment.crit_extra_dice_melee
            modifier = NumericalModifier(
                uuid=source_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Half-Orc Savage Attacks",
                value=1,
            )
            value.self_static.add_value_modifier(modifier)

            def undo_savage_attacks() -> None:
                value.remove_modifier(modifier.uuid)
                modifier.remove_from_register()

            return undo_savage_attacks
        if feature_id == "species.tiefling.fire_resistance":
            value = entity.health.damage_reduction
            modifier = ResistanceModifier(
                uuid=source_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Tiefling fire resistance",
                value=ResistanceStatus.RESISTANCE,
                damage_type=DamageType.FIRE,
            )
            value.self_static.add_resistance_modifier(modifier)

            def undo_fire_resistance() -> None:
                value.remove_modifier(modifier.uuid)
                modifier.remove_from_register()

            return undo_fire_resistance
        raise RuntimeError(f"origin feature {feature_id} has no transform")

    return EntityTransform(feature_id, apply)


def resolve_origin_transforms(
    *,
    species: Species,
    species_variant: SpeciesVariant | None,
    background: Background,
    state: AppliedOriginState,
) -> tuple[EntityTransform, ...]:
    """Validate one authored origin and return its complete concrete changes."""
    _validate_origin_state(
        species=species,
        species_variant=species_variant,
        background=background,
        state=state,
    )
    species_definition = SPECIES_DEFINITIONS[species]
    variant_definition = get_species_variant_definition(species_variant)
    background_definition = BACKGROUND_DEFINITIONS[background]
    feature_ids = (
        *species_definition.feature_ids,
        *(variant_definition.feature_ids if variant_definition is not None else ()),
        *background_definition.feature_ids,
    )
    unsupported = tuple(
        feature_id
        for feature_id in feature_ids
        if feature_id not in _SUPPORTED_FEATURE_IDS
        and feature_id not in _SEPARATELY_COMPOSED_FEATURE_IDS
    )
    if unsupported:
        raise NotImplementedError(
            "origin cannot yet compose without deferred action/condition/item "
            f"content: {', '.join(unsupported)}",
        )

    choices = {choice.choice_id: choice.values for choice in state.choices}
    chosen_languages = tuple(
        value
        for choice_id, values in choices.items()
        if "language" in choice_id
        for value in values
    )
    chosen_skills = tuple(
        SkillName(value)
        for choice_id, values in choices.items()
        if "skill" in choice_id
        for value in values
    )
    chosen_tools = tuple(
        value
        for choice_id, values in choices.items()
        if "tool" in choice_id
        for value in values
    )
    languages = tuple(language.value for language in (
        *species_definition.fixed_languages,
        *(variant_definition.fixed_languages if variant_definition is not None else ()),
    )) + chosen_languages
    skills = (
        *species_definition.fixed_skills,
        *background_definition.fixed_skills,
        *chosen_skills,
    )
    capabilities = (
        *species_definition.capabilities,
        *(variant_definition.capabilities if variant_definition is not None else ()),
        *background_definition.capabilities,
    )
    transforms = [
        _identity_transform(species, species_variant, background),
        _ability_scores_transform(state),
        _physical_transform(species),
        _language_transform(languages),
    ]
    if skills:
        transforms.append(_skill_transform(skills))
    if chosen_tools:
        transforms.append(_tool_transform(chosen_tools))
    if capabilities:
        transforms.append(_capability_transform(capabilities))
    if feature_ids:
        transforms.append(_feature_identities_transform(feature_ids))
    transforms.extend(
        _feature_transform(feature_id, choices)
        for feature_id in feature_ids
        if feature_id in _SUPPORTED_FEATURE_IDS
    )
    return tuple(transforms)


__all__ = [
    "resolve_origin_level_transforms",
    "resolve_origin_transforms",
]
