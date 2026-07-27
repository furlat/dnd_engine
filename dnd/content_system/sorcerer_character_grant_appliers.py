"""Reversible Sorcerer and Draconic Bloodline structural grants.

Cold composition owns permanent actions, resource rules, formulae, and
modifiers. Temporary spell overrides remain evented ``MetamagicActive`` state
and are removed by exact behavior identity when their owning choice is removed.
"""

from collections.abc import Callable
from uuid import UUID, uuid5

from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.blocks.equipment import ArmorClassFormulaCandidate
from dnd.classes import sorcerer
from dnd.classes.sorcerer_progression_definitions import SORCERER_CLASS_REF
from dnd.classes.sorcerer_structural_feature_definitions import (
    DRACONIC_PRESENCE_DECLARATION,
    DRAGON_WINGS_DECLARATION,
    ELEMENTAL_AFFINITY_DECLARATION,
    METAMAGIC_OPTION_DECLARATIONS,
    SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF,
    SORCEROUS_RESTORATION_DECLARATION,
    SorcererMetamagicOption,
    SorcererStructuralFeatureKind,
)
from dnd.content_system.character_build_validation import (
    CharacterGrantScheduleEntry,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    ModifierHandle,
)
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.core.base_actions import BaseAction
from dnd.core.content.identities import ContentRef
from dnd.core.modifiers import DamageType, NumericalModifier


SORCERY_POINTS_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    sorcerer.SorceryPointsFeature
].ref
DRACONIC_RESILIENCE_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    sorcerer.DraconicResilience
].ref
DRACONIC_PRESENCE_AURA_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    sorcerer.DraconicPresenceAura
].ref
DRACONIC_PRESENCE_IMMUNITY_REF = (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
        sorcerer.DraconicPresenceImmunity
    ].ref
)
ELEMENTAL_AFFINITY_REF = ELEMENTAL_AFFINITY_DECLARATION.ref
ELEMENTAL_AFFINITY_RESISTANCE_REF = (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
        sorcerer.ElementalAffinityResistance
    ].ref
)
METAMAGIC_ACTIVE_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    sorcerer.MetamagicActive
].ref
DRAGON_WINGS_ACTIVE_REF = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[
    sorcerer.DragonWingsActive
].ref


SorcererCharacterGrantApplier = Callable[
    [BuiltinCharacterGrantContext, CharacterGrantScheduleEntry],
    CharacterGrantReceipt,
]


_METAMAGIC_ACTION_BY_OPTION: dict[
    SorcererMetamagicOption,
    type[BaseAction],
] = {
    SorcererMetamagicOption.DISTANT_SPELL: sorcerer.DistantSpell,
    SorcererMetamagicOption.QUICKENED_SPELL: sorcerer.QuickenedSpell,
    SorcererMetamagicOption.TWINNED_SPELL: sorcerer.TwinnedSpell,
}


def _grant_id(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> UUID:
    return uuid5(context.character_id, entry.grant_token)


def _base_receipt(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    *,
    modifier_handles: tuple[ModifierHandle, ...] = (),
    spell_damage_affinity_contribution_ids: tuple[UUID, ...] = (),
    action_uuids: tuple[UUID, ...] = (),
    resource_contribution_ids: tuple[tuple[str, UUID], ...] = (),
    resource_recovery_contribution_ids: tuple[
        tuple[str, UUID],
        ...,
    ] = (),
    armor_class_formula_ids: tuple[UUID, ...] = (),
    transient_condition_refs_to_remove: tuple[ContentRef, ...] = (),
) -> CharacterGrantReceipt:
    return CharacterGrantReceipt(
        grant_id=_grant_id(context, entry),
        grant_token=entry.grant_token,
        definition_ref=entry.content_ref,
        modifier_handles=modifier_handles,
        spell_damage_affinity_contribution_ids=(
            spell_damage_affinity_contribution_ids
        ),
        action_uuids=action_uuids,
        resource_contribution_ids=resource_contribution_ids,
        resource_recovery_contribution_ids=(
            resource_recovery_contribution_ids
        ),
        armor_class_formula_ids=armor_class_formula_ids,
        transient_condition_refs_to_remove=(
            transient_condition_refs_to_remove
        ),
    )


def _require_ref(
    entry: CharacterGrantScheduleEntry,
    expected_ref: ContentRef,
) -> None:
    if entry.content_ref != expected_ref:
        raise ValueError(
            "Sorcerer grant applier received a different content ref",
        )


def _sorcerer_level(context: BuiltinCharacterGrantContext) -> int:
    for class_ref, level in context.preview.class_level_counts:
        if class_ref == SORCERER_CLASS_REF:
            return level
    raise ValueError("Sorcerer feature grant requires Sorcerer class levels")


def _is_first_grant_for_ref(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> bool:
    for scheduled in context.preview.grant_schedule:
        if scheduled.content_ref == entry.content_ref:
            return scheduled.grant_token == entry.grant_token
    raise ValueError("grant entry is absent from its validated preview")


def _selected_ancestry_damage_type(
    context: BuiltinCharacterGrantContext,
) -> DamageType:
    ancestry_definitions = tuple(
        definition
        for scheduled in context.preview.grant_schedule
        if scheduled.content_ref is not None
        for definition in (
            SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF.get(
                scheduled.content_ref,
            ),
        )
        if (
            definition is not None
            and definition.feature_kind
            is SorcererStructuralFeatureKind.DRACONIC_ANCESTRY
        )
    )
    if len(ancestry_definitions) != 1:
        raise ValueError(
            "Elemental Affinity requires exactly one selected ancestry",
        )
    damage_type = ancestry_definitions[0].ancestry_damage_type
    if damage_type is None:
        raise RuntimeError("Draconic ancestry omitted its damage type")
    return DamageType[damage_type.upper()]


def _register_bound_action(
    context: BuiltinCharacterGrantContext,
    *,
    provider_ref: ContentRef,
    action: BaseAction,
) -> None:
    context.runtime.bind_granted_behavior(
        action,
        provider_ref=provider_ref,
        runtime_owner_uuid=context.entity.uuid,
    )
    context.entity.register_action(action)


def _apply_sorcery_points(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, SORCERY_POINTS_REF)
    class_level = entry.provenance.class_level
    if class_level is None or class_level < 2:
        raise ValueError("Sorcery Points require Sorcerer class level 2")
    source_id = _grant_id(context, entry)
    economy = context.entity.action_economy
    economy.add_resource_contribution(
        "sorcery_points",
        source_id,
        maximum=class_level,
        recharge_type=RechargeType.LONG_REST,
        capacity_policy=ResourceCapacityPolicy.MAXIMUM,
    )
    actions: list[BaseAction] = []
    try:
        if _is_first_grant_for_ref(context, entry):
            for slot_level, capacity in context.preview.normal_spell_slots:
                if capacity <= 0 or not 1 <= slot_level <= 5:
                    continue
                actions.extend((
                    sorcerer.ConvertSlotToSP(
                        source_entity_uuid=context.entity.uuid,
                        slot_level=slot_level,
                        template=True,
                    ),
                    sorcerer.ConvertSPToSlot(
                        source_entity_uuid=context.entity.uuid,
                        slot_level=slot_level,
                        template=True,
                    ),
                ))
            for action in actions:
                _register_bound_action(
                    context,
                    provider_ref=SORCERY_POINTS_REF,
                    action=action,
                )
    except Exception:
        for action in reversed(actions):
            context.entity.unregister_action_by_uuid(action.uuid)
        economy.remove_resource_contribution("sorcery_points", source_id)
        raise
    return _base_receipt(
        context,
        entry,
        action_uuids=tuple(action.uuid for action in actions),
        resource_contribution_ids=(("sorcery_points", source_id),),
    )


def _apply_metamagic_option(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    content_ref = entry.content_ref
    if content_ref is None:
        raise ValueError("Metamagic choice requires exact content identity")
    definition = SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF.get(
        content_ref,
    )
    if (
        definition is None
        or definition.feature_kind
        is not SorcererStructuralFeatureKind.METAMAGIC_OPTION
        or definition.metamagic_option is None
    ):
        raise ValueError("Metamagic applier received a non-metamagic feature")
    action_type = _METAMAGIC_ACTION_BY_OPTION.get(
        definition.metamagic_option,
    )
    if action_type is None:
        raise RuntimeError(
            "No lawful runtime mechanic is installed for selected Metamagic "
            f"{definition.metamagic_option.value!r}",
        )
    action = action_type(
        source_entity_uuid=context.entity.uuid,
        template=True,
    )
    _register_bound_action(
        context,
        provider_ref=content_ref,
        action=action,
    )
    return _base_receipt(
        context,
        entry,
        action_uuids=(action.uuid,),
        transient_condition_refs_to_remove=(METAMAGIC_ACTIVE_REF,),
    )


def _apply_draconic_resilience(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, DRACONIC_RESILIENCE_REF)
    source_id = _grant_id(context, entry)
    hp_modifier = NumericalModifier.create(
        source_entity_uuid=context.entity.uuid,
        target_entity_uuid=context.entity.uuid,
        name="Draconic Resilience HP",
        value=_sorcerer_level(context),
    )
    context.entity.health.max_hit_points_bonus.self_static.add_value_modifier(
        hp_modifier,
    )
    try:
        context.entity.equipment.add_armor_class_formula_candidate(
            ArmorClassFormulaCandidate(
                source_id=source_id,
                base_ac=13,
                ability_names=("dexterity",),
                requires_unarmored=True,
                allows_shield=True,
            ),
        )
    except Exception:
        context.entity.health.max_hit_points_bonus.self_static.remove_value_modifier(
            hp_modifier.uuid,
        )
        raise
    return _base_receipt(
        context,
        entry,
        modifier_handles=(
            ModifierHandle(
                value_uuid=(
                    context.entity.health.max_hit_points_bonus.uuid
                ),
                modifier_uuid=hp_modifier.uuid,
            ),
        ),
        armor_class_formula_ids=(source_id,),
    )


def _apply_draconic_ancestry(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    content_ref = entry.content_ref
    if content_ref is None:
        raise ValueError("Draconic ancestry requires exact content identity")
    definition = SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF.get(
        content_ref,
    )
    if (
        definition is None
        or definition.feature_kind
        is not SorcererStructuralFeatureKind.DRACONIC_ANCESTRY
    ):
        raise ValueError(
            "Draconic ancestry applier received a different feature",
        )
    return _base_receipt(context, entry)


def _apply_elemental_affinity(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, ELEMENTAL_AFFINITY_REF)
    damage_type = _selected_ancestry_damage_type(context)
    source_id = _grant_id(context, entry)
    context.entity.spellcasting.add_spell_damage_affinity_contribution(
        source_id,
        damage_type=damage_type,
        ability_name="charisma",
    )
    action = sorcerer.ElementalAffinityResistanceAction(
        source_entity_uuid=context.entity.uuid,
        damage_type=damage_type,
        template=True,
    )
    try:
        _register_bound_action(
            context,
            provider_ref=ELEMENTAL_AFFINITY_REF,
            action=action,
        )
    except Exception:
        context.entity.spellcasting.remove_spell_damage_affinity_contribution(
            source_id,
        )
        raise
    return _base_receipt(
        context,
        entry,
        spell_damage_affinity_contribution_ids=(source_id,),
        action_uuids=(action.uuid,),
        transient_condition_refs_to_remove=(
            ELEMENTAL_AFFINITY_RESISTANCE_REF,
        ),
    )


def _apply_sorcerous_restoration(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, SORCEROUS_RESTORATION_DECLARATION.ref)
    definition = SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF[
        SORCEROUS_RESTORATION_DECLARATION.ref
    ]
    amount = definition.short_rest_sorcery_point_recovery
    if amount is None:
        raise RuntimeError("Sorcerous Restoration omitted recovery amount")
    source_id = _grant_id(context, entry)
    context.entity.action_economy.add_resource_recovery_contribution(
        "sorcery_points",
        source_id,
        trigger=RechargeType.SHORT_REST,
        amount=amount,
    )
    return _base_receipt(
        context,
        entry,
        resource_recovery_contribution_ids=(
            ("sorcery_points", source_id),
        ),
    )


def _apply_dragon_wings(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, DRAGON_WINGS_DECLARATION.ref)
    actions: tuple[BaseAction, ...] = (
        sorcerer.DragonWings(
            source_entity_uuid=context.entity.uuid,
            template=True,
        ),
        sorcerer.Fly(
            source_entity_uuid=context.entity.uuid,
            template=True,
        ),
    )
    registered: list[BaseAction] = []
    try:
        for action in actions:
            _register_bound_action(
                context,
                provider_ref=DRAGON_WINGS_DECLARATION.ref,
                action=action,
            )
            registered.append(action)
    except Exception:
        for action in reversed(registered):
            context.entity.unregister_action_by_uuid(action.uuid)
        raise
    return _base_receipt(
        context,
        entry,
        action_uuids=tuple(action.uuid for action in registered),
        transient_condition_refs_to_remove=(DRAGON_WINGS_ACTIVE_REF,),
    )


def _apply_draconic_presence(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    _require_ref(entry, DRACONIC_PRESENCE_DECLARATION.ref)
    actions: tuple[BaseAction, ...] = (
        sorcerer.DraconicPresence(
            source_entity_uuid=context.entity.uuid,
            mode="awe",
            template=True,
        ),
        sorcerer.DraconicPresence(
            source_entity_uuid=context.entity.uuid,
            mode="fear",
            template=True,
        ),
    )
    registered: list[BaseAction] = []
    try:
        for action in actions:
            _register_bound_action(
                context,
                provider_ref=DRACONIC_PRESENCE_DECLARATION.ref,
                action=action,
            )
            registered.append(action)
    except Exception:
        for action in reversed(registered):
            context.entity.unregister_action_by_uuid(action.uuid)
        raise
    return _base_receipt(
        context,
        entry,
        action_uuids=tuple(action.uuid for action in registered),
        transient_condition_refs_to_remove=(
            DRACONIC_PRESENCE_AURA_REF,
            DRACONIC_PRESENCE_IMMUNITY_REF,
        ),
    )


SORCERER_CHARACTER_GRANT_APPLIERS: dict[
    str,
    SorcererCharacterGrantApplier,
] = {
    SORCERY_POINTS_REF.identity_key: _apply_sorcery_points,
    DRACONIC_RESILIENCE_REF.identity_key: _apply_draconic_resilience,
    ELEMENTAL_AFFINITY_REF.identity_key: _apply_elemental_affinity,
    SORCEROUS_RESTORATION_DECLARATION.ref.identity_key: (
        _apply_sorcerous_restoration
    ),
    DRAGON_WINGS_DECLARATION.ref.identity_key: _apply_dragon_wings,
    DRACONIC_PRESENCE_DECLARATION.ref.identity_key: (
        _apply_draconic_presence
    ),
    **{
        declaration.ref.identity_key: _apply_metamagic_option
        for declaration in METAMAGIC_OPTION_DECLARATIONS
    },
    **{
        content_ref.identity_key: _apply_draconic_ancestry
        for content_ref, definition in (
            SORCERER_STRUCTURAL_FEATURE_DEFINITIONS_BY_REF.items()
        )
        if (
            definition.feature_kind
            is SorcererStructuralFeatureKind.DRACONIC_ANCESTRY
        )
    },
}


__all__ = [
    "DRACONIC_PRESENCE_AURA_REF",
    "DRACONIC_PRESENCE_IMMUNITY_REF",
    "DRACONIC_RESILIENCE_REF",
    "DRAGON_WINGS_ACTIVE_REF",
    "ELEMENTAL_AFFINITY_REF",
    "ELEMENTAL_AFFINITY_RESISTANCE_REF",
    "METAMAGIC_ACTIVE_REF",
    "SORCERER_CHARACTER_GRANT_APPLIERS",
    "SORCERY_POINTS_REF",
    "SorcererCharacterGrantApplier",
]
