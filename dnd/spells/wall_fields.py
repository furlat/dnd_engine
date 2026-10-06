"""Permeable wall fields composed from geometry, area triggers and damage facts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dnd.actions import SpellAction, SpellEvent, entity_action_economy_cost_evaluator
from dnd.core.action_types import ActionVariantFacet, PositionPathSelection, PositionSelection, SinglePositionSelection
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import ConditionTag, DurationType, HazardFilter
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.registration import behavior_content_ref
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.creature_types import DamageType, Size
from dnd.core.dice import AttackOutcome
from dnd.core.events import Damage, Event, EventHandler, EventPhase, EventQueue, EventType, SpatialEffectChangeEvent, SpatialEffectInteractionEvent, Range, RangeType, SpatialChangeEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallPolyline, WallRing, WallSegment
from dnd.core.wall_geometry import wall_path_contact, wall_shell_cells
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition, SpatialCondition
from dnd.types.abilities import AbilityName
from dnd.types.physical_access import PhysicalAccess
from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.spatial_effects import SpatialDamageSource, SpatialEffectChangeOperation, SpatialEffectInteractionIntensity, SpatialEffectInteractionOperation, SpatialEffectLayer, SpatialEffectOccupancyPolicy, SpatialEffectTriggerKind
from dnd.types.world import MovementMode, OccupancyLayer


def wall_condition_ref(identity: str) -> ContentRef:
    return behavior_content_ref(definition_kind=ContentDefinitionKind.CONDITION,
        runtime_behavior_kind=RuntimeBehaviorKind.CONDITION, pack_id="content.srd_5_1_cc",
        content_id=identity, version=1)


class WallDamageSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dice_count: int = Field(ge=1)
    die: Literal[6, 8]
    damage_type: DamageType
    save_ability: AbilityName
    effect_id: str


def apply_wall_damage(zone: AreaCondition, entity: Entity, spec: WallDamageSpec,
                      dc: int, parent_event: Event, base_height_steps: int,
                      contact_position: tuple[int, int] | None = None, *, formation: bool = False) -> None:
    caster = Entity.get(zone.source_entity_uuid)
    if caster is None:
        return
    request = entity.create_saving_throw_request(target_entity_uuid=entity.uuid,
        ability_name=spec.save_ability, dc=dc, parent_event=parent_event.uuid,
        saving_throw_context=zone.saving_throw_context(effect_id=spec.effect_id))
    _, _, success = entity.saving_throw(request)
    damage = Damage(source_entity_uuid=caster.uuid, target_entity_uuid=entity.uuid,
        damage_dice=spec.die, dice_numbers=spec.dice_count,
        damage_bonus=caster.get_spell_damage_bonus(), damage_type=spec.damage_type)
    roll = damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
    entity.receive_damage(roll.total // 2 if success else roll.total, spec.damage_type, caster.uuid,
        damage_rolls=[roll], damages=[damage], parent_event=parent_event.uuid, effect_id=spec.effect_id,
        independent_resolution=not formation, effect_origin=zone.effect_origin,
        spatial_source=SpatialDamageSource(spatial_effect_uuid=zone.uuid, position=contact_position or entity.position,
            target_position=entity.position, base_height_steps=base_height_steps, exposure="contact"))


class WallFieldZone(AreaCondition):
    """Data-authored appearance/contact packets over one permeable wall footprint."""

    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    geometry: WallAssemblyPresentationGeometry
    spell_dc: int
    formation_damage: WallDamageSpec | None = None
    contact_damage: WallDamageSpec | None = None
    has_visible_presence: bool = True
    hazard_filter: HazardFilter = HazardFilter.ALL
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    affected_occupancy_layers: frozenset[OccupancyLayer] = frozenset({OccupancyLayer.GROUND, OccupancyLayer.AIR})

    def resolve_condition_footprint(self) -> set[tuple[int, int]]:
        return self._apply_spell_protection({p for p in wall_shell_cells(self.geometry) if get_map().has_tile(*p)})

    def get_spatial_observation(self, positions: set[tuple[int, int]], *, observer_uuid,
                                discovered=False) -> PerceivedSpatialEffect | None:
        observed = SpatialCondition.get_spatial_observation(self, positions,
            observer_uuid=observer_uuid, discovered=discovered)
        return observed.model_copy(update={"area_geometry": self.geometry,
            "anchor_elevation_steps": self.geometry.base_height_steps}) if observed is not None else None

    def _apply_appearance_effect(self, entity: Entity, *, parent_event: Event) -> None:
        if self.formation_damage is not None:
            apply_wall_damage(self, entity, self.formation_damage, self.spell_dc,
                parent_event, self.geometry.base_height_steps, formation=True)

    def admits_occupancy_transition(self, event: SpatialChangeEvent) -> bool:
        if not super().admits_occupancy_transition(event):
            return False
        return not (event.event_type is EventType.SPATIAL_ENTITY_ENTERED
                    and event.old_position in self.affected_positions
                    and (event.previous_occupancy_layer is None
                         or self.affects_occupancy_layer(event.previous_occupancy_layer)))

    def _create_zone_entry_handler(self) -> EventHandler:
        def process(event: Event, _source) -> Event | None:
            if isinstance(event, SpatialChangeEvent) and event.entity_uuid is not None:
                entity = Entity.get(event.entity_uuid)
                if entity is not None and self.contact_damage is not None:
                    apply_wall_damage(self, entity, self.contact_damage, self.spell_dc,
                        event, self.geometry.base_height_steps,
                        contact_position=self.damage_contact_position(event, entity))
            return None
        return EventHandler(name=f"{self.name} passage", source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED, event_phase=EventPhase.EFFECT)],
            event_processor=process)

    def damage_contact_position(self, event: SpatialChangeEvent, entity: Entity) -> tuple[int, int]:
        return entity.position

    def _create_zone_turn_end_handler(self) -> EventHandler:
        def process(event: Event, _source) -> Event | None:
            entity = Entity.get(event.source_entity_uuid) if event.source_entity_uuid is not None else None
            if entity is not None and self.contact_damage is not None:
                apply_wall_damage(self, entity, self.contact_damage, self.spell_dc,
                    event, self.geometry.base_height_steps)
            return None
        return EventHandler(name=f"{self.name} turn end", source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT)],
            event_processor=process)


class WallOfThornsZone(WallFieldZone):
    name: str = "Wall of Thorns"
    description: str = "Opaque thorns require four feet of movement per foot and cut passing creatures."
    content_ref: ContentRef = wall_condition_ref("spatial_effect.spell.wall_of_thorns")
    blocks_physical_optics: bool = True
    movement_expenditure_extra: float = 3
    duration: Duration = Field(default_factory=lambda: Duration(duration=100, duration_type=DurationType.ROUNDS))
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.APPEAR,
        SpatialEffectTriggerKind.ENTER, SpatialEffectTriggerKind.TURN_END})
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.ENTER})


class WindWallZone(WallFieldZone):
    name: str = "Wind Wall"
    description: str = "Transparent wind keeps gas and small flying bodies back and deflects ordinary missiles."
    content_ref: ContentRef = wall_condition_ref("spatial_effect.spell.wind_wall")
    duration: Duration = Field(default_factory=lambda: Duration(duration=10, duration_type=DurationType.ROUNDS))
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.APPEAR})


    def blocks_crossing_between(self, start, end, channel, requester_uuid, mode, terminal_provider_uuid=None) -> bool:
        if channel != "movement" or wall_path_contact(self.geometry, start, end,
                {cell for cell in self.affected_positions if self.allows_contribution_at(cell)}) is None:
            return False
        actor = Entity.get(requester_uuid) if requester_uuid is not None else None
        return actor is not None and (actor.gaseous_body
            or mode is MovementMode.FLYING and actor.size in {Size.TINY, Size.SMALL})

    def missile_deflection_contact(self, start, end, missile_size) -> tuple[float, float] | None:
        return wall_path_contact(self.geometry, start, end,
                {cell for cell in self.affected_positions if self.allows_contribution_at(cell)}) if missile_size == "ordinary" else None

    def _emit_wind_exposure(self, parent_event: Event) -> None:
        interaction = EventQueue.publish_declaration(SpatialEffectInteractionEvent(
            source_entity_uuid=self.source_entity_uuid, operation=SpatialEffectInteractionOperation.DISPERSE,
            positions=tuple(sorted(cell for cell in self.affected_positions if self.allows_contribution_at(cell))), intensity=SpatialEffectInteractionIntensity.STRONG,
            parent_event=parent_event.uuid, phase=EventPhase.DECLARATION, use_register=False))
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT, EventPhase.COMPLETION):
            if interaction.canceled:
                break
            interaction = interaction.phase_to(phase)

    def _apply(self, execution_event: Event):
        modifiers, handlers, children, spatial_handlers, effect = super()._apply(execution_event)
        def process(event: Event, _source) -> Event | None:
            if isinstance(event, SpatialEffectChangeEvent):
                if (event.spatial_effect_uuid == self.uuid or event.layer is not SpatialEffectLayer.CLOUD
                        or event.operation not in {SpatialEffectChangeOperation.CREATED,
                                                  SpatialEffectChangeOperation.FOOTPRINT_CHANGED}):
                    return None
                if not self.affected_positions.intersection(event.affected_positions):
                    return None
            self._emit_wind_exposure(event)
            return None
        handler = EventHandler(name="Maintained Wind Wall gas exposure", source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_START, event_phase=EventPhase.EFFECT,
                                        event_source_entity_uuid=self.source_entity_uuid),
                                Trigger(event_type=EventType.SPATIAL_EFFECT_CHANGED, event_phase=EventPhase.COMPLETION)],
            event_processor=process)
        EventQueue.add_event_handler(handler)
        handlers.append(handler.uuid)
        self._emit_wind_exposure(effect)
        return modifiers, handlers, children, spatial_handlers, effect


def field_geometry(action: SpellAction, *, form: str, height: int, width: int) -> WallAssemblyPresentationGeometry | None:
    if action.end_position is None:
        return None
    points = action.get_selected_position_path()
    if points is not None and any(a == b for a, b in zip(points, points[1:])):
        return None
    if form == "ring":
        path = WallRing(center=action.end_position, radius_feet=10)
        anchor = action.end_position
    elif points is not None and len(points) >= 2:
        path = WallPolyline(points=tuple(points)) if form == "path" else WallSegment(start=points[0], end=points[-1])
        anchor = points[0]
    else:
        return None
    tile = get_map().get_tile(*anchor)
    return WallAssemblyPresentationGeometry(path=path, base_height_steps=tile.height,
        height_feet=height, width_feet=width) if tile is not None else None


def wall_support_error(action: SpellAction, geometry: WallAssemblyPresentationGeometry | None,
                       *, subjective: bool) -> str | None:
    caster = Entity.get(action.source_entity_uuid)
    if caster is None or geometry is None or action.end_position is None:
        return "Select complete wall placement"
    error = action.target_position_error(action.end_position)
    if error is not None:
        return error
    grid = get_map()
    for position in wall_shell_cells(geometry):
        tile = grid.get_tile(*position)
        if tile is None or tile.height != geometry.base_height_steps or tile.get_movement_cost(MovementMode.WALKING) <= 0:
            return "Wall requires a supported footprint on one level"
        if grid.is_blocking_propagation(*position, observer_uuid=caster.uuid if subjective else None):
            return "Existing solid geometry obstructs the wall"
    points = action.get_selected_position_path()
    if not isinstance(geometry.path, WallRing) and points is not None:
        for first, second in zip(points, points[1:]):
            if not grid.can_reach_between(first, second, PhysicalAccess.PROJECTILE,
                                           caster.uuid, subjective=subjective):
                return "A solid boundary crosses the wall"
    elif isinstance(geometry.path, WallRing):
        shell = wall_shell_cells(geometry)
        for x, y in shell:
            for dx, dy in ((1, 0), (0, 1)):
                neighbor = x + dx, y + dy
                if (neighbor in shell and not grid.can_reach_between((x, y), neighbor,
                        PhysicalAccess.PROJECTILE, caster.uuid, subjective=subjective)):
                    return "A solid boundary crosses the wall"
    return None


class WallOfThorns(SpellAction):
    name: str = "Wall of Thorns"
    description: str = "Create an opaque, permeable straight or circular wall of cutting thorns."
    spell_level: int = 6
    spell_school: str = "conjuration"
    harmful: bool = True
    concentration: bool = True
    spell_damage_type: DamageType = DamageType.PIERCING
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=120))
    target_type: TargetType = TargetType.POSITION_LOS
    physical_access: PhysicalAccess = PhysicalAccess.PROJECTILE
    wall_form: Literal["segment", "ring"] = "segment"
    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Wall of Thorns action", cost_type="actions",
        cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def wall_geometry(self) -> WallAssemblyPresentationGeometry | None:
        return field_geometry(self, form=self.wall_form, height=10, width=5)

    def get_position_selection(self) -> PositionSelection:
        return (SinglePositionSelection() if self.wall_form == "ring" else PositionPathSelection(
            max_length_feet=60, max_segments=1, allow_origin_start=True, origin_start_offset_cells=1))

    def _create_declaration_event(self, parent_event=None, use_register=True) -> Event | None:
        event = super()._create_declaration_event(parent_event, use_register)
        return event.with_updates(area_geometry=self.wall_geometry()) if isinstance(event, SpellEvent) else event

    def selection_preview_error(self) -> str | None:
        return self.position_selection_error() or self.position_placement_error(subjective=True)

    def get_selection_geometry(self):
        return self.wall_geometry()

    def position_placement_error(self, *, subjective=False) -> str | None:
        return wall_support_error(self, self.wall_geometry(), subjective=subjective)

    def _validate(self, declaration_event: SpellEvent) -> SpellEvent | None:
        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: SpellEvent) -> SpellEvent | None:
        caster = Entity.get(self.source_entity_uuid)
        geometry = self.wall_geometry()
        if caster is None or geometry is None or self.end_position is None:
            return execution_event.cancel(status_message="Wall placement unavailable")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        count = 7 + self.cast_at_level - 6
        points = self.get_selected_position_path()
        zone = WallOfThornsZone(source_entity_uuid=caster.uuid,
            position=points[0] if self.wall_form != "ring" and points is not None else self.end_position,
            geometry=geometry, spell_dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
            formation_damage=WallDamageSpec(dice_count=count, die=8, damage_type=DamageType.PIERCING,
                save_ability="dexterity", effect_id="wall_of_thorns.appearance"),
            contact_damage=WallDamageSpec(dice_count=count, die=8, damage_type=DamageType.SLASHING,
                save_ability="dexterity", effect_id="wall_of_thorns.exposure"),
            effect_origin=execution_event.to_effect_origin())
        result = zone.activate(parent_event=effect)
        if result is not None and not result.canceled and zone.applied:
            self.ensure_concentration(effect).add_linked_condition(zone.uuid, zone.uuid)
            return effect
        return effect.cancel(status_message="Thorn wall creation was canceled")

    def get_variant_facets(self) -> tuple[ActionVariantFacet, ...]:
        return (ActionVariantFacet(key="form", value=self.wall_form, label=self.wall_form.title()),)

    def get_discovery_variants(self, entity) -> list[BaseAction]:
        return [slot.model_copy(update={"wall_form": form}) for slot in super().get_discovery_variants(entity)
                for form in ("segment", "ring")]

    def get_discovery_template_name(self) -> str:
        return f"{super().get_discovery_template_name()}__wall_{self.wall_form}"


class WindWall(SpellAction):
    name: str = "Wind Wall"
    description: str = "Create a continuous ground path of wind, up to fifty feet long."
    spell_level: int = 3
    spell_school: str = "evocation"
    harmful: bool = True
    concentration: bool = True
    spell_damage_type: DamageType = DamageType.BLUDGEONING
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=120))
    target_type: TargetType = TargetType.POSITION_LOS
    physical_access: PhysicalAccess = PhysicalAccess.PROJECTILE
    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Wind Wall action", cost_type="actions",
        cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def wall_geometry(self) -> WallAssemblyPresentationGeometry | None:
        return field_geometry(self, form="path", height=15, width=1)

    def get_position_selection(self) -> PositionSelection:
        return PositionPathSelection(max_length_feet=50, max_segments=10,
            allow_origin_start=True, origin_start_offset_cells=1)

    def _create_declaration_event(self, parent_event=None, use_register=True) -> Event | None:
        event = super()._create_declaration_event(parent_event, use_register)
        return event.with_updates(area_geometry=self.wall_geometry()) if isinstance(event, SpellEvent) else event

    def selection_preview_error(self) -> str | None:
        return self.position_selection_error() or self.position_placement_error(subjective=True)

    def get_selection_geometry(self):
        return self.wall_geometry()

    def position_placement_error(self, *, subjective=False) -> str | None:
        return wall_support_error(self, self.wall_geometry(), subjective=subjective)

    def _validate(self, declaration_event: SpellEvent) -> SpellEvent | None:
        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: SpellEvent) -> SpellEvent | None:
        caster = Entity.get(self.source_entity_uuid)
        geometry = self.wall_geometry()
        points = self.get_selected_position_path()
        if caster is None or geometry is None or points is None:
            return execution_event.cancel(status_message="Wind path unavailable")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        zone = WindWallZone(source_entity_uuid=caster.uuid, position=points[0], geometry=geometry,
            spell_dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
            formation_damage=WallDamageSpec(dice_count=3, die=8, damage_type=DamageType.BLUDGEONING,
                save_ability="strength", effect_id="wind_wall.appearance"),
            effect_origin=execution_event.to_effect_origin())
        result = zone.activate(parent_event=effect)
        if result is not None and not result.canceled and zone.applied:
            self.ensure_concentration(effect).add_linked_condition(zone.uuid, zone.uuid)
            return effect
        return effect.cancel(status_message="Wind wall creation was canceled")
