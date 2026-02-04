"""
Tile condition system for zone spells and terrain effects.

Provides base classes for:
- ZoneControlCondition: Applied to caster, manages a zone of tile effects
- TileEffectCondition: Applied to individual tiles, provides the actual effect

Zone Spell Pattern:
    Caster: Concentrating(spell_name="Fog Cloud")
        +-- external_conditions -> FogCloudZone (on caster)
                +-- terrain_conditions -> FogCloudTileEffect (on each tile)
"""

import re
from typing import List, Optional, Tuple, Type
from uuid import UUID
from pydantic import Field

from dnd.core.base_conditions import BaseCondition
from dnd.core.events import Event, EventPhase, EventType, EventHandler, Trigger
from dnd.core.modifiers import NumericalModifier, DamageType
from dnd.core.dice import Dice, RollType
from dnd.core.values import ModifiableValue


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

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], Optional[Event]]:
        """Apply tile effect modifiers and handlers."""
        from dnd.core.gridmap import get_map

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        # target_entity_uuid is the tile UUID
        if self.target_entity_uuid is None:
            return [], [], [], None

        grid = get_map()
        tile = grid.get_tile_by_uuid(self.target_entity_uuid)
        if not tile:
            return [], [], [], None

        # Apply difficult terrain modifier
        if self.adds_difficult_terrain:
            mod = NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name=f"{self.name} Difficult Terrain",
                value=1  # +1 to walking cost (total = 2)
            )
            mod_uuid = tile.walking_cost.self_static.add_value_modifier(mod)
            outs.append((tile.walking_cost.uuid, mod_uuid))

        # Register entry damage handler if needed
        if self.damage_on_entry_dice:
            handler = self._create_entry_damage_handler(tile.uuid)
            handler_uuids.append(handler.uuid)

        # Register turn start damage handler if needed
        if self.damage_on_turn_start_dice:
            handler = self._create_turn_start_damage_handler(tile.uuid)
            handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return outs, handler_uuids, [], effect_event

    def _create_entry_damage_handler(self, tile_uuid: UUID) -> EventHandler:
        """Create an event handler that deals damage when entities enter this tile."""
        from dnd.core.events import SpatialChangeType

        damage_dice_str = self.damage_on_entry_dice
        damage_type = self.damage_on_entry_type
        source_uuid = self.source_entity_uuid

        def entry_damage_processor(event: Event, _handler_source_uuid: UUID) -> Optional[Event]:
            """Deal damage when entity enters the tile."""
            from dnd.core.gridmap import get_map
            from dnd.entity import Entity

            # Check event type
            if not hasattr(event, 'change_type'):
                return None
            if event.change_type != SpatialChangeType.ENTITY_ENTERED:  # type: ignore
                return None

            # Check position matches this tile
            grid = get_map()
            tile = grid.get_tile_by_uuid(tile_uuid)
            if not tile or tile.position != event.position:  # type: ignore
                return None

            # Get entering entity
            if not hasattr(event, 'entity_uuid'):
                return None
            entity = Entity.get(event.entity_uuid)  # type: ignore
            if not entity:
                return None

            # Deal damage
            if damage_dice_str:
                count, value = parse_dice_string(damage_dice_str)
                bonus = ModifiableValue.create(source_entity_uuid=source_uuid, base_value=0, value_name="Damage Bonus")
                dice = Dice(count=count, value=value, bonus=bonus, roll_type=RollType.DAMAGE)
                roll = dice.roll
                entity.health.take_damage(
                    roll.total,
                    damage_type,
                    source_entity_uuid=source_uuid
                )

            return None

        handler = EventHandler(
            name=f"{self.name} Entry Damage",
            source_entity_uuid=tile_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=entry_damage_processor
        )
        return handler

    def _create_turn_start_damage_handler(self, tile_uuid: UUID) -> EventHandler:
        """Create an event handler that deals damage at turn start if entity is on tile."""
        damage_dice_str = self.damage_on_turn_start_dice
        damage_type = self.damage_on_turn_start_type
        source_uuid = self.source_entity_uuid

        def turn_start_damage_processor(event: Event, _handler_source_uuid: UUID) -> Optional[Event]:
            """Deal damage at turn start if entity is on this tile."""
            from dnd.core.gridmap import get_map
            from dnd.entity import Entity

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

            # Deal damage
            if damage_dice_str:
                count, value = parse_dice_string(damage_dice_str)
                bonus = ModifiableValue.create(source_entity_uuid=source_uuid, base_value=0, value_name="Damage Bonus")
                dice = Dice(count=count, value=value, bonus=bonus, roll_type=RollType.DAMAGE)
                roll = dice.roll
                entity.health.take_damage(
                    roll.total,
                    damage_type,
                    source_entity_uuid=source_uuid
                )

            return None

        handler = EventHandler(
            name=f"{self.name} Turn Start Damage",
            source_entity_uuid=tile_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=turn_start_damage_processor
        )
        return handler


class ZoneControlCondition(BaseCondition):
    """
    Base condition for controlling a zone of tile effects.

    Applied to the caster. Manages affected tiles via terrain_conditions.
    When this condition is removed, all tile effects are automatically cleaned up.

    Subclasses should:
    1. Override get_tile_effect_class() to return the TileEffectCondition subclass to use
    2. Override _compute_affected_positions() if using custom geometry
    """
    name: str = "Zone Control"
    description: str = "Controls a zone of tile effects"

    # Zone geometry
    zone_center: Tuple[int, int] = Field(default=(0, 0), description="Center position of the zone")
    zone_shape: str = Field(default="sphere", description="Shape: 'sphere', 'cone', 'line', 'cube'")
    zone_radius_feet: int = Field(default=20, description="Radius/size in feet")
    zone_direction: Optional[Tuple[int, int]] = Field(default=None, description="Direction for cones/lines")

    # Track affected positions
    affected_positions: List[Tuple[int, int]] = Field(default_factory=list, description="Currently affected tile positions")

    # Tile effect class name (for serialization - actual class set at runtime)
    tile_effect_class_name: str = Field(default="TileEffectCondition", description="Name of TileEffectCondition subclass to use")

    def get_tile_effect_class(self) -> Type[TileEffectCondition]:
        """Get the TileEffectCondition class to use for this zone.

        Override in subclasses to return the specific tile effect class.
        Default returns base TileEffectCondition.
        """
        return TileEffectCondition

    def _compute_affected_positions(self) -> List[Tuple[int, int]]:
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
        return list(shape.affected_tiles)

    def _apply_to_tiles(self, _declaration_event: Event) -> None:
        """Apply tile effect conditions to all affected tiles."""
        from dnd.core.gridmap import get_map

        tile_effect_class = self.get_tile_effect_class()
        grid = get_map()

        for pos in self.affected_positions:
            tile = grid.get_tile(*pos)
            if tile:
                # Create tile effect condition
                effect = tile_effect_class(
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=tile.uuid,
                    parent_condition=self.uuid
                )
                tile.add_condition(effect)

                # Track in terrain_conditions for automatic cleanup
                self.add_terrain_condition(tile.uuid, effect.uuid)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], Optional[Event]]:
        """Apply zone control - compute positions and apply tile effects."""
        # Compute affected positions
        self.affected_positions = self._compute_affected_positions()

        # Apply tile effects
        self._apply_to_tiles(declaration_event)

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], [], [], effect_event

    def move_zone(self, new_center: Tuple[int, int]) -> bool:
        """Move the zone to a new position.

        Removes old tile effects and applies to new positions.
        Returns False if move is invalid.
        """
        # Remove from old positions (via terrain_conditions)
        self.remove_terrain_conditions()
        self.affected_positions.clear()

        # Update center
        self.zone_center = new_center
        self.affected_positions = self._compute_affected_positions()

        # Apply to new positions (need a dummy event for _apply_to_tiles)
        # In practice, moving a zone would fire its own event
        dummy_event = Event(
            name="Zone Move",
            source_entity_uuid=self.source_entity_uuid,
            phase=EventPhase.EFFECT
        )
        self._apply_to_tiles(dummy_event)

        return True
