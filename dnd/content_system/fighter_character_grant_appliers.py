"""Reversible Fighter and Champion structural feature grants.

The authored feature definitions remain the exact providers for every action
and handler installed here.  Character composition owns the runtime handles;
no permanent ``BaseCondition`` is created merely to reuse its old lifecycle.
"""

from collections.abc import Callable

from dnd.blocks.action_economy import (
    RechargeType,
    ResourceCapacityPolicy,
)
from dnd.classes import feats, fighter
from dnd.classes.permanent_feature_definitions import (
    FIGHTER_ACTION_SURGE_DECLARATION,
    FIGHTER_ARCHERY_DECLARATION,
    FIGHTER_DEFENSE_DECLARATION,
    FIGHTER_DUELING_DECLARATION,
    FIGHTER_GREAT_WEAPON_FIGHTING_DECLARATION,
    FIGHTER_IMPROVED_CRITICAL_DECLARATION,
    FIGHTER_INDOMITABLE_DECLARATION,
    FIGHTER_PROTECTION_DECLARATION,
    FIGHTER_SECOND_WIND_DECLARATION,
    FIGHTER_SUPERIOR_CRITICAL_DECLARATION,
    FIGHTER_SURVIVOR_DECLARATION,
    FIGHTER_TWO_WEAPON_FIGHTING_DECLARATION,
    LUCKY_FEAT_DECLARATION,
)
from dnd.classes.progression_definitions import FIGHTER_CLASS_REF
from dnd.content_system.character_build_validation import (
    CharacterGrantScheduleEntry,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_applier_runtime import (
    CharacterGrantInstallation,
    character_grant_id,
    grant_receipt,
    install_bound_handler,
    install_contextual_value_modifier,
    install_static_value_modifier,
    is_first_grant_for_ref,
    require_grant_ref,
    validated_class_level,
)
from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
)
from dnd.core.content.identities import ContentRef
from dnd.core.events import (
    EventHandler,
    EventPhase,
    EventType,
    Trigger,
)


FIGHTING_STYLE_ARCHERY_REF = FIGHTER_ARCHERY_DECLARATION.ref
FIGHTING_STYLE_DEFENSE_REF = FIGHTER_DEFENSE_DECLARATION.ref
FIGHTING_STYLE_DUELING_REF = FIGHTER_DUELING_DECLARATION.ref
FIGHTING_STYLE_GREAT_WEAPON_REF = (
    FIGHTER_GREAT_WEAPON_FIGHTING_DECLARATION.ref
)
FIGHTING_STYLE_PROTECTION_REF = FIGHTER_PROTECTION_DECLARATION.ref
FIGHTING_STYLE_TWO_WEAPON_REF = (
    FIGHTER_TWO_WEAPON_FIGHTING_DECLARATION.ref
)
SECOND_WIND_REF = FIGHTER_SECOND_WIND_DECLARATION.ref
ACTION_SURGE_REF = FIGHTER_ACTION_SURGE_DECLARATION.ref
IMPROVED_CRITICAL_REF = FIGHTER_IMPROVED_CRITICAL_DECLARATION.ref
SUPERIOR_CRITICAL_REF = FIGHTER_SUPERIOR_CRITICAL_DECLARATION.ref
INDOMITABLE_REF = FIGHTER_INDOMITABLE_DECLARATION.ref
SURVIVOR_REF = FIGHTER_SURVIVOR_DECLARATION.ref
LUCKY_FEAT_REF = LUCKY_FEAT_DECLARATION.ref


FighterCharacterGrantApplier = Callable[
    [BuiltinCharacterGrantContext, CharacterGrantScheduleEntry],
    CharacterGrantReceipt,
]


def _apply_archery(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, FIGHTING_STYLE_ARCHERY_REF)
    return install_static_value_modifier(
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
    require_grant_ref(entry, FIGHTING_STYLE_DEFENSE_REF)
    return install_contextual_value_modifier(
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
    require_grant_ref(entry, FIGHTING_STYLE_DUELING_REF)
    return install_contextual_value_modifier(
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
    require_grant_ref(entry, FIGHTING_STYLE_TWO_WEAPON_REF)
    entity = context.entity
    with CharacterGrantInstallation(context, entry) as installation:
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
            installation.add_contextual_value_modifier(
                value=value,
                callable_=callable_,
                name="Two-Weapon Fighting",
            )
    return grant_receipt(
        context,
        entry,
        modifier_handles=installation.modifier_handles,
    )


def _apply_great_weapon_fighting(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, FIGHTING_STYLE_GREAT_WEAPON_REF)
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
    return install_bound_handler(context, entry, handler)


def _apply_protection(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, FIGHTING_STYLE_PROTECTION_REF)
    return install_bound_handler(
        context,
        entry,
        fighter.create_protection_handler(context.entity.uuid),
    )


def _apply_second_wind(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, SECOND_WIND_REF)
    entity = context.entity
    grant_id = character_grant_id(context, entry)
    action = fighter.SecondWind(
        source_entity_uuid=entity.uuid,
        fighter_level=validated_class_level(context, FIGHTER_CLASS_REF),
        template=True,
    )
    with CharacterGrantInstallation(context, entry) as installation:
        installation.add_resource(
            "second_wind",
            grant_id,
            maximum=1,
            recharge_type=RechargeType.SHORT_REST,
            capacity_policy=ResourceCapacityPolicy.SUM,
        )
        installation.add_bound_action(action)
    return grant_receipt(
        context,
        entry,
        action_uuids=installation.action_uuids,
        resource_contribution_ids=installation.resource_contribution_ids,
    )


def _apply_action_surge(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, ACTION_SURGE_REF)
    entity = context.entity
    grant_id = character_grant_id(context, entry)
    with CharacterGrantInstallation(context, entry) as installation:
        installation.add_resource(
            "action_surge",
            grant_id,
            maximum=1,
            recharge_type=RechargeType.SHORT_REST,
            capacity_policy=ResourceCapacityPolicy.SUM,
        )
        if is_first_grant_for_ref(context, entry):
            installation.add_bound_action(
                fighter.ActionSurge(
                    source_entity_uuid=entity.uuid,
                    template=True,
                ),
            )
    return grant_receipt(
        context,
        entry,
        action_uuids=installation.action_uuids,
        resource_contribution_ids=installation.resource_contribution_ids,
    )


def _install_weapon_critical_upgrade(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    *,
    expected_ref: ContentRef,
    name: str,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, expected_ref)
    entity = context.entity
    with CharacterGrantInstallation(context, entry) as installation:
        for value in (
            entity.equipment.crit_threshold_melee,
            entity.equipment.crit_threshold_ranged,
        ):
            installation.add_static_value_modifier(
                value=value,
                name=name,
                amount=1,
            )
    return grant_receipt(
        context,
        entry,
        modifier_handles=installation.modifier_handles,
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
    require_grant_ref(entry, INDOMITABLE_REF)
    entity = context.entity
    grant_id = character_grant_id(context, entry)
    with CharacterGrantInstallation(context, entry) as installation:
        installation.add_resource(
            "indomitable",
            grant_id,
            maximum=1,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.SUM,
        )
        if is_first_grant_for_ref(context, entry):
            installation.add_bound_handler(
                fighter.create_indomitable_handler(entity.uuid),
            )
    return grant_receipt(
        context,
        entry,
        handler_uuids=installation.handler_uuids,
        resource_contribution_ids=installation.resource_contribution_ids,
    )


def _apply_survivor(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, SURVIVOR_REF)
    return install_bound_handler(
        context,
        entry,
        fighter.create_survivor_handler(context.entity.uuid),
    )


def _apply_lucky(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, LUCKY_FEAT_REF)
    entity = context.entity
    grant_id = character_grant_id(context, entry)
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
    with CharacterGrantInstallation(context, entry) as installation:
        installation.add_resource(
            "luck_points",
            grant_id,
            maximum=3,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.SUM,
        )
        installation.add_bound_handler(handler)
    return grant_receipt(
        context,
        entry,
        handler_uuids=installation.handler_uuids,
        resource_contribution_ids=installation.resource_contribution_ids,
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
