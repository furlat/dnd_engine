"""Dependency-neutral contracts for the canonical content system."""

from __future__ import annotations

import sys
from collections.abc import Callable
from types import ModuleType
from typing import cast

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentVisibility,
)
from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
)
from dnd.core.content.item_definitions import (
    ItemDefinition,
    ItemPersistencePolicy,
)
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
    ContentSource,
    ContentSourceFamily,
    RulesBaseline,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentConstruction,
    ContentDeclaration,
    ContentDeclarationMode,
    get_content_declaration,
    item_factory,
    scan_module_content_declarations,
)
from dnd.core.content.registry import ContentRegistryBuilder
from dnd.core.content.runtime import HandlerDispatchOutcome, RuntimeBehaviorKind


class _TestItemParameters(BaseModel):
    """Typed parameters used by the fixture factory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    charges: int


_SRD_SOURCE = ContentSource(
    source_id="wotc.srd_5_1_cc",
    source_family=ContentSourceFamily.SRD_5_1_CC,
    title="System Reference Document 5.1",
    source_version="5.1",
    rules_baseline=RulesBaseline.RULES_2014,
    license_id="CC-BY-4.0",
    canonical_uri="https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf",
    document_digest="a" * 64,
    attribution_text="SRD 5.1 by Wizards of the Coast, licensed under CC-BY-4.0.",
)

_SRD_PROVENANCE = ContentProvenance(
    primary_source_id=_SRD_SOURCE.source_id,
    source_anchor="Equipment / Adventuring Gear",
    relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
    fidelity=ContentFidelity.PARTIAL,
    review_status=ContentReviewStatus.REVIEWED,
)


@item_factory(
    pack_id="fixture.core",
    content_id="item.clockwork_flask",
    version=1,
    parameters=_TestItemParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Clockwork Flask",
        description="A deterministic content-system fixture.",
        visibility=ContentVisibility.PUBLIC,
        tags=("fixture", "item"),
    ),
    provenance=_SRD_PROVENANCE,
    item_definition=ItemDefinition(
        persistence_policy=ItemPersistencePolicy.POSSESSION,
    ),
)
def _create_test_item(context: object, parameters: _TestItemParameters) -> tuple[object, int]:
    """Return enough data to prove typed parameter materialization."""
    return context, parameters.charges


def test_existing_runtime_content_contracts_remain_available_from_package() -> None:
    """The atomic module-to-package move preserves the existing public surface."""
    assert RuntimeBehaviorKind.ITEM.value == "item"
    assert HandlerDispatchOutcome.EMITTED_EVENTS.value == "emitted_events"


def test_content_ref_is_normalized_namespaced_and_contract_bound() -> None:
    """Durable content identity cannot fall back to a display name or Python path."""
    declaration = get_content_declaration(_create_test_item)
    ref = declaration.ref

    assert ref.pack_id == "fixture.core"
    assert ref.definition_kind == ContentDefinitionKind.ITEM
    assert ref.content_id == "item.clockwork_flask"
    assert ref.content_version == 1
    assert len(ref.definition_contract_hash) == 64
    assert ref.identity_key == "fixture.core:item:item.clockwork_flask@1"

    for invalid in ("Fixture.Core", "fixture core", "dnd.items.TestItem", ""):
        with pytest.raises(ValidationError):
            ContentRef(
                pack_id=invalid,
                definition_kind=ContentDefinitionKind.ITEM,
                content_id="item.valid",
                content_version=1,
                definition_contract_hash="b" * 64,
            )


def test_recipe_digest_is_canonical_and_self_authenticating() -> None:
    """JSON key order cannot change recipe identity and tampering fails validation."""
    ref = get_content_declaration(_create_test_item).ref
    first = ContentRecipe.create(
        ref=ref,
        parameters={"charges": 3, "metadata": {"b": 2, "a": 1}},
    )
    second = ContentRecipe.create(
        ref=ref,
        parameters={"metadata": {"a": 1, "b": 2}, "charges": 3},
    )

    assert first.recipe_digest == second.recipe_digest
    tampered = first.model_dump(mode="json")
    tampered["parameters"]["charges"] = 4
    with pytest.raises(ValidationError, match="recipe_digest"):
        ContentRecipe.model_validate(tampered)


def test_materialization_rejects_mutated_validated_recipe_parameters() -> None:
    """Nested mutable JSON cannot bypass a recipe's authenticated digest."""
    declaration = get_content_declaration(_create_test_item)
    builder = ContentRegistryBuilder()
    builder.add_source(_SRD_SOURCE)
    builder.add_declaration(declaration)
    registry = builder.freeze(pack_dependencies={"fixture.core": frozenset()})

    top_level = ContentRecipe.create(
        ref=declaration.ref,
        parameters={"charges": 1},
    )
    top_level.parameters["charges"] = 9
    with pytest.raises(ValueError, match="recipe_digest"):
        registry.materialize(top_level, object())

    nested = ContentRecipe.create(
        ref=declaration.ref,
        parameters={"charges": 1, "metadata": {"history": ["original"]}},
    )
    metadata = nested.parameters["metadata"]
    assert isinstance(metadata, dict)
    history = metadata["history"]
    assert isinstance(history, list)
    history.append("tampered")
    with pytest.raises(ValueError, match="recipe_digest"):
        registry.materialize(nested, object())


def test_provenance_keeps_rules_source_separate_from_runtime_origin() -> None:
    """SRD, adaptation, original, and fixture provenance are authored contracts."""
    assert _SRD_SOURCE.source_family == ContentSourceFamily.SRD_5_1_CC
    assert _SRD_SOURCE.rules_baseline == RulesBaseline.RULES_2014
    assert _SRD_PROVENANCE.primary_source_id == _SRD_SOURCE.source_id
    assert _SRD_PROVENANCE.fidelity == ContentFidelity.PARTIAL

    invalid_source = _SRD_SOURCE.model_dump(mode="json")
    invalid_source["document_digest"] = ""
    with pytest.raises(ValidationError):
        ContentSource.model_validate(invalid_source)


def test_factory_decorator_is_pure_and_scanner_ignores_imported_aliases() -> None:
    """Declarations attach to definitions without mutating a process-global registry."""
    declaration = get_content_declaration(_create_test_item)
    assert declaration.mode == ContentDeclarationMode.FACTORY
    assert declaration.construction is not None
    assert declaration.construction.parameter_model is _TestItemParameters
    assert declaration.descriptor.ref == declaration.ref
    assert declaration.provenance == _SRD_PROVENANCE

    fixture_module = ModuleType("fixture_importing_module")
    setattr(fixture_module, "imported_alias", _create_test_item)
    sys.modules[fixture_module.__name__] = fixture_module
    try:
        assert scan_module_content_declarations(fixture_module) == ()
    finally:
        del sys.modules[fixture_module.__name__]

    local_declarations = scan_module_content_declarations(sys.modules[__name__])
    assert tuple(row.ref for row in local_declarations) == (declaration.ref,)


def test_frozen_registry_validates_dependencies_and_materializes_typed_parameters() -> None:
    """One immutable registry resolves recipes in O(1) after complete validation."""
    declaration = get_content_declaration(_create_test_item)
    builder = ContentRegistryBuilder()
    builder.add_source(_SRD_SOURCE)
    builder.add_declaration(declaration)
    registry = builder.freeze(pack_dependencies={"fixture.core": frozenset()})

    recipe = ContentRecipe.create(ref=declaration.ref, parameters={"charges": 5})
    context = object()
    assert registry.materialize(recipe, context) == (context, 5)
    assert registry.resolve_definition(declaration.ref) is declaration
    assert registry.resolve_factory(declaration.ref) is declaration

    with pytest.raises(RuntimeError, match="frozen"):
        builder.add_declaration(declaration)


def test_direct_declaration_cannot_lie_about_parameter_contract() -> None:
    """The authenticated definition hash is bound to the parameter model."""

    class DifferentParameters(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True)

        quantity: int

    declaration = get_content_declaration(_create_test_item)
    assert declaration.construction is not None
    with pytest.raises(ValidationError, match="definition contract"):
        ContentDeclaration(
            ref=declaration.ref,
            mode=declaration.mode,
            descriptor=declaration.descriptor,
            provenance=declaration.provenance,
            item_definition=declaration.item_definition,
            construction=ContentConstruction(
                parameter_model=DifferentParameters,
                factory=declaration.construction.factory,
            ),
        )


def test_direct_declaration_requires_exact_two_argument_factory_shape() -> None:
    """Factory signature errors fail during registry construction, not gameplay."""
    declaration = get_content_declaration(_create_test_item)

    def invalid_factory(parameters: _TestItemParameters) -> object:
        return parameters

    assert declaration.construction is not None
    with pytest.raises(ValidationError, match="exactly two positional"):
        ContentDeclaration(
            ref=declaration.ref,
            mode=declaration.mode,
            descriptor=declaration.descriptor,
            provenance=declaration.provenance,
            item_definition=declaration.item_definition,
            construction=ContentConstruction(
                parameter_model=declaration.construction.parameter_model,
                factory=cast(
                    Callable[[object, BaseModel], object],
                    invalid_factory,
                ),
            ),
        )


def test_item_declaration_requires_explicit_persistence_semantics() -> None:
    """No item can enter the registry without a settlement policy."""
    declaration = get_content_declaration(_create_test_item)
    assert declaration.construction is not None
    with pytest.raises(ValidationError, match="require item_definition"):
        ContentDeclaration(
            ref=declaration.ref,
            mode=declaration.mode,
            descriptor=declaration.descriptor,
            provenance=declaration.provenance,
            construction=declaration.construction,
        )


def test_registry_rejects_missing_cross_pack_dependencies_and_construction_cycles() -> None:
    """A pack cannot become ready with a broken or cyclic construction closure."""
    first = get_content_declaration(_create_test_item)
    missing_ref = first.ref.model_copy(
        update={
            "pack_id": "fixture.missing",
            "content_id": "item.missing",
            "definition_contract_hash": "c" * 64,
        },
    )
    dependent = first.model_copy(
        update={
            "dependencies": (
                ContentDependency(
                    relation=ContentDependencyRelation.CREATES_ITEM,
                    target_ref=missing_ref,
                    phase=ContentDependencyPhase.CONSTRUCTION,
                ),
            ),
        },
    )
    missing_builder = ContentRegistryBuilder()
    missing_builder.add_source(_SRD_SOURCE)
    missing_builder.add_declaration(dependent)
    with pytest.raises(ValueError, match="Missing content dependency"):
        missing_builder.freeze(
            pack_dependencies={"fixture.core": frozenset({"fixture.missing"})},
        )

    second = first.model_copy(
        update={
            "ref": first.ref.model_copy(
                update={
                    "content_id": "item.second",
                    "definition_contract_hash": "d" * 64,
                },
            ),
        },
    )
    first_to_second = first.model_copy(
        update={
            "dependencies": (
                ContentDependency(
                    relation=ContentDependencyRelation.CREATES_ITEM,
                    target_ref=second.ref,
                    phase=ContentDependencyPhase.CONSTRUCTION,
                ),
            ),
        },
    )
    second_to_first = second.model_copy(
        update={
            "descriptor": second.descriptor.model_copy(update={"ref": second.ref}),
            "dependencies": (
                ContentDependency(
                    relation=ContentDependencyRelation.CREATES_ITEM,
                    target_ref=first.ref,
                    phase=ContentDependencyPhase.CONSTRUCTION,
                ),
            ),
        },
    )
    cycle_builder = ContentRegistryBuilder()
    cycle_builder.add_source(_SRD_SOURCE)
    cycle_builder.add_declaration(first_to_second)
    cycle_builder.add_declaration(second_to_first)
    with pytest.raises(ValueError, match="construction dependency cycle"):
        cycle_builder.freeze(pack_dependencies={"fixture.core": frozenset()})


def test_installed_optional_construction_dependencies_still_cannot_cycle() -> None:
    """Optional means an absent target is allowed, not an installed cycle."""
    first = get_content_declaration(_create_test_item)
    second_ref = first.ref.model_copy(
        update={
            "content_id": "item.optional_second",
            "definition_contract_hash": first.ref.definition_contract_hash,
        },
    )
    second = first.model_copy(
        update={
            "ref": second_ref,
            "descriptor": first.descriptor.model_copy(update={"ref": second_ref}),
        },
    )
    first_to_second = first.model_copy(
        update={
            "dependencies": (
                ContentDependency(
                    relation=ContentDependencyRelation.CREATES_ITEM,
                    target_ref=second.ref,
                    required=False,
                    phase=ContentDependencyPhase.CONSTRUCTION,
                ),
            ),
        },
    )
    second_to_first = second.model_copy(
        update={
            "dependencies": (
                ContentDependency(
                    relation=ContentDependencyRelation.CREATES_ITEM,
                    target_ref=first.ref,
                    required=False,
                    phase=ContentDependencyPhase.CONSTRUCTION,
                ),
            ),
        },
    )
    builder = ContentRegistryBuilder()
    builder.add_source(_SRD_SOURCE)
    builder.add_declaration(first_to_second)
    builder.add_declaration(second_to_first)
    with pytest.raises(ValueError, match="construction dependency cycle"):
        builder.freeze(pack_dependencies={"fixture.core": frozenset()})

    absent_builder = ContentRegistryBuilder()
    absent_builder.add_source(_SRD_SOURCE)
    absent_builder.add_declaration(first_to_second)
    absent_registry = absent_builder.freeze(
        pack_dependencies={"fixture.core": frozenset()},
    )
    assert absent_registry.resolve_definition(first.ref) is first_to_second
