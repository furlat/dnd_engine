"""Shared reversible-install primitives for structural character grants."""

from __future__ import annotations

from types import TracebackType
from typing import Sequence
from uuid import UUID, uuid5

from dnd.blocks.action_economy import (
    RechargeType,
    ResourceCapacityPolicy,
)
from dnd.content_system.character_build_validation import (
    CharacterGrantScheduleEntry,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    ConditionImmunityHandle,
    LearnedReactionSpellHandle,
    ModifierHandle,
    ModifierHandleChannel,
    ModifierHandleKind,
    ProficiencyHandle,
)
from dnd.core.base_actions import BaseAction
from dnd.core.content.identities import ContentRef
from dnd.core.content.origin_features import OriginCapability
from dnd.core.events import EventHandler
from dnd.core.modifiers import (
    ContextAwareNumerical,
    ContextualNumericalModifier,
    NumericalModifier,
)
from dnd.core.values import ModifiableValue


def character_grant_id(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> UUID:
    """Return the deterministic runtime owner id for one sealed grant row."""
    return uuid5(context.character_id, entry.grant_token)


def require_grant_ref(
    entry: CharacterGrantScheduleEntry,
    expected_ref: ContentRef,
) -> None:
    """Reject dispatch drift before a grant mutates engine state."""
    if entry.content_ref != expected_ref:
        raise ValueError("grant applier received a different content ref")


def grant_receipt(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    *,
    modifier_handles: tuple[ModifierHandle, ...] = (),
    proficiency_handles: tuple[ProficiencyHandle, ...] = (),
    hit_die_uuids: tuple[UUID, ...] = (),
    spellcasting_source_ids: tuple[UUID, ...] = (),
    normal_spell_slot_capacity_source_ids: tuple[UUID, ...] = (),
    spell_damage_affinity_contribution_ids: tuple[UUID, ...] = (),
    action_uuids: tuple[UUID, ...] = (),
    handler_uuids: tuple[UUID, ...] = (),
    learned_reaction_spell_handles: tuple[
        LearnedReactionSpellHandle,
        ...,
    ] = (),
    resource_contribution_ids: tuple[tuple[str, UUID], ...] = (),
    resource_recovery_contribution_ids: tuple[tuple[str, UUID], ...] = (),
    armor_class_formula_ids: tuple[UUID, ...] = (),
    attack_multiplicity_grant_ids: tuple[UUID, ...] = (),
    condition_immunity_handles: tuple[ConditionImmunityHandle, ...] = (),
    sense_mode_source_ids: tuple[UUID, ...] = (),
    structural_size_source_ids: tuple[UUID, ...] = (),
    origin_capability_source_ids: tuple[
        tuple[OriginCapability, UUID],
        ...,
    ] = (),
    transient_condition_refs_to_remove: tuple[ContentRef, ...] = (),
) -> CharacterGrantReceipt:
    """Build the one canonical receipt shape from a validated grant row."""
    return CharacterGrantReceipt(
        grant_id=character_grant_id(context, entry),
        grant_token=entry.grant_token,
        definition_ref=entry.content_ref,
        modifier_handles=modifier_handles,
        proficiency_handles=proficiency_handles,
        hit_die_uuids=hit_die_uuids,
        spellcasting_source_ids=spellcasting_source_ids,
        normal_spell_slot_capacity_source_ids=(
            normal_spell_slot_capacity_source_ids
        ),
        spell_damage_affinity_contribution_ids=(
            spell_damage_affinity_contribution_ids
        ),
        action_uuids=action_uuids,
        handler_uuids=handler_uuids,
        learned_reaction_spell_handles=learned_reaction_spell_handles,
        resource_contribution_ids=resource_contribution_ids,
        resource_recovery_contribution_ids=(
            resource_recovery_contribution_ids
        ),
        armor_class_formula_ids=armor_class_formula_ids,
        attack_multiplicity_grant_ids=attack_multiplicity_grant_ids,
        condition_immunity_handles=condition_immunity_handles,
        sense_mode_source_ids=sense_mode_source_ids,
        structural_size_source_ids=structural_size_source_ids,
        origin_capability_source_ids=origin_capability_source_ids,
        transient_condition_refs_to_remove=(
            transient_condition_refs_to_remove
        ),
    )


def is_first_grant_for_ref(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> bool:
    """Return whether a repeated row owns its feature's shared runtime family."""
    if entry.content_ref is None:
        return False
    for scheduled in context.preview.grant_schedule:
        if scheduled.content_ref == entry.content_ref:
            return scheduled.grant_token == entry.grant_token
    raise ValueError("grant entry is absent from its validated preview")


def validated_class_level(
    context: BuiltinCharacterGrantContext,
    class_ref: ContentRef,
) -> int:
    """Resolve an exact class level from the sealed validation preview."""
    for scheduled_ref, level in context.preview.class_level_counts:
        if scheduled_ref == class_ref:
            return level
    raise ValueError(
        f"feature grant requires class levels in {class_ref.identity_key}",
    )


def register_bound_action(
    context: BuiltinCharacterGrantContext,
    *,
    provider_ref: ContentRef,
    action: BaseAction,
) -> None:
    """Bind and register one action under its exact authored provider."""
    context.runtime.bind_granted_behavior(
        action,
        provider_ref=provider_ref,
        runtime_owner_uuid=context.entity.uuid,
    )
    context.entity.register_action(action)


def remove_modifier_handle(handle: ModifierHandle) -> None:
    """Remove one exact structural modifier through its declared collection."""
    value = ModifiableValue.get(handle.value_uuid)
    if value is None:
        raise RuntimeError(
            f"character-grant value {handle.value_uuid} is missing",
        )
    if handle.channel is ModifierHandleChannel.SELF_STATIC:
        channel = value.self_static
    elif handle.channel is ModifierHandleChannel.SELF_CONTEXTUAL:
        channel = value.self_contextual
    else:
        raise RuntimeError(
            "unsupported character-grant modifier channel "
            f"{handle.channel.value}",
        )
    if handle.kind is ModifierHandleKind.VALUE:
        channel.remove_value_modifier(handle.modifier_uuid)
    elif handle.kind is ModifierHandleKind.MIN_CONSTRAINT:
        channel.remove_min_constraint(handle.modifier_uuid)
    elif handle.kind is ModifierHandleKind.MAX_CONSTRAINT:
        channel.remove_max_constraint(handle.modifier_uuid)
    elif handle.kind is ModifierHandleKind.ADVANTAGE:
        channel.remove_advantage_modifier(handle.modifier_uuid)
    elif handle.kind is ModifierHandleKind.CRITICAL:
        channel.remove_critical_modifier(handle.modifier_uuid)
    elif handle.kind is ModifierHandleKind.AUTO_HIT:
        channel.remove_auto_hit_modifier(handle.modifier_uuid)
    elif handle.kind is ModifierHandleKind.RESISTANCE:
        channel.remove_resistance_modifier(handle.modifier_uuid)
    else:
        raise RuntimeError(
            f"unsupported character-grant modifier kind {handle.kind.value}",
        )


class CharacterGrantInstallation:
    """One exception-safe installation of source-owned character structure."""

    def __init__(
        self,
        context: BuiltinCharacterGrantContext,
        entry: CharacterGrantScheduleEntry,
    ) -> None:
        self._context = context
        self._entry = entry
        self._actions: list[BaseAction] = []
        self._handlers: list[EventHandler] = []
        self._resources: list[tuple[str, UUID]] = []
        self._modifiers: list[
            tuple[ModifiableValue, UUID, ModifierHandleChannel]
        ] = []

    @property
    def action_uuids(self) -> tuple[UUID, ...]:
        """Return actions installed by this transaction in authored order."""
        return tuple(action.uuid for action in self._actions)

    @property
    def handler_uuids(self) -> tuple[UUID, ...]:
        """Return handlers installed by this transaction in authored order."""
        return tuple(handler.uuid for handler in self._handlers)

    @property
    def resource_contribution_ids(self) -> tuple[tuple[str, UUID], ...]:
        """Return resource contributions installed by this transaction."""
        return tuple(self._resources)

    @property
    def modifier_handles(self) -> tuple[ModifierHandle, ...]:
        """Return exact reversible handles for installed value modifiers."""
        return tuple(
            ModifierHandle(
                value_uuid=value.uuid,
                modifier_uuid=modifier_uuid,
                channel=channel,
            )
            for value, modifier_uuid, channel in self._modifiers
        )

    def add_resource(
        self,
        name: str,
        source_id: UUID,
        *,
        maximum: int,
        recharge_type: RechargeType,
        capacity_policy: ResourceCapacityPolicy,
    ) -> None:
        """Install one source-owned action-economy contribution."""
        self._context.entity.action_economy.add_resource_contribution(
            name,
            source_id,
            maximum=maximum,
            recharge_type=recharge_type,
            capacity_policy=capacity_policy,
        )
        self._resources.append((name, source_id))

    def add_bound_action(
        self,
        action: BaseAction,
        *,
        provider_ref: ContentRef | None = None,
    ) -> None:
        """Bind and register one newly constructed action template."""
        resolved_provider = provider_ref or self._entry.content_ref
        if resolved_provider is None:
            raise ValueError("action grant requires exact content identity")
        try:
            register_bound_action(
                self._context,
                provider_ref=resolved_provider,
                action=action,
            )
        except Exception:
            action.remove_from_register()
            raise
        self._actions.append(action)

    def add_bound_actions(
        self,
        actions: Sequence[BaseAction],
        *,
        provider_ref: ContentRef | None = None,
    ) -> None:
        """Bind/register newly constructed action templates in order."""
        for action in actions:
            self.add_bound_action(action, provider_ref=provider_ref)

    def add_bound_handler(
        self,
        handler: EventHandler,
        *,
        provider_ref: ContentRef | None = None,
    ) -> None:
        """Bind and register one newly constructed event handler."""
        resolved_provider = provider_ref or self._entry.content_ref
        if resolved_provider is None:
            raise ValueError("handler grant requires exact content identity")
        try:
            self._context.runtime.bind_granted_behavior(
                handler,
                provider_ref=resolved_provider,
                runtime_owner_uuid=self._context.entity.uuid,
            )
            self._context.entity.add_event_handler(handler)
        except Exception:
            self._context.entity.remove_event_handler(handler)
            handler.remove_from_register()
            raise
        self._handlers.append(handler)

    def add_static_value_modifier(
        self,
        *,
        value: ModifiableValue,
        amount: int,
        name: str,
    ) -> None:
        """Install one static numerical modifier and retain its undo handle."""
        modifier = NumericalModifier.create(
            source_entity_uuid=self._context.entity.uuid,
            name=name,
            value=amount,
        )
        try:
            value.self_static.add_value_modifier(modifier)
        except Exception:
            modifier.remove_from_register()
            raise
        self._modifiers.append(
            (value, modifier.uuid, ModifierHandleChannel.SELF_STATIC),
        )

    def add_contextual_value_modifier(
        self,
        *,
        value: ModifiableValue,
        callable_: ContextAwareNumerical,
        name: str,
    ) -> None:
        """Install one contextual numerical modifier and retain its handle."""
        modifier = ContextualNumericalModifier(
            name=name,
            source_entity_uuid=self._context.entity.uuid,
            target_entity_uuid=self._context.entity.uuid,
            callable=callable_,
        )
        try:
            value.self_contextual.add_value_modifier(modifier)
        except Exception:
            modifier.remove_from_register()
            raise
        self._modifiers.append(
            (value, modifier.uuid, ModifierHandleChannel.SELF_CONTEXTUAL),
        )

    def __enter__(self) -> "CharacterGrantInstallation":
        """Begin an installation transaction."""
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Rollback only when installation leaves through an exception."""
        del exception, traceback
        if exception_type is None:
            return False
        self._rollback()
        return False

    def _rollback(self) -> None:
        """Remove installed structure in reverse dependency order."""
        entity = self._context.entity
        for handler in reversed(self._handlers):
            entity.remove_event_handler(handler)
        for action in reversed(self._actions):
            entity.unregister_action_by_uuid(action.uuid)
        for name, source_id in reversed(self._resources):
            entity.action_economy.remove_resource_contribution(name, source_id)
        for handle in reversed(self.modifier_handles):
            remove_modifier_handle(handle)


def install_bound_handler(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    handler: EventHandler,
) -> CharacterGrantReceipt:
    """Bind/register one handler and return its reversible receipt."""
    with CharacterGrantInstallation(context, entry) as installation:
        installation.add_bound_handler(handler)
    return grant_receipt(
        context,
        entry,
        handler_uuids=installation.handler_uuids,
    )


def install_static_value_modifier(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    *,
    value: ModifiableValue,
    amount: int,
    name: str,
) -> CharacterGrantReceipt:
    """Install one reversible static numerical character-grant modifier."""
    with CharacterGrantInstallation(context, entry) as installation:
        installation.add_static_value_modifier(
            value=value,
            amount=amount,
            name=name,
        )
    return grant_receipt(
        context,
        entry,
        modifier_handles=installation.modifier_handles,
    )


def install_contextual_value_modifier(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    *,
    value: ModifiableValue,
    callable_: ContextAwareNumerical,
    name: str,
) -> CharacterGrantReceipt:
    """Install one reversible contextual numerical grant modifier."""
    with CharacterGrantInstallation(context, entry) as installation:
        installation.add_contextual_value_modifier(
            value=value,
            callable_=callable_,
            name=name,
        )
    return grant_receipt(
        context,
        entry,
        modifier_handles=installation.modifier_handles,
    )


__all__ = [
    "CharacterGrantInstallation",
    "character_grant_id",
    "grant_receipt",
    "install_bound_handler",
    "install_contextual_value_modifier",
    "install_static_value_modifier",
    "is_first_grant_for_ref",
    "register_bound_action",
    "remove_modifier_handle",
    "require_grant_ref",
    "validated_class_level",
]
