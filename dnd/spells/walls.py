"""Native wall spells composed from existing spatial, damage and action owners."""

from typing import Literal
from math import hypot

from pydantic import Field

from dnd.actions import SpellAction, SpellEvent, entity_action_economy_cost_evaluator
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.core.action_types import PositionSelection, PositionPathSelection, SinglePositionSelection
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import ConditionTag, DurationType, HazardFilter
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.registration import behavior_content_ref
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.events import Damage, Event, EventHandler, EventPhase, EventType, Range, RangeType, SpatialChangeEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.core.presentation_geometry import WallPresentationGeometry, WallRing, WallSegment
from dnd.core.wall_geometry import wall_shell_cells, wall_side_cells
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition, SpatialCondition
from dnd.spatial.ignition import ignite_surface_contacts
from dnd.types.physical_access import PhysicalAccess
from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.spatial_effects import SpatialDamageSource, SpatialEffectLayer, SpatialEffectOccupancyPolicy, SpatialEffectTriggerKind
from dnd.types.world import MovementMode, OccupancyLayer


HotSide = Literal["left", "right", "inside", "outside"]

WALL_OF_FIRE_REF = behavior_content_ref(
    definition_kind=ContentDefinitionKind.CONDITION,
    runtime_behavior_kind=RuntimeBehaviorKind.CONDITION,
    pack_id="content.srd_5_1_cc",
    content_id="spatial_effect.spell.wall_of_fire",
    version=1,
)


class WallOfFireZone(AreaCondition):
    """One owner for flame contact, hot-side heat, opacity and retirement."""

    name: str = "Wall of Fire"
    description: str = "Opaque, permeable flames burn on contact and radiate heat to the chosen side."
    content_ref: ContentRef = WALL_OF_FIRE_REF
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    hazard_filter: HazardFilter = HazardFilter.ALL
    affected_occupancy_layers: frozenset[OccupancyLayer] = frozenset({OccupancyLayer.GROUND, OccupancyLayer.AIR})
    has_visible_presence: bool = True
    blocks_physical_optics: bool = True
    geometry: WallPresentationGeometry
    hot_side: HotSide
    flame_positions: set[tuple[int, int]] = Field(default_factory=set)
    heat_positions: set[tuple[int, int]] = Field(default_factory=set)
    damage_dice_count: int = Field(default=5, ge=5)
    spell_dc: int
    duration: Duration = Field(default_factory=lambda: Duration(duration=10, duration_type=DurationType.ROUNDS))
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({
        SpatialEffectTriggerKind.APPEAR, SpatialEffectTriggerKind.ENTER, SpatialEffectTriggerKind.TURN_END,
    })
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.ENTER})

    def resolve_condition_footprint(self) -> set[tuple[int, int]]:
        grid = get_map()
        self.flame_positions = wall_shell_cells(self.geometry)
        heat = {cell for cell in wall_side_cells(self.geometry, self.hot_side, 10)
                if (tile := grid.get_tile(*cell)) is not None and tile.height == self.geometry.base_height_steps}
        # Heat is local exposure from the shell; it cannot travel through a solid
        # provider to a neighbor that happens to lie in the geometric band.
        self.heat_positions = {
            cell for cell in heat if any(self._heat_reaches(flame, cell) for flame in self.flame_positions)
        }
        footprint = self._apply_spell_protection(self.flame_positions | self.heat_positions)
        self.flame_positions.intersection_update(footprint)
        self.heat_positions.intersection_update(footprint)
        self.heat_positions = {cell for cell in self.heat_positions if any(
            self._heat_reaches(flame, cell)
            for flame in self.flame_positions
        )}
        return self.flame_positions | self.heat_positions

    def _heat_reaches(self, flame: tuple[int, int], cell: tuple[int, int]) -> bool:
        return (hypot(flame[0] - cell[0], flame[1] - cell[1]) * 5 <= 10
                and get_map().can_reach_between(flame, cell, PhysicalAccess.PROJECTILE, self.source_entity_uuid))

    def get_trigger_positions(self, kind: SpatialEffectTriggerKind) -> set[tuple[int, int]]:
        if kind in {SpatialEffectTriggerKind.APPEAR, SpatialEffectTriggerKind.ENTER}:
            return self.flame_positions & self.affected_positions
        return set(self.affected_positions)

    def admits_occupancy_transition(self, event: SpatialChangeEvent) -> bool:
        if not super().admits_occupancy_transition(event):
            return False
        if (event.event_type is EventType.SPATIAL_ENTITY_ENTERED
                and event.old_position in self.get_trigger_positions(SpatialEffectTriggerKind.ENTER)):
            return (event.previous_occupancy_layer is not None
                    and not self.affects_occupancy_layer(event.previous_occupancy_layer))
        return True

    def blocks_physical_optics_at(self, position: tuple[int, int]) -> bool:
        return position in self.flame_positions and position in self.affected_positions

    def get_spatial_observation(self, positions, *, observer_uuid, discovered=False) -> PerceivedSpatialEffect | None:
        flames = positions & self.flame_positions
        if not flames:
            return None
        observed = SpatialCondition.get_spatial_observation(
            self, flames, observer_uuid=observer_uuid, discovered=discovered,
        )
        return observed.model_copy(update={"area_geometry": self.geometry,
            "anchor_elevation_steps": self.geometry.base_height_steps}) if observed is not None else None

    def _deal_damage(self, entity: Entity, *, parent_event: Event, appearance: bool = False) -> None:
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return
        success = False
        if appearance:
            request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid, ability_name="dexterity", dc=self.spell_dc,
                parent_event=parent_event.uuid,
                saving_throw_context=self.saving_throw_context(effect_id="wall_of_fire.appearance"),
            )
            _, _, success = entity.saving_throw(request)
        damage = Damage(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=entity.uuid,
            damage_dice=8, dice_numbers=self.damage_dice_count,
            damage_bonus=caster.get_spell_damage_bonus(), damage_type=DamageType.FIRE,
        )
        roll = damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        contact = entity.position if entity.position in self.flame_positions else min(
            (position for position in self.flame_positions if self._heat_reaches(position, entity.position)),
            key=lambda position: (hypot(position[0] - entity.position[0], position[1] - entity.position[1]), position),
            default=None,
        )
        entity.receive_damage(
            roll.total // 2 if success else roll.total, DamageType.FIRE, self.source_entity_uuid,
            damage_rolls=[roll], damages=[damage], parent_event=parent_event.uuid,
            effect_id="wall_of_fire.appearance" if appearance else "wall_of_fire.exposure",
            spatial_source=SpatialDamageSource(spatial_effect_uuid=self.uuid, position=contact,
                target_position=entity.position, base_height_steps=self.geometry.base_height_steps,
                exposure="contact" if entity.position in self.flame_positions else "radiated_heat")
                if contact is not None else None,
        )

    def _apply_appearance_effect(self, entity: Entity, *, parent_event: Event) -> None:
        self._deal_damage(entity, parent_event=parent_event, appearance=True)

    def _create_zone_entry_handler(self) -> EventHandler:
        def process(event: Event, _source) -> Event | None:
            if isinstance(event, SpatialChangeEvent):
                entity = Entity.get(event.entity_uuid) if event.entity_uuid is not None else None
                if entity is not None:
                    self._deal_damage(entity, parent_event=event)
            return None
        return EventHandler(
            name="Wall of Fire contact", source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED, event_phase=EventPhase.EFFECT)],
            event_processor=process,
        )

    def _create_zone_turn_end_handler(self) -> EventHandler:
        def process(event: Event, _source) -> Event | None:
            entity = Entity.get(event.source_entity_uuid) if event.source_entity_uuid is not None else None
            if entity is not None:
                self._deal_damage(entity, parent_event=event)
            return None
        return EventHandler(
            name="Wall of Fire turn-end exposure", source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT)],
            event_processor=process,
        )


class WallOfFire(SpellAction):
    """Create an opaque, permeable straight or ring wall with one heated side."""

    name: str = "Wall of Fire"
    description: str = "Create an opaque wall of flame; choose the side radiating heat."
    spell_level: int = 4
    spell_school: str = "evocation"
    spell_damage_type: DamageType = DamageType.FIRE
    harmful: bool = True
    concentration: bool = True
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=120))
    target_type: TargetType = TargetType.POSITION_LOS
    physical_access: PhysicalAccess = PhysicalAccess.PROJECTILE
    wall_form: Literal["segment", "ring"] = "segment"
    wall_radius_feet: Literal[10] = 10
    hot_side: HotSide = "left"
    costs: list[Cost] = Field(default_factory=lambda: [Cost(
        name="Wall of Fire action", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator,
    )])

    def wall_geometry(self) -> WallPresentationGeometry | None:
        if self.end_position is None:
            return None
        if self.wall_form == "ring":
            path = WallRing(center=self.end_position, radius_feet=self.wall_radius_feet)
            anchor = self.end_position
        else:
            selected = self.get_selected_position_path()
            if selected is None or len(selected) != 2 or selected[0] == selected[1]:
                return None
            path = WallSegment(start=selected[0], end=selected[1])
            anchor = selected[0]
        support = get_map().get_tile(*anchor)
        if support is None:
            return None
        return WallPresentationGeometry(path=path, height_feet=20, width_feet=1,
            base_height_steps=support.height, hot_side=self.hot_side)

    def get_position_selection(self) -> PositionSelection:
        return PositionPathSelection(max_length_feet=60, max_segments=1,
            allow_origin_start=True, origin_start_offset_cells=1) if self.wall_form == "segment" else SinglePositionSelection()

    def _create_declaration_event(self, parent_event=None, use_register=True) -> Event | None:
        event = super()._create_declaration_event(parent_event, use_register)
        if isinstance(event, SpellEvent):
            return event.with_updates(area_geometry=self.wall_geometry())
        return event

    def position_placement_error(self, *, subjective: bool = False) -> str | None:
        caster = Entity.get(self.source_entity_uuid)
        geometry = self.wall_geometry()
        if caster is None or geometry is None:
            return "Wall needs a caster and complete placement"
        if self.end_position is None:
            return "Select a wall position"
        range_error = self.target_position_error(self.end_position)
        if range_error is not None:
            return range_error
        if not caster.senses.visible.get(self.end_position, False):
            return "Wall origin is not visible"
        allowed_sides = {"left", "right"} if self.wall_form == "segment" else {"inside", "outside"}
        if self.hot_side not in allowed_sides:
            return "Heated side does not match wall form"
        grid = get_map()
        shell = wall_shell_cells(geometry)
        for position in shell:
            tile = grid.get_tile(*position)
            if tile is None or tile.get_movement_cost(MovementMode.WALKING) <= 0 or tile.height != geometry.base_height_steps:
                return "Wall requires a continuous solid surface on one level"
            if grid.is_blocking_propagation(*position, observer_uuid=self.source_entity_uuid if subjective else None):
                return "Solid geometry obstructs the wall"
        if isinstance(geometry.path, WallSegment):
            selected = self.get_selected_position_path()
            if selected is None:
                return "Select wall endpoints"
            if not grid.can_reach_between(selected[0], selected[1],
                    PhysicalAccess.PROJECTILE, self.source_entity_uuid, subjective=subjective):
                return "A solid boundary crosses the wall"
        else:
            for first in shell:
                for dx, dy in ((1, 0), (0, 1)):
                    second = (first[0] + dx, first[1] + dy)
                    if second in shell and not grid.can_reach_between(first, second,
                            PhysicalAccess.PROJECTILE, self.source_entity_uuid, subjective=subjective):
                        return "A solid boundary crosses the wall"
        return None

    def _validate(self, declaration_event: SpellEvent) -> SpellEvent | None:
        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: SpellEvent) -> SpellEvent | None:
        caster = Entity.get(self.source_entity_uuid)
        geometry = self.wall_geometry()
        if caster is None or geometry is None or self.end_position is None:
            return execution_event.cancel(status_message="Wall placement is unavailable")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        selected = self.get_selected_position_path()
        anchor = selected[0] if selected is not None else self.end_position
        zone = WallOfFireZone(
            source_entity_uuid=caster.uuid, position=anchor, geometry=geometry,
            hot_side=self.hot_side, spell_dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
            damage_dice_count=5 + self.cast_at_level - 4, effect_origin=execution_event.to_effect_origin(),
        )
        result = zone.activate(parent_event=effect)
        if result is not None and not result.canceled and zone.applied:
            ignite_surface_contacts(effect, zone.flame_positions & zone.affected_positions)
            concentration = self.ensure_concentration(effect)
            concentration.add_linked_condition(zone.uuid, zone.uuid)
        return effect

    def get_discovery_variants(self, entity) -> list[BaseAction]:
        variants = []
        for slot in super().get_discovery_variants(entity):
            for side in ("left", "right"):
                variants.append(slot.model_copy(update={"wall_form": "segment", "hot_side": side}))
            for side in ("inside", "outside"):
                variants.append(slot.model_copy(update={"wall_form": "ring", "hot_side": side}))
        return variants

    def get_discovery_template_name(self) -> str:
        return f"{super().get_discovery_template_name()}__wall_{self.wall_form}_{self.hot_side}"

    def get_discovery_display_name(self) -> str:
        return f"{super().get_discovery_display_name()} · {self.wall_form}, heat {self.hot_side}"
