"""Static composition of the engine's trusted built-in content packs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import MappingProxyType

from dnd.content_system.artifact_digest import (
    digest_artifact_paths,
    resolve_local_python_module_closure,
)
from dnd.content_system.icon_bindings import (
    BUILT_IN_CONTENT_ICON_BINDING_LEDGER,
    CONTENT_ICON_BINDING_LEDGER_PATH,
    GAME_ICON_ASSET_INDEX_PATH,
    NEUROCLIENT_GAME_ICON_ASSET_INDEX,
    validate_builtin_content_icons,
)
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
NEURODRAGON_SOURCE_DOCUMENT_PATH = (
    REPOSITORY_ROOT
    / "content_data"
    / "sources"
    / "neurodragon_original_b2b3930.txt"
)

_NEURODRAGON_SOURCE = ContentSource.model_validate_json(
    NEURODRAGON_SOURCE_PATH.read_text(encoding="utf-8"),
)
if (
    hashlib.sha256(NEURODRAGON_SOURCE_DOCUMENT_PATH.read_bytes()).hexdigest()
    != _NEURODRAGON_SOURCE.document_digest
):
    raise RuntimeError(
        "Neurodragon original source document digest does not match its "
        "content-source contract",
    )

CORE_RULES_PACK_ID = "core.rules"
SRD_5_1_PACK_ID = "content.srd_5_1_cc"
NEURODRAGON_PACK_ID = "content.neurodragon"

BUILT_IN_SOURCES: tuple[ContentSource, ...] = (
    ContentSource.model_validate_json(
        SRD_5_1_SOURCE_PATH.read_text(encoding="utf-8"),
    ),
    _NEURODRAGON_SOURCE,
)
UNBOUND_BUILT_IN_DECLARATIONS = BUILT_IN_DECLARATION_INVENTORY
UNBOUND_BUILT_IN_RECIPE_PRESETS = BUILT_IN_RECIPE_PRESET_INVENTORY
(
    BUILT_IN_DECLARATIONS,
    BUILT_IN_RECIPE_PRESETS,
) = validate_builtin_content_icons(
    declarations=UNBOUND_BUILT_IN_DECLARATIONS,
    recipe_presets=UNBOUND_BUILT_IN_RECIPE_PRESETS,
    ledger=BUILT_IN_CONTENT_ICON_BINDING_LEDGER,
    asset_index=NEUROCLIENT_GAME_ICON_ASSET_INDEX,
)
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

# The composition module is the sole Python root. Its imports necessarily name
# every declaration owner aggregated below, and the static closure follows all
# local dnd.* helpers without importing them dynamically.
BUILT_IN_IMPLEMENTATION_ROOT_MODULES: tuple[str, ...] = (
    "dnd.content_system.builtin",
)
BUILT_IN_DATA_ARTIFACT_PATHS: tuple[Path, ...] = (
    SRD_5_1_SOURCE_PATH,
    NEURODRAGON_SOURCE_PATH,
    NEURODRAGON_SOURCE_DOCUMENT_PATH,
    (
        REPOSITORY_ROOT
        / "content_data"
        / "ledgers"
        / "neuroclient_authored_item_visuals.json"
    ),
    GAME_ICON_ASSET_INDEX_PATH,
    CONTENT_ICON_BINDING_LEDGER_PATH,
)
BUILT_IN_PYTHON_ARTIFACT_PATHS = resolve_local_python_module_closure(
    BUILT_IN_IMPLEMENTATION_ROOT_MODULES,
    repository_root=REPOSITORY_ROOT,
)
BUILT_IN_ARTIFACT_PATHS: tuple[Path, ...] = tuple(
    sorted(
        {
            *BUILT_IN_PYTHON_ARTIFACT_PATHS,
            *BUILT_IN_DATA_ARTIFACT_PATHS,
        },
        key=lambda path: path.relative_to(REPOSITORY_ROOT).as_posix(),
    ),
)
BUILT_IN_ARTIFACT_DIGEST = digest_artifact_paths(
    BUILT_IN_ARTIFACT_PATHS,
    repository_root=REPOSITORY_ROOT,
)
