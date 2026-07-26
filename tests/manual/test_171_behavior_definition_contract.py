"""One canonical identity boundary for factories and private behavior."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest
from pydantic import BaseModel, ConfigDict

import dnd.conditions as condition_module
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentVisibility,
)
from dnd.core.content.identities import ContentDefinitionKind
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
    ContentDeclarationMode,
    behavior_identity,
    compute_definition_contract_hash,
    content_factory,
    get_content_declaration,
    item_factory,
    scan_module_content_declarations,
)
from dnd.core.content.registry import (
    ContentRegistryBuilder,
    NonConstructibleContentError,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from server.content_catalog import build_public_content_catalog


class _ItemParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    charges: int


_SOURCE = ContentSource(
    source_id="fixture.behaviors.source",
    source_family=ContentSourceFamily.FIXTURE_INTERNAL,
    title="Behavior identity fixture",
    source_version="1",
    rules_baseline=RulesBaseline.ENGINE_NEUTRAL,
    license_id="INTERNAL-TEST",
    canonical_uri="https://example.invalid/behavior-identity",
    document_digest="e" * 64,
    attribution_text="Internal deterministic behavior fixture.",
)
_PROVENANCE = ContentProvenance(
    primary_source_id=_SOURCE.source_id,
    source_anchor="Behavior identity fixture",
    relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
    fidelity=ContentFidelity.COMPLETE,
    review_status=ContentReviewStatus.REVIEWED,
)


@behavior_identity(
    definition_kind=ContentDefinitionKind.ACTION,
    runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
    pack_id="fixture.behaviors",
    content_id="action.clockwork_flask.drink",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Drink Clockwork Flask",
        description="A public, metadata-only fixture action.",
        tags=("action", "fixture"),
        visibility=ContentVisibility.PUBLIC,
    ),
    provenance=_PROVENANCE,
)
class _DrinkClockworkFlask:
    pass


@behavior_identity(
    definition_kind=ContentDefinitionKind.CONDITION,
    runtime_behavior_kind=RuntimeBehaviorKind.CONDITION,
    pack_id="fixture.behaviors",
    content_id="condition.clockwork_flask.consumed",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Clockwork Flask Consumed",
        description="An internal marker fixture.",
        tags=("condition", "fixture"),
        visibility=ContentVisibility.INTERNAL,
    ),
    provenance=_PROVENANCE,
)
class _ClockworkFlaskConsumed:
    pass


@item_factory(
    pack_id="fixture.items",
    content_id="item.clockwork_flask",
    version=1,
    parameters=_ItemParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Clockwork Flask",
        description="A constructible item fixture.",
        tags=("fixture", "item"),
        visibility=ContentVisibility.PUBLIC,
    ),
    provenance=_PROVENANCE,
    item_definition=ItemDefinition(
        persistence_policy=ItemPersistencePolicy.POSSESSION,
    ),
)
def _build_clockwork_flask(
    context: object,
    parameters: _ItemParameters,
) -> tuple[object, int]:
    return context, parameters.charges


def _registry(*definitions: object):
    builder = ContentRegistryBuilder()
    builder.add_source(_SOURCE)
    for definition in definitions:
        builder.add_declaration(get_content_declaration(definition))
    return builder.freeze(
        pack_dependencies={
            "fixture.behaviors": frozenset({"fixture.items"}),
            "fixture.items": frozenset({"fixture.behaviors"}),
        },
    )


def test_behavior_identity_resolves_but_is_not_materializable() -> None:
    declaration = get_content_declaration(_DrinkClockworkFlask)
    registry = _registry(_DrinkClockworkFlask)

    assert declaration.mode == ContentDeclarationMode.BEHAVIOR_IDENTITY
    assert declaration.construction is None
    assert registry.resolve_definition(declaration.ref) is declaration
    with pytest.raises(NonConstructibleContentError, match="metadata-only"):
        registry.resolve_factory(declaration.ref)
    recipe = ContentRecipe.create(ref=declaration.ref, parameters={})
    with pytest.raises(NonConstructibleContentError, match="metadata-only"):
        registry.materialize(recipe, object())


def test_retired_closed_condition_factory_cannot_reappear() -> None:
    """Concrete conditions are authored behaviors, not members of a second switch."""

    assert not hasattr(condition_module, "ConditionType")
    assert not hasattr(condition_module, "CONDITION_MAP")
    assert not hasattr(condition_module, "create_condition")


def test_behavior_contract_hash_authenticates_mode_kind_and_runtime_kind() -> None:
    declaration = get_content_declaration(_DrinkClockworkFlask)
    base = declaration.ref.definition_contract_hash

    assert base == compute_definition_contract_hash(
        mode=ContentDeclarationMode.BEHAVIOR_IDENTITY,
        definition_kind=ContentDefinitionKind.ACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
    )
    assert base != compute_definition_contract_hash(
        mode=ContentDeclarationMode.BEHAVIOR_IDENTITY,
        definition_kind=ContentDefinitionKind.REACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.REACTION,
    )
    assert base != compute_definition_contract_hash(
        mode=ContentDeclarationMode.BEHAVIOR_IDENTITY,
        definition_kind=ContentDefinitionKind.ACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.SPELL,
    )


def test_factory_and_behavior_cannot_share_one_identity() -> None:
    behavior = get_content_declaration(_DrinkClockworkFlask)

    @content_factory(
        definition_kind=ContentDefinitionKind.ACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
        pack_id=behavior.ref.pack_id,
        content_id=behavior.ref.content_id,
        version=behavior.ref.content_version,
        parameters=_ItemParameters,
        descriptor=ContentDescriptorSpec(
            display_name="Constructible collision",
            visibility=ContentVisibility.INTERNAL,
        ),
        provenance=_PROVENANCE,
    )
    def conflicting_factory(
        context: object,
        parameters: _ItemParameters,
    ) -> tuple[object, int]:
        return context, parameters.charges

    builder = ContentRegistryBuilder()
    builder.add_source(_SOURCE)
    builder.add_declaration(behavior)
    with pytest.raises(ValueError, match="Duplicate content identity"):
        builder.add_declaration(get_content_declaration(conflicting_factory))


def test_construction_dependency_cannot_target_metadata_only_definition() -> None:
    behavior = get_content_declaration(_DrinkClockworkFlask)
    item = get_content_declaration(_build_clockwork_flask).model_copy(
        update={
            "dependencies": (
                ContentDependency(
                    relation=ContentDependencyRelation.GRANTS_ACTION,
                    target_ref=behavior.ref,
                    phase=ContentDependencyPhase.CONSTRUCTION,
                ),
            ),
        },
    )
    builder = ContentRegistryBuilder()
    builder.add_source(_SOURCE)
    builder.add_declaration(item)
    builder.add_declaration(behavior)

    with pytest.raises(ValueError, match="metadata-only"):
        builder.freeze(
            pack_dependencies={
                "fixture.items": frozenset({"fixture.behaviors"}),
                "fixture.behaviors": frozenset(),
            },
        )


def test_cross_pack_behavior_dependency_requires_manifest_edge() -> None:
    item = get_content_declaration(_build_clockwork_flask)
    behavior = get_content_declaration(_DrinkClockworkFlask).model_copy(
        update={
            "dependencies": (
                ContentDependency(
                    relation=ContentDependencyRelation.CREATES_ITEM,
                    target_ref=item.ref,
                ),
            ),
        },
    )
    builder = ContentRegistryBuilder()
    builder.add_source(_SOURCE)
    builder.add_declaration(item)
    builder.add_declaration(behavior)

    with pytest.raises(ValueError, match="without a declared pack dependency"):
        builder.freeze(
            pack_dependencies={
                "fixture.items": frozenset(),
                "fixture.behaviors": frozenset(),
            },
        )


def test_scanner_discovers_local_behavior_declarations_only() -> None:
    fixture_module = ModuleType("fixture_imported_behavior")
    setattr(fixture_module, "imported_behavior", _DrinkClockworkFlask)
    sys.modules[fixture_module.__name__] = fixture_module
    try:
        assert scan_module_content_declarations(fixture_module) == ()
    finally:
        del sys.modules[fixture_module.__name__]

    local = scan_module_content_declarations(sys.modules[__name__])
    assert {row.ref.identity_key for row in local} == {
        get_content_declaration(_DrinkClockworkFlask).ref.identity_key,
        get_content_declaration(_ClockworkFlaskConsumed).ref.identity_key,
        get_content_declaration(_build_clockwork_flask).ref.identity_key,
    }


def test_public_behavior_catalog_is_code_free_and_has_no_parameter_schema() -> None:
    registry = _registry(
        _DrinkClockworkFlask,
        _ClockworkFlaskConsumed,
        _build_clockwork_flask,
    )
    loaded = LoadedContentSystem(
        registry=registry,
        packs=(),
        built_in_artifact_digest="a" * 64,
        content_set_digest="b" * 64,
    )
    catalog = build_public_content_catalog(loaded)
    entries = {entry.ref.identity_key: entry for entry in catalog.entries}
    behavior = get_content_declaration(_DrinkClockworkFlask)
    internal = get_content_declaration(_ClockworkFlaskConsumed)

    entry = entries[behavior.ref.identity_key]
    assert entry.definition_mode == ContentDeclarationMode.BEHAVIOR_IDENTITY
    assert entry.runtime_behavior_kind == RuntimeBehaviorKind.ACTION
    assert entry.parameter_schema is None
    assert entry.item_definition is None
    assert internal.ref.identity_key not in entries
    encoded = catalog.model_dump_json()
    assert '"factory":' not in encoded
    assert "dnd." not in encoded


def test_factory_catalog_keeps_typed_schema_and_materialization() -> None:
    declaration = get_content_declaration(_build_clockwork_flask)
    registry = _registry(_build_clockwork_flask)
    recipe = ContentRecipe.create(
        ref=declaration.ref,
        parameters={"charges": 3},
    )

    assert registry.materialize(recipe, "context") == ("context", 3)
    assert registry.resolve_factory(declaration.ref) is declaration
