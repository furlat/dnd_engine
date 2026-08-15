"""Shared built-in content bootstrap used by every deployment composition."""

from __future__ import annotations

from dnd.content_system.builtin import (
    BUILT_IN_ARTIFACT_DIGEST,
    BUILT_IN_DECLARATIONS,
    BUILT_IN_RECIPE_PRESETS,
    BUILT_IN_SOURCES,
)
from dnd.content_system.system import LoadedContentSystem
from dnd.core.content.canonical import canonical_content_sha256
from dnd.core.content.registry import ContentRegistryBuilder


def _content_set_digest() -> str:
    """Return the deterministic identity of the trusted built-in content."""
    return canonical_content_sha256({
        "schema_version": 1,
        "built_in_artifact_digest": BUILT_IN_ARTIFACT_DIGEST,
        "sources": [
            source.model_dump(mode="json")
            for source in sorted(
                BUILT_IN_SOURCES,
                key=lambda row: row.source_id,
            )
        ],
        "declarations": [
            {
                "ref": declaration.ref.model_dump(mode="json"),
                "mode": declaration.mode.value,
                "runtime_behavior_kind": (
                    declaration.runtime_behavior_kind.value
                    if declaration.runtime_behavior_kind is not None
                    else None
                ),
                "descriptor": declaration.descriptor.model_dump(mode="json"),
                "provenance": declaration.provenance.model_dump(mode="json"),
                "item_definition": (
                    declaration.item_definition.model_dump(mode="json")
                    if declaration.item_definition is not None
                    else None
                ),
                "spatial_effect_definition": (
                    declaration.spatial_effect_definition.model_dump(mode="json")
                    if declaration.spatial_effect_definition is not None
                    else None
                ),
                "definition_payload": (
                    declaration.definition_payload.model_dump(mode="json")
                    if declaration.definition_payload is not None
                    else None
                ),
                "dependencies": [
                    dependency.model_dump(mode="json")
                    for dependency in declaration.dependencies
                ],
                "condition_effect_coverage": (
                    declaration.condition_effect_coverage.value
                ),
                "condition_effect_profile": (
                    declaration.condition_effect_profile.model_dump(mode="json")
                    if declaration.condition_effect_profile is not None
                    else None
                ),
                "condition_lifecycle": (
                    declaration.condition_lifecycle.model_dump(mode="json")
                    if declaration.condition_lifecycle is not None
                    else None
                ),
            }
            for declaration in sorted(
                BUILT_IN_DECLARATIONS,
                key=lambda row: row.ref.identity_key,
            )
        ],
        "recipe_presets": [
            preset.model_dump(mode="json")
            for preset in sorted(
                BUILT_IN_RECIPE_PRESETS,
                key=lambda row: row.ref.identity_key,
            )
        ],
    })


def bootstrap_content_system() -> LoadedContentSystem:
    """Validate trusted built-ins and return one complete frozen registry."""
    builder = ContentRegistryBuilder()
    for source in BUILT_IN_SOURCES:
        builder.add_source(source)
    for declaration in BUILT_IN_DECLARATIONS:
        builder.add_declaration(declaration)
    for preset in BUILT_IN_RECIPE_PRESETS:
        builder.add_recipe_preset(preset)
    return LoadedContentSystem(
        registry=builder.freeze(),
        built_in_artifact_digest=BUILT_IN_ARTIFACT_DIGEST,
        content_set_digest=_content_set_digest(),
    )
