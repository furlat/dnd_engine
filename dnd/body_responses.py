"""Configured injury responses installed by authored creature composition."""

from dataclasses import dataclass
from collections.abc import Mapping
from math import atan2, radians
from typing import Literal, cast
from uuid import UUID

from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.creature_types import DamageType
from dnd.core.events import DamageAppliedEvent, Event, EventHandler, EventPhase, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.core.geometry import supercover_line
from dnd.core.residue_geometry import ellipse_tiles, local_ellipse, place_ellipse
from dnd.entity import Entity
from dnd.residues import (
    BLOOD_RESIDUE, BONE_RESIDUE, CORROSIVE_RESIDUE, DREAD_RESIDUE,
    ResidueProfile, deposit_residue,
)
from dnd.types.residues import BodyReleaseRegion, BodyReleaseResult, ResidueEllipse
from dnd.types.world import OccupancyLayer


@dataclass(frozen=True, slots=True)
class BodyResponseProfile:
    release_id: str
    residue: ResidueProfile | None
    patterns: Mapping[str, tuple[ResidueEllipse, ...]]
    qualifying_damage_types: frozenset[DamageType] = frozenset(DamageType)
    deposition_layers: frozenset[OccupancyLayer] = frozenset({OccupancyLayer.GROUND})


RELEASE_PATTERNS: dict[str, tuple[ResidueEllipse, ...]] = {
    "piercing": (
        ResidueEllipse(center=(0, 0), radius_x=.27, radius_y=.27),
        ResidueEllipse(center=(.63, 0), radius_x=.57, radius_y=.20),
    ),
    "slashing": (
        ResidueEllipse(center=(0, 0), radius_x=.27, radius_y=.27),
        ResidueEllipse(center=(.52, .35), radius_x=.51, radius_y=.27, angle=radians(30)),
        ResidueEllipse(center=(.52, -.35), radius_x=.51, radius_y=.27, angle=radians(-30)),
    ),
    "blunt": (ResidueEllipse(center=(0, 0), radius_x=.49, radius_y=.49),),
}
BLOOD_RELEASE_PATTERNS: dict[str, tuple[ResidueEllipse, ...]] = {
    "piercing": (ResidueEllipse(center=(.45, 0), radius_x=2.25, radius_y=1.45),),
    "slashing": (ResidueEllipse(center=(.42, 0), radius_x=2.1, radius_y=1.6),),
    "blunt": (ResidueEllipse(center=(0, 0), radius_x=1.5, radius_y=1.5),),
}

BLOOD_BODY_RESPONSE = BodyResponseProfile("body.blood", BLOOD_RESIDUE, BLOOD_RELEASE_PATTERNS)
BONE_BODY_RESPONSE = BodyResponseProfile("body.bone", BONE_RESIDUE, RELEASE_PATTERNS)
CORROSIVE_BODY_RESPONSE = BodyResponseProfile("body.corrosive_blood", CORROSIVE_RESIDUE, RELEASE_PATTERNS)
DREAD_BODY_RESPONSE = BodyResponseProfile("body.dread_blood", DREAD_RESIDUE, RELEASE_PATTERNS)
PHYSICAL_PATTERNS: dict[DamageType, Literal["piercing", "slashing", "blunt"]] = {
    DamageType.PIERCING: "piercing", DamageType.SLASHING: "slashing", DamageType.BLUDGEONING: "blunt",
}


def receiving_regions(position: tuple[int, int], shapes: tuple[ResidueEllipse, ...], angle: float) -> tuple[BodyReleaseRegion, ...]:
    """Resolve authored floor pieces once through existing support and propagation."""
    grid = get_map()
    origin = grid.get_tile(*position)
    if origin is None:
        return ()
    admitted: dict[tuple[int, int], bool] = {}
    result = []
    for source in shapes:
        ellipse = place_ellipse(source, position, angle)
        positions = []
        for target in ellipse_tiles(ellipse):
            if target not in admitted:
                admitted[target] = all(
                    (tile := grid.get_tile(*cell)) is not None and tile.height == origin.height
                    for cell in supercover_line(position, target)
                ) and grid.raycast_clear(position, target, "propagation")
            if admitted[target]:
                positions.append(target)
        if positions:
            result.append(BodyReleaseRegion(ellipse=ellipse, positions=tuple(positions), elevation_steps=origin.height))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class BodyResponseProcessor:
    profile: BodyResponseProfile

    def __call__(self, event: Event, source_entity_uuid: UUID) -> Event:
        injury = cast(DamageAppliedEvent, event)
        resolution = injury.resolution
        if (
            injury.body_release is not None
            or resolution is None
            or resolution.effective_normal_hit_point_damage <= 0
            or not any(
                component.damage_type in self.profile.qualifying_damage_types
                and component.after_affinity_damage > 0
                for component in resolution.components
            )
        ):
            return event
        owner = Entity.get(source_entity_uuid)
        if owner is None:
            return event
        position = owner.position
        layer = owner.get_occupancy_layer()
        # A magical rider must not replace the wound pattern of its weapon.
        component = max((row for row in resolution.components
                         if row.damage_type in PHYSICAL_PATTERNS
                         and row.damage_type in self.profile.qualifying_damage_types
                         and row.after_affinity_damage > 0),
                        key=lambda row: row.after_affinity_damage, default=None)
        elemental = max((row for row in resolution.components
                         if row.damage_type not in PHYSICAL_PATTERNS
                         and row.damage_type in self.profile.qualifying_damage_types
                         and row.after_affinity_damage > 0),
                        key=lambda row: row.after_affinity_damage, default=None)
        primary = component or elemental
        direction = injury.impact_direction
        pattern = (PHYSICAL_PATTERNS[component.damage_type]
                   if component is not None and direction is not None and direction != (0, 0) else "blunt")
        angle = atan2(direction[1], direction[0]) if direction is not None else 0
        deposited_position = None
        regions: tuple[BodyReleaseRegion, ...] = ()
        if self.profile.residue is not None and layer in self.profile.deposition_layers:
            regions = receiving_regions(position, self.profile.patterns[pattern], angle)
            footprints: dict[tuple[int, int], list[ResidueEllipse]] = {}
            for region in regions:
                for destination in region.positions:
                    footprints.setdefault(destination, []).append(local_ellipse(region.ellipse, destination))
            deposited: set[tuple[int, int]] = set()
            for destination, ellipses in footprints.items():
                tile = get_map().get_tile(*destination)
                assert tile is not None
                if deposit_residue(tile, self.profile.residue, parent_event=event, ellipses=tuple(ellipses)) is not None:
                    deposited.add(destination)
            regions = tuple(BodyReleaseRegion(ellipse=region.ellipse, elevation_steps=region.elevation_steps,
                positions=tuple(cell for cell in region.positions if cell in deposited))
                for region in regions if any(cell in deposited for cell in region.positions))
            if position in deposited:
                deposited_position = position
        return injury.with_updates(body_release=BodyReleaseResult(
            release_id=self.profile.release_id, position=position,
            occupancy_layer=layer, deposited_position=deposited_position,
            pattern=pattern, critical_hit=injury.critical_hit, regions=regions,
            primary_damage_type=primary.damage_type if primary is not None else None,
            secondary_damage_type=elemental.damage_type if component is not None and elemental is not None else None,
        ))


class BodyResponseHandler(EventHandler):
    """One shared authored behavior identity for configured body responses."""


def install_body_response(entity: Entity, profile: BodyResponseProfile) -> None:
    """Compose one target-filtered body response through the existing owner."""
    key = "trait.body_response"
    if any(handler.semantic_key == key for handler in entity.event_handlers.values()):
        raise ValueError("The creature already has a configured body response")
    entity.add_event_handler(BodyResponseHandler(
        name="Body Response", semantic_key=key, content_kind=RuntimeBehaviorKind.TRAIT,
        source_entity_uuid=entity.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.DAMAGE_APPLIED, event_phase=EventPhase.EFFECT,
            event_target_entity_uuid=entity.uuid,
        )],
        event_processor=BodyResponseProcessor(profile),
    ))
