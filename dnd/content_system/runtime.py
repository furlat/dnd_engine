"""Process-local ownership of one frozen, bootstrapped content system."""

from __future__ import annotations

from uuid import UUID

from dnd.content_system.behavior_bindings import BehaviorBinder
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.runtime import (
    BehaviorBinding,
    bind_runtime_behavior_child,
    install_runtime_behavior_binding_gateway,
    runtime_behavior_binding_gateway,
)


class ContentSystemRuntime:
    """Own exactly one immutable content registry for a process generation."""

    def __init__(
        self,
        *,
        owns_engine_behavior_gateway: bool = False,
    ) -> None:
        self._loaded: LoadedContentSystem | None = None
        self._materialization_count = 0
        self._behavior_binder: BehaviorBinder | None = None
        self._owns_engine_behavior_gateway = owns_engine_behavior_gateway

    @property
    def materialization_count(self) -> int:
        """Return the number of successful canonical materializations."""
        return self._materialization_count

    @property
    def is_installed(self) -> bool:
        """Return whether this process generation owns a frozen registry."""
        return self._loaded is not None

    def install(self, loaded: LoadedContentSystem) -> LoadedContentSystem:
        """Install once; permit idempotent bootstrap of the authenticated set."""
        existing = self._loaded
        if existing is None:
            binder = BehaviorBinder(loaded.registry)
            if self._owns_engine_behavior_gateway:
                install_runtime_behavior_binding_gateway(
                    binder,
                    content_set_digest=loaded.content_set_digest,
                )
            self._behavior_binder = binder
            self._loaded = loaded
            return loaded
        if existing.content_set_digest == loaded.content_set_digest:
            return existing
        raise RuntimeError(
            "A content system is already installed for this process generation",
        )

    def require(self) -> LoadedContentSystem:
        """Return the installed system or fail before gameplay begins."""
        if self._loaded is None:
            raise RuntimeError("Content system is not installed")
        return self._loaded

    def materialize(self, recipe: ContentRecipe, context: object) -> object:
        """Materialize through the sole installed registry and record usage."""
        loaded = self.require()
        binder = self._behavior_binder
        if binder is None:
            raise RuntimeError("Content system behavior binder is not installed")
        with runtime_behavior_binding_gateway(binder):
            value = loaded.registry.materialize(recipe, context)
        self._materialization_count += 1
        return value

    def bind_child(
        self,
        behavior: object,
        *,
        provider: object,
        runtime_owner_uuid: UUID,
    ) -> BehaviorBinding:
        """Bind one explicit provider-owned behavior in this runtime."""
        self.require()
        binder = self._behavior_binder
        if binder is None:
            raise RuntimeError("Content system behavior binder is not installed")
        with runtime_behavior_binding_gateway(binder):
            return bind_runtime_behavior_child(
                behavior,
                provider=provider,
                runtime_owner_uuid=runtime_owner_uuid,
            )


SERVER_CONTENT_SYSTEM_RUNTIME = ContentSystemRuntime(
    owns_engine_behavior_gateway=True,
)
