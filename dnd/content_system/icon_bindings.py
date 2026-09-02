"""Authenticated built-in content bindings to one reviewed icon atlas.

This module is the cold runtime boundary.  It consumes only checked-in
ContentRef-keyed data and never inspects renderer files, Python implementation
paths, display names, aliases, or normalized strings.  The offline importer is
the only place where legacy evidence may be consulted.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.core.content.descriptors import (
    ContentVisibility,
)
from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
    validate_sha256,
)
from dnd.core.content.recipe_presets import (
    ContentRecipePreset,
    ContentRecipePresetRef,
)
from dnd.core.content.registration import ContentDeclaration
from dnd.content.characters.class_definitions import (
    CHARACTER_RETIRED_DECLARATION_IDS,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GAME_ICON_ASSET_INDEX_PATH = (
    REPOSITORY_ROOT
    / "content_data"
    / "ledgers"
    / "neuroclient_game_icon_asset_index.json"
)
CONTENT_ICON_BINDING_LEDGER_PATH = (
    REPOSITORY_ROOT
    / "content_data"
    / "ledgers"
    / "content_icon_bindings.json"
)


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class IconBindingDecision(str, Enum):
    """Whether one public definition owns an authenticated atlas asset."""

    BIND = "bind"
    INTENTIONAL_NULL = "intentional_null"
    MISSING_ASSET = "missing_asset"
    AMBIGUOUS = "ambiguous"


class IconBindingEvidenceKind(str, Enum):
    """Reviewed evidence used by the offline import, never runtime lookup."""

    AUTHORED_PRESENTATION = "authored_presentation"
    BACKEND_SPELL_CATALOG = "backend_spell_catalog"
    BACKEND_CONDITION_CLASS = "backend_condition_class"
    RUNTIME_ACTION_CLASS = "runtime_action_class"
    CONTEXTUAL_ACTION = "contextual_action"
    BACKEND_ITEM_CATALOG = "backend_item_catalog"
    RUNTIME_ITEM_CLASS = "runtime_item_class"
    BACKEND_ENVIRONMENT_CATALOG = "backend_environment_catalog"
    CONTENT_DEPENDENCY = "content_dependency"
    HUMAN_REVIEWED = "human_reviewed"
    INHERIT_DEFINITION = "inherit_definition"
    INTENTIONAL_DYNAMIC_PROVIDER = "intentional_dynamic_provider"
    INTENTIONAL_NON_ICON_PRESENTATION = (
        "intentional_non_icon_presentation"
    )
    UNRESOLVED_AMBIGUOUS = "unresolved_ambiguous"
    UNRESOLVED_UNCOVERED = "unresolved_uncovered"


class IconManifestIdentity(BaseModel):
    """Pinned identity of the external manifest used only during import."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sha256: str
    schema_version: int = Field(ge=1)
    style_id: str = Field(min_length=1)
    asset_count: int = Field(ge=1)

    @model_validator(mode="after")
    def _validate_digest(self) -> Self:
        validate_sha256(self.sha256, "sha256")
        return self


class GameIconAssetIndexRow(BaseModel):
    """One exact asset key and immutable payload digest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    icon_key: str = Field(min_length=1)
    asset_sha256: str
    asset_path: str = Field(
        min_length=1,
        description="Renderer-root-relative immutable asset path.",
    )

    @model_validator(mode="after")
    def _validate_digest(self) -> Self:
        validate_sha256(self.asset_sha256, "asset_sha256")
        if not self.asset_path.startswith("/game-icons/"):
            raise ValueError("asset_path must be renderer-root-relative")
        return self


class GameIconAssetIndex(BaseModel):
    """Backend-vendored exact key/digest index for one renderer icon atlas."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    source_manifest: IconManifestIdentity
    asset_index_digest: str
    assets: tuple[GameIconAssetIndexRow, ...]

    @model_validator(mode="after")
    def _validate_index(self) -> Self:
        validate_sha256(self.asset_index_digest, "asset_index_digest")
        keys = [row.icon_key for row in self.assets]
        if len(keys) != len(set(keys)):
            raise ValueError("game icon asset keys must be unique")
        paths = [row.asset_path for row in self.assets]
        if len(paths) != len(set(paths)):
            raise ValueError("game icon asset paths must be unique")
        if len(self.assets) != self.source_manifest.asset_count:
            raise ValueError("source manifest asset count does not match index")
        expected = _canonical_digest(
            [row.model_dump(mode="json") for row in self.assets],
        )
        if self.asset_index_digest != expected:
            raise ValueError("asset_index_digest does not authenticate assets")
        return self


class ContentIconBindingRow(BaseModel):
    """One exact built-in public definition and its reviewed disposition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content_ref: ContentRef
    decision: IconBindingDecision
    icon_key: str | None
    asset_sha256: str | None
    evidence_kind: IconBindingEvidenceKind
    evidence_token: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_disposition(self) -> Self:
        if self.decision is IconBindingDecision.BIND:
            if self.icon_key is None or self.asset_sha256 is None:
                raise ValueError("bound icon row requires key and asset digest")
            validate_sha256(self.asset_sha256, "asset_sha256")
            if self.evidence_kind in {
                IconBindingEvidenceKind.UNRESOLVED_AMBIGUOUS,
                IconBindingEvidenceKind.UNRESOLVED_UNCOVERED,
            }:
                raise ValueError("bound icon row cannot use unresolved evidence")
        elif self.decision is IconBindingDecision.AMBIGUOUS:
            if self.icon_key is not None or self.asset_sha256 is not None:
                raise ValueError("unresolved icon row cannot name an asset")
            if (
                self.evidence_kind
                is not IconBindingEvidenceKind.UNRESOLVED_AMBIGUOUS
            ):
                raise ValueError("ambiguous row requires ambiguous evidence")
        elif self.decision is IconBindingDecision.MISSING_ASSET:
            if self.icon_key is not None or self.asset_sha256 is not None:
                raise ValueError("missing-asset row cannot name an asset")
            if (
                self.evidence_kind
                is not IconBindingEvidenceKind.UNRESOLVED_UNCOVERED
            ):
                raise ValueError(
                    "missing-asset row requires uncovered evidence",
                )
        else:
            if self.icon_key is not None or self.asset_sha256 is not None:
                raise ValueError("intentional-null row cannot name an asset")
            if self.evidence_kind not in {
                IconBindingEvidenceKind.INTENTIONAL_DYNAMIC_PROVIDER,
                IconBindingEvidenceKind.INTENTIONAL_NON_ICON_PRESENTATION,
            }:
                raise ValueError(
                    "intentional-null row requires a closed omission reason",
                )
        return self


class RecipePresetIconBindingRow(BaseModel):
    """One exact source preset and explicit definition-icon inheritance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preset_ref: ContentRecipePresetRef
    inherit_definition_ref: ContentRef
    bound_preset_contract_hash: str
    decision: IconBindingDecision
    icon_key: str | None
    asset_sha256: str | None
    evidence_kind: Literal[IconBindingEvidenceKind.INHERIT_DEFINITION]
    evidence_token: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_disposition(self) -> Self:
        validate_sha256(
            self.bound_preset_contract_hash,
            "bound_preset_contract_hash",
        )
        if self.decision is IconBindingDecision.BIND:
            if self.icon_key is None or self.asset_sha256 is None:
                raise ValueError("bound preset row requires key and digest")
            validate_sha256(self.asset_sha256, "asset_sha256")
        elif self.icon_key is not None or self.asset_sha256 is not None:
            raise ValueError("null preset row cannot name an asset")
        if self.evidence_token != self.inherit_definition_ref.identity_key:
            raise ValueError(
                "preset evidence token must be the exact inherited identity",
            )
        return self


class BuiltInContentIconBindingLedger(BaseModel):
    """Complete authenticated icon disposition for all built-in public rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    source_manifest: IconManifestIdentity
    asset_index_digest: str
    binding_digest: str
    definitions: tuple[ContentIconBindingRow, ...]
    recipe_presets: tuple[RecipePresetIconBindingRow, ...]

    @model_validator(mode="after")
    def _validate_ledger(self) -> Self:
        validate_sha256(self.asset_index_digest, "asset_index_digest")
        validate_sha256(self.binding_digest, "binding_digest")
        definition_identities = [
            row.content_ref.identity_key
            for row in self.definitions
        ]
        if len(definition_identities) != len(set(definition_identities)):
            raise ValueError("content icon definition rows must be unique")
        preset_identities = [
            row.preset_ref.identity_key
            for row in self.recipe_presets
        ]
        if len(preset_identities) != len(set(preset_identities)):
            raise ValueError("content icon preset rows must be unique")
        expected = _canonical_digest({
            "definitions": [
                row.model_dump(mode="json")
                for row in self.definitions
            ],
            "recipe_presets": [
                row.model_dump(mode="json")
                for row in self.recipe_presets
            ],
        })
        if self.binding_digest != expected:
            raise ValueError(
                "binding_digest does not authenticate icon bindings",
            )
        return self


def validate_builtin_content_icons(
    *,
    declarations: tuple[ContentDeclaration, ...],
    recipe_presets: tuple[ContentRecipePreset, ...],
    ledger: BuiltInContentIconBindingLedger,
    asset_index: GameIconAssetIndex,
) -> tuple[tuple[ContentDeclaration, ...], tuple[ContentRecipePreset, ...]]:
    """Validate icons already bound during original descriptor construction."""
    if ledger.source_manifest != asset_index.source_manifest:
        raise ValueError("icon ledger and asset index source manifests differ")
    if ledger.asset_index_digest != asset_index.asset_index_digest:
        raise ValueError("icon ledger targets another asset index")
    assets_by_key = {
        row.icon_key: row
        for row in asset_index.assets
    }
    public_by_identity = {
        declaration.ref.identity_key: declaration
        for declaration in declarations
        if declaration.descriptor.visibility == ContentVisibility.PUBLIC
    }
    rows_by_identity = {
        row.content_ref.identity_key: row
        for row in ledger.definitions
        if row.content_ref.definition_kind not in {
            ContentDefinitionKind.ITEM,
            ContentDefinitionKind.ENVIRONMENT_OBJECT,
            ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE,
        }
        and row.content_ref.definition_kind not in {
            ContentDefinitionKind.SPECIES,
            ContentDefinitionKind.SPECIES_VARIANT,
            ContentDefinitionKind.BACKGROUND,
        }
        and not row.content_ref.content_id.startswith("trait.origin.")
        and row.content_ref.content_id
        != "action.origin.dragonborn.breath_weapon"
        and row.content_ref.content_id
        != "starting_holdings.background.acolyte"
        and row.content_ref.content_id not in CHARACTER_RETIRED_DECLARATION_IDS
        and not row.content_ref.content_id.startswith("creature.player.")
        and not row.content_ref.content_id.startswith("creature.premade.")
    }
    if rows_by_identity.keys() != public_by_identity.keys():
        missing = sorted(public_by_identity.keys() - rows_by_identity.keys())
        unknown = sorted(rows_by_identity.keys() - public_by_identity.keys())
        raise ValueError(
            "icon ledger public-definition closure mismatch; "
            f"missing={missing}, unknown={unknown}",
        )

    definition_rows_by_ref: dict[str, ContentIconBindingRow] = {}
    for declaration in declarations:
        if declaration.descriptor.visibility != ContentVisibility.PUBLIC:
            continue
        row = rows_by_identity[declaration.ref.identity_key]
        if row.icon_key is not None:
            asset = assets_by_key.get(row.icon_key)
            if asset is None or asset.asset_sha256 != row.asset_sha256:
                raise ValueError(
                    "icon binding names a missing or mismatched asset for "
                    f"{declaration.ref.identity_key}",
                )
        definition_rows_by_ref[declaration.ref.identity_key] = row
        if declaration.descriptor.presentation.icon_key != row.icon_key:
            raise ValueError(
                "original built-in descriptor was not bound to its exact "
                f"icon ledger row: {declaration.ref.identity_key}",
            )

    preset_rows_by_identity = {
        row.preset_ref.identity_key: row
        for row in ledger.recipe_presets
        if row.inherit_definition_ref.definition_kind not in {
            ContentDefinitionKind.ITEM,
            ContentDefinitionKind.ENVIRONMENT_OBJECT,
            ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE,
        }
    }
    presets_by_identity = {
        preset.ref.identity_key: preset
        for preset in recipe_presets
    }
    if preset_rows_by_identity.keys() != presets_by_identity.keys():
        missing = sorted(
            presets_by_identity.keys() - preset_rows_by_identity.keys(),
        )
        unknown = sorted(
            preset_rows_by_identity.keys() - presets_by_identity.keys(),
        )
        raise ValueError(
            "icon ledger recipe-preset closure mismatch; "
            f"missing={missing}, unknown={unknown}",
        )

    for preset in recipe_presets:
        row = preset_rows_by_identity[preset.ref.identity_key]
        if row.preset_ref != preset.ref:
            raise ValueError(
                "icon ledger preset contract is stale for "
                f"{preset.ref.identity_key}",
            )
        if row.inherit_definition_ref != preset.recipe.ref:
            raise ValueError(
                "icon preset inheritance target disagrees with recipe for "
                f"{preset.ref.identity_key}",
            )
        definition_row = definition_rows_by_ref.get(
            row.inherit_definition_ref.identity_key,
        )
        if (
            definition_row is None
            or definition_row.content_ref != row.inherit_definition_ref
            or definition_row.decision is not row.decision
            or definition_row.icon_key != row.icon_key
            or definition_row.asset_sha256 != row.asset_sha256
        ):
            raise ValueError(
                "icon preset does not exactly inherit its definition row for "
                f"{preset.ref.identity_key}",
            )
        if preset.descriptor.presentation.icon_key != row.icon_key:
            raise ValueError(
                "original built-in preset did not inherit its exact "
                f"definition icon: {preset.ref.identity_key}",
            )
        if preset.ref.preset_contract_hash != row.bound_preset_contract_hash:
            raise ValueError(
                "icon preset bound contract hash is stale for "
                f"{preset.ref.identity_key}",
            )
    return declarations, recipe_presets


def load_game_icon_asset_index(path: Path) -> GameIconAssetIndex:
    """Load one checked-in asset index with strict schema validation."""
    return GameIconAssetIndex.model_validate_json(
        path.read_text(encoding="utf-8"),
    )


def load_content_icon_binding_ledger(
    path: Path,
) -> BuiltInContentIconBindingLedger:
    """Load one checked-in exact ContentRef binding ledger."""
    return BuiltInContentIconBindingLedger.model_validate_json(
        path.read_text(encoding="utf-8"),
    )


NEUROCLIENT_GAME_ICON_ASSET_INDEX = load_game_icon_asset_index(
    GAME_ICON_ASSET_INDEX_PATH,
)
BUILT_IN_CONTENT_ICON_BINDING_LEDGER = load_content_icon_binding_ledger(
    CONTENT_ICON_BINDING_LEDGER_PATH,
)


__all__ = [
    "BUILT_IN_CONTENT_ICON_BINDING_LEDGER",
    "CONTENT_ICON_BINDING_LEDGER_PATH",
    "BuiltInContentIconBindingLedger",
    "ContentIconBindingRow",
    "GAME_ICON_ASSET_INDEX_PATH",
    "GameIconAssetIndex",
    "GameIconAssetIndexRow",
    "IconBindingDecision",
    "IconBindingEvidenceKind",
    "IconManifestIdentity",
    "NEUROCLIENT_GAME_ICON_ASSET_INDEX",
    "RecipePresetIconBindingRow",
    "load_content_icon_binding_ledger",
    "load_game_icon_asset_index",
    "validate_builtin_content_icons",
]
