"""
Tile condition system for zone spells and terrain effects.

Provides base classes for:
- ZoneControlCondition: Applied to caster, manages a zone of tile effects
- TileEffectCondition: Applied to individual tiles, provides the actual effect

Zone Spell Pattern:
    Caster: Concentrating(spell_name="Fog Cloud")
        +-- external_conditions -> FogCloudZone (on caster)
                +-- terrain_conditions -> FogCloudTileEffect (on each tile)

Event Handling:
- SPATIAL events now fire through full lifecycle: DECLARATION -> EXECUTION -> EFFECT -> COMPLETION
- Entry damage handlers fire at EFFECT phase using standard EventHandlers
- Turn start damage handlers also fire at EFFECT phase
- SpatialSensesCallback still uses callbacks for passive senses updates at COMPLETION
"""

import re
from typing import List, Optional, Tuple, Type, Set, Dict

from dnd.core.base_tiles import Tile
from uuid import UUID
from pydantic import Field, PrivateAttr

from dnd.core.base_conditions import BaseCondition
from dnd.core.events import Event, EventPhase, EventType, EventHandler, SpatialHandler, EventQueue, Trigger
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier, DamageType
from dnd.core.values import ModifiableValue
import random
from dnd.entity import Entity


def parse_dice_string(dice_str: str) -> Tuple[int, int]:
    """Parse a dice string like '2d4' into (count, value)."""
    match = re.match(r'(\d+)d(\d+)', dice_str.lower())
    if match:
        return int(match.group(1)), int(match.group(2))
    return 1, 4  # Default fallback


class TileEffectCondition(BaseCondition):
    """
    Base condition applied to tiles by zone spells.

    Handles common patterns: cost modification, entry damage, obscurement.
    The target_entity_uuid is the tile's UUID.

    Subclasses should override _apply() to add specific effects.

    Event Handling:
    - Entry damage uses position-indexed spatial handlers for O(1) lookup
    - Turn start damage uses EventHandler at EFFECT phase (not spatial)
    """
    name: str = "Tile Effect"
    description: str = "A tile effect from a zone spell"

    # Effect properties (override in subclasses)
    adds_difficult_terrain: bool = Field(default=False, description="If True, adds +1 to walking cost")
    heavily_obscured: bool = Field(default=False, description="Blocks vision through this tile")
    lightly_obscured: bool = Field(default=False, description="Provides light obscurement")

    # Damage on entry (optional)
    damage_on_entry_dice: Optional[str] = Field(default=None, description="Dice string like '2d4' for entry damage")
    damage_on_entry_type: DamageType = Field(default=DamageType.PIERCING, description="Damage type")

    # Damage at turn start (optional)
    damage_on_turn_start_dice: Optional[str] = Field(default=None, description="Dice string for turn start damage")
    damage_on_turn_start_type: DamageType = Field(default=DamageType.FIRE, description="Damage type for turn start")

    # Private attribute to track the entry handler UUID for cleanup
    _entry_handler_uuid: Optional[UUID] = PrivateAttr(default=None)

    model_config = {"arbitrary_types_allowed": True}

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply tile effect modifiers and handlers."""
        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []
        spatial_handler_uuids: List[UUID] = []

        # target_entity_uuid is the tile UUID
        if self.target_entity_uuid is None:
            return [], [], [], [], None

        grid = get_map()
        tile = grid.get_tile_by_uuid(self.target_entity_uuid)
        if not tile:
            return [], [], [], [], None

        # Apply difficult terrain modifier
        if self.adds_difficult_terrain:
            mod = NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name=f"{self.name} Difficult Terrain",
                value=1  # +1 to walking cost (total = 2)
            )
            mod_uuid = tile.walking_cost.self_static.add_value_modifier(mod)
            outs.append((tile.walking_cost.uuid, mod_uuid))

        # Register entry damage handler using SpatialHandler class
        if self.damage_on_entry_dice:
            handler = self._create_entry_damage_handler(tile)
            EventQueue.add_spatial_handler(handler)
            self._entry_handler_uuid = handler.uuid
            spatial_handler_uuids.append(handler.uuid)

        # Register turn start damage handler (NOT spatial - uses normal triggers)
        if self.damage_on_turn_start_dice:
            handler = self._create_turn_start_damage_handler(tile.uuid)
            EventQueue.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        if declaration_event is not None:
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        else:
            effect_event = None
        return outs, handler_uuids, [], spatial_handler_uuids, effect_event

    def _create_entry_damage_handler(self, tile: Tile) -> SpatialHandler:
        """Create a spatial handler that deals damage when entities enter this tile.

        Uses SpatialHandler class for position-indexed lookup (O(1)).
        Position check is handled by the registry - no need to check in processor.
        """
        damage_dice_str = self.damage_on_entry_dice
        damage_type = self.damage_on_entry_type
        source_uuid = self.source_entity_uuid

        def entry_damage_processor(event: Event, _handler_source_uuid: UUID) -> Optional[Event]:
            """Deal damage when entity enters this tile.

            Position already validated by SpatialHandler registry - no need to check.
            """
            # Get entering entity
            entity_uuid = getattr(event, 'entity_uuid', None)
            if not entity_uuid:
                return None
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            # Deal damage (simple roll, no attack required)
            if damage_dice_str:
                count, value = parse_dice_string(damage_dice_str)
                damage = sum(random.randint(1, value) for _ in range(count))
                entity.health.take_damage(
                    damage,
                    damage_type,
                    source_entity_uuid=source_uuid
                )

            return None

        return SpatialHandler(
            name=f"{self.name} Entry Damage",
            source_entity_uuid=tile.uuid,
            positions={tile.position},  # Single position
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_processor=entry_damage_processor
        )

    def _create_turn_start_damage_handler(self, tile_uuid: UUID) -> EventHandler:
        """Create an event handler that deals damage at turn start if entity is on tile."""
        damage_dice_str = self.damage_on_turn_start_dice
        damage_type = self.damage_on_turn_start_type
        source_uuid = self.source_entity_uuid

        def turn_start_damage_processor(event: Event, _handler_source_uuid: UUID) -> Optional[Event]:
            """Deal damage at turn start if entity is on this tile."""
            if event.event_type != EventType.TURN_START:
                return None

            # Get entity whose turn is starting
            entity = Entity.get(event.source_entity_uuid)
            if not entity:
                return None

            # Check if entity is on this tile
            grid = get_map()
            tile = grid.get_tile_by_uuid(tile_uuid)
            if not tile:
                return None

            if entity.senses.position != tile.position:
                return None

            # Deal damage (simple roll, no attack required)
            if damage_dice_str:
                count, value = parse_dice_string(damage_dice_str)
                damage = sum(random.randint(1, value) for _ in range(count))
                entity.health.take_damage(
                    damage,
                    damage_type,
                    source_entity_uuid=source_uuid
                )

            return None

        return EventHandler(
            name=f"{self.name} Turn Start Damage",
            source_entity_uuid=tile_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=turn_start_damage_processor
        )

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up spatial handler for entry damage.

        Entry damage handlers are now tracked in spatial_handler_uuids and
        cleaned up by parent class's remove_spatial_handlers().
        Turn start handlers are tracked in event_handlers_uuids and
        cleaned up by parent class's remove_event_handlers().
        """
        # Clear local reference (cleanup happens in parent)
        self._entry_handler_uuid = None
        return super()._remove(event)


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

    # Track affected positions as a set for efficient operations
    affected_positions: Set[Tuple[int, int]] = Field(default_factory=set, description="Currently affected tile positions")

    # Zone-level handler UUIDs (ONE per effect type, not per tile)
    _entry_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _exit_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _turn_start_handler_uuid: Optional[UUID] = PrivateAttr(default=None)

    # Terrain modifier tracking (separate from handlers)
    # Maps tile.walking_cost.uuid -> [modifier_uuid, ...]
    _terrain_modifier_uuids: Dict[UUID, List[UUID]] = PrivateAttr(default_factory=dict)

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
        from dnd.core.aoe import Sphere, Cone, Line, Cube

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
        return outs

    def _remove_terrain_modifiers(self) -> None:
        """Remove terrain modifiers before zone move or removal."""
        for value_uuid, mod_uuids in self._terrain_modifier_uuids.items():
            value = ModifiableValue.get(value_uuid)
            if value is not None:
                for mod_uuid in mod_uuids:
                    try:
                        value.self_static.remove_modifier(mod_uuid)
                    except (ValueError, KeyError):
                        pass  # Modifier already removed
        self._terrain_modifier_uuids.clear()

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
        # Remove old terrain modifiers
        self._remove_terrain_modifiers()

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

        # Apply terrain modifiers to new positions
        self._apply_terrain_modifiers()

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
                self.add_terrain_condition(tile.uuid, effect.uuid)
