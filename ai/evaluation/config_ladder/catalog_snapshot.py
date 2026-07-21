"""Immutable catalog snapshots for reproducible configuration experiments."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dnd.scenarios.evaluation.models import BattlefieldSpec, DeploymentSpec, SideConfigurationSpec


class CatalogSnapshot(BaseModel):
    """Complete typed catalog and runtime identity supplied to workers."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Catalog snapshot schema version.")
    generated_at: str = Field(description="UTC snapshot generation timestamp.")
    ruleset_id: str = Field(description="Single engine ruleset identity.")
    policy_version: str = Field(description="Traditional AI policy version under evaluation.")
    policy_source_hash: str = Field(description="Hash of the complete policy source snapshot.")
    heroes: tuple[SideConfigurationSpec, ...] = Field(description="Rated hero configuration catalog.")
    monster_parties: tuple[SideConfigurationSpec, ...] = Field(description="Rated monster-party configuration catalog.")
    battlefields: tuple[BattlefieldSpec, ...] = Field(description="Battlefield catalog.")
    deployments: tuple[DeploymentSpec, ...] = Field(description="Deployment catalog.")
    catalog_hash: str = Field(description="Hash of all mechanical catalogs and runtime identities.")

    def hero(self, configuration_id: str) -> SideConfigurationSpec:
        """Return one hero configuration by id."""
        return _find_configuration(self.heroes, configuration_id)

    def monster_party(self, configuration_id: str) -> SideConfigurationSpec:
        """Return one monster-party configuration by id."""
        return _find_configuration(self.monster_parties, configuration_id)

    def battlefield(self, battlefield_id: str) -> BattlefieldSpec:
        """Return one battlefield by id."""
        for row in self.battlefields:
            if row.battlefield_id == battlefield_id:
                return row
        raise KeyError(f"Unknown battlefield: {battlefield_id}")

    def deployment(self, deployment_id: str) -> DeploymentSpec:
        """Return one deployment by id."""
        for row in self.deployments:
            if row.deployment_id == deployment_id:
                return row
        raise KeyError(f"Unknown deployment: {deployment_id}")


def build_catalog_snapshot(
    *,
    heroes: tuple[SideConfigurationSpec, ...],
    monster_parties: tuple[SideConfigurationSpec, ...],
    battlefields: tuple[BattlefieldSpec, ...],
    deployments: tuple[DeploymentSpec, ...],
    policy_version: str,
    policy_source_hash: str,
    ruleset_id: str = "single-videogame-ruleset-v1",
    generated_at: str | None = None,
) -> CatalogSnapshot:
    """Build and hash a complete immutable catalog snapshot."""
    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    payload = {
        "ruleset_id": ruleset_id,
        "policy_version": policy_version,
        "policy_source_hash": policy_source_hash,
        "heroes": [_mechanical_configuration_payload(row) for row in heroes],
        "monster_parties": [_mechanical_configuration_payload(row) for row in monster_parties],
        "battlefields": [_mechanical_model_payload(row) for row in battlefields],
        "deployments": [_mechanical_model_payload(row) for row in deployments],
    }
    catalog_hash = _stable_hash(payload)
    return CatalogSnapshot(
        generated_at=timestamp,
        ruleset_id=ruleset_id,
        policy_version=policy_version,
        policy_source_hash=policy_source_hash,
        heroes=heroes,
        monster_parties=monster_parties,
        battlefields=battlefields,
        deployments=deployments,
        catalog_hash=catalog_hash,
    )


def write_catalog_snapshot(snapshot: CatalogSnapshot, path: Path | str) -> Path:
    """Write a catalog snapshot atomically as canonical JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{sha256(str(destination).encode()).hexdigest()[:8]}.tmp")
    temporary.write_text(
        json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, indent=2),
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def load_catalog_snapshot(path: Path | str) -> CatalogSnapshot:
    """Load and authenticate one retained catalog snapshot."""
    snapshot = CatalogSnapshot.model_validate_json(Path(path).read_text(encoding="utf-8"))
    rebuilt = build_catalog_snapshot(
        heroes=snapshot.heroes,
        monster_parties=snapshot.monster_parties,
        battlefields=snapshot.battlefields,
        deployments=snapshot.deployments,
        policy_version=snapshot.policy_version,
        policy_source_hash=snapshot.policy_source_hash,
        ruleset_id=snapshot.ruleset_id,
        generated_at=snapshot.generated_at,
    )
    if rebuilt.catalog_hash != snapshot.catalog_hash:
        raise ValueError("Catalog snapshot hash does not match its mechanical content.")
    return snapshot


def _find_configuration(
    rows: tuple[SideConfigurationSpec, ...],
    configuration_id: str,
) -> SideConfigurationSpec:
    """Return one side configuration by stable id."""
    for row in rows:
        if row.configuration_id == configuration_id:
            return row
    raise KeyError(f"Unknown side configuration: {configuration_id}")


def _mechanical_configuration_payload(row: SideConfigurationSpec) -> dict[str, object]:
    """Return participant identity plus its stable catalog id."""
    return {
        "configuration_id": row.configuration_id,
        "mechanical_hash": row.mechanical_hash,
        "rating_eligible": row.rating_eligible,
    }


def _mechanical_model_payload(row: BaseModel) -> dict[str, object]:
    """Return a model payload without computed fields."""
    return row.model_dump(mode="json", exclude_computed_fields=True)


def _stable_hash(payload: object) -> str:
    """Return SHA-256 for deterministic compact JSON."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()
