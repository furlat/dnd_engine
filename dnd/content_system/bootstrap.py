"""Shared content-system bootstrap used by every deployment composition."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from dnd.content_system.builtin import (
    BUILT_IN_ARTIFACT_DIGEST,
    BUILT_IN_DECLARATIONS,
    BUILT_IN_PACK_DEPENDENCIES,
    BUILT_IN_PACK_VERSIONS,
    BUILT_IN_RECIPE_PRESETS,
    BUILT_IN_SOURCES,
)
from dnd.content_system.configuration import configured_content_pack_roots
from dnd.content_system.builtin_inventory import (
    BUILT_IN_BEHAVIOR_DECLARATIONS_BY_CLASS,
    BUILT_IN_PROVIDER_ONLY_BEHAVIOR_IDS,
)
from dnd.content_system.pack_loader import (
    LoadedContentSystem,
    load_content_system,
)


def bootstrap_content_system(
    *,
    pack_roots: Sequence[Path] | None = None,
) -> LoadedContentSystem:
    """Validate all configured content and return one complete frozen system."""
    resolved_roots = (
        configured_content_pack_roots()
        if pack_roots is None
        else tuple(pack_roots)
    )
    loaded = load_content_system(
        pack_roots=resolved_roots,
        built_in_artifact_digest=BUILT_IN_ARTIFACT_DIGEST,
        built_in_sources=BUILT_IN_SOURCES,
        built_in_declarations=BUILT_IN_DECLARATIONS,
        built_in_recipe_presets=BUILT_IN_RECIPE_PRESETS,
        built_in_pack_versions=BUILT_IN_PACK_VERSIONS,
        built_in_pack_dependencies=BUILT_IN_PACK_DEPENDENCIES,
    )
    return replace(
        loaded,
        behavior_declarations_by_class=(
            BUILT_IN_BEHAVIOR_DECLARATIONS_BY_CLASS
        ),
        provider_only_behavior_ids=BUILT_IN_PROVIDER_ONLY_BEHAVIOR_IDS,
    )
