"""Direct Barbarian/Berserker component grants and exact cleanup."""

from typing import cast
from uuid import UUID, uuid5

from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.blocks.equipment import ArmorClassFormulaCandidate
from dnd.blocks.health import HitDice, HitDiceConfig
from dnd.classes import barbarian, feats, fighter, rage
from dnd.content.characters.class_definitions import (
    ResolvedBarbarianLevel,
    resolve_barbarian_level,
)
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.equipment_types import ArmorType, WeaponProperty
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.feature_grants import AttackMultiplicityGrant
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    ContextualAdvantageModifier,
    ContextualNumericalModifier,
    NumericalModifier,
)
from dnd.core.proficiency_types import ProficiencyMode
from dnd.entity import Entity
from dnd.types.abilities import AbilityName, SavingThrowName
from dnd.types.character_progression import AppliedClassLevel, CharacterClass
from dnd.types.character_receipts import BarbarianGrantReceipt


_RAGE = "class_feature.barbarian.rage"
_UNARMORED_DEFENSE = "class_feature.barbarian.unarmored_defense"
_RECKLESS_ATTACK = "class_feature.barbarian.reckless_attack"
_DANGER_SENSE = "class_feature.barbarian.danger_sense"
_EXTRA_ATTACK = "class_feature.extra_attack"
_FAST_MOVEMENT = "class_feature.barbarian.fast_movement"
_FERAL_INSTINCT = "class_feature.barbarian.feral_instinct"
_BRUTAL_CRITICAL = "class_feature.barbarian.brutal_critical"
_RELENTLESS_RAGE = "class_feature.barbarian.relentless_rage"
_PERSISTENT_RAGE = "class_feature.barbarian.persistent_rage"
_INDOMITABLE_MIGHT = "class_feature.barbarian.indomitable_might"
_PRIMAL_CHAMPION = "class_feature.barbarian.primal_champion"
_FRENZY = "class_feature.barbarian.frenzy"
_MINDLESS_RAGE = "class_feature.barbarian.mindless_rage"
_INTIMIDATING_PRESENCE = "class_feature.barbarian.intimidating_presence"
_RETALIATION = "class_feature.barbarian.retaliation"

_RAGE_USES = {
    1: 2,
    3: 3,
    6: 4,
    9: 4,
    12: 5,
    16: 5,
    17: 6,
    20: 999,
}


def _source(entity: Entity, identity: str) -> UUID:
    return uuid5(entity.uuid, f"dnd-engine:barbarian:v1:{identity}")


def _binding(
    entity: Entity,
    *,
    behavior_id: str,
    provided_by_id: str,
) -> BehaviorBinding:
    return BehaviorBinding(
        behavior_id=behavior_id,
        provided_by_id=provided_by_id,
        origin_root_id=CharacterClass.BARBARIAN.value,
        runtime_owner_uuid=entity.uuid,
    )


def _register_action(entity: Entity, actions: list[UUID], action) -> UUID:
    try:
        entity.register_action(action)
    except BaseException:
        action.remove_from_register()
        raise
    actions.append(action.uuid)
    return action.uuid


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


def _registered_action(entity: Entity, action_uuid: UUID):
    action = next(
        (
            candidate
            for candidate in entity.registered_actions
            if candidate.uuid == action_uuid
        ),
        None,
    )
    if action is None:
        raise RuntimeError(f"Barbarian action {action_uuid} is missing")
    return action


def _rage_action(entity: Entity):
    try:
        frenzy_receipt = cast(
            BarbarianGrantReceipt,
            entity.character_grant_receipt("class.barbarian.level_3"),
        )
    except KeyError:
        level_one = cast(
            BarbarianGrantReceipt,
            entity.character_grant_receipt("class.barbarian.level_1"),
        )
        if len(level_one.action_uuids) != 2:
            raise RuntimeError("Barbarian level 1 must own Rage and End Rage")
        return cast(rage.Rage, _registered_action(entity, level_one.action_uuids[0]))
    if len(frenzy_receipt.action_uuids) != 1:
        raise RuntimeError("Berserker level 3 must own exactly one Frenzy action")
    return cast(
        rage.Frenzy,
        _registered_action(entity, frenzy_receipt.action_uuids[0]),
    )


def _rage_damage(class_level: int) -> int:
    return 4 if class_level >= 16 else 3 if class_level >= 9 else 2


def _rage_configuration(entity: Entity, class_level: int) -> tuple[int, bool, bool]:
    return (
        _rage_damage(class_level),
        entity.has_feature(_MINDLESS_RAGE),
        entity.has_feature(_PERSISTENT_RAGE),
    )


def _update_rage_action(entity: Entity, class_level: int) -> None:
    if class_level < 1:
        return
    action = _rage_action(entity)
    damage, mindless, persistent = _rage_configuration(entity, class_level)
    action.rage_damage = damage
    action.mindless_rage = mindless
    action.persistent_rage = persistent


def _remove_rage_root(
    entity: Entity,
    action: rage.Rage | rage.Frenzy,
    parent_event: Event | None = None,
) -> None:
    root_uuid = action.active_raging_condition_uuid
    if root_uuid is None:
        return
    if not entity.remove_condition_by_uuid(root_uuid, parent_event=parent_event):
        raise RuntimeError("Barbarian Rage template lost its active root")
    if action.active_raging_condition_uuid is not None:
        raise RuntimeError("Raging cleanup did not release its template owner")


def _remove_reckless_root(
    entity: Entity,
    action: barbarian.RecklessAttack,
    parent_event: Event | None = None,
) -> None:
    root_uuid = action.active_reckless_condition_uuid
    if root_uuid is None:
        return
    if not entity.remove_condition_by_uuid(root_uuid, parent_event=parent_event):
        raise RuntimeError("Reckless Attack template lost its active root")
    if action.active_reckless_condition_uuid is not None:
        raise RuntimeError("Reckless cleanup did not release its template owner")


def _apply_proficiencies(
    entity: Entity,
    resolved: ResolvedBarbarianLevel,
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
            elif proficiency == "shield.shield":
                entity.creature_proficiencies.add_shield_source(source_id)
            else:
                raise ValueError(f"unsupported Barbarian proficiency {proficiency}")
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


def _apply_lucky(
    entity: Entity,
    resolved: ResolvedBarbarianLevel,
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
    resolved: ResolvedBarbarianLevel,
    *,
    actions: list[UUID],
    raging_root_owners: list[UUID],
    reckless_root_owners: list[UUID],
    handlers: list[UUID],
    resources: list[tuple[str, UUID]],
    armor_formulas: list[UUID],
    attack_grants: list[UUID],
    dex_save: list[UUID],
    walking: list[UUID],
    initiative: list[UUID],
    critical: list[UUID],
    immunities: list[tuple[str, UUID]],
    ability_modifiers: list[tuple[AbilityName, UUID]],
) -> tuple[UUID | None, int | None, int | None, bool | None, bool | None]:
    level = resolved.level.resulting_class_level
    step_id = resolved.level.step_id
    features = set(resolved.feature_ids)
    replacement: tuple[
        UUID | None,
        int | None,
        int | None,
        bool | None,
        bool | None,
    ] = (
        None,
        None,
        None,
        None,
        None,
    )

    if _UNARMORED_DEFENSE in features:
        source_id = _source(entity, f"{step_id}.{_UNARMORED_DEFENSE}")
        entity.equipment.add_armor_class_formula_candidate(
            ArmorClassFormulaCandidate(
                source_id=source_id,
                base_ac=10,
                ability_names=("dexterity", "constitution"),
                requires_unarmored=True,
                allows_shield=True,
            ),
        )
        armor_formulas.append(source_id)

    if _RAGE in features:
        uses = _RAGE_USES[level]
        source_id = _source(entity, f"{step_id}.{_RAGE}")
        entity.action_economy.add_resource_contribution(
            "rage",
            source_id,
            maximum=uses,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        resources.append(("rage", source_id))
        if level == 1:
            damage, mindless, persistent = _rage_configuration(entity, level)
            raging_root_owners.append(_register_action(
                entity,
                actions,
                rage.Rage(
                    uuid=_source(entity, f"{step_id}.{_RAGE}.action"),
                    source_entity_uuid=entity.uuid,
                    rage_damage=damage,
                    mindless_rage=mindless,
                    persistent_rage=persistent,
                    template=True,
                    semantic_key="action.class.barbarian.rage",
                    behavior_binding=_binding(
                        entity,
                        behavior_id="action.class.barbarian.rage",
                        provided_by_id=_RAGE,
                    ),
                ),
            ))
            _register_action(
                entity,
                actions,
                rage.EndRage(
                    uuid=_source(entity, f"{step_id}.{_RAGE}.end_action"),
                    source_entity_uuid=entity.uuid,
                    template=True,
                    semantic_key="action.class.barbarian.end_rage",
                    behavior_binding=_binding(
                        entity,
                        behavior_id="action.class.barbarian.end_rage",
                        provided_by_id=_RAGE,
                    ),
                ),
            )

    if _RECKLESS_ATTACK in features:
        reckless_root_owners.append(_register_action(
            entity,
            actions,
            barbarian.RecklessAttack(
                uuid=_source(entity, f"{step_id}.{_RECKLESS_ATTACK}.action"),
                source_entity_uuid=entity.uuid,
                template=True,
                semantic_key="action.class.barbarian.reckless_attack",
                behavior_binding=_binding(
                    entity,
                    behavior_id="action.class.barbarian.reckless_attack",
                    provided_by_id=_RECKLESS_ATTACK,
                ),
            ),
        ))
    if _DANGER_SENSE in features:
        modifier_id = _source(entity, f"{step_id}.{_DANGER_SENSE}")
        value = entity.saving_throws.get_saving_throw("dexterity").bonus
        value.self_contextual.add_advantage_modifier(ContextualAdvantageModifier(
            uuid=modifier_id,
            name="Danger Sense",
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            callable=barbarian.danger_sense_check,
        ))
        dex_save.append(modifier_id)
    if _EXTRA_ATTACK in features:
        source_id = _source(entity, f"{step_id}.{_EXTRA_ATTACK}")
        entity.action_economy.add_attack_multiplicity_grant(
            AttackMultiplicityGrant(
                grant_id=source_id,
                provider_id=_EXTRA_ATTACK,
                attacks_per_attack_action=2,
                acquisition_ordinal=resolved.level.character_level,
            ),
        )
        attack_grants.append(source_id)
        entity.action_economy.add_resource_contribution(
            "extra_attacks",
            source_id,
            maximum=1,
            recharge_type=RechargeType.TURN_START,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        resources.append(("extra_attacks", source_id))
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
    if _FAST_MOVEMENT in features:
        modifier_id = _source(entity, f"{step_id}.{_FAST_MOVEMENT}")
        entity.action_economy.movement.self_contextual.add_value_modifier(
            ContextualNumericalModifier(
                uuid=modifier_id,
                name="Fast Movement",
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                callable=barbarian.fast_movement_check,
            ),
        )
        walking.append(modifier_id)
    if _FERAL_INSTINCT in features:
        modifier_id = _source(entity, f"{step_id}.{_FERAL_INSTINCT}")
        entity.initiative.self_static.add_advantage_modifier(AdvantageModifier(
            uuid=modifier_id,
            name="Feral Instinct",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
        ))
        initiative.append(modifier_id)
    if _BRUTAL_CRITICAL in features:
        modifier_id = _source(entity, f"{step_id}.{_BRUTAL_CRITICAL}")
        entity.equipment.crit_extra_dice_melee.self_static.add_value_modifier(
            NumericalModifier(
                uuid=modifier_id,
                name="Brutal Critical",
                value=1,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
            ),
        )
        critical.append(modifier_id)
    if _RELENTLESS_RAGE in features:
        source_id = _source(entity, f"{step_id}.{_RELENTLESS_RAGE}")
        entity.action_economy.add_resource_contribution(
            "relentless_rage",
            source_id,
            maximum=999,
            recharge_type=RechargeType.SHORT_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        resources.append(("relentless_rage", source_id))
        _register_handler(
            entity,
            handlers,
            EventHandler(
                uuid=_source(
                    entity,
                    f"{step_id}.{_RELENTLESS_RAGE}.handler",
                ),
                name="Relentless Rage",
                semantic_key=_RELENTLESS_RAGE,
                source_entity_uuid=entity.uuid,
                trigger_conditions=[Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.EFFECT,
                )],
                event_processor=barbarian.relentless_rage_processor,
                behavior_binding=_binding(
                    entity,
                    behavior_id=_RELENTLESS_RAGE,
                    provided_by_id=_RELENTLESS_RAGE,
                ),
            ),
        )
    if _INDOMITABLE_MIGHT in features:
        handler = barbarian.create_indomitable_might_handler(
            entity.uuid,
            handler_uuid=_source(
                entity,
                f"{step_id}.{_INDOMITABLE_MIGHT}.handler",
            ),
        )
        handler.behavior_binding = _binding(
            entity,
            behavior_id=_INDOMITABLE_MIGHT,
            provided_by_id=_INDOMITABLE_MIGHT,
        )
        _register_handler(entity, handlers, handler)
    if _PRIMAL_CHAMPION in features:
        for ability in ("strength", "constitution"):
            modifier_id = _source(
                entity,
                f"{step_id}.{_PRIMAL_CHAMPION}.{ability}",
            )
            entity.ability_scores.get_ability(
                ability,
            ).ability_score.self_static.add_value_modifier(NumericalModifier(
                uuid=modifier_id,
                name=f"Primal Champion ({ability.upper()})",
                value=4,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
            ))
            ability_modifiers.append((ability, modifier_id))
    if _MINDLESS_RAGE in features:
        source_id = _source(entity, f"{step_id}.{_MINDLESS_RAGE}")
        for condition_name in ("Charmed", "Frightened"):
            entity.add_condition_immunity_source(
                condition_name,
                source_id,
                immunity_check=barbarian.mindless_rage_immunity_check,
            )
            immunities.append((condition_name, source_id))
    if _FRENZY in features:
        level_one = cast(
            BarbarianGrantReceipt,
            entity.character_grant_receipt("class.barbarian.level_1"),
        )
        rage_action = cast(
            rage.Rage,
            _registered_action(entity, level_one.action_uuids[0]),
        )
        rage_action_index = entity.registered_actions.index(rage_action)
        _remove_rage_root(entity, rage_action)
        replacement = (
            rage_action.uuid,
            rage_action_index,
            rage_action.rage_damage,
            rage_action.mindless_rage,
            rage_action.persistent_rage,
        )
        if not entity.unregister_action_by_uuid(rage_action.uuid):
            raise RuntimeError("Berserker could not replace its owned Rage action")
        damage, mindless, persistent = _rage_configuration(entity, level)
        try:
            raging_root_owners.append(_register_action(
                entity,
                actions,
                rage.Frenzy(
                    uuid=_source(entity, f"{step_id}.{_FRENZY}.action"),
                    source_entity_uuid=entity.uuid,
                    rage_damage=damage,
                    mindless_rage=mindless,
                    persistent_rage=persistent,
                    template=True,
                    semantic_key="action.class.barbarian.frenzy",
                    behavior_binding=_binding(
                        entity,
                        behavior_id="action.class.barbarian.frenzy",
                        provided_by_id=_FRENZY,
                    ),
                ),
            ))
        except BaseException:
            _restore_rage_action(
                entity,
                action_uuid=rage_action.uuid,
                action_index=rage_action_index,
                rage_damage=rage_action.rage_damage,
                mindless_rage=rage_action.mindless_rage,
                persistent_rage=rage_action.persistent_rage,
            )
            raise
    if _INTIMIDATING_PRESENCE in features:
        for action in (
            barbarian.IntimidatingPresence(
                uuid=_source(
                    entity,
                    f"{step_id}.{_INTIMIDATING_PRESENCE}.action",
                ),
                source_entity_uuid=entity.uuid,
                template=True,
                semantic_key="action.class.barbarian.intimidating_presence",
                behavior_binding=_binding(
                    entity,
                    behavior_id="action.class.barbarian.intimidating_presence",
                    provided_by_id=_INTIMIDATING_PRESENCE,
                ),
            ),
            barbarian.ExtendIntimidatingPresence(
                uuid=_source(
                    entity,
                    f"{step_id}.{_INTIMIDATING_PRESENCE}.extend_action",
                ),
                source_entity_uuid=entity.uuid,
                template=True,
                semantic_key=(
                    "action.class.barbarian.extend_intimidating_presence"
                ),
                behavior_binding=_binding(
                    entity,
                    behavior_id=(
                        "action.class.barbarian.extend_intimidating_presence"
                    ),
                    provided_by_id=_INTIMIDATING_PRESENCE,
                ),
            ),
        ):
            _register_action(entity, actions, action)
    if _RETALIATION in features:
        handler = barbarian.create_retaliation_handler(
            entity.uuid,
            handler_uuid=_source(entity, f"{step_id}.{_RETALIATION}.handler"),
        )
        handler.behavior_binding = _binding(
            entity,
            behavior_id="reaction.class_feature.barbarian.retaliation",
            provided_by_id=_RETALIATION,
        )
        _register_handler(entity, handlers, handler)

    return replacement


def _restore_rage_action(
    entity: Entity,
    *,
    action_uuid: UUID,
    action_index: int,
    rage_damage: int,
    mindless_rage: bool,
    persistent_rage: bool,
) -> None:
    if action_index > len(entity.registered_actions):
        raise RuntimeError("displaced Rage action index is no longer valid")
    restored = rage.Rage(
        uuid=action_uuid,
        source_entity_uuid=entity.uuid,
        rage_damage=rage_damage,
        mindless_rage=mindless_rage,
        persistent_rage=persistent_rage,
        template=True,
        semantic_key="action.class.barbarian.rage",
        behavior_binding=_binding(
            entity,
            behavior_id="action.class.barbarian.rage",
            provided_by_id=_RAGE,
        ),
    )
    try:
        entity.register_action(restored)
    except BaseException:
        restored.remove_from_register()
        raise
    if entity.registered_actions[-1] is not restored:
        raise RuntimeError("restored Rage action was not admitted at the tail")
    entity.registered_actions.pop()
    entity.registered_actions.insert(action_index, restored)


def _restore_replaced_rage(
    entity: Entity,
    receipt: BarbarianGrantReceipt,
) -> None:
    if receipt.replaced_rage_action_uuid is None:
        return
    _restore_rage_action(
        entity,
        action_uuid=receipt.replaced_rage_action_uuid,
        action_index=cast(int, receipt.replaced_rage_action_index),
        rage_damage=cast(int, receipt.replaced_rage_damage),
        mindless_rage=cast(bool, receipt.replaced_rage_mindless),
        persistent_rage=cast(bool, receipt.replaced_rage_persistent),
    )


def _barbarian_creature_source_is_owned(entity: Entity, source_id: UUID) -> bool:
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


def _validate_barbarian_receipt_ownership(
    entity: Entity,
    receipt: BarbarianGrantReceipt,
) -> None:
    """Fail before mutation when one Barbarian handle changed owner."""
    actions = {action.uuid: action for action in entity.registered_actions}
    for action_uuid in receipt.action_uuids:
        if action_uuid not in actions:
            raise RuntimeError("Barbarian action template is missing")
    for action_uuid in receipt.raging_root_owner_action_uuids:
        action = actions.get(action_uuid)
        if action is None:
            raise RuntimeError("Barbarian Rage root owner is missing")
        if action_uuid == _source(
            entity,
            f"{receipt.step_id}.{_RAGE}.action",
        ):
            expected_binding = _binding(
                entity,
                behavior_id="action.class.barbarian.rage",
                provided_by_id=_RAGE,
            )
        elif action_uuid == _source(
            entity,
            f"{receipt.step_id}.{_FRENZY}.action",
        ):
            expected_binding = _binding(
                entity,
                behavior_id="action.class.barbarian.frenzy",
                provided_by_id=_FRENZY,
            )
        else:
            raise RuntimeError("Barbarian Rage root ownership changed")
        if action.behavior_binding != expected_binding:
            raise RuntimeError("Barbarian Rage root ownership changed")
        _ = cast(rage.Rage | rage.Frenzy, action).active_raging_condition_uuid
    for action_uuid in receipt.reckless_root_owner_action_uuids:
        action = actions.get(action_uuid)
        if action is None:
            raise RuntimeError("Barbarian Reckless root owner is missing")
        binding = action.behavior_binding
        if binding != _binding(
            entity,
            behavior_id="action.class.barbarian.reckless_attack",
            provided_by_id=_RECKLESS_ATTACK,
        ):
            raise RuntimeError("Barbarian Reckless root ownership changed")
        _ = cast(barbarian.RecklessAttack, action).active_reckless_condition_uuid
    queue_handlers = {
        handler.uuid: handler
        for handler in EventQueue.get_handlers_by_source_entity(entity.uuid)
    }
    for handler_uuid in receipt.handler_uuids:
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None or queue_handlers.get(handler_uuid) is not handler:
            raise RuntimeError("Barbarian event handler ownership changed")
    for resource_name, source_id in receipt.resource_contributions:
        resource = entity.action_economy.resources.get(resource_name)
        if resource is None or str(source_id) not in resource.capacity_contributions:
            raise RuntimeError("Barbarian resource contribution ownership changed")
    attack_grants = {
        grant.grant_id
        for grant in entity.action_economy.get_attack_multiplicity_grants()
    }
    if any(
        grant_id not in attack_grants
        for grant_id in receipt.attack_multiplicity_grant_ids
    ):
        raise RuntimeError("Barbarian attack grant ownership changed")
    for condition_name, source_id in receipt.condition_immunity_sources:
        source_name = f"structural-source:{source_id}"
        static_owned = (condition_name, source_name) in entity.condition_immunities
        contextual_owned = any(
            name == source_name
            for name, _check in entity.contextual_condition_immunities.get(
                condition_name,
                (),
            )
        )
        if not static_owned and not contextual_owned:
            raise RuntimeError("Barbarian condition immunity ownership changed")
    for source_id in receipt.armor_class_formula_ids:
        if source_id not in entity.equipment.armor_class_formula_candidates:
            raise RuntimeError("Barbarian armor formula ownership changed")

    numerical_owners = (
        (entity.equipment.crit_extra_dice_melee.self_static.value_modifiers,
         receipt.melee_critical_extra_dice_modifier_ids),
    )
    for modifiers, modifier_ids in numerical_owners:
        for modifier_id in modifier_ids:
            modifier = modifiers.get(modifier_id)
            if modifier is None or NumericalModifier.get(modifier_id) is not modifier:
                raise RuntimeError("Barbarian numerical modifier ownership changed")
    for ability, modifier_id in receipt.ability_score_modifier_ids:
        modifiers = entity.ability_scores.get_ability(
            ability,
        ).ability_score.self_static.value_modifiers
        modifier = modifiers.get(modifier_id)
        if modifier is None or NumericalModifier.get(modifier_id) is not modifier:
            raise RuntimeError("Barbarian ability modifier ownership changed")
    for modifier_id in receipt.initiative_advantage_modifier_ids:
        modifiers = entity.initiative.self_static.advantage_modifiers
        modifier = modifiers.get(modifier_id)
        if modifier is None or AdvantageModifier.get(modifier_id) is not modifier:
            raise RuntimeError("Barbarian initiative modifier ownership changed")
    for modifier_id in receipt.walking_speed_modifier_ids:
        modifiers = entity.action_economy.movement.self_contextual.value_modifiers
        modifier = modifiers.get(modifier_id)
        if (
            modifier is None
            or ContextualNumericalModifier.get(modifier_id) is not modifier
        ):
            raise RuntimeError("Barbarian movement modifier ownership changed")
    for modifier_id in receipt.dexterity_save_advantage_modifier_ids:
        modifiers = entity.saving_throws.dexterity_saving_throw.bonus.self_contextual.advantage_modifiers
        modifier = modifiers.get(modifier_id)
        if (
            modifier is None
            or ContextualAdvantageModifier.get(modifier_id) is not modifier
        ):
            raise RuntimeError("Barbarian save modifier ownership changed")

    for feature_id, source_id in receipt.feature_sources:
        if source_id not in entity.feature_sources.get(feature_id, set()):
            raise RuntimeError("Barbarian feature source ownership changed")
    for source_id in receipt.creature_proficiency_source_ids:
        if not _barbarian_creature_source_is_owned(entity, source_id):
            raise RuntimeError("Barbarian creature proficiency ownership changed")
    for saving_throw, source_id in receipt.saving_throw_proficiency_sources:
        if source_id not in entity.saving_throws.get_saving_throw(
            saving_throw.removesuffix("_saving_throw"),
        ).proficiency_sources.sources:
            raise RuntimeError("Barbarian saving-throw source ownership changed")
    for skill, source_id in receipt.skill_proficiency_sources:
        if source_id not in entity.skill_set.get_skill(
            skill,
        ).proficiency_sources.sources:
            raise RuntimeError("Barbarian skill source ownership changed")
    hit_dice = {hit_die.uuid: hit_die for hit_die in entity.health.hit_dices}
    for hit_die_uuid in receipt.hit_die_uuids:
        hit_die = hit_dice.get(hit_die_uuid)
        if hit_die is None or hit_die.source_entity_uuid != entity.uuid:
            raise RuntimeError("Barbarian hit-die ownership changed")
    if receipt.replaced_rage_action_uuid is not None:
        if receipt.replaced_rage_action_uuid in actions:
            raise RuntimeError("displaced Rage identity is unexpectedly live")
        if cast(int, receipt.replaced_rage_action_index) > len(actions):
            raise RuntimeError("displaced Rage action index is no longer valid")


def _remove_barbarian_receipt(
    entity: Entity,
    receipt: BarbarianGrantReceipt,
    parent_event: Event | None = None,
) -> None:
    _validate_barbarian_receipt_ownership(entity, receipt)
    for handler_uuid in reversed(receipt.handler_uuids):
        handler = entity.event_handlers.get(handler_uuid)
        if handler is None:
            raise RuntimeError("Barbarian event handler is missing")
        entity.remove_event_handler(handler)
        handler.remove_from_register()
    for action_uuid in reversed(receipt.action_uuids):
        action = _registered_action(entity, action_uuid)
        if action_uuid in receipt.raging_root_owner_action_uuids:
            _remove_rage_root(
                entity,
                cast(rage.Rage | rage.Frenzy, action),
                parent_event,
            )
        elif action_uuid in receipt.reckless_root_owner_action_uuids:
            _remove_reckless_root(
                entity,
                cast(barbarian.RecklessAttack, action),
                parent_event,
            )
        if not entity.unregister_action_by_uuid(action_uuid):
            raise RuntimeError("Barbarian action template is missing")
    _restore_replaced_rage(entity, receipt)
    for resource_name, source_id in reversed(receipt.resource_contributions):
        if not entity.action_economy.remove_resource_contribution(
            resource_name,
            source_id,
        ):
            raise RuntimeError("Barbarian resource contribution is missing")
    for source_id in reversed(receipt.attack_multiplicity_grant_ids):
        if not entity.action_economy.remove_attack_multiplicity_grant(source_id):
            raise RuntimeError("Barbarian attack grant is missing")
    for condition_name, source_id in reversed(receipt.condition_immunity_sources):
        if not entity.remove_condition_immunity_source(condition_name, source_id):
            raise RuntimeError("Barbarian condition immunity source is missing")
    for source_id in reversed(receipt.armor_class_formula_ids):
        if not entity.equipment.remove_armor_class_formula_candidate(source_id):
            raise RuntimeError("Barbarian armor formula source is missing")
    for modifier_id in reversed(receipt.melee_critical_extra_dice_modifier_ids):
        entity.equipment.crit_extra_dice_melee.self_static.remove_value_modifier(
            modifier_id,
        )
        NumericalModifier.unregister(modifier_id)
    for modifier_id in reversed(receipt.initiative_advantage_modifier_ids):
        entity.initiative.self_static.remove_advantage_modifier(modifier_id)
        AdvantageModifier.unregister(modifier_id)
    for modifier_id in reversed(receipt.walking_speed_modifier_ids):
        entity.action_economy.movement.self_contextual.remove_value_modifier(
            modifier_id,
        )
        ContextualNumericalModifier.unregister(modifier_id)
    for modifier_id in reversed(receipt.dexterity_save_advantage_modifier_ids):
        entity.saving_throws.dexterity_saving_throw.bonus.self_contextual.remove_advantage_modifier(
            modifier_id,
        )
        ContextualAdvantageModifier.unregister(modifier_id)
    for ability, modifier_id in reversed(receipt.ability_score_modifier_ids):
        entity.ability_scores.get_ability(
            ability,
        ).ability_score.self_static.remove_value_modifier(modifier_id)
        NumericalModifier.unregister(modifier_id)
    for feature_id, source_id in reversed(receipt.feature_sources):
        if not entity.remove_feature_source(feature_id, source_id):
            raise RuntimeError("Barbarian feature source is missing")
    for source_id in reversed(receipt.creature_proficiency_source_ids):
        if not entity.creature_proficiencies.remove_source(source_id):
            raise RuntimeError("Barbarian creature proficiency source is missing")
    for saving_throw, source_id in reversed(
        receipt.saving_throw_proficiency_sources,
    ):
        if not entity.saving_throws.get_saving_throw(
            saving_throw.removesuffix("_saving_throw"),
        ).remove_proficiency_source(source_id):
            raise RuntimeError("Barbarian saving-throw source is missing")
    for skill, source_id in reversed(receipt.skill_proficiency_sources):
        if not entity.skill_set.get_skill(skill).remove_proficiency_source(source_id):
            raise RuntimeError("Barbarian skill source is missing")
    for hit_die_uuid in reversed(receipt.hit_die_uuids):
        if not entity.health.remove_hit_dice_by_uuid(hit_die_uuid):
            raise RuntimeError("Barbarian hit die is missing")


def apply_barbarian_level(
    entity: Entity,
    level: AppliedClassLevel,
    *,
    initial_first_class: bool | None = None,
) -> BarbarianGrantReceipt:
    """Apply one next resolved Barbarian/Berserker row."""
    resolved = resolve_barbarian_level(
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
        raise RuntimeError(f"Barbarian receipt {level.step_id} is already installed")

    source_id = _source(entity, level.step_id)
    hit_dice: list[UUID] = []
    skills: list[tuple[str, UUID]] = []
    saves: list[tuple[SavingThrowName, UUID]] = []
    creature_sources: list[UUID] = []
    ability_modifiers: list[tuple[AbilityName, UUID]] = []
    dex_save: list[UUID] = []
    walking: list[UUID] = []
    initiative: list[UUID] = []
    critical: list[UUID] = []
    actions: list[UUID] = []
    raging_root_owners: list[UUID] = []
    reckless_root_owners: list[UUID] = []
    handlers: list[UUID] = []
    resources: list[tuple[str, UUID]] = []
    armor_formulas: list[UUID] = []
    attack_grants: list[UUID] = []
    immunities: list[tuple[str, UUID]] = []
    features: list[tuple[str, UUID]] = []
    replacement: tuple[
        UUID | None,
        int | None,
        int | None,
        bool | None,
        bool | None,
    ] = (
        None,
        None,
        None,
        None,
        None,
    )
    receipt_stored = False
    state_stored = False

    def receipt() -> BarbarianGrantReceipt:
        return BarbarianGrantReceipt(
            step_id=level.step_id,
            source_id=source_id,
            hit_die_uuids=tuple(hit_dice),
            skill_proficiency_sources=tuple(skills),
            saving_throw_proficiency_sources=tuple(saves),
            creature_proficiency_source_ids=tuple(creature_sources),
            ability_score_modifier_ids=tuple(ability_modifiers),
            dexterity_save_advantage_modifier_ids=tuple(dex_save),
            walking_speed_modifier_ids=tuple(walking),
            initiative_advantage_modifier_ids=tuple(initiative),
            melee_critical_extra_dice_modifier_ids=tuple(critical),
            action_uuids=tuple(actions),
            raging_root_owner_action_uuids=tuple(raging_root_owners),
            reckless_root_owner_action_uuids=tuple(reckless_root_owners),
            handler_uuids=tuple(handlers),
            resource_contributions=tuple(resources),
            armor_class_formula_ids=tuple(armor_formulas),
            attack_multiplicity_grant_ids=tuple(attack_grants),
            condition_immunity_sources=tuple(immunities),
            feature_sources=tuple(features),
            replaced_rage_action_uuid=replacement[0],
            replaced_rage_action_index=replacement[1],
            replaced_rage_damage=replacement[2],
            replaced_rage_mindless=replacement[3],
            replaced_rage_persistent=replacement[4],
        )

    try:
        hit_die = HitDice.create(
            source_entity_uuid=entity.uuid,
            name=level.step_id,
            config=HitDiceConfig(
                hit_dice_value=12,
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
                name=f"Barbarian level {level.resulting_class_level} ASI",
                value=amount,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
            ))
            ability_modifiers.append((ability, modifier_id))
        for feature_id in resolved.feature_ids:
            feature_source = _source(
                entity,
                f"{level.step_id}.feature.{feature_id}",
            )
            entity.add_feature_source(feature_id, feature_source)
            features.append((feature_id, feature_source))
        _apply_lucky(entity, resolved, resources, handlers)
        replacement = _apply_level_features(
            entity,
            resolved,
            actions=actions,
            raging_root_owners=raging_root_owners,
            reckless_root_owners=reckless_root_owners,
            handlers=handlers,
            resources=resources,
            armor_formulas=armor_formulas,
            attack_grants=attack_grants,
            dex_save=dex_save,
            walking=walking,
            initiative=initiative,
            critical=critical,
            immunities=immunities,
            ability_modifiers=ability_modifiers,
        )
        completed = receipt()
        entity.store_character_grant_receipt(completed)
        receipt_stored = True
        entity.applied_class_levels = (*entity.applied_class_levels, level)
        state_stored = True
        _update_rage_action(entity, level.resulting_class_level)
        return completed
    except BaseException:
        if state_stored:
            entity.applied_class_levels = entity.applied_class_levels[:-1]
        if receipt_stored:
            entity.remove_character_grant_receipt(level.step_id)
        _remove_barbarian_receipt(entity, receipt())
        remaining = level.resulting_class_level - 1
        if remaining >= 1:
            _update_rage_action(entity, remaining)
        raise


def barbarian_level_has_active_child(entity: Entity) -> bool:
    """Return whether removing the last Barbarian row commits child facts."""
    if not entity.applied_class_levels:
        return False
    level = entity.applied_class_levels[-1]
    if level.class_id is not CharacterClass.BARBARIAN:
        return False
    receipt = cast(
        BarbarianGrantReceipt,
        entity.character_grant_receipt(level.step_id),
    )
    _validate_barbarian_receipt_ownership(entity, receipt)
    for action_uuid in receipt.raging_root_owner_action_uuids:
        action = _registered_action(entity, action_uuid)
        if cast(
            rage.Rage | rage.Frenzy,
            action,
        ).active_raging_condition_uuid is not None:
            return True
    for action_uuid in receipt.reckless_root_owner_action_uuids:
        action = _registered_action(entity, action_uuid)
        if cast(
            barbarian.RecklessAttack,
            action,
        ).active_reckless_condition_uuid is not None:
            return True
    if level.resulting_class_level <= 1:
        return False
    rage_action = _rage_action(entity)
    if rage_action.active_raging_condition_uuid is None:
        return False
    removed_feature_sources = {
        feature_id: source_id
        for feature_id, source_id in receipt.feature_sources
    }
    desired_configuration = (
        _rage_damage(level.resulting_class_level - 1),
        bool(
            entity.feature_sources.get(_MINDLESS_RAGE, set())
            - {removed_feature_sources.get(_MINDLESS_RAGE)}
        ),
        bool(
            entity.feature_sources.get(_PERSISTENT_RAGE, set())
            - {removed_feature_sources.get(_PERSISTENT_RAGE)}
        ),
    )
    return (
        rage_action.rage_damage,
        rage_action.mindless_rage,
        rage_action.persistent_rage,
    ) != desired_configuration


def remove_last_barbarian_level(
    entity: Entity,
    *,
    parent_event: Event | None = None,
) -> AppliedClassLevel:
    """Remove the last applied Barbarian row through its exact receipt."""
    if not entity.applied_class_levels:
        raise RuntimeError("entity has no applied class level")
    level = entity.applied_class_levels[-1]
    if level.class_id is not CharacterClass.BARBARIAN:
        raise RuntimeError("the last applied class level is not Barbarian")
    stored = entity.character_grant_receipt(level.step_id)
    receipt = cast(BarbarianGrantReceipt, stored)
    _validate_barbarian_receipt_ownership(entity, receipt)
    if level.resulting_class_level > 1:
        action = _rage_action(entity)
        removed_feature_sources = {
            feature_id: source_id
            for feature_id, source_id in receipt.feature_sources
        }
        desired_configuration = (
            _rage_damage(level.resulting_class_level - 1),
            bool(
                entity.feature_sources.get(_MINDLESS_RAGE, set())
                - {removed_feature_sources.get(_MINDLESS_RAGE)}
            ),
            bool(
                entity.feature_sources.get(_PERSISTENT_RAGE, set())
                - {removed_feature_sources.get(_PERSISTENT_RAGE)}
            ),
        )
        current_configuration = (
            action.rage_damage,
            action.mindless_rage,
            action.persistent_rage,
        )
        if current_configuration != desired_configuration:
            _remove_rage_root(entity, action, parent_event)
    _remove_barbarian_receipt(entity, receipt, parent_event)
    entity.remove_character_grant_receipt(level.step_id)
    entity.applied_class_levels = entity.applied_class_levels[:-1]
    if level.resulting_class_level > 1:
        _update_rage_action(entity, level.resulting_class_level - 1)
    return level


__all__ = [
    "apply_barbarian_level",
    "barbarian_level_has_active_child",
    "remove_last_barbarian_level",
]
