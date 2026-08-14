"""Mutable-at-bootstrap builder and immutable runtime content registry."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TypeVar

from pydantic import BaseModel
from dnd.core.content.dependencies import (
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.effects import (
    ConditionEffectCoverage,
    ConditionEffectOperation,
)
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.identities import ContentRef
from dnd.core.content.provenance import ContentSource
from dnd.core.content.recipe_presets import (
    ContentRecipePreset,
    ContentRecipePresetRef,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentDeclaration,
    ContentDeclarationMode,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.spatial_effect_types import SpatialEffectTransitionAction


class NonConstructibleContentError(TypeError):
    """Raised when metadata-only content is used as a factory."""


class NonTypedDefinitionError(NonConstructibleContentError):
    """Raised when a typed-definition operation targets another mode."""


_TypedDefinition = TypeVar("_TypedDefinition", bound=BaseModel)


class ContentRegistryBuilder:
    """Collect and validate declarations before one atomic freeze."""

    def __init__(self) -> None:
        self._declarations: dict[str, ContentDeclaration] = {}
        self._recipe_presets: dict[str, ContentRecipePreset] = {}
        self._sources: dict[str, ContentSource] = {}
        self._frozen = False

    def add_source(self, source: ContentSource) -> None:
        """Add one exact source contract."""
        self._ensure_mutable()
        existing = self._sources.get(source.source_id)
        if existing is not None and existing != source:
            raise ValueError(f"Conflicting content source {source.source_id}")
        self._sources[source.source_id] = source

    def add_declaration(self, declaration: ContentDeclaration) -> None:
        """Add one exact factory declaration."""
        self._ensure_mutable()
        key = declaration.ref.identity_key
        existing = self._declarations.get(key)
        if existing is declaration:
            return
        if existing is not None:
            detail = (
                "with a different definition contract"
                if existing.ref != declaration.ref
                else "from multiple definitions"
            )
            raise ValueError(f"Duplicate content identity {key} {detail}")
        self._declarations[key] = declaration

    def add_recipe_preset(self, preset: ContentRecipePreset) -> None:
        """Add one exact named recipe without duplicating its target factory."""
        self._ensure_mutable()
        key = preset.ref.identity_key
        existing = self._recipe_presets.get(key)
        if existing is preset:
            return
        if existing is not None:
            detail = (
                "with a different preset contract"
                if existing.ref != preset.ref
                else "from multiple declarations"
            )
            raise ValueError(f"Duplicate recipe preset identity {key} {detail}")
        self._recipe_presets[key] = preset

    def freeze(self) -> "FrozenContentRegistry":
        """Validate complete closure and return an immutable registry."""
        self._ensure_mutable()
        _validate_sources(self._declarations, self._sources)
        _validate_recipe_preset_sources(self._recipe_presets, self._sources)
        _validate_dependencies(self._declarations)
        _validate_spatial_effects(self._declarations)
        _validate_condition_effects(self._declarations)
        _validate_related_content(self._declarations)
        _validate_construction_cycles(self._declarations)
        _validate_recipe_presets(
            self._recipe_presets,
            self._declarations,
        )
        self._frozen = True
        return FrozenContentRegistry(
            declarations=self._declarations,
            recipe_presets=self._recipe_presets,
            sources=self._sources,
        )

    def _ensure_mutable(self) -> None:
        if self._frozen:
            raise RuntimeError("ContentRegistryBuilder is frozen")


class FrozenContentRegistry:
    """Validated O(1) registry used by construction and catalog consumers."""

    def __init__(
        self,
        *,
        declarations: Mapping[str, ContentDeclaration],
        recipe_presets: Mapping[str, ContentRecipePreset],
        sources: Mapping[str, ContentSource],
    ) -> None:
        self._declarations = MappingProxyType(dict(declarations))
        self._recipe_presets = MappingProxyType(dict(recipe_presets))
        self._recipe_presets_by_recipe_digest = MappingProxyType({
            preset.recipe.recipe_digest: preset
            for preset in recipe_presets.values()
        })
        self._sources = MappingProxyType(dict(sources))

    @property
    def declarations(self) -> Mapping[str, ContentDeclaration]:
        """Return the immutable identity-keyed declaration mapping."""
        return self._declarations

    @property
    def sources(self) -> Mapping[str, ContentSource]:
        """Return the immutable source mapping."""
        return self._sources

    @property
    def recipe_presets(self) -> Mapping[str, ContentRecipePreset]:
        """Return immutable preset-identity to exact-recipe declarations."""
        return self._recipe_presets

    def resolve_definition(self, ref: ContentRef) -> ContentDeclaration:
        """Resolve an exact definition reference in O(1)."""
        declaration = self._declarations.get(ref.identity_key)
        if declaration is None:
            raise KeyError(f"Unknown content reference {ref.identity_key}")
        if declaration.ref != ref:
            raise ValueError(
                f"Definition contract mismatch for {ref.identity_key}",
            )
        return declaration

    def resolve_factory(self, ref: ContentRef) -> ContentDeclaration:
        """Resolve an exact constructible definition or fail closed."""
        declaration = self.resolve_definition(ref)
        if declaration.mode == ContentDeclarationMode.TYPED_DEFINITION:
            raise NonTypedDefinitionError(
                f"Content {ref.identity_key} is a typed definition",
            )
        if (
            declaration.mode != ContentDeclarationMode.FACTORY
            or declaration.construction is None
        ):
            raise NonConstructibleContentError(
                f"Content {ref.identity_key} is metadata-only",
            )
        return declaration

    def resolve_typed_definition(
        self,
        ref: ContentRef,
        expected_type: type[_TypedDefinition],
    ) -> _TypedDefinition:
        """Resolve one exact typed structural definition or fail closed."""
        declaration = self.resolve_definition(ref)
        payload = declaration.definition_payload
        if (
            declaration.mode != ContentDeclarationMode.TYPED_DEFINITION
            or payload is None
        ):
            raise NonTypedDefinitionError(
                f"Content {ref.identity_key} is not a typed definition",
            )
        if not isinstance(payload, expected_type):
            raise TypeError(
                f"Typed definition {ref.identity_key} is "
                f"{type(payload).__name__}, expected {expected_type.__name__}",
            )
        return payload

    def resolve_recipe_preset(
        self,
        ref: ContentRecipePresetRef,
    ) -> ContentRecipePreset:
        """Resolve one exact preset identity or reject a contract mismatch."""
        preset = self._recipe_presets.get(ref.identity_key)
        if preset is None:
            raise KeyError(f"Unknown recipe preset {ref.identity_key}")
        if preset.ref != ref:
            raise ValueError(
                f"Recipe preset contract mismatch for {ref.identity_key}",
            )
        return preset

    def find_recipe_preset(
        self,
        recipe: ContentRecipe,
    ) -> ContentRecipePreset | None:
        """Return the unique named preset for an exact recipe, if one exists."""
        recipe.verify_integrity()
        preset = self._recipe_presets_by_recipe_digest.get(
            recipe.recipe_digest,
        )
        if preset is not None and preset.recipe != recipe:
            raise ValueError(
                "Recipe digest collision while resolving a content preset",
            )
        return preset

    def materialize(self, recipe: ContentRecipe, context: object) -> object:
        """Validate typed parameters and invoke the one registered factory."""
        recipe.verify_integrity()
        declaration = self.resolve_factory(recipe.ref)
        construction = declaration.construction
        if construction is None:
            raise AssertionError("resolve_factory returned no construction")
        parameters = construction.parameter_model.model_validate(
            recipe.parameters,
        )
        return construction.factory(context, parameters)


def _validate_sources(
    declarations: Mapping[str, ContentDeclaration],
    sources: Mapping[str, ContentSource],
) -> None:
    for key, declaration in declarations.items():
        source_id = declaration.provenance.primary_source_id
        if source_id not in sources:
            raise ValueError(
                f"Content {key} references missing source {source_id}",
            )
        adapted_from = declaration.provenance.adapted_from_source_id
        if adapted_from is not None and adapted_from not in sources:
            raise ValueError(
                f"Content {key} references missing adaptation source "
                f"{adapted_from}",
            )


def _validate_recipe_preset_sources(
    presets: Mapping[str, ContentRecipePreset],
    sources: Mapping[str, ContentSource],
) -> None:
    for key, preset in presets.items():
        source_id = preset.provenance.primary_source_id
        if source_id not in sources:
            raise ValueError(
                f"Recipe preset {key} references missing source {source_id}",
            )
        adapted_from = preset.provenance.adapted_from_source_id
        if adapted_from is not None and adapted_from not in sources:
            raise ValueError(
                f"Recipe preset {key} references missing adaptation source "
                f"{adapted_from}",
            )


def _validate_dependencies(
    declarations: Mapping[str, ContentDeclaration],
) -> None:
    for key, declaration in declarations.items():
        dependency_keys = [
            (dependency.relation, dependency.target_ref.identity_key)
            for dependency in declaration.dependencies
        ]
        if len(dependency_keys) != len(set(dependency_keys)):
            raise ValueError(
                f"Content {key} contains duplicate dependency edges",
            )
        for dependency in declaration.dependencies:
            target = declarations.get(dependency.target_ref.identity_key)
            if target is None:
                if dependency.required:
                    raise ValueError(
                        "Missing content dependency "
                        f"{dependency.target_ref.identity_key} required by {key}",
                    )
                continue
            if target.ref != dependency.target_ref:
                raise ValueError(
                    "Content dependency contract mismatch for "
                    f"{dependency.target_ref.identity_key} required by {key}",
                )
            if (
                dependency.phase == ContentDependencyPhase.CONSTRUCTION
                and (
                    target.mode != ContentDeclarationMode.FACTORY
                    or target.construction is None
                )
            ):
                raise ValueError(
                    "Construction dependency "
                    f"{dependency.target_ref.identity_key} required by {key} "
                    "is metadata-only",
                )
def _validate_spatial_effects(
    declarations: Mapping[str, ContentDeclaration],
) -> None:
    """Validate exact replacement closure for every authored effect transition."""
    for key, declaration in declarations.items():
        definition = declaration.spatial_effect_definition
        transition_dependencies = {
            dependency.target_ref.identity_key: dependency.target_ref
            for dependency in declaration.dependencies
            if dependency.relation
            is ContentDependencyRelation.TRANSFORMS_TO_SPATIAL_EFFECT
        }
        if definition is None:
            if transition_dependencies:
                raise ValueError(
                    f"Content {key} declares a spatial transformation without "
                    "a spatial-effect definition",
                )
            continue
        replacement_refs: dict[str, ContentRef] = {}
        for transition in definition.transitions:
            recipe = transition.replacement_recipe
            if recipe is None:
                continue
            target = declarations.get(recipe.ref.identity_key)
            if target is None:
                raise ValueError(
                    f"Spatial transition from {key} targets missing "
                    f"{recipe.ref.identity_key}",
                )
            if target.ref != recipe.ref:
                raise ValueError(
                    f"Spatial transition from {key} has a target contract "
                    f"mismatch for {recipe.ref.identity_key}",
                )
            target_definition = target.spatial_effect_definition
            if target_definition is None:
                raise ValueError(
                    f"Spatial transition from {key} targets a non-effect",
                )
            same_layer = target_definition.layer is definition.layer
            if (
                transition.action
                is SpatialEffectTransitionAction.REPLACE_AFFECTED
                and not same_layer
            ):
                raise ValueError(
                    f"Replacement transition from {key} changes layers; "
                    "secondary-layer creation requires a separate operation",
                )
            if (
                transition.action
                is (
                    SpatialEffectTransitionAction
                    .REMOVE_AFFECTED_AND_CREATE_SECONDARY
                )
                and same_layer
            ):
                raise ValueError(
                    f"Secondary-layer transition from {key} stays on "
                    f"{definition.layer.value}",
                )
            replacement_refs[recipe.ref.identity_key] = recipe.ref
        if replacement_refs != transition_dependencies:
            raise ValueError(
                f"Content {key} transformation dependencies do not exactly "
                "match its authored replacement transitions",
            )


def _validate_condition_effects(
    declarations: Mapping[str, ContentDeclaration],
) -> None:
    """Validate exact condition-effect closure and dependency equality."""
    for key, declaration in declarations.items():
        profile = declaration.condition_effect_profile
        coverage = declaration.condition_effect_coverage
        apply_dependencies = {
            dependency.target_ref.identity_key: dependency.target_ref
            for dependency in declaration.dependencies
            if dependency.relation
            is ContentDependencyRelation.APPLIES_CONDITION
        }
        if coverage is ConditionEffectCoverage.PROFILED:
            if profile is None:
                raise ValueError(
                    f"Content {key} claims profiled condition effects "
                    "without a profile",
                )
        elif profile is not None:
            raise ValueError(
                f"Content {key} owns a condition-effect profile but coverage "
                f"is {coverage.value}",
            )
        if coverage is ConditionEffectCoverage.LIFECYCLE_ONLY:
            if (
                declaration.runtime_behavior_kind
                is not RuntimeBehaviorKind.CONDITION
                or declaration.condition_lifecycle is None
            ):
                raise ValueError(
                    f"Content {key} claims lifecycle-only condition behavior "
                    "without condition lifecycle ownership",
                )
        elif (
            declaration.runtime_behavior_kind is RuntimeBehaviorKind.CONDITION
            and coverage
            not in {
                ConditionEffectCoverage.PROFILED,
                ConditionEffectCoverage.INTERNAL_ONLY,
            }
        ):
            raise ValueError(
                f"Content {key} condition behavior must be profiled, "
                "lifecycle-only, or internal-only",
            )
        if coverage is ConditionEffectCoverage.INDIRECT:
            indirect_relations = {
                ContentDependencyRelation.CREATES_OBJECT,
                ContentDependencyRelation.CREATES_SPATIAL_EFFECT,
                ContentDependencyRelation.TRANSFORMS_TO_SPATIAL_EFFECT,
                ContentDependencyRelation.GRANTS_ACTION,
                ContentDependencyRelation.GRANTS_FEATURE,
                ContentDependencyRelation.CREATES_ITEM,
                ContentDependencyRelation.SUMMONS_CREATURE,
            }
            if not any(
                dependency.relation in indirect_relations
                for dependency in declaration.dependencies
            ):
                raise ValueError(
                    f"Content {key} claims indirect condition behavior "
                    "without an exact intermediary dependency",
                )
        if profile is None:
            if apply_dependencies:
                raise ValueError(
                    f"Content {key} declares APPLIES_CONDITION without an "
                    "authored condition effect profile",
                )
            continue

        apply_refs = {
            effect.condition_ref.identity_key: effect.condition_ref
            for effect in profile.effects
            if (
                effect.operation is ConditionEffectOperation.APPLY
                and effect.condition_ref is not None
            )
        }
        if any(
            effect.operation is ConditionEffectOperation.APPLY
            and effect.condition_ref is None
            for effect in profile.effects
        ):
            raise ValueError(
                f"Content {key} has a condition application without an "
                "exact condition ref",
            )
        if apply_refs != apply_dependencies:
            raise ValueError(
                f"Content {key} APPLIES_CONDITION dependencies do not "
                "exactly match its authored application effects",
            )

        for effect in profile.effects:
            if effect.source_ref != declaration.ref:
                raise ValueError(
                    f"Content {key} condition effect {effect.effect_id} "
                    "claims a different source definition",
                )
            exact_refs = (
                (effect.condition_ref,)
                if effect.condition_ref is not None
                else ()
            )
            if effect.selector is not None:
                matched_refs = tuple(sorted(
                    (
                        candidate.ref
                        for candidate in declarations.values()
                        if candidate.condition_lifecycle is not None
                        and set(effect.selector.required_tags).issubset(
                            set(candidate.condition_lifecycle.tags),
                        )
                        and set(
                            effect.selector.required_removal_triggers,
                        ).issubset(
                            set(
                                candidate.condition_lifecycle.removal_triggers,
                            ),
                        )
                    ),
                    key=lambda ref: ref.identity_key,
                ))
                if (
                    effect.selector.resolved_condition_refs
                    and effect.selector.resolved_condition_refs != matched_refs
                ):
                    raise ValueError(
                        f"Content {key} condition selector for "
                        f"{effect.effect_id} has stale resolved refs",
                    )
                exact_refs = matched_refs

            for condition_ref in exact_refs:
                target = declarations.get(condition_ref.identity_key)
                if target is None or target.ref != condition_ref:
                    raise ValueError(
                        f"Content {key} condition effect {effect.effect_id} "
                        f"references missing {condition_ref.identity_key}",
                    )
                if target.runtime_behavior_kind is not RuntimeBehaviorKind.CONDITION:
                    raise ValueError(
                        f"Content {key} condition effect {effect.effect_id} "
                        f"targets non-condition {condition_ref.identity_key}",
                    )
def _validate_related_content(
    declarations: Mapping[str, ContentDeclaration],
) -> None:
    """Validate every descriptor relationship against exact installed refs."""
    for key, declaration in declarations.items():
        for related_ref in declaration.descriptor.related_content_refs:
            target = declarations.get(related_ref.identity_key)
            if target is None:
                raise ValueError(
                    f"Content {key} references missing related definition "
                    f"{related_ref.identity_key}",
                )
            if target.ref != related_ref:
                raise ValueError(
                    "Related content definition contract mismatch for "
                    f"{related_ref.identity_key} referenced by {key}",
                )
def _validate_construction_cycles(
    declarations: Mapping[str, ContentDeclaration],
) -> None:
    graph: dict[str, tuple[str, ...]] = {}
    for key, declaration in declarations.items():
        graph[key] = tuple(
            dependency.target_ref.identity_key
            for dependency in declaration.dependencies
            if dependency.phase == ContentDependencyPhase.CONSTRUCTION
            and dependency.target_ref.identity_key in declarations
        )

    visited: set[str] = set()
    active: list[str] = []
    active_set: set[str] = set()

    def visit(key: str) -> None:
        if key in visited:
            return
        if key in active_set:
            start = active.index(key)
            cycle = " -> ".join((*active[start:], key))
            raise ValueError(f"Content construction dependency cycle: {cycle}")
        active.append(key)
        active_set.add(key)
        for target in sorted(graph[key]):
            visit(target)
        active.pop()
        active_set.remove(key)
        visited.add(key)

    for key in sorted(graph):
        visit(key)


_VISIBILITY_RANK = {
    ContentVisibility.INTERNAL: 0,
    ContentVisibility.DEVELOPER: 1,
    ContentVisibility.OBSERVED: 2,
    ContentVisibility.PUBLIC: 3,
}


def _validate_recipe_presets(
    presets: Mapping[str, ContentRecipePreset],
    declarations: Mapping[str, ContentDeclaration],
) -> None:
    """Validate target closure, parameters, visibility, and one-way ownership."""
    recipe_owners: dict[str, str] = {}
    for key, preset in presets.items():
        target = declarations.get(preset.recipe.ref.identity_key)
        if target is None:
            raise ValueError(
                f"Recipe preset {key} references missing definition "
                f"{preset.recipe.ref.identity_key}",
            )
        if target.ref != preset.recipe.ref:
            raise ValueError(
                "Recipe preset target contract mismatch for "
                f"{preset.recipe.ref.identity_key} referenced by {key}",
            )
        if (
            target.mode != ContentDeclarationMode.FACTORY
            or target.construction is None
        ):
            raise ValueError(
                f"Recipe preset {key} targets non-constructible content",
            )
        target.construction.parameter_model.model_validate(
            preset.recipe.parameters,
        )
        if (
            _VISIBILITY_RANK[preset.descriptor.visibility]
            > _VISIBILITY_RANK[target.descriptor.visibility]
        ):
            raise ValueError(
                f"Recipe preset {key} is more visible than its target",
            )
        for related_ref in preset.descriptor.related_content_refs:
            related = declarations.get(related_ref.identity_key)
            if related is None or related.ref != related_ref:
                raise ValueError(
                    f"Recipe preset {key} references missing related content "
                    f"{related_ref.identity_key}",
                )
        existing_owner = recipe_owners.get(preset.recipe.recipe_digest)
        if existing_owner is not None:
            raise ValueError(
                f"Recipe presets {existing_owner} and {key} are aliases for "
                "the same exact recipe",
            )
        recipe_owners[preset.recipe.recipe_digest] = key
