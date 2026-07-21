"""Typed static and built-map compatibility checks for scenario composition."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from dnd.core.gridmap import GridMap
from dnd.scenarios.evaluation.models import BattlefieldSpec, DeploymentSpec, SideConfigurationSpec


CompatibilitySeverity = Literal["hard", "diagnostic"]
CompatibilityCode = Literal[
    "battlefield_mismatch",
    "blocked_spawn",
    "configuration_kind",
    "diagnostic_configuration",
    "diagnostic_context",
    "duplicate_spawn",
    "forbidden_capability",
    "member_capacity",
    "missing_capability",
    "missing_role_slot",
    "occupied_spawn",
    "out_of_bounds_spawn",
    "unreachable_factions",
]


class CompatibilityIssue(BaseModel):
    """One typed reason emitted by composition preflight."""

    model_config = ConfigDict(frozen=True)

    code: CompatibilityCode = Field(description="Stable machine-readable compatibility reason.")
    severity: CompatibilitySeverity = Field(description="Whether the reason rejects or only annotates the composition.")
    message: str = Field(description="Human-readable compatibility explanation.")
    role: str | None = Field(default=None, description="Deployment role implicated by the issue, if any.")
    position: tuple[int, int] | None = Field(default=None, description="Grid coordinate implicated by the issue, if any.")


class CompatibilityReport(BaseModel):
    """Immutable preflight result for one four-part composition."""

    model_config = ConfigDict(frozen=True)

    hero_configuration_id: str = Field(description="Hero-side configuration checked.")
    monster_configuration_id: str = Field(description="Monster-party configuration checked.")
    battlefield_id: str = Field(description="Battlefield checked.")
    deployment_id: str = Field(description="Deployment checked.")
    phase: Literal["static", "built"] = Field(description="Furthest compatibility phase represented.")
    issues: tuple[CompatibilityIssue, ...] = Field(default_factory=tuple, description="All hard and diagnostic reasons found.")

    @computed_field(return_type=bool)
    @property
    def admitted(self) -> bool:
        """Return whether no hard-invalid reason was found."""
        return not any(issue.severity == "hard" for issue in self.issues)


def _role_positions(
    side: SideConfigurationSpec,
    deployment: DeploymentSpec,
) -> tuple[dict[str, tuple[int, int]], tuple[CompatibilityIssue, ...]]:
    """Resolve active side roles to explicit or ordered deployment slots."""
    role_slots = deployment.hero_role_slots if side.side_kind == "hero" else deployment.monster_role_slots
    ordered_slots = deployment.hero_slots if side.side_kind == "hero" else deployment.monster_slots
    explicit = {slot.role: slot.position for slot in role_slots}
    positions: dict[str, tuple[int, int]] = {}
    issues: list[CompatibilityIssue] = []
    for index, member in enumerate(side.members):
        role = member.deployment_role or member.actor_id
        position = explicit.get(role)
        if position is None and not role_slots and index < len(ordered_slots):
            position = ordered_slots[index]
        if position is None:
            issues.append(CompatibilityIssue(
                code="missing_role_slot",
                severity="hard",
                message=f"Deployment {deployment.deployment_id!r} has no slot for role {role!r}.",
                role=role,
            ))
            continue
        positions[role] = position
    return positions, tuple(issues)


def resolve_deployment_positions(
    hero: SideConfigurationSpec,
    monsters: SideConfigurationSpec,
    deployment: DeploymentSpec,
) -> tuple[dict[str, tuple[int, int]], dict[str, tuple[int, int]]]:
    """Resolve role-addressed positions, raising when static preflight would reject."""
    hero_positions, hero_issues = _role_positions(hero, deployment)
    monster_positions, monster_issues = _role_positions(monsters, deployment)
    issues = (*hero_issues, *monster_issues)
    if issues:
        raise ValueError("; ".join(issue.message for issue in issues))
    return hero_positions, monster_positions


def check_compatibility(
    hero: SideConfigurationSpec,
    monsters: SideConfigurationSpec,
    battlefield: BattlefieldSpec,
    deployment: DeploymentSpec,
) -> CompatibilityReport:
    """Run deterministic compatibility checks that do not construct engine state."""
    issues: list[CompatibilityIssue] = []
    if hero.side_kind != "hero":
        issues.append(CompatibilityIssue(
            code="configuration_kind",
            severity="hard",
            message=f"{hero.configuration_id!r} is not a hero configuration.",
        ))
    if monsters.side_kind != "monster_party":
        issues.append(CompatibilityIssue(
            code="configuration_kind",
            severity="hard",
            message=f"{monsters.configuration_id!r} is not a monster-party configuration.",
        ))
    if deployment.battlefield_id != battlefield.battlefield_id:
        issues.append(CompatibilityIssue(
            code="battlefield_mismatch",
            severity="hard",
            message=(
                f"Deployment {deployment.deployment_id!r} targets {deployment.battlefield_id!r}, "
                f"not {battlefield.battlefield_id!r}."
            ),
        ))
    if len(hero.members) > deployment.max_hero_members:
        issues.append(CompatibilityIssue(
            code="member_capacity",
            severity="hard",
            message=f"Hero side has {len(hero.members)} members but deployment capacity is {deployment.max_hero_members}.",
        ))
    if len(monsters.members) > deployment.max_monster_members:
        issues.append(CompatibilityIssue(
            code="member_capacity",
            severity="hard",
            message=f"Monster side has {len(monsters.members)} members but deployment capacity is {deployment.max_monster_members}.",
        ))

    capabilities = set(battlefield.capabilities)
    for side in (hero, monsters):
        for capability in sorted(set(side.required_battlefield_capabilities) - capabilities):
            issues.append(CompatibilityIssue(
                code="missing_capability",
                severity="hard",
                message=f"{side.configuration_id!r} requires absent battlefield capability {capability!r}.",
            ))
        for capability in sorted(set(side.forbidden_battlefield_capabilities) & capabilities):
            issues.append(CompatibilityIssue(
                code="forbidden_capability",
                severity="hard",
                message=f"{side.configuration_id!r} forbids battlefield capability {capability!r}.",
            ))
        for warning in side.diagnostic_warnings:
            issues.append(CompatibilityIssue(
                code="diagnostic_configuration",
                severity="diagnostic",
                message=f"{side.configuration_id}: {warning}",
            ))

    hero_positions, hero_role_issues = _role_positions(hero, deployment)
    monster_positions, monster_role_issues = _role_positions(monsters, deployment)
    issues.extend(hero_role_issues)
    issues.extend(monster_role_issues)
    active_positions = [*hero_positions.items(), *monster_positions.items()]
    positions_only = [position for _, position in active_positions]
    if len(positions_only) != len(set(positions_only)):
        issues.append(CompatibilityIssue(
            code="duplicate_spawn",
            severity="hard",
            message="Two active combatant roles resolve to the same spawn coordinate.",
        ))
    for role, position in active_positions:
        x, y = position
        if not (0 <= x < battlefield.width and 0 <= y < battlefield.height):
            issues.append(CompatibilityIssue(
                code="out_of_bounds_spawn",
                severity="hard",
                message=f"Role {role!r} resolves outside the battlefield bounds.",
                role=role,
                position=position,
            ))

    if not (
        hero.rating_eligible
        and hero.portable
        and monsters.rating_eligible
        and monsters.portable
        and battlefield.portable
        and deployment.portable
        and deployment.rating_eligible
    ):
        issues.append(CompatibilityIssue(
            code="diagnostic_context",
            severity="diagnostic",
            message="Composition contains a legacy or fixture-specific diagnostic component.",
        ))
    return CompatibilityReport(
        hero_configuration_id=hero.configuration_id,
        monster_configuration_id=monsters.configuration_id,
        battlefield_id=battlefield.battlefield_id,
        deployment_id=deployment.deployment_id,
        phase="static",
        issues=tuple(issues),
    )


def check_built_compatibility(
    static_report: CompatibilityReport,
    hero: SideConfigurationSpec,
    monsters: SideConfigurationSpec,
    deployment: DeploymentSpec,
    grid: GridMap,
) -> CompatibilityReport:
    """Extend static preflight with spawn occupancy and traversability checks."""
    issues = list(static_report.issues)
    if not static_report.admitted:
        return static_report.model_copy(update={"phase": "built"})
    hero_positions, monster_positions = resolve_deployment_positions(hero, monsters, deployment)
    active_positions = [*hero_positions.items(), *monster_positions.items()]
    for role, position in active_positions:
        if not grid.is_walkable_for(position[0], position[1]):
            issues.append(CompatibilityIssue(
                code="blocked_spawn",
                severity="hard",
                message=f"Role {role!r} resolves to a blocked spawn coordinate.",
                role=role,
                position=position,
            ))
        if grid.get_entities_at(position):
            issues.append(CompatibilityIssue(
                code="occupied_spawn",
                severity="hard",
                message=f"Role {role!r} resolves to an occupied spawn coordinate.",
                role=role,
                position=position,
            ))

    if hero_positions and monster_positions:
        traversable = any(
            grid.get_path(hero_position, monster_position) is not None
            for hero_position in hero_positions.values()
            for monster_position in monster_positions.values()
        )
        if not traversable:
            issues.append(CompatibilityIssue(
                code="unreachable_factions",
                severity="hard",
                message="No traversable relationship exists between the active faction spawn zones.",
            ))
    return static_report.model_copy(update={"phase": "built", "issues": tuple(issues)})
