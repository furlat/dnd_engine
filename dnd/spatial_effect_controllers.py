"""Reusable geometric controllers for independently owned spatial effects."""

from typing import Callable, List, Optional, Tuple, Set, Dict

from dnd.core.base_block import LightLevel
from uuid import UUID, uuid4
from pydantic import Field, PrivateAttr

from dnd.core.base_conditions import SpellProtectionRegistry
from dnd.core.effect_types import EffectOriginKind
from dnd.core.events import Event, EventPhase, EventType, EventHandler, EventQueue, SpatialChangeEvent, SensesUpdateHint
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.core.spatial_effect_types import SpatialEffectTriggerKind
from dnd.core.values import ModifiableValue
from dnd.core.aoe import Sphere, Cone, Line, Cube, Cylinder
from dnd.entity import Entity
from dnd.spatial_effects import SpatialEffect, SpatialEffectController


class AreaSpatialEffectController(SpatialEffectController):
    """Shared geometric mechanics for one independently owned spatial effect.

    Canonical spatial effects install this condition on their exact
    ``SpatialEffect`` owner. Position-indexed handlers provide O(1) entry/exit
    lookup instead of O(tiles) handlers.

    Key architecture:
    - ONE handler per effect type per zone (not per tile)
    - Handlers are registered via EventQueue.add_spatial_handler() with position set
    - Zone movement uses EventQueue.update_spatial_handler_positions() for O(delta) updates
    - Terrain modifiers (difficult terrain) are separate from event handlers

    Controller subclasses should:
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
    _turn_end_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _terrain_modifier_uuids: Dict[UUID, List[UUID]] = PrivateAttr(default_factory=dict)
    _light_modifier_uuids: Dict[Tuple[int, int], UUID] = PrivateAttr(default_factory=dict)
    _last_trigger_turn_by_target: Dict[UUID, UUID] = PrivateAttr(
        default_factory=dict,
    )

    model_config = {"arbitrary_types_allowed": True}

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create the zone-level entry handler for all affected positions."""
        raise NotImplementedError("Subclass must implement _create_zone_entry_handler")

    def _create_zone_exit_handler(self) -> EventHandler:
        """Create the zone-level exit handler for all affected positions."""
        raise NotImplementedError("Subclass must implement _create_zone_exit_handler")

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create a normal event handler for turn starts inside the zone."""
        raise NotImplementedError("Subclass must implement _create_zone_turn_start_handler")

    def _create_zone_turn_end_handler(self) -> EventHandler:
        """Create a normal event handler for turn ends inside the zone."""
        raise NotImplementedError("Subclass must implement _create_zone_turn_end_handler")

    def _apply_appearance_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Apply this controller's explicitly authored APPEAR consequence."""
        del entity, parent_event
        raise NotImplementedError(
            f"{type(self).__name__} declares APPEAR without an implementation",
        )

    def _apply_effect_entry_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Apply a rule triggered by the effect moving onto one occupant."""
        del entity, parent_event
        raise NotImplementedError(
            f"{type(self).__name__} declares EFFECT_ENTERS_OCCUPANT "
            "without an implementation",
        )

    def _apply_effect_exit_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Apply a rule triggered by an effect moving away from an occupant."""
        del entity, parent_event
        raise NotImplementedError(
            f"{type(self).__name__} declares EFFECT_LEAVES_OCCUPANT "
            "without an implementation",
        )

    def _admit_trigger(
        self,
        trigger_kind: SpatialEffectTriggerKind,
        target_entity_uuid: UUID,
        event: Event,
    ) -> bool:
        """Admit a trigger, enforcing exact first-per-turn semantics."""
        if trigger_kind not in self.first_per_turn_trigger_kinds:
            return True
        turn_execution_id = event.turn_execution_id
        if turn_execution_id is None:
            return True
        if (
            self._last_trigger_turn_by_target.get(target_entity_uuid)
            == turn_execution_id
        ):
            return False
        self._last_trigger_turn_by_target[target_entity_uuid] = turn_execution_id
        return True

    def _wrap_processor_with_trigger_admission(
        self,
        original_processor: Callable[[Event, UUID], Optional[Event]],
        trigger_kind: SpatialEffectTriggerKind,
    ) -> Callable[[Event, UUID], Optional[Event]]:
        """Apply one effect/target/turn admission fence around a processor."""
        def wrapped(event: Event, source_uuid: UUID) -> Optional[Event]:
            target_uuid = (
                event.entity_uuid
                if isinstance(event, SpatialChangeEvent)
                else event.source_entity_uuid
            )
            if target_uuid is None:
                return None
            if not self._admit_trigger(trigger_kind, target_uuid, event):
                return None
            return original_processor(event, source_uuid)

        return wrapped

    def apply_appearance_trigger(self, *, parent_event: Event) -> None:
        """Apply APPEAR only when the authored controller declares it."""
        if SpatialEffectTriggerKind.APPEAR not in self.trigger_kinds:
            return
        grid = get_map()
        occupant_uuids = {
            entity_uuid
            for position in self.affected_positions
            for entity_uuid in grid.get_entities_at(position)
        }
        spell_level = self._protection_spell_level()
        source = Entity.get(self.source_entity_uuid)
        source_position = source.position if source is not None else (0, 0)
        for entity_uuid in sorted(occupant_uuids, key=str):
            entity = Entity.get(entity_uuid)
            if entity is None:
                continue
            if (
                spell_level is not None
                and self.magical_origin
                and SpellProtectionRegistry.is_protected(
                    entity.position,
                    source_position,
                    spell_level,
                )
            ):
                continue
            if not self._admit_trigger(
                SpatialEffectTriggerKind.APPEAR,
                entity.uuid,
                parent_event,
            ):
                continue
            self._apply_appearance_effect(entity, parent_event=parent_event)

    def apply_effect_entry_trigger(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Apply an explicitly authored moving-area consequence."""
        trigger_kind = SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT
        if trigger_kind not in self.trigger_kinds:
            return
        grid = get_map()
        occupant_uuids = {
            entity_uuid
            for position in positions
            for entity_uuid in grid.get_entities_at(position)
        }
        spell_level = self._protection_spell_level()
        source = Entity.get(self.source_entity_uuid)
        source_position = source.position if source is not None else (0, 0)
        for entity_uuid in sorted(occupant_uuids, key=str):
            entity = Entity.get(entity_uuid)
            if entity is None:
                continue
            if (
                spell_level is not None
                and self.magical_origin
                and SpellProtectionRegistry.is_protected(
                    entity.position,
                    source_position,
                    spell_level,
                )
            ):
                continue
            if not self._admit_trigger(trigger_kind, entity.uuid, parent_event):
                continue
            self._apply_effect_entry_effect(
                entity,
                parent_event=parent_event,
            )

    def apply_effect_exit_trigger(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Apply an explicitly authored moving-area departure consequence."""
        trigger_kind = SpatialEffectTriggerKind.EFFECT_LEAVES_OCCUPANT
        if trigger_kind not in self.trigger_kinds:
            return
        grid = get_map()
        occupant_uuids = {
            entity_uuid
            for position in positions
            for entity_uuid in grid.get_entities_at(position)
        }
        for entity_uuid in sorted(occupant_uuids, key=str):
            entity = Entity.get(entity_uuid)
            if entity is None:
                continue
            self._apply_effect_exit_effect(
                entity,
                parent_event=parent_event,
            )

    def _effect_host(self) -> Optional[SpatialEffect]:
        """Return the explicit spatial owner when hosted independently."""
        if self.target_entity_uuid is None:
            return None
        return SpatialEffect.get_effect(self.target_entity_uuid)

    def _protection_spell_level(self) -> Optional[int]:
        """Return the explicit base spell level used by globe protection."""
        if (
            self.effect_origin is None
            or self.effect_origin.kind is not EffectOriginKind.SPELL
        ):
            return None
        return self.effect_origin.base_spell_level

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
        elif self.zone_shape == "cube":
            shape = Cube(
                source_entity_uuid=self.source_entity_uuid,
                target=self.zone_center,
                size_feet=self.zone_radius_feet,
                centered=True,
            )
        elif self.zone_shape == "cylinder":
            shape = Cylinder(
                source_entity_uuid=self.source_entity_uuid,
                target=self.zone_center,
                radius_feet=self.zone_radius_feet,
            )
        else:
            shape = Sphere(
                source_entity_uuid=self.source_entity_uuid,
                target=self.zone_center,
                radius_feet=self.zone_radius_feet,
            )

        shape.compute_objective(self.zone_center)
        return set(shape.affected_positions)

    def resolve_effect_footprint(self) -> Set[Tuple[int, int]]:
        """Resolve valid cells after map bounds and spell protection."""
        grid = get_map()
        positions = {
            position
            for position in self._compute_affected_positions()
            if grid.has_tile(*position)
        }
        spell_level = self._protection_spell_level()
        if spell_level is None or not self.magical_origin:
            return positions
        source = Entity.get(self.source_entity_uuid)
        if source is None:
            return positions
        return positions - SpellProtectionRegistry.get_excluded_positions(
            source.position,
            spell_level,
        )

    def rollback_failed_install(self) -> None:
        """Release every lease created before a failed controller commit."""
        for handler_uuid in (
            self._entry_handler_uuid,
            self._exit_handler_uuid,
        ):
            if handler_uuid is not None:
                EventQueue.remove_spatial_handler(handler_uuid)
        for handler_uuid in (
            self._turn_start_handler_uuid,
            self._turn_end_handler_uuid,
        ):
            if handler_uuid is None:
                continue
            handler = EventHandler.get(handler_uuid)
            if isinstance(handler, EventHandler):
                handler.remove()
        self._entry_handler_uuid = None
        self._exit_handler_uuid = None
        self._turn_start_handler_uuid = None
        self._turn_end_handler_uuid = None
        self._remove_terrain_modifiers()
        self._remove_light_modifiers()

    def _apply_terrain_modifiers(
        self,
        positions: Optional[Set[Tuple[int, int]]] = None,
    ) -> List[Tuple[UUID, UUID]]:
        """Apply difficult terrain modifiers to affected tiles.

        Args:
            positions: Optional position subset. Defaults to the whole zone.

        Returns:
            List of (value_uuid, modifier_uuid) pairs for tracking in modifers_uuids.
        """
        outs: List[Tuple[UUID, UUID]] = []
        if not self.adds_difficult_terrain:
            return outs

        grid = get_map()
        modified_positions: List[Tuple[int, int]] = []
        target_positions = (
            positions if positions is not None else self.affected_positions
        )
        for pos in target_positions:
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
            grid.invalidate_spatial_caches({"movement"})
            hint = SensesUpdateHint(requires_paths=True)
            representative_pos = modified_positions[0]
            tile = grid.get_tile(*representative_pos)
            if tile:
                event = SpatialChangeEvent.tile_changed(
                    representative_pos, walkable=True, visible=True,
                    senses_hint=hint,
                )
                EventQueue.publish_lifecycle(event)

        return outs

    def _remove_terrain_modifiers_from_positions(
        self,
        positions: Optional[Set[Tuple[int, int]]] = None,
    ) -> bool:
        """Remove terrain modifiers through one batched invalidation path.

        Args:
            positions: Position subset to remove. ``None`` removes every
                modifier still owned by this zone.

        Returns:
            True when at least one owned modifier was removed.
        """
        grid = get_map()
        representative_positions = (
            set(self.affected_positions) if positions is None else positions
        )
        owned_modifiers: List[Tuple[UUID, List[UUID]]]
        if positions is None:
            owned_modifiers = list(self._terrain_modifier_uuids.items())
            self._terrain_modifier_uuids.clear()
        else:
            owned_modifiers = []
            for position in positions:
                tile = grid.get_tile(*position)
                if tile is None:
                    continue
                value_uuid = tile.walking_cost.uuid
                modifier_uuids = self._terrain_modifier_uuids.pop(
                    value_uuid,
                    [],
                )
                if modifier_uuids:
                    owned_modifiers.append((value_uuid, modifier_uuids))

        removed_any = bool(owned_modifiers)
        for value_uuid, modifier_uuids in owned_modifiers:
            value = ModifiableValue.get(value_uuid)
            if value is not None:
                for modifier_uuid in modifier_uuids:
                    try:
                        value.remove_modifier(modifier_uuid)
                    except (ValueError, KeyError):
                        continue
            tracked_modifiers = self.modifers_uuids.get(value_uuid)
            if tracked_modifiers is not None:
                self.modifers_uuids[value_uuid] = [
                    modifier_uuid
                    for modifier_uuid in tracked_modifiers
                    if modifier_uuid not in modifier_uuids
                ]
                if not self.modifers_uuids[value_uuid]:
                    del self.modifers_uuids[value_uuid]

        if not removed_any:
            return False
        grid.invalidate_spatial_caches({"movement"})
        hint = SensesUpdateHint(requires_paths=True)
        representative_position = next(iter(representative_positions), None)
        if representative_position is not None:
            tile = grid.get_tile(*representative_position)
            if tile is not None:
                event = SpatialChangeEvent.tile_changed(
                    representative_position,
                    walkable=True,
                    visible=True,
                    senses_hint=hint,
                )
                EventQueue.publish_lifecycle(event)
        return True

    def _remove_terrain_modifiers(self) -> None:
        """Remove every terrain modifier through the batched primitive."""
        self._remove_terrain_modifiers_from_positions()

    def _remove_terrain_modifier_at(self, position: Tuple[int, int]) -> bool:
        """Remove this zone's difficult-terrain modifier from one tile.

        Args:
            position: Grid position whose terrain modifier should be removed.

        Returns:
            True if a modifier was removed from the tile.
        """
        return self._remove_terrain_modifiers_from_positions({position})

    def _apply_light_modifiers(
        self,
        positions: Optional[Set[Tuple[int, int]]] = None,
    ) -> None:
        """Apply light level modifiers to affected tiles.

        Uses fire_event=False per tile + batch event after, same pattern
        as GridMap._apply_light_source().
        """
        if self.sets_light_level is None:
            return

        grid = get_map()
        changed_positions: List[Tuple[int, int]] = []
        requires_fov = False
        target_positions = (
            positions if positions is not None else self.affected_positions
        )
        for pos in target_positions:
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

    def _remove_light_modifiers_from_positions(
        self,
        positions: Optional[Set[Tuple[int, int]]] = None,
    ) -> bool:
        """Remove light modifiers through one batched event path.

        Args:
            positions: Position subset to remove. ``None`` removes every
                modifier still owned by this zone.

        Returns:
            True when at least one tile's resolved light state changed.
        """
        grid = get_map()
        changed_positions: List[Tuple[int, int]] = []
        requires_fov = False
        target_positions = (
            set(self._light_modifier_uuids)
            if positions is None
            else positions
        )
        for position in target_positions:
            modifier_uuid = self._light_modifier_uuids.pop(position, None)
            if modifier_uuid is None:
                continue
            tile = grid.get_tile(*position)
            if tile is None:
                continue
            old_light_level = tile.resolved_light_level
            if tile.remove_light_modifier(modifier_uuid, fire_event=False):
                changed_positions.append(position)
                if (
                    old_light_level == LightLevel.MAGICAL_DARKNESS
                    or tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS
                ):
                    requires_fov = True

        grid._fire_light_batch_events(
            changed_positions,
            requires_fov=requires_fov,
        )
        return bool(changed_positions)

    def _remove_light_modifiers(self) -> None:
        """Remove every light modifier through the batched primitive."""
        self._remove_light_modifiers_from_positions()

    def _remove_light_modifier_at(self, position: Tuple[int, int]) -> bool:
        """Remove this zone's light or obscurement modifier from one tile.

        Args:
            position: Grid position whose light modifier should be removed.

        Returns:
            True if a tile light state changed.
        """
        return self._remove_light_modifiers_from_positions({position})

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

    def transition_footprint(
        self,
        remaining_positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Shrink zone-owned mechanics before the effect index commits."""
        if not remaining_positions:
            raise ValueError("Empty zone transition must retire its effect")
        if not remaining_positions.issubset(self.affected_positions):
            raise ValueError(
                "Spatial-effect transition cannot add controller positions",
            )
        removed_positions = self.affected_positions - remaining_positions
        for position in removed_positions:
            self._remove_terrain_modifier_at(position)
            self._remove_light_modifier_at(position)
        self.affected_positions = set(remaining_positions)
        self._sync_spatial_handler_positions()

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply zone control by computing positions and registering handlers."""
        handler_uuids: List[UUID] = []
        spatial_handler_uuids: List[UUID] = []

        self.affected_positions = self.resolve_installation_footprint()
        effect_host = self._effect_host()
        if effect_host is None:
            raise RuntimeError(
                "AreaSpatialEffectController requires an independent "
                "SpatialEffect owner",
            )
        spell_level = self._protection_spell_level()

        if SpatialEffectTriggerKind.ENTER in self.trigger_kinds:
            handler = self._create_zone_entry_handler()
            handler.event_processor = self._wrap_processor_with_trigger_admission(
                handler.event_processor,
                SpatialEffectTriggerKind.ENTER,
            )
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

        if SpatialEffectTriggerKind.LEAVE in self.trigger_kinds:
            handler = self._create_zone_exit_handler()
            handler.event_processor = self._wrap_processor_with_trigger_admission(
                handler.event_processor,
                SpatialEffectTriggerKind.LEAVE,
            )
            EventQueue.add_spatial_handler(
                handler,
                self.affected_positions,
                EventType.SPATIAL_ENTITY_LEFT,
                EventPhase.EFFECT
            )
            self._exit_handler_uuid = handler.uuid
            spatial_handler_uuids.append(handler.uuid)

        if SpatialEffectTriggerKind.TURN_START in self.trigger_kinds:
            handler = self._create_zone_turn_start_handler()
            handler.event_processor = self._wrap_processor_with_trigger_admission(
                handler.event_processor,
                SpatialEffectTriggerKind.TURN_START,
            )
            if spell_level is not None and self.magical_origin:
                handler.event_processor = self._wrap_processor_with_protection(
                    handler.event_processor, self.source_entity_uuid, spell_level)
            EventQueue.add_event_handler(handler)
            self._turn_start_handler_uuid = handler.uuid
            handler_uuids.append(handler.uuid)

        if SpatialEffectTriggerKind.TURN_END in self.trigger_kinds:
            handler = self._create_zone_turn_end_handler()
            handler.event_processor = self._wrap_processor_with_trigger_admission(
                handler.event_processor,
                SpatialEffectTriggerKind.TURN_END,
            )
            if spell_level is not None and self.magical_origin:
                handler.event_processor = self._wrap_processor_with_protection(
                    handler.event_processor,
                    self.source_entity_uuid,
                    spell_level,
                )
            EventQueue.add_event_handler(handler)
            self._turn_end_handler_uuid = handler.uuid
            handler_uuids.append(handler.uuid)

        terrain_modifiers = self._apply_terrain_modifiers()

        self._apply_light_modifiers()

        effect_host.synchronize_footprint(self.affected_positions)

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

        if self._turn_end_handler_uuid:
            self._turn_end_handler_uuid = None

        self._remove_terrain_modifiers()
        self._remove_light_modifiers()

        return super()._remove(event)

    def move_zone(
        self,
        new_center: Tuple[int, int],
        *,
        parent_event: Event,
    ) -> bool:
        """Move every zone-owned spatial fact using one position delta.

        This method:
        1. Computes removed, retained, and added positions
        2. Removes terrain and light facts only from removed cells
        3. Updates shared spatial handler indices once
        4. Applies terrain and light facts only to added cells

        Returns True on success.
        """
        old_positions = set(self.affected_positions)
        self.zone_center = new_center
        new_positions = self._compute_affected_positions()
        grid = get_map()
        new_positions = {
            position
            for position in new_positions
            if grid.has_tile(*position)
        }
        removed_positions = old_positions - new_positions
        added_positions = new_positions - old_positions

        self._remove_terrain_modifiers_from_positions(removed_positions)
        self._remove_light_modifiers_from_positions(removed_positions)

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
        effect_host = self._effect_host()
        if effect_host is None:
            raise RuntimeError(
                "AreaSpatialEffectController lost its SpatialEffect owner",
            )
        effect_host.set_position(new_center)
        change_event = effect_host.synchronize_footprint(
            new_positions,
            parent_event=parent_event,
        )
        self.apply_effect_exit_trigger(
            removed_positions,
            parent_event=change_event or parent_event,
        )
        self.apply_effect_entry_trigger(
            added_positions,
            parent_event=change_event or parent_event,
        )

        self._apply_terrain_modifiers(added_positions)
        self._apply_light_modifiers(added_positions)

        return True

    def relocate_anchor(
        self,
        position: Tuple[int, int],
        *,
        parent_event: Event,
    ) -> None:
        """Recenter an attached zone through the shared delta-movement path."""
        self.move_zone(position, parent_event=parent_event)
