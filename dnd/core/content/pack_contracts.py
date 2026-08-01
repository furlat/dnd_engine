"""Cold manifests for trusted installed content packs."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dnd.core.content.canonical import canonical_content_sha256
from dnd.core.content.identities import validate_namespaced_id
from dnd.core.content.provenance import ContentSource


_PYTHON_PACKAGE_PATTERN = re.compile(
    r"^[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*$",
)
_PACK_VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$",
)


def _validate_pack_relative_path(value: str, field_name: str) -> str:
    if "\\" in value:
        raise ValueError(f"{field_name} must use POSIX path separators")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must stay within the pack directory")
    normalized = path.as_posix()
    if (
        value != normalized
        or (value != "." and not path.parts)
        or any(part in {"", "."} for part in path.parts)
    ):
        raise ValueError(f"{field_name} must be a normalized relative path")
    return normalized


class ContentPackDependency(BaseModel):
    """One exact pack dependency declared before importing code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_id: str
    version: str = Field(min_length=1)

    @field_validator("pack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "pack_id")


class ContentPackManifest(BaseModel):
    """Validated data-only manifest for one trusted installed pack."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    pack_id: str
    pack_version: str
    engine_content_api: int = Field(ge=1)
    python_root: str
    python_package: str
    assets_root: str | None = None
    dependencies: tuple[ContentPackDependency, ...] = ()
    sources: tuple[ContentSource, ...] = ()

    @field_validator("pack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "pack_id")

    @field_validator("pack_version")
    @classmethod
    def _validate_pack_version(cls, value: str) -> str:
        if not _PACK_VERSION_PATTERN.fullmatch(value):
            raise ValueError("pack_version must be a semantic version")
        return value

    @field_validator("python_root")
    @classmethod
    def _validate_python_root(cls, value: str) -> str:
        return _validate_pack_relative_path(value, "python_root")

    @field_validator("assets_root")
    @classmethod
    def _validate_assets_root(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_pack_relative_path(value, "assets_root")

    @field_validator("python_package")
    @classmethod
    def _validate_python_package(cls, value: str) -> str:
        if not _PYTHON_PACKAGE_PATTERN.fullmatch(value):
            raise ValueError(
                "python_package must be a lowercase dotted Python package",
            )
        return value

    @field_validator("dependencies")
    @classmethod
    def _order_dependencies(
        cls,
        value: tuple[ContentPackDependency, ...],
    ) -> tuple[ContentPackDependency, ...]:
        return tuple(sorted(value, key=lambda row: row.pack_id))

    @field_validator("sources")
    @classmethod
    def _order_sources(
        cls,
        value: tuple[ContentSource, ...],
    ) -> tuple[ContentSource, ...]:
        return tuple(sorted(value, key=lambda row: row.source_id))

    @model_validator(mode="after")
    def _validate_unique_contracts(self) -> Self:
        dependency_ids = [row.pack_id for row in self.dependencies]
        duplicate_dependencies = sorted({
            pack_id
            for pack_id in dependency_ids
            if dependency_ids.count(pack_id) > 1
        })
        if duplicate_dependencies:
            raise ValueError(
                "Duplicate pack dependency: "
                + ", ".join(duplicate_dependencies),
            )
        if self.pack_id in dependency_ids:
            raise ValueError(f"Pack {self.pack_id} cannot depend on itself")

        source_ids = [row.source_id for row in self.sources]
        duplicate_sources = sorted({
            source_id
            for source_id in source_ids
            if source_ids.count(source_id) > 1
        })
        if duplicate_sources:
            raise ValueError(
                "Duplicate content source: " + ", ".join(duplicate_sources),
            )
        return self

    @property
    def dependency_pack_ids(self) -> tuple[str, ...]:
        """Return deterministic direct dependency identities."""
        return tuple(row.pack_id for row in self.dependencies)

    @property
    def contract_digest(self) -> str:
        """Hash the complete normalized cold manifest contract."""
        return canonical_content_sha256(self.model_dump(mode="json"))
