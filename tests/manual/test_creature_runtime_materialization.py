"""Canonical creature factories bind exact deployment-local runtime identity."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from dnd.content_system.creature_bindings import (
    CREATURE_RUNTIME_BINDINGS,
    CreatureRuntimeBindingRegistry,
)
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.system import LoadedContentSystem
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentVisibility,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.materialization import (
    CreatureBuildContext,
    CreatureDeploymentRole,
    CreaturePossessionMode,
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
    ContentDeclaration,
    creature_factory,
    get_content_declaration,
)
from dnd.core.content.registry import ContentRegistryBuilder
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime


class _CreatureParameters(BaseModel):
    """Typed structural inputs for the fixture creature."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    marker: str


_SOURCE = ContentSource(
    source_id="fixture.creature_source",
    source_family=ContentSourceFamily.FIXTURE_INTERNAL,
    title="Creature runtime fixture",
    source_version="1",
    rules_baseline=RulesBaseline.ENGINE_NEUTRAL,
    license_id="fixture-only",
    canonical_uri="fixture://creature-runtime",
    document_digest="a" * 64,
    attribution_text="Internal deterministic fixture.",
)
_PROVENANCE = ContentProvenance(
    primary_source_id=_SOURCE.source_id,
    source_anchor="tests/manual/test_creature_runtime_materialization.py",
    relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
    fidelity=ContentFidelity.COMPLETE,
    review_status=ContentReviewStatus.REVIEWED,
)
_DESCRIPTOR = ContentDescriptorSpec(
    display_name="Fixture Guard",
    visibility=ContentVisibility.INTERNAL,
    tags=("creature", "fixture"),
)


def _create_entity(
    context: CreatureBuildContext,
    *,
    content_ref=None,
    runtime_entity_uuid=None,
) -> Entity:
    entity_uuid = runtime_entity_uuid or context.runtime_entity_uuid
    return Entity.create(
        source_entity_uuid=entity_uuid,
        name=context.display_name,
        config=EntityConfig(
            position=context.position,
            faction=context.faction,
        ),
        content_ref=context.requested_ref if content_ref is None else content_ref,
    )


@creature_factory(
    pack_id="fixture.creatures",
    content_id="creature.guard",
    version=1,
    parameters=_CreatureParameters,
    descriptor=_DESCRIPTOR,
    provenance=_PROVENANCE,
)
def _build_guard(
    raw_context: object,
    parameters: _CreatureParameters,
) -> Entity:
    assert isinstance(raw_context, CreatureBuildContext)
    assert parameters.marker == "canonical"
    return _create_entity(raw_context)


@creature_factory(
    pack_id="fixture.creatures",
    content_id="creature.alternate",
    version=1,
    parameters=_CreatureParameters,
    descriptor=_DESCRIPTOR.model_copy(update={"display_name": "Alternate"}),
    provenance=_PROVENANCE,
)
def _build_alternate(
    raw_context: object,
    parameters: _CreatureParameters,
) -> Entity:
    assert isinstance(raw_context, CreatureBuildContext)
    assert parameters.marker == "canonical"
    return _create_entity(raw_context)


_ALTERNATE_REF = get_content_declaration(_build_alternate).ref


@creature_factory(
    pack_id="fixture.creatures",
    content_id="creature.wrong_return",
    version=1,
    parameters=_CreatureParameters,
    descriptor=_DESCRIPTOR.model_copy(update={"display_name": "Wrong return"}),
    provenance=_PROVENANCE,
)
def _build_wrong_return(
    raw_context: object,
    parameters: _CreatureParameters,
) -> tuple[object, str]:
    return raw_context, parameters.marker


@creature_factory(
    pack_id="fixture.creatures",
    content_id="creature.wrong_ref",
    version=1,
    parameters=_CreatureParameters,
    descriptor=_DESCRIPTOR.model_copy(update={"display_name": "Wrong ref"}),
    provenance=_PROVENANCE,
)
def _build_wrong_ref(
    raw_context: object,
    parameters: _CreatureParameters,
) -> Entity:
    assert isinstance(raw_context, CreatureBuildContext)
    assert parameters.marker == "canonical"
    return _create_entity(raw_context, content_ref=_ALTERNATE_REF)


@creature_factory(
    pack_id="fixture.creatures",
    content_id="creature.wrong_runtime_uuid",
    version=1,
    parameters=_CreatureParameters,
    descriptor=_DESCRIPTOR.model_copy(update={"display_name": "Wrong UUID"}),
    provenance=_PROVENANCE,
)
def _build_wrong_runtime_uuid(
    raw_context: object,
    parameters: _CreatureParameters,
) -> Entity:
    assert isinstance(raw_context, CreatureBuildContext)
    assert parameters.marker == "canonical"
    return _create_entity(raw_context, runtime_entity_uuid=uuid4())


_GUARD_DECLARATION = get_content_declaration(_build_guard)
_GUARD_RECIPE = ContentRecipe.create(
    ref=_GUARD_DECLARATION.ref,
    parameters={"marker": "canonical"},
)
_ROLE = CreatureDeploymentRole(role_id="encounter.alpha.guard_one")


def _runtime(
    declarations: Iterable[ContentDeclaration],
) -> ContentSystemRuntime:
    builder = ContentRegistryBuilder()
    builder.add_source(_SOURCE)
    for declaration in declarations:
        builder.add_declaration(declaration)
    registry = builder.freeze()
    runtime = ContentSystemRuntime()
    runtime.install(
        LoadedContentSystem(
            registry=registry,
            built_in_artifact_digest="b" * 64,
            content_set_digest="c" * 64,
        ),
    )
    return runtime


def _materialize(
    recipe: ContentRecipe,
    *,
    runtime: ContentSystemRuntime,
    bindings: CreatureRuntimeBindingRegistry,
    possession_mode: CreaturePossessionMode = (
        CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
    ),
) -> Entity:
    return materialize_creature(
        recipe,
        runtime_entity_uuid=uuid4(),
        display_name="Runtime Guard",
        faction="allies",
        position=(2, 3),
        deployment_role=_ROLE,
        possession_mode=possession_mode,
        binding_registry=bindings,
        runtime=runtime,
    )


@pytest.fixture(autouse=True)
def _reset_runtime_state():
    reset_engine_runtime(grid_size=(6, 6))
    yield
    reset_engine_runtime()


@pytest.mark.parametrize(
    "possession_mode",
    tuple(CreaturePossessionMode),
)
def test_exact_factory_materialization_binds_each_possession_mode(
    possession_mode: CreaturePossessionMode,
) -> None:
    """Both loadout paths retain one exact recipe and deployment role."""
    runtime = _runtime((_GUARD_DECLARATION,))
    bindings = CreatureRuntimeBindingRegistry()

    entity = _materialize(
        _GUARD_RECIPE,
        runtime=runtime,
        bindings=bindings,
        possession_mode=possession_mode,
    )
    binding = bindings.require(entity.uuid)

    assert entity.uuid == entity.source_entity_uuid
    assert entity.name == "Runtime Guard"
    assert entity.faction == "allies"
    assert entity.position == (2, 3)
    assert entity.content_ref == _GUARD_RECIPE.ref
    assert "content_ref" not in entity.model_dump()
    assert binding.runtime_entity_uuid == entity.uuid
    assert binding.recipe == _GUARD_RECIPE
    assert binding.content_set_digest == runtime.require().content_set_digest
    assert binding.deployment_role == _ROLE
    assert binding.possession_mode == possession_mode
    assert runtime.materialization_count == 1

    with pytest.raises(ValidationError, match="frozen"):
        entity.content_ref = _ALTERNATE_REF


def test_creature_context_rejects_invalid_role_mode_and_definition_kind() -> None:
    """Deployment facts are typed and cannot be inferred from loose strings."""
    with pytest.raises(ValidationError, match="role_id"):
        CreatureDeploymentRole(role_id="Guard One")

    payload = {
        "runtime_entity_uuid": uuid4(),
        "requested_ref": _GUARD_RECIPE.ref,
        "display_name": "Guard",
        "faction": None,
        "position": (0, 0),
        "deployment_role": _ROLE,
        "possession_mode": "invent_default_gear",
    }
    with pytest.raises(ValidationError, match="possession_mode"):
        CreatureBuildContext.model_validate(payload)

    item_ref = _GUARD_RECIPE.ref.model_copy(
        update={"definition_kind": ContentDefinitionKind.ITEM},
    )
    with pytest.raises(ValidationError, match="creature content reference"):
        CreatureBuildContext.model_validate(
            {
                **payload,
                "requested_ref": item_ref,
                "possession_mode": (
                    CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
                ),
            },
        )


def test_wrong_definition_kind_is_rejected_before_factory_dispatch() -> None:
    """The creature adapter never dispatches an item-shaped recipe."""
    runtime = _runtime((_GUARD_DECLARATION,))
    bindings = CreatureRuntimeBindingRegistry()
    wrong_kind_recipe = ContentRecipe.create(
        ref=_GUARD_RECIPE.ref.model_copy(
            update={"definition_kind": ContentDefinitionKind.ITEM},
        ),
        parameters=_GUARD_RECIPE.parameters,
    )

    with pytest.raises(TypeError, match="requires a creature recipe"):
        _materialize(
            wrong_kind_recipe,
            runtime=runtime,
            bindings=bindings,
        )

    assert runtime.materialization_count == 0
    assert bindings.bindings == {}


def test_wrong_factory_return_type_is_rejected_without_a_binding() -> None:
    """A registered creature factory must return an Entity."""
    declaration = get_content_declaration(_build_wrong_return)
    runtime = _runtime((declaration,))
    bindings = CreatureRuntimeBindingRegistry()
    recipe = ContentRecipe.create(
        ref=declaration.ref,
        parameters={"marker": "canonical"},
    )

    with pytest.raises(TypeError, match="returned builtins.tuple"):
        _materialize(recipe, runtime=runtime, bindings=bindings)

    assert runtime.materialization_count == 1
    assert bindings.bindings == {}


def test_wrong_factory_content_ref_is_rejected_without_a_binding() -> None:
    """A creature cannot substitute a class/name-compatible authored identity."""
    declaration = get_content_declaration(_build_wrong_ref)
    runtime = _runtime((declaration,))
    bindings = CreatureRuntimeBindingRegistry()
    recipe = ContentRecipe.create(
        ref=declaration.ref,
        parameters={"marker": "canonical"},
    )

    with pytest.raises(ValueError, match="exact content reference"):
        _materialize(recipe, runtime=runtime, bindings=bindings)

    assert bindings.bindings == {}


def test_wrong_factory_runtime_uuid_is_rejected_without_a_binding() -> None:
    """Factory output must retain the deployment-assigned entity/source UUID."""
    declaration = get_content_declaration(_build_wrong_runtime_uuid)
    runtime = _runtime((declaration,))
    bindings = CreatureRuntimeBindingRegistry()
    recipe = ContentRecipe.create(
        ref=declaration.ref,
        parameters={"marker": "canonical"},
    )

    with pytest.raises(ValueError, match="runtime entity/source UUID"):
        _materialize(recipe, runtime=runtime, bindings=bindings)

    assert bindings.bindings == {}


def test_binding_registry_never_infers_identity_from_entity_class_or_name() -> None:
    """An ordinary Entity with a matching name has no canonical recipe binding."""
    bindings = CreatureRuntimeBindingRegistry()
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Runtime Guard",
        config=EntityConfig(position=(1, 1), faction="allies"),
    )

    assert entity.content_ref is None
    with pytest.raises(KeyError, match="not bound"):
        bindings.require(entity.uuid)


def test_engine_reset_retires_global_creature_bindings() -> None:
    """A new game generation cannot observe the prior generation's creature."""
    runtime = _runtime((_GUARD_DECLARATION,))
    entity = _materialize(
        _GUARD_RECIPE,
        runtime=runtime,
        bindings=CREATURE_RUNTIME_BINDINGS,
    )
    assert CREATURE_RUNTIME_BINDINGS.require(entity.uuid).recipe == _GUARD_RECIPE

    reset_engine_runtime()

    with pytest.raises(KeyError, match="not bound"):
        CREATURE_RUNTIME_BINDINGS.require(entity.uuid)
