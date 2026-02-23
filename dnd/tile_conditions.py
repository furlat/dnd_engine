"""
Tile condition system for zone spells and terrain effects.

Provides base classes for:
- ZoneControlCondition: Applied to caster, manages a zone of tile effects
- TileEffectCondition: Applied to individual tiles, provides the actual effect

Zone Spell Pattern:
    Caster: Concentrating(spell_name="Fog Cloud")
        +-- linked_conditions -> FogCloudZone (on caster)
                +-- linked_conditions -> FogCloudTileEffect (on each tile)

Event Handling:
- SPATIAL events now fire through full lifecycle: DECLARATION -> EXECUTION -> EFFECT -> COMPLETION
- Entry damage handlers fire at EFFECT phase using standard EventHandlers
- Turn start damage handlers also fire at EFFECT phase
- SpatialSensesCallback still uses callbacks for passive senses updates at COMPLETION
"""

import re
from typing import List, Optional, Tuple, Type, Set, Dict

from dnd.core.base_block import LightLevel
from dnd.core.base_tiles import Tile
from uuid import UUID, uuid4
from pydantic import Field, PrivateAttr

from dnd.core.base_conditions import BaseCondition, ConditionCategory, HazardFilter
from dnd.core.events import Event, EventPhase, EventType, EventHandler, EventQueue, SpatialChangeEvent, SensesUpdateHint
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import ModifiableValue
from dnd.core.aoe import Sphere, Cone, Line, Cube


def parse_dice_string(dice_str: str) -> Tuple[int, int]:
    """Parse a dice string like '2d4' into (count, value)."""
    match = re.match(r'(\d+)d(\d+)', dice_str.lower())
    if match:
        return int(match.group(1)), int(match.group(2))
    return 1, 4  # Default fallback


class TileEffectCondition(BaseCondition):
    """
    Base condition applied to tiles by zone spells.

    The target_entity_uuid is the tile's UUID.
    Subclasses override _apply() to add specific effects (terrain modifiers,
    damage handlers, obscurement, etc.).

    This is a minimal base class - spell-specific logic belongs in subclasses.
    """
    name: str = "Tile Effect"
    description: str = "A tile effect from a zone spell"

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
        """Subclasses must override to add specific effects.

        Default implementation does nothing - returns empty lists.
        """
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
    """Lightweight marker applied to tiles in a zone spell.
    Pure data — no handlers, no modifiers. Just carries:
    - name (zone spell name shown in API)
    - hazard_filter (pathfinding avoidance)
    - condition_stealth_dc (perception check to detect)
    """
    condition_category: ConditionCategory = ConditionCategory.CONDITION

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], [], [], [], effect_event


class SpikeTrapCondition(TileEffectCondition):
    """Marker condition on spike trap tiles. Does NOT create handlers —
    the shared spatial handler handles damage. This is purely for:
    - hazard_filter → pathfinding knows to avoid
    - condition_stealth_dc → perception check to detect
    - condition shows in API → display/agent sees "Spike Trap"
    """
    name: str = "Spike Trap"
    description: str = "Sharp spikes deal damage when stepped on"
    hazard_filter: HazardFilter = HazardFilter.ALL
    condition_category: ConditionCategory = ConditionCategory.CONDITION

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], [], [], [], effect_event


class ZoneControlCondition(BaseCondition):
    """
    Base condition for controlling a zone of tile effects.

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
    name: str = "Zone Control"
    description: str = "Controls a zone of tile effects"

    # Zone geometry
    zone_center: Tuple[int, int] = Field(default=(0, 0), description="Center position of the zone")
    zone_shape: str = Field(default="sphere", description="Shape: 'sphere', 'cone', 'line', 'cube'")
    zone_radius_feet: int = Field(default=20, description="Radius/size in feet")
    zone_direction: Optional[Tuple[int, int]] = Field(default=None, description="Direction for cones/lines")

    # Terrain effects
    adds_difficult_terrain: bool = Field(default=False, description="If True, adds +1 to walking cost")

    # Light effects
    sets_light_level: Optional[LightLevel] = Field(default=None, description="Light level to apply to zone tiles")
    light_is_obscurement: bool = Field(default=False, description="If True, uses add_obscurement(); else add_illumination()")

    # Track affected positions as a set for efficient operations
    affected_positions: Set[Tuple[int, int]] = Field(default_factory=set, description="Currently affected tile positions")

    # Zone-level handler UUIDs (ONE per effect type, not per tile)
    _entry_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _exit_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _turn_start_handler_uuid: Optional[UUID] = PrivateAttr(default=None)

    # Terrain modifier tracking (separate from handlers)
    # Maps tile.walking_cost.uuid -> [modifier_uuid, ...]
    _terrain_modifier_uuids: Dict[UUID, List[UUID]] = PrivateAttr(default_factory=dict)

    # Light modifier tracking (separate from handlers)
    # Maps tile position -> light modifier UUID used with add_illumination/add_obscurement
    _light_modifier_uuids: Dict[Tuple[int, int], UUID] = PrivateAttr(default_factory=dict)

    # Tile marker fields — subclasses set these for pathfinding/display
    marker_name: Optional[str] = Field(default=None, description="Name for ZoneMarkerCondition on each tile (e.g. 'Spike Growth'). None = no markers.")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=None, description="HazardFilter for tile markers")
    marker_stealth_dc: Optional[int] = Field(default=None, description="Stealth DC for tile markers (perception to detect)")

    model_config = {"arbitrary_types_allowed": True}

    # =========================================================================
    # Override Points for Subclasses
    # =========================================================================

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
        """Create the zone-level entry handler.

        Override in subclasses. This handler will be registered for ALL
        positions in the zone - no need to check position in the processor.
        """
        raise NotImplementedError("Subclass must implement _create_zone_entry_handler")

    def _create_zone_exit_handler(self) -> EventHandler:
        """Create the zone-level exit handler.

        Override in subclasses. This handler will be registered for ALL
        positions in the zone - no need to check position in the processor.
        """
        raise NotImplementedError("Subclass must implement _create_zone_exit_handler")

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create a turn start handler for entities in the zone.

        Note: Turn start handlers are NOT spatial handlers - they use normal
        trigger registration and check position in the processor.
        """
        raise NotImplementedError("Subclass must implement _create_zone_turn_start_handler")

    # =========================================================================
    # Geometry
    # =========================================================================

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
        }

        ShapeClass = shape_classes.get(self.zone_shape, Sphere)

        # Create shape instance
        if self.zone_shape in ("cone", "line") and self.zone_direction:
            shape = ShapeClass(
                source_entity_uuid=self.source_entity_uuid,
                target=self.zone_center,
                radius_feet=self.zone_radius_feet,
                direction=self.zone_direction
            )
        else:
            shape = ShapeClass(
                source_entity_uuid=self.source_entity_uuid,
                target=self.zone_center,
                radius_feet=self.zone_radius_feet
            )

        shape.compute_objective(self.zone_center)
        return set(shape.affected_positions)

    # =========================================================================
    # Terrain Modifiers (separate from event handlers)
    # =========================================================================

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
                    value=1  # +1 to walking cost (total = 2)
                )
                mod_uuid = tile.walking_cost.self_static.add_value_modifier(mod)
                self._terrain_modifier_uuids[tile.walking_cost.uuid] = [mod_uuid]
                outs.append((tile.walking_cost.uuid, mod_uuid))
                modified_positions.append(pos)

        # Fire batched path notification for all modified tiles
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
                        pass  # Modifier already removed
        self._terrain_modifier_uuids.clear()

        # Fire batched path notification if terrain modifiers were removed
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

    # =========================================================================
    # Tile Markers (zone name + hazard info on each tile)
    # =========================================================================

    def _apply_tile_markers(self, parent_event: Optional[Event] = None) -> None:
        """Apply ZoneMarkerCondition to each tile in the zone.
        Markers are tracked via linked_conditions → auto-cleanup when zone ends."""
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
            )
            tile.add_condition(marker, event=parent_event)
            self.add_linked_condition(tile.uuid, marker.uuid)

        # Fire batched path notification so safe paths recompute
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

    # =========================================================================
    # Light Modifiers (separate from terrain modifiers)
    # =========================================================================

    def _apply_light_modifiers(self) -> None:
        """Apply light level modifiers to affected tiles.

        Uses fire_event=False per tile + batch event after, same pattern
        as GridMap._apply_light_source().
        """
        if self.sets_light_level is None:
            return

        grid = get_map()
        changed_positions: List[Tuple[int, int]] = []
        for pos in self.affected_positions:
            tile = grid.get_tile(*pos)
            if tile:
                modifier_uuid = uuid4()
                if self.light_is_obscurement:
                    if tile.add_obscurement(modifier_uuid, self.sets_light_level, fire_event=False):
                        changed_positions.append(pos)
                else:
                    if tile.add_illumination(modifier_uuid, self.sets_light_level, fire_event=False):
                        changed_positions.append(pos)
                self._light_modifier_uuids[pos] = modifier_uuid

        # Batch event for all actually-changed positions
        grid._fire_light_batch_events(changed_positions)

    def _remove_light_modifiers(self) -> None:
        """Remove light level modifiers from affected tiles.

        Uses fire_event=False per tile + batch event after.
        """
        grid = get_map()
        changed_positions: List[Tuple[int, int]] = []
        for pos, modifier_uuid in self._light_modifier_uuids.items():
            tile = grid.get_tile(*pos)
            if tile:
                if tile.remove_light_modifier(modifier_uuid, fire_event=False):
                    changed_positions.append(pos)
        self._light_modifier_uuids.clear()

        # Batch event for all actually-changed positions
        grid._fire_light_batch_events(changed_positions)

    # =========================================================================
    # Core Apply / Remove / Move
    # =========================================================================

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply zone control - compute positions and register spatial handlers."""
        handler_uuids: List[UUID] = []
        spatial_handler_uuids: List[UUID] = []

        # Compute affected positions
        self.affected_positions = self._compute_affected_positions()

        # Create and register entry handler using position-indexed spatial registration
        if self._has_entry_effect():
            handler = self._create_zone_entry_handler()
            EventQueue.add_spatial_handler(
                handler,
                self.affected_positions,
                EventType.SPATIAL_ENTITY_ENTERED,
                EventPhase.EFFECT
            )
            self._entry_handler_uuid = handler.uuid
            spatial_handler_uuids.append(handler.uuid)

        # Create and register exit handler if needed
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

        # Turn start handler (not spatial - uses normal trigger)
        if self._has_turn_start_effect():
            handler = self._create_zone_turn_start_handler()
            EventQueue.add_event_handler(handler)
            self._turn_start_handler_uuid = handler.uuid
            handler_uuids.append(handler.uuid)

        # Apply terrain modifiers and get modifier pairs for tracking
        terrain_modifiers = self._apply_terrain_modifiers()

        # Apply light modifiers to zone tiles
        self._apply_light_modifiers()

        # Apply tile markers (zone name + hazard info for pathfinding/display)
        self._apply_tile_markers(parent_event=declaration_event)

        if declaration_event is not None:
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        else:
            effect_event = None

        return terrain_modifiers, handler_uuids, [], spatial_handler_uuids, effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Custom removal logic - clean up spatial handlers and modifiers.

        Called by parent's remove() method during removal process.
        """
        # Remove spatial handlers from position indices
        if self._entry_handler_uuid:
            EventQueue.remove_spatial_handler(self._entry_handler_uuid)
            self._entry_handler_uuid = None

        if self._exit_handler_uuid:
            EventQueue.remove_spatial_handler(self._exit_handler_uuid)
            self._exit_handler_uuid = None

        if self._turn_start_handler_uuid:
            # Turn start handler is in the normal event_handlers_uuids list,
            # so parent's remove_event_handlers() will handle it, but clear our ref
            self._turn_start_handler_uuid = None

        # Remove terrain modifiers
        self._remove_terrain_modifiers()

        # Remove light modifiers
        self._remove_light_modifiers()

        # Call parent _remove for standard event progression
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
        # Remove old terrain modifiers and light modifiers
        self._remove_terrain_modifiers()
        self._remove_light_modifiers()

        # Compute new positions
        self.zone_center = new_center
        new_positions = self._compute_affected_positions()

        # Batch update handler positions (efficient - only changes delta)
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

        # Apply terrain modifiers and light modifiers to new positions
        self._apply_terrain_modifiers()
        self._apply_light_modifiers()

        return True

    # =========================================================================
    # Legacy Compatibility: Tile Effect Pattern
    # =========================================================================

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
