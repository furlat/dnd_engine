"""Pure declarations attached to authored content definitions."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable
from enum import Enum
from types import ModuleType
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, SerializeAsAny, model_validator
from pydantic_core import PydanticUndefined

from dnd.core.content.dependencies import ContentDependency
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
)
from dnd.core.content.effects import (
    AuthoredConditionEffectProfile,
    AuthoredConditionLifecycle,
    ConditionEffectCoverage,
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
    TYPED_DEFINITION = "typed_definition"


def behavior_content_ref(
    *,
    definition_kind: ContentDefinitionKind,
    runtime_behavior_kind: RuntimeBehaviorKind,
    pack_id: str,
    content_id: str,
    version: int,
) -> ContentRef:
    """Return the exact ref a behavior-identity declaration will own."""
    return ContentRef(
        pack_id=pack_id,
        definition_kind=definition_kind,
        content_id=content_id,
        content_version=version,
        definition_contract_hash=compute_definition_contract_hash(
            mode=ContentDeclarationMode.BEHAVIOR_IDENTITY,
            definition_kind=definition_kind,
            runtime_behavior_kind=runtime_behavior_kind,
        ),
    )


def compute_definition_contract_hash(
    *,
    mode: ContentDeclarationMode,
    definition_kind: ContentDefinitionKind,
    runtime_behavior_kind: RuntimeBehaviorKind | None = None,
    parameter_model: type[BaseModel] | None = None,
    definition_model: type[BaseModel] | None = None,
    contract_version: int = 1,
) -> str:
    """Hash one domain-separated definition API contract."""
    if mode == ContentDeclarationMode.FACTORY:
        if parameter_model is None:
            raise ValueError("factory definition contract requires parameters")
        if definition_model is not None:
            raise ValueError("factory contract cannot own a typed definition")
        parameter_schema = parameter_model.model_json_schema(mode="validation")
        definition_schema = None
    elif mode == ContentDeclarationMode.BEHAVIOR_IDENTITY:
        if parameter_model is not None:
            raise ValueError(
                "behavior identity contract cannot have factory parameters",
            )
        if runtime_behavior_kind is None:
            raise ValueError(
                "behavior identity contract requires runtime_behavior_kind",
            )
        parameter_schema = None
        definition_schema = None
    else:
        if parameter_model is not None or runtime_behavior_kind is not None:
            raise ValueError(
                "typed definition contract cannot construct runtime behavior",
            )
        if definition_model is None:
            raise ValueError("typed definition contract requires a model")
        parameter_schema = None
        definition_schema = definition_model.model_json_schema(mode="validation")
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
    if definition_schema is not None:
        payload["definition_schema"] = definition_schema
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
_TYPED_DEFINITION_KINDS = frozenset({
    ContentDefinitionKind.ACTION,
    ContentDefinitionKind.CLASS,
    ContentDefinitionKind.SUBCLASS,
    ContentDefinitionKind.SPECIES,
    ContentDefinitionKind.SPECIES_VARIANT,
    ContentDefinitionKind.BACKGROUND,
    ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE,
    ContentDefinitionKind.TRAIT,
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
    definition_payload: SerializeAsAny[BaseModel] | None = None
    dependencies: tuple[ContentDependency, ...] = ()
    condition_effect_coverage: ConditionEffectCoverage = (
        ConditionEffectCoverage.NONE
    )
    condition_effect_profile: AuthoredConditionEffectProfile | None = None
    condition_lifecycle: AuthoredConditionLifecycle | None = None
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
            if self.definition_payload is not None:
                raise ValueError(
                    "factory declaration cannot own typed definition",
                )
        elif self.mode == ContentDeclarationMode.BEHAVIOR_IDENTITY:
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
            if self.definition_payload is not None:
                raise ValueError(
                    "behavior_identity declaration cannot own typed definition",
                )
        else:
            if self.ref.definition_kind not in _TYPED_DEFINITION_KINDS:
                raise ValueError(
                    "typed_definition mode is reserved for structural build "
                    "definitions and authored action configurations",
                )
            if self.definition_payload is None:
                raise ValueError(
                    "typed_definition declaration requires definition_payload",
                )
            if (
                self.construction is not None
                or self.item_definition is not None
                or self.runtime_behavior_kind is not None
            ):
                raise ValueError(
                    "typed_definition declaration cannot construct runtime "
                    "behavior",
                )
            expected_contract_hash = compute_definition_contract_hash(
                mode=self.mode,
                definition_kind=self.ref.definition_kind,
                definition_model=type(self.definition_payload),
            )
        if self.ref.definition_contract_hash != expected_contract_hash:
            raise ValueError(
                "content ref definition contract does not authenticate "
                "the declaration",
            )
        if self.condition_effect_profile is not None:
            source_refs = {
                effect.source_ref.identity_key
                for effect in self.condition_effect_profile.effects
            }
            if source_refs != {self.ref.identity_key}:
                raise ValueError(
                    "declaration-owned condition effects must use the "
                    "declaration ref as their exact source",
                )
            if (
                self.condition_effect_coverage
                is not ConditionEffectCoverage.PROFILED
            ):
                raise ValueError(
                    "authored condition effects require profiled coverage",
                )
        elif (
            self.condition_effect_coverage
            is ConditionEffectCoverage.PROFILED
        ):
            raise ValueError(
                "profiled condition-effect coverage requires a profile",
            )
        if (
            self.condition_lifecycle is not None
            and self.runtime_behavior_kind != RuntimeBehaviorKind.CONDITION
        ):
            raise ValueError(
                "condition lifecycle metadata requires condition runtime "
                "behavior",
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
    condition_effect_profile: AuthoredConditionEffectProfile | None = None,
    condition_lifecycle: AuthoredConditionLifecycle | None = None,
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
            condition_effect_coverage=(
                ConditionEffectCoverage.PROFILED
                if condition_effect_profile is not None
                else (
                    ConditionEffectCoverage.LIFECYCLE_ONLY
                    if runtime_behavior_kind is RuntimeBehaviorKind.CONDITION
                    else ConditionEffectCoverage.NONE
                )
            ),
            condition_effect_profile=condition_effect_profile,
            condition_lifecycle=condition_lifecycle,
            construction=ContentConstruction(
                parameter_model=parameters,
                factory=factory,
            ),
        )
        setattr(factory, _DECLARATION_ATTRIBUTE, declaration)
        return factory

    return decorate


def typed_definition(
    *,
    definition_kind: ContentDefinitionKind,
    pack_id: str,
    content_id: str,
    version: int,
    descriptor: ContentDescriptorSpec,
    provenance: ContentProvenance,
    definition: BaseModel,
    dependencies: tuple[ContentDependency, ...] = (),
    condition_effect_profile: AuthoredConditionEffectProfile | None = None,
) -> Callable[[_Definition], _Definition]:
    """Attach one immutable data definition to a local declaration marker."""
    mode = ContentDeclarationMode.TYPED_DEFINITION
    ref = ContentRef(
        pack_id=pack_id,
        definition_kind=definition_kind,
        content_id=content_id,
        content_version=version,
        definition_contract_hash=compute_definition_contract_hash(
            mode=mode,
            definition_kind=definition_kind,
            definition_model=type(definition),
        ),
    )
    bound_descriptor = ContentDescriptor.from_spec(ref, descriptor)

    def decorate(marker: _Definition) -> _Definition:
        if _direct_content_declaration(marker) is not None:
            raise ValueError(f"{marker!r} already has a content declaration")
        declaration = ContentDeclaration(
            ref=ref,
            mode=mode,
            descriptor=bound_descriptor,
            provenance=provenance,
            definition_payload=definition,
            dependencies=dependencies,
            condition_effect_coverage=(
                ConditionEffectCoverage.PROFILED
                if condition_effect_profile is not None
                else ConditionEffectCoverage.NONE
            ),
            condition_effect_profile=condition_effect_profile,
        )
        setattr(marker, _DECLARATION_ATTRIBUTE, declaration)
        return marker

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
    condition_effect_profile: AuthoredConditionEffectProfile | None = None,
    condition_lifecycle: AuthoredConditionLifecycle | None = None,
) -> Callable[[_Definition], _Definition]:
    """Attach a resolvable, deliberately non-constructible behavior identity."""
    mode = ContentDeclarationMode.BEHAVIOR_IDENTITY
    ref = behavior_content_ref(
        definition_kind=definition_kind,
        runtime_behavior_kind=runtime_behavior_kind,
        pack_id=pack_id,
        content_id=content_id,
        version=version,
    )
    bound_descriptor = ContentDescriptor.from_spec(ref, descriptor)

    def decorate(definition: _Definition) -> _Definition:
        if _direct_content_declaration(definition) is not None:
            raise ValueError(
                f"{definition!r} already has a content declaration",
            )
        resolved_condition_lifecycle = condition_lifecycle
        if (
            resolved_condition_lifecycle is None
            and runtime_behavior_kind is RuntimeBehaviorKind.CONDITION
        ):
            model_fields = getattr(definition, "model_fields", None)
            if not isinstance(model_fields, dict):
                raise TypeError(
                    "condition behavior identity requires a Pydantic model "
                    "with lifecycle fields",
                )

            def field_default(field_name: str) -> object:
                field = model_fields.get(field_name)
                if field is None:
                    raise TypeError(
                        "condition behavior identity is missing lifecycle "
                        f"field {field_name}",
                    )
                if field.default_factory is not None:
                    return field.default_factory()
                if field.default is PydanticUndefined:
                    raise TypeError(
                        "condition behavior identity lifecycle field has no "
                        f"authored default: {field_name}",
                    )
                return field.default

            resolved_condition_lifecycle = (
                AuthoredConditionLifecycle.model_validate({
                    "tags": field_default("tags"),
                    "removal_triggers": field_default("removal_triggers"),
                    "agency_denial": field_default("agency_denial"),
                })
            )
        declaration = ContentDeclaration(
            ref=ref,
            mode=mode,
            descriptor=bound_descriptor,
            provenance=provenance,
            runtime_behavior_kind=runtime_behavior_kind,
            dependencies=dependencies,
            condition_effect_coverage=(
                ConditionEffectCoverage.PROFILED
                if condition_effect_profile is not None
                else (
                    ConditionEffectCoverage.LIFECYCLE_ONLY
                    if runtime_behavior_kind is RuntimeBehaviorKind.CONDITION
                    else ConditionEffectCoverage.NONE
                )
            ),
            condition_effect_profile=condition_effect_profile,
            condition_lifecycle=resolved_condition_lifecycle,
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
    condition_effect_profile: AuthoredConditionEffectProfile | None = None,
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
        condition_effect_profile=condition_effect_profile,
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
    condition_effect_profile: AuthoredConditionEffectProfile | None = None,
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
        condition_effect_profile=condition_effect_profile,
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
    condition_effect_profile: AuthoredConditionEffectProfile | None = None,
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
        condition_effect_profile=condition_effect_profile,
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


def replace_content_declaration_at_cold_startup(
    definition: object,
    declaration: ContentDeclaration,
) -> ContentDeclaration:
    """Replace one decorator result before registry freeze.

    Built-in composition uses this once to add cross-module authored metadata
    after every exact source and target declaration exists.  The source ref
    and immutable definition contract cannot change.
    """
    existing = get_content_declaration(definition)
    if existing.ref != declaration.ref:
        raise ValueError(
            "cold-start declaration replacement cannot change content ref",
        )
    if (
        existing.mode != declaration.mode
        or existing.runtime_behavior_kind
        != declaration.runtime_behavior_kind
        or existing.construction != declaration.construction
        or existing.definition_payload != declaration.definition_payload
    ):
        raise ValueError(
            "cold-start declaration replacement is metadata-only",
        )
    setattr(definition, _DECLARATION_ATTRIBUTE, declaration)
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
