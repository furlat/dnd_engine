"""Immutable catalogs for reproducible policy promotion workers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai.policy.definitions import PolicyGenerationIdentity
from dnd.scenarios.evaluation.models import BattlefieldSpec, DeploymentSpec, SideConfigurationSpec


class PromotionCatalogSnapshot(BaseModel):
    """Complete roster, context, ruleset, and executable-policy catalog."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Promotion catalog schema version.")
    generated_at: str = Field(description="UTC snapshot generation timestamp.")
    ruleset_id: str = Field(description="Single engine ruleset identity.")
    configurations: tuple[SideConfigurationSpec, ...] = Field(description="Generic rated roster catalog.")
    battlefields: tuple[BattlefieldSpec, ...] = Field(description="Battlefield catalog.")
    deployments: tuple[DeploymentSpec, ...] = Field(description="Symmetric promotion deployments.")
    policy_generations: tuple[PolicyGenerationIdentity, ...] = Field(description="Executable policy releases.")
    catalog_hash: str = Field(description="SHA-256 of all mechanical and executable identities.")

    def configuration(self, configuration_id: str) -> SideConfigurationSpec:
        """Return one generic roster configuration."""
        for row in self.configurations:
            if row.configuration_id == configuration_id:
                return row
        raise KeyError(f"Unknown promotion configuration: {configuration_id}")

    def battlefield(self, battlefield_id: str) -> BattlefieldSpec:
        """Return one battlefield context."""
        for row in self.battlefields:
            if row.battlefield_id == battlefield_id:
                return row
        raise KeyError(f"Unknown promotion battlefield: {battlefield_id}")

    def deployment(self, deployment_id: str) -> DeploymentSpec:
        """Return one symmetric deployment context."""
        for row in self.deployments:
            if row.deployment_id == deployment_id:
                return row
        raise KeyError(f"Unknown promotion deployment: {deployment_id}")

    def policy(self, generation_id: str) -> PolicyGenerationIdentity:
        """Return one executable policy identity."""
        for row in self.policy_generations:
            if row.generation_id == generation_id:
                return row
        raise KeyError(f"Unknown promotion policy generation: {generation_id}")


def build_promotion_catalog_snapshot(
    *,
    configurations: tuple[SideConfigurationSpec, ...],
    battlefields: tuple[BattlefieldSpec, ...],
    deployments: tuple[DeploymentSpec, ...],
    policy_generations: tuple[PolicyGenerationIdentity, ...],
    ruleset_id: str = "single-videogame-ruleset-v1",
    generated_at: str | None = None,
) -> PromotionCatalogSnapshot:
    """Build and authenticate one complete promotion catalog."""
    _require_unique(configurations, "configuration_id")
    _require_unique(battlefields, "battlefield_id")
    _require_unique(deployments, "deployment_id")
    _require_unique(policy_generations, "generation_id")
    payload = {
        "ruleset_id": ruleset_id,
        "configurations": sorted((row.configuration_id, row.mechanical_hash) for row in configurations),
        "battlefields": sorted((row.battlefield_id, row.content_hash) for row in battlefields),
        "deployments": sorted((row.deployment_id, row.content_hash) for row in deployments),
        "policy_generations": sorted(
            (row.generation_id, row.executable_sha256) for row in policy_generations
        ),
    }
    catalog_hash = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return PromotionCatalogSnapshot(
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
        ruleset_id=ruleset_id,
        configurations=configurations,
        battlefields=battlefields,
        deployments=deployments,
        policy_generations=policy_generations,
        catalog_hash=catalog_hash,
    )


def write_promotion_catalog_snapshot(
    snapshot: PromotionCatalogSnapshot,
    path: Path | str,
) -> Path:
    """Atomically write canonical promotion catalog JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(
        json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, indent=2),
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def load_promotion_catalog_snapshot(path: Path | str) -> PromotionCatalogSnapshot:
    """Load and independently authenticate one promotion catalog."""
    snapshot = PromotionCatalogSnapshot.model_validate_json(Path(path).read_text(encoding="utf-8"))
    rebuilt = build_promotion_catalog_snapshot(
        configurations=snapshot.configurations,
        battlefields=snapshot.battlefields,
        deployments=snapshot.deployments,
        policy_generations=snapshot.policy_generations,
        ruleset_id=snapshot.ruleset_id,
        generated_at=snapshot.generated_at,
    )
    if rebuilt.catalog_hash != snapshot.catalog_hash:
        raise ValueError("Promotion catalog hash differs from its mechanical content.")
    return snapshot


def _require_unique(rows: tuple[object, ...], field_name: str) -> None:
    """Reject duplicate stable identities in one immutable catalog."""
    values = [str(getattr(row, field_name)) for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate promotion catalog {field_name} values are not allowed.")
