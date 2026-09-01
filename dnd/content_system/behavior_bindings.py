"""Cold admission of primitive identities to live rules behaviors."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from uuid import UUID

from dnd.core.base_actions import BaseAction
from dnd.core.base_conditions import BaseCondition
from dnd.core.content.registration import ContentDeclaration
from dnd.core.content.runtime import BehaviorBinding, RuntimeBehaviorKind
from dnd.core.events import BaseHandler


_ACTION_RUNTIME_KINDS = frozenset({
    RuntimeBehaviorKind.ACTION,
    RuntimeBehaviorKind.SPELL,
    RuntimeBehaviorKind.REACTION,
    RuntimeBehaviorKind.TRAIT,
    RuntimeBehaviorKind.FEAT,
    RuntimeBehaviorKind.CLASS_FEATURE,
    RuntimeBehaviorKind.ENVIRONMENT_INTERACTION,
    RuntimeBehaviorKind.SYSTEM,
})
_CONDITION_RUNTIME_KINDS = frozenset({
    RuntimeBehaviorKind.CONDITION,
    RuntimeBehaviorKind.TRAIT,
    RuntimeBehaviorKind.FEAT,
    RuntimeBehaviorKind.CLASS_FEATURE,
})
_HANDLER_RUNTIME_KINDS = (
    _ACTION_RUNTIME_KINDS
    | _CONDITION_RUNTIME_KINDS
    | {RuntimeBehaviorKind.ITEM}
)


class BehaviorBinder:
    """Bind live behaviors from one immutable cold class inventory."""

    def __init__(
        self,
        declarations_by_class: Mapping[type[object], ContentDeclaration],
        *,
        provider_only_behavior_ids: frozenset[str] = frozenset(),
    ) -> None:
        copied = dict(declarations_by_class)
        declarations_by_id = {
            declaration.ref.content_id: declaration
            for declaration in copied.values()
        }
        if (
            len(copied) != len(declarations_by_class)
            or len(declarations_by_id) != len(copied)
            or set(declarations_by_id) & provider_only_behavior_ids
        ):
            raise ValueError("Behavior admission inventory is not one-to-one")
        self._declarations_by_class = MappingProxyType(copied)
        self._declarations_by_id = MappingProxyType(declarations_by_id)
        self._provider_only_behavior_ids = provider_only_behavior_ids

    def bind_independent(
        self,
        behavior: object,
        *,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding | None:
        """Bind one known behavior with itself as provider."""
        declaration = self._declarations_by_class.get(type(behavior))
        if declaration is None:
            return None
        return self._bind_declared(
            behavior,
            declaration=declaration,
            provided_by_id=declaration.ref.content_id,
            origin_root_id=None,
            runtime_owner_uuid=runtime_owner_uuid,
        )

    def bind_root_owned(
        self,
        behavior: object,
        *,
        origin_root_id: str,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding | None:
        """Bind one explicitly root-owned behavior through a primitive root."""
        declaration = self._declarations_by_class.get(type(behavior))
        if declaration is None or "root_owned" not in declaration.descriptor.tags:
            return None
        return self._bind_declared(
            behavior,
            declaration=declaration,
            provided_by_id=origin_root_id,
            origin_root_id=origin_root_id,
            runtime_owner_uuid=runtime_owner_uuid,
        )

    def bind_child(
        self,
        behavior: object,
        *,
        provider_binding: BehaviorBinding,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Bind one child through an already authenticated primitive fact."""
        declaration = self._declarations_by_class.get(type(behavior))
        if isinstance(behavior, BaseHandler) and declaration is None:
            return self._bind_private_handler(
                behavior,
                behavior_id=provider_binding.behavior_id,
                origin_root_id=provider_binding.origin_root_id,
                runtime_owner_uuid=runtime_owner_uuid,
            )
        if declaration is None:
            raise ValueError("Provider-owned behavior has no cold class admission")
        return self._bind_declared(
            behavior,
            declaration=declaration,
            provided_by_id=provider_binding.behavior_id,
            origin_root_id=provider_binding.origin_root_id,
            runtime_owner_uuid=runtime_owner_uuid,
        )

    def bind_direct_child(
        self,
        behavior: object,
        *,
        provided_by_id: str,
        origin_root_id: str | None,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Bind one child through explicit item/root primitive facts."""
        declaration = self._declarations_by_class.get(type(behavior))
        if isinstance(behavior, BaseHandler) and declaration is None:
            return self._bind_private_handler(
                behavior,
                behavior_id=provided_by_id,
                origin_root_id=origin_root_id,
                runtime_owner_uuid=runtime_owner_uuid,
            )
        if declaration is None:
            raise ValueError("Direct child has no cold class admission")
        return self._bind_declared(
            behavior,
            declaration=declaration,
            provided_by_id=provided_by_id,
            origin_root_id=origin_root_id,
            runtime_owner_uuid=runtime_owner_uuid,
        )

    def bind_granted(
        self,
        behavior: object,
        *,
        provider_id: str,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Bind one explicit structural grant from a primitive provider ID."""
        declaration = self._declarations_by_class.get(type(behavior))
        if isinstance(behavior, BaseHandler) and declaration is None:
            if (
                provider_id not in self._declarations_by_id
                and provider_id not in self._provider_only_behavior_ids
            ):
                raise ValueError(
                    f"Unknown private handler provider {provider_id}"
                )
            return self._bind_private_handler(
                behavior,
                behavior_id=provider_id,
                origin_root_id=None,
                runtime_owner_uuid=runtime_owner_uuid,
            )
        if declaration is None:
            raise ValueError("Granted behavior has no cold class admission")
        return self._bind_declared(
            behavior,
            declaration=declaration,
            provided_by_id=provider_id,
            origin_root_id=None,
            runtime_owner_uuid=runtime_owner_uuid,
        )

    def _bind_private_handler(
        self,
        behavior: BaseHandler,
        *,
        behavior_id: str,
        origin_root_id: str | None,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        declaration = self._declarations_by_id.get(behavior_id)
        if behavior.content_kind is RuntimeBehaviorKind.UNCLASSIFIED:
            behavior.content_kind = (
                declaration.runtime_behavior_kind
                if declaration is not None
                else RuntimeBehaviorKind.TRAIT
            )
        if behavior.content_kind not in _HANDLER_RUNTIME_KINDS:
            raise ValueError(
                f"Unsupported private handler kind {behavior.content_kind.value}",
            )
        if behavior.semantic_key is None:
            behavior.semantic_key = behavior_id
        return self._install_binding(
            behavior,
            BehaviorBinding(
                behavior_id=behavior_id,
                provided_by_id=behavior_id,
                origin_root_id=origin_root_id,
                runtime_owner_uuid=runtime_owner_uuid,
            ),
        )

    def _bind_declared(
        self,
        behavior: object,
        *,
        declaration: ContentDeclaration,
        provided_by_id: str,
        origin_root_id: str | None,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        expected_kind = declaration.runtime_behavior_kind
        if expected_kind is None:
            raise ValueError(
                f"Behavior {declaration.ref.content_id} has no runtime kind",
            )
        self._validate_runtime_kind(behavior, expected_kind)
        return self._install_binding(
            behavior,
            BehaviorBinding(
                behavior_id=declaration.ref.content_id,
                provided_by_id=provided_by_id,
                origin_root_id=origin_root_id,
                runtime_owner_uuid=runtime_owner_uuid,
            ),
        )

    @staticmethod
    def _install_binding(
        behavior: object,
        binding: BehaviorBinding,
    ) -> BehaviorBinding:
        if not isinstance(behavior, (BaseAction, BaseCondition, BaseHandler)):
            raise TypeError(
                "BehaviorBinder accepts actions, conditions, and handlers",
            )
        existing = behavior.behavior_binding
        if existing is not None:
            if existing == binding:
                return existing
            raise ValueError(
                f"Runtime behavior {behavior.uuid} already has a conflicting binding",
            )
        behavior.behavior_binding = binding
        return binding

    @staticmethod
    def _validate_runtime_kind(
        behavior: object,
        expected_kind: RuntimeBehaviorKind,
    ) -> None:
        if isinstance(behavior, BaseAction):
            if expected_kind not in _ACTION_RUNTIME_KINDS:
                raise TypeError(f"{expected_kind.value} cannot bind an action")
            return
        if isinstance(behavior, BaseCondition):
            if expected_kind not in _CONDITION_RUNTIME_KINDS:
                raise TypeError(f"{expected_kind.value} cannot bind a condition")
            if behavior.content_kind != expected_kind:
                raise ValueError(
                    f"Condition kind {behavior.content_kind.value} does not match "
                    f"{expected_kind.value}",
                )
            return
        if isinstance(behavior, BaseHandler):
            if behavior.content_kind != expected_kind:
                raise ValueError(
                    f"Handler kind {behavior.content_kind.value} does not match "
                    f"{expected_kind.value}",
                )
            return
        raise TypeError(
            "BehaviorBinder accepts actions, conditions, and handlers",
        )


__all__ = ["BehaviorBinder"]
