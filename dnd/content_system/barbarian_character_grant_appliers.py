"""Reversible Barbarian and Berserker structural feature grants.

Character composition owns the permanent actions, handlers, resources,
formulae, and modifiers installed here.  Evented states such as ``Raging`` and
``RecklessAttacking`` remain conditions, but no permanent feature condition is
created merely to hold cold character structure.
"""

from collections.abc import Callable
from uuid import UUID

from dnd.blocks.action_economy import (
    RechargeType,
    ResourceCapacityPolicy,
)
from dnd.blocks.equipment import ArmorClassFormulaCandidate
from dnd.classes import barbarian, rage
from dnd.classes.barbarian_progression_definitions import BARBARIAN_CLASS_REF
from dnd.classes.structural_feature_definitions import (
    UNARMORED_DEFENSE_DECLARATION,
)
from dnd.content_system.character_build_validation import (
    CharacterGrantScheduleEntry,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_applier_runtime import (
    character_grant_id,
    grant_receipt,
    install_bound_handler,
    is_first_grant_for_ref,
    register_bound_action,
    require_grant_ref,
    validated_class_level,
)
from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    ConditionImmunityHandle,
    ModifierHandle,
    ModifierHandleChannel,
    ModifierHandleKind,
)
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.core.content.identities import ContentRef
from dnd.core.base_actions import BaseAction
from dnd.core.events import EventHandler, EventPhase, EventType, Trigger
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    ContextualAdvantageModifier,
    ContextualNumericalModifier,
    NumericalModifier,
)
from dnd.core.values import ModifiableValue


RAGE_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[rage.RageFeature].ref
RECKLESS_ATTACK_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.RecklessAttackFeature
].ref
DANGER_SENSE_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.DangerSense
].ref
FAST_MOVEMENT_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.FastMovement
].ref
MINDLESS_RAGE_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.MindlessRage
].ref
FERAL_INSTINCT_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.FeralInstinct
].ref
BRUTAL_CRITICAL_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.BrutalCritical
].ref
RELENTLESS_RAGE_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.RelentlessRage
].ref
PERSISTENT_RAGE_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.PersistentRage
].ref
INDOMITABLE_MIGHT_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.IndomitableMight
].ref
PRIMAL_CHAMPION_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.PrimalChampion
].ref
FRENZY_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    rage.FrenzyFeature
].ref
INTIMIDATING_PRESENCE_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.IntimidatingPresenceFeature
].ref
RETALIATION_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.Retaliation
].ref

RAGING_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[rage.Raging].ref
FRENZIED_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[rage.Frenzied].ref
RECKLESS_ATTACKING_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    barbarian.RecklessAttacking
].ref


BarbarianCharacterGrantApplier = Callable[
    [BuiltinCharacterGrantContext, CharacterGrantScheduleEntry],
    CharacterGrantReceipt,
]


def _preview_has(
    context: BuiltinCharacterGrantContext,
    content_ref: ContentRef,
) -> bool:
    return any(
        ref == content_ref
        for ref in context.preview.automatic_grant_refs
    )


def _install_static_value(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    *,
    value: ModifiableValue,
    amount: int,
    name: str,
) -> CharacterGrantReceipt:
    modifier = NumericalModifier.create(
        source_entity_uuid=context.entity.uuid,
        name=name,
        value=amount,
    )
    value.self_static.add_value_modifier(modifier)
    return grant_receipt(
        context,
        entry,
        modifier_handles=(
            ModifierHandle(
                value_uuid=value.uuid,
                modifier_uuid=modifier.uuid,
            ),
        ),
    )


def _apply_unarmored_defense(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, UNARMORED_DEFENSE_DECLARATION.ref)
    source_id = character_grant_id(context, entry)
    context.entity.equipment.add_armor_class_formula_candidate(
        ArmorClassFormulaCandidate(
            source_id=source_id,
            base_ac=10,
            ability_names=("dexterity", "constitution"),
            requires_unarmored=True,
            allows_shield=True,
        ),
    )
    return grant_receipt(
        context,
        entry,
        armor_class_formula_ids=(source_id,),
    )


_RAGE_ADVANCEMENT: dict[int, tuple[int, int]] = {
    1: (2, 2),
    3: (3, 2),
    6: (4, 2),
    9: (4, 3),
    12: (5, 3),
    16: (5, 4),
    17: (6, 4),
    20: (999, 4),
}


def _apply_rage(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, RAGE_REF)
    class_level = entry.provenance.class_level
    if class_level not in _RAGE_ADVANCEMENT:
        raise ValueError(f"Unsupported Rage advancement level {class_level}")
    rage_uses, _rage_damage = _RAGE_ADVANCEMENT[class_level]
    grant_id = character_grant_id(context, entry)
    entity = context.entity
    entity.action_economy.add_resource_contribution(
        "rage",
        grant_id,
        maximum=rage_uses,
        recharge_type=RechargeType.LONG_REST,
        capacity_policy=ResourceCapacityPolicy.MAXIMUM,
    )

    action_uuids: tuple[UUID, ...] = ()
    try:
        if is_first_grant_for_ref(context, entry):
            actions: list[BaseAction] = [
                rage.EndRage(
                    source_entity_uuid=entity.uuid,
                    template=True,
                ),
            ]
            if not _preview_has(context, FRENZY_REF):
                actions.insert(
                    0,
                    rage.Rage(
                        source_entity_uuid=entity.uuid,
                        rage_damage=(
                            4
                            if validated_class_level(
                                context,
                                BARBARIAN_CLASS_REF,
                            )
                            >= 16
                            else 3
                            if validated_class_level(
                                context,
                                BARBARIAN_CLASS_REF,
                            )
                            >= 9
                            else 2
                        ),
                        mindless_rage=_preview_has(
                            context,
                            MINDLESS_RAGE_REF,
                        ),
                        persistent_rage=_preview_has(
                            context,
                            PERSISTENT_RAGE_REF,
                        ),
                        template=True,
                    ),
                )
            installed: list[UUID] = []
            try:
                for action in actions:
                    register_bound_action(
                        context,
                        provider_ref=RAGE_REF,
                        action=action,
                    )
                    installed.append(action.uuid)
            except Exception:
                for action_uuid in reversed(installed):
                    entity.unregister_action_by_uuid(action_uuid)
                raise
            action_uuids = tuple(installed)
    except Exception:
        entity.action_economy.remove_resource_contribution("rage", grant_id)
        raise

    return grant_receipt(
        context,
        entry,
        action_uuids=action_uuids,
        resource_contribution_ids=(("rage", grant_id),),
        transient_condition_refs_to_remove=(RAGING_REF, FRENZIED_REF),
    )


def _apply_reckless_attack(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, RECKLESS_ATTACK_REF)
    action = barbarian.RecklessAttack(
        source_entity_uuid=context.entity.uuid,
        template=True,
    )
    register_bound_action(
        context,
        provider_ref=RECKLESS_ATTACK_REF,
        action=action,
    )
    return grant_receipt(
        context,
        entry,
        action_uuids=(action.uuid,),
        transient_condition_refs_to_remove=(RECKLESS_ATTACKING_REF,),
    )


def _apply_danger_sense(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, DANGER_SENSE_REF)
    value = context.entity.saving_throws.get_saving_throw("dexterity").bonus
    modifier = ContextualAdvantageModifier(
        name="Danger Sense",
        source_entity_uuid=context.entity.uuid,
        target_entity_uuid=context.entity.uuid,
        callable=barbarian.danger_sense_check,
    )
    value.self_contextual.add_advantage_modifier(modifier)
    return grant_receipt(
        context,
        entry,
        modifier_handles=(
            ModifierHandle(
                value_uuid=value.uuid,
                modifier_uuid=modifier.uuid,
                channel=ModifierHandleChannel.SELF_CONTEXTUAL,
                kind=ModifierHandleKind.ADVANTAGE,
            ),
        ),
    )


def _apply_fast_movement(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, FAST_MOVEMENT_REF)
    value = context.entity.action_economy.movement
    modifier = ContextualNumericalModifier(
        name="Fast Movement",
        source_entity_uuid=context.entity.uuid,
        target_entity_uuid=context.entity.uuid,
        callable=barbarian.fast_movement_check,
    )
    value.self_contextual.add_value_modifier(modifier)
    return grant_receipt(
        context,
        entry,
        modifier_handles=(
            ModifierHandle(
                value_uuid=value.uuid,
                modifier_uuid=modifier.uuid,
                channel=ModifierHandleChannel.SELF_CONTEXTUAL,
            ),
        ),
    )


def _apply_mindless_rage(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, MINDLESS_RAGE_REF)
    source_id = character_grant_id(context, entry)
    entity = context.entity
    handles: list[ConditionImmunityHandle] = []
    try:
        for condition_name in ("Charmed", "Frightened"):
            entity.add_condition_immunity_source(
                condition_name,
                source_id,
                immunity_check=barbarian.mindless_rage_immunity_check,
            )
            handles.append(
                ConditionImmunityHandle(
                    block_uuid=entity.uuid,
                    condition_name=condition_name,
                    source_id=source_id,
                ),
            )
    except Exception:
        for handle in reversed(handles):
            entity.remove_condition_immunity_source(
                handle.condition_name,
                handle.source_id,
            )
        raise
    return grant_receipt(
        context,
        entry,
        condition_immunity_handles=tuple(handles),
        transient_condition_refs_to_remove=(RAGING_REF, FRENZIED_REF),
    )


def _apply_feral_instinct(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, FERAL_INSTINCT_REF)
    value = context.entity.initiative
    modifier = AdvantageModifier(
        name="Feral Instinct",
        value=AdvantageStatus.ADVANTAGE,
        source_entity_uuid=context.entity.uuid,
        target_entity_uuid=context.entity.uuid,
    )
    value.self_static.add_advantage_modifier(modifier)
    return grant_receipt(
        context,
        entry,
        modifier_handles=(
            ModifierHandle(
                value_uuid=value.uuid,
                modifier_uuid=modifier.uuid,
                kind=ModifierHandleKind.ADVANTAGE,
            ),
        ),
    )


def _apply_brutal_critical(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, BRUTAL_CRITICAL_REF)
    return _install_static_value(
        context,
        entry,
        value=context.entity.equipment.crit_extra_dice_melee,
        amount=1,
        name="Brutal Critical",
    )


def _apply_relentless_rage(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, RELENTLESS_RAGE_REF)
    entity = context.entity
    grant_id = character_grant_id(context, entry)
    entity.action_economy.add_resource_contribution(
        "relentless_rage",
        grant_id,
        maximum=999,
        recharge_type=RechargeType.SHORT_REST,
        capacity_policy=ResourceCapacityPolicy.MAXIMUM,
    )
    handler = EventHandler(
        name="Relentless Rage",
        source_entity_uuid=entity.uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TAKE_DAMAGE,
                event_phase=EventPhase.EFFECT,
            ),
        ],
        event_processor=barbarian.relentless_rage_processor,
    )
    try:
        context.runtime.bind_granted_behavior(
            handler,
            provider_id=RELENTLESS_RAGE_REF.content_id,
            runtime_owner_uuid=entity.uuid,
        )
        entity.add_event_handler(handler)
    except Exception:
        entity.action_economy.remove_resource_contribution(
            "relentless_rage",
            grant_id,
        )
        raise
    return grant_receipt(
        context,
        entry,
        handler_uuids=(handler.uuid,),
        resource_contribution_ids=(("relentless_rage", grant_id),),
    )


def _apply_persistent_rage(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, PERSISTENT_RAGE_REF)
    return grant_receipt(
        context,
        entry,
        transient_condition_refs_to_remove=(RAGING_REF, FRENZIED_REF),
    )


def _apply_indomitable_might(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, INDOMITABLE_MIGHT_REF)
    return install_bound_handler(
        context,
        entry,
        barbarian.create_indomitable_might_handler(context.entity.uuid),
    )


def _apply_primal_champion(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, PRIMAL_CHAMPION_REF)
    entity = context.entity
    installed: list[tuple[ModifiableValue, NumericalModifier]] = []
    handles: list[ModifierHandle] = []
    try:
        for name, value in (
            ("Primal Champion (STR)", entity.ability_scores.strength.ability_score),
            ("Primal Champion (CON)", entity.ability_scores.constitution.ability_score),
        ):
            modifier = NumericalModifier.create(
                source_entity_uuid=entity.uuid,
                name=name,
                value=4,
            )
            value.self_static.add_value_modifier(modifier)
            installed.append((value, modifier))
            handles.append(
                ModifierHandle(
                    value_uuid=value.uuid,
                    modifier_uuid=modifier.uuid,
                ),
            )
    except Exception:
        for value, modifier in reversed(installed):
            value.self_static.remove_value_modifier(modifier.uuid)
        raise
    return grant_receipt(
        context,
        entry,
        modifier_handles=tuple(handles),
    )


def _apply_frenzy(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, FRENZY_REF)
    barbarian_level = validated_class_level(
        context,
        BARBARIAN_CLASS_REF,
    )
    action = rage.Frenzy(
        source_entity_uuid=context.entity.uuid,
        rage_damage=4 if barbarian_level >= 16 else 3 if barbarian_level >= 9 else 2,
        mindless_rage=_preview_has(context, MINDLESS_RAGE_REF),
        persistent_rage=_preview_has(context, PERSISTENT_RAGE_REF),
        template=True,
    )
    register_bound_action(
        context,
        provider_ref=FRENZY_REF,
        action=action,
    )
    return grant_receipt(
        context,
        entry,
        action_uuids=(action.uuid,),
        transient_condition_refs_to_remove=(RAGING_REF, FRENZIED_REF),
    )


def _apply_intimidating_presence(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, INTIMIDATING_PRESENCE_REF)
    actions = (
        barbarian.IntimidatingPresence(
            source_entity_uuid=context.entity.uuid,
            template=True,
        ),
        barbarian.ExtendIntimidatingPresence(
            source_entity_uuid=context.entity.uuid,
            template=True,
        ),
    )
    installed: list[UUID] = []
    try:
        for action in actions:
            register_bound_action(
                context,
                provider_ref=INTIMIDATING_PRESENCE_REF,
                action=action,
            )
            installed.append(action.uuid)
    except Exception:
        for action_uuid in reversed(installed):
            context.entity.unregister_action_by_uuid(action_uuid)
        raise
    return grant_receipt(
        context,
        entry,
        action_uuids=tuple(installed),
    )


def _apply_retaliation(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, RETALIATION_REF)
    return install_bound_handler(
        context,
        entry,
        barbarian.create_retaliation_handler(context.entity.uuid),
    )


BARBARIAN_CHARACTER_GRANT_APPLIERS: dict[
    str,
    BarbarianCharacterGrantApplier,
] = {
    UNARMORED_DEFENSE_DECLARATION.ref.identity_key: _apply_unarmored_defense,
    RAGE_REF.identity_key: _apply_rage,
    RECKLESS_ATTACK_REF.identity_key: _apply_reckless_attack,
    DANGER_SENSE_REF.identity_key: _apply_danger_sense,
    FAST_MOVEMENT_REF.identity_key: _apply_fast_movement,
    MINDLESS_RAGE_REF.identity_key: _apply_mindless_rage,
    FERAL_INSTINCT_REF.identity_key: _apply_feral_instinct,
    BRUTAL_CRITICAL_REF.identity_key: _apply_brutal_critical,
    RELENTLESS_RAGE_REF.identity_key: _apply_relentless_rage,
    PERSISTENT_RAGE_REF.identity_key: _apply_persistent_rage,
    INDOMITABLE_MIGHT_REF.identity_key: _apply_indomitable_might,
    PRIMAL_CHAMPION_REF.identity_key: _apply_primal_champion,
    FRENZY_REF.identity_key: _apply_frenzy,
    INTIMIDATING_PRESENCE_REF.identity_key: _apply_intimidating_presence,
    RETALIATION_REF.identity_key: _apply_retaliation,
}


__all__ = [
    "BARBARIAN_CHARACTER_GRANT_APPLIERS",
    "BRUTAL_CRITICAL_REF",
    "DANGER_SENSE_REF",
    "FAST_MOVEMENT_REF",
    "FERAL_INSTINCT_REF",
    "FRENZY_REF",
    "INDOMITABLE_MIGHT_REF",
    "INTIMIDATING_PRESENCE_REF",
    "MINDLESS_RAGE_REF",
    "PERSISTENT_RAGE_REF",
    "PRIMAL_CHAMPION_REF",
    "RAGE_REF",
    "RECKLESS_ATTACK_REF",
    "RELENTLESS_RAGE_REF",
    "RETALIATION_REF",
]
