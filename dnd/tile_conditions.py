"""Zone and tile condition models for terrain, hazards, and spell areas."""

import re
from typing import Callable, List, Optional, Tuple, Type, Set, Dict

from dnd.core.base_block import LightLevel
from dnd.core.base_tiles import Tile
from uuid import UUID, uuid4
from pydantic import Field, PrivateAttr

from dnd.core.base_conditions import BaseCondition, ConditionCategory, HazardFilter, SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.events import Event, EventPhase, EventType, EventHandler, EventQueue, SpatialChangeEvent, SensesUpdateHint
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import ModifiableValue
from dnd.core.aoe import Sphere, Cone, Line, Cube, Cylinder


def parse_dice_string(dice_str: str) -> Tuple[int, int]:
    """Parse a dice string like '2d4' into (count, value)."""
    match = re.match(r'(\d+)d(\d+)', dice_str.lower())
    if match:
        return int(match.group(1)), int(match.group(2))
    return 1, 4


class TileEffectCondition(BaseCondition):
    """Base condition applied to tiles by zone spells.

    The target_entity_uuid is the tile's UUID.
    Subclasses override _apply() to add specific effects (terrain modifiers,
    damage handlers, obscurement, etc.).
    """

    name: str = Field(default="Tile Effect", description="Tile condition name.")
    description: str = Field(default="A tile effect from a zone spell", description="Tile condition description.")

    model_config = {"arbitrary_types_allowed": True}

    def get_tile(self) -> Optional[Tile]:
        """Helper to get the tile this condition is applied to.

        The target_entity_uuid is the tile's UUID.
        """
        if self.target_entity_uuid is None:
            return None
        grid = get_map()
        return grid.get_tile_by_uuid(self.target_entity_uuid)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply no direct effect and return an effect event for parity."""
        effect_event = None
        if declaration_event is not None:
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Remove the tile effect condition.

        Spatial handlers are tracked in spatial_handler_uuids and
        cleaned up by parent class's remove_spatial_handlers().
        Event handlers are tracked in event_handlers_uuids and
        cleaned up by parent class's remove_event_handlers().
        """
        return super()._remove(event)


class ZoneMarkerCondition(TileEffectCondition):
    """Data-only marker applied to tiles in a zone spell."""

    condition_category: ConditionCategory = ConditionCategory.CONDITION

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], [], [], [], effect_event


class SpikeTrapCondition(TileEffectCondition):
    """Data-only marker on spike trap tiles."""

    name: str = Field(default="Spike Trap", description="Spike trap condition name.")
    description: str = Field(default="Sharp spikes deal damage when stepped on", description="Spike trap condition description.")
    hazard_filter: HazardFilter = Field(default=HazardFilter.ALL, description="Entities that should treat the trap as hazardous.")
    condition_category: ConditionCategory = ConditionCategory.CONDITION

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], [], [], [], effect_event


class ZoneControlCondition(BaseCondition):
    """Base condition for controlling a zone of tile effects.

    Applied to the caster. Uses position-indexed spatial handlers for efficient
    O(1) lookup when entities enter/exit the zone, instead of O(tiles) handlers.

    Key architecture:
    - ONE handler per effect type per zone (not per tile)
    - Handlers are registered via EventQueue.add_spatial_handler() with position set
    - Zone movement uses EventQueue.update_spatial_handler_positions() for O(delta) updates
    - Terrain modifiers (difficult terrain) are separate from event handlers

    Subclasses should:
    1. Override _has_entry_effect() and _create_zone_entry_handler() for entry effects
    2. Override _has_exit_effect() and _create_zone_exit_handler() for exit effects
    3. Override _compute_affected_positions() if using custom geometry
    """
    name: str = Field(default="Zone Control", description="Zone condition name.")
    description: str = Field(default="Controls a zone of tile effects", description="Zone condition description.")

    zone_center: Tuple[int, int] = Field(default=(0, 0), description="Center position of the zone")
    zone_shape: str = Field(default="sphere", description="Shape: 'sphere', 'cone', 'line', 'cube', or 'cylinder'")
    zone_radius_feet: int = Field(default=20, description="Radius/size in feet")
    zone_width_feet: int = Field(default=5, description="Line width in feet for line-shaped zones")
    zone_direction: Optional[Tuple[int, int]] = Field(default=None, description="Direction for cones/lines")

    adds_difficult_terrain: bool = Field(default=False, description="If True, adds +1 to walking cost")

    sets_light_level: Optional[LightLevel] = Field(default=None, description="Light level to apply to zone tiles")
    light_is_obscurement: bool = Field(default=False, description="If True, uses add_obscurement(); else add_illumination()")

    affected_positions: Set[Tuple[int, int]] = Field(default_factory=set, description="Currently affected tile positions")

    _entry_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _exit_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _turn_start_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _terrain_modifier_uuids: Dict[UUID, List[UUID]] = PrivateAttr(default_factory=dict)
    _light_modifier_uuids: Dict[Tuple[int, int], UUID] = PrivateAttr(default_factory=dict)

    marker_name: Optional[str] = Field(default=None, description="Name for ZoneMarkerCondition on each tile (e.g. 'Spike Growth'). None = no markers.")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=None, description="HazardFilter for tile markers")
    marker_stealth_dc: Optional[int] = Field(default=None, description="Stealth DC for tile markers (perception to detect)")

    model_config = {"arbitrary_types_allowed": True}

    def _has_entry_effect(self) -> bool:
        """Return True if this zone has an effect when entities enter."""
        return False

    def _has_exit_effect(self) -> bool:
        """Return True if this zone has an effect when entities exit."""
        return False

    def _has_turn_start_effect(self) -> bool:
        """Return True if this zone has a turn start effect."""
        return False

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create the zone-level entry handler for all affected positions."""
        raise NotImplementedError("Subclass must implement _create_zone_entry_handler")

    def _create_zone_exit_handler(self) -> EventHandler:
        """Create the zone-level exit handler for all affected positions."""
        raise NotImplementedError("Subclass must implement _create_zone_exit_handler")

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create a normal event handler for turn starts inside the zone."""
        raise NotImplementedError("Subclass must implement _create_zone_turn_start_handler")

    def _find_source_spell_level(self, event: Optional[Event]) -> Optional[int]:
        """Walk parent_event chain to find the originating SpellEvent's base level.

        Returns the spell_level (base, not upcast) or None if no SpellEvent found.
        """
        from dnd.actions import SpellEvent
        current_uuid = event.uuid if event else None
        visited = 0
        while current_uuid and visited < 20:
            obj = BaseObject.get(current_uuid)
            if obj is None:
                break
            if isinstance(obj, SpellEvent):
                return obj.spell_level
            if isinstance(obj, Event):
                current_uuid = obj.parent_event
            else:
                break
            visited += 1
        return None

    @staticmethod
    def _wrap_processor_with_protection(
        original_processor: Callable[[Event, UUID], Optional[Event]],
        source_entity_uuid: UUID,
        spell_level: int,
    ) -> Callable[[Event, UUID], Optional[Event]]:
        """Wrap a zone handler processor with a SpellProtectionRegistry check.

        At fire time, checks if the target entity's position is protected by a
        globe-like effect. If protected, skips the effect (returns None).
        """
        from dnd.entity import Entity

        def wrapped(event: Event, src_uuid: UUID) -> Optional[Event]:
            if event.target_entity_uuid:
                target = Entity.get(event.target_entity_uuid)
                if target:
                    source = Entity.get(source_entity_uuid)
                    source_pos = source.position if source else (0, 0)
                    if SpellProtectionRegistry.is_protected(target.position, source_pos, spell_level):
                        return None
            return original_processor(event, src_uuid)

        return wrapped

    def _compute_affected_positions(self) -> Set[Tuple[int, int]]:
        """Compute which tile positions are affected by this zone.

        Override in subclasses for custom geometry.
        Default uses AoE shapes from dnd.core.aoe.
        """
        shape_classes = {
            "sphere": Sphere,
            "cone": Cone,
            "line": Line,
            "cube": Cube,
            "cylinder": Cylinder,
        }

        if self.zone_shape in ("cone", "line") and self.zone_direction:
            dx, dy = self.zone_direction
            target = (self.zone_center[0] + dx, self.zone_center[1] + dy)
            if self.zone_shape == "cone":
                shape = Cone(
                    source_entity_uuid=self.source_entity_uuid,
                    target=target,
                    length_feet=self.zone_radius_feet,
                )
            else:
                shape = Line(
                    source_entity_uuid=self.source_entity_uuid,
                    target=target,
                    length_feet=self.zone_radius_feet,
                    width_feet=self.zone_width_feet,
                )
        else:
            ShapeClass = shape_classes.get(self.zone_shape, Sphere)
            shape = ShapeClass(
                source_entity_uuid=self.source_entity_uuid,
                target=self.zone_center,
                radius_feet=self.zone_radius_feet
            )

        shape.compute_objective(self.zone_center)
        return set(shape.affected_positions)

    def _apply_terrain_modifiers(self) -> List[Tuple[UUID, UUID]]:
        """Apply difficult terrain modifiers to affected tiles.

        Returns:
            List of (value_uuid, modifier_uuid) pairs for tracking in modifers_uuids.
        """
        outs: List[Tuple[UUID, UUID]] = []
        if not self.adds_difficult_terrain:
            return outs

        grid = get_map()
        modified_positions: List[Tuple[int, int]] = []
        for pos in self.affected_positions:
            tile = grid.get_tile(*pos)
            if tile:
                mod = NumericalModifier.create(
                    source_entity_uuid=self.source_entity_uuid,
                    name=f"{self.name} Difficult Terrain",
                    value=1,
                )
                mod_uuid = tile.walking_cost.self_static.add_value_modifier(mod)
                self._terrain_modifier_uuids[tile.walking_cost.uuid] = [mod_uuid]
                outs.append((tile.walking_cost.uuid, mod_uuid))
                modified_positions.append(pos)

        if modified_positions:
            hint = SensesUpdateHint(requires_paths=True)
            representative_pos = modified_positions[0]
            tile = grid.get_tile(*representative_pos)
            if tile:
                event = SpatialChangeEvent.tile_changed(
                    representative_pos, walkable=True, visible=True,
                    senses_hint=hint,
                )
                event = event.phase_to(EventPhase.COMPLETION)
                EventQueue.register(event)

        return outs

    def _remove_terrain_modifiers(self) -> None:
        """Remove terrain modifiers before zone move or removal."""
        had_modifiers = bool(self._terrain_modifier_uuids)
        for value_uuid, mod_uuids in self._terrain_modifier_uuids.items():
            value = ModifiableValue.get(value_uuid)
            if value is not None:
                for mod_uuid in mod_uuids:
                    try:
                        value.self_static.remove_modifier(mod_uuid)
                    except (ValueError, KeyError):
                        pass
        self._terrain_modifier_uuids.clear()

        if had_modifiers and self.affected_positions:
            hint = SensesUpdateHint(requires_paths=True)
            representative_pos = next(iter(self.affected_positions))
            grid = get_map()
            tile = grid.get_tile(*representative_pos)
            if tile:
                event = SpatialChangeEvent.tile_changed(
                    representative_pos, walkable=True, visible=True,
                    senses_hint=hint,
                )
                event = event.phase_to(EventPhase.COMPLETION)
                EventQueue.register(event)

    def _remove_terrain_modifier_at(self, position: Tuple[int, int]) -> bool:
        """Remove this zone's difficult-terrain modifier from one tile.

        Args:
            position: Grid position whose terrain modifier should be removed.

        Returns:
            True if a modifier was removed from the tile.
        """
        grid = get_map()
        tile = grid.get_tile(*position)
        if tile is None:
            return False

        value_uuid = tile.walking_cost.uuid
        mod_uuids = self._terrain_modifier_uuids.pop(value_uuid, [])
        if not mod_uuids:
            return False

        value = ModifiableValue.get(value_uuid)
        if value is not None:
            for mod_uuid in mod_uuids:
                value.remove_modifier(mod_uuid)

        tracked_modifiers = self.modifers_uuids.get(value_uuid)
        if tracked_modifiers is not None:
            for mod_uuid in mod_uuids:
                if mod_uuid in tracked_modifiers:
                    tracked_modifiers.remove(mod_uuid)
            if not tracked_modifiers:
                del self.modifers_uuids[value_uuid]

        hint = SensesUpdateHint(requires_paths=True)
        event = SpatialChangeEvent.tile_changed(
            position, walkable=True, visible=True,
            senses_hint=hint,
        )
        event = event.phase_to(EventPhase.COMPLETION)
        EventQueue.register(event)
        return True

    def _apply_tile_markers(self, parent_event: Optional[Event] = None) -> None:
        """Apply linked `ZoneMarkerCondition` records to affected tiles."""
        if self.marker_name is None:
            return

        grid = get_map()
        for pos in self.affected_positions:
            tile = grid.get_tile(*pos)
            if tile is None:
                continue
            marker = ZoneMarkerCondition(
                name=self.marker_name,
                hazard_filter=self.marker_hazard_filter,
                condition_stealth_dc=self.marker_stealth_dc,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=tile.uuid,
                tags=self.tags,
            )
            tile.add_condition(marker, event=parent_event)
            self.add_linked_condition(tile.uuid, marker.uuid)

        if self.affected_positions and self.marker_hazard_filter is not None:
            hint = SensesUpdateHint(requires_paths=True)
            representative_pos = next(iter(self.affected_positions))
            tile = grid.get_tile(*representative_pos)
            if tile:
                event = SpatialChangeEvent.tile_changed(
                    representative_pos, walkable=True, visible=True,
                    senses_hint=hint,
                )
                event = event.phase_to(EventPhase.COMPLETION)
                EventQueue.register(event)

    def _apply_light_modifiers(self) -> None:
        """Apply light level modifiers to affected tiles.

        Uses fire_event=False per tile + batch event after, same pattern
        as GridMap._apply_light_source().
        """
        if self.sets_light_level is None:
            return

        grid = get_map()
        changed_positions: List[Tuple[int, int]] = []
        requires_fov = False
        for pos in self.affected_positions:
            tile = grid.get_tile(*pos)
            if tile:
                modifier_uuid = uuid4()
                old_light_level = tile.resolved_light_level
                if self.light_is_obscurement:
                    if tile.add_obscurement(modifier_uuid, self.sets_light_level, fire_event=False):
                        changed_positions.append(pos)
                else:
                    if tile.add_illumination(modifier_uuid, self.sets_light_level, fire_event=False):
                        changed_positions.append(pos)
                if (
                    old_light_level == LightLevel.MAGICAL_DARKNESS
                    or tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS
                ):
                    requires_fov = True
                self._light_modifier_uuids[pos] = modifier_uuid

        grid._fire_light_batch_events(changed_positions, requires_fov=requires_fov)

    def _remove_light_modifiers(self) -> None:
        """Remove light level modifiers from affected tiles.

        Uses fire_event=False per tile + batch event after.
        """
        grid = get_map()
        changed_positions: List[Tuple[int, int]] = []
        requires_fov = False
        for pos, modifier_uuid in self._light_modifier_uuids.items():
            tile = grid.get_tile(*pos)
            if tile:
                old_light_level = tile.resolved_light_level
                if tile.remove_light_modifier(modifier_uuid, fire_event=False):
                    changed_positions.append(pos)
                    if (
                        old_light_level == LightLevel.MAGICAL_DARKNESS
                        or tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS
                    ):
                        requires_fov = True
        self._light_modifier_uuids.clear()

        grid._fire_light_batch_events(changed_positions, requires_fov=requires_fov)

    def _remove_light_modifier_at(self, position: Tuple[int, int]) -> bool:
        """Remove this zone's light or obscurement modifier from one tile.

        Args:
            position: Grid position whose light modifier should be removed.

        Returns:
            True if a tile light state changed.
        """
        modifier_uuid = self._light_modifier_uuids.pop(position, None)
        if modifier_uuid is None:
            return False

        grid = get_map()
        tile = grid.get_tile(*position)
        if tile is None:
            return False

        old_light_level = tile.resolved_light_level
        changed = tile.remove_light_modifier(modifier_uuid, fire_event=False)
        requires_fov = (
            old_light_level == LightLevel.MAGICAL_DARKNESS
            or tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS
        )
        if changed:
            grid._fire_light_batch_events([position], requires_fov=requires_fov)
        return changed

    def _remove_tile_marker_at(
        self,
        position: Tuple[int, int],
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Remove this zone's linked marker condition from one tile.

        Args:
            position: Grid position whose marker should be removed.
            parent_event: Optional parent event for removal lineage.

        Returns:
            True if a linked marker was removed.
        """
        if self.marker_name is None:
            return False

        grid = get_map()
        tile = grid.get_tile(*position)
        if tile is None:
            return False

        removed = False
        remaining_links: List[Tuple[UUID, UUID]] = []
        for block_uuid, condition_uuid in self.linked_conditions:
            condition = BaseCondition.get(condition_uuid)
            if (
                block_uuid == tile.uuid
                and condition is not None
                and isinstance(condition, BaseCondition)
                and condition.name == self.marker_name
            ):
                tile.remove_condition_by_uuid(condition_uuid, parent_event=parent_event)
                removed = True
                continue
            remaining_links.append((block_uuid, condition_uuid))
        self.linked_conditions = remaining_links
        return removed

    def _sync_spatial_handler_positions(self) -> None:
        """Synchronize spatial handlers with the current affected positions."""
        if self._entry_handler_uuid:
            EventQueue.update_spatial_handler_positions(
                self._entry_handler_uuid,
                self.affected_positions,
                EventType.SPATIAL_ENTITY_ENTERED,
                EventPhase.EFFECT,
            )

        if self._exit_handler_uuid:
            EventQueue.update_spatial_handler_positions(
                self._exit_handler_uuid,
                self.affected_positions,
                EventType.SPATIAL_ENTITY_LEFT,
                EventPhase.EFFECT,
            )

    def _remove_position_effects(
        self,
        position: Tuple[int, int],
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Remove terrain, light, markers, and spatial indexing for one cell.

        Args:
            position: Grid position to remove from the zone.
            parent_event: Optional parent event for linked marker removal.

        Returns:
            True if the position belonged to this zone and was removed.
        """
        if position not in self.affected_positions:
            return False

        self.affected_positions.remove(position)
        self._sync_spatial_handler_positions()
        self._remove_terrain_modifier_at(position)
        self._remove_light_modifier_at(position)
        self._remove_tile_marker_at(position, parent_event=parent_event)
        return True

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply zone control by computing positions and registering handlers."""
        from dnd.entity import Entity

        handler_uuids: List[UUID] = []
        spatial_handler_uuids: List[UUID] = []

        self.affected_positions = self._compute_affected_positions()

        spell_level = self._find_source_spell_level(declaration_event)
        if spell_level is not None and self.magical_origin:
            source = Entity.get(self.source_entity_uuid)
            if source:
                excluded = SpellProtectionRegistry.get_excluded_positions(
                    source.position, spell_level)
                self.affected_positions -= excluded

        if self._has_entry_effect():
            handler = self._create_zone_entry_handler()
            if spell_level is not None and self.magical_origin:
                handler.event_processor = self._wrap_processor_with_protection(
                    handler.event_processor, self.source_entity_uuid, spell_level)
            EventQueue.add_spatial_handler(
                handler,
                self.affected_positions,
                EventType.SPATIAL_ENTITY_ENTERED,
                EventPhase.EFFECT
            )
            self._entry_handler_uuid = handler.uuid
            spatial_handler_uuids.append(handler.uuid)

        if self._has_exit_effect():
            handler = self._create_zone_exit_handler()
            EventQueue.add_spatial_handler(
                handler,
                self.affected_positions,
                EventType.SPATIAL_ENTITY_LEFT,
                EventPhase.EFFECT
            )
            self._exit_handler_uuid = handler.uuid
            spatial_handler_uuids.append(handler.uuid)

        if self._has_turn_start_effect():
            handler = self._create_zone_turn_start_handler()
            if spell_level is not None and self.magical_origin:
                handler.event_processor = self._wrap_processor_with_protection(
                    handler.event_processor, self.source_entity_uuid, spell_level)
            EventQueue.add_event_handler(handler)
            self._turn_start_handler_uuid = handler.uuid
            handler_uuids.append(handler.uuid)

        terrain_modifiers = self._apply_terrain_modifiers()

        self._apply_light_modifiers()

        self._apply_tile_markers(parent_event=declaration_event)

        if declaration_event is not None:
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        else:
            effect_event = None

        return terrain_modifiers, handler_uuids, [], spatial_handler_uuids, effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up spatial handlers and zone-owned modifiers."""
        if self._entry_handler_uuid:
            EventQueue.remove_spatial_handler(self._entry_handler_uuid)
            self._entry_handler_uuid = None

        if self._exit_handler_uuid:
            EventQueue.remove_spatial_handler(self._exit_handler_uuid)
            self._exit_handler_uuid = None

        if self._turn_start_handler_uuid:
            self._turn_start_handler_uuid = None

        self._remove_terrain_modifiers()
        self._remove_light_modifiers()

        return super()._remove(event)

    def move_zone(self, new_center: Tuple[int, int]) -> bool:
        """Move the zone to a new position using efficient batch update.

        This method:
        1. Removes terrain modifiers from old positions
        2. Computes new affected positions
        3. Uses batch position update for handlers (O(delta) not O(total))
        4. Applies terrain modifiers to new positions

        Returns True on success.
        """
        self._remove_terrain_modifiers()
        self._remove_light_modifiers()

        self.zone_center = new_center
        new_positions = self._compute_affected_positions()

        if self._entry_handler_uuid:
            EventQueue.update_spatial_handler_positions(
                self._entry_handler_uuid,
                new_positions,
                EventType.SPATIAL_ENTITY_ENTERED,
                EventPhase.EFFECT
            )

        if self._exit_handler_uuid:
            EventQueue.update_spatial_handler_positions(
                self._exit_handler_uuid,
                new_positions,
                EventType.SPATIAL_ENTITY_LEFT,
                EventPhase.EFFECT
            )

        self.affected_positions = new_positions

        self._apply_terrain_modifiers()
        self._apply_light_modifiers()

        return True

    def get_tile_effect_class(self) -> Type[TileEffectCondition]:
        """Get the TileEffectCondition class to use for this zone.

        DEPRECATED: Use _has_entry_effect() and _create_zone_entry_handler() instead.
        This method is kept for backward compatibility with zones that use
        the per-tile TileEffectCondition pattern.
        """
        return TileEffectCondition

    def _apply_to_tiles(self, _declaration_event: Event) -> None:
        """Apply tile effect conditions to all affected tiles.

        DEPRECATED: Use position-indexed spatial handlers instead.
        This method is kept for backward compatibility.
        """
        tile_effect_class = self.get_tile_effect_class()
        grid = get_map()

        for pos in self.affected_positions:
            tile = grid.get_tile(*pos)
            if tile:
                effect = tile_effect_class(
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=tile.uuid
                )
                tile.add_condition(effect)
                self.add_linked_condition(tile.uuid, effect.uuid)
