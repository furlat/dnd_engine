"""Static composition of the engine's trusted built-in content packs."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

from dnd.content_system.builtin_inventory import (
    BUILT_IN_DECLARATION_INVENTORY,
    BUILT_IN_RECIPE_PRESET_INVENTORY,
)
from dnd.core.content.provenance import ContentSource


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SRD_5_1_SOURCE_PATH = (
    REPOSITORY_ROOT / "content_data" / "sources" / "srd_5_1_cc.json"
)
NEURODRAGON_SOURCE_PATH = (
    REPOSITORY_ROOT
    / "content_data"
    / "sources"
    / "neurodragon_original_b2b3930.json"
)
_NEURODRAGON_SOURCE = ContentSource.model_validate_json(
    NEURODRAGON_SOURCE_PATH.read_text(encoding="utf-8"),
)
CORE_RULES_PACK_ID = "core.rules"
SRD_5_1_PACK_ID = "content.srd_5_1_cc"
NEURODRAGON_PACK_ID = "content.neurodragon"

BUILT_IN_SOURCES: tuple[ContentSource, ...] = (
    ContentSource.model_validate_json(
        SRD_5_1_SOURCE_PATH.read_text(encoding="utf-8"),
    ),
    _NEURODRAGON_SOURCE,
    ContentSource.model_validate_json(
        (REPOSITORY_ROOT / "content_data" / "sources" / "ice_knife_legacy.json").read_text(encoding="utf-8"),
    ),
)
BUILT_IN_DECLARATIONS = BUILT_IN_DECLARATION_INVENTORY
BUILT_IN_RECIPE_PRESETS = BUILT_IN_RECIPE_PRESET_INVENTORY
BUILT_IN_PACK_VERSIONS = MappingProxyType(
    {
        CORE_RULES_PACK_ID: "1.0.0",
        NEURODRAGON_PACK_ID: "1.0.0",
        SRD_5_1_PACK_ID: "1.0.0",
    },
)
BUILT_IN_PACK_DEPENDENCIES = MappingProxyType(
    {
        CORE_RULES_PACK_ID: frozenset(),
        NEURODRAGON_PACK_ID: frozenset({
            CORE_RULES_PACK_ID,
            SRD_5_1_PACK_ID,
        }),
        SRD_5_1_PACK_ID: frozenset({CORE_RULES_PACK_ID}),
    },
)
