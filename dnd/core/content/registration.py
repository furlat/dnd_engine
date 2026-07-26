"""Pure declarations attached to authored content definitions."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable
from enum import Enum
from types import ModuleType
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

from dnd.core.content.dependencies import ContentDependency
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.item_definitions import ItemDefinition
from dnd.core.content.provenance import ContentProvenance
from dnd.core.content.runtime import RuntimeBehaviorKind


_DECLARATION_ATTRIBUTE = "__dnd_content_declaration__"
_Factory = TypeVar("_Factory", bound=Callable[..., object])
_Definition = TypeVar("_Definition")


class ContentDeclarationMode(str, Enum):
    """Whether a definition is constructible or metadata-only."""

    FACTORY = "factory"
    BEHAVIOR_IDENTITY = "behavior_identity"


def compute_definition_contract_hash(
    *,
    mode: ContentDeclarationMode,
    definition_kind: ContentDefinitionKind,
    runtime_behavior_kind: RuntimeBehaviorKind | None = None,
    parameter_model: type[BaseModel] | None = None,
    contract_version: int = 1,
) -> str:
    """Hash one domain-separated definition API contract."""
    if mode == ContentDeclarationMode.FACTORY:
        if parameter_model is None:
            raise ValueError("factory definition contract requires parameters")
        parameter_schema = parameter_model.model_json_schema(mode="validation")
    else:
        if parameter_model is not None:
            raise ValueError(
                "behavior identity contract cannot have factory parameters",
            )
        if runtime_behavior_kind is None:
            raise ValueError(
                "behavior identity contract requires runtime_behavior_kind",
            )
        parameter_schema = None
    payload = {
        "contract_version": contract_version,
        "mode": mode.value,
        "definition_kind": definition_kind.value,
        "runtime_behavior_kind": (
            runtime_behavior_kind.value
            if runtime_behavior_kind is not None
            else None
        ),
        "parameter_schema": parameter_schema,
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ContentConstruction(BaseModel):
    """Private callable contract for one constructible definition."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        frozen=True,
    )

    parameter_model: type[BaseModel]
    factory: Callable[[object, BaseModel], object]

    @model_validator(mode="after")
    def _validate_factory_shape(self) -> "ContentConstruction":
        parameters = tuple(inspect.signature(self.factory).parameters.values())
        positional = tuple(
            parameter
            for parameter in parameters
            if parameter.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }
        )
        if (
            len(positional) != 2
            or len(parameters) != 2
        ):
            raise ValueError(
                "content factory must accept exactly two positional arguments: "
                "materialization context and typed parameters",
            )
        return self


_METADATA_ONLY_KINDS = frozenset({
    ContentDefinitionKind.ACTION,
    ContentDefinitionKind.SPELL,
    ContentDefinitionKind.CONDITION,
    ContentDefinitionKind.TRAIT,
    ContentDefinitionKind.REACTION,
    ContentDefinitionKind.FEAT,
    ContentDefinitionKind.CLASS_FEATURE,
    ContentDefinitionKind.RULE_PRIMITIVE,
})


class ContentDeclaration(BaseModel):
    """One exact constructible or metadata-only authored definition."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        frozen=True,
    )

    ref: ContentRef
    mode: ContentDeclarationMode
    descriptor: ContentDescriptor
    provenance: ContentProvenance
    runtime_behavior_kind: RuntimeBehaviorKind | None = None
    item_definition: ItemDefinition | None = None
    dependencies: tuple[ContentDependency, ...] = ()
    construction: ContentConstruction | None = None

    @model_validator(mode="after")
    def _validate_bound_contract(self) -> "ContentDeclaration":
        if self.descriptor.ref != self.ref:
            raise ValueError("descriptor ref must match declaration ref")
        item_owned_kind = self.ref.definition_kind in {
            ContentDefinitionKind.ITEM,
            ContentDefinitionKind.ENVIRONMENT_OBJECT,
        }
        if self.mode == ContentDeclarationMode.FACTORY:
            if self.construction is None:
                raise ValueError(
                    "factory declaration requires a construction contract",
                )
            expected_contract_hash = compute_definition_contract_hash(
                mode=self.mode,
                definition_kind=self.ref.definition_kind,
                runtime_behavior_kind=self.runtime_behavior_kind,
                parameter_model=self.construction.parameter_model,
            )
            if item_owned_kind and self.item_definition is None:
                raise ValueError(
                    "item and environment_object declarations require "
                    "item_definition",
                )
            if not item_owned_kind and self.item_definition is not None:
                raise ValueError(
                    "item_definition is reserved for item and "
                    "environment_object declarations",
                )
        else:
            if self.ref.definition_kind not in _METADATA_ONLY_KINDS:
                raise ValueError(
                    "behavior_identity mode is reserved for behavior kinds",
                )
            if self.construction is not None:
                raise ValueError(
                    "behavior_identity declaration cannot be constructible",
                )
            if self.item_definition is not None:
                raise ValueError(
                    "behavior_identity declaration cannot own item_definition",
                )
            if self.runtime_behavior_kind is None:
                raise ValueError(
                    "behavior_identity declaration requires "
                    "runtime_behavior_kind",
                )
            expected_contract_hash = compute_definition_contract_hash(
                mode=self.mode,
                definition_kind=self.ref.definition_kind,
                runtime_behavior_kind=self.runtime_behavior_kind,
            )
        if self.ref.definition_contract_hash != expected_contract_hash:
            raise ValueError(
                "content ref definition contract does not authenticate "
                "the declaration",
            )
        return self


def content_factory(
    *,
    definition_kind: ContentDefinitionKind,
    pack_id: str,
    content_id: str,
    version: int,
    parameters: type[BaseModel],
    descriptor: ContentDescriptorSpec,
    provenance: ContentProvenance,
    runtime_behavior_kind: RuntimeBehaviorKind | None = None,
    item_definition: ItemDefinition | None = None,
    dependencies: tuple[ContentDependency, ...] = (),
) -> Callable[[_Factory], _Factory]:
    """Return a pure decorator for one typed factory definition."""
    mode = ContentDeclarationMode.FACTORY
    contract_hash = compute_definition_contract_hash(
        mode=mode,
        definition_kind=definition_kind,
        runtime_behavior_kind=runtime_behavior_kind,
        parameter_model=parameters,
    )
    ref = ContentRef(
        pack_id=pack_id,
        definition_kind=definition_kind,
        content_id=content_id,
        content_version=version,
        definition_contract_hash=contract_hash,
    )
    bound_descriptor = ContentDescriptor.from_spec(ref, descriptor)

    def decorate(factory: _Factory) -> _Factory:
        if _direct_content_declaration(factory) is not None:
            raise ValueError(f"{factory!r} already has a content declaration")
        declaration = ContentDeclaration(
            ref=ref,
            mode=mode,
            descriptor=bound_descriptor,
            provenance=provenance,
            runtime_behavior_kind=runtime_behavior_kind,
            item_definition=item_definition,
            dependencies=dependencies,
            construction=ContentConstruction(
                parameter_model=parameters,
                factory=factory,
            ),
        )
        setattr(factory, _DECLARATION_ATTRIBUTE, declaration)
        return factory

    return decorate


def behavior_identity(
    *,
    definition_kind: ContentDefinitionKind,
    runtime_behavior_kind: RuntimeBehaviorKind,
    pack_id: str,
    content_id: str,
    version: int,
    descriptor: ContentDescriptorSpec,
    provenance: ContentProvenance,
    dependencies: tuple[ContentDependency, ...] = (),
) -> Callable[[_Definition], _Definition]:
    """Attach a resolvable, deliberately non-constructible behavior identity."""
    mode = ContentDeclarationMode.BEHAVIOR_IDENTITY
    ref = ContentRef(
        pack_id=pack_id,
        definition_kind=definition_kind,
        content_id=content_id,
        content_version=version,
        definition_contract_hash=compute_definition_contract_hash(
            mode=mode,
            definition_kind=definition_kind,
            runtime_behavior_kind=runtime_behavior_kind,
        ),
    )
    bound_descriptor = ContentDescriptor.from_spec(ref, descriptor)

    def decorate(definition: _Definition) -> _Definition:
        if _direct_content_declaration(definition) is not None:
            raise ValueError(
                f"{definition!r} already has a content declaration",
            )
        declaration = ContentDeclaration(
            ref=ref,
            mode=mode,
            descriptor=bound_descriptor,
            provenance=provenance,
            runtime_behavior_kind=runtime_behavior_kind,
            dependencies=dependencies,
        )
        setattr(definition, _DECLARATION_ATTRIBUTE, declaration)
        return definition

    return decorate


def item_factory(
    *,
    pack_id: str,
    content_id: str,
    version: int,
    parameters: type[BaseModel],
    descriptor: ContentDescriptorSpec,
    provenance: ContentProvenance,
    item_definition: ItemDefinition,
    dependencies: tuple[ContentDependency, ...] = (),
) -> Callable[[_Factory], _Factory]:
    """Declare an item reconstruction factory."""
    return content_factory(
        definition_kind=ContentDefinitionKind.ITEM,
        pack_id=pack_id,
        content_id=content_id,
        version=version,
        parameters=parameters,
        descriptor=descriptor,
        provenance=provenance,
        item_definition=item_definition,
        dependencies=dependencies,
    )


def environment_object_factory(
    *,
    pack_id: str,
    content_id: str,
    version: int,
    parameters: type[BaseModel],
    descriptor: ContentDescriptorSpec,
    provenance: ContentProvenance,
    item_definition: ItemDefinition,
    dependencies: tuple[ContentDependency, ...] = (),
) -> Callable[[_Factory], _Factory]:
    """Declare a non-possession environment-object reconstruction factory."""
    return content_factory(
        definition_kind=ContentDefinitionKind.ENVIRONMENT_OBJECT,
        pack_id=pack_id,
        content_id=content_id,
        version=version,
        parameters=parameters,
        descriptor=descriptor,
        provenance=provenance,
        item_definition=item_definition,
        dependencies=dependencies,
    )


def creature_factory(
    *,
    pack_id: str,
    content_id: str,
    version: int,
    parameters: type[BaseModel],
    descriptor: ContentDescriptorSpec,
    provenance: ContentProvenance,
    dependencies: tuple[ContentDependency, ...] = (),
) -> Callable[[_Factory], _Factory]:
    """Declare a creature reconstruction factory."""
    return content_factory(
        definition_kind=ContentDefinitionKind.CREATURE,
        pack_id=pack_id,
        content_id=content_id,
        version=version,
        parameters=parameters,
        descriptor=descriptor,
        provenance=provenance,
        dependencies=dependencies,
    )


def get_content_declaration(definition: object) -> ContentDeclaration:
    """Return the declaration authored directly on a factory or class.

    Content identity is never inherited by an undecorated subclass. A
    subclass is a distinct runtime rule until it receives its own exact
    declaration.
    """
    declaration = _direct_content_declaration(definition)
    if not isinstance(declaration, ContentDeclaration):
        raise ValueError(f"{definition!r} has no content declaration")
    return declaration


def _direct_content_declaration(
    definition: object,
) -> ContentDeclaration | None:
    """Return only a declaration stored directly on ``definition``."""
    namespace = getattr(definition, "__dict__", None)
    if namespace is None:
        return None
    declaration = namespace.get(_DECLARATION_ATTRIBUTE)
    return (
        declaration
        if isinstance(declaration, ContentDeclaration)
        else None
    )


def scan_module_content_declarations(
    module: ModuleType,
) -> tuple[ContentDeclaration, ...]:
    """Return declarations defined locally by one already-imported module."""
    declarations: dict[str, ContentDeclaration] = {}
    for value in vars(module).values():
        if getattr(value, "__module__", None) != module.__name__:
            continue
        declaration = _direct_content_declaration(value)
        if not isinstance(declaration, ContentDeclaration):
            continue
        existing = declarations.get(declaration.ref.identity_key)
        if existing is not None and existing is not declaration:
            raise ValueError(
                "Multiple local declarations use "
                f"{declaration.ref.identity_key}",
            )
        declarations[declaration.ref.identity_key] = declaration
    return tuple(declarations[key] for key in sorted(declarations))
