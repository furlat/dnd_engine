"""Solid wall spells: ordinary attackable sections and one native spatial owner."""

from math import ceil, hypot, isclose
from typing import ClassVar, Literal, Optional, Tuple
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.actions import Move, SpellAction, SpellEvent, commit_forced_movement, entity_action_economy_cost_evaluator
from dnd.blocks.base_item import BaseItem, WorldItem, PreparedItemRetirement
from dnd.core.action_types import ActionSelection, ActionVariantFacet, PositionPathSelection, PositionSelection, SinglePositionSelection, selection_facet
from dnd.core.base_actions import Cost, TargetType
from dnd.core.base_block import BaseBlock, resolution_order_key
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import ConditionTag, DurationType
from dnd.core.content.identities import ContentRef
from dnd.core.creature_types import DamageType, Size
from dnd.spells.spell_utils import condition_save
from dnd.types.spell_suppression import SpellSuppression
from dnd.core.effect_types import ObjectSectionVolume
from dnd.core.events import Event, EventHandler, EventType, Trigger, PortalTransferEvent, EventPhase, EventQueue, ForcedMovementEvent, ItemDestructionEvent, Range, RangeType, SpatialChangeEvent
from dnd.core.gridmap import CrossingChannel, get_map
from dnd.core.navigation import route, route_costs
from dnd.core.item_types import ItemPresentationState
from dnd.core.life_types import RemainsDisposition
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallDome, WallPolyline, WallRing, WallSegment
from dnd.core.wall_geometry import wall_crosses_path, wall_path_contact, wall_shell_cells
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition, SpatialCondition
from dnd.spells.wall_fields import WallDamageSpec, WallFieldZone, apply_wall_damage, selection_wall_support_error, wall_condition_ref
from dnd.types.discovery import ActorScan, ScanRecord
from dnd.types.event_facts import GroupEntryKind
from dnd.types.materials import Material
from dnd.types.physical_access import PhysicalAccess
from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.spatial_effects import SpatialEffectChangeOperation, SpatialEffectLayer, SpatialEffectOccupancyPolicy, SpatialEffectTriggerKind
from dnd.types.summoning import TerminalOwnerRelease
from dnd.types.world import MovementMode, WorldEdgeChannel
from dnd.types.world_placement import WorldPlacementKind, WorldPlacementSpec
from dnd.conditions import Prone
from dnd.core.values import Channel, Kind, add_modifier


class FrigidAirZone(WallFieldZone):
    section_positions: frozenset[tuple[int, int]] | None = None
    name: str = "Frigid Air"
    description: str = "Passing through the former ice sheet causes cold damage once per turn."
    content_ref: ContentRef = wall_condition_ref("spatial_effect.spell.frigid_air")
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.ENTER})
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.ENTER})
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.PERMANENT))

    def resolve_condition_footprint(self) -> set[tuple[int, int]]:
        footprint = super().resolve_condition_footprint()
        return footprint & self.section_positions if self.section_positions is not None else footprint

    def admits_occupancy_transition(self, event: SpatialChangeEvent) -> bool:
        return (SpatialCondition.admits_occupancy_transition(self, event)
            and event.old_position is not None
            and wall_path_contact(self.geometry, event.old_position, event.position,
                {cell for cell in self.affected_positions if self.allows_contribution_at(cell)}) is not None)

    def _occupancy_admits_trigger(self, kind, target_entity_uuid, event) -> bool:
        if isinstance(event, SpatialChangeEvent) and kind is SpatialEffectTriggerKind.ENTER:
            return self.admits_occupancy_transition(event)
        return super()._occupancy_admits_trigger(kind, target_entity_uuid, event)

    def get_trigger_positions(self, kind) -> set[tuple[int, int]]:
        # The indexed ENTER event is dispatched at its destination. Include
        # adjacent endpoints so a shell-to-interior crossing reaches admission.
        return { (x + dx, y + dy) for x, y in self.affected_positions
                 for dx in (-1, 0, 1) for dy in (-1, 0, 1) }

    def damage_contact_position(self, event: SpatialChangeEvent, entity: Entity) -> tuple[int, int]:
        contact = (wall_path_contact(self.geometry, event.old_position, event.position,
                {cell for cell in self.affected_positions if self.allows_contribution_at(cell)})
                   if event.old_position is not None else None)
        return (min(self.affected_positions, key=lambda p: hypot(p[0] - contact[0], p[1] - contact[1]))
                if contact is not None else entity.position)


class WallSection(WorldItem):
    """One physical health identity, independent of its owning spell condition."""

    wall_owner_uuid: UUID
    geometry: WallAssemblyPresentationGeometry
    magical_force: bool = False
    force_owner_disintegration: Literal["whole", "section"] = "whole"
    is_pickable: bool = False
    is_targetable: bool = True
    blocks_movement: bool = False
    blocks_optics_field: bool = False
    blocks_propagation_field: bool = False
    tags: list[str] = Field(default_factory=lambda: ["spell_construction"])
    known_to_creator: bool = True
    _break_event: Event | None = PrivateAttr(default=None)

    def to_item_presentation_state(self, *, stack_count: int | None = None) -> ItemPresentationState:
        owner = BaseCondition.get(self.wall_owner_uuid)
        return super().to_item_presentation_state(stack_count=stack_count).model_copy(
            update={"construction_owner_uuid": self.wall_owner_uuid, "construction_geometry": self.geometry,
                "construction_suppressions": owner.spatial_suppressions if isinstance(owner, BaseCondition) else (),
                "known_to_creator": self.known_to_creator})

    def _on_destroy(self, parent_event: Event | None) -> None:
        self._break_event = parent_event

    def permits_terminal_retirement(self, release: TerminalOwnerRelease) -> bool:
        owner = BaseCondition.get(self.wall_owner_uuid)
        if not isinstance(owner, SolidWallZone) or self.uuid not in owner.sections or owner.parent_link is None:
            return False
        parent_owner, parent_uuid = owner.parent_link
        parent = BaseCondition.get(parent_uuid)
        return (owner.applied and owner.source_entity_uuid == release.entity_uuid
            and parent_owner == release.entity_uuid and isinstance(parent, BaseCondition)
            and parent.source_entity_uuid == release.entity_uuid
            and (owner.uuid, owner.uuid) in parent.linked_conditions
            and BaseBlock.prepared_condition_terminal_release(parent.uuid) == release)

    def retire(self, parent_event: Event | None = None) -> bool:
        accepted = super().retire(parent_event)
        if BaseBlock.get(self.uuid) is None and self._break_event is not None:
            owner = BaseCondition.get(self.wall_owner_uuid)
            if isinstance(owner, SolidWallZone) and owner.applied:
                owner.on_section_destroyed(self.uuid, self._break_event)
            self._break_event = None
        return accepted

    def disintegrate(self, parent_event: Event) -> bool:
        owner = BaseCondition.get(self.wall_owner_uuid)
        if self.magical_force and self.force_owner_disintegration == "whole":
            if not isinstance(owner, SolidWallZone):
                return False
            event = ItemDestructionEvent(source_entity_uuid=parent_event.source_entity_uuid,
                target_entity_uuid=self.uuid, item_uuid=self.uuid,
                previous_state=self.to_item_presentation_state(),
                previous_placement=get_map().get_object_placement(self.uuid),
                remains_disposition=RemainsDisposition.DISINTEGRATED,
                destroyed_item_uuids=tuple(owner.sections), parent_event=parent_event.uuid)
            event = event.phase_to(EventPhase.EXECUTION)
            if not event.canceled:
                event = event.phase_to(EventPhase.EFFECT)
            if event.canceled:
                return False
            if not owner.deactivate(parent_event=event):
                event.cancel(status_message="Force creation removal was refused")
                return False
            event.phase_to(EventPhase.COMPLETION)
            return True
        volume = self.disintegration_volume(parent_event)
        if volume is not None:
            return self.disintegrate_section(volume, parent_event)
        prepared = self.prepare_retirement(parent_event)
        if prepared is None:
            return False
        event = self.commit_disintegration(prepared)
        if isinstance(owner, SolidWallZone) and owner.applied:
            owner.on_section_destroyed(self.uuid, event)
        return BaseBlock.get(self.uuid) is None

    def disintegration_volume(self, parent_event: Event) -> ObjectSectionVolume | None:
        path = self.geometry.path
        if (not self.geometry.removed_sections and isinstance(path, WallSegment)
                and hypot(path.end[0] - path.start[0], path.end[1] - path.start[1]) <= 2
                and self.geometry.height_feet <= 10):
            return None
        return super().disintegration_volume(parent_event)

    def on_object_section_removed(self, volume: ObjectSectionVolume, parent_event: Event) -> None:
        previous = self.geometry
        self.geometry = self.geometry.model_copy(update={
            "removed_sections": (*self.geometry.removed_sections, volume)})
        owner = BaseCondition.get(self.wall_owner_uuid)
        if isinstance(owner, SolidWallZone) and owner.applied:
            owner.sections[self.uuid] = self.geometry
            get_map().spatial_condition_changed(owner)
            change = owner._open_change(SpatialEffectChangeOperation.STATE_CHANGED,
                previous_positions=set(owner.affected_positions), affected_positions=set(owner.affected_positions),
                parent_event=parent_event)
            if owner.material == "ice":
                positions = {position for position in wall_shell_cells(previous)
                    if volume.contains_band(position, previous.base_height_steps)} & owner.affected_positions
                owner.leave_frigid_air(previous, positions, change)
            owner._complete_change(change)

    def disintegration_error(self) -> str | None:
        return None if get_map().get_object_placement(self.uuid) is not None else "Wall section is absent"


class SolidWallZone(AreaCondition):
    """Ownership links and exact shell crossings, without a filled-volume blocker."""
    creates = (FrigidAirZone, Move, Prone)

    crossing_channels: ClassVar[frozenset[CrossingChannel] | None] = frozenset({
        WorldEdgeChannel.MOVEMENT, WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION})

    geometry: WallAssemblyPresentationGeometry
    material: Literal["ice", "stone", "force"]
    sections: dict[UUID, WallAssemblyPresentationGeometry] = Field(default_factory=dict)
    spell_dc: int
    residual_dice_count: int = 5
    permanent: bool = False
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    duration: Duration = Field(default_factory=lambda: Duration(duration=100, duration_type=DurationType.ROUNDS))
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    _prepared_retirements: tuple[PreparedItemRetirement, ...] = PrivateAttr(default=())

    _pending_sections: tuple[tuple[WallSection, tuple[int, int]], ...] = PrivateAttr(default=())
    _formation_displacements: dict[UUID, tuple[int, int]] = PrivateAttr(default={})

    def _commit_activation_footprint(self, parent_event: Event) -> None:
        """Commit real sections before CREATED can disclose the construction."""
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            raise ValueError("Construction caster no longer exists")
        for identity, destination in self._formation_displacements.items():
            entity = Entity.get(identity)
            if entity is not None and not move_displaced(entity, destination, caster, parent_event):
                raise ValueError("Formation displacement was canceled")
        placements = get_map().place_object_sections(
            tuple((item.uuid, anchor) for item, anchor in self._pending_sections), parent_event=parent_event.uuid)
        for (item, _), placement in zip(self._pending_sections, placements, strict=True):
            item.synchronize_floor_placement(placement)
            self.sections[item.uuid] = item.geometry
        super()._commit_activation_footprint(parent_event)
        self._pending_sections = ()
        self._formation_displacements.clear()

    def resolve_condition_footprint(self) -> set[tuple[int, int]]:
        return self._apply_spell_protection({p for p in wall_shell_cells(self.geometry) if get_map().has_tile(*p)})



    def blocks_crossing_between(self, start, end, channel, requester_uuid, mode,
                                terminal_provider_uuid=None) -> bool:
        if channel is WorldEdgeChannel.OPTICAL and self.material != "stone":
            return False
        if channel is WorldEdgeChannel.MOVEMENT and mode is MovementMode.BURROWING and self.material != "force":
            return False
        admitted = {p for p in self.affected_positions if self.allows_contribution_at(p)}
        return any(identity != terminal_provider_uuid and wall_path_contact(geometry, start, end, admitted) is not None
                   for identity, geometry in self.sections.items())

    def blocks_physical_optics_at(self, position: tuple[int, int]) -> bool:
        return self.material == "stone" and self.allows_contribution_at(position) and any(position in wall_shell_cells(g) for g in self.sections.values())

    def get_spatial_observation(self, positions: set[tuple[int, int]], *, observer_uuid) -> PerceivedSpatialEffect | None:
        live = set().union(*(wall_shell_cells(g) for g in self.sections.values())) if self.sections else set()
        observed = SpatialCondition.get_spatial_observation(self, positions & live,
            observer_uuid=observer_uuid)
        return observed.model_copy(update={"area_geometry": self.geometry,
            "construction_sections": tuple(g for g in self.sections.values() if wall_shell_cells(g) & positions),
            "anchor_elevation_steps": self.geometry.base_height_steps}) if observed is not None else None

    def on_section_destroyed(self, identity: UUID, parent_event: Event) -> None:
        geometry = self.sections.pop(identity, None)
        if geometry is None:
            return
        get_map().spatial_condition_changed(self)
        change = self._open_change(SpatialEffectChangeOperation.STATE_CHANGED,
            previous_positions=set(self.affected_positions), affected_positions=set(self.affected_positions),
            parent_event=parent_event)
        if self.material == "ice":
            positions = wall_shell_cells(geometry) & self.affected_positions
            if not positions:
                self._complete_change(change)
                return
            self.leave_frigid_air(geometry, positions, change)
        self._complete_change(change)

    def leave_frigid_air(self, geometry: WallAssemblyPresentationGeometry,
                         positions: set[tuple[int, int]], parent_event: Event) -> None:
        """The existing cold remnant owns only the section actually destroyed."""
        if not positions:
            return
        air = FrigidAirZone(source_entity_uuid=self.source_entity_uuid, position=min(positions),
            geometry=geometry, affected_positions=positions, section_positions=frozenset(positions), spell_dc=self.spell_dc,
            contact_damage=WallDamageSpec(dice_count=self.residual_dice_count, die=6,
                damage_type=DamageType.COLD, save_ability="constitution", effect_id="wall_of_ice.frigid_air"),
            effect_origin=self.effect_origin)
        result = air.activate(parent_event=parent_event)
        if result is not None and not result.canceled and air.applied:
            self.add_linked_condition(air.uuid, air.uuid)

    def publish_removal_effect(self, declaration_event: Event) -> Event:
        effect = super().publish_removal_effect(declaration_event)
        if effect.canceled:
            return effect
        return self._prepare_section_retirements(effect)

    def prepare_removal_state(self, event: Event) -> Event:
        event = super().prepare_removal_state(event)
        release = (BaseBlock.prepared_condition_terminal_release(self.parent_link[1])
            if self.parent_link is not None else None)
        return self._prepare_section_retirements(event, release) if release is not None else event

    def _prepare_section_retirements(self, effect: Event,
            release: TerminalOwnerRelease | None = None) -> Event:
        try:
            for identity in self.sections:
                item = BaseBlock.get(identity)
                retirement = item.prepare_retirement(effect, terminal_release=release) if isinstance(item, BaseItem) else None
                if retirement is None:
                    self.cancel_prepared_removal("A wall section refused retirement")
                    return effect.cancel(status_message="A wall section refused retirement")
                self._prepared_retirements = (*self._prepared_retirements, retirement)
        except BaseException as failure:
            try:
                self.cancel_prepared_removal("Wall retirement admission raised")
            except BaseException as cleanup:
                raise BaseExceptionGroup("Wall retirement admission and cancellation failed", [failure, cleanup]) from failure
            raise
        return effect

    def cancel_prepared_removal(self, reason: str) -> None:
        pending = self._prepared_retirements
        self._prepared_retirements = ()
        errors: list[BaseException] = []
        for prepared in pending:
            try:
                prepared.item.cancel_retirement(prepared)
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("Wall retirement cancellation failed", errors)

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        if self.sections and not self._prepared_retirements:
            if self._removal_publication is not None:
                raise RuntimeError("Wall retirement requires admitted section cleanup")
            # Failed formation has no accepted removal graph. Preserve its
            # ordinary cleanup route; prepared replacement never enters here.
            for identity in tuple(self.sections):
                item = BaseBlock.get(identity)
                if isinstance(item, WallSection):
                    item._break_event = None
                if isinstance(item, BaseItem) and not item.retire(parent_event):
                    raise RuntimeError("Wall section could not release its native owner")
        for prepared in self._prepared_retirements:
            item = prepared.item
            if isinstance(item, WallSection):
                # Expiry/concentration removal never completes a deferred break
                # or admits a new child after the removal graph was preflighted.
                item._break_event = None
            item.commit_retirement(prepared, publish=False)
        self.sections.clear()
        super()._release_owned_runtime_state(parent_event=parent_event)
        changed = get_map().recompute_lights_at_positions(set(self.affected_positions),
            parent_event=parent_event.uuid if parent_event is not None else None, publish=False)
        light = get_map().snapshot_light_change(list(changed),
            parent_event=parent_event.uuid if parent_event is not None else None)
        if light is not None and self._removal_publication is not None:
            self._removal_publication.light_changes.append(light)

    def publish_runtime_owner_removal(self, effect: Event) -> None:
        errors: list[BaseException] = []
        for prepared in self._prepared_retirements:
            try:
                prepared.item.publish_retirement(prepared)
            except BaseException as error:
                errors.append(error)
        try:
            super().publish_runtime_owner_removal(effect)
        except BaseException as error:
            errors.append(error)
        if errors:
            raise BaseExceptionGroup("Committed wall removal publication failed", errors)

    def progress(self) -> bool:
        if self.material == "stone" and not self.permanent and self.duration.duration == 1:
            change = self._open_change(SpatialEffectChangeOperation.STATE_CHANGED,
                previous_positions=set(self.affected_positions), affected_positions=set(self.affected_positions),
                parent_event=None)
            self.permanent = True
            self.duration.duration_type = DurationType.PERMANENT
            self.duration.duration = None
            if self.parent_link is not None:
                parent = BaseCondition.get(self.parent_link[1])
                if isinstance(parent, BaseCondition):
                    parent.unlink_condition(self.uuid, parent_event=change)
                    parent.publish_owner_state(change)
                self.parent_link = None
            self.tags.discard(ConditionTag.MAGICAL)
            self._complete_change(change)
            return False
        return super().progress()


class WallOfIceZone(SolidWallZone):
    name: str = "Wall of Ice"
    description: str = "See-through solid ice; destroyed sheets leave frigid air."
    content_ref: ContentRef = wall_condition_ref("spatial_effect.spell.wall_of_ice")
    material: Literal["ice", "stone", "force"] = "ice"
    has_visible_presence: bool = True


class WallOfStoneZone(SolidWallZone):
    name: str = "Wall of Stone"
    description: str = "Supported stone sections become permanent after full concentration."
    content_ref: ContentRef = wall_condition_ref("spatial_effect.spell.wall_of_stone")
    material: Literal["ice", "stone", "force"] = "stone"
    has_visible_presence: bool = True
    blocks_physical_optics: bool = True


class WallOfForceZone(SolidWallZone):
    name: str = "Wall of Force"
    description: str = "Invisible physical obstruction, destroyed completely by Disintegrate."
    content_ref: ContentRef = wall_condition_ref("spatial_effect.spell.wall_of_force")
    material: Literal["ice", "stone", "force"] = "force"
    has_visible_presence: bool = False


def construction_sections(geometry: WallAssemblyPresentationGeometry, panel_width_feet: int = 10) -> tuple[WallAssemblyPresentationGeometry, ...] | None:
    if isinstance(geometry.path, WallDome):
        return (geometry,)
    if isinstance(geometry.path, WallRing):
        return None
    points = geometry.path.points if isinstance(geometry.path, WallPolyline) else (geometry.path.start, geometry.path.end)
    result = []
    for first, last in zip(points, points[1:]):
        length = hypot(last[0] - first[0], last[1] - first[1])
        panel_cells = panel_width_feet / 5
        count = round(length / panel_cells)
        if count < 1 or not isclose(length, count * panel_cells, abs_tol=1e-6):
            return None
        for i in range(count):
            start = (first[0] + (last[0] - first[0]) * i / count,
                     first[1] + (last[1] - first[1]) * i / count)
            end = (first[0] + (last[0] - first[0]) * (i + 1) / count,
                   first[1] + (last[1] - first[1]) * (i + 1) / count)
            result.append(geometry.model_copy(update={"path": WallSegment(start=start, end=end)}))
    return tuple(result) if len(result) <= 10 else None


def displacement_plan(caster: Entity, geometry: WallAssemblyPresentationGeometry,
                      *, side: str, subjective: bool = False) -> dict[UUID, tuple[int, int]] | None:
    grid = get_map()
    shell = wall_shell_cells(geometry)
    occupants = {identity for position in shell for identity in grid.get_entities_at(position)}
    if subjective:
        occupants = {identity for identity in occupants
                     if identity == caster.uuid or identity in caster.senses.entities}
    used: set[tuple[int, int]] = set()
    result = {}
    path = geometry.path
    if isinstance(path, WallRing):
        return None
    # The path's segments with their shells, rasterized once per plan, on the first side test.
    segment_shells: list[tuple[WallSegment, set[tuple[int, int]]]] | None = None
    for identity in sorted(occupants, key=str):
        entity = Entity.get(identity)
        if entity is None:
            continue
        entity_position = entity.position
        # The segment the occupant is displaced across, chosen on its first side test.
        segment: WallSegment | None = None
        candidates = []
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx != 0 and dy != 0:
                    continue
                position = (entity.position[0] + dx, entity.position[1] + dy)
                tile = grid.get_tile(*position)
                if (position in shell or position in used or tile is None
                        or tile.height != geometry.base_height_steps
                        or not grid.is_walkable_for(*position, entity.uuid)
                        or not grid.can_reach_between(entity.position, position, PhysicalAccess.BODY, entity.uuid)):
                    continue
                if isinstance(path, WallDome):
                    chosen = hypot(position[0] - path.center[0], position[1] - path.center[1]) < path.radius_feet / 5
                    if chosen != (side == "inside"):
                        continue
                else:
                    if segment is None:
                        if segment_shells is None:
                            segment_shells = [(part, wall_shell_cells(geometry.model_copy(update={"path": part})))
                                              for part in ([WallSegment(start=a, end=b)
                                                            for a, b in zip(path.points, path.points[1:])]
                                                           if isinstance(path, WallPolyline) else [path])]
                        # The nearest by midpoint among the segments whose shell holds the occupant, else all.
                        segments = ([part for part, cells in segment_shells if entity_position in cells]
                                    or [part for part, _ in segment_shells])
                        segment = min(segments, key=lambda s: hypot(
                            (s.start[0] + s.end[0]) / 2 - entity_position[0],
                            (s.start[1] + s.end[1]) / 2 - entity_position[1]))
                    cross = ((segment.end[0] - segment.start[0]) * (position[1] - segment.start[1])
                             - (segment.end[1] - segment.start[1]) * (position[0] - segment.start[0]))
                    if (cross > 0) != (side == "left"):
                        continue
                # Keep the existing subjective reach check above. New occupancy
                # checks use the chooser's perception; execution also checks each
                # actual ground step, without exposing hidden blockers in Preview.
                step = (0 if dx == 0 else 1 if dx > 0 else -1,
                        0 if dy == 0 else 1 if dy > 0 else -1)
                previous = entity_position
                for _ in range(max(abs(dx), abs(dy))):
                    reached = (previous[0] + step[0], previous[1] + step[1])
                    if (reached in used or not entity.can_end_movement_at(
                            reached, subjective=subjective, observer=caster)
                            or not subjective and not grid.can_transition(previous, reached, entity.uuid)):
                        break
                    previous = reached
                if previous != position:
                    continue
                candidates.append(position)
        if not candidates:
            return None
        start_position = entity.position
        destination = min(candidates, key=lambda p: (hypot(p[0] - start_position[0], p[1] - start_position[1]), p))
        used.add(destination)
        result[identity] = destination
    return result


def move_displaced(entity: Entity, destination: tuple[int, int], caster: Entity,
                   parent_event: Event) -> bool:
    start = entity.position
    distance = max(abs(destination[0] - start[0]), abs(destination[1] - start[1])) * 5
    direction = (0 if destination[0] == start[0] else 1 if destination[0] > start[0] else -1,
                 0 if destination[1] == start[1] else 1 if destination[1] > start[1] else -1)
    event = EventQueue.publish_declaration(ForcedMovementEvent(source_entity_uuid=caster.uuid,
        target_entity_uuid=entity.uuid, source_entity_name=caster.name, target_entity_name=entity.name,
        start_position=start, end_position=destination,
        direction=direction,
        intended_distance=distance, actual_distance=distance, cause="wall_formation",
        parent_event=parent_event.uuid, use_register=False))
    for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
        if event.canceled:
            return False
        event = event.phase_to(phase)
    if event.canceled:
        return False
    commit_forced_movement(entity, event, parent_event=parent_event)
    return entity.position == destination


def stone_enclosure_escapes(caster: Entity, geometry: WallAssemblyPresentationGeometry,
                           dc: int, parent_event: Event,
                           displacements: dict[UUID, tuple[int, int]]) -> None:
    """Proposed barriers identify enclosure; accepted reactions use ordinary steps."""
    grid = get_map()
    shell = wall_shell_cells(geometry)
    min_x, max_x = min(p[0] for p in shell), max(p[0] for p in shell)
    min_y, max_y = min(p[1] for p in shell), max(p[1] for p in shell)
    # Displaced creatures stand on shell cells, inside the box; the formation group fixes the order (plan §5.3).
    for entity in sorted(map(Entity.get, grid.get_entities_in_bounds((min_x, min_y, max_x, max_y))),
                         key=resolution_order_key):
        start = displacements.get(entity.uuid, entity.position)
        if not min_x <= start[0] <= max_x or not min_y <= start[1] <= max_y:
            continue
        visited = {start}
        pending = [start]
        enclosed = True
        while pending:
            position = pending.pop()
            if not (min_x <= position[0] <= max_x and min_y <= position[1] <= max_y):
                enclosed = False
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
                neighbor = position[0] + dx, position[1] + dy
                if (neighbor not in visited and grid.can_transition(position, neighbor, entity.uuid)
                        and not wall_crosses_path(geometry, position, neighbor)):
                    visited.add(neighbor)
                    pending.append(neighbor)
        if not enclosed or entity.action_economy.reactions.normalized_score < 1:
            continue
        request = caster.create_saving_throw_request(target_entity_uuid=entity.uuid,
            ability_name="dexterity", dc=dc, parent_event=parent_event.uuid)
        _, _, success = entity.saving_throw(request)
        if not success:
            continue
        speed = entity.action_economy.current_speed()
        reached = grid.compute_paths(entity.position, requesting_entity_uuid=entity.uuid,
            max_distance=ceil(speed / 5), subjective=True)
        costs = dict(route_costs(reached))
        exits = [p for p in costs if (p[0] < min_x or p[0] > max_x or p[1] < min_y or p[1] > max_y)
                 and costs[p] <= speed]
        if not exits:
            continue
        destination = min(exits, key=lambda p: (costs[p], p))
        escape = Move(name="Escape forming wall", source_entity_uuid=entity.uuid, end_position=destination,
            path=route(reached, destination), use_movement_cost=False, movement_allowance_feet=speed,
            costs=[Cost(name="Wall enclosure escape", cost_type="reactions", cost=1,
                        evaluator=entity_action_economy_cost_evaluator)])
        entity.perform(escape, escape.current_selection(), parent_event=parent_event)


class ConstructWall(SpellAction):
    """Concrete shared placement composer, configured by native spell data."""
    creates = (*SpellAction.creates, WallOfIceZone, WallOfStoneZone, WallOfForceZone, Move)

    construction_material: Literal["ice", "stone", "force"]
    concentration: bool = True
    harmful: bool = True
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=120))
    target_type: TargetType = TargetType.POSITION_LOS
    physical_access: PhysicalAccess = PhysicalAccess.PROJECTILE
    wall_form: Literal["panels", "dome"] = "panels"
    dome_radius_feet: Literal[5, 10] = 10
    displacement_side: Literal["left", "right", "inside", "outside"] = "left"
    stone_panel_width_feet: Literal[10, 20] = 10
    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Wall construction action", cost_type="actions",
        cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def get_position_selection(self) -> PositionSelection:
        return (SinglePositionSelection() if self.wall_form == "dome" else PositionPathSelection(
            max_length_feet=200 if self.construction_material == "stone" else 100,
            max_segments=10 if self.construction_material == "stone" else 1,
            allow_origin_start=True, origin_start_offset_cells=1))

    def wall_geometry(self) -> WallAssemblyPresentationGeometry | None:
        return self._wall_geometry(self.current_selection())

    def _wall_geometry(self, selection: ActionSelection) -> WallAssemblyPresentationGeometry | None:
        if not selection.positions:
            return None
        end_position = selection.positions[0]
        points = self._selected_position_path(selection)
        if points is not None and any(a == b for a, b in zip(points, points[1:])):
            return None
        if self.wall_form == "dome":
            path = WallDome(center=end_position, radius_feet=self.dome_radius_feet)
            anchor = end_position
        elif points is not None and len(points) >= 2:
            path = WallPolyline(points=tuple(points)) if self.construction_material == "stone" else WallSegment(start=points[0], end=points[-1])
            anchor = points[0]
        else:
            return None
        tile = get_map().get_tile(*anchor)
        width = {"ice": 1., "stone": .5 if self.stone_panel_width_feet == 10 else .25, "force": 1 / 48}[self.construction_material]
        return WallAssemblyPresentationGeometry(path=path, base_height_steps=tile.height,
            width_feet=width, height_feet=self.dome_radius_feet if self.wall_form == "dome" else 10) if tile is not None else None

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        """Panels pushing left or right (stone: 10 or 20 ft panels); a non-stone dome of 5 or 10 ft pushing in or out."""
        form = lambda value: ActionVariantFacet(key="form", value=value, label=value.title())
        panels = tuple((form("panels"), ActionVariantFacet(key="side", value=side, label=f"Push {side}"),
                        *((ActionVariantFacet(key="width", value=str(width), label=f"{width} ft panels"),)
                          if self.construction_material == "stone" else ()))
                       for width in ((10, 20) if self.construction_material == "stone" else (10,))
                       for side in ("left", "right"))
        domes = () if self.construction_material == "stone" else tuple(
            (form("dome"), ActionVariantFacet(key="side", value=side, label=f"Push {side}"),
             ActionVariantFacet(key="radius", value=str(radius), label=f"{radius} ft radius"))
            for radius in (5, 10) for side in ("inside", "outside"))
        return (*panels, *domes)

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        chosen = {facet.key: facet.value for facet in selection.facets}
        overrides = {**super()._selection_overrides(selection), "wall_form": selection_facet(selection, "form"),
                     "displacement_side": selection_facet(selection, "side")}
        if overrides["wall_form"] == "dome":
            overrides["dome_radius_feet"] = int(selection_facet(selection, "radius"))
        else:
            overrides["stone_panel_width_feet"] = int(chosen.get("width", "10"))
        return overrides

    def get_selection_geometry(self):
        return self.wall_geometry()

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        return self._placement_error(selection, subjective=scan.subjective)

    def _placement_error(self, selection: ActionSelection, *, subjective: bool) -> str | None:
        geometry = self._wall_geometry(selection)
        error = selection_wall_support_error(self, selection, geometry, subjective=subjective)
        if error is not None or geometry is None:
            return error
        if self.construction_material == "stone" and self.wall_form == "dome":
            return "Stone uses supported connected panels, not a dome"
        legal_sides = {"inside", "outside"} if self.wall_form == "dome" else {"left", "right"}
        if self.displacement_side not in legal_sides:
            return "Displacement side does not match the selected wall form"
        if self.wall_form == "panels" and self.construction_material in {"ice", "stone"}:
            path = geometry.path
            points = path.points if isinstance(path, WallPolyline) else (
                (path.start, path.end) if isinstance(path, WallSegment) else ())
            if any(a[0] != b[0] and a[1] != b[1] for a, b in zip(points, points[1:])):
                return "Ice and Stone sections use the four grid directions"
        sections = construction_sections(geometry, self.stone_panel_width_feet if self.construction_material == "stone" else 10)
        if sections is None:
            return "Select contiguous complete ten-foot panels, at most ten"
        if self.construction_material == "stone":
            # This bounded vertical lane is merged into existing stone support;
            # it does not claim unsupported spans, bridges or ramps.
            if any((tile := get_map().get_tile(*p)) is None
                   or tile.surface.base_material is not Material.STONE for p in wall_shell_cells(geometry)):
                return "Stone panels require existing stone support"
        caster = Entity.get(self.source_entity_uuid)
        if caster is None or displacement_plan(caster, geometry,
                side=self.displacement_side, subjective=subjective) is None:
            return "No free supported side for displaced creatures"
        return None

    def _create_declaration_event(self, parent_event=None, use_register=True) -> Event | None:
        event = super()._create_declaration_event(parent_event, use_register)
        return event.with_updates(area_geometry=self.wall_geometry()) if isinstance(event, SpellEvent) else event

    def _apply(self, execution_event: SpellEvent) -> SpellEvent | None:
        caster = Entity.get(self.source_entity_uuid)
        geometry = self.wall_geometry()
        if caster is None or geometry is None:
            return execution_event.cancel(status_message="Wall construction unavailable")
        sections = construction_sections(geometry, self.stone_panel_width_feet if self.construction_material == "stone" else 10)
        displacements = displacement_plan(caster, geometry, side=self.displacement_side)
        if sections is None or displacements is None:
            return execution_event.cancel(status_message="Wall placement changed before formation")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        # Escapes, displacement, sections and appearance damage are one formation
        # instant; observers settle once when it closes (plan §5.2).
        with EventQueue.group(GroupEntryKind.WALL_FORMATION, root=effect, shares_damage_rolls=True):
            dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
            if self.construction_material == "stone":
                stone_enclosure_escapes(caster, geometry, dc, effect, displacements)
                displacements = displacement_plan(caster, geometry, side=self.displacement_side)
                if displacements is None:
                    return effect.cancel(status_message="No supported formation displacement remains")
            formation_contacts = {identity: entity.position for identity in displacements
                                  if (entity := Entity.get(identity)) is not None}
            zone_type = {"ice": WallOfIceZone, "stone": WallOfStoneZone, "force": WallOfForceZone}[self.construction_material]
            zone = zone_type(source_entity_uuid=caster.uuid, position=self.end_position,
                geometry=geometry, spell_dc=dc,
                residual_dice_count=5 + max(0, self.cast_at_level - 6), effect_origin=execution_event.to_effect_origin())
            pending = []
            grid = get_map()
            try:
                for section in sections:
                    positions = wall_shell_cells(section)
                    anchor = min(positions)
                    offsets = tuple(sorted((p[0] - anchor[0], p[1] - anchor[1]) for p in positions))
                    hp = (120 if self.wall_form == "dome" else 30) if self.construction_material == "ice" else (180 if self.stone_panel_width_feet == 10 else 90)
                    item = WallSection(source_entity_uuid=caster.uuid, wall_owner_uuid=zone.uuid,
                        item_id=f"spell_construction.{self.construction_material}.section", name=f"{self.name} section",
                        geometry=section, magical_force=self.construction_material == "force",
                        armor_class=12 if self.construction_material == "ice" else 15,
                        health=None if self.construction_material == "force" else BaseItem.create_item_health(caster.uuid, hp),
                        is_invisible=self.construction_material == "force",
                        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=False,
                            vertical_extent_steps=ceil(section.height_feet / 5), footprint_offsets=offsets))
                    pending.append((item, anchor))
                    if item.health is not None and self.construction_material == "ice":
                        add_modifier(item.health.damage_reduction, Channel.SELF_STATIC, Kind.RESISTANCE, ResistanceModifier(
                            source_entity_uuid=caster.uuid, target_entity_uuid=item.uuid, name="Ice fire vulnerability",
                            damage_type=DamageType.FIRE, value=ResistanceStatus.VULNERABILITY))
                    grid.validate_object_placement(item.uuid, anchor)
                # All native placements are preflighted before displacement or commit.
                zone._pending_sections = tuple(pending)
                zone._formation_displacements = dict(displacements)
                try:
                    activated = zone.activate(parent_event=effect)
                except ValueError as error:
                    return effect.cancel(status_message=str(error))
                if activated is None or activated.canceled or not zone.applied:
                    return effect.cancel(status_message="Wall construction was canceled")
                self.ensure_concentration(effect).add_linked_condition(zone.uuid, zone.uuid)
                if self.construction_material == "ice":
                    spec = WallDamageSpec(dice_count=10 + 2 * max(0, self.cast_at_level - 6), die=6,
                        damage_type=DamageType.COLD, save_ability="dexterity", effect_id="wall_of_ice.appearance")
                    for identity in displacements:
                        entity = Entity.get(identity)
                        if entity is not None:
                            apply_wall_damage(zone, entity, spec, zone.spell_dc, effect, geometry.base_height_steps,
                                              contact_position=formation_contacts[identity])
                return effect
            finally:
                if not zone.sections:
                    if zone.applied:
                        zone.deactivate(parent_event=effect)
                    for item, _ in pending:
                        item.retire(effect)
                    remaining = {item.uuid: item.geometry for item, _ in pending if BaseBlock.get(item.uuid) is not None}
                    zone.sections = remaining
                    if not remaining and not zone.applied:
                        zone.discard_from_runtime_owner()


class WallOfIce(ConstructWall):
    name: str = "Wall of Ice"
    description: str = "Create translucent solid panels or a shared-HP hollow ice dome."
    spell_level: int = 6
    spell_school: str = "evocation"
    spell_damage_type: DamageType = DamageType.COLD
    construction_material: Literal["ice", "stone", "force"] = "ice"


class WallOfStone(ConstructWall):
    name: str = "Wall of Stone"
    description: str = "Create connected supported stone panels; completed concentration makes them permanent."
    spell_level: int = 5
    spell_school: str = "evocation"
    construction_material: Literal["ice", "stone", "force"] = "stone"


class WallOfForce(ConstructWall):
    name: str = "Wall of Force"
    description: str = "Create an invisible solid flat wall or hollow dome; Disintegrate removes the whole construction."
    spell_level: int = 5
    spell_school: str = "evocation"
    construction_material: Literal["ice", "stone", "force"] = "force"


class ForcecageZone(SolidWallZone):
    name: str = "Forcecage"
    description: str = "Invisible independent barred cage or sealed box with paid magical escape saves."
    content_ref: ContentRef = wall_condition_ref("spatial_effect.spell.forcecage")
    material: Literal["ice", "stone", "force"] = "force"
    cage_form: Literal["cage", "box"] = "cage"
    center: tuple[int,int]
    side_feet: int
    duration: Duration = Field(default_factory=lambda: Duration(duration=600, duration_type=DurationType.ROUNDS))
    crossing_channels: ClassVar[frozenset[CrossingChannel] | None] = frozenset({
        WorldEdgeChannel.MOVEMENT, WorldEdgeChannel.PROPAGATION, PhysicalAccess.HAND, PhysicalAccess.WEAPON,
        PhysicalAccess.LIGHT_WEAPON, PhysicalAccess.NATURAL, PhysicalAccess.BODY})

    def _commit_activation_footprint(self,parent_event):
        admitted=[]
        for identity,destination in self._formation_displacements.items():
            actor=Entity.get(identity)
            if actor is None:raise ValueError("Formation occupant disappeared")
            start=actor.position
            direction=(0 if destination[0]==start[0] else 1 if destination[0]>start[0] else -1,
                0 if destination[1]==start[1] else 1 if destination[1]>start[1] else -1)
            distance=max(abs(destination[0]-start[0]),abs(destination[1]-start[1]))*5
            event=ForcedMovementEvent(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=actor.uuid,
                start_position=start,end_position=destination,direction=direction,intended_distance=distance,actual_distance=distance,
                cause="forcecage_formation",parent_event=parent_event.uuid)
            for phase in (EventPhase.EXECUTION,EventPhase.EFFECT):
                if not event.canceled:event=event.phase_to(phase)
            if event.canceled:raise ValueError("Formation ejection refused")
            admitted.append((actor,destination,event))
        grid=get_map()
        sections=grid.prepare_object_sections(tuple((item.uuid,anchor) for item,anchor in self._pending_sections),parent_event=parent_event.uuid)
        placements=grid.commit_object_sections(sections,publish=False)
        for (item,_),placement in zip(self._pending_sections,placements,strict=True):
            item.synchronize_floor_placement(placement)
            self.sections[item.uuid]=item.geometry
        AreaCondition._commit_activation_footprint(self,parent_event)
        self._pending_sections=()
        self._formation_displacements.clear()
        errors=[]
        try:Entity.commit_position_transfers(tuple((actor,destination,event.uuid) for actor,destination,event in admitted))
        except BaseException as error:errors.append(error)
        try:grid.publish_object_sections(sections)
        except BaseException as error:errors.append(error)
        for _,_,event in admitted:
            try:event.phase_to(EventPhase.COMPLETION)
            except BaseException as error:errors.append(error)
        if errors:raise BaseExceptionGroup("Forcecage formation publication failed",errors)

    def contains(self, position: tuple[int,int]) -> bool:
        half = self.side_feet / 10
        return abs(position[0]-self.center[0]) < half and abs(position[1]-self.center[1]) < half

    def blocks_crossing_between(self,start,end,channel,requester_uuid,mode,terminal_provider_uuid=None):
        if channel is WorldEdgeChannel.PROPAGATION and self.cage_form == "cage": return False
        admitted={cell for cell in self.affected_positions if self.allows_contribution_at(cell)}
        # Rays and creature crossings on the supported floor use the remaining
        # ground band. A 10-foot breach need not erase the bars above it.
        return any(identity != terminal_provider_uuid and wall_path_contact(
            geometry.model_copy(update={"height_feet":5}),start,end,admitted) is not None
            for identity,geometry in self.sections.items())

    def _apply(self,event: Event):
        modifiers,handlers,children,spatial,effect=super()._apply(event)
        if effect is None or effect.canceled: return modifiers,handlers,children,spatial,effect
        def escape(transfer: Event,_):
            if not isinstance(transfer,PortalTransferEvent) or not self.contains(transfer.start_position) or self.contains(transfer.end_position):
                return None
            if not any(self.allows_contribution_at(cell) for cell in self.affected_positions): return None
            traveler=Entity.get(transfer.target_entity_uuid) if transfer.target_entity_uuid else None
            if traveler is not None and not condition_save(self,traveler,transfer,"charisma",self.spell_dc,"spell.forcecage.escape"):
                return transfer.cancel(status_message="Forcecage prevents magical escape; attempted resources remain spent")
            return None
        def spell_boundary(incoming: Event,_):
            if self.cage_form != "box" or not isinstance(incoming,SpellEvent) or incoming.canceled:
                return None
            if not any(self.allows_contribution_at(cell) for cell in self.affected_positions): return None
            origin=incoming.effect_source_position or incoming.source_position
            if origin is None: return None
            inside=self.contains(origin)
            if inside and incoming.magical_transfer: return None
            terminal=BaseBlock.get(incoming.target_entity_uuid) if incoming.target_entity_uuid else None
            if incoming.authored_spell_id=="spell.disintegrate" and isinstance(terminal,WallSection) and terminal.wall_owner_uuid==self.uuid:return None
            target=BaseBlock.get(incoming.target_entity_uuid) if incoming.target_entity_uuid else None
            destination=target.position if target is not None else incoming.target_position or incoming.aoe_position or origin
            if destination is not None and inside != self.contains(destination):
                return incoming.cancel(status_message="Sealed Forcecage blocks the spell boundary")
            if not inside and incoming.resolved_area_positions is not None:
                excluded=tuple(cell for cell in incoming.resolved_area_positions if self.contains(cell))
                if excluded:
                    return incoming.with_updates(resolved_area_positions=tuple(cell for cell in incoming.resolved_area_positions if cell not in excluded),
                        suppressions=(*incoming.suppressions,SpellSuppression(provider_uuid=self.uuid,positions=excluded)))
            return None
        for handler in (EventHandler(name="Forcecage paid magical escape",source_entity_uuid=self.source_entity_uuid,
                trigger_conditions=[Trigger(event_type=EventType.PORTAL_TRANSFER,event_phase=EventPhase.EFFECT)],event_processor=escape),
                EventHandler(name="Forcecage sealed spell boundary",source_entity_uuid=self.source_entity_uuid,
                trigger_conditions=[Trigger(event_type=kind,event_phase=phase) for kind in (EventType.CAST_SPELL,EventType.BASE_ACTION)
                    for phase in (EventPhase.EXECUTION,EventPhase.EFFECT)],event_processor=spell_boundary)):
            EventQueue.add_event_handler(handler);handlers.append(handler.uuid)
        return modifiers,handlers,children,spatial,effect


def forcecage_geometry(center: tuple[int,int], side_feet: int) -> WallAssemblyPresentationGeometry | None:
    tile=get_map().get_tile(*center)
    if tile is None: return None
    half=side_feet//10
    x,y=center
    points=((x-half,y-half),(x+half,y-half),(x+half,y+half),(x-half,y+half),(x-half,y-half))
    return WallAssemblyPresentationGeometry(path=WallPolyline(points=points),base_height_steps=tile.height,
        width_feet=1/48,height_feet=side_feet)


def forcecage_displacements(caster: Entity, center: tuple[int,int],side_feet:int,*,subjective:bool) -> dict[UUID,tuple[int,int]] | None:
    """Where each partially enclosed creature is pushed out; None when one cannot be.

    Subjective (discovery) knows only the creatures, positions and blockers the
    caster perceives; objective (execution) knows the world.
    """
    half=side_feet/10
    used=set()
    result={}
    grid=get_map()
    known=caster.senses.entities
    occupied={contact.position for contact in known.values()}|{caster.position} if subjective else set()
    # The box spans half the side plus a Gargantuan space, so it holds every partially enclosed occupant.
    reach=side_feet//10+2
    nearby=((caster.uuid,*known) if subjective
            else grid.get_entities_in_bounds((center[0]-reach,center[1]-reach,center[0]+reach,center[1]+reach)))
    for identity in sorted(nearby,key=str):
        entity=Entity.get(identity)
        if entity is None: continue
        position=known[identity].position if subjective and identity!=caster.uuid else entity.position
        space={Size.TINY:2.5,Size.SMALL:5,Size.MEDIUM:5,Size.LARGE:10,Size.HUGE:15,Size.GARGANTUAN:20}[entity.size]/10
        dx,dy=abs(position[0]-center[0]),abs(position[1]-center[1])
        if dx-space>=half or dy-space>=half: continue
        if dx+space<=half and dy+space<=half: continue
        candidates=[]
        for x in range(center[0]-6,center[0]+7):
            for y in range(center[1]-6,center[1]+7):
                point=(x,y)
                if max(abs(x-center[0])-space,abs(y-center[1])-space)<half or point in used: continue
                tile=grid.get_tile(*point)
                if tile is None or tile.height!=grid.get_support_elevation_feet(center)//5: continue
                if not grid.is_walkable_for(*point,caster.uuid if subjective else entity.uuid,subjective=subjective): continue
                if (point in occupied and point!=position) if subjective else grid.get_entities_at(point)-{entity.uuid}: continue
                if not grid.can_reach_between(position,point,PhysicalAccess.BODY,entity.uuid,subjective=subjective,
                        knowledge_observer_uuid=caster.uuid if subjective else None): continue
                candidates.append(point)
        if not candidates:return None
        destination=min(candidates,key=lambda p:(hypot(p[0]-position[0],p[1]-position[1]),p))
        used.add(destination);result[entity.uuid]=destination
    return result


class Forcecage(SpellAction):
    creates = (*SpellAction.creates, ForcecageZone)
    name: str = "Forcecage"
    description: str = "Independent invisible 20-foot barred cage or 10-foot sealed box for one hour."
    spell_level: int = 7
    spell_school: str = "evocation"
    spell_range: Range = Field(default_factory=lambda:Range(type=RangeType.RANGE,normal=100))
    target_type: TargetType = TargetType.POSITION_LOS
    cage_form: Literal["cage","box"] = "cage"
    concentration: bool = False

    def get_selection_geometry(self):
        return forcecage_geometry(self.end_position,20 if self.cage_form=="cage" else 10) if self.end_position else None

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        return tuple((ActionVariantFacet(key="form", value=form, label=form.title()),) for form in ("cage", "box"))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "cage_form": selection_facet(selection, "form")}

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        side=20 if self.cage_form=="cage" else 10
        center=selection.positions[0] if selection.positions else None
        error=selection_wall_support_error(self,selection,forcecage_geometry(center,side) if center else None,subjective=scan.subjective)
        if error is not None:return error
        caster=Entity.get(self.source_entity_uuid)
        if caster is None or center is None or forcecage_displacements(caster,center,side,subjective=scan.subjective) is None:
            return "Forcecage cannot displace a partially enclosed creature"
        return None

    def _create_declaration_event(self,parent_event=None,use_register=True):
        event=super()._create_declaration_event(parent_event,use_register)
        return event.with_updates(area_geometry=self.get_selection_geometry()) if event is not None else None

    def _apply(self,event: SpellEvent):
        caster=Entity.get(self.source_entity_uuid)
        geometry=self.get_selection_geometry()
        if caster is None or geometry is None or self.end_position is None:return event.cancel(status_message="Cage placement absent")
        side=20 if self.cage_form=="cage" else 10
        displacements=forcecage_displacements(caster,self.end_position,side,subjective=False)
        sections=construction_sections(geometry)
        if displacements is None or sections is None:return event.cancel(status_message="Cage formation is impossible")
        effect=event.phase_to(EventPhase.EFFECT)
        if effect.canceled:return effect
        zone=ForcecageZone(source_entity_uuid=caster.uuid,position=self.end_position,geometry=geometry,
            spell_dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),cage_form=self.cage_form,
            center=self.end_position,side_feet=side,effect_origin=event.to_effect_origin())
        pending=[]
        try:
            for section in sections:
                cells=wall_shell_cells(section);anchor=min(cells)
                item=WallSection(source_entity_uuid=caster.uuid,wall_owner_uuid=zone.uuid,
                    item_id="spell_construction.forcecage.section",name="Forcecage section",geometry=section,
                    magical_force=True,force_owner_disintegration="whole" if self.cage_form=="box" else "section",is_invisible=True,health=None,
                    world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.CENTER,occupies_bands=False,
                        vertical_extent_steps=ceil(section.height_feet/5),footprint_offsets=tuple(sorted((x-anchor[0],y-anchor[1]) for x,y in cells))))
                pending.append((item,anchor));get_map().validate_object_placement(item.uuid,anchor)
            zone._pending_sections=tuple(pending);zone._formation_displacements=displacements
            result=zone.activate(parent_event=effect)
            if result is None or result.canceled:return effect.cancel(status_message="Forcecage was not admitted")
            return effect
        except ValueError as error:
            return effect.cancel(status_message=str(error))
        finally:
            if not zone.applied:
                for item,_ in pending:item.retire(effect)
                zone.discard_from_runtime_owner()
