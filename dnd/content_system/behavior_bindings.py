"""Validated one-time binding of authored identities to runtime behaviors."""

from __future__ import annotations

from uuid import UUID

from dnd.blocks.base_item import BaseItem
from dnd.core.base_actions import BaseAction
from dnd.core.base_conditions import BaseCondition
from dnd.core.content.identities import ContentRef
from dnd.core.content.registration import (
    ContentDeclaration,
    get_content_declaration,
)
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.content.runtime import (
    BehaviorBinding,
    RuntimeBehaviorKind,
    has_direct_behavior_declaration,
)
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
_HANDLER_RUNTIME_KINDS = _ACTION_RUNTIME_KINDS | _CONDITION_RUNTIME_KINDS


class BehaviorBinder:
    """Validate content closure and bind one live behavior exactly once."""

    def __init__(self, registry: FrozenContentRegistry) -> None:
        self._registry = registry

    def bind_independent(
        self,
        behavior: object,
        *,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Bind one directly declared behavior with itself as provider."""
        if not isinstance(behavior, (BaseAction, BaseCondition, BaseHandler)):
            raise TypeError(
                "Independent runtime behavior must be an action, condition, "
                "or handler",
            )
        declaration_source = type(behavior)
        declaration = self._resolve_decorated_source(declaration_source)
        expected_kind = declaration.runtime_behavior_kind
        if expected_kind is None:
            raise ValueError(
                f"Content {declaration.ref.identity_key} does not declare a "
                "runtime behavior kind",
            )
        return self.bind(
            behavior,
            declaration_source=declaration_source,
            expected_kind=expected_kind,
            provided_by_ref=declaration.ref,
            runtime_owner_uuid=runtime_owner_uuid,
        )

    def bind_root_owned(
        self,
        behavior: object,
        *,
        origin_root_ref: ContentRef,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding | None:
        """Bind only behavior explicitly authored as part of a durable root."""
        if not isinstance(behavior, (BaseAction, BaseCondition)):
            raise TypeError(
                "Root-owned runtime behavior must be an action or condition",
            )
        declaration_source = type(behavior)
        declaration = self._resolve_decorated_source(declaration_source)
        if "root_owned" not in declaration.descriptor.tags:
            return None
        expected_kind = declaration.runtime_behavior_kind
        if expected_kind is None:
            raise ValueError(
                f"Content {declaration.ref.identity_key} does not declare a "
                "runtime behavior kind",
            )
        self._registry.resolve_factory(origin_root_ref)
        return self.bind(
            behavior,
            declaration_source=declaration_source,
            expected_kind=expected_kind,
            provided_by_ref=origin_root_ref,
            origin_root_ref=origin_root_ref,
            runtime_owner_uuid=runtime_owner_uuid,
        )

    def bind_child(
        self,
        behavior: object,
        *,
        provider: object,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Bind one declared behavior or handler through its exact provider.

        Declared action and condition children retain their own authored
        definition while naming the item, action, or condition that granted
        them. Handlers deliberately preserve the existing provider-derived
        identity contract because many condition-owned handlers are private
        runtime implementation details rather than standalone declarations.
        """
        if isinstance(behavior, BaseHandler):
            return self._bind_handler_child(
                behavior,
                provider=provider,
                runtime_owner_uuid=runtime_owner_uuid,
            )
        if not isinstance(behavior, (BaseAction, BaseCondition)):
            raise TypeError(
                "Provider-owned runtime behavior must be an action, "
                "condition, or handler",
            )

        provider_ref, origin_root_ref = self._resolve_behavior_provider(
            provider,
            runtime_owner_uuid=runtime_owner_uuid,
        )
        declaration_source = type(behavior)
        declaration = self._resolve_decorated_source(declaration_source)
        expected_kind = declaration.runtime_behavior_kind
        if expected_kind is None:
            raise ValueError(
                f"Content {declaration.ref.identity_key} does not declare a "
                "runtime behavior kind",
            )
        return self.bind(
            behavior,
            declaration_source=declaration_source,
            expected_kind=expected_kind,
            provided_by_ref=provider_ref,
            origin_root_ref=origin_root_ref,
            runtime_owner_uuid=runtime_owner_uuid,
        )

    def bind_granted(
        self,
        behavior: object,
        *,
        provider_ref: ContentRef,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Bind a structural grant through an exact authored provider.

        This entry point is for durable character/creature composition where
        the provider is an authored feature rather than a live condition or
        action object. Declared behaviors retain their own exact definition.
        Undeclared implementation handlers inherit the provider definition
        without manufacturing a fake runtime provider object.
        """
        if not isinstance(behavior, (BaseAction, BaseCondition, BaseHandler)):
            raise TypeError(
                "Structurally granted runtime behavior must be an action, "
                "condition, or handler",
            )
        provider_declaration = self._registry.resolve_definition(provider_ref)
        if (
            isinstance(behavior, BaseHandler)
            and not has_direct_behavior_declaration(behavior)
        ):
            return self._bind_private_granted_handler(
                behavior,
                provider_declaration=provider_declaration,
                runtime_owner_uuid=runtime_owner_uuid,
            )

        declaration_source = type(behavior)
        declaration = self._resolve_decorated_source(declaration_source)
        expected_kind = declaration.runtime_behavior_kind
        if expected_kind is None:
            raise ValueError(
                f"Content {declaration.ref.identity_key} does not declare a "
                "runtime behavior kind",
            )
        return self.bind(
            behavior,
            declaration_source=declaration_source,
            expected_kind=expected_kind,
            provided_by_ref=provider_ref,
            runtime_owner_uuid=runtime_owner_uuid,
        )

    def _bind_private_granted_handler(
        self,
        behavior: BaseHandler,
        *,
        provider_declaration: ContentDeclaration,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Give one private structural handler its provider's exact identity."""
        provider_kind = provider_declaration.runtime_behavior_kind
        if provider_kind is None:
            raise ValueError(
                f"Private handler provider "
                f"{provider_declaration.ref.identity_key} does not declare a "
                "runtime behavior kind",
            )
        if behavior.content_kind == RuntimeBehaviorKind.UNCLASSIFIED:
            behavior.content_kind = provider_kind
        if behavior.content_kind not in _HANDLER_RUNTIME_KINDS:
            raise ValueError(
                f"Provider-owned handler content kind "
                f"{behavior.content_kind.value} is not a supported runtime "
                "behavior kind",
            )
        if behavior.semantic_key is None:
            behavior.semantic_key = self._private_handler_semantic_key(
                provider_declaration.ref,
                behavior.name,
            )
        return self._install_binding(
            behavior,
            BehaviorBinding(
                definition_ref=provider_declaration.ref,
                provided_by_ref=provider_declaration.ref,
                origin_root_ref=None,
                runtime_owner_uuid=runtime_owner_uuid,
            ),
        )

    def _bind_handler_child(
        self,
        behavior: BaseHandler,
        *,
        provider: object,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Preserve provider-derived identity for private runtime handlers."""
        if not isinstance(provider, (BaseAction, BaseCondition)):
            raise TypeError(
                "Handler provider must be a bound action or condition",
            )
        provider_binding = provider.behavior_binding
        if provider_binding is None:
            raise ValueError("Handler provider has no runtime behavior binding")

        declaration_source = type(provider)
        declaration = self._resolve_decorated_source(declaration_source)
        if provider_binding.definition_ref != declaration.ref:
            raise ValueError(
                "Handler provider binding does not match its exact declaration",
            )
        expected_kind = declaration.runtime_behavior_kind
        if expected_kind is None:
            raise ValueError(
                f"Content {declaration.ref.identity_key} does not declare a "
                "runtime behavior kind",
            )
        if behavior.content_kind == RuntimeBehaviorKind.UNCLASSIFIED:
            behavior.content_kind = expected_kind
        if behavior.semantic_key is None:
            behavior.semantic_key = self._private_handler_semantic_key(
                declaration.ref,
                behavior.name,
            )
        if behavior.content_kind not in _HANDLER_RUNTIME_KINDS:
            raise ValueError(
                f"Provider-owned handler content kind "
                f"{behavior.content_kind.value} is not a supported runtime "
                "behavior kind",
            )
        origin_root_ref = provider_binding.origin_root_ref
        self._registry.resolve_definition(declaration.ref)
        if origin_root_ref is not None:
            self._registry.resolve_factory(origin_root_ref)
            self._require_reachable(
                source_ref=origin_root_ref,
                target_ref=declaration.ref,
                relation_name="origin root",
            )
        return self._install_binding(
            behavior,
            BehaviorBinding(
                definition_ref=declaration.ref,
                provided_by_ref=declaration.ref,
                origin_root_ref=origin_root_ref,
                runtime_owner_uuid=runtime_owner_uuid,
            ),
        )

    @staticmethod
    def _private_handler_semantic_key(
        provider_ref: ContentRef,
        handler_name: str,
    ) -> str:
        """Return one deterministic provider-scoped implementation key."""
        normalized_name = "_".join(
            fragment
            for fragment in "".join(
                character.lower() if character.isalnum() else "_"
                for character in handler_name
            ).split("_")
            if fragment
        )
        return (
            f"{provider_ref.identity_key}#handler."
            f"{normalized_name or 'effect'}"
        )

    def _resolve_behavior_provider(
        self,
        provider: object,
        *,
        runtime_owner_uuid: UUID,
    ) -> tuple[ContentRef, ContentRef | None]:
        """Return the exact provider and durable root for a declared child."""
        if isinstance(provider, BaseItem):
            provider_ref = provider.content_ref
            if provider_ref is None:
                raise ValueError("Item behavior provider has no content reference")
            self._registry.resolve_factory(provider_ref)
            if runtime_owner_uuid != provider.uuid:
                raise ValueError(
                    "Item-provided behavior must use the item UUID as its "
                    "runtime owner",
                )
            return provider_ref, provider_ref

        if not isinstance(provider, (BaseAction, BaseCondition)):
            raise TypeError(
                "Behavior provider must be a bound item, action, or condition",
            )
        provider_binding = provider.behavior_binding
        if provider_binding is None:
            raise ValueError("Behavior provider has no runtime behavior binding")
        provider_declaration = self._resolve_decorated_source(type(provider))
        if provider_binding.definition_ref != provider_declaration.ref:
            raise ValueError(
                "Behavior provider binding does not match its exact declaration",
            )
        return provider_declaration.ref, provider_binding.origin_root_ref

    def bind(
        self,
        behavior: BaseAction | BaseCondition | BaseHandler,
        *,
        declaration_source: object,
        expected_kind: RuntimeBehaviorKind,
        provided_by_ref: ContentRef,
        runtime_owner_uuid: UUID,
        origin_root_ref: ContentRef | None = None,
    ) -> BehaviorBinding:
        """Validate and install an immutable binding before runtime admission.

        Args:
            behavior: Unadmitted action, condition, or handler being bound.
            declaration_source: Decorated class or function that authored the
                behavior definition.
            expected_kind: Explicit runtime family expected by the caller.
            provided_by_ref: Definition that installed or granted the behavior.
            runtime_owner_uuid: Encounter-local owner of this behavior instance.
            origin_root_ref: Optional constructible durable root.

        Returns:
            The installed binding, or the existing equal binding on an
            idempotent repeated call.

        Raises:
            ValueError: If identity, kind, closure, or an existing binding
                conflicts.
            TypeError: If the target family is incompatible or a declared root
                is not constructible.
        """
        declaration = self._resolve_decorated_source(declaration_source)
        self._validate_runtime_kind(behavior, declaration, expected_kind)
        self._registry.resolve_definition(provided_by_ref)
        self._require_reachable(
            source_ref=provided_by_ref,
            target_ref=declaration.ref,
            relation_name="provider",
        )

        if origin_root_ref is not None:
            self._registry.resolve_factory(origin_root_ref)
            self._require_reachable(
                source_ref=origin_root_ref,
                target_ref=provided_by_ref,
                relation_name="origin root",
            )

        binding = BehaviorBinding(
            definition_ref=declaration.ref,
            provided_by_ref=provided_by_ref,
            origin_root_ref=origin_root_ref,
            runtime_owner_uuid=runtime_owner_uuid,
        )
        return self._install_binding(behavior, binding)

    def _install_binding(
        self,
        behavior: BaseAction | BaseCondition | BaseHandler,
        binding: BehaviorBinding,
    ) -> BehaviorBinding:
        """Install one validated immutable binding exactly once."""
        existing = behavior.behavior_binding
        if existing is not None:
            if existing == binding:
                return existing
            raise ValueError(
                f"Runtime behavior {behavior.uuid} already has a conflicting "
                "content binding",
            )
        behavior.behavior_binding = binding
        return binding

    def _resolve_decorated_source(
        self,
        declaration_source: object,
    ) -> ContentDeclaration:
        source_declaration = get_content_declaration(declaration_source)
        registered = self._registry.resolve_definition(source_declaration.ref)
        if registered is not source_declaration:
            raise ValueError(
                "Behavior declaration source is not the exact declaration "
                f"installed for {source_declaration.ref.identity_key}",
            )
        return registered

    def _validate_runtime_kind(
        self,
        behavior: BaseAction | BaseCondition | BaseHandler,
        declaration: ContentDeclaration,
        expected_kind: RuntimeBehaviorKind,
    ) -> None:
        declared_kind = declaration.runtime_behavior_kind
        if declared_kind is None:
            raise ValueError(
                f"Content {declaration.ref.identity_key} does not declare a "
                "runtime behavior kind",
            )
        if declared_kind != expected_kind:
            raise ValueError(
                f"Runtime behavior kind mismatch for "
                f"{declaration.ref.identity_key}: declared "
                f"{declared_kind.value}, expected {expected_kind.value}",
            )
        if isinstance(behavior, BaseAction):
            if expected_kind not in _ACTION_RUNTIME_KINDS:
                raise TypeError(
                    f"{expected_kind.value} cannot bind a BaseAction",
                )
            return
        if isinstance(behavior, BaseCondition):
            if expected_kind not in _CONDITION_RUNTIME_KINDS:
                raise TypeError(
                    f"{expected_kind.value} cannot bind a BaseCondition",
                )
            if behavior.content_kind != expected_kind:
                raise ValueError(
                    f"Condition content kind {behavior.content_kind.value} "
                    f"does not match expected {expected_kind.value}",
                )
            return
        if isinstance(behavior, BaseHandler):
            if behavior.content_kind != expected_kind:
                raise ValueError(
                    f"Handler content kind {behavior.content_kind.value} does "
                    f"not match expected {expected_kind.value}",
                )
            return
        raise TypeError(
            "BehaviorBinder accepts only BaseAction, BaseCondition, or "
            "BaseHandler instances",
        )

    def _require_reachable(
        self,
        *,
        source_ref: ContentRef,
        target_ref: ContentRef,
        relation_name: str,
    ) -> None:
        if self._is_reachable(source_ref, target_ref):
            return
        raise ValueError(
            f"Behavior {target_ref.identity_key} is not reachable from "
            f"{relation_name} {source_ref.identity_key} through declared "
            "content dependencies",
        )

    def _is_reachable(
        self,
        source_ref: ContentRef,
        target_ref: ContentRef,
    ) -> bool:
        pending = [self._registry.resolve_definition(source_ref)]
        visited: set[str] = set()
        while pending:
            declaration = pending.pop()
            key = declaration.ref.identity_key
            if key in visited:
                continue
            visited.add(key)
            if declaration.ref == target_ref:
                return True
            for dependency in declaration.dependencies:
                try:
                    target = self._registry.resolve_definition(
                        dependency.target_ref,
                    )
                except KeyError:
                    if dependency.required:
                        raise
                    continue
                pending.append(target)
        return False
