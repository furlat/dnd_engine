"""Direct monster composition through the universal Entity transaction."""

from collections.abc import Callable
from typing import Optional
from uuid import UUID, uuid5

from dnd.actions.operations import standard_actions_transform
from dnd.actions.standard import Disengage, Hide
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.saving_throws import SavingThrowConfig, SavingThrowSetConfig
from dnd.blocks.skills import SkillConfig, SkillSetConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.item_placement import resolve_item_loadout_transforms
from dnd.content.monsters.monster_definitions import (
    MONSTER_DEFINITIONS,
    MONSTER_WARDROBE_LOADOUTS,
    MonsterDefinition,
)
from dnd.content.monsters.srd_monster_definitions import (
    SRD_CONFIGURED_WARDROBE_LOADOUTS,
    SRD_MONSTER_DEFINITIONS,
)
from dnd.core.progression import (
    full_caster_spell_slots_for_level,
    proficiency_bonus_for_level,
)
from dnd.core.modifiers import (
    ContextualAdvantageModifier,
    ContextualNumericalModifier,
    NumericalModifier,
    ResistanceModifier,
)
from dnd.core.values import ModifiableValue
from dnd.entities.creature_transforms import EntityTransform
from dnd.entities.entity import Entity, EntityConfig
from dnd.entities.entity_creation import compose_entity, create_entity
from dnd.entities.entity_progression import ResolvedLevelStep
from dnd.monsters.skeleton_abilities import MarkTargetAction
from dnd.monsters.traits import (
    MultiattackAction,
    register_aggressive,
    register_brave,
    register_brute,
    register_cunning_action,
    register_dark_devotion,
    register_dire_wolf_bite_prone_rider,
    register_divine_eminence,
    register_ghoul_claws_paralysis,
    register_keen_hearing_and_sight,
    register_keen_hearing_and_smell,
    register_leadership,
    register_martial_advantage,
    register_natural_bite,
    register_pack_tactics,
    register_parry,
    register_rampage,
    register_reckless,
    register_sneak_attack,
    register_sunlight_sensitivity,
    register_surprise_attack,
    register_undead_fortitude,
    register_wolf_bite_prone_rider,
)
from dnd.monsters.circus_fighter_traits import (
    dual_wielder_ac_bonus,
    elemental_weapon_advantage,
)
from dnd.actions.reactions import create_opportunity_attack_handler
from dnd.spells.spell_builders import (
    REACTION_HANDLER_FACTORIES_BY_SPELL_ID,
    SPELL_ACTION_TYPES_BY_ID,
)
from dnd.types.abilities import AbilityName
from dnd.types.damage import DamageType, ResistanceStatus
from dnd.types.senses import SenseMode, SensesType


Undo = Callable[[], None]


_TRAIT_INSTALLERS: dict[str, Callable[[Entity], None]] = {
    "trait.srd.aggressive": register_aggressive,
    "trait.srd.brave": register_brave,
    "trait.srd.brute": register_brute,
    "trait.srd.cunning_action": register_cunning_action,
    "trait.srd.dark_devotion": register_dark_devotion,
    "trait.srd.dire_wolf_bite_prone_rider": (
        register_dire_wolf_bite_prone_rider
    ),
    "trait.srd.divine_eminence": register_divine_eminence,
    "trait.srd.ghoul_claws_paralysis": register_ghoul_claws_paralysis,
    "trait.srd.keen_hearing_and_sight": register_keen_hearing_and_sight,
    "trait.srd.keen_hearing_and_smell": register_keen_hearing_and_smell,
    "trait.srd.leadership": register_leadership,
    "trait.srd.martial_advantage": register_martial_advantage,
    "trait.srd.natural_bite": register_natural_bite,
    "trait.srd.pack_tactics": register_pack_tactics,
    "trait.srd.parry": register_parry,
    "trait.srd.rampage": register_rampage,
    "trait.srd.reckless": register_reckless,
    "trait.srd.sneak_attack": register_sneak_attack,
    "trait.srd.sunlight_sensitivity": register_sunlight_sensitivity,
    "trait.srd.surprise_attack": register_surprise_attack,
    "trait.srd.undead_fortitude": register_undead_fortitude,
    "trait.srd.wolf_bite_prone_rider": register_wolf_bite_prone_rider,
}


def _senses_transform(
    definition: MonsterDefinition,
    *,
    darkvision: Optional[bool],
) -> EntityTransform:
    def apply(entity: Entity) -> Undo:
        added: list[SenseMode] = []
        for sense in definition.senses:
            if darkvision is False and sense.sense_type is SensesType.DARKVISION:
                continue
            mode = SenseMode(
                sense_type=sense.sense_type,
                range_feet=sense.range_feet,
            )
            entity.senses.sense_modes.append(mode)
            added.append(mode)
        if darkvision is True and not any(
            mode.sense_type is SensesType.DARKVISION
            for mode in added
        ):
            mode = SenseMode(
                sense_type=SensesType.DARKVISION,
                range_feet=60,
            )
            entity.senses.sense_modes.append(mode)
            added.append(mode)

        def undo() -> None:
            for mode in reversed(added):
                entity.senses.sense_modes.remove(mode)

        return undo

    return EntityTransform(f"{definition.monster_id}.senses", apply)


def _condition_immunity_transform(
    definition: MonsterDefinition,
) -> EntityTransform:
    def apply(entity: Entity) -> Undo:
        source_name = definition.monster_id
        for condition_id in definition.condition_immunities:
            entity.add_condition_immunity(condition_id, immunity_name=source_name)

        def undo() -> None:
            for condition_id in reversed(definition.condition_immunities):
                entity._remove_static_condition_immunity(
                    condition_id,
                    source_name,
                )

        return undo

    return EntityTransform(f"{definition.monster_id}.condition_immunities", apply)


def _feature_source(entity: Entity, feature_id: str) -> UUID:
    return uuid5(entity.uuid, f"monster-feature:{feature_id}")


def _intrinsic_actions_transform(
    definition: MonsterDefinition,
) -> EntityTransform:
    def apply(entity: Entity) -> Undo:
        actions = []
        features: list[tuple[str, UUID]] = []
        try:
            for feature_id in definition.intrinsic_action_ids:
                source_id = _feature_source(entity, feature_id)
                if feature_id == "trait.goblin.nimble_escape":
                    new_actions = (
                        Hide(
                            source_entity_uuid=entity.uuid,
                            template=True,
                            name="Nimble Escape: Hide",
                            description="Take the Hide action as a bonus action.",
                            alt_cost_type="bonus_actions",
                            semantic_key="action.goblin.nimble_escape.hide",
                            behavior_id="action.goblin.nimble_escape.hide",
                        ),
                        Disengage(
                            source_entity_uuid=entity.uuid,
                            template=True,
                            name="Nimble Escape: Disengage",
                            description="Take the Disengage action as a bonus action.",
                            alt_cost_type="bonus_actions",
                            semantic_key="action.goblin.nimble_escape.disengage",
                            behavior_id="action.goblin.nimble_escape.disengage",
                        ),
                    )
                elif feature_id == "trait.skeleton.mark_target":
                    new_actions = (
                        MarkTargetAction(
                            source_entity_uuid=entity.uuid,
                            template=True,
                            semantic_key="action.skeleton.mark_target",
                            behavior_id="action.skeleton.mark_target",
                        ),
                    )
                else:
                    raise KeyError(f"unknown monster intrinsic action {feature_id!r}")
                for action in new_actions:
                    action.provided_by_id = feature_id
                    action.origin_root_id = definition.monster_id
                    entity.register_action(action)
                    actions.append(action)
                entity.add_feature_source(feature_id, source_id)
                features.append((feature_id, source_id))
        except Exception:
            for action in reversed(actions):
                entity.unregister_action_by_uuid(action.uuid)
            for feature_id, source_id in reversed(features):
                entity.remove_feature_source(feature_id, source_id)
            raise

        def undo() -> None:
            for action in reversed(actions):
                entity.unregister_action_by_uuid(action.uuid)
            for feature_id, source_id in reversed(features):
                entity.remove_feature_source(feature_id, source_id)

        return undo

    return EntityTransform(f"{definition.monster_id}.intrinsic_actions", apply)


def _spell_actions_transform(
    definition: MonsterDefinition,
    *,
    caster_level: int,
) -> EntityTransform:
    def apply(entity: Entity) -> Undo:
        actions = []
        handlers = []
        try:
            for spell_id in definition.spell_ids:
                try:
                    spell_type = SPELL_ACTION_TYPES_BY_ID[spell_id]
                except KeyError as exc:
                    raise KeyError(f"unknown monster spell {spell_id!r}") from exc
                action = spell_type(
                    source_entity_uuid=entity.uuid,
                    caster_level=caster_level,
                    template=True,
                    semantic_key=spell_id,
                    behavior_id=spell_id,
                    provided_by_id=definition.monster_id,
                    origin_root_id=definition.monster_id,
                )
                entity.register_action(action)
                actions.append(action)
            for reaction_id in definition.reaction_ids:
                spell_id = {
                    "reaction.spell.shield": "spell.shield",
                    "reaction.spell.counterspell": "spell.counterspell",
                }.get(reaction_id, reaction_id)
                try:
                    reaction_factory = (
                        REACTION_HANDLER_FACTORIES_BY_SPELL_ID[spell_id]
                    )
                except KeyError as exc:
                    raise KeyError(
                        f"unknown monster reaction {reaction_id!r}",
                    ) from exc
                handler = reaction_factory(entity.uuid)
                handler.provided_by_id = definition.monster_id
                handler.origin_root_id = definition.monster_id
                entity.add_event_handler(handler)
                handlers.append(handler)
        except Exception:
            for handler in reversed(handlers):
                entity.remove_event_handler(handler)
                handler.remove_from_register()
            for action in reversed(actions):
                entity.unregister_action_by_uuid(action.uuid)
            raise

        def undo() -> None:
            for handler in reversed(handlers):
                entity.remove_event_handler(handler)
                handler.remove_from_register()
            for action in reversed(actions):
                entity.unregister_action_by_uuid(action.uuid)

        return undo

    return EntityTransform(f"{definition.monster_id}.spell_actions", apply)


def _srd_traits_transform(definition: MonsterDefinition) -> EntityTransform:
    """Install existing SRD runtime mechanics from direct semantic IDs."""

    def apply(entity: Entity) -> Undo:
        before_actions = {action.uuid for action in entity.registered_actions}
        before_handlers = set(entity.event_handlers)
        before_conditions = set(entity.active_conditions_by_uuid)
        feature_sources: list[tuple[str, UUID]] = []
        try:
            for trait_id in definition.trait_ids:
                try:
                    installer = _TRAIT_INSTALLERS[trait_id]
                except KeyError as exc:
                    raise KeyError(f"unknown monster trait {trait_id!r}") from exc
                installer(entity)
                source_id = _feature_source(entity, trait_id)
                entity.add_feature_source(trait_id, source_id)
                feature_sources.append((trait_id, source_id))
        except Exception:
            for trait_id, source_id in reversed(feature_sources):
                entity.remove_feature_source(trait_id, source_id)
            raise

        action_uuids = tuple(
            action.uuid
            for action in entity.registered_actions
            if action.uuid not in before_actions
        )
        handlers = tuple(
            handler
            for handler_uuid, handler in entity.event_handlers.items()
            if handler_uuid not in before_handlers
        )
        conditions = tuple(
            condition
            for condition_uuid, condition in entity.active_conditions_by_uuid.items()
            if condition_uuid not in before_conditions
        )

        def undo() -> None:
            for trait_id, source_id in reversed(feature_sources):
                entity.remove_feature_source(trait_id, source_id)
            for condition in reversed(conditions):
                if condition.uuid not in entity.active_conditions_by_uuid:
                    continue
                entity._discard_condition_indexes(condition)
                entity._discard_uncommitted_condition_tree(condition)
            live_action_uuids = {
                action.uuid for action in entity.registered_actions
            }
            for action_uuid in reversed(action_uuids):
                if action_uuid in live_action_uuids:
                    entity.unregister_action_by_uuid(action_uuid)
            for handler in reversed(handlers):
                if handler.uuid in entity.event_handlers:
                    entity.remove_event_handler(handler)
                    handler.remove_from_register()

        return undo

    return EntityTransform(f"{definition.monster_id}.srd_traits", apply)


def _multiattacks_transform(definition: MonsterDefinition) -> EntityTransform:
    """Install cold stat-block attack sequences without content declarations."""

    def apply(entity: Entity) -> Undo:
        actions = []
        try:
            for row in definition.multiattacks:
                action = MultiattackAction(
                    source_entity_uuid=entity.uuid,
                    template=True,
                    name=row.name,
                    attack_sequence=row.attacks,
                    semantic_key=row.action_id,
                    behavior_id=row.action_id,
                    provided_by_id=definition.monster_id,
                    origin_root_id=definition.monster_id,
                )
                entity.register_action(action)
                actions.append(action)
        except Exception:
            for action in reversed(actions):
                entity.unregister_action_by_uuid(action.uuid)
            raise

        def undo() -> None:
            for action in reversed(actions):
                entity.unregister_action_by_uuid(action.uuid)

        return undo

    return EntityTransform(f"{definition.monster_id}.multiattacks", apply)


def _circus_traits_transform(definition: MonsterDefinition) -> EntityTransform:
    """Install the Circus Fighter's intrinsic mechanics without conditions."""
    if definition.monster_id != "monster.circus_fighter":
        raise ValueError("circus traits require the Circus Fighter definition")

    def apply(entity: Entity) -> Undo:
        installed: list[tuple[ModifiableValue, object]] = []
        feature_sources: list[tuple[str, UUID]] = []
        handler = None

        def add_static(value: ModifiableValue, name: str, amount: int) -> None:
            modifier = NumericalModifier(
                name=name,
                value=amount,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
            )
            value.self_static.add_value_modifier(modifier)
            installed.append((value, modifier))

        try:
            dual_wielder = ContextualNumericalModifier(
                name="Dual Wielder",
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                callable=dual_wielder_ac_bonus,
            )
            entity.equipment.ac_bonus.self_contextual.add_value_modifier(
                dual_wielder,
            )
            installed.append((entity.equipment.ac_bonus, dual_wielder))

            elemental_mastery = ContextualAdvantageModifier(
                name="Elemental Weapon",
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                callable=elemental_weapon_advantage,
            )
            entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(
                elemental_mastery,
            )
            installed.append((entity.equipment.attack_bonus, elemental_mastery))

            for damage_type, status in (
                (DamageType.FIRE, ResistanceStatus.RESISTANCE),
                (DamageType.COLD, ResistanceStatus.VULNERABILITY),
            ):
                affinity = ResistanceModifier(
                    name="Elemental Affinity",
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    damage_type=damage_type,
                    value=status,
                )
                entity.health.damage_reduction.self_static.add_resistance_modifier(
                    affinity,
                )
                installed.append((entity.health.damage_reduction, affinity))

            add_static(
                entity.skill_set.acrobatics.skill_bonus,
                "Circus Training",
                7,
            )
            add_static(entity.skill_set.history.skill_bonus, "Circus Training", -2)
            add_static(
                entity.saving_throws.strength_saving_throw.bonus,
                "Circus Training",
                1,
            )
            add_static(
                entity.saving_throws.intelligence_saving_throw.bonus,
                "Circus Training",
                -1,
            )
            add_static(entity.action_economy.reactions, "Circus Training", 2)
            add_static(entity.action_economy.actions, "Circus Training", 99)
            add_static(entity.action_economy.movement, "Circus Training", -5)
            add_static(entity.equipment.ac_bonus, "Circus Training", 1)
            add_static(
                entity.equipment.unarmed_damage_bonus,
                "Circus Training",
                1,
            )
            add_static(entity.proficiency_bonus, "Circus Training", -1)

            for feature_id in definition.intrinsic_feature_ids:
                source_id = _feature_source(entity, feature_id)
                entity.add_feature_source(feature_id, source_id)
                feature_sources.append((feature_id, source_id))

            handler = create_opportunity_attack_handler(entity.uuid)
            handler.provided_by_id = definition.monster_id
            handler.origin_root_id = definition.monster_id
            entity.add_event_handler(handler)
        except Exception:
            if handler is not None:
                entity.remove_event_handler(handler)
                handler.remove_from_register()
            for feature_id, source_id in reversed(feature_sources):
                entity.remove_feature_source(feature_id, source_id)
            for value, modifier in reversed(installed):
                value.remove_modifier(modifier.uuid)
                modifier.remove_from_register()
            raise

        def undo() -> None:
            assert handler is not None
            entity.remove_event_handler(handler)
            handler.remove_from_register()
            for feature_id, source_id in reversed(feature_sources):
                entity.remove_feature_source(feature_id, source_id)
            for value, modifier in reversed(installed):
                value.remove_modifier(modifier.uuid)
                modifier.remove_from_register()

        return undo

    return EntityTransform(f"{definition.monster_id}.intrinsic_traits", apply)


def _entity_config(
    definition: MonsterDefinition,
    *,
    faction: Optional[str],
    caster_level: int,
    weight: Optional[int],
) -> EntityConfig:
    abilities = {
        ability.value: AbilityConfig(
            ability_score=score,
            modifier_bonus=dict(definition.ability_modifier_bonuses).get(
                ability,
                0,
            ),
        )
        for ability, score in definition.abilities
    }
    skills = {
        training.skill.value: SkillConfig(
            proficiency=True,
            expertise=training.expertise,
        )
        for training in definition.skills
    }
    saving_throws = {
        f"{ability.value}_saving_throw": SavingThrowConfig(proficiency=True)
        for ability in definition.saving_throw_proficiencies
    }
    hit_dice = tuple(
        HitDiceConfig(
            hit_dice_value=row.die,
            hit_dice_count=(
                caster_level
                if definition.uses_full_caster_slots
                else row.count
            ),
            mode=row.mode,
            ignore_first_level=row.ignore_first_level,
        )
        for row in definition.hit_dice
    )
    spell_slots = (
        full_caster_spell_slots_for_level(caster_level)
        if definition.uses_full_caster_slots
        else dict(definition.spell_slots)
    )
    proficiency_bonus = (
        proficiency_bonus_for_level(caster_level)
        if definition.uses_full_caster_slots
        else definition.proficiency_bonus
    )
    return EntityConfig(
        ability_scores=AbilityScoresConfig(**abilities),
        skill_set=SkillSetConfig(**skills),
        health=HealthConfig(
            hit_dices=list(hit_dice),
            damage_reduction=definition.damage_reduction,
            temporary_hit_points=definition.temporary_hit_points,
            vulnerabilities=list(definition.damage_vulnerabilities),
            immunities=list(definition.damage_immunities),
        ),
        saving_throws=SavingThrowSetConfig(**saving_throws),
        equipment=EquipmentConfig(
            unarmed_damage_type=definition.unarmed_damage_type,
        ),
        action_economy=ActionEconomyConfig(
            movement=definition.movement_feet,
            spell_slots=spell_slots,
        ),
        spellcasting=(
            SpellcastingConfig(
                spellcasting_ability=definition.spellcasting_ability,
            )
            if definition.spellcasting_ability is not None
            else None
        ),
        proficiency_bonus=proficiency_bonus,
        faction=faction,
        appearance=AppearanceConfig(
            semantic_properties=dict(definition.body_semantics),
        ),
        weight=definition.weight if weight is None else weight,
        creature_type=definition.creature_type,
        size=definition.size,
    )


def create_monster(
    monster_id: str,
    entity_uuid: UUID,
    *,
    name: Optional[str] = None,
    faction: Optional[str] = None,
    include_default_possessions: bool = True,
    caster_level: int = 5,
    darkvision: Optional[bool] = None,
    weight: Optional[int] = None,
    wardrobe: Optional[str] = None,
    initial_levels: tuple[ResolvedLevelStep, ...] = (),
    additional_transforms: tuple[EntityTransform, ...] = (),
) -> Entity:
    """Create one committed undeployed monster from direct authored facts."""
    try:
        definition = (
            MONSTER_DEFINITIONS.get(monster_id)
            or SRD_MONSTER_DEFINITIONS[monster_id]
        )
    except KeyError as exc:
        raise KeyError(f"unknown monster {monster_id!r}") from exc
    if not 1 <= caster_level <= 20:
        raise ValueError("caster_level must be between 1 and 20")
    if definition.monster_id == "monster.generic_caster":
        wardrobe_key = f"{definition.monster_id}.{wardrobe or 'arcane'}"
        wardrobe_loadouts = MONSTER_WARDROBE_LOADOUTS
    elif definition.monster_id in SRD_MONSTER_DEFINITIONS:
        if wardrobe is None:
            wardrobe_key = None
        elif wardrobe == "configured":
            wardrobe_key = f"{definition.monster_id}.configured"
        else:
            raise ValueError(
                f"unknown {monster_id} wardrobe {wardrobe!r}",
            )
        wardrobe_loadouts = SRD_CONFIGURED_WARDROBE_LOADOUTS
    elif definition.monster_id in MONSTER_WARDROBE_LOADOUTS:
        if wardrobe is not None:
            raise ValueError(f"{monster_id} has no selectable wardrobe")
        wardrobe_key = definition.monster_id
        wardrobe_loadouts = MONSTER_WARDROBE_LOADOUTS
    else:
        if wardrobe is not None:
            raise ValueError(f"{monster_id} has no selectable wardrobe")
        wardrobe_key = None
        wardrobe_loadouts = MONSTER_WARDROBE_LOADOUTS
    try:
        wardrobe_entries = (
            wardrobe_loadouts[wardrobe_key]
            if wardrobe_key is not None
            else ()
        )
    except KeyError as exc:
        raise ValueError(
            f"unknown {monster_id} wardrobe {wardrobe!r}",
        ) from exc

    entity = create_entity(
        entity_uuid,
        entity_kind_id=definition.monster_id,
        name=name or definition.name,
        description=definition.description,
        config=_entity_config(
            definition,
            faction=faction,
            caster_level=caster_level,
            weight=weight,
        ),
    )
    try:
        possession_entries = definition.intrinsic_loadout + (
            definition.default_loadout + wardrobe_entries
            if include_default_possessions
            else ()
        )
        possession_transforms = resolve_item_loadout_transforms(
            entity.uuid,
            transform_prefix=f"{definition.monster_id}.possession",
            entries=possession_entries,
        )
        transforms = [
            *possession_transforms,
            standard_actions_transform(
                f"{definition.monster_id}.standard_actions",
            ),
            _senses_transform(definition, darkvision=darkvision),
            _condition_immunity_transform(definition),
        ]
        if definition.intrinsic_action_ids:
            transforms.append(_intrinsic_actions_transform(definition))
        if definition.intrinsic_feature_ids:
            transforms.append(_circus_traits_transform(definition))
        if definition.trait_ids:
            transforms.append(_srd_traits_transform(definition))
        if definition.multiattacks:
            transforms.append(_multiattacks_transform(definition))
        if definition.spell_ids or definition.reaction_ids:
            transforms.append(_spell_actions_transform(
                definition,
                caster_level=(definition.spellcaster_level or caster_level),
            ))
        transforms.extend(additional_transforms)
        compose_entity(
            entity,
            transforms=tuple(transforms),
            initial_levels=initial_levels,
        )
    except Exception:
        if Entity.get(entity.uuid) is entity:
            entity.discard_unpublished_runtime()
        raise
    return entity


__all__ = ["create_monster"]
