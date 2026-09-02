"""Concrete source-owned origin installation, removal, and level scaling."""

from dataclasses import replace
from functools import partial
from typing import cast
from uuid import UUID, uuid5

from dnd.actions import SpellAction
from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.conditions import Concentrating
from dnd.content.characters.origin_definitions import (
    ABILITY_ORDER,
    DRAGONBORN_ANCESTRY_DEFINITIONS,
    ResolvedOrigin,
)
from dnd.core.aoe import Cone, Line
from dnd.core.base_actions import Cost, block_action_resource_cost_evaluator
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.creature_types import DamageType
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    ContextualAdvantageModifier,
    NumericalModifier,
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.core.proficiency_types import ProficiencyMode
from dnd.core.saving_throw_types import (
    SAVING_THROW_CONTEXT_KEY,
    SavingThrowContext,
    SavingThrowEffectTag,
)
from dnd.entity import Entity
from dnd.origins.dragonborn import (
    DRAGONBORN_BREATH_RESOURCE,
    DragonbornBreathWeapon,
)
from dnd.origins.halfling import halfling_lucky_processor
from dnd.origins.half_orc import (
    HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
    half_orc_relentless_endurance_processor,
)
from dnd.spells.conjuration import Darkness
from dnd.spells.evocation import FireBolt
from dnd.spells.infernal import (
    Thaumaturgy,
    create_hellish_rebuke_reaction_handler,
)
from dnd.types.abilities import AbilityName, SkillName
from dnd.types.character_progression import (
    OriginCapability,
    Species,
    SpeciesVariant,
)
from dnd.types.character_receipts import OriginGrantReceipt
from dnd.types.senses import SenseMode, SensesType


ORIGIN_STEP_ID = "origin.character"
_DWARF_WEAPONS = (
    "weapon.battleaxe",
    "weapon.handaxe",
    "weapon.light_hammer",
    "weapon.warhammer",
)
_HIGH_ELF_WEAPONS = (
    "weapon.longbow",
    "weapon.longsword",
    "weapon.shortbow",
    "weapon.shortsword",
)
_TIEFLING_REBUKE_RESOURCE = "origin_innate_spell:tiefling:hellish_rebuke"
_TIEFLING_DARKNESS_RESOURCE = "origin_innate_spell:tiefling:darkness"


def _source(entity: Entity, identity: str) -> UUID:
    return uuid5(entity.uuid, f"dnd-engine:origin:v1:{identity}")


def _binding(
    entity: Entity,
    *,
    behavior_id: str,
    provided_by_id: str,
    origin_root_id: str,
) -> BehaviorBinding:
    return BehaviorBinding(
        behavior_id=behavior_id,
        provided_by_id=provided_by_id,
        origin_root_id=origin_root_id,
        runtime_owner_uuid=entity.uuid,
    )


def _saving_throw_advantage(
    source_entity_uuid: UUID,
    target_entity_uuid: UUID | None,
    modifier_context: dict[str, object] | None,
    *,
    modifier_name: str,
    effect_tag: SavingThrowEffectTag | None,
    requires_magical: bool | None,
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


def _add_saving_advantage(
    entity: Entity,
    rows: list[tuple[AbilityName, UUID]],
    *,
    feature_id: str,
    abilities: tuple[AbilityName, ...] = ABILITY_ORDER,
    effect_tag: SavingThrowEffectTag | None = None,
    requires_magical: bool | None = None,
) -> None:
    for ability in abilities:
        modifier_id = _source(entity, f"{feature_id}.save.{ability}")
        modifier_name = f"{feature_id} {ability} saving throw advantage"
        modifier = ContextualAdvantageModifier(
            uuid=modifier_id,
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=modifier_name,
            callable=partial(
                _saving_throw_advantage,
                modifier_name=modifier_name,
                effect_tag=effect_tag,
                requires_magical=requires_magical,
            ),
        )
        entity.saving_throws.get_saving_throw(
            ability,
        ).bonus.self_contextual.add_advantage_modifier(modifier)
        rows.append((ability, modifier_id))


def _add_resistance(
    entity: Entity,
    rows: list[tuple[str, UUID]],
    *,
    feature_id: str,
    damage_type: DamageType,
    name: str,
) -> None:
    modifier_id = _source(entity, f"{feature_id}.{damage_type.value}")
    modifier = ResistanceModifier(
        uuid=modifier_id,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        name=name,
        value=ResistanceStatus.RESISTANCE,
        damage_type=damage_type,
    )
    entity.health.damage_reduction.self_static.add_resistance_modifier(modifier)
    rows.append((damage_type.value, modifier_id))


def _add_spell_action(
    entity: Entity,
    actions: list[UUID],
    action: SpellAction,
    *,
    behavior_id: str,
    provided_by_id: str,
    origin_root_id: str,
) -> None:
    action.behavior_binding = _binding(
        entity,
        behavior_id=behavior_id,
        provided_by_id=provided_by_id,
        origin_root_id=origin_root_id,
    )
    try:
        entity.register_action(action)
    except BaseException:
        action.remove_from_register()
        raise
    actions.append(action.uuid)


def _install_base_innate_spells(
    entity: Entity,
    resolved: ResolvedOrigin,
    character_level: int,
    spell_sources: list[UUID],
    actions: list[UUID],
) -> None:
    if resolved.species_variant is SpeciesVariant.HIGH_ELF:
        feature_id = "species_variant.high_elf.wizard_cantrip"
        source_id = _source(entity, f"{feature_id}.source")
        entity.spellcasting.add_innate_source(
            source_id,
            "intelligence",
            provider_id=feature_id,
            provider_level=character_level,
            maximum_spell_rank=0,
        )
        spell_sources.append(source_id)
        spell_id = resolved.choice(feature_id)[0]
        _add_spell_action(
            entity,
            actions,
            FireBolt(
                uuid=_source(entity, f"{feature_id}.action.{spell_id}"),
                source_entity_uuid=entity.uuid,
                caster_level=character_level,
                cast_at_level=0,
                spellcasting_source_id=source_id,
                template=True,
                semantic_key=spell_id,
            ),
            behavior_id=spell_id,
            provided_by_id=feature_id,
            origin_root_id=SpeciesVariant.HIGH_ELF.value,
        )

    if resolved.species is Species.TIEFLING:
        feature_id = "species.tiefling.infernal_legacy"
        source_id = _source(entity, f"{feature_id}.source")
        entity.spellcasting.add_innate_source(
            source_id,
            "charisma",
            provider_id=feature_id,
            provider_level=character_level,
            maximum_spell_rank=2,
        )
        spell_sources.append(source_id)
        _add_spell_action(
            entity,
            actions,
            Thaumaturgy(
                uuid=_source(entity, f"{feature_id}.action.spell.thaumaturgy"),
                source_entity_uuid=entity.uuid,
                caster_level=character_level,
                cast_at_level=0,
                spellcasting_source_id=source_id,
                template=True,
                semantic_key="spell.thaumaturgy",
            ),
            behavior_id="spell.thaumaturgy",
            provided_by_id=feature_id,
            origin_root_id=Species.TIEFLING.value,
        )


def _install_level_spells(
    entity: Entity,
    species: Species,
    character_level: int,
    actions: list[UUID],
    darkness_root_owners: list[UUID],
    resources: list[tuple[str, UUID]],
    learned_reactions: list[tuple[str, UUID, UUID]],
    *,
    install_rebuke: bool | None = None,
    install_darkness: bool | None = None,
) -> None:
    if species is not Species.TIEFLING:
        return
    feature_id = "species.tiefling.infernal_legacy"
    source_id = _source(entity, f"{feature_id}.source")
    add_rebuke = character_level >= 3 if install_rebuke is None else install_rebuke
    add_darkness = character_level >= 5 if install_darkness is None else install_darkness
    if add_rebuke:
        grant_id = _source(entity, f"{feature_id}.hellish_rebuke")
        entity.action_economy.add_resource_contribution(
            _TIEFLING_REBUKE_RESOURCE,
            grant_id,
            maximum=1,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        resources.append((_TIEFLING_REBUKE_RESOURCE, grant_id))
        handler_uuid = entity.spellcasting.learned_reaction_spell_handler_uuid(
            "spell.hellish_rebuke",
        )
        created_handler = None
        if handler_uuid is None:
            created_handler = create_hellish_rebuke_reaction_handler(
                entity.uuid,
                handler_uuid=_source(
                    entity,
                    f"{feature_id}.hellish_rebuke.handler",
                ),
            )
            created_handler.behavior_binding = _binding(
                entity,
                behavior_id="reaction.spell.hellish_rebuke",
                provided_by_id="spell.hellish_rebuke",
                origin_root_id="spell.hellish_rebuke",
            )
            entity.add_event_handler(created_handler)
            handler_uuid = created_handler.uuid
        elif handler_uuid not in entity.event_handlers:
            raise RuntimeError("learned Hellish Rebuke handler is missing")
        try:
            entity.spellcasting.add_learned_reaction_spell_source(
                spell_id="spell.hellish_rebuke",
                source_id=source_id,
                handler_uuid=handler_uuid,
                fixed_cast_rank=2,
                resource_name=_TIEFLING_REBUKE_RESOURCE,
            )
        except BaseException:
            if created_handler is not None:
                entity.remove_event_handler(created_handler)
                created_handler.remove_from_register()
            raise
        learned_reactions.append(("spell.hellish_rebuke", source_id, handler_uuid))

    if add_darkness:
        grant_id = _source(entity, f"{feature_id}.darkness")
        entity.action_economy.add_resource_contribution(
            _TIEFLING_DARKNESS_RESOURCE,
            grant_id,
            maximum=1,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        resources.append((_TIEFLING_DARKNESS_RESOURCE, grant_id))
        darkness = Darkness(
            uuid=_source(entity, f"{feature_id}.action.spell.darkness"),
            source_entity_uuid=entity.uuid,
            caster_level=character_level,
            cast_at_level=2,
            spellcasting_source_id=source_id,
            alt_skip_slot=True,
            alt_extra_costs=[Cost(
                name="Tiefling Darkness long-rest use",
                cost_type="actions",
                cost=0,
                resource_name=_TIEFLING_DARKNESS_RESOURCE,
                resource_cost=1,
                resource_evaluator=block_action_resource_cost_evaluator,
            )],
            template=True,
            semantic_key="spell.darkness",
        )
        _add_spell_action(
            entity,
            actions,
            darkness,
            behavior_id="spell.darkness",
            provided_by_id=feature_id,
            origin_root_id=Species.TIEFLING.value,
        )
        darkness_root_owners.append(darkness.uuid)


def apply_origin(
    entity: Entity,
    resolved: ResolvedOrigin,
    *,
    character_level: int,
) -> OriginGrantReceipt:
    """Install one validated origin with exact source-owned contributions."""
    if not 1 <= character_level <= 20:
        raise ValueError("origin character level must be between 1 and 20")
    if entity.applied_origin_state is not None:
        raise RuntimeError("character origin is already installed")
    try:
        entity.character_grant_receipt(ORIGIN_STEP_ID)
    except KeyError:
        pass
    else:
        raise RuntimeError("character origin receipt is already installed")

    source_id = _source(entity, ORIGIN_STEP_ID)
    ability_modifiers: list[tuple[AbilityName, UUID]] = []
    skills: list[tuple[SkillName, UUID]] = []
    creature_sources: list[UUID] = []
    saving_advantages: list[tuple[AbilityName, UUID]] = []
    resistances: list[tuple[str, UUID]] = []
    critical_modifiers: list[UUID] = []
    maximum_hp_modifiers: list[UUID] = []
    speed_modifiers: list[UUID] = []
    actions: list[UUID] = []
    darkness_root_owners: list[UUID] = []
    handlers: list[UUID] = []
    resources: list[tuple[str, UUID]] = []
    senses: list[UUID] = []
    sizes: list[UUID] = []
    capabilities: list[tuple[OriginCapability, UUID]] = []
    features: list[tuple[str, UUID]] = []
    spell_sources: list[UUID] = []
    learned_reactions: list[tuple[str, UUID, UUID]] = []
    identity_installed = False
    state_installed = False

    try:
        entity.set_character_origin_identity(
            species=resolved.species,
            species_variant=resolved.species_variant,
            background=resolved.background,
        )
        identity_installed = True
        entity.applied_origin_state = resolved.state
        state_installed = True

        for ability, amount in resolved.state.flexible_ability_bonuses:
            modifier_id = _source(entity, f"ability.{ability}")
            modifier = NumericalModifier(
                uuid=modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name=f"Character creation {ability} bonus",
                value=amount,
            )
            entity.ability_scores.get_ability(
                ability,
            ).ability_score.self_static.add_value_modifier(modifier)
            ability_modifiers.append((ability, modifier_id))

        size_id = _source(entity, "physical.size")
        entity.add_structural_size_source(size_id, resolved.size)
        sizes.append(size_id)
        speed_delta = resolved.walking_speed_feet - entity.action_economy.get_base_value(
            "movement",
        )
        if speed_delta:
            modifier_id = _source(entity, "physical.walking_speed")
            modifier = NumericalModifier(
                uuid=modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name=f"{resolved.species.value} walking speed",
                value=speed_delta,
            )
            entity.action_economy.movement.self_static.add_value_modifier(modifier)
            speed_modifiers.append(modifier_id)

        for language_id in resolved.languages:
            language_source = _source(entity, f"language.{language_id}")
            entity.creature_proficiencies.add_language_source(
                language_source,
                language_id,
            )
            creature_sources.append(language_source)
        for skill in resolved.skills:
            skill_source = _source(entity, f"skill.{skill}")
            entity.skill_set.get_skill(skill).add_proficiency_source(
                skill_source,
                ProficiencyMode.FULL,
            )
            skills.append((skill, skill_source))
        for tool_id in resolved.tools:
            tool_source = _source(entity, f"tool.{tool_id}")
            entity.creature_proficiencies.add_tool_source(tool_source, tool_id)
            creature_sources.append(tool_source)
        if resolved.species_variant is SpeciesVariant.ROCK_GNOME:
            tool_source = _source(entity, "tool.tool.tinkers_tools")
            entity.creature_proficiencies.add_tool_source(
                tool_source,
                "tool.tinkers_tools",
            )
            creature_sources.append(tool_source)

        weapon_ids: tuple[str, ...] = ()
        if resolved.species is Species.DWARF:
            weapon_ids = _DWARF_WEAPONS
        if resolved.species_variant is SpeciesVariant.HIGH_ELF:
            weapon_ids = (*weapon_ids, *_HIGH_ELF_WEAPONS)
        for weapon_id in weapon_ids:
            weapon_source = _source(entity, f"weapon.{weapon_id}")
            entity.creature_proficiencies.add_specific_weapon_source(
                weapon_source,
                weapon_id,
            )
            creature_sources.append(weapon_source)

        for capability in resolved.capabilities:
            capability_source = _source(entity, f"capability.{capability.value}")
            entity.add_origin_capability_source(capability, capability_source)
            capabilities.append((capability, capability_source))
        for feature_id in resolved.feature_ids:
            feature_source = _source(entity, f"feature.{feature_id}")
            entity.add_feature_source(feature_id, feature_source)
            features.append((feature_id, feature_source))

        if "sense.darkvision.60" in resolved.feature_ids:
            sense_id = _source(entity, "sense.darkvision.60")
            entity.senses.add_sense_mode_source(
                sense_id,
                SenseMode(sense_type=SensesType.DARKVISION, range_feet=60),
            )
            senses.append(sense_id)
        if resolved.species is Species.DWARF:
            _add_resistance(
                entity,
                resistances,
                feature_id="species.dwarf.poison_resilience",
                damage_type=DamageType.POISON,
                name="Dwarven Resilience poison resistance",
            )
            _add_saving_advantage(
                entity,
                saving_advantages,
                feature_id="species.dwarf.poison_resilience",
                effect_tag=SavingThrowEffectTag.POISON,
            )
        if "species.elf.fey_ancestry" in resolved.feature_ids:
            _add_saving_advantage(
                entity,
                saving_advantages,
                feature_id="species.elf.fey_ancestry",
                effect_tag=SavingThrowEffectTag.CHARM,
            )
        if resolved.species is Species.GNOME:
            _add_saving_advantage(
                entity,
                saving_advantages,
                feature_id="species.gnome.cunning",
                abilities=("intelligence", "wisdom", "charisma"),
                requires_magical=True,
            )
        if resolved.species is Species.HALFLING:
            _add_saving_advantage(
                entity,
                saving_advantages,
                feature_id="species.halfling.brave",
                effect_tag=SavingThrowEffectTag.FEAR,
            )
            handler = EventHandler(
                uuid=_source(entity, "species.halfling.lucky.handler"),
                name="Halfling Lucky",
                semantic_key="species.halfling.lucky",
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
                behavior_binding=_binding(
                    entity,
                    behavior_id="trait.origin.halfling.lucky",
                    provided_by_id="species.halfling.lucky",
                    origin_root_id=Species.HALFLING.value,
                ),
            )
            entity.add_event_handler(handler)
            handlers.append(handler.uuid)
        if resolved.species is Species.HALF_ORC:
            modifier_id = _source(entity, "species.half_orc.savage_attacks")
            modifier = NumericalModifier(
                uuid=modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Half-Orc Savage Attacks",
                value=1,
            )
            entity.equipment.crit_extra_dice_melee.self_static.add_value_modifier(
                modifier,
            )
            critical_modifiers.append(modifier_id)
            resource_id = _source(entity, "species.half_orc.relentless_endurance")
            entity.action_economy.add_resource_contribution(
                HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
                resource_id,
                maximum=1,
                recharge_type=RechargeType.LONG_REST,
                capacity_policy=ResourceCapacityPolicy.MAXIMUM,
            )
            resources.append((HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE, resource_id))
            handler = EventHandler(
                uuid=_source(
                    entity,
                    "species.half_orc.relentless_endurance.handler",
                ),
                name="Relentless Endurance",
                semantic_key="species.half_orc.relentless_endurance",
                source_entity_uuid=entity.uuid,
                trigger_conditions=[Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=entity.uuid,
                )],
                event_processor=half_orc_relentless_endurance_processor,
                behavior_binding=_binding(
                    entity,
                    behavior_id="trait.origin.half_orc.relentless_endurance",
                    provided_by_id="species.half_orc.relentless_endurance",
                    origin_root_id=Species.HALF_ORC.value,
                ),
            )
            entity.add_event_handler(handler)
            handlers.append(handler.uuid)
        if resolved.species is Species.TIEFLING:
            _add_resistance(
                entity,
                resistances,
                feature_id="species.tiefling.fire_resistance",
                damage_type=DamageType.FIRE,
                name="Tiefling fire resistance",
            )
        if resolved.species is Species.DRAGONBORN:
            ancestry_name = resolved.choice("species.dragonborn.draconic_ancestry")[0]
            ancestry = DRAGONBORN_ANCESTRY_DEFINITIONS[ancestry_name]
            _add_resistance(
                entity,
                resistances,
                feature_id="species.dragonborn.ancestry_resistance",
                damage_type=ancestry.damage_type,
                name=f"{ancestry_name.title()} Draconic Ancestry",
            )
            action = DragonbornBreathWeapon(
                uuid=_source(entity, "species.dragonborn.breath_weapon.action"),
                source_entity_uuid=entity.uuid,
                ancestry=ancestry_name,
                damage_type=ancestry.damage_type,
                breath_geometry=ancestry.geometry,
                save_ability=ancestry.save_ability,
                character_level=character_level,
                aoe_shape=(
                    Line(
                        source_entity_uuid=entity.uuid,
                        target=(1, 0),
                        length_feet=30,
                        width_feet=5,
                    )
                    if ancestry.geometry == "line"
                    else Cone(
                        source_entity_uuid=entity.uuid,
                        target=(1, 0),
                        length_feet=15,
                    )
                ),
                template=True,
                semantic_key="action.origin.dragonborn.breath_weapon",
                behavior_binding=_binding(
                    entity,
                    behavior_id="action.origin.dragonborn.breath_weapon",
                    provided_by_id="species.dragonborn.breath_weapon",
                    origin_root_id=Species.DRAGONBORN.value,
                ),
            )
            resource_id = _source(entity, "species.dragonborn.breath_weapon")
            entity.action_economy.add_resource_contribution(
                DRAGONBORN_BREATH_RESOURCE,
                resource_id,
                maximum=1,
                recharge_type=RechargeType.SHORT_REST,
                capacity_policy=ResourceCapacityPolicy.MAXIMUM,
            )
            resources.append((DRAGONBORN_BREATH_RESOURCE, resource_id))
            try:
                entity.register_action(action)
            except BaseException:
                action.remove_from_register()
                raise
            actions.append(action.uuid)

        if resolved.species_variant is SpeciesVariant.HILL_DWARF:
            modifier_id = _source(
                entity,
                "species_variant.hill_dwarf.dwarven_toughness",
            )
            modifier = NumericalModifier(
                uuid=modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Dwarven Toughness",
                value=character_level,
            )
            entity.health.max_hit_points_bonus.self_static.add_value_modifier(modifier)
            maximum_hp_modifiers.append(modifier_id)

        _install_base_innate_spells(
            entity,
            resolved,
            character_level,
            spell_sources,
            actions,
        )
        _install_level_spells(
            entity,
            resolved.species,
            character_level,
            actions,
            darkness_root_owners,
            resources,
            learned_reactions,
        )

        receipt = OriginGrantReceipt(
            step_id=ORIGIN_STEP_ID,
            source_id=source_id,
            ability_score_modifier_ids=tuple(ability_modifiers),
            skill_proficiency_sources=tuple(skills),
            creature_proficiency_source_ids=tuple(creature_sources),
            saving_throw_advantage_modifier_ids=tuple(saving_advantages),
            damage_resistance_modifier_ids=tuple(resistances),
            melee_critical_extra_dice_modifier_ids=tuple(critical_modifiers),
            maximum_hit_point_modifier_ids=tuple(maximum_hp_modifiers),
            walking_speed_modifier_ids=tuple(speed_modifiers),
            action_uuids=tuple(actions),
            darkness_root_owner_action_uuids=tuple(darkness_root_owners),
            handler_uuids=tuple(handlers),
            resource_contributions=tuple(resources),
            sense_source_ids=tuple(senses),
            size_source_ids=tuple(sizes),
            capability_sources=tuple(capabilities),
            feature_sources=tuple(features),
            spell_source_ids=tuple(spell_sources),
            learned_reaction_spell_sources=tuple(learned_reactions),
        )
        entity.store_character_grant_receipt(receipt)
        return receipt
    except BaseException:
        partial_receipt = OriginGrantReceipt(
            step_id=ORIGIN_STEP_ID,
            source_id=source_id,
            ability_score_modifier_ids=tuple(ability_modifiers),
            skill_proficiency_sources=tuple(skills),
            creature_proficiency_source_ids=tuple(creature_sources),
            saving_throw_advantage_modifier_ids=tuple(saving_advantages),
            damage_resistance_modifier_ids=tuple(resistances),
            melee_critical_extra_dice_modifier_ids=tuple(critical_modifiers),
            maximum_hit_point_modifier_ids=tuple(maximum_hp_modifiers),
            walking_speed_modifier_ids=tuple(speed_modifiers),
            action_uuids=tuple(actions),
            darkness_root_owner_action_uuids=tuple(darkness_root_owners),
            handler_uuids=tuple(handlers),
            resource_contributions=tuple(resources),
            sense_source_ids=tuple(senses),
            size_source_ids=tuple(sizes),
            capability_sources=tuple(capabilities),
            feature_sources=tuple(features),
            spell_source_ids=tuple(spell_sources),
            learned_reaction_spell_sources=tuple(learned_reactions),
        )
        _remove_origin_receipt(entity, partial_receipt)
        if state_installed:
            entity.applied_origin_state = None
        if identity_installed:
            entity.clear_character_origin_identity()
        raise


def _origin_creature_source_is_owned(entity: Entity, source_id: UUID) -> bool:
    owner = entity.creature_proficiencies
    return any(
        source_id in sources.sources
        for sources in (
            owner.shield_sources,
            *owner.weapon_sources.values(),
            *owner.specific_weapon_sources.values(),
            *owner.armor_sources.values(),
            *owner.language_sources.values(),
            *owner.tool_sources.values(),
        )
    )


def _validate_origin_receipt_ownership(
    entity: Entity,
    receipt: OriginGrantReceipt,
) -> None:
    """Fail before mutation when one origin handle changed owner."""
    actions = {action.uuid: action for action in entity.registered_actions}
    for action_uuid in receipt.action_uuids:
        if action_uuid not in actions:
            raise RuntimeError("origin action template is missing")
    for action_uuid in receipt.darkness_root_owner_action_uuids:
        action = actions.get(action_uuid)
        if action is None:
            raise RuntimeError("Tiefling Darkness root owner is missing")
        binding = action.behavior_binding
        if binding != _binding(
            entity,
            behavior_id="spell.darkness",
            provided_by_id="species.tiefling.infernal_legacy",
            origin_root_id=Species.TIEFLING.value,
        ):
            raise RuntimeError("Tiefling Darkness root ownership changed")
        _ = cast(Darkness, action).active_concentration_slot_uuid
    queue_handlers = {
        handler.uuid: handler
        for handler in EventQueue.get_handlers_by_source_entity(entity.uuid)
    }
    for handler_uuid in receipt.handler_uuids:
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None or queue_handlers.get(handler_uuid) is not handler:
            raise RuntimeError("origin event handler ownership changed")
    for spell_id, source_id, handler_uuid in receipt.learned_reaction_spell_sources:
        ownership = entity.spellcasting.learned_reaction_spell_handlers.get(spell_id)
        if (
            ownership is None
            or ownership.handler_uuid != handler_uuid
            or source_id not in ownership.sources
        ):
            raise RuntimeError("origin reaction-spell ownership changed")
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None or queue_handlers.get(handler_uuid) is not handler:
            raise RuntimeError("origin reaction handler ownership changed")
    for resource_name, source_id in receipt.resource_contributions:
        resource = entity.action_economy.resources.get(resource_name)
        if resource is None or str(source_id) not in resource.capacity_contributions:
            raise RuntimeError("origin resource contribution ownership changed")
    for source_id in receipt.spell_source_ids:
        if source_id not in entity.spellcasting.sources:
            raise RuntimeError("origin spell source ownership changed")
    for feature_id, source_id in receipt.feature_sources:
        if source_id not in entity.feature_sources.get(feature_id, set()):
            raise RuntimeError("origin feature source ownership changed")
    for capability, source_id in receipt.capability_sources:
        if source_id not in entity.origin_capability_sources.get(capability, set()):
            raise RuntimeError("origin capability ownership changed")
    for source_id in receipt.size_source_ids:
        if source_id not in entity.structural_size_sources:
            raise RuntimeError("origin size ownership changed")
    for source_id in receipt.sense_source_ids:
        if source_id not in entity.senses.sense_mode_sources:
            raise RuntimeError("origin sense ownership changed")

    numerical_owners = (
        (entity.action_economy.movement.self_static.value_modifiers,
         receipt.walking_speed_modifier_ids),
        (entity.health.max_hit_points_bonus.self_static.value_modifiers,
         receipt.maximum_hit_point_modifier_ids),
        (entity.equipment.crit_extra_dice_melee.self_static.value_modifiers,
         receipt.melee_critical_extra_dice_modifier_ids),
    )
    for modifiers, modifier_ids in numerical_owners:
        for modifier_id in modifier_ids:
            modifier = modifiers.get(modifier_id)
            if modifier is None or NumericalModifier.get(modifier_id) is not modifier:
                raise RuntimeError("origin numerical modifier ownership changed")
    for ability, modifier_id in receipt.ability_score_modifier_ids:
        modifiers = entity.ability_scores.get_ability(
            ability,
        ).ability_score.self_static.value_modifiers
        modifier = modifiers.get(modifier_id)
        if modifier is None or NumericalModifier.get(modifier_id) is not modifier:
            raise RuntimeError("origin ability modifier ownership changed")
    for ability, modifier_id in receipt.saving_throw_advantage_modifier_ids:
        modifiers = entity.saving_throws.get_saving_throw(
            ability,
        ).bonus.self_contextual.advantage_modifiers
        modifier = modifiers.get(modifier_id)
        if (
            modifier is None
            or ContextualAdvantageModifier.get(modifier_id) is not modifier
        ):
            raise RuntimeError("origin save modifier ownership changed")
    for _damage_type, modifier_id in receipt.damage_resistance_modifier_ids:
        modifiers = entity.health.damage_reduction.self_static.resistance_modifiers
        modifier = modifiers.get(modifier_id)
        if modifier is None or ResistanceModifier.get(modifier_id) is not modifier:
            raise RuntimeError("origin resistance modifier ownership changed")
    for source_id in receipt.creature_proficiency_source_ids:
        if not _origin_creature_source_is_owned(entity, source_id):
            raise RuntimeError("origin creature proficiency ownership changed")
    for skill, source_id in receipt.skill_proficiency_sources:
        if source_id not in entity.skill_set.get_skill(
            skill,
        ).proficiency_sources.sources:
            raise RuntimeError("origin skill source ownership changed")


def _remove_origin_receipt(entity: Entity, receipt: OriginGrantReceipt) -> None:
    _validate_origin_receipt_ownership(entity, receipt)
    for spell_id, source_id, handler_uuid in reversed(
        receipt.learned_reaction_spell_sources,
    ):
        remove_handler = entity.spellcasting.remove_learned_reaction_spell_source(
            spell_id=spell_id,
            source_id=source_id,
            handler_uuid=handler_uuid,
        )
        if remove_handler:
            handler = entity.event_handlers.get(handler_uuid)
            if handler is None:
                raise RuntimeError("learned reaction handler is missing")
            entity.remove_event_handler(handler)
            handler.remove_from_register()
    for action_uuid in reversed(receipt.action_uuids):
        if not entity.unregister_action_by_uuid(action_uuid):
            raise RuntimeError("origin action template is missing")
    for handler_uuid in reversed(receipt.handler_uuids):
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None:
            raise RuntimeError("origin event handler is missing")
        entity.remove_event_handler(handler)
        handler.remove_from_register()
    for resource_name, contribution_id in reversed(receipt.resource_contributions):
        if not entity.action_economy.remove_resource_contribution(
            resource_name,
            contribution_id,
        ):
            raise RuntimeError("origin resource contribution is missing")
    for source_id in reversed(receipt.spell_source_ids):
        if not entity.spellcasting.remove_source(source_id):
            raise RuntimeError("origin spell source is missing")
    for feature_id, feature_source in reversed(receipt.feature_sources):
        if not entity.remove_feature_source(feature_id, feature_source):
            raise RuntimeError("origin feature source is missing")
    for capability, capability_source in reversed(receipt.capability_sources):
        if not entity.remove_origin_capability_source(capability, capability_source):
            raise RuntimeError("origin capability source is missing")
    for size_source in reversed(receipt.size_source_ids):
        if not entity.remove_structural_size_source(size_source):
            raise RuntimeError("origin size source is missing")
    for sense_source in reversed(receipt.sense_source_ids):
        if not entity.senses.remove_sense_mode_source(sense_source):
            raise RuntimeError("origin sense source is missing")
    for modifier_id in reversed(receipt.walking_speed_modifier_ids):
        entity.action_economy.movement.self_static.remove_value_modifier(modifier_id)
        NumericalModifier.unregister(modifier_id)
    for modifier_id in reversed(receipt.maximum_hit_point_modifier_ids):
        entity.health.max_hit_points_bonus.self_static.remove_value_modifier(modifier_id)
        NumericalModifier.unregister(modifier_id)
    for modifier_id in reversed(receipt.melee_critical_extra_dice_modifier_ids):
        entity.equipment.crit_extra_dice_melee.self_static.remove_value_modifier(
            modifier_id,
        )
        NumericalModifier.unregister(modifier_id)
    for _, modifier_id in reversed(receipt.damage_resistance_modifier_ids):
        entity.health.damage_reduction.self_static.remove_resistance_modifier(modifier_id)
        ResistanceModifier.unregister(modifier_id)
    for ability, modifier_id in reversed(
        receipt.saving_throw_advantage_modifier_ids,
    ):
        entity.saving_throws.get_saving_throw(
            ability,
        ).bonus.self_contextual.remove_advantage_modifier(modifier_id)
        ContextualAdvantageModifier.unregister(modifier_id)
    for creature_source in reversed(receipt.creature_proficiency_source_ids):
        if not entity.creature_proficiencies.remove_source(creature_source):
            raise RuntimeError("origin creature proficiency source is missing")
    for skill, skill_source in reversed(receipt.skill_proficiency_sources):
        if not entity.skill_set.get_skill(skill).remove_proficiency_source(
            skill_source,
        ):
            raise RuntimeError("origin skill source is missing")
    for ability, modifier_id in reversed(receipt.ability_score_modifier_ids):
        entity.ability_scores.get_ability(
            ability,
        ).ability_score.self_static.remove_value_modifier(modifier_id)
        NumericalModifier.unregister(modifier_id)


def _drop_darkness_concentration(
    entity: Entity,
    receipt: OriginGrantReceipt,
    parent_event: Event | None,
) -> None:
    if not receipt.darkness_root_owner_action_uuids:
        return
    if len(receipt.darkness_root_owner_action_uuids) != 1:
        raise RuntimeError("Tiefling Darkness must have exactly one root owner")
    darkness_uuid = receipt.darkness_root_owner_action_uuids[0]
    darkness = cast(
        Darkness,
        next(
            (
                action
                for action in entity.registered_actions
                if action.uuid == darkness_uuid
            ),
            None,
        ),
    )
    if darkness is None:
        raise RuntimeError("Tiefling Darkness root owner is missing")
    if darkness.active_concentration_slot_uuid is None:
        return
    condition = entity.active_conditions.get("Concentrating")
    if condition is None:
        darkness.active_concentration_slot_uuid = None
        return
    concentrating = cast(Concentrating, condition)
    slot_uuid = darkness.active_concentration_slot_uuid
    if slot_uuid not in concentrating.concentration_slots:
        darkness.active_concentration_slot_uuid = None
        return
    if not concentrating.drop_slot(slot_uuid, parent_event=parent_event):
        raise RuntimeError("active Tiefling Darkness could not be removed")
    darkness.active_concentration_slot_uuid = None


def remove_origin(entity: Entity, *, parent_event: Event | None = None) -> None:
    """Remove the exact installed origin without scanning other entities."""
    receipt = entity.character_grant_receipt(ORIGIN_STEP_ID)
    if not isinstance(receipt, OriginGrantReceipt):
        raise TypeError("origin step owns a non-origin receipt")
    _validate_origin_receipt_ownership(entity, receipt)
    _drop_darkness_concentration(entity, receipt, parent_event)
    _remove_origin_receipt(entity, receipt)
    entity.remove_character_grant_receipt(ORIGIN_STEP_ID)
    entity.applied_origin_state = None
    entity.clear_character_origin_identity()


def reconcile_origin_total_level(
    entity: Entity,
    *,
    previous_level: int,
    new_level: int,
    parent_event: Event | None = None,
) -> OriginGrantReceipt:
    """Reconcile only origin mechanics whose values depend on total level."""
    if not 1 <= previous_level <= 20 or not 1 <= new_level <= 20:
        raise ValueError("origin character level must be between 1 and 20")
    receipt = entity.character_grant_receipt(ORIGIN_STEP_ID)
    if not isinstance(receipt, OriginGrantReceipt):
        raise TypeError("origin step owns a non-origin receipt")
    _validate_origin_receipt_ownership(entity, receipt)

    for modifier_id in receipt.maximum_hit_point_modifier_ids:
        modifier = entity.health.max_hit_points_bonus.self_static.value_modifiers.get(
            modifier_id,
        )
        if modifier is None:
            raise RuntimeError("Dwarven Toughness modifier is missing")
        modifier.value = new_level
    for action in entity.registered_actions:
        if action.uuid not in receipt.action_uuids or action.behavior_binding is None:
            continue
        if action.behavior_binding.behavior_id == "action.origin.dragonborn.breath_weapon":
            action.character_level = new_level
        elif action.behavior_binding.behavior_id in {
            "spell.fire_bolt",
            "spell.thaumaturgy",
            "spell.darkness",
        }:
            action.caster_level = new_level

    for source_id in receipt.spell_source_ids:
        source = entity.spellcasting.sources[source_id]
        entity.spellcasting.remove_source(source_id)
        entity.spellcasting.add_innate_source(
            source_id,
            source.ability,
            provider_id=source.provider_id,
            provider_level=new_level,
            maximum_spell_rank=source.maximum_spell_rank,
        )

    actions = list(receipt.action_uuids)
    darkness_root_owners = list(receipt.darkness_root_owner_action_uuids)
    handlers = list(receipt.handler_uuids)
    resources = list(receipt.resource_contributions)
    learned = list(receipt.learned_reaction_spell_sources)
    species = entity.character_species
    if species is None:
        raise RuntimeError("origin semantic state is incomplete")
    if species is Species.TIEFLING:
        if previous_level < 3 <= new_level:
            _install_level_spells(
                entity,
                species,
                new_level,
                actions,
                darkness_root_owners,
                resources,
                learned,
                install_rebuke=True,
                install_darkness=False,
            )
        if previous_level < 5 <= new_level:
            _install_level_spells(
                entity,
                species,
                new_level,
                actions,
                darkness_root_owners,
                resources,
                learned,
                install_rebuke=False,
                install_darkness=True,
            )
        if new_level < 5 <= previous_level:
            _drop_darkness_concentration(entity, receipt, parent_event)
            if len(darkness_root_owners) != 1:
                raise RuntimeError("Tiefling Darkness root receipt is inconsistent")
            darkness_uuid = darkness_root_owners.pop()
            if not entity.unregister_action_by_uuid(darkness_uuid):
                raise RuntimeError("Tiefling Darkness root owner is missing")
            actions.remove(darkness_uuid)
            darkness_grant = _source(entity, "species.tiefling.infernal_legacy.darkness")
            entity.action_economy.remove_resource_contribution(
                _TIEFLING_DARKNESS_RESOURCE,
                darkness_grant,
            )
            resources.remove((_TIEFLING_DARKNESS_RESOURCE, darkness_grant))
        if new_level < 3 <= previous_level:
            for spell_id, learned_source, handler_uuid in tuple(learned):
                if spell_id != "spell.hellish_rebuke":
                    continue
                remove_handler = entity.spellcasting.remove_learned_reaction_spell_source(
                    spell_id=spell_id,
                    source_id=learned_source,
                    handler_uuid=handler_uuid,
                )
                if remove_handler:
                    handler = entity.event_handlers.get(handler_uuid)
                    if handler is None:
                        raise RuntimeError("learned reaction handler is missing")
                    entity.remove_event_handler(handler)
                    handler.remove_from_register()
                learned.remove((spell_id, learned_source, handler_uuid))
            rebuke_grant = _source(entity, "species.tiefling.infernal_legacy.hellish_rebuke")
            entity.action_economy.remove_resource_contribution(
                _TIEFLING_REBUKE_RESOURCE,
                rebuke_grant,
            )
            resources.remove((_TIEFLING_REBUKE_RESOURCE, rebuke_grant))

    updated = replace(
        receipt,
        action_uuids=tuple(actions),
        darkness_root_owner_action_uuids=tuple(darkness_root_owners),
        handler_uuids=tuple(handlers),
        resource_contributions=tuple(resources),
        learned_reaction_spell_sources=tuple(learned),
    )
    entity.remove_character_grant_receipt(ORIGIN_STEP_ID)
    entity.store_character_grant_receipt(updated)
    return updated


__all__ = [
    "ORIGIN_STEP_ID",
    "apply_origin",
    "reconcile_origin_total_level",
    "remove_origin",
]
