"""Direct reversible class-feature transforms.

The functions here implement authored Fighter, Barbarian, and Sorcerer rules
using ordinary entity capabilities.  Stable semantic IDs are data; UUIDs are
only ephemeral ownership handles derived from an entity and an applied step.
There is no registry lookup or global content runtime.
"""

from collections.abc import Callable, Sequence
from typing import Optional
from uuid import UUID, uuid5

from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.blocks.equipment import ArmorClassFormulaCandidate
from dnd.blocks.health import HitDice, HitDiceConfig
from dnd.classes import barbarian, feats, fighter, rage, sorcerer
from dnd.core.base_actions import BaseAction
from dnd.core.events.events_registry import EventHandler, EventPhase, EventType, Trigger
from dnd.core.feature_grants import AttackMultiplicityGrant
from dnd.core.modifiers import (
    AdvantageModifier,
    ContextualAdvantageModifier,
    ContextualNumericalModifier,
    NumericalModifier,
)
from dnd.core.progression import (
    SpellcastingClassContribution,
    full_caster_spell_slots_for_level,
    maximum_spell_rank_for_contribution,
    proficiency_bonus_for_level,
)
from dnd.core.values import ModifiableValue
from dnd.entities.creature_transforms import EntityTransform
from dnd.entities.entity import Entity
from dnd.spells.spell_builders import (
    REACTION_HANDLER_FACTORIES_BY_SPELL_ID,
    SPELL_ACTION_TYPES_BY_ID,
)
from dnd.types.abilities import AbilityName, SkillName
from dnd.types.equipment import ArmorType, WeaponProperty
from dnd.types.damage import DamageType
from dnd.types.proficiency import ProficiencyMode
from dnd.types.progression import (
    AppliedClassLevel,
    CasterProgression,
    CharacterClass,
    RitualPreparationPolicy,
)
from dnd.types.rolls import AdvantageStatus


Undo = Callable[[], None]
Operation = Callable[[Entity], Undo]


def _source_id(entity: Entity, step_id: str, grant_id: str) -> UUID:
    return uuid5(entity.uuid, f"progression:{step_id}:{grant_id}")


def _feature_transform(
    level: AppliedClassLevel,
    feature_id: str,
    operation: Operation,
) -> EntityTransform:
    """Attach semantic feature state only after its mechanic installs."""

    transform_id = f"{level.step_id}:{feature_id}"

    def apply(entity: Entity) -> Undo:
        undo_operation = operation(entity)
        source_id = _source_id(entity, level.step_id, feature_id)
        try:
            entity.add_feature_source(feature_id, source_id)
        except Exception:
            undo_operation()
            raise

        def undo() -> None:
            entity.remove_feature_source(feature_id, source_id)
            undo_operation()

        return undo

    return EntityTransform(transform_id, apply)


def _no_mechanics(_entity: Entity) -> Undo:
    return lambda: None


def _static_modifier(
    level: AppliedClassLevel,
    grant_id: str,
    value_getter: Callable[[Entity], ModifiableValue],
    amount: int,
    name: str,
) -> Operation:
    def apply(entity: Entity) -> Undo:
        value = value_getter(entity)
        modifier = NumericalModifier(
            uuid=_source_id(entity, level.step_id, grant_id),
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=name,
            value=amount,
        )
        value.self_static.add_value_modifier(modifier)

        def undo() -> None:
            value.self_static.remove_value_modifier(modifier.uuid)
            modifier.remove_from_register()

        return undo

    return apply


def _contextual_modifier(
    level: AppliedClassLevel,
    grant_id: str,
    value_getter: Callable[[Entity], ModifiableValue],
    evaluator: Callable[..., Optional[NumericalModifier]],
    name: str,
) -> Operation:
    def apply(entity: Entity) -> Undo:
        value = value_getter(entity)
        modifier = ContextualNumericalModifier(
            uuid=_source_id(entity, level.step_id, grant_id),
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=name,
            callable=evaluator,
        )
        value.self_contextual.add_value_modifier(modifier)

        def undo() -> None:
            value.self_contextual.remove_value_modifier(modifier.uuid)
            modifier.remove_from_register()

        return undo

    return apply


def _actions_operation(
    level: AppliedClassLevel,
    provider_id: str,
    factories: Sequence[Callable[[UUID], BaseAction]],
    behavior_ids: Sequence[str],
) -> Operation:
    if len(factories) != len(behavior_ids):
        raise ValueError("action factories and behavior IDs must align")

    def apply(entity: Entity) -> Undo:
        actions: list[BaseAction] = []
        try:
            for factory, behavior_id in zip(factories, behavior_ids, strict=True):
                action = factory(entity.uuid)
                action.behavior_id = behavior_id
                action.provided_by_id = provider_id
                action.origin_root_id = f"class.{level.class_id.value}"
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

    return apply


def _handlers_operation(
    level: AppliedClassLevel,
    provider_id: str,
    factories: Sequence[Callable[[UUID], EventHandler]],
    behavior_ids: Sequence[str],
) -> Operation:
    if len(factories) != len(behavior_ids):
        raise ValueError("handler factories and behavior IDs must align")

    def apply(entity: Entity) -> Undo:
        handlers: list[EventHandler] = []
        try:
            for factory, behavior_id in zip(factories, behavior_ids, strict=True):
                handler = factory(entity.uuid)
                handler.behavior_id = behavior_id
                handler.provided_by_id = provider_id
                handler.origin_root_id = f"class.{level.class_id.value}"
                entity.add_event_handler(handler)
                handlers.append(handler)
        except Exception:
            for handler in reversed(handlers):
                entity.remove_event_handler(handler)
                handler.remove_from_register()
            raise

        def undo() -> None:
            for handler in reversed(handlers):
                entity.remove_event_handler(handler)
                handler.remove_from_register()

        return undo

    return apply


def _resource_operation(
    level: AppliedClassLevel,
    grant_id: str,
    name: str,
    maximum: int,
    recharge: RechargeType,
    policy: ResourceCapacityPolicy,
) -> Operation:
    def apply(entity: Entity) -> Undo:
        source_id = _source_id(entity, level.step_id, grant_id)
        entity.action_economy.add_resource_contribution(
            name,
            source_id,
            maximum=maximum,
            recharge_type=recharge,
            capacity_policy=policy,
        )
        return lambda: entity.action_economy.remove_resource_contribution(
            name,
            source_id,
        )

    return apply


def _combine(*operations: Operation) -> Operation:
    def apply(entity: Entity) -> Undo:
        undos: list[Undo] = []
        try:
            for operation in operations:
                undos.append(operation(entity))
        except Exception:
            for undo in reversed(undos):
                undo()
            raise

        def undo() -> None:
            for inverse in reversed(undos):
                inverse()

        return undo

    return apply


def _hit_die_transform(
    level: AppliedClassLevel,
    hit_die: int,
) -> EntityTransform:
    def apply(entity: Entity) -> Undo:
        hit_dice = HitDice.create(
            source_entity_uuid=entity.uuid,
            config=HitDiceConfig(
                hit_dice_value=hit_die,
                hit_dice_count=1,
                mode="average",
                ignore_first_level=bool(entity.applied_class_levels),
            ),
        )
        entity.health.add_hit_dice(hit_dice)
        return lambda: entity.health.remove_hit_dice_by_uuid(hit_dice.uuid)

    return EntityTransform(f"{level.step_id}:hit_die.d{hit_die}", apply)


def _proficiency_bonus_transform(level: AppliedClassLevel) -> EntityTransform:
    def apply(entity: Entity) -> Undo:
        base = entity.proficiency_bonus.get_base_modifier()
        if base is None:
            raise RuntimeError("proficiency bonus has no base modifier")
        previous = base.value
        base.value = proficiency_bonus_for_level(level.character_level)
        return lambda: setattr(base, "value", previous)

    return EntityTransform(f"{level.step_id}:proficiency_bonus", apply)


def _death_save_transform(level: AppliedClassLevel) -> EntityTransform:
    def apply(entity: Entity) -> Undo:
        previous = entity.uses_death_saves
        entity.uses_death_saves = True
        return lambda: setattr(entity, "uses_death_saves", previous)

    return EntityTransform(f"{level.step_id}:death_saves", apply)


def _class_proficiencies_transform(
    level: AppliedClassLevel,
    proficiencies: tuple[str, ...],
    saving_throws: tuple[AbilityName, ...],
    skills: tuple[SkillName, ...],
) -> EntityTransform:
    def apply(entity: Entity) -> Undo:
        source_id = _source_id(entity, level.step_id, "proficiencies")
        applied_skills: list[SkillName] = []
        applied_saves: list[AbilityName] = []
        try:
            for proficiency in proficiencies:
                if proficiency == "weapon.simple":
                    entity.creature_proficiencies.add_weapon_source(
                        source_id, WeaponProperty.SIMPLE,
                    )
                elif proficiency == "weapon.martial":
                    entity.creature_proficiencies.add_weapon_source(
                        source_id, WeaponProperty.MARTIAL,
                    )
                elif proficiency == "shield.shield":
                    entity.creature_proficiencies.add_shield_source(source_id)
                elif proficiency.startswith("armor."):
                    entity.creature_proficiencies.add_armor_source(
                        source_id,
                        ArmorType(proficiency.removeprefix("armor.").title()),
                    )
                elif proficiency.startswith("weapon."):
                    entity.creature_proficiencies.add_specific_weapon_source(
                        source_id, proficiency,
                    )
                else:
                    raise ValueError(f"unsupported class proficiency {proficiency}")
            for ability in saving_throws:
                entity.saving_throws.get_saving_throw(ability).add_proficiency_source(
                    source_id,
                    ProficiencyMode.FULL,
                )
                applied_saves.append(ability)
            for skill in skills:
                entity.skill_set.get_skill(skill).add_proficiency_source(
                    source_id,
                    ProficiencyMode.FULL,
                )
                applied_skills.append(skill)
        except Exception:
            for skill in reversed(applied_skills):
                entity.skill_set.get_skill(skill).remove_proficiency_source(source_id)
            for ability in reversed(applied_saves):
                entity.saving_throws.get_saving_throw(
                    ability,
                ).remove_proficiency_source(source_id)
            entity.creature_proficiencies.remove_source(source_id)
            raise

        def undo() -> None:
            for skill in reversed(applied_skills):
                entity.skill_set.get_skill(skill).remove_proficiency_source(source_id)
            for ability in reversed(applied_saves):
                entity.saving_throws.get_saving_throw(
                    ability,
                ).remove_proficiency_source(source_id)
            entity.creature_proficiencies.remove_source(source_id)

        return undo

    return EntityTransform(f"{level.step_id}:class_proficiencies", apply)


def common_level_transforms(
    level: AppliedClassLevel,
    *,
    hit_die: int,
    proficiencies: tuple[str, ...] = (),
    saving_throws: tuple[AbilityName, ...] = (),
    skills: tuple[SkillName, ...] = (),
    first_character_level: bool,
) -> tuple[EntityTransform, ...]:
    """Resolve class-neutral per-level and entry-package mechanics."""
    rows: list[EntityTransform] = [
        _hit_die_transform(level, hit_die),
        _proficiency_bonus_transform(level),
    ]
    if first_character_level:
        rows.append(_death_save_transform(level))
    if proficiencies or saving_throws or skills:
        rows.append(_class_proficiencies_transform(
            level,
            proficiencies,
            saving_throws,
            skills,
        ))
    return tuple(rows)


def _find_action(entity: Entity, behavior_id: str) -> Optional[BaseAction]:
    return next(
        (action for action in entity.registered_actions if action.behavior_id == behavior_id),
        None,
    )


def _action_field_transform(
    level: AppliedClassLevel,
    behavior_id: str,
    **updates: object,
) -> EntityTransform:
    def apply(entity: Entity) -> Undo:
        action = _find_action(entity, behavior_id)
        if action is None:
            raise RuntimeError(f"required action {behavior_id} is not installed")
        previous = {name: getattr(action, name) for name in updates}
        for name, value in updates.items():
            setattr(action, name, value)

        def undo() -> None:
            for name, value in previous.items():
                setattr(action, name, value)

        return undo

    return EntityTransform(f"{level.step_id}:{behavior_id}.reconcile", apply)


def _extra_attack_transform(
    level: AppliedClassLevel,
    attacks_per_action: int,
) -> EntityTransform:
    feature_id = "class_feature.extra_attack"

    def operation(entity: Entity) -> Undo:
        grant_id = _source_id(entity, level.step_id, feature_id)
        install_family = not entity.has_feature(feature_id)
        action: Optional[BaseAction] = None
        handler: Optional[EventHandler] = None
        entity.action_economy.add_attack_multiplicity_grant(
            AttackMultiplicityGrant(
                grant_id=grant_id,
                provider_id=feature_id,
                attacks_per_attack_action=attacks_per_action,
                acquisition_ordinal=level.character_level,
            ),
        )
        try:
            entity.action_economy.add_resource_contribution(
                "extra_attacks",
                grant_id,
                maximum=attacks_per_action - 1,
                recharge_type=RechargeType.TURN_START,
                capacity_policy=ResourceCapacityPolicy.MAXIMUM,
            )
            if install_family:
                action = fighter.ExtraAttack(
                    source_entity_uuid=entity.uuid,
                    name="Extra Attack",
                    template=True,
                    discover_equipped_weapon_slots=True,
                    behavior_id="action.feature.extra_attack",
                    provided_by_id=feature_id,
                    origin_root_id=f"class.{level.class_id.value}",
                )
                entity.register_action(action)
                handler = fighter.create_extra_attack_resource_handler(entity.uuid)
                handler.behavior_id = "handler.feature.extra_attack.resource"
                handler.provided_by_id = feature_id
                handler.origin_root_id = f"class.{level.class_id.value}"
                entity.add_event_handler(handler)
        except Exception:
            if handler is not None:
                entity.remove_event_handler(handler)
                handler.remove_from_register()
            if action is not None:
                entity.unregister_action_by_uuid(action.uuid)
            entity.action_economy.remove_resource_contribution(
                "extra_attacks", grant_id,
            )
            entity.action_economy.remove_attack_multiplicity_grant(grant_id)
            raise

        def undo() -> None:
            if handler is not None:
                entity.remove_event_handler(handler)
                handler.remove_from_register()
            if action is not None:
                entity.unregister_action_by_uuid(action.uuid)
            entity.action_economy.remove_resource_contribution(
                "extra_attacks", grant_id,
            )
            entity.action_economy.remove_attack_multiplicity_grant(grant_id)

        return undo

    return _feature_transform(level, feature_id, operation)


def _asi_transform(
    level: AppliedClassLevel,
    increases: tuple[tuple[AbilityName, int], ...],
) -> EntityTransform:
    def apply(entity: Entity) -> Undo:
        installed: list[tuple[ModifiableValue, NumericalModifier]] = []
        try:
            for ability, amount in increases:
                value = entity.ability_scores.get_ability(ability).ability_score
                if value.score + amount > 20:
                    raise ValueError(f"ASI would raise {ability.value} above 20")
                modifier = NumericalModifier(
                    uuid=_source_id(
                        entity,
                        level.step_id,
                        f"asi.{ability.value}",
                    ),
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    name=f"Level {level.character_level} ASI ({ability.value})",
                    value=amount,
                )
                value.self_static.add_value_modifier(modifier)
                installed.append((value, modifier))
        except Exception:
            for value, modifier in reversed(installed):
                value.self_static.remove_value_modifier(modifier.uuid)
                modifier.remove_from_register()
            raise

        def undo() -> None:
            for value, modifier in reversed(installed):
                value.self_static.remove_value_modifier(modifier.uuid)
                modifier.remove_from_register()

        return undo

    return EntityTransform(f"{level.step_id}:ability_score_improvement", apply)


def ability_score_improvement_transform(
    level: AppliedClassLevel,
    values: tuple[str, ...],
) -> EntityTransform:
    """Decode and install one validated +2 total ability improvement."""
    increases: list[tuple[AbilityName, int]] = []
    for value in values:
        ability_token, separator, amount_token = value.partition(":+")
        if not separator or not ability_token.startswith("ability."):
            raise ValueError(f"invalid ASI value {value!r}")
        increases.append((
            AbilityName(ability_token.removeprefix("ability.")),
            int(amount_token),
        ))
    if sum(amount for _, amount in increases) != 2:
        raise ValueError("an ability score improvement must total +2")
    if len({ability for ability, _ in increases}) != len(increases):
        raise ValueError("an ASI cannot repeat an ability")
    return _asi_transform(level, tuple(increases))


def _lucky_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "feat.lucky"

    def handler_factory(entity_uuid: UUID) -> EventHandler:
        return EventHandler(
            name="Lucky",
            source_entity_uuid=entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=event_type,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=entity_uuid,
                )
                for event_type in (
                    EventType.ATTACK_D20_ROLL_RESULT,
                    EventType.SAVE_D20_ROLL_RESULT,
                    EventType.CHECK_D20_ROLL_RESULT,
                )
            ],
            event_processor=feats.lucky_processor,
            player_toggleable=True,
        )

    operation = _combine(
        _resource_operation(
            level,
            feature_id,
            "luck_points",
            3,
            RechargeType.LONG_REST,
            ResourceCapacityPolicy.SUM,
        ),
        _handlers_operation(
            level,
            feature_id,
            (handler_factory,),
            ("handler.feat.lucky",),
        ),
    )
    return _feature_transform(level, feature_id, operation)


def feat_transform(level: AppliedClassLevel, feat_id: str) -> EntityTransform:
    if feat_id == "feat.lucky":
        return _lucky_transform(level)
    raise ValueError(f"unsupported feat {feat_id}")


def _fighting_style_transform(
    level: AppliedClassLevel,
    feature_id: str,
) -> EntityTransform:
    operations: dict[str, Operation] = {
        "class_feature.fighter.fighting_style.archery": _static_modifier(
            level,
            feature_id,
            lambda entity: entity.equipment.ranged_attack_bonus,
            2,
            "Archery",
        ),
        "class_feature.fighter.fighting_style.defense": _contextual_modifier(
            level,
            feature_id,
            lambda entity: entity.equipment.ac_bonus,
            fighter.defense_ac_check,
            "Defense",
        ),
        "class_feature.fighter.fighting_style.dueling": _contextual_modifier(
            level,
            feature_id,
            lambda entity: entity.equipment.melee_damage_bonus,
            fighter.dueling_damage_check,
            "Dueling",
        ),
        "class_feature.fighter.fighting_style.two_weapon_fighting": _combine(
            _contextual_modifier(
                level,
                f"{feature_id}.melee",
                lambda entity: entity.equipment.off_hand_melee_ability_bonus,
                fighter.twf_off_hand_melee_ability_bonus,
                "Two-Weapon Fighting",
            ),
            _contextual_modifier(
                level,
                f"{feature_id}.ranged",
                lambda entity: entity.equipment.off_hand_ranged_ability_bonus,
                fighter.twf_off_hand_ranged_ability_bonus,
                "Two-Weapon Fighting",
            ),
        ),
        "class_feature.fighter.fighting_style.great_weapon_fighting": (
            _handlers_operation(
                level,
                feature_id,
                (lambda entity_uuid: EventHandler(
                    name="Great Weapon Fighting",
                    source_entity_uuid=entity_uuid,
                    trigger_conditions=[Trigger(
                        event_type=EventType.DAMAGE_ROLL_RESULT,
                        event_phase=EventPhase.EFFECT,
                    )],
                    event_processor=fighter.great_weapon_fighting_processor,
                    player_toggleable=True,
                ),),
                ("handler.class_feature.fighter.great_weapon_fighting",),
            )
        ),
        "class_feature.fighter.fighting_style.protection": _handlers_operation(
            level,
            feature_id,
            (fighter.create_protection_handler,),
            ("reaction.class_feature.fighter.protection",),
        ),
    }
    try:
        operation = operations[feature_id]
    except KeyError as error:
        raise ValueError(f"unsupported fighting style {feature_id}") from error
    return _feature_transform(level, feature_id, operation)


def _second_wind_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.fighter.second_wind"
    operation = _combine(
        _resource_operation(
            level,
            feature_id,
            "second_wind",
            1,
            RechargeType.SHORT_REST,
            ResourceCapacityPolicy.SUM,
        ),
        _actions_operation(
            level,
            feature_id,
            (lambda entity_uuid: fighter.SecondWind(
                source_entity_uuid=entity_uuid,
                fighter_level=level.resulting_class_level,
                template=True,
            ),),
            ("action.class.fighter.second_wind",),
        ),
    )
    return _feature_transform(level, feature_id, operation)


def _action_surge_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.fighter.action_surge"
    operations: list[Operation] = [_resource_operation(
        level,
        feature_id,
        "action_surge",
        1,
        RechargeType.SHORT_REST,
        ResourceCapacityPolicy.SUM,
    )]
    if level.resulting_class_level == 2:
        operations.append(_actions_operation(
            level,
            feature_id,
            (lambda entity_uuid: fighter.ActionSurge(
                source_entity_uuid=entity_uuid,
                template=True,
            ),),
            ("action.class.fighter.action_surge",),
        ))
    return _feature_transform(level, feature_id, _combine(*operations))


def _critical_transform(
    level: AppliedClassLevel,
    feature_id: str,
    name: str,
) -> EntityTransform:
    return _feature_transform(
        level,
        feature_id,
        _combine(*(
            _static_modifier(
                level,
                f"{feature_id}.{channel}",
                getter,
                1,
                name,
            )
            for channel, getter in (
                ("melee", lambda entity: entity.equipment.crit_threshold_melee),
                ("ranged", lambda entity: entity.equipment.crit_threshold_ranged),
            )
        )),
    )


def _indomitable_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.fighter.indomitable"
    operations: list[Operation] = [_resource_operation(
        level,
        feature_id,
        "indomitable",
        1,
        RechargeType.LONG_REST,
        ResourceCapacityPolicy.SUM,
    )]
    if level.resulting_class_level == 9:
        operations.append(_handlers_operation(
            level,
            feature_id,
            (fighter.create_indomitable_handler,),
            ("handler.class_feature.fighter.indomitable",),
        ))
    return _feature_transform(level, feature_id, _combine(*operations))


def _remarkable_athlete_jump_bonus(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict[str, object]] = None,
) -> Optional[NumericalModifier]:
    del target_entity_uuid, context
    entity = Entity.get(source_entity_uuid)
    if entity is None:
        return None
    return NumericalModifier(
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=source_entity_uuid,
        name="Remarkable Athlete",
        value=entity.ability_scores.strength.modifier,
    )


def _remarkable_athlete_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.fighter.remarkable_athlete"

    def operation(entity: Entity) -> Undo:
        source_id = _source_id(entity, level.step_id, feature_id)
        abilities: list[AbilityName] = []
        modifier: Optional[ContextualNumericalModifier] = None
        try:
            for ability in (
                AbilityName.STRENGTH,
                AbilityName.DEXTERITY,
                AbilityName.CONSTITUTION,
            ):
                entity.ability_scores.get_ability(
                    ability,
                ).add_check_proficiency_source(
                    source_id,
                    ProficiencyMode.HALF_ROUND_UP,
                )
                abilities.append(ability)
            modifier = ContextualNumericalModifier(
                uuid=_source_id(entity, level.step_id, f"{feature_id}.jump"),
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Remarkable Athlete",
                callable=_remarkable_athlete_jump_bonus,
            )
            entity.jump_distance_additive.self_contextual.add_value_modifier(
                modifier,
            )
        except Exception:
            for ability in reversed(abilities):
                entity.ability_scores.get_ability(
                    ability,
                ).remove_check_proficiency_source(source_id)
            if modifier is not None:
                modifier.remove_from_register()
            raise

        def undo() -> None:
            assert modifier is not None
            entity.jump_distance_additive.self_contextual.remove_value_modifier(
                modifier.uuid,
            )
            modifier.remove_from_register()
            for ability in reversed(abilities):
                entity.ability_scores.get_ability(
                    ability,
                ).remove_check_proficiency_source(source_id)

        return undo

    return _feature_transform(level, feature_id, operation)


def _survivor_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.fighter.survivor"
    return _feature_transform(
        level,
        feature_id,
        _handlers_operation(
            level,
            feature_id,
            (fighter.create_survivor_handler,),
            ("handler.class_feature.fighter.survivor",),
        ),
    )


def fighter_feature_transform(
    level: AppliedClassLevel,
    feature_id: str,
) -> EntityTransform:
    """Resolve one authored Fighter or Champion feature."""
    if feature_id.startswith("class_feature.fighter.fighting_style."):
        return _fighting_style_transform(level, feature_id)
    if feature_id == "class_feature.fighter.second_wind":
        return _second_wind_transform(level)
    if feature_id == "class_feature.fighter.action_surge":
        return _action_surge_transform(level)
    if feature_id == "class_feature.extra_attack":
        return _extra_attack_transform(
            level,
            {5: 2, 11: 3, 20: 4}[level.resulting_class_level],
        )
    if feature_id == "class_feature.fighter.improved_critical":
        return _critical_transform(level, feature_id, "Improved Critical")
    if feature_id == "class_feature.fighter.superior_critical":
        return _critical_transform(level, feature_id, "Superior Critical Upgrade")
    if feature_id == "class_feature.fighter.indomitable":
        return _indomitable_transform(level)
    if feature_id == "class_feature.fighter.remarkable_athlete":
        return _remarkable_athlete_transform(level)
    if feature_id == "class_feature.fighter.survivor":
        return _survivor_transform(level)
    raise ValueError(f"unsupported Fighter feature {feature_id}")


_RAGE_ADVANCEMENT = {
    1: (2, 2),
    3: (3, 2),
    6: (4, 2),
    9: (4, 3),
    12: (5, 3),
    16: (5, 4),
    17: (6, 4),
    20: (999, 4),
}


def _unarmored_defense_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.unarmored_defense"

    def operation(entity: Entity) -> Undo:
        source_id = _source_id(entity, level.step_id, feature_id)
        entity.equipment.add_armor_class_formula_candidate(
            ArmorClassFormulaCandidate(
                source_id=source_id,
                base_ac=10,
                ability_names=(AbilityName.DEXTERITY, AbilityName.CONSTITUTION),
                requires_unarmored=True,
                allows_shield=True,
            ),
        )
        return lambda: entity.equipment.remove_armor_class_formula_candidate(
            source_id,
        )

    return _feature_transform(level, feature_id, operation)


def _rage_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.rage"
    uses, damage = _RAGE_ADVANCEMENT[level.resulting_class_level]
    operations: list[Operation] = [_resource_operation(
        level,
        feature_id,
        "rage",
        uses,
        RechargeType.LONG_REST,
        ResourceCapacityPolicy.MAXIMUM,
    )]
    if level.resulting_class_level == 1:
        operations.append(_actions_operation(
            level,
            feature_id,
            (
                lambda entity_uuid: rage.Rage(
                    source_entity_uuid=entity_uuid,
                    rage_damage=damage,
                    template=True,
                ),
                lambda entity_uuid: rage.EndRage(
                    source_entity_uuid=entity_uuid,
                    template=True,
                ),
            ),
            (
                "action.class.barbarian.rage",
                "action.class.barbarian.end_rage",
            ),
        ))
    return _feature_transform(level, feature_id, _combine(*operations))


def _replace_rage_with_frenzy(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.frenzy"

    def operation(entity: Entity) -> Undo:
        existing = _find_action(entity, "action.class.barbarian.rage")
        if existing is None:
            raise RuntimeError("Frenzy requires the Rage action")
        index = entity.registered_actions.index(existing)
        entity.registered_actions.pop(index)
        frenzy = rage.Frenzy(
            source_entity_uuid=entity.uuid,
            rage_damage=2,
            template=True,
            behavior_id="action.class.barbarian.frenzy",
            provided_by_id=feature_id,
            origin_root_id="class.barbarian",
        )
        try:
            entity.register_action(frenzy)
        except Exception:
            entity.registered_actions.insert(index, existing)
            frenzy.remove_from_register()
            raise
        existing.remove_from_register()

        def undo() -> None:
            entity.unregister_action_by_uuid(frenzy.uuid)
            # Restore the exact prior template at its authored position.
            type(existing).register(existing)
            existing.use_register = True
            entity.registered_actions.insert(index, existing)

        return undo

    return _feature_transform(level, feature_id, operation)


def _reckless_attack_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.reckless_attack"
    return _feature_transform(
        level,
        feature_id,
        _actions_operation(
            level,
            feature_id,
            (lambda entity_uuid: barbarian.RecklessAttack(
                source_entity_uuid=entity_uuid,
                template=True,
            ),),
            ("action.class.barbarian.reckless_attack",),
        ),
    )


def _danger_sense_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.danger_sense"

    def operation(entity: Entity) -> Undo:
        value = entity.saving_throws.get_saving_throw(
            AbilityName.DEXTERITY,
        ).bonus
        modifier = ContextualAdvantageModifier(
            uuid=_source_id(entity, level.step_id, feature_id),
            name="Danger Sense",
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            callable=barbarian.danger_sense_check,
        )
        value.self_contextual.add_advantage_modifier(modifier)

        def undo() -> None:
            value.self_contextual.remove_advantage_modifier(modifier.uuid)
            modifier.remove_from_register()

        return undo

    return _feature_transform(level, feature_id, operation)


def _fast_movement_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.fast_movement"
    return _feature_transform(
        level,
        feature_id,
        _contextual_modifier(
            level,
            feature_id,
            lambda entity: entity.action_economy.movement,
            barbarian.fast_movement_check,
            "Fast Movement",
        ),
    )


def _mindless_rage_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.mindless_rage"

    def operation(entity: Entity) -> Undo:
        source_id = _source_id(entity, level.step_id, feature_id)
        installed: list[str] = []
        try:
            for condition_id in ("Charmed", "Frightened"):
                entity.add_condition_immunity_source(
                    condition_id,
                    source_id,
                    immunity_check=barbarian.mindless_rage_immunity_check,
                )
                installed.append(condition_id)
        except Exception:
            for condition_id in reversed(installed):
                entity.remove_condition_immunity_source(condition_id, source_id)
            raise

        def undo() -> None:
            for condition_id in reversed(installed):
                entity.remove_condition_immunity_source(condition_id, source_id)

        return undo

    return _feature_transform(level, feature_id, operation)


def _feral_instinct_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.feral_instinct"

    def operation(entity: Entity) -> Undo:
        modifier = AdvantageModifier(
            uuid=_source_id(entity, level.step_id, feature_id),
            name="Feral Instinct",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
        )
        entity.initiative.self_static.add_advantage_modifier(modifier)

        def undo() -> None:
            entity.initiative.self_static.remove_advantage_modifier(modifier.uuid)
            modifier.remove_from_register()

        return undo

    return _feature_transform(level, feature_id, operation)


def _brutal_critical_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.brutal_critical"
    return _feature_transform(
        level,
        feature_id,
        _static_modifier(
            level,
            feature_id,
            lambda entity: entity.equipment.crit_extra_dice_melee,
            1,
            "Brutal Critical",
        ),
    )


def _relentless_rage_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.relentless_rage"

    def handler_factory(entity_uuid: UUID) -> EventHandler:
        return EventHandler(
            name="Relentless Rage",
            source_entity_uuid=entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TAKE_DAMAGE,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=barbarian.relentless_rage_processor,
        )

    return _feature_transform(
        level,
        feature_id,
        _combine(
            _resource_operation(
                level,
                feature_id,
                "relentless_rage",
                999,
                RechargeType.SHORT_REST,
                ResourceCapacityPolicy.MAXIMUM,
            ),
            _handlers_operation(
                level,
                feature_id,
                (handler_factory,),
                ("handler.class_feature.barbarian.relentless_rage",),
            ),
        ),
    )


def _indomitable_might_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.indomitable_might"
    return _feature_transform(
        level,
        feature_id,
        _handlers_operation(
            level,
            feature_id,
            (barbarian.create_indomitable_might_handler,),
            ("handler.class_feature.barbarian.indomitable_might",),
        ),
    )


def _primal_champion_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.primal_champion"
    return _feature_transform(
        level,
        feature_id,
        _combine(
            _static_modifier(
                level,
                f"{feature_id}.strength",
                lambda entity: entity.ability_scores.strength.ability_score,
                4,
                "Primal Champion (STR)",
            ),
            _static_modifier(
                level,
                f"{feature_id}.constitution",
                lambda entity: entity.ability_scores.constitution.ability_score,
                4,
                "Primal Champion (CON)",
            ),
        ),
    )


def _intimidating_presence_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.intimidating_presence"
    return _feature_transform(
        level,
        feature_id,
        _actions_operation(
            level,
            feature_id,
            (
                lambda entity_uuid: barbarian.IntimidatingPresence(
                    source_entity_uuid=entity_uuid,
                    template=True,
                ),
                lambda entity_uuid: barbarian.ExtendIntimidatingPresence(
                    source_entity_uuid=entity_uuid,
                    template=True,
                ),
            ),
            (
                "action.class.barbarian.intimidating_presence",
                "action.class.barbarian.extend_intimidating_presence",
            ),
        ),
    )


def _retaliation_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.barbarian.retaliation"
    return _feature_transform(
        level,
        feature_id,
        _handlers_operation(
            level,
            feature_id,
            (barbarian.create_retaliation_handler,),
            ("reaction.class_feature.barbarian.retaliation",),
        ),
    )


def barbarian_feature_transform(
    level: AppliedClassLevel,
    feature_id: str,
) -> EntityTransform:
    """Resolve one authored Barbarian or Berserker feature."""
    if feature_id == "class_feature.barbarian.unarmored_defense":
        return _unarmored_defense_transform(level)
    if feature_id == "class_feature.barbarian.rage":
        return _rage_transform(level)
    if feature_id == "class_feature.barbarian.frenzy":
        return _replace_rage_with_frenzy(level)
    if feature_id == "class_feature.barbarian.reckless_attack":
        return _reckless_attack_transform(level)
    if feature_id == "class_feature.barbarian.danger_sense":
        return _danger_sense_transform(level)
    if feature_id == "class_feature.extra_attack":
        return _extra_attack_transform(level, 2)
    if feature_id == "class_feature.barbarian.fast_movement":
        return _fast_movement_transform(level)
    if feature_id == "class_feature.barbarian.mindless_rage":
        return _mindless_rage_transform(level)
    if feature_id == "class_feature.barbarian.feral_instinct":
        return _feral_instinct_transform(level)
    if feature_id == "class_feature.barbarian.brutal_critical":
        return _brutal_critical_transform(level)
    if feature_id == "class_feature.barbarian.relentless_rage":
        return _relentless_rage_transform(level)
    if feature_id == "class_feature.barbarian.persistent_rage":
        return _feature_transform(level, feature_id, _no_mechanics)
    if feature_id == "class_feature.barbarian.indomitable_might":
        return _indomitable_might_transform(level)
    if feature_id == "class_feature.barbarian.primal_champion":
        return _primal_champion_transform(level)
    if feature_id == "class_feature.barbarian.intimidating_presence":
        return _intimidating_presence_transform(level)
    if feature_id == "class_feature.barbarian.retaliation":
        return _retaliation_transform(level)
    raise ValueError(f"unsupported Barbarian feature {feature_id}")


def rage_reconciliation_transform(
    level: AppliedClassLevel,
    *,
    damage: int,
    mindless: bool,
    persistent: bool,
) -> Optional[EntityTransform]:
    """Update whichever persistent Rage-family action is currently installed."""
    behavior_id = (
        "action.class.barbarian.frenzy"
        if level.subclass_id is not None
        else "action.class.barbarian.rage"
    )
    return _action_field_transform(
        level,
        behavior_id,
        rage_damage=damage,
        mindless_rage=mindless,
        persistent_rage=persistent,
    )


def second_wind_reconciliation_transform(
    level: AppliedClassLevel,
) -> EntityTransform:
    """Keep Second Wind's healing scale equal to current Fighter level."""
    return _action_field_transform(
        level,
        "action.class.fighter.second_wind",
        fighter_level=level.resulting_class_level,
    )


def _sorcerer_source_id(entity: Entity) -> UUID:
    return uuid5(entity.uuid, "spellcasting-source:class.sorcerer")


def sorcerer_spellcasting_transform(
    level: AppliedClassLevel,
) -> EntityTransform:
    """Reconcile the direct Sorcerer casting source to this class level."""
    contribution = SpellcastingClassContribution(
        class_level=level.resulting_class_level,
        progression=CasterProgression.FULL_CASTER,
        spellcasting_feature_class_level=1,
    )
    maximum_rank = maximum_spell_rank_for_contribution(contribution)

    def apply(entity: Entity) -> Undo:
        source_id = _sorcerer_source_id(entity)
        previous = entity.spellcasting.sources.pop(source_id, None)
        try:
            entity.spellcasting.add_source(
                source_id,
                AbilityName.CHARISMA,
                provider_id="class.sorcerer",
                caster_progression=CasterProgression.FULL_CASTER,
                provider_level=level.resulting_class_level,
                maximum_spell_rank=maximum_rank,
                ritual_policy=RitualPreparationPolicy.NONE,
            )
        except Exception:
            if previous is not None:
                entity.spellcasting.sources[source_id] = previous
            raise

        def undo() -> None:
            entity.spellcasting.remove_source(source_id)
            if previous is not None:
                entity.spellcasting.sources[source_id] = previous

        return undo

    return EntityTransform(f"{level.step_id}:class.sorcerer.spellcasting", apply)


def normal_spell_slots_transform(
    level: AppliedClassLevel,
    effective_caster_level: int,
) -> EntityTransform:
    """Replace the one aggregate normal-slot capacity with an exact inverse."""
    capacities = (
        full_caster_spell_slots_for_level(effective_caster_level)
        if effective_caster_level
        else {}
    )

    def apply(entity: Entity) -> Undo:
        source_id = uuid5(entity.uuid, "progression:normal-spell-slot-capacity")
        previous_source = entity.action_economy.get_normal_spell_slot_capacity_source()
        previous_capacities = entity.action_economy.get_normal_spell_slot_capacities()
        if previous_source is not None:
            entity.action_economy.remove_normal_spell_slot_capacity(previous_source)
        try:
            entity.action_economy.set_normal_spell_slot_capacity(
                source_id,
                capacities,
            )
        except Exception:
            if previous_source is not None:
                entity.action_economy.set_normal_spell_slot_capacity(
                    previous_source,
                    previous_capacities,
                )
            raise

        def undo() -> None:
            entity.action_economy.remove_normal_spell_slot_capacity(source_id)
            if previous_source is not None:
                entity.action_economy.set_normal_spell_slot_capacity(
                    previous_source,
                    previous_capacities,
                )

        return undo

    return EntityTransform(f"{level.step_id}:normal_spell_slots", apply)


def spell_learning_transform(
    level: AppliedClassLevel,
    spell_id: str,
) -> EntityTransform:
    """Install one known spell as its direct action or reaction behavior."""
    if spell_id not in SPELL_ACTION_TYPES_BY_ID and spell_id not in (
        REACTION_HANDLER_FACTORIES_BY_SPELL_ID
    ):
        raise ValueError(f"spell {spell_id} has no direct runtime behavior")

    def apply(entity: Entity) -> Undo:
        source_id = _sorcerer_source_id(entity)
        if source_id not in entity.spellcasting.sources:
            raise RuntimeError("known Sorcerer spell requires its casting source")
        action: Optional[BaseAction] = None
        handler: Optional[EventHandler] = None
        spell_type = SPELL_ACTION_TYPES_BY_ID.get(spell_id)
        if spell_type is not None:
            action = spell_type(
                source_entity_uuid=entity.uuid,
                caster_level=level.resulting_class_level,
                spellcasting_source_id=source_id,
                template=True,
                behavior_id=spell_id,
                provided_by_id="class.sorcerer",
                origin_root_id="class.sorcerer",
            )
            entity.register_action(action)
        else:
            factory = REACTION_HANDLER_FACTORIES_BY_SPELL_ID[spell_id]
            handler = factory(entity.uuid)
            handler.provided_by_id = spell_id
            handler.origin_root_id = "class.sorcerer"
            entity.add_event_handler(handler)
            try:
                entity.spellcasting.add_learned_reaction_spell_source(
                    spell_id=spell_id,
                    source_id=source_id,
                    handler_uuid=handler.uuid,
                )
            except Exception:
                entity.remove_event_handler(handler)
                handler.remove_from_register()
                raise

        def undo() -> None:
            if action is not None:
                entity.unregister_action_by_uuid(action.uuid)
            if handler is not None:
                remove_handler = entity.spellcasting.remove_learned_reaction_spell_source(
                    spell_id=spell_id,
                    source_id=source_id,
                    handler_uuid=handler.uuid,
                )
                if remove_handler:
                    entity.remove_event_handler(handler)
                    handler.remove_from_register()

        return undo

    return EntityTransform(f"{level.step_id}:learn.{spell_id}", apply)


def spell_replacement_transform(
    level: AppliedClassLevel,
    replaced_spell_id: str,
    learned_spell_id: str,
) -> EntityTransform:
    """Replace one known spell while retaining an exact inverse."""
    if replaced_spell_id == learned_spell_id:
        raise ValueError("spell replacement must change the spell")
    learned = spell_learning_transform(level, learned_spell_id)

    def apply(entity: Entity) -> Undo:
        source_id = _sorcerer_source_id(entity)
        action = next((
            candidate
            for candidate in entity.registered_actions
            if candidate.behavior_id == replaced_spell_id
            and getattr(candidate, "spellcasting_source_id", None) == source_id
        ), None)
        handler_uuid = entity.spellcasting.learned_reaction_spell_handler_uuid(
            replaced_spell_id,
        )
        handler = (
            entity.event_handlers.get(handler_uuid)
            if handler_uuid is not None
            else None
        )
        if (action is None) == (handler is None):
            raise ValueError(
                f"known spell {replaced_spell_id} does not own one runtime behavior",
            )
        action_index: Optional[int] = None
        if action is not None:
            action_index = entity.registered_actions.index(action)
            entity.unregister_action_by_uuid(action.uuid)
        else:
            assert handler is not None
            remove_handler = entity.spellcasting.remove_learned_reaction_spell_source(
                spell_id=replaced_spell_id,
                source_id=source_id,
                handler_uuid=handler.uuid,
            )
            if not remove_handler:
                raise RuntimeError("Sorcerer replacement did not release its handler")
            entity.remove_event_handler(handler)
            handler.remove_from_register()

        def restore_replaced() -> None:
            if action is not None:
                type(action).register(action)
                action.use_register = True
                assert action_index is not None
                entity.registered_actions.insert(action_index, action)
                return
            assert handler is not None
            type(handler).register(handler)
            handler.use_register = True
            entity.add_event_handler(handler)
            entity.spellcasting.add_learned_reaction_spell_source(
                spell_id=replaced_spell_id,
                source_id=source_id,
                handler_uuid=handler.uuid,
            )

        try:
            learned_receipt = learned.apply(entity)
        except Exception:
            restore_replaced()
            raise

        def undo() -> None:
            learned_receipt.undo()
            restore_replaced()

        return undo

    return EntityTransform(
        f"{level.step_id}:replace.{replaced_spell_id}.with.{learned_spell_id}",
        apply,
    )


def spell_caster_level_reconciliation_transform(
    level: AppliedClassLevel,
) -> EntityTransform:
    """Keep every Sorcerer-owned spell template at current provider level."""
    def apply(entity: Entity) -> Undo:
        source_id = _sorcerer_source_id(entity)
        actions = tuple(
            action
            for action in entity.registered_actions
            if getattr(action, "spellcasting_source_id", None) == source_id
            and hasattr(action, "caster_level")
        )
        previous = tuple((action, action.caster_level) for action in actions)
        for action in actions:
            action.caster_level = level.resulting_class_level

        def undo() -> None:
            for action, caster_level in previous:
                action.caster_level = caster_level

        return undo

    return EntityTransform(f"{level.step_id}:spell_caster_level", apply)


def _sorcery_points_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.sorcerer.sorcery_points"
    slot_ranks = tuple(
        rank
        for rank in full_caster_spell_slots_for_level(
            level.resulting_class_level,
        )
        if 1 <= rank <= 5
    )
    previous_slot_ranks = (
        set(full_caster_spell_slots_for_level(level.resulting_class_level - 1))
        if level.resulting_class_level > 2
        else set()
    )
    new_slot_ranks = tuple(rank for rank in slot_ranks if rank not in previous_slot_ranks)
    operations: list[Operation] = [_resource_operation(
        level,
        feature_id,
        "sorcery_points",
        level.resulting_class_level,
        RechargeType.LONG_REST,
        ResourceCapacityPolicy.MAXIMUM,
    )]
    for rank in new_slot_ranks:
        operations.append(_actions_operation(
            level,
            feature_id,
            (
                lambda entity_uuid, rank=rank: sorcerer.ConvertSlotToSP(
                    source_entity_uuid=entity_uuid,
                    slot_level=rank,
                    template=True,
                ),
                lambda entity_uuid, rank=rank: sorcerer.ConvertSPToSlot(
                    source_entity_uuid=entity_uuid,
                    slot_level=rank,
                    template=True,
                ),
            ),
            (
                f"action.class.sorcerer.convert_slot_{rank}_to_sorcery_points",
                f"action.class.sorcerer.convert_sorcery_points_to_slot_{rank}",
            ),
        ))
    return _feature_transform(level, feature_id, _combine(*operations))


def _draconic_resilience_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.sorcerer.draconic_resilience"

    def armor_operation(entity: Entity) -> Undo:
        source_id = _source_id(entity, level.step_id, f"{feature_id}.armor")
        entity.equipment.add_armor_class_formula_candidate(
            ArmorClassFormulaCandidate(
                source_id=source_id,
                base_ac=13,
                ability_names=(AbilityName.DEXTERITY,),
                requires_unarmored=True,
                allows_shield=True,
            ),
        )
        return lambda: entity.equipment.remove_armor_class_formula_candidate(source_id)

    return _feature_transform(
        level,
        feature_id,
        _combine(
            _static_modifier(
                level,
                f"{feature_id}.hp.level_1",
                lambda entity: entity.health.max_hit_points_bonus,
                1,
                "Draconic Resilience HP",
            ),
            armor_operation,
        ),
    )


def draconic_resilience_hp_transform(level: AppliedClassLevel) -> EntityTransform:
    """Add the subclass's one HP per later Sorcerer level."""
    return EntityTransform(
        f"{level.step_id}:class_feature.sorcerer.draconic_resilience.hp",
        _static_modifier(
            level,
            "class_feature.sorcerer.draconic_resilience.hp",
            lambda entity: entity.health.max_hit_points_bonus,
            1,
            "Draconic Resilience HP",
        ),
    )


_METAMAGIC_ACTIONS = {
    "class_feature.sorcerer.metamagic.distant_spell": (
        sorcerer.DistantSpell,
        "action.class.sorcerer.distant_spell",
    ),
    "class_feature.sorcerer.metamagic.quickened_spell": (
        sorcerer.QuickenedSpell,
        "action.class.sorcerer.quickened_spell",
    ),
    "class_feature.sorcerer.metamagic.twinned_spell": (
        sorcerer.TwinnedSpell,
        "action.class.sorcerer.twinned_spell",
    ),
}

_DRACONIC_DAMAGE_TYPES = {
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


def _metamagic_transform(level: AppliedClassLevel, feature_id: str) -> EntityTransform:
    action_type, behavior_id = _METAMAGIC_ACTIONS[feature_id]
    return _feature_transform(
        level,
        feature_id,
        _actions_operation(
            level,
            feature_id,
            (lambda entity_uuid: action_type(
                source_entity_uuid=entity_uuid,
                template=True,
            ),),
            (behavior_id,),
        ),
    )


def _elemental_affinity_transform(
    level: AppliedClassLevel,
    ancestry_feature_id: str,
) -> EntityTransform:
    feature_id = "class_feature.sorcerer.elemental_affinity"
    ancestry = ancestry_feature_id.rsplit(".", 1)[-1]
    damage_type = _DRACONIC_DAMAGE_TYPES[ancestry]

    def operation(entity: Entity) -> Undo:
        source_id = _source_id(entity, level.step_id, feature_id)
        entity.spellcasting.add_spell_damage_affinity_contribution(
            source_id,
            damage_type=damage_type,
            ability_name=AbilityName.CHARISMA,
        )
        action = sorcerer.ElementalAffinityResistanceAction(
            source_entity_uuid=entity.uuid,
            damage_type=damage_type,
            template=True,
            behavior_id="action.class.sorcerer.elemental_affinity.resistance",
            provided_by_id=feature_id,
            origin_root_id="class.sorcerer",
        )
        try:
            entity.register_action(action)
        except Exception:
            entity.spellcasting.remove_spell_damage_affinity_contribution(source_id)
            action.remove_from_register()
            raise

        def undo() -> None:
            entity.unregister_action_by_uuid(action.uuid)
            entity.spellcasting.remove_spell_damage_affinity_contribution(source_id)

        return undo

    return _feature_transform(level, feature_id, operation)


def _dragon_wings_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.sorcerer.dragon_wings"
    return _feature_transform(
        level,
        feature_id,
        _actions_operation(
            level,
            feature_id,
            (
                lambda entity_uuid: sorcerer.DragonWings(
                    source_entity_uuid=entity_uuid,
                    template=True,
                ),
                lambda entity_uuid: sorcerer.Fly(
                    source_entity_uuid=entity_uuid,
                    template=True,
                ),
            ),
            (
                "action.class.sorcerer.dragon_wings.toggle",
                "action.class.sorcerer.dragon_wings.fly",
            ),
        ),
    )


def _draconic_presence_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.sorcerer.draconic_presence"
    return _feature_transform(
        level,
        feature_id,
        _actions_operation(
            level,
            feature_id,
            (
                lambda entity_uuid: sorcerer.DraconicPresence(
                    source_entity_uuid=entity_uuid,
                    mode="awe",
                    template=True,
                ),
                lambda entity_uuid: sorcerer.DraconicPresence(
                    source_entity_uuid=entity_uuid,
                    mode="fear",
                    template=True,
                ),
            ),
            (
                "action.class.sorcerer.draconic_presence.awe",
                "action.class.sorcerer.draconic_presence.fear",
            ),
        ),
    )


def _sorcerous_restoration_transform(level: AppliedClassLevel) -> EntityTransform:
    feature_id = "class_feature.sorcerer.sorcerous_restoration"

    def operation(entity: Entity) -> Undo:
        source_id = _source_id(entity, level.step_id, feature_id)
        entity.action_economy.add_resource_recovery_contribution(
            "sorcery_points",
            source_id,
            trigger=RechargeType.SHORT_REST,
            amount=4,
        )
        return lambda: entity.action_economy.remove_resource_recovery_contribution(
            "sorcery_points",
            source_id,
        )

    return _feature_transform(level, feature_id, operation)


def sorcerer_feature_transform(
    level: AppliedClassLevel,
    feature_id: str,
    *,
    ancestry_feature_id: Optional[str],
) -> EntityTransform:
    """Resolve one authored Sorcerer or Draconic Bloodline feature."""
    if feature_id == "class_feature.sorcerer.sorcery_points":
        return _sorcery_points_transform(level)
    if feature_id == "class_feature.sorcerer.draconic_resilience":
        return _draconic_resilience_transform(level)
    if feature_id.startswith("class_feature.sorcerer.draconic_ancestry."):
        return _feature_transform(level, feature_id, _no_mechanics)
    if feature_id in _METAMAGIC_ACTIONS:
        return _metamagic_transform(level, feature_id)
    if feature_id == "class_feature.sorcerer.elemental_affinity":
        if ancestry_feature_id is None:
            raise ValueError("Elemental Affinity requires Draconic ancestry")
        return _elemental_affinity_transform(level, ancestry_feature_id)
    if feature_id == "class_feature.sorcerer.dragon_wings":
        return _dragon_wings_transform(level)
    if feature_id == "class_feature.sorcerer.draconic_presence":
        return _draconic_presence_transform(level)
    if feature_id == "class_feature.sorcerer.sorcerous_restoration":
        return _sorcerous_restoration_transform(level)
    raise ValueError(f"unsupported Sorcerer feature {feature_id}")


__all__ = [
    "ability_score_improvement_transform",
    "barbarian_feature_transform",
    "common_level_transforms",
    "feat_transform",
    "fighter_feature_transform",
    "draconic_resilience_hp_transform",
    "normal_spell_slots_transform",
    "rage_reconciliation_transform",
    "second_wind_reconciliation_transform",
    "sorcerer_feature_transform",
    "sorcerer_spellcasting_transform",
    "spell_caster_level_reconciliation_transform",
    "spell_learning_transform",
    "spell_replacement_transform",
]
