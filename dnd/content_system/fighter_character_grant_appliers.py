"""Reversible Fighter and Champion structural feature grants.

The authored feature definitions remain the exact providers for every action
and handler installed here.  Character composition owns the runtime handles;
no permanent ``BaseCondition`` is created merely to reuse its old lifecycle.
"""

from collections.abc import Callable
from uuid import UUID, uuid5

from dnd.blocks.action_economy import (
    RechargeType,
    ResourceCapacityPolicy,
)
from dnd.classes import feats, fighter
from dnd.classes.progression_definitions import FIGHTER_CLASS_REF
from dnd.content_system.character_build_validation import (
    CharacterGrantScheduleEntry,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    ModifierHandle,
    ModifierHandleChannel,
)
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.core.content.identities import ContentRef
from dnd.core.events import (
    EventHandler,
    EventPhase,
    EventType,
    Trigger,
)
from dnd.core.modifiers import (
    ContextualNumericalModifier,
    NumericalModifier,
)
from dnd.core.values import ModifiableValue


FIGHTING_STYLE_ARCHERY_REF = (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
        fighter.FightingStyleArchery
    ].ref
)
FIGHTING_STYLE_DEFENSE_REF = (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
        fighter.FightingStyleDefense
    ].ref
)
FIGHTING_STYLE_DUELING_REF = (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
        fighter.FightingStyleDueling
    ].ref
)
FIGHTING_STYLE_GREAT_WEAPON_REF = (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
        fighter.GreatWeaponFighting
    ].ref
)
FIGHTING_STYLE_PROTECTION_REF = (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
        fighter.FightingStyleProtection
    ].ref
)
FIGHTING_STYLE_TWO_WEAPON_REF = (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
        fighter.FightingStyleTwoWeaponFighting
    ].ref
)
SECOND_WIND_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    fighter.SecondWindFeature
].ref
ACTION_SURGE_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    fighter.ActionSurgeFeature
].ref
IMPROVED_CRITICAL_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    fighter.ImprovedCritical
].ref
SUPERIOR_CRITICAL_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    fighter.SuperiorCritical
].ref
INDOMITABLE_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    fighter.Indomitable
].ref
SURVIVOR_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    fighter.Survivor
].ref
LUCKY_FEAT_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    feats.LuckyFeature
].ref


FighterCharacterGrantApplier = Callable[
    [BuiltinCharacterGrantContext, CharacterGrantScheduleEntry],
    CharacterGrantReceipt,
]


def _require_ref(
    entry: CharacterGrantScheduleEntry,
    expected_ref: ContentRef,
) -> None:
    if entry.content_ref != expected_ref:
        raise ValueError(
            "Fighter grant applier received a different content ref",
        )


def _grant_id(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
):
    return uuid5(context.character_id, entry.grant_token)


def _base_receipt(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    *,
    modifier_handles: tuple[ModifierHandle, ...] = (),
    action_uuids: tuple[UUID, ...] = (),
    handler_uuids: tuple[UUID, ...] = (),
    resource_contribution_ids: tuple[tuple[str, UUID], ...] = (),
) -> CharacterGrantReceipt:
    return CharacterGrantReceipt(
        grant_id=_grant_id(context, entry),
        grant_token=entry.grant_token,
        definition_ref=entry.content_ref,
        modifier_handles=modifier_handles,
        action_uuids=action_uuids,
        handler_uuids=handler_uuids,
        resource_contribution_ids=resource_contribution_ids,
    )


def _is_first_grant_for_ref(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> bool:
    """Return whether this row owns its repeated feature's runtime family."""
    if entry.content_ref is None:
        return False
    for scheduled in context.preview.grant_schedule:
        if scheduled.content_ref == entry.content_ref:
            return scheduled.grant_token == entry.grant_token
    raise ValueError("grant entry is absent from its validated preview")


def _fighter_level(context: BuiltinCharacterGrantContext) -> int:
    for class_ref, level in context.preview.class_level_counts:
        if class_ref == FIGHTER_CLASS_REF:
            return level
    raise ValueError("Fighter feature grant requires Fighter class levels")


def _install_static_modifier(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    *,
    value,
    amount: int,
    name: str,
) -> CharacterGrantReceipt:
    modifier = NumericalModifier.create(
        source_entity_uuid=context.entity.uuid,
        name=name,
        value=amount,
    )
    value.self_static.add_value_modifier(modifier)
    return _base_receipt(
        context,
        entry,
        modifier_handles=(
            ModifierHandle(
                value_uuid=value.uuid,
                modifier_uuid=modifier.uuid,
            ),
        ),
    )


def _install_contextual_modifier(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    *,
    value,
    callable_,
    name: str,
) -> CharacterGrantReceipt:
    modifier = ContextualNumericalModifier(
        name=name,
        source_entity_uuid=context.entity.uuid,
        target_entity_uuid=context.entity.uuid,
        callable=callable_,
    )
    value.self_contextual.add_value_modifier(modifier)
    return _base_receipt(
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


def _apply_archery(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, FIGHTING_STYLE_ARCHERY_REF)
    return _install_static_modifier(
        context,
        entry,
        value=context.entity.equipment.ranged_attack_bonus,
        amount=2,
        name="Archery",
    )


def _apply_defense(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, FIGHTING_STYLE_DEFENSE_REF)
    return _install_contextual_modifier(
        context,
        entry,
        value=context.entity.equipment.ac_bonus,
        callable_=fighter.defense_ac_check,
        name="Defense",
    )


def _apply_dueling(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, FIGHTING_STYLE_DUELING_REF)
    return _install_contextual_modifier(
        context,
        entry,
        value=context.entity.equipment.melee_damage_bonus,
        callable_=fighter.dueling_damage_check,
        name="Dueling",
    )


def _apply_two_weapon_fighting(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, FIGHTING_STYLE_TWO_WEAPON_REF)
    entity = context.entity
    installed: list[tuple[ModifiableValue, ContextualNumericalModifier]] = []
    handles: list[ModifierHandle] = []
    try:
        for value, callable_ in (
            (
                entity.equipment.off_hand_melee_ability_bonus,
                fighter.twf_off_hand_melee_ability_bonus,
            ),
            (
                entity.equipment.off_hand_ranged_ability_bonus,
                fighter.twf_off_hand_ranged_ability_bonus,
            ),
        ):
            modifier = ContextualNumericalModifier(
                name="Two-Weapon Fighting",
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                callable=callable_,
            )
            value.self_contextual.add_value_modifier(modifier)
            installed.append((value, modifier))
            handles.append(
                ModifierHandle(
                    value_uuid=value.uuid,
                    modifier_uuid=modifier.uuid,
                    channel=ModifierHandleChannel.SELF_CONTEXTUAL,
                ),
            )
    except Exception:
        for value, modifier in reversed(installed):
            value.self_contextual.remove_value_modifier(modifier.uuid)
        raise
    return _base_receipt(
        context,
        entry,
        modifier_handles=tuple(handles),
    )


def _install_handler(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    handler: EventHandler,
) -> CharacterGrantReceipt:
    content_ref = entry.content_ref
    if content_ref is None:
        raise ValueError("handler grant requires exact content identity")
    context.runtime.bind_granted_behavior(
        handler,
        provider_ref=content_ref,
        runtime_owner_uuid=context.entity.uuid,
    )
    context.entity.add_event_handler(handler)
    return _base_receipt(
        context,
        entry,
        handler_uuids=(handler.uuid,),
    )


def _apply_great_weapon_fighting(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, FIGHTING_STYLE_GREAT_WEAPON_REF)
    handler = EventHandler(
        name="Great Weapon Fighting",
        source_entity_uuid=context.entity.uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.DAMAGE_ROLL_RESULT,
                event_phase=EventPhase.EFFECT,
            ),
        ],
        event_processor=fighter.great_weapon_fighting_processor,
        player_toggleable=True,
    )
    return _install_handler(context, entry, handler)


def _apply_protection(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, FIGHTING_STYLE_PROTECTION_REF)
    return _install_handler(
        context,
        entry,
        fighter.create_protection_handler(context.entity.uuid),
    )


def _register_bound_action(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    action,
) -> None:
    content_ref = entry.content_ref
    if content_ref is None:
        raise ValueError("action grant requires exact content identity")
    context.runtime.bind_granted_behavior(
        action,
        provider_ref=content_ref,
        runtime_owner_uuid=context.entity.uuid,
    )
    context.entity.register_action(action)


def _apply_second_wind(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, SECOND_WIND_REF)
    entity = context.entity
    grant_id = _grant_id(context, entry)
    entity.action_economy.add_resource_contribution(
        "second_wind",
        grant_id,
        maximum=1,
        recharge_type=RechargeType.SHORT_REST,
        capacity_policy=ResourceCapacityPolicy.SUM,
    )
    action = fighter.SecondWind(
        source_entity_uuid=entity.uuid,
        fighter_level=_fighter_level(context),
        template=True,
    )
    try:
        _register_bound_action(context, entry, action)
    except Exception:
        entity.action_economy.remove_resource_contribution(
            "second_wind",
            grant_id,
        )
        raise
    return _base_receipt(
        context,
        entry,
        action_uuids=(action.uuid,),
        resource_contribution_ids=(("second_wind", grant_id),),
    )


def _apply_action_surge(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, ACTION_SURGE_REF)
    entity = context.entity
    grant_id = _grant_id(context, entry)
    entity.action_economy.add_resource_contribution(
        "action_surge",
        grant_id,
        maximum=1,
        recharge_type=RechargeType.SHORT_REST,
        capacity_policy=ResourceCapacityPolicy.SUM,
    )
    action_uuids = ()
    if _is_first_grant_for_ref(context, entry):
        action = fighter.ActionSurge(
            source_entity_uuid=entity.uuid,
            template=True,
        )
        try:
            _register_bound_action(context, entry, action)
        except Exception:
            entity.action_economy.remove_resource_contribution(
                "action_surge",
                grant_id,
            )
            raise
        action_uuids = (action.uuid,)
    return _base_receipt(
        context,
        entry,
        action_uuids=action_uuids,
        resource_contribution_ids=(("action_surge", grant_id),),
    )


def _install_weapon_critical_upgrade(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    *,
    expected_ref: ContentRef,
    name: str,
) -> CharacterGrantReceipt:
    _require_ref(entry, expected_ref)
    entity = context.entity
    handles: list[ModifierHandle] = []
    installed: list[tuple[ModifiableValue, NumericalModifier]] = []
    try:
        for value in (
            entity.equipment.crit_threshold_melee,
            entity.equipment.crit_threshold_ranged,
        ):
            modifier = NumericalModifier.create(
                source_entity_uuid=entity.uuid,
                name=name,
                value=1,
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
    return _base_receipt(
        context,
        entry,
        modifier_handles=tuple(handles),
    )


def _apply_improved_critical(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    return _install_weapon_critical_upgrade(
        context,
        entry,
        expected_ref=IMPROVED_CRITICAL_REF,
        name="Improved Critical",
    )


def _apply_superior_critical(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    """Install the one-point upgrade from Improved to Superior Critical."""
    return _install_weapon_critical_upgrade(
        context,
        entry,
        expected_ref=SUPERIOR_CRITICAL_REF,
        name="Superior Critical Upgrade",
    )


def _apply_indomitable(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, INDOMITABLE_REF)
    entity = context.entity
    grant_id = _grant_id(context, entry)
    entity.action_economy.add_resource_contribution(
        "indomitable",
        grant_id,
        maximum=1,
        recharge_type=RechargeType.LONG_REST,
        capacity_policy=ResourceCapacityPolicy.SUM,
    )
    handler_uuids = ()
    if _is_first_grant_for_ref(context, entry):
        handler = fighter.create_indomitable_handler(entity.uuid)
        try:
            context.runtime.bind_granted_behavior(
                handler,
                provider_ref=INDOMITABLE_REF,
                runtime_owner_uuid=entity.uuid,
            )
            entity.add_event_handler(handler)
        except Exception:
            entity.action_economy.remove_resource_contribution(
                "indomitable",
                grant_id,
            )
            raise
        handler_uuids = (handler.uuid,)
    return _base_receipt(
        context,
        entry,
        handler_uuids=handler_uuids,
        resource_contribution_ids=(("indomitable", grant_id),),
    )


def _apply_survivor(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, SURVIVOR_REF)
    return _install_handler(
        context,
        entry,
        fighter.create_survivor_handler(context.entity.uuid),
    )


def _apply_lucky(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, LUCKY_FEAT_REF)
    entity = context.entity
    grant_id = _grant_id(context, entry)
    entity.action_economy.add_resource_contribution(
        "luck_points",
        grant_id,
        maximum=3,
        recharge_type=RechargeType.LONG_REST,
        capacity_policy=ResourceCapacityPolicy.SUM,
    )
    handler = EventHandler(
        name="Lucky",
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
    )
    try:
        context.runtime.bind_granted_behavior(
            handler,
            provider_ref=LUCKY_FEAT_REF,
            runtime_owner_uuid=entity.uuid,
        )
        entity.add_event_handler(handler)
    except Exception:
        entity.action_economy.remove_resource_contribution(
            "luck_points",
            grant_id,
        )
        raise
    return _base_receipt(
        context,
        entry,
        handler_uuids=(handler.uuid,),
        resource_contribution_ids=(("luck_points", grant_id),),
    )


FIGHTER_CHARACTER_GRANT_APPLIERS: dict[
    str,
    FighterCharacterGrantApplier,
] = {
    FIGHTING_STYLE_ARCHERY_REF.identity_key: _apply_archery,
    FIGHTING_STYLE_DEFENSE_REF.identity_key: _apply_defense,
    FIGHTING_STYLE_DUELING_REF.identity_key: _apply_dueling,
    FIGHTING_STYLE_GREAT_WEAPON_REF.identity_key: (
        _apply_great_weapon_fighting
    ),
    FIGHTING_STYLE_PROTECTION_REF.identity_key: _apply_protection,
    FIGHTING_STYLE_TWO_WEAPON_REF.identity_key: _apply_two_weapon_fighting,
    SECOND_WIND_REF.identity_key: _apply_second_wind,
    ACTION_SURGE_REF.identity_key: _apply_action_surge,
    IMPROVED_CRITICAL_REF.identity_key: _apply_improved_critical,
    SUPERIOR_CRITICAL_REF.identity_key: _apply_superior_critical,
    INDOMITABLE_REF.identity_key: _apply_indomitable,
    SURVIVOR_REF.identity_key: _apply_survivor,
    LUCKY_FEAT_REF.identity_key: _apply_lucky,
}


__all__ = [
    "ACTION_SURGE_REF",
    "FIGHTER_CHARACTER_GRANT_APPLIERS",
    "FIGHTING_STYLE_ARCHERY_REF",
    "FIGHTING_STYLE_DEFENSE_REF",
    "FIGHTING_STYLE_DUELING_REF",
    "FIGHTING_STYLE_GREAT_WEAPON_REF",
    "FIGHTING_STYLE_PROTECTION_REF",
    "FIGHTING_STYLE_TWO_WEAPON_REF",
    "IMPROVED_CRITICAL_REF",
    "INDOMITABLE_REF",
    "LUCKY_FEAT_REF",
    "SECOND_WIND_REF",
    "SUPERIOR_CRITICAL_REF",
    "SURVIVOR_REF",
]
