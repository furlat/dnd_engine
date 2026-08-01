"""Safe, cacheable transport contracts for the installed content system."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from dnd.content_system.builtin import (
    BUILT_IN_PACK_DEPENDENCIES,
    BUILT_IN_PACK_VERSIONS,
)
from dnd.content_system.pack_loader import (
    ENGINE_CONTENT_API_VERSION,
    LoadedContentSystem,
)
from dnd.core.content.dependencies import ContentDependency
from dnd.core.content.descriptors import (
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
    compute_safe_content_presentation_hash,
)
from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
    validate_namespaced_id,
    validate_sha256,
)
from dnd.core.content.effects import (
    AuthoredConditionEffectProfile,
    AuthoredConditionLifecycle,
    ConditionEffectCoverage,
)
from dnd.core.content.item_definitions import ItemDefinition
from dnd.core.content.spatial_effect_definitions import SpatialEffectDefinition
from dnd.core.content.provenance import ContentProvenance, ContentSource
from dnd.core.content.recipe_presets import ContentRecipePresetRef
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclarationMode
from dnd.core.content.runtime import RuntimeBehaviorKind
from server.world_contracts import SafeContentPresentationRef


CONTENT_MANIFEST_SCHEMA_VERSION = 2
CONTENT_CATALOG_SCHEMA_VERSION = 7


def safe_content_presentation_ref(
    presentation: ContentPresentation,
) -> SafeContentPresentationRef:
    """Return the transport ref for one mechanics-free presentation payload."""
    return SafeContentPresentationRef(
        presentation_contract_hash=compute_safe_content_presentation_hash(
            presentation,
        ),
    )


class ContentPackOrigin(str, Enum):
    """Whether a pack ships with the engine or was discovered at startup."""

    BUILT_IN = "built_in"
    EXTERNAL = "external"


class ContentPackManifestEntry(BaseModel):
    """Cold pack identity safe for clients and deployment diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_id: str
    pack_version: str = Field(min_length=1)
    origin: ContentPackOrigin
    dependencies: tuple[str, ...] = ()
    manifest_contract_digest: str | None = None
    pack_digest: str | None = None

    @field_validator("pack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "pack_id")

    @field_validator("manifest_contract_digest", "pack_digest")
    @classmethod
    def _validate_optional_digest(
        cls,
        value: str | None,
        info,
    ) -> str | None:
        if value is None:
            return None
        return validate_sha256(value, info.field_name)


class ContentManifestResponse(BaseModel):
    """Exact installed pack/source identity for cache and replay selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2] = CONTENT_MANIFEST_SCHEMA_VERSION
    engine_content_api: int
    content_set_digest: str
    built_in_artifact_digest: str
    packs: tuple[ContentPackManifestEntry, ...]
    sources: tuple[ContentSource, ...]

    @field_validator("content_set_digest", "built_in_artifact_digest")
    @classmethod
    def _validate_digest(cls, value: str, info) -> str:
        return validate_sha256(value, info.field_name)


class ContentCatalogEntry(BaseModel):
    """One safe authored descriptor; never a runtime factory or instance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: ContentRef
    display_name: str
    description: str
    tags: tuple[str, ...]
    visibility: ContentVisibility
    presentation: ContentPresentation
    ordering: ContentOrdering
    related_content_refs: tuple[ContentRef, ...]
    provenance: ContentProvenance
    definition_mode: ContentDeclarationMode
    runtime_behavior_kind: RuntimeBehaviorKind | None = None
    item_definition: ItemDefinition | None = None
    spatial_effect_definition: SpatialEffectDefinition | None = None
    dependencies: tuple[ContentDependency, ...] = ()
    condition_effect_coverage: ConditionEffectCoverage
    condition_effect_profile: AuthoredConditionEffectProfile | None = None
    condition_lifecycle: AuthoredConditionLifecycle | None = None
    parameter_schema: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def _validate_definition_boundary(self) -> Self:
        item_owned_kind = self.ref.definition_kind in {
            ContentDefinitionKind.ITEM,
            ContentDefinitionKind.ENVIRONMENT_OBJECT,
        }
        spatial_effect_owned_kind = (
            self.ref.definition_kind is ContentDefinitionKind.SPATIAL_EFFECT
        )
        if self.definition_mode == ContentDeclarationMode.FACTORY:
            if self.parameter_schema is None:
                raise ValueError(
                    "factory catalog entry requires parameter_schema",
                )
            if item_owned_kind and self.item_definition is None:
                raise ValueError(
                    "item factory catalog entry requires item_definition",
                )
            if not item_owned_kind and self.item_definition is not None:
                raise ValueError(
                    "non-item factory catalog entry cannot own item_definition",
                )
            if (
                spatial_effect_owned_kind
                and self.spatial_effect_definition is None
            ):
                raise ValueError(
                    "spatial-effect factory catalog entry requires "
                    "spatial_effect_definition",
                )
            if (
                not spatial_effect_owned_kind
                and self.spatial_effect_definition is not None
            ):
                raise ValueError(
                    "non-spatial factory catalog entry cannot own "
                    "spatial_effect_definition",
                )
        elif self.definition_mode == ContentDeclarationMode.BEHAVIOR_IDENTITY:
            if self.runtime_behavior_kind is None:
                raise ValueError(
                    "behavior catalog entry requires runtime_behavior_kind",
                )
            if self.parameter_schema is not None:
                raise ValueError(
                    "behavior catalog entry cannot expose parameter_schema",
                )
            if self.item_definition is not None:
                raise ValueError(
                    "behavior catalog entry cannot own item_definition",
                )
            if self.spatial_effect_definition is not None:
                raise ValueError(
                    "behavior catalog entry cannot own "
                    "spatial_effect_definition",
                )
        else:
            if self.runtime_behavior_kind is not None:
                raise ValueError(
                    "typed-definition catalog entry cannot own runtime behavior",
                )
            if self.parameter_schema is not None:
                raise ValueError(
                    "typed-definition catalog entry cannot expose factory "
                    "parameters",
                )
            if self.item_definition is not None:
                raise ValueError(
                    "typed-definition catalog entry cannot own item_definition",
                )
            if self.spatial_effect_definition is not None:
                raise ValueError(
                    "typed-definition catalog entry cannot own "
                    "spatial_effect_definition",
                )
        return self


class ContentRecipePresetCatalogEntry(BaseModel):
    """One named exact recipe safe for selectors and durable authoring."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: ContentRecipePresetRef
    recipe: ContentRecipe
    display_name: str
    description: str
    tags: tuple[str, ...]
    visibility: ContentVisibility
    presentation: ContentPresentation
    ordering: ContentOrdering
    related_content_refs: tuple[ContentRef, ...]
    provenance: ContentProvenance


class SafeContentPresentationCatalogEntry(BaseModel):
    """One mechanics-free presentation payload addressed by its exact hash."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: SafeContentPresentationRef
    presentation: ContentPresentation

    @model_validator(mode="after")
    def _validate_ref(self) -> Self:
        expected = safe_content_presentation_ref(self.presentation)
        if self.ref != expected:
            raise ValueError(
                "safe presentation reference does not authenticate payload",
            )
        return self


class ContentCatalogResponse(BaseModel):
    """Self-authenticating public descriptor catalog for one content set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[7] = CONTENT_CATALOG_SCHEMA_VERSION
    content_set_digest: str
    catalog_digest: str
    entries: tuple[ContentCatalogEntry, ...]
    presets: tuple[ContentRecipePresetCatalogEntry, ...]
    safe_presentations: tuple[SafeContentPresentationCatalogEntry, ...]

    @model_validator(mode="after")
    def _validate_catalog(self) -> Self:
        expected_order = tuple(sorted(
            self.entries,
            key=lambda entry: (
                entry.ordering.sort_group,
                entry.ordering.sort_order,
                entry.ref.identity_key,
            ),
        ))
        if self.entries != expected_order:
            raise ValueError("content catalog entries must use canonical order")
        keys = [entry.ref.identity_key for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("content catalog entries contain duplicate identities")
        expected_preset_order = tuple(sorted(
            self.presets,
            key=lambda preset: (
                preset.ordering.sort_group,
                preset.ordering.sort_order,
                preset.ref.identity_key,
            ),
        ))
        if self.presets != expected_preset_order:
            raise ValueError("content recipe presets must use canonical order")
        preset_keys = [preset.ref.identity_key for preset in self.presets]
        if len(preset_keys) != len(set(preset_keys)):
            raise ValueError("content recipe presets contain duplicate identities")
        recipe_digests = [
            preset.recipe.recipe_digest
            for preset in self.presets
        ]
        if len(recipe_digests) != len(set(recipe_digests)):
            raise ValueError("content recipe presets contain recipe aliases")
        expected_safe_order = tuple(sorted(
            self.safe_presentations,
            key=lambda row: row.ref.presentation_contract_hash,
        ))
        if self.safe_presentations != expected_safe_order:
            raise ValueError(
                "safe content presentations must use canonical order",
            )
        safe_refs = [
            row.ref.presentation_contract_hash
            for row in self.safe_presentations
        ]
        if len(safe_refs) != len(set(safe_refs)):
            raise ValueError(
                "safe content presentations contain duplicate identities",
            )
        expected_safe_refs = {
            safe_content_presentation_ref(
                row.presentation,
            ).presentation_contract_hash
            for row in (*self.entries, *self.presets)
        }
        if set(safe_refs) != expected_safe_refs:
            raise ValueError(
                "safe content presentations must exactly cover public "
                "definition and preset presentations",
            )
        expected_digest = compute_content_catalog_digest(
            self.content_set_digest,
            self.entries,
            self.presets,
            self.safe_presentations,
        )
        if self.catalog_digest != expected_digest:
            raise ValueError(
                "catalog_digest does not authenticate the content catalog",
            )
        return self


def compute_content_catalog_digest(
    content_set_digest: str,
    entries: tuple[ContentCatalogEntry, ...],
    presets: tuple[ContentRecipePresetCatalogEntry, ...],
    safe_presentations: tuple[SafeContentPresentationCatalogEntry, ...],
) -> str:
    """Hash the complete ordered public descriptor payload."""
    validate_sha256(content_set_digest, "content_set_digest")
    encoded = json.dumps(
        {
            "schema_version": CONTENT_CATALOG_SCHEMA_VERSION,
            "content_set_digest": content_set_digest,
            "entries": [
                entry.model_dump(mode="json")
                for entry in entries
            ],
            "presets": [
                preset.model_dump(mode="json")
                for preset in presets
            ],
            "safe_presentations": [
                row.model_dump(mode="json")
                for row in safe_presentations
            ],
        },
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_content_manifest(
    loaded: LoadedContentSystem,
) -> ContentManifestResponse:
    """Project one frozen runtime into an exact code-free manifest."""
    packs = [
        ContentPackManifestEntry(
            pack_id=pack_id,
            pack_version=version,
            origin=ContentPackOrigin.BUILT_IN,
            dependencies=tuple(sorted(BUILT_IN_PACK_DEPENDENCIES[pack_id])),
        )
        for pack_id, version in BUILT_IN_PACK_VERSIONS.items()
    ]
    packs.extend(
        ContentPackManifestEntry(
            pack_id=pack.manifest.pack_id,
            pack_version=pack.manifest.pack_version,
            origin=ContentPackOrigin.EXTERNAL,
            dependencies=pack.manifest.dependency_pack_ids,
            manifest_contract_digest=pack.manifest.contract_digest,
            pack_digest=pack.discovery_pack_digest,
        )
        for pack in loaded.packs
    )
    return ContentManifestResponse(
        engine_content_api=ENGINE_CONTENT_API_VERSION,
        content_set_digest=loaded.content_set_digest,
        built_in_artifact_digest=loaded.built_in_artifact_digest,
        packs=tuple(sorted(packs, key=lambda pack: pack.pack_id)),
        sources=tuple(sorted(
            loaded.registry.sources.values(),
            key=lambda source: source.source_id,
        )),
    )


def build_public_content_catalog(
    loaded: LoadedContentSystem,
) -> ContentCatalogResponse:
    """Return only definitions explicitly safe for unconditional discovery."""
    entries = []
    for declaration in loaded.registry.declarations.values():
        descriptor = declaration.descriptor
        if descriptor.visibility != ContentVisibility.PUBLIC:
            continue
        entries.append(
            ContentCatalogEntry(
                ref=declaration.ref,
                display_name=descriptor.display_name,
                description=descriptor.description,
                tags=descriptor.tags,
                visibility=descriptor.visibility,
                presentation=descriptor.presentation,
                ordering=descriptor.ordering,
                related_content_refs=descriptor.related_content_refs,
                provenance=declaration.provenance,
                definition_mode=declaration.mode,
                runtime_behavior_kind=declaration.runtime_behavior_kind,
                item_definition=declaration.item_definition,
                spatial_effect_definition=(
                    declaration.spatial_effect_definition
                ),
                dependencies=declaration.dependencies,
                condition_effect_coverage=(
                    declaration.condition_effect_coverage
                ),
                condition_effect_profile=(
                    _resolve_public_condition_effect_profile(
                        loaded,
                        declaration.condition_effect_profile,
                    )
                    if declaration.condition_effect_profile is not None
                    else None
                ),
                condition_lifecycle=declaration.condition_lifecycle,
                parameter_schema=(
                    declaration.construction.parameter_model.model_json_schema(
                        mode="validation",
                    )
                    if declaration.construction is not None
                    else None
                ),
            ),
        )
    ordered = tuple(sorted(
        entries,
        key=lambda entry: (
            entry.ordering.sort_group,
            entry.ordering.sort_order,
            entry.ref.identity_key,
        ),
    ))
    presets = []
    for preset in loaded.registry.recipe_presets.values():
        descriptor = preset.descriptor
        if descriptor.visibility != ContentVisibility.PUBLIC:
            continue
        presets.append(
            ContentRecipePresetCatalogEntry(
                ref=preset.ref,
                recipe=preset.recipe,
                display_name=descriptor.display_name,
                description=descriptor.description,
                tags=descriptor.tags,
                visibility=descriptor.visibility,
                presentation=descriptor.presentation,
                ordering=descriptor.ordering,
                related_content_refs=descriptor.related_content_refs,
                provenance=preset.provenance,
            ),
        )
    ordered_presets = tuple(sorted(
        presets,
        key=lambda preset: (
            preset.ordering.sort_group,
            preset.ordering.sort_order,
            preset.ref.identity_key,
        ),
    ))
    safe_presentations_by_hash: dict[
        str,
        SafeContentPresentationCatalogEntry,
    ] = {}
    for presentation in (
        *(entry.presentation for entry in ordered),
        *(preset.presentation for preset in ordered_presets),
    ):
        ref = safe_content_presentation_ref(presentation)
        safe_presentations_by_hash.setdefault(
            ref.presentation_contract_hash,
            SafeContentPresentationCatalogEntry(
                ref=ref,
                presentation=presentation,
            ),
        )
    safe_presentations = tuple(
        safe_presentations_by_hash[key]
        for key in sorted(safe_presentations_by_hash)
    )
    return ContentCatalogResponse(
        content_set_digest=loaded.content_set_digest,
        catalog_digest=compute_content_catalog_digest(
            loaded.content_set_digest,
            ordered,
            ordered_presets,
            safe_presentations,
        ),
        entries=ordered,
        presets=ordered_presets,
        safe_presentations=safe_presentations,
    )


def _resolve_public_condition_effect_profile(
    loaded: LoadedContentSystem,
    profile: AuthoredConditionEffectProfile,
) -> AuthoredConditionEffectProfile:
    """Expand typed cleanse selectors to exact installed public refs."""
    resolved_branches = []
    for branch in profile.branches:
        resolved_effects = []
        for effect in branch.effects:
            selector = effect.selector
            if selector is None:
                resolved_effects.append(effect)
                continue
            matched_refs = tuple(sorted(
                (
                    declaration.ref
                    for declaration in loaded.registry.declarations.values()
                    if (
                        declaration.descriptor.visibility
                        is ContentVisibility.PUBLIC
                        and declaration.condition_lifecycle is not None
                        and set(selector.required_tags).issubset(
                            set(declaration.condition_lifecycle.tags),
                        )
                        and set(
                            selector.required_removal_triggers,
                        ).issubset(
                            set(
                                declaration.condition_lifecycle.removal_triggers,
                            ),
                        )
                    )
                ),
                key=lambda ref: ref.identity_key,
            ))
            resolved_effects.append(effect.model_copy(update={
                "selector": selector.model_copy(update={
                    "resolved_condition_refs": matched_refs,
                }),
            }))
        resolved_branches.append(branch.model_copy(update={
            "effects": tuple(resolved_effects),
        }))
    return profile.model_copy(update={"branches": tuple(resolved_branches)})


def content_response_etag(digest: str) -> str:
    """Return a strong quoted ETag for one authenticated response digest."""
    return f'"{validate_sha256(digest, "digest")}"'
