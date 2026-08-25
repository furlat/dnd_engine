"""Neutral static and built-map checks for direct authored encounters."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping

from dnd.content.scenarios.battlefield_definitions import BattlefieldDefinition
from dnd.content.scenarios.scenario_definitions import (
    EncounterCompatibilityCode,
    EncounterCompatibilityIssue,
    EncounterCompatibilityPhase,
    EncounterCompatibilityReport,
    EncounterCompatibilitySeverity,
    EncounterDefinition,
)
from dnd.core.gridmap import GridMap


ResolvedRosterPositions = dict[str, dict[str, tuple[int, int]]]


def resolve_encounter_positions(
    recipe: EncounterDefinition,
) -> tuple[
    ResolvedRosterPositions,
    tuple[EncounterCompatibilityIssue, ...],
]:
    """Resolve every member role through its selected neutral zone."""
    zones = {
        zone.zone_id: zone for zone in recipe.deployment.zones
    }
    resolved: ResolvedRosterPositions = {}
    issues: list[EncounterCompatibilityIssue] = []
    for roster_slot in recipe.roster_slots:
        zone = zones[roster_slot.deployment_zone_id]
        explicit = {
            role_slot.role: role_slot.position
            for role_slot in zone.role_slots
        }
        selected_roles = {
            member.deployment_role
            for member in roster_slot.roster.members
        }
        claimed_explicit_positions = {
            position
            for role, position in explicit.items()
            if role in selected_roles
        }
        fallback_positions = tuple(
            position
            for position in zone.ordered_slots
            if position not in claimed_explicit_positions
        )
        fallback_index = 0
        positions: dict[str, tuple[int, int]] = {}
        for member in roster_slot.roster.members:
            position = explicit.get(member.deployment_role)
            if position is None and fallback_index < len(fallback_positions):
                position = fallback_positions[fallback_index]
                fallback_index += 1
            if position is None:
                issues.append(EncounterCompatibilityIssue(
                    code=EncounterCompatibilityCode.MISSING_ROLE_SLOT,
                    severity=EncounterCompatibilitySeverity.HARD,
                    message=(
                        f"Deployment {recipe.deployment.deployment_id!r} "
                        f"has no slot for role "
                        f"{member.deployment_role!r}."
                    ),
                    roster_slot_id=roster_slot.roster_slot_id,
                    member_id=member.member_id,
                ))
                continue
            positions[member.member_id] = position
        resolved[roster_slot.roster_slot_id] = positions
    return resolved, tuple(issues)


def check_encounter_compatibility(
    recipe: EncounterDefinition,
    battlefield: BattlefieldDefinition,
) -> EncounterCompatibilityReport:
    """Run deterministic checks that do not construct engine state."""
    issues: list[EncounterCompatibilityIssue] = []
    if (
        recipe.battlefield_id != battlefield.battlefield_id
        or recipe.deployment.battlefield_id != battlefield.battlefield_id
    ):
        issues.append(EncounterCompatibilityIssue(
            code=EncounterCompatibilityCode.BATTLEFIELD_MISMATCH,
            severity=EncounterCompatibilitySeverity.HARD,
            message=(
                f"Encounter/deployment target "
                f"{recipe.battlefield_id!r}/"
                f"{recipe.deployment.battlefield_id!r}, not "
                f"{battlefield.battlefield_id!r}."
            ),
        ))

    capabilities = set(battlefield.capabilities)
    zones = {
        zone.zone_id: zone for zone in recipe.deployment.zones
    }
    for roster_slot in recipe.roster_slots:
        roster = roster_slot.roster
        zone = zones[roster_slot.deployment_zone_id]
        capacity = zone.max_members or len(zone.ordered_slots)
        if len(roster.members) > capacity:
            issues.append(EncounterCompatibilityIssue(
                code=EncounterCompatibilityCode.MEMBER_CAPACITY,
                severity=EncounterCompatibilitySeverity.HARD,
                message=(
                    f"Roster {roster_slot.roster_slot_id!r} has "
                    f"{len(roster.members)} members but zone "
                    f"{zone.zone_id!r} has capacity {capacity}."
                ),
                roster_slot_id=roster_slot.roster_slot_id,
            ))
        for capability in sorted(
            set(roster.required_battlefield_capabilities) - capabilities,
        ):
            issues.append(EncounterCompatibilityIssue(
                code=EncounterCompatibilityCode.MISSING_CAPABILITY,
                severity=EncounterCompatibilitySeverity.HARD,
                message=(
                    f"Roster {roster.roster_id!r} requires absent "
                    f"battlefield capability {capability!r}."
                ),
                roster_slot_id=roster_slot.roster_slot_id,
            ))
        for capability in sorted(
            set(roster.forbidden_battlefield_capabilities) & capabilities,
        ):
            issues.append(EncounterCompatibilityIssue(
                code=EncounterCompatibilityCode.FORBIDDEN_CAPABILITY,
                severity=EncounterCompatibilitySeverity.HARD,
                message=(
                    f"Roster {roster.roster_id!r} forbids battlefield "
                    f"capability {capability!r}."
                ),
                roster_slot_id=roster_slot.roster_slot_id,
            ))
    positions, position_issues = resolve_encounter_positions(recipe)
    issues.extend(position_issues)
    active_positions = [
        (
            roster_slot_id,
            member_id,
            position,
        )
        for roster_slot_id, member_positions in positions.items()
        for member_id, position in member_positions.items()
    ]
    coordinates = [row[2] for row in active_positions]
    if len(coordinates) != len(set(coordinates)):
        issues.append(EncounterCompatibilityIssue(
            code=EncounterCompatibilityCode.DUPLICATE_SPAWN,
            severity=EncounterCompatibilitySeverity.HARD,
            message="Two active encounter members share a spawn coordinate.",
        ))
    for roster_slot_id, member_id, position in active_positions:
        x, y = position
        if not (0 <= x < battlefield.width and 0 <= y < battlefield.height):
            issues.append(EncounterCompatibilityIssue(
                code=EncounterCompatibilityCode.OUT_OF_BOUNDS_SPAWN,
                severity=EncounterCompatibilitySeverity.HARD,
                message=(
                    f"Member {member_id!r} resolves outside the battlefield."
                ),
                roster_slot_id=roster_slot_id,
                member_id=member_id,
                position=position,
            ))
    return EncounterCompatibilityReport(
        encounter_id=recipe.encounter_id,
        battlefield_id=battlefield.battlefield_id,
        deployment_id=recipe.deployment.deployment_id,
        phase=EncounterCompatibilityPhase.STATIC,
        issues=tuple(issues),
        admitted=not any(
            issue.severity is EncounterCompatibilitySeverity.HARD
            for issue in issues
        ),
    )


def check_built_encounter_compatibility(
    static_report: EncounterCompatibilityReport,
    recipe: EncounterDefinition,
    grid: GridMap,
) -> EncounterCompatibilityReport:
    """Extend static preflight with occupancy and traversability checks."""
    if not static_report.admitted:
        return static_report.model_copy(update={
            "phase": EncounterCompatibilityPhase.BUILT,
        })
    issues = list(static_report.issues)
    positions, _ = resolve_encounter_positions(recipe)
    for roster_slot_id, member_positions in positions.items():
        for member_id, position in member_positions.items():
            if not grid.is_walkable_for(position[0], position[1]):
                issues.append(EncounterCompatibilityIssue(
                    code=EncounterCompatibilityCode.BLOCKED_SPAWN,
                    severity=EncounterCompatibilitySeverity.HARD,
                    message=(
                        f"Member {member_id!r} resolves to a blocked spawn."
                    ),
                    roster_slot_id=roster_slot_id,
                    member_id=member_id,
                    position=position,
                ))
            if grid.get_entities_at(position):
                issues.append(EncounterCompatibilityIssue(
                    code=EncounterCompatibilityCode.OCCUPIED_SPAWN,
                    severity=EncounterCompatibilitySeverity.HARD,
                    message=(
                        f"Member {member_id!r} resolves to an occupied spawn."
                    ),
                    roster_slot_id=roster_slot_id,
                    member_id=member_id,
                    position=position,
                ))

    if not _has_cross_faction_path(
        positions,
        {
            slot.roster_slot_id: slot.faction_id
            for slot in recipe.roster_slots
        },
        grid,
    ):
        issues.append(EncounterCompatibilityIssue(
            code=EncounterCompatibilityCode.UNREACHABLE_FACTIONS,
            severity=EncounterCompatibilitySeverity.HARD,
            message=(
                "No traversable relationship exists between hostile "
                "encounter factions."
            ),
        ))
    return static_report.model_copy(update={
        "phase": EncounterCompatibilityPhase.BUILT,
        "issues": tuple(issues),
        "admitted": not any(
            issue.severity is EncounterCompatibilitySeverity.HARD
            for issue in issues
        ),
    })


def _has_cross_faction_path(
    positions: Mapping[str, Mapping[str, tuple[int, int]]],
    faction_by_roster_slot: Mapping[str, str],
    grid: GridMap,
) -> bool:
    roster_slots = tuple(positions)
    hostile_pairs = tuple(
        (first, second)
        for index, first in enumerate(roster_slots)
        for second in roster_slots[index + 1:]
        if faction_by_roster_slot[first] != faction_by_roster_slot[second]
    )
    if not hostile_pairs:
        return True
    if any(
        grid.get_path(first_position, second_position) is not None
        for first, second in hostile_pairs
        for first_position in positions[first].values()
        for second_position in positions[second].values()
    ):
        return True
    return any(
        _has_interactable_topology_path(
            grid,
            first_position,
            second_position,
        )
        for first, second in hostile_pairs
        for first_position in positions[first].values()
        for second_position in positions[second].values()
    )


def _has_interactable_topology_path(
    grid: GridMap,
    start: tuple[int, int],
    end: tuple[int, int],
) -> bool:
    """Return connectivity through the public movement transition query."""
    if not grid.is_walkable(*start):
        return False
    pending = deque((start,))
    visited = {start}
    while pending:
        current = pending.popleft()
        if current == end:
            return True
        for dx, dy in (
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ):
            candidate = (current[0] + dx, current[1] + dy)
            if candidate in visited:
                continue
            if not grid.can_transition(
                current,
                candidate,
                treat_closed_doors_as_interactable=True,
            ):
                continue
            visited.add(candidate)
            pending.append(candidate)
    return False


__all__ = [
    "ResolvedRosterPositions",
    "check_built_encounter_compatibility",
    "check_encounter_compatibility",
    "resolve_encounter_positions",
]
