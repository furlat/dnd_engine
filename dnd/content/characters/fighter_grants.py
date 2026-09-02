"""Direct Fighter/Champion component grants and exact cleanup."""

from typing import cast
from uuid import UUID, uuid5

from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.blocks.health import HitDice, HitDiceConfig
from dnd.classes import feats, fighter
from dnd.content.characters.class_definitions import (
    ResolvedFighterLevel,
    resolve_fighter_level,
)
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.equipment_types import ArmorType, WeaponProperty
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.feature_grants import AttackMultiplicityGrant
from dnd.core.modifiers import ContextualNumericalModifier, NumericalModifier
from dnd.core.proficiency_types import ProficiencyMode
from dnd.entity import Entity
from dnd.types.abilities import AbilityName, SavingThrowName
from dnd.types.character_progression import AppliedClassLevel, CharacterClass
from dnd.types.character_receipts import FighterGrantReceipt


_SECOND_WIND = "class_feature.fighter.second_wind"
_ACTION_SURGE = "class_feature.fighter.action_surge"
_EXTRA_ATTACK = "class_feature.extra_attack"
_INDOMITABLE = "class_feature.fighter.indomitable"
_IMPROVED_CRITICAL = "class_feature.fighter.improved_critical"
_REMARKABLE_ATHLETE = "class_feature.fighter.remarkable_athlete"
_SUPERIOR_CRITICAL = "class_feature.fighter.superior_critical"
_SURVIVOR = "class_feature.fighter.survivor"
_ATTACKS_PER_ACTION = {5: 2, 11: 3, 20: 4}


def _source(entity: Entity, identity: str) -> UUID:
    return uuid5(entity.uuid, f"dnd-engine:fighter:v1:{identity}")


def _binding(
    entity: Entity,
    *,
    behavior_id: str,
    provided_by_id: str,
) -> BehaviorBinding:
    return BehaviorBinding(
        behavior_id=behavior_id,
        provided_by_id=provided_by_id,
        origin_root_id=CharacterClass.FIGHTER.value,
        runtime_owner_uuid=entity.uuid,
    )


def _register_action(entity: Entity, actions: list[UUID], action) -> None:
    try:
        entity.register_action(action)
    except BaseException:
        action.remove_from_register()
        raise
    actions.append(action.uuid)


def _register_handler(
    entity: Entity,
    handlers: list[UUID],
    handler: EventHandler,
) -> None:
    try:
        entity.add_event_handler(handler)
    except BaseException:
        handler.remove_from_register()
        raise
    handlers.append(handler.uuid)


def _remarkable_athlete_jump_bonus(
    source_entity_uuid: UUID,
    target_entity_uuid: UUID | None = None,
    context: dict[str, object] | None = None,
) -> NumericalModifier | None:
    _ = target_entity_uuid, context
    entity = Entity.get(source_entity_uuid)
    if entity is None:
        return None
    return NumericalModifier(
        source_entity_uuid=source_entity_uuid,
        name="Remarkable Athlete",
        value=entity.ability_scores.strength.modifier,
        use_register=False,
    )


def _apply_proficiencies(
    entity: Entity,
    resolved: ResolvedFighterLevel,
    creature_sources: list[UUID],
    skills: list[tuple[str, UUID]],
    saves: list[tuple[SavingThrowName, UUID]],
) -> None:
    if resolved.proficiencies:
        source_id = _source(entity, f"{resolved.level.step_id}.proficiencies")
        for proficiency in resolved.proficiencies:
            if proficiency == "weapon.simple":
                entity.creature_proficiencies.add_weapon_source(
                    source_id,
                    WeaponProperty.SIMPLE,
                )
            elif proficiency == "weapon.martial":
                entity.creature_proficiencies.add_weapon_source(
                    source_id,
                    WeaponProperty.MARTIAL,
                )
            elif proficiency == "armor.light":
                entity.creature_proficiencies.add_armor_source(
                    source_id,
                    ArmorType.LIGHT,
                )
            elif proficiency == "armor.medium":
                entity.creature_proficiencies.add_armor_source(
                    source_id,
                    ArmorType.MEDIUM,
                )
            elif proficiency == "armor.heavy":
                entity.creature_proficiencies.add_armor_source(
                    source_id,
                    ArmorType.HEAVY,
                )
            elif proficiency == "shield.shield":
                entity.creature_proficiencies.add_shield_source(source_id)
            else:
                raise ValueError(f"unsupported Fighter proficiency {proficiency}")
        creature_sources.append(source_id)

    for skill in resolved.skills:
        source_id = _source(entity, f"{resolved.level.step_id}.skill.{skill}")
        entity.skill_set.get_skill(skill).add_proficiency_source(
            source_id,
            ProficiencyMode.FULL,
        )
        skills.append((skill, source_id))
    for ability in resolved.saving_throws:
        source_id = _source(entity, f"{resolved.level.step_id}.save.{ability}")
        entity.saving_throws.get_saving_throw(ability).add_proficiency_source(
            source_id,
            ProficiencyMode.FULL,
        )
        saves.append((f"{ability}_saving_throw", source_id))


def _apply_style(
    entity: Entity,
    resolved: ResolvedFighterLevel,
    *,
    ranged: list[UUID],
    armor: list[UUID],
    melee: list[UUID],
    off_hand_melee: list[UUID],
    off_hand_ranged: list[UUID],
    handlers: list[UUID],
) -> None:
    style = resolved.fighting_style_id
    if style is None:
        return
    modifier_id = _source(entity, f"{resolved.level.step_id}.{style}.modifier")
    if style.endswith(".archery"):
        entity.equipment.ranged_attack_bonus.self_static.add_value_modifier(
            NumericalModifier(
                uuid=modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Archery",
                value=2,
            ),
        )
        ranged.append(modifier_id)
    elif style.endswith(".defense"):
        entity.equipment.ac_bonus.self_contextual.add_value_modifier(
            ContextualNumericalModifier(
                uuid=modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Defense",
                callable=fighter.defense_ac_check,
            ),
        )
        armor.append(modifier_id)
    elif style.endswith(".dueling"):
        entity.equipment.melee_damage_bonus.self_contextual.add_value_modifier(
            ContextualNumericalModifier(
                uuid=modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Dueling",
                callable=fighter.dueling_damage_check,
            ),
        )
        melee.append(modifier_id)
    elif style.endswith(".two_weapon_fighting"):
        melee_id = _source(entity, f"{resolved.level.step_id}.{style}.melee")
        ranged_id = _source(entity, f"{resolved.level.step_id}.{style}.ranged")
        entity.equipment.off_hand_melee_ability_bonus.self_contextual.add_value_modifier(
            ContextualNumericalModifier(
                uuid=melee_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Two-Weapon Fighting",
                callable=fighter.twf_off_hand_melee_ability_bonus,
            ),
        )
        off_hand_melee.append(melee_id)
        entity.equipment.off_hand_ranged_ability_bonus.self_contextual.add_value_modifier(
            ContextualNumericalModifier(
                uuid=ranged_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Two-Weapon Fighting",
                callable=fighter.twf_off_hand_ranged_ability_bonus,
            ),
        )
        off_hand_ranged.append(ranged_id)
    elif style.endswith(".great_weapon_fighting"):
        _register_handler(
            entity,
            handlers,
            EventHandler(
                uuid=_source(
                    entity,
                    f"{resolved.level.step_id}.{style}.handler",
                ),
                name="Great Weapon Fighting",
                semantic_key=style,
                source_entity_uuid=entity.uuid,
                trigger_conditions=[Trigger(
                    event_type=EventType.DAMAGE_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                )],
                event_processor=fighter.great_weapon_fighting_processor,
                player_toggleable=True,
                behavior_binding=_binding(
                    entity,
                    behavior_id=style,
                    provided_by_id=style,
                ),
            ),
        )
    elif style.endswith(".protection"):
        handler = fighter.create_protection_handler(
            entity.uuid,
            handler_uuid=_source(
                entity,
                f"{resolved.level.step_id}.{style}.handler",
            ),
        )
        handler.behavior_binding = _binding(
            entity,
            behavior_id="reaction.class_feature.fighter.protection",
            provided_by_id=style,
        )
        _register_handler(entity, handlers, handler)
    else:
        raise ValueError(f"unsupported Fighter fighting style {style}")


def _apply_lucky(
    entity: Entity,
    resolved: ResolvedFighterLevel,
    resources: list[tuple[str, UUID]],
    handlers: list[UUID],
) -> None:
    if resolved.feat_id != "feat.lucky":
        return
    source_id = _source(entity, f"{resolved.level.step_id}.feat.lucky")
    entity.action_economy.add_resource_contribution(
        "luck_points",
        source_id,
        maximum=3,
        recharge_type=RechargeType.LONG_REST,
        capacity_policy=ResourceCapacityPolicy.SUM,
    )
    resources.append(("luck_points", source_id))
    _register_handler(
        entity,
        handlers,
        EventHandler(
            uuid=_source(
                entity,
                f"{resolved.level.step_id}.feat.lucky.handler",
            ),
            name="Lucky",
            semantic_key="feat.lucky",
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
            event_processor=feats.lucky_processor,
            player_toggleable=True,
            behavior_binding=_binding(
                entity,
                behavior_id="feat.lucky",
                provided_by_id="feat.lucky",
            ),
        ),
    )


def _apply_level_features(
    entity: Entity,
    resolved: ResolvedFighterLevel,
    *,
    actions: list[UUID],
    handlers: list[UUID],
    resources: list[tuple[str, UUID]],
    attack_grants: list[UUID],
    melee_crit: list[UUID],
    ranged_crit: list[UUID],
    ability_checks: list[tuple[AbilityName, UUID]],
    jump_modifiers: list[UUID],
) -> None:
    class_level = resolved.level.resulting_class_level
    step_id = resolved.level.step_id
    if _SECOND_WIND in resolved.feature_ids:
        source_id = _source(entity, f"{step_id}.{_SECOND_WIND}")
        entity.action_economy.add_resource_contribution(
            "second_wind",
            source_id,
            maximum=1,
            recharge_type=RechargeType.SHORT_REST,
            capacity_policy=ResourceCapacityPolicy.SUM,
        )
        resources.append(("second_wind", source_id))
        _register_action(
            entity,
            actions,
            fighter.SecondWind(
                uuid=_source(entity, f"{step_id}.{_SECOND_WIND}.action"),
                source_entity_uuid=entity.uuid,
                fighter_level=class_level,
                template=True,
                semantic_key="action.class.fighter.second_wind",
                behavior_binding=_binding(
                    entity,
                    behavior_id="action.class.fighter.second_wind",
                    provided_by_id=_SECOND_WIND,
                ),
            ),
        )
    if _ACTION_SURGE in resolved.feature_ids:
        source_id = _source(entity, f"{step_id}.{_ACTION_SURGE}")
        entity.action_economy.add_resource_contribution(
            "action_surge",
            source_id,
            maximum=1,
            recharge_type=RechargeType.SHORT_REST,
            capacity_policy=ResourceCapacityPolicy.SUM,
        )
        resources.append(("action_surge", source_id))
        if class_level == 2:
            _register_action(
                entity,
                actions,
                fighter.ActionSurge(
                    uuid=_source(entity, f"{step_id}.{_ACTION_SURGE}.action"),
                    source_entity_uuid=entity.uuid,
                    template=True,
                    semantic_key="action.class.fighter.action_surge",
                    behavior_binding=_binding(
                        entity,
                        behavior_id="action.class.fighter.action_surge",
                        provided_by_id=_ACTION_SURGE,
                    ),
                ),
            )
    if _EXTRA_ATTACK in resolved.feature_ids:
        attacks = _ATTACKS_PER_ACTION[class_level]
        source_id = _source(entity, f"{step_id}.{_EXTRA_ATTACK}")
        entity.action_economy.add_attack_multiplicity_grant(
            AttackMultiplicityGrant(
                grant_id=source_id,
                provider_id=_EXTRA_ATTACK,
                attacks_per_attack_action=attacks,
                acquisition_ordinal=resolved.level.character_level,
            ),
        )
        attack_grants.append(source_id)
        entity.action_economy.add_resource_contribution(
            "extra_attacks",
            source_id,
            maximum=attacks - 1,
            recharge_type=RechargeType.TURN_START,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        resources.append(("extra_attacks", source_id))
        if class_level == 5:
            _register_action(
                entity,
                actions,
                fighter.ExtraAttack(
                    uuid=_source(entity, f"{step_id}.{_EXTRA_ATTACK}.action"),
                    source_entity_uuid=entity.uuid,
                    name="Extra Attack",
                    template=True,
                    discover_equipped_weapon_slots=True,
                    semantic_key="action.feature.extra_attack",
                    behavior_binding=_binding(
                        entity,
                        behavior_id="action.feature.extra_attack",
                        provided_by_id=_EXTRA_ATTACK,
                    ),
                ),
            )
            handler = fighter.create_extra_attack_resource_handler(
                entity.uuid,
                handler_uuid=_source(
                    entity,
                    f"{step_id}.{_EXTRA_ATTACK}.handler",
                ),
            )
            handler.behavior_binding = _binding(
                entity,
                behavior_id=_EXTRA_ATTACK,
                provided_by_id=_EXTRA_ATTACK,
            )
            _register_handler(entity, handlers, handler)
    if _INDOMITABLE in resolved.feature_ids:
        source_id = _source(entity, f"{step_id}.{_INDOMITABLE}")
        entity.action_economy.add_resource_contribution(
            "indomitable",
            source_id,
            maximum=1,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.SUM,
        )
        resources.append(("indomitable", source_id))
        if class_level == 9:
            handler = fighter.create_indomitable_handler(
                entity.uuid,
                handler_uuid=_source(
                    entity,
                    f"{step_id}.{_INDOMITABLE}.handler",
                ),
            )
            handler.behavior_binding = _binding(
                entity,
                behavior_id=_INDOMITABLE,
                provided_by_id=_INDOMITABLE,
            )
            _register_handler(entity, handlers, handler)

    critical_feature_id = None
    if _IMPROVED_CRITICAL in resolved.feature_ids:
        critical_feature_id = _IMPROVED_CRITICAL
    elif _SUPERIOR_CRITICAL in resolved.feature_ids:
        critical_feature_id = _SUPERIOR_CRITICAL
    if critical_feature_id is not None:
        for suffix, value, destination in (
            ("melee", entity.equipment.crit_threshold_melee, melee_crit),
            ("ranged", entity.equipment.crit_threshold_ranged, ranged_crit),
        ):
            modifier_id = _source(
                entity,
                f"{step_id}.{critical_feature_id}.{suffix}",
            )
            value.self_static.add_value_modifier(NumericalModifier(
                uuid=modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name=(
                    "Improved Critical"
                    if critical_feature_id == _IMPROVED_CRITICAL
                    else "Superior Critical Upgrade"
                ),
                value=1,
            ))
            destination.append(modifier_id)
    if _REMARKABLE_ATHLETE in resolved.feature_ids:
        source_id = _source(entity, f"{step_id}.{_REMARKABLE_ATHLETE}")
        for ability in ("strength", "dexterity", "constitution"):
            entity.ability_scores.get_ability(
                ability,
            ).add_check_proficiency_source(
                source_id,
                ProficiencyMode.HALF_ROUND_UP,
            )
            ability_checks.append((ability, source_id))
        modifier_id = _source(entity, f"{step_id}.{_REMARKABLE_ATHLETE}.jump")
        entity.jump_distance_additive.self_contextual.add_value_modifier(
            ContextualNumericalModifier(
                uuid=modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name="Remarkable Athlete",
                callable=_remarkable_athlete_jump_bonus,
            ),
        )
        jump_modifiers.append(modifier_id)
    if _SURVIVOR in resolved.feature_ids:
        handler = fighter.create_survivor_handler(
            entity.uuid,
            handler_uuid=_source(entity, f"{step_id}.{_SURVIVOR}.handler"),
        )
        handler.behavior_binding = _binding(
            entity,
            behavior_id=_SURVIVOR,
            provided_by_id=_SURVIVOR,
        )
        _register_handler(entity, handlers, handler)


def _fighter_creature_source_is_owned(entity: Entity, source_id: UUID) -> bool:
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


def _validate_fighter_receipt_ownership(
    entity: Entity,
    receipt: FighterGrantReceipt,
) -> None:
    """Fail before mutation when one Fighter handle changed owner."""
    actions = {action.uuid: action for action in entity.registered_actions}
    for action_uuid in receipt.action_uuids:
        if action_uuid not in actions:
            raise RuntimeError("Fighter action template is missing")
    queue_handlers = {
        handler.uuid: handler
        for handler in EventQueue.get_handlers_by_source_entity(entity.uuid)
    }
    for handler_uuid in receipt.handler_uuids:
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None or queue_handlers.get(handler_uuid) is not handler:
            raise RuntimeError("Fighter event handler ownership changed")
    for resource_name, source_id in receipt.resource_contributions:
        resource = entity.action_economy.resources.get(resource_name)
        if resource is None or str(source_id) not in resource.capacity_contributions:
            raise RuntimeError("Fighter resource contribution ownership changed")
    attack_grants = {
        grant.grant_id
        for grant in entity.action_economy.get_attack_multiplicity_grants()
    }
    if any(
        grant_id not in attack_grants
        for grant_id in receipt.attack_multiplicity_grant_ids
    ):
        raise RuntimeError("Fighter attack grant ownership changed")

    numerical_owners = (
        (entity.equipment.ranged_attack_bonus.self_static.value_modifiers,
         receipt.ranged_attack_bonus_modifier_ids),
        (entity.equipment.crit_threshold_melee.self_static.value_modifiers,
         receipt.melee_critical_threshold_modifier_ids),
        (entity.equipment.crit_threshold_ranged.self_static.value_modifiers,
         receipt.ranged_critical_threshold_modifier_ids),
    )
    for modifiers, modifier_ids in numerical_owners:
        for modifier_id in modifier_ids:
            modifier = modifiers.get(modifier_id)
            if modifier is None or NumericalModifier.get(modifier_id) is not modifier:
                raise RuntimeError("Fighter numerical modifier ownership changed")
    for ability, modifier_id in receipt.ability_score_modifier_ids:
        modifiers = entity.ability_scores.get_ability(
            ability,
        ).ability_score.self_static.value_modifiers
        modifier = modifiers.get(modifier_id)
        if modifier is None or NumericalModifier.get(modifier_id) is not modifier:
            raise RuntimeError("Fighter ability modifier ownership changed")

    contextual_owners = (
        (entity.equipment.ac_bonus.self_contextual.value_modifiers,
         receipt.armor_class_bonus_modifier_ids),
        (entity.equipment.melee_damage_bonus.self_contextual.value_modifiers,
         receipt.melee_damage_bonus_modifier_ids),
        (entity.equipment.off_hand_melee_ability_bonus.self_contextual.value_modifiers,
         receipt.off_hand_melee_ability_bonus_modifier_ids),
        (entity.equipment.off_hand_ranged_ability_bonus.self_contextual.value_modifiers,
         receipt.off_hand_ranged_ability_bonus_modifier_ids),
        (entity.jump_distance_additive.self_contextual.value_modifiers,
         receipt.jump_distance_additive_modifier_ids),
    )
    for modifiers, modifier_ids in contextual_owners:
        for modifier_id in modifier_ids:
            modifier = modifiers.get(modifier_id)
            if (
                modifier is None
                or ContextualNumericalModifier.get(modifier_id) is not modifier
            ):
                raise RuntimeError("Fighter contextual modifier ownership changed")

    for ability, source_id in receipt.ability_check_proficiency_sources:
        if source_id not in entity.ability_scores.get_ability(
            ability,
        ).check_proficiency_sources.sources:
            raise RuntimeError("Fighter ability-check source ownership changed")
    for feature_id, source_id in receipt.feature_sources:
        if source_id not in entity.feature_sources.get(feature_id, set()):
            raise RuntimeError("Fighter feature source ownership changed")
    for source_id in receipt.creature_proficiency_source_ids:
        if not _fighter_creature_source_is_owned(entity, source_id):
            raise RuntimeError("Fighter creature proficiency ownership changed")
    for saving_throw, source_id in receipt.saving_throw_proficiency_sources:
        if source_id not in entity.saving_throws.get_saving_throw(
            saving_throw.removesuffix("_saving_throw"),
        ).proficiency_sources.sources:
            raise RuntimeError("Fighter saving-throw source ownership changed")
    for skill, source_id in receipt.skill_proficiency_sources:
        if source_id not in entity.skill_set.get_skill(
            skill,
        ).proficiency_sources.sources:
            raise RuntimeError("Fighter skill source ownership changed")
    hit_dice = {hit_die.uuid: hit_die for hit_die in entity.health.hit_dices}
    for hit_die_uuid in receipt.hit_die_uuids:
        hit_die = hit_dice.get(hit_die_uuid)
        if hit_die is None or hit_die.source_entity_uuid != entity.uuid:
            raise RuntimeError("Fighter hit-die ownership changed")


def _remove_fighter_receipt(entity: Entity, receipt: FighterGrantReceipt) -> None:
    _validate_fighter_receipt_ownership(entity, receipt)
    for handler_uuid in reversed(receipt.handler_uuids):
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None:
            raise RuntimeError("Fighter event handler is missing")
        entity.remove_event_handler(handler)
        handler.remove_from_register()
    for action_uuid in reversed(receipt.action_uuids):
        if not entity.unregister_action_by_uuid(action_uuid):
            raise RuntimeError("Fighter action template is missing")
    for resource_name, source_id in reversed(receipt.resource_contributions):
        if not entity.action_economy.remove_resource_contribution(
            resource_name,
            source_id,
        ):
            raise RuntimeError("Fighter resource contribution is missing")
    for source_id in reversed(receipt.attack_multiplicity_grant_ids):
        if not entity.action_economy.remove_attack_multiplicity_grant(source_id):
            raise RuntimeError("Fighter attack grant is missing")
    for modifier_id in reversed(receipt.jump_distance_additive_modifier_ids):
        entity.jump_distance_additive.self_contextual.remove_value_modifier(modifier_id)
        ContextualNumericalModifier.unregister(modifier_id)
    for ability, source_id in reversed(receipt.ability_check_proficiency_sources):
        if not entity.ability_scores.get_ability(
            ability,
        ).remove_check_proficiency_source(source_id):
            raise RuntimeError("Fighter ability-check source is missing")
    for modifier_id in reversed(receipt.ranged_critical_threshold_modifier_ids):
        entity.equipment.crit_threshold_ranged.self_static.remove_value_modifier(
            modifier_id,
        )
        NumericalModifier.unregister(modifier_id)
    for modifier_id in reversed(receipt.melee_critical_threshold_modifier_ids):
        entity.equipment.crit_threshold_melee.self_static.remove_value_modifier(
            modifier_id,
        )
        NumericalModifier.unregister(modifier_id)
    for modifier_id in reversed(receipt.off_hand_ranged_ability_bonus_modifier_ids):
        entity.equipment.off_hand_ranged_ability_bonus.self_contextual.remove_value_modifier(
            modifier_id,
        )
        ContextualNumericalModifier.unregister(modifier_id)
    for modifier_id in reversed(receipt.off_hand_melee_ability_bonus_modifier_ids):
        entity.equipment.off_hand_melee_ability_bonus.self_contextual.remove_value_modifier(
            modifier_id,
        )
        ContextualNumericalModifier.unregister(modifier_id)
    for modifier_id in reversed(receipt.melee_damage_bonus_modifier_ids):
        entity.equipment.melee_damage_bonus.self_contextual.remove_value_modifier(
            modifier_id,
        )
        ContextualNumericalModifier.unregister(modifier_id)
    for modifier_id in reversed(receipt.armor_class_bonus_modifier_ids):
        entity.equipment.ac_bonus.self_contextual.remove_value_modifier(modifier_id)
        ContextualNumericalModifier.unregister(modifier_id)
    for modifier_id in reversed(receipt.ranged_attack_bonus_modifier_ids):
        entity.equipment.ranged_attack_bonus.self_static.remove_value_modifier(
            modifier_id,
        )
        NumericalModifier.unregister(modifier_id)
    for ability, modifier_id in reversed(receipt.ability_score_modifier_ids):
        entity.ability_scores.get_ability(
            ability,
        ).ability_score.self_static.remove_value_modifier(modifier_id)
        NumericalModifier.unregister(modifier_id)
    for feature_id, source_id in reversed(receipt.feature_sources):
        if not entity.remove_feature_source(feature_id, source_id):
            raise RuntimeError("Fighter feature source is missing")
    for source_id in reversed(receipt.creature_proficiency_source_ids):
        if not entity.creature_proficiencies.remove_source(source_id):
            raise RuntimeError("Fighter creature proficiency source is missing")
    for saving_throw, source_id in reversed(
        receipt.saving_throw_proficiency_sources,
    ):
        ability = saving_throw.removesuffix("_saving_throw")
        if not entity.saving_throws.get_saving_throw(
            ability,
        ).remove_proficiency_source(source_id):
            raise RuntimeError("Fighter saving-throw source is missing")
    for skill, source_id in reversed(receipt.skill_proficiency_sources):
        if not entity.skill_set.get_skill(skill).remove_proficiency_source(source_id):
            raise RuntimeError("Fighter skill source is missing")
    for hit_die_uuid in reversed(receipt.hit_die_uuids):
        if not entity.health.remove_hit_dice_by_uuid(hit_die_uuid):
            raise RuntimeError("Fighter hit die is missing")


def _second_wind_action(entity: Entity) -> fighter.SecondWind | None:
    try:
        stored = entity.character_grant_receipt("class.fighter.level_1")
    except KeyError:
        return None
    receipt = cast(FighterGrantReceipt, stored)
    if len(receipt.action_uuids) != 1:
        raise RuntimeError("Fighter level 1 must own exactly one action")
    action_uuid = receipt.action_uuids[0]
    action = next(
        (
            candidate
            for candidate in entity.registered_actions
            if candidate.uuid == action_uuid
        ),
        None,
    )
    if action is None:
        raise RuntimeError("Fighter-owned Second Wind action is missing")
    return cast(fighter.SecondWind, action)


def apply_fighter_level(
    entity: Entity,
    level: AppliedClassLevel,
    *,
    initial_first_class: bool | None = None,
) -> FighterGrantReceipt:
    """Apply one next resolved Fighter/Champion row without publishing Events."""
    resolved = resolve_fighter_level(
        level,
        entity.applied_class_levels,
        initial_first_class=initial_first_class,
    )
    for ability, amount in resolved.ability_increases:
        current = entity.ability_scores.get_ability(ability).ability_score.score
        if current + amount > 20:
            raise ValueError(f"ASI would raise {ability} above 20")
    try:
        entity.character_grant_receipt(level.step_id)
    except KeyError:
        pass
    else:
        raise RuntimeError(f"Fighter receipt {level.step_id} is already installed")

    source_id = _source(entity, level.step_id)
    hit_dice: list[UUID] = []
    skills: list[tuple[str, UUID]] = []
    saves: list[tuple[SavingThrowName, UUID]] = []
    creature_sources: list[UUID] = []
    ability_modifiers: list[tuple[AbilityName, UUID]] = []
    ability_checks: list[tuple[AbilityName, UUID]] = []
    ranged: list[UUID] = []
    armor: list[UUID] = []
    melee: list[UUID] = []
    off_hand_melee: list[UUID] = []
    off_hand_ranged: list[UUID] = []
    melee_crit: list[UUID] = []
    ranged_crit: list[UUID] = []
    jump_modifiers: list[UUID] = []
    actions: list[UUID] = []
    handlers: list[UUID] = []
    resources: list[tuple[str, UUID]] = []
    attack_grants: list[UUID] = []
    features: list[tuple[str, UUID]] = []
    receipt_stored = False
    state_stored = False

    def receipt() -> FighterGrantReceipt:
        return FighterGrantReceipt(
            step_id=level.step_id,
            source_id=source_id,
            hit_die_uuids=tuple(hit_dice),
            skill_proficiency_sources=tuple(skills),
            saving_throw_proficiency_sources=tuple(saves),
            creature_proficiency_source_ids=tuple(creature_sources),
            ability_score_modifier_ids=tuple(ability_modifiers),
            ability_check_proficiency_sources=tuple(ability_checks),
            ranged_attack_bonus_modifier_ids=tuple(ranged),
            armor_class_bonus_modifier_ids=tuple(armor),
            melee_damage_bonus_modifier_ids=tuple(melee),
            off_hand_melee_ability_bonus_modifier_ids=tuple(off_hand_melee),
            off_hand_ranged_ability_bonus_modifier_ids=tuple(off_hand_ranged),
            melee_critical_threshold_modifier_ids=tuple(melee_crit),
            ranged_critical_threshold_modifier_ids=tuple(ranged_crit),
            jump_distance_additive_modifier_ids=tuple(jump_modifiers),
            action_uuids=tuple(actions),
            handler_uuids=tuple(handlers),
            resource_contributions=tuple(resources),
            attack_multiplicity_grant_ids=tuple(attack_grants),
            feature_sources=tuple(features),
        )

    try:
        hit_die = HitDice.create(
            source_entity_uuid=entity.uuid,
            name=level.step_id,
            config=HitDiceConfig(
                hit_dice_value=10,
                hit_dice_count=1,
                mode="maximums" if level.character_level == 1 else "average",
                ignore_first_level=level.character_level != 1,
            ),
            identity_uuid=_source(entity, f"{level.step_id}.hit_die"),
        )
        entity.health.add_hit_dice(hit_die)
        hit_dice.append(hit_die.uuid)
        _apply_proficiencies(entity, resolved, creature_sources, skills, saves)

        for ability, amount in resolved.ability_increases:
            modifier_id = _source(entity, f"{level.step_id}.asi.{ability}")
            entity.ability_scores.get_ability(
                ability,
            ).ability_score.self_static.add_value_modifier(NumericalModifier(
                uuid=modifier_id,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name=f"Fighter level {level.resulting_class_level} ASI",
                value=amount,
            ))
            ability_modifiers.append((ability, modifier_id))

        for feature_id in resolved.feature_ids:
            feature_source = _source(entity, f"{level.step_id}.feature.{feature_id}")
            entity.add_feature_source(feature_id, feature_source)
            features.append((feature_id, feature_source))

        _apply_style(
            entity,
            resolved,
            ranged=ranged,
            armor=armor,
            melee=melee,
            off_hand_melee=off_hand_melee,
            off_hand_ranged=off_hand_ranged,
            handlers=handlers,
        )
        _apply_lucky(entity, resolved, resources, handlers)
        _apply_level_features(
            entity,
            resolved,
            actions=actions,
            handlers=handlers,
            resources=resources,
            attack_grants=attack_grants,
            melee_crit=melee_crit,
            ranged_crit=ranged_crit,
            ability_checks=ability_checks,
            jump_modifiers=jump_modifiers,
        )

        completed = receipt()
        entity.store_character_grant_receipt(completed)
        receipt_stored = True
        entity.applied_class_levels = (*entity.applied_class_levels, level)
        state_stored = True
        second_wind = _second_wind_action(entity)
        if second_wind is not None:
            second_wind.fighter_level = level.resulting_class_level
        return completed
    except BaseException:
        if state_stored:
            entity.applied_class_levels = entity.applied_class_levels[:-1]
        if receipt_stored:
            entity.remove_character_grant_receipt(level.step_id)
        _remove_fighter_receipt(entity, receipt())
        previous = _second_wind_action(entity)
        if previous is not None:
            previous.fighter_level = level.resulting_class_level - 1
        raise


def remove_last_fighter_level(entity: Entity) -> AppliedClassLevel:
    """Remove the last applied Fighter row through its exact typed receipt."""
    if not entity.applied_class_levels:
        raise RuntimeError("entity has no applied class level")
    level = entity.applied_class_levels[-1]
    if level.class_id is not CharacterClass.FIGHTER:
        raise RuntimeError("the last applied class level is not Fighter")
    stored = entity.character_grant_receipt(level.step_id)
    receipt = cast(FighterGrantReceipt, stored)
    _remove_fighter_receipt(entity, receipt)
    entity.remove_character_grant_receipt(level.step_id)
    entity.applied_class_levels = entity.applied_class_levels[:-1]
    second_wind = _second_wind_action(entity)
    if second_wind is not None:
        second_wind.fighter_level = level.resulting_class_level - 1
    return level


__all__ = ["apply_fighter_level", "remove_last_fighter_level"]
