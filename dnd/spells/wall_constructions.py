"""Solid wall spells: ordinary attackable sections and one native spatial owner."""

from math import ceil, hypot, isclose
from typing import Literal
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.actions import Move, SpellAction, SpellEvent, commit_forced_movement, entity_action_economy_cost_evaluator
from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.core.action_types import PositionPathSelection, PositionSelection, SinglePositionSelection
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import ConditionTag, DurationType
from dnd.core.content.identities import ContentRef
from dnd.core.creature_types import DamageType
from dnd.core.events import Event, EventPhase, EventQueue, ForcedMovementEvent, Range, RangeType, SpatialChangeEvent
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemPresentationState
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallDome, WallPolyline, WallRing, WallSegment
from dnd.core.wall_geometry import wall_crosses_path, wall_path_contact, wall_shell_cells
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition, SpatialCondition
from dnd.spells.wall_fields import WallDamageSpec, WallFieldZone, apply_wall_damage, wall_condition_ref, wall_support_error
from dnd.types.materials import Material
from dnd.types.physical_access import PhysicalAccess
from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.spatial_effects import SpatialEffectChangeOperation, SpatialEffectLayer, SpatialEffectOccupancyPolicy, SpatialEffectTriggerKind
from dnd.types.world import MovementMode
from dnd.types.world_placement import WorldObjectPlacement, WorldPlacementKind, WorldPlacementSpec


class FrigidAirZone(WallFieldZone):
    name: str = "Frigid Air"
    description: str = "Passing through the former ice sheet causes cold damage once per turn."
    content_ref: ContentRef = wall_condition_ref("spatial_effect.spell.frigid_air")
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.ENTER})
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.ENTER})
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.PERMANENT))

    def admits_occupancy_transition(self, event: SpatialChangeEvent) -> bool:
        return (SpatialCondition.admits_occupancy_transition(self, event)
            and event.old_position is not None
            and wall_path_contact(self.geometry, event.old_position, event.position, self.affected_positions) is not None)

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
        contact = (wall_path_contact(self.geometry, event.old_position, event.position, self.affected_positions)
                   if event.old_position is not None else None)
        return (min(self.affected_positions, key=lambda p: hypot(p[0] - contact[0], p[1] - contact[1]))
                if contact is not None else entity.position)


class WallSection(WorldItem):
    """One physical health identity, independent of its owning spell condition."""

    wall_owner_uuid: UUID
    geometry: WallAssemblyPresentationGeometry
    magical_force: bool = False
    is_pickable: bool = False
    is_targetable: bool = True
    blocks_movement: bool = False
    blocks_optics_field: bool = False
    blocks_propagation_field: bool = False
    tags: list[str] = Field(default_factory=lambda: ["spell_construction"])
    known_to_creator: bool = True
    _break_event: Event | None = PrivateAttr(default=None)

    def to_item_presentation_state(self, *, stack_count: int | None = None) -> ItemPresentationState:
        return super().to_item_presentation_state(stack_count=stack_count).model_copy(
            update={"construction_geometry": self.geometry, "known_to_creator": self.known_to_creator})

    def _on_destroy(self, parent_event: Event | None) -> None:
        self._break_event = parent_event

    def retire(self, parent_event: Event | None = None) -> None:
        super().retire(parent_event)
        if BaseBlock.get(self.uuid) is None and self._break_event is not None:
            owner = BaseCondition.get(self.wall_owner_uuid)
            if isinstance(owner, SolidWallZone) and owner.applied:
                owner.on_section_destroyed(self.uuid, self._break_event)
            self._break_event = None

    def disintegrate(self, parent_event: Event) -> bool:
        if self.magical_force:
            owner = BaseCondition.get(self.wall_owner_uuid)
            return owner.deactivate(parent_event=parent_event) if isinstance(owner, SolidWallZone) else False
        self.destroy(parent_event)
        return BaseBlock.get(self.uuid) is None

    def disintegration_error(self) -> str | None:
        if self.magical_force:
            return None
        path = self.geometry.path
        if isinstance(path, WallDome) or (isinstance(path, WallSegment)
                and hypot(path.end[0] - path.start[0], path.end[1] - path.start[1]) > 2):
            return "Partial disintegration of larger objects is not yet supported"
        return None


class SolidWallZone(AreaCondition):
    """Ownership links and exact shell crossings, without a filled-volume blocker."""

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
    _prepared_removals: list[tuple[BaseBlock, WorldObjectPlacement, Event | None]] | None = PrivateAttr(default=None)

    def resolve_condition_footprint(self) -> set[tuple[int, int]]:
        return self._apply_spell_protection({p for p in wall_shell_cells(self.geometry) if get_map().has_tile(*p)})

    def blocks_crossing_between(self, start, end, channel, requester_uuid, mode,
                                terminal_provider_uuid=None) -> bool:
        if channel == "optical" and self.material != "stone":
            return False
        if channel == "movement" and mode is MovementMode.BURROWING and self.material != "force":
            return False
        return any(identity != terminal_provider_uuid and wall_path_contact(geometry, start, end,
                   self.affected_positions) is not None
                   for identity, geometry in self.sections.items())

    def blocks_physical_optics_at(self, position: tuple[int, int]) -> bool:
        return self.material == "stone" and any(position in wall_shell_cells(g) for g in self.sections.values())

    def get_spatial_observation(self, positions: set[tuple[int, int]], *, observer_uuid,
                                discovered=False) -> PerceivedSpatialEffect | None:
        live = set().union(*(wall_shell_cells(g) for g in self.sections.values())) if self.sections else set()
        observed = SpatialCondition.get_spatial_observation(self, positions & live,
            observer_uuid=observer_uuid, discovered=discovered)
        return observed.model_copy(update={"area_geometry": self.geometry,
            "construction_sections": tuple(g for g in self.sections.values() if wall_shell_cells(g) & positions),
            "anchor_elevation_steps": self.geometry.base_height_steps}) if observed is not None else None

    def on_section_destroyed(self, identity: UUID, parent_event: Event) -> None:
        geometry = self.sections.pop(identity, None)
        if geometry is None:
            return
        change = self._open_change(SpatialEffectChangeOperation.STATE_CHANGED,
            previous_positions=set(self.affected_positions), affected_positions=set(self.affected_positions),
            parent_event=parent_event)
        if self.material == "ice":
            positions = wall_shell_cells(geometry) & self.affected_positions
            if not positions:
                get_map().invalidate_spatial_caches({"movement", "optical", "propagation"})
                self._complete_change(change)
                return
            air = FrigidAirZone(source_entity_uuid=self.source_entity_uuid, position=min(positions),
                geometry=geometry, affected_positions=positions, spell_dc=self.spell_dc,
                contact_damage=WallDamageSpec(dice_count=self.residual_dice_count, die=6,
                    damage_type=DamageType.COLD, save_ability="constitution", effect_id="wall_of_ice.frigid_air"),
                effect_origin=self.effect_origin)
            result = air.activate(parent_event=change)
            if result is not None and not result.canceled and air.applied:
                self.add_linked_condition(air.uuid, air.uuid)
        get_map().invalidate_spatial_caches({"movement", "optical", "propagation"})
        self._complete_change(change)

    def publish_removal_effect(self, declaration_event: Event) -> Event:
        effect = super().publish_removal_effect(declaration_event)
        if effect.canceled:
            return effect
        if self.sections:
            self._prepared_removals = get_map().prepare_object_removals(tuple(self.sections), effect.uuid)
            if self._prepared_removals is None:
                return effect.cancel(status_message="A wall section refused retirement")
        return effect

    def cancel_prepared_removal(self, reason: str) -> None:
        if self._prepared_removals is not None:
            get_map().cancel_object_removals(self._prepared_removals, reason)
            self._prepared_removals = None

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        grid = get_map()
        identities = tuple(self.sections)
        if self._prepared_removals is not None:
            grid.commit_object_removals(self._prepared_removals,
                parent_event=parent_event.uuid if parent_event is not None else None)
            self._prepared_removals = None
        for identity in identities:
            item = BaseBlock.get(identity)
            if isinstance(item, WallSection):
                # Expiry/concentration removal never completes a deferred break
                # or admits a new child after the removal graph was preflighted.
                item._break_event = None
            if isinstance(item, BaseItem):
                item.retire(parent_event)
                if BaseBlock.get(identity) is not None:
                    raise RuntimeError("Wall section could not release its native owner")
        self.sections.clear()
        super()._release_owned_runtime_state(parent_event=parent_event)

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
                      *, side: str) -> dict[UUID, tuple[int, int]] | None:
    grid = get_map()
    shell = wall_shell_cells(geometry)
    occupants = {identity for position in shell for identity in grid.get_entities_at(position)}
    used: set[tuple[int, int]] = set()
    result = {}
    path = geometry.path
    if isinstance(path, WallRing):
        return None
    for identity in sorted(occupants, key=str):
        entity = Entity.get(identity)
        if entity is None:
            continue
        entity_position = entity.position
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
                    segments = ([WallSegment(start=a, end=b) for a, b in zip(path.points, path.points[1:])]
                                if isinstance(path, WallPolyline) else [path])
                    segments = [s for s in segments if entity_position in wall_shell_cells(
                        geometry.model_copy(update={"path": s}))] or segments
                    segment = min(segments, key=lambda s: hypot(
                        (s.start[0] + s.end[0]) / 2 - entity_position[0],
                        (s.start[1] + s.end[1]) / 2 - entity_position[1]))
                    cross = ((segment.end[0] - segment.start[0]) * (position[1] - segment.start[1])
                             - (segment.end[1] - segment.start[1]) * (position[0] - segment.start[0]))
                    if (cross > 0) != (side == "left"):
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
    for entity in Entity.get_all_entities():
        start = displacements.get(entity.uuid, entity.position)
        if (not entity.is_deployed or not min_x <= start[0] <= max_x
                or not min_y <= start[1] <= max_y):
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
        costs, paths = grid.compute_paths(entity.position, requesting_entity_uuid=entity.uuid,
            max_distance=ceil(speed / 5), subjective=True)
        exits = [p for p in paths if (p[0] < min_x or p[0] > max_x or p[1] < min_y or p[1] > max_y)
                 and costs[p] * 5 <= speed]
        if not exits:
            continue
        destination = min(exits, key=lambda p: (costs[p], p))
        Move(name="Escape forming wall", source_entity_uuid=entity.uuid, end_position=destination,
            path=paths[destination], use_movement_cost=False, movement_allowance_feet=speed,
            costs=[Cost(name="Wall enclosure escape", cost_type="reactions", cost=1,
                        evaluator=entity_action_economy_cost_evaluator)]).apply(parent_event=parent_event)


class ConstructWall(SpellAction):
    """Concrete shared placement composer, configured by native spell data."""

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
        if self.end_position is None:
            return None
        points = self.get_selected_position_path()
        if points is not None and any(a == b for a, b in zip(points, points[1:])):
            return None
        if self.wall_form == "dome":
            path = WallDome(center=self.end_position, radius_feet=self.dome_radius_feet)
            anchor = self.end_position
        elif points is not None and len(points) >= 2:
            path = WallPolyline(points=tuple(points)) if self.construction_material == "stone" else WallSegment(start=points[0], end=points[-1])
            anchor = points[0]
        else:
            return None
        tile = get_map().get_tile(*anchor)
        width = {"ice": 1., "stone": .5 if self.stone_panel_width_feet == 10 else .25, "force": 1 / 48}[self.construction_material]
        return WallAssemblyPresentationGeometry(path=path, base_height_steps=tile.height,
            width_feet=width, height_feet=self.dome_radius_feet if self.wall_form == "dome" else 10) if tile is not None else None

    def position_placement_error(self, *, subjective=False) -> str | None:
        geometry = self.wall_geometry()
        error = wall_support_error(self, geometry, subjective=subjective)
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
        if caster is None or displacement_plan(caster, geometry, side=self.displacement_side) is None:
            return "No free supported side for displaced creatures"
        return None

    def _create_declaration_event(self, parent_event=None, use_register=True) -> Event | None:
        event = super()._create_declaration_event(parent_event, use_register)
        return event.with_updates(area_geometry=self.wall_geometry()) if isinstance(event, SpellEvent) else event

    def _validate(self, declaration_event: SpellEvent) -> SpellEvent | None:
        return declaration_event.phase_to(EventPhase.EXECUTION)

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
                    item.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
                        source_entity_uuid=caster.uuid, target_entity_uuid=item.uuid, name="Ice fire vulnerability",
                        damage_type=DamageType.FIRE, value=ResistanceStatus.VULNERABILITY))
                grid.validate_object_placement(item.uuid, anchor)
            # All native placements are preflighted before displacement or commit.
            activated = zone.activate(parent_event=effect)
            if activated is None or activated.canceled or not zone.applied:
                return effect.cancel(status_message="Wall construction was canceled")
            for identity, destination in displacements.items():
                entity = Entity.get(identity)
                if entity is not None and not move_displaced(entity, destination, caster, effect):
                    return effect.cancel(status_message="Formation displacement was canceled")
            try:
                placements = grid.place_object_sections(tuple((item.uuid, anchor) for item, anchor in pending),
                                                        parent_event=effect.uuid)
            except ValueError as error:
                return effect.cancel(status_message=str(error))
            for (item, _), placement in zip(pending, placements):
                item.synchronize_floor_placement(placement)
                zone.sections[item.uuid] = item.geometry
            change = zone._open_change(SpatialEffectChangeOperation.STATE_CHANGED,
                previous_positions=set(zone.affected_positions), affected_positions=set(zone.affected_positions),
                parent_event=effect)
            zone._complete_change(change)
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

    def get_discovery_variants(self, entity) -> list[BaseAction]:
        variants = []
        for slot in super().get_discovery_variants(entity):
            for width in ((10, 20) if self.construction_material == "stone" else (10,)):
                for side in ("left", "right"):
                    variants.append(slot.model_copy(update={"wall_form": "panels", "displacement_side": side,
                                                            "stone_panel_width_feet": width}))
            if self.construction_material != "stone":
                for radius in (5, 10):
                    for side in ("inside", "outside"):
                        variants.append(slot.model_copy(update={"wall_form": "dome", "dome_radius_feet": radius,
                                                                 "displacement_side": side}))
        return variants

    def get_discovery_template_name(self) -> str:
        return f"{super().get_discovery_template_name()}__{self.wall_form}_{self.displacement_side}_{self.dome_radius_feet}_{self.stone_panel_width_feet}"


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
