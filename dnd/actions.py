"""Concrete action implementations for combat, movement, spells, and objects."""

import time
from dataclasses import dataclass, replace
from types import MappingProxyType

from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_actions import (
    ActionDiscoveryDescription,
    ActionCategory,
    ActionEvent,
    ActionOutcomeProfile,
    BaseAction,
    BaseCost,
    Cost,
    CostType,
    DamageRollProfile,
    OutcomeApplicationScope,
    OutcomeResolution,
    PositionDiscoveryContract,
    TargetType,
    ActionTargetEffectProfile,
    spell_slot_cost_type,
    TargetEffectDisposition,
)
from dnd.core.attack_types import AttackSourceMetadata, NaturalWeaponSpec, ShieldAttackSpec
from dnd.core.values import (
    ModifiableValue,
    ValueRead,
    ValueReading,
    outgoing_of,
    read_value,
    Channel,
    Kind,
    Row,
    parts,
    value_breakdown,
    with_rows,
)
from dnd.core.spell_damage import finalize_spell_damage_roll
from dnd.core.condition_types import ConditionRemovalTrigger, DurationType
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus

from dnd.core.dice import  DiceRoll, AttackOutcome, RollType
from dnd.core.events import RangeType, Event, EventQueue, EventType, Range, Damage, EventPhase, DamageRollPacket, DamageRollResultEvent, StepMovementEvent, ForcedMovementEvent, TakeDamageEvent, DamageAppliedEvent, SkillCheckEvent, SpatialChangeEvent, MovementTrajectory, advantage_log_rows, value_log_rows
from dnd.types.abilities import AbilityName
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.spatial_effects import AreaPropagation
from dnd.spells.content_metadata import get_spell_catalog_metadata
from dnd.types.summoning import SummonApplication
from dnd.types.discovery import ActorScan
from dnd.core.elevation import support_distance_feet
from dnd.core.navigation import has_route, remember_blocked_cell, remember_blocked_sides, route
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.effect_types import EffectOrigin
from dnd.core.action_types import ActionAffordance, ActionSelection, ActionVariantFacet, CostSource, RestrictedActionKind
from dnd.blocks.spellcasting import FreeSpellCastGrant
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    behavior_identity,
    get_content_declaration,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.life_types import LifeState
from dnd.core.spell_execution import (
    SpellExecutionState,
    bind_spell_execution_lineage,
    current_spell_execution,
    spell_execution_scope,
)
from dnd.core.saving_throw_types import SavingThrowEffectTag
from dnd.core.action_execution import (
    MovementContinuationDecision,
    MovementProvocationPolicy,
    MovementStepBoundary,
    MovementTerminationReason,
    revalidate_after_committed_movement_step,
)
from dnd.core.traversal_connectors import (
    ConnectorActionCostType,
    ConnectorDestinationStatus,
    ConnectorProvocationPolicy,
    ConnectorTraversalDiscovery,
    TraversalConnector,
    TraversalConnectorCommand,
    TraversalConnectorEndpoint,
    TraversalConnectorKind,
)
from dnd.core.creature_types import DamageType
from dnd.core.gridmap import ConcealmentHolder, get_map
from dnd.core.concealment_types import (
    NOTICED_ON_OBJECTS, ConcealedAspect, Concealment, knower_key, knows, with_failure, with_knowers,
)
from dnd.core.view import cell_visible, visible_positions
from dnd.core.geometry import grid_distance_feet, position_in_sector
from dnd.core.presentation_geometry import AoEPresentationGeometry
from dnd.core.naming import normalize_spell_id
from dnd.core.base_block import BaseBlock, MovementMode, PreparedConditionApplication
from dnd.types.event_facts import LandingKind
from dnd.types.world import OccupancyLayer, WorldEdgeChannel
from dnd.core.base_block import LightLevel
from dnd.action_timing import record_action_elapsed, record_action_timing
from dnd.core.combat_log import JumpMovementLogData, ConnectorMovementLogData, EmptyLogData, ShoveLogData, SpellDamageLogData
from dnd.core.combat_log import (
    CombatLogEntry, CombatLogEntryType, ModifierBreakdown, DiceRollDisplay,
    DamageRollDisplay, AttackLogData, MovementLogData, SpellSaveLogData,
    format_attack_compact, format_attack_verbose, format_attack_detailed,
    md_color
)
from dnd.types.physical_access import ObjectContact, PhysicalAccess
from pydantic import BaseModel, Field, StrictBool, StrictInt, model_validator
from typing import AbstractSet, Annotated, Any, Callable, ClassVar, Dict, Iterable, Literal, Optional, List, Set, TypeVar, Tuple, Self, cast, final
from uuid import UUID, uuid4
from dnd.entity import Entity, determine_attack_outcome
from dnd.blocks.action_economy import (
    ActionEconomyChannelCost,
    FixedCostCommitError,
    NamedResourceCost,
)
from dnd.blocks.base_item import BaseItem
from dnd.blocks.sensory import spatial_senses_system
from dnd.conditions import AttackAssistance, ExtraAttacksGranted, Dashing, Dodging, Disengaging, Prone, Hidden, Concentrating
from dnd.core.base_object import empty_list


_CoreActionDefinition = TypeVar("_CoreActionDefinition")


def _core_action_identity(
    *,
    content_id: str,
    display_name: str,
    description: str,
    source_anchor: str,
    sort_order: int,
) -> Callable[[_CoreActionDefinition], _CoreActionDefinition]:
    """Declare one independently provided standard core action."""
    return behavior_identity(
        definition_kind=ContentDefinitionKind.ACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
        pack_id="core.rules",
        content_id=content_id,
        version=1,
        descriptor=ContentDescriptorSpec(
            display_name=display_name,
            description=description,
            tags=("action", "core", "srd"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(
                icon_key=content_id,
                visual_variant_key=content_id.removeprefix("action."),
                ui_group="actions.standard",
            ),
            ordering=ContentOrdering(
                sort_group="actions.standard",
                sort_order=sort_order,
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id="wotc.srd_5_1_cc",
            source_anchor=source_anchor,
            relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
            notes=(
                "Playable core action identity; implementation-specific "
                "targeting and presentation remain engine adaptations."
            ),
        ),
    )


def entity_resource_cost_evaluator(entity_uuid: UUID, resource_name: str, resource_cost: int) -> bool:
    """Check whether an entity can afford a named resource cost.

    Args:
        entity_uuid: Entity that would pay the resource.
        resource_name: Action economy resource name.
        resource_cost: Resource amount required.

    Returns:
        True if the entity exists and can afford the resource.
    """
    entity = Entity.get(entity_uuid)
    if entity is None or not isinstance(entity, Entity):
        return False
    return entity.action_economy.can_afford_resource(resource_name, resource_cost)


def entity_action_economy_cost_evaluator(source_entity_uuid: UUID, cost_type: CostType, cost: int) -> bool:
    """Check whether an entity can afford an action economy cost.

    Args:
        source_entity_uuid: Entity that would pay the cost.
        cost_type: Action economy bucket to inspect.
        cost: Amount required.

    Returns:
        True if the entity exists and can afford the cost.
    """
    entity = Entity.get(source_entity_uuid)
    if entity is None or not isinstance(entity, Entity):
        return False
    return entity.action_economy.can_afford(cost_type, cost)


def build_weapon_attack_outcome_profile(
    actor: Entity,
    weapon_slot: WeaponSlot,
    override_ability: Optional[AbilityName] = None,
    natural_weapon: Optional[NaturalWeaponSpec] = None,
    shield_attack: Optional[ShieldAttackSpec] = None,
) -> Optional[ActionOutcomeProfile]:
    """Build one actor-baseline weapon profile for all attack wrappers.

    Args:
        actor: Entity discovering the weapon attack.
        weapon_slot: Equipment slot used by the attack rule.
        override_ability: Optional ability selected by the action rule.

    Returns:
        Actor-owned stochastic data, or ``None`` for a slot without damage.
    """
    baseline = actor.weapon_attack_outcome_baseline(
        weapon_slot,
        override_ability,
        natural_weapon=natural_weapon, shield_attack=shield_attack,
    )
    damage_rolls = actor.weapon_damage_outcome_baseline(
        weapon_slot,
        override_ability,
        natural_weapon=natural_weapon, shield_attack=shield_attack,
    )
    if not damage_rolls:
        return None
    return ActionOutcomeProfile(
        resolution=OutcomeResolution.ATTACK_ROLL,
        damage_rolls=damage_rolls,
        attack_bonus=baseline.attack_bonus,
        advantage=baseline.advantage,
        critical_threshold=baseline.critical_threshold,
        critical_extra_dice=baseline.critical_extra_dice,
    )

PolymorphicActionEvent = TypeVar('PolymorphicActionEvent', bound='ActionEvent')


def _consume_entity_action_economy_costs(
    action_event: PolymorphicActionEvent,
    source_entity_uuid: UUID,
    *,
    excluded_cost_types: AbstractSet[CostType] = frozenset(),
) -> PolymorphicActionEvent:
    """Atomically commit serialized costs without advancing the lifecycle."""
    entity = Entity.get(source_entity_uuid)
    if entity is None or not isinstance(entity, Entity):
        return action_event.cancel(
            status_message=f"Entity not found for {action_event.name}"
        )
    channel_costs = tuple(
        ActionEconomyChannelCost(
            cost_type=cost.cost_type,
            amount=cost.cost,
            name=cost.name,
        )
        for cost in action_event.costs
        if cost.cost_type not in excluded_cost_types and cost.cost > 0
    )
    resource_costs = tuple(
        NamedResourceCost(
            name=cost.resource_name,
            amount=cost.resource_cost,
        )
        for cost in action_event.costs
        if cost.resource_name and cost.resource_cost > 0
    )
    if not channel_costs and not resource_costs:
        return action_event
    try:
        entity.action_economy.commit_fixed_costs_without_dispatch(
            channel_costs=channel_costs,
            resource_costs=resource_costs,
        )
    except FixedCostCommitError:
        return action_event.cancel(
            status_message=f"Failed to commit costs for {action_event.name}"
        )
    return action_event.model_copy(update={
        "action_economy_spent": action_event.action_economy_spent or bool(channel_costs or resource_costs),
    })


def entity_action_economy_cost_applier(
    action_event: PolymorphicActionEvent,
    source_entity_uuid: UUID,
) -> PolymorphicActionEvent:
    """Commit turn-based and named-resource costs before execution.

    Args:
        action_event: Detached execution proposal carrying serialized costs.
        source_entity_uuid: Entity that pays the costs.

    Returns:
        The unchanged proposal after an atomic commit, or a detached
        cancellation if the commit fails.
    """
    return _consume_entity_action_economy_costs(
        action_event,
        source_entity_uuid,
    )


def resolve_paid_entry_retreats(source: Entity, *, since_cursor: int, parent_event: Event) -> bool:
    """Resolve newly applied entry requests only after spatial publication completes."""
    requests = tuple(request for condition in tuple(source.active_conditions.values())
        if (request := condition.get_paid_entry_retreat(since_cursor=since_cursor)) is not None)
    for request in requests:
        if request.destination is None:
            continue
        source.materialize_navigation(max_distance=20)
        retreat = Move(source_entity_uuid=source.uuid, end_position=request.destination,
            path=[source.position, request.destination], prefer_safe=False)
        source.perform(retreat, retreat.current_selection(), parent_event=parent_event)
    # The original path stays interrupted even if the retreat removed its fear.
    return bool(requests)


def resolve_fall_damage(target: Entity, *, drop_feet: int, source_entity_uuid: UUID,
                        parent_event: Event, knock_prone: bool = True) -> int:
    """Resolve actual support loss through ordinary damage and condition owners."""
    dice_count = min(20, max(0, drop_feet) // 10)
    if not dice_count:
        return 0
    damage = Damage(name="Fall", source_entity_uuid=source_entity_uuid, target_entity_uuid=target.uuid, damage_dice=6, dice_numbers=dice_count,
        damage_bonus=parts(ModifiableValue(source_entity_uuid=source_entity_uuid, base=0)), damage_type=DamageType.BLUDGEONING)
    roll = damage.get_dice(AttackOutcome.HIT).roll
    applied = 0

    def record_damage(_incoming: TakeDamageEvent, result: DamageAppliedEvent | None) -> None:
        nonlocal applied
        if result is not None and result.phase is EventPhase.COMPLETION:
            applied = result.applied_damage

    target.receive_damage(roll.total, DamageType.BLUDGEONING,
        source_entity_uuid=source_entity_uuid, damage_rolls=[roll], damages=[damage],
        parent_event=parent_event.uuid, independent_resolution=True, on_completed=record_damage)
    if applied > 0 and knock_prone and target.health.life_state is not LifeState.DEAD:
        target.add_condition(Prone(source_entity_uuid=source_entity_uuid,
            target_entity_uuid=target.uuid), parent_event=parent_event)
    return applied


def commit_forced_movement(target: Entity, event: ForcedMovementEvent, *,
                           parent_event: Event, stop_on_incapacitation: bool = False,
                           on_landing: Callable[[ForcedMovementEvent], None] | None = None) -> ForcedMovementEvent:
    """Commit admitted displacement, resolve contact once, then entry responses."""
    if event.canceled:
        return event
    grid = get_map()
    start = target.position
    start_height = grid.get_support_elevation_feet(start)
    endpoint = start
    path = [start]
    interrupted = False
    blocked, blocked_by = event.blocked_by_obstacle, event.blocked_by
    kind = event.landing_kind
    drop_feet = 0
    entry_cursor = EventQueue.event_cursor()
    if kind in (LandingKind.CONTROLLED, LandingKind.IMPACT):
        admitted = grid.admit_airborne_transfer(start, event.end_position, target.uuid)
        if admitted is None:
            return event.cancel(status_message="Landing is no longer available")
        admitted_distance = max(0, min(event.actual_distance, event.intended_distance))
        path = [start]
        for position in admitted[1:]:
            if support_distance_feet(start, start_height, position,
                    grid.get_support_elevation_feet(position)) > admitted_distance:
                break
            path.append(position)
        destination = path[-1]
        if start != destination:
            # AIR contact at the origin leaves ground effects; no intermediate
            # ground cells are entered, and the destination is entered once.
            Entity.update_entity_position(target, start, parent_event=event.uuid,
                occupancy_layer=OccupancyLayer.AIR)
            if target.position != start:
                return event.cancel(status_message="Transfer interrupted before departure")
            Entity.update_entity_position(target, destination, parent_event=event.uuid,
                occupancy_layer=OccupancyLayer.GROUND)
            endpoint = destination
    else:
        for _ in range(event.actual_distance // 5):
            next_pos = (endpoint[0] + event.direction[0], endpoint[1] + event.direction[1])
            admitted_kind = grid.admit_forced_step(endpoint, next_pos, target.uuid)
            if admitted_kind is None or not target.can_end_movement_at(next_pos):
                blocked, blocked_by = True, grid.identify_blocker_at(next_pos, target.uuid)
                break
            entry_cursor = EventQueue.event_cursor()
            departure_height = grid.get_support_elevation_feet(endpoint)
            Entity.update_entity_position(target, next_pos, parent_event=event.uuid)
            endpoint = next_pos
            path.append(next_pos)
            if admitted_kind is LandingKind.FALL:
                kind = LandingKind.FALL
                drop_feet = max(0, departure_height - grid.get_support_elevation_feet(endpoint))
                break
            if (target.position != next_pos or stop_on_incapacitation and not target.can_take_actions()
                    or any(condition.get_paid_entry_retreat(since_cursor=entry_cursor) is not None
                           for condition in target.active_conditions.values())):
                interrupted = True
                break
    end_height = grid.get_support_elevation_feet(endpoint)
    finite_transfer = kind in (LandingKind.CONTROLLED, LandingKind.IMPACT)
    result = event.with_updates(start_position=start, end_position=endpoint,
        actual_distance=(support_distance_feet(start, start_height, endpoint, end_height)
                         if finite_transfer else (len(path) - 1) * 5), disclosed_path=tuple(path),
        start_elevation_feet=start_height, end_elevation_feet=end_height,
        drop_feet=max(0, start_height - end_height) if finite_transfer else drop_feet, landing_kind=kind,
        blocked_by_obstacle=False if interrupted else blocked,
        blocked_by=None if interrupted else blocked_by)
    if endpoint != start:
        if on_landing is not None:
            on_landing(result)
        elif kind is LandingKind.FALL:
            resolve_fall_damage(target, drop_feet=result.drop_feet,
                source_entity_uuid=event.source_entity_uuid or target.uuid, parent_event=result)
    result = result.phase_to(EventPhase.COMPLETION)
    resolve_paid_entry_retreats(target, since_cursor=entry_cursor, parent_event=parent_event)
    return result


class MovementEvent(ActionEvent):
    """Event payload for path-based movement actions."""

    name: str = Field(default="Movement", description="Human-readable movement event label.")
    event_type: EventType = Field(default=EventType.MOVEMENT, description="Movement event category.")
    costs: List[BaseCost] = Field(default_factory=list, description="Serialized movement costs.")
    movement_mode: Optional[MovementMode] = None
    start_layer: Optional[OccupancyLayer] = None
    end_layer: Optional[OccupancyLayer] = None
    start_position: Tuple[int, int] = Field(description="Position occupied before movement starts.")
    end_position: Tuple[int, int] = Field(description="Intended or actual final movement position.")
    requested_end_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Destination requested before any partial-path termination.",
    )
    path: Optional[List[Tuple[int, int]]] = Field(default=None, description="Grid path used by the movement.")
    trajectory: MovementTrajectory = Field(
        default=MovementTrajectory.PATH,
        description="Typed trajectory used for each committed movement step.",
    )
    termination_reason: MovementTerminationReason = Field(
        default=MovementTerminationReason.COMPLETED,
        description="Reason the authoritative traversed path ended.",
    )
    controller_revalidation: bool = Field(
        default=False,
        description="Whether a committed step required a fresh controller decision.",
    )
    controller_revalidation_reason: Optional[str] = Field(
        default=None,
        description="Typed subjective change that required controller revalidation.",
    )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return movement positions relevant to spatial handlers."""
        positions = {self.start_position, self.end_position}
        if self.path:
            positions.update(self.path)
        return positions

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this movement event.

        Uses self.* fields only - no external lookups. Entity name must be
        populated when the event is created.
        """
        source_name = self.source_entity_name or "Unknown"

        path = self.path or []
        distance_feet = (len(path) - 1) * 5 if len(path) > 1 else 0

        movement_cost = 0
        for cost in self.costs:
            if cost.cost_type == "movement":
                movement_cost = cost.cost

        path_str = " -> ".join(f"({p[0]}, {p[1]})" for p in path) if path else ""

        end_pos = f"({self.end_position[0]},{self.end_position[1]})"
        start_pos = f"({self.start_position[0]},{self.start_position[1]})"

        compact_text = f"{md_color(source_name, 'cyan')} moves {md_color(f'{distance_feet}ft', 'green')} to {md_color(end_pos, 'yellow')}"
        verbose_text = f"{md_color(source_name, 'cyan')} moves {start_pos} → {md_color(end_pos, 'green')}"
        if movement_cost > 0:
            verbose_text += f" ({movement_cost}ft)"

        detailed_text = verbose_text
        if path_str:
            detailed_text += f"\n  Path: {path_str}"

        data = MovementLogData(
                entity_name=source_name,
                entity_uuid=str(self.source_entity_uuid),
                start_position=self.start_position,
                end_position=self.end_position,
                path=path,
                distance_feet=distance_feet,
                movement_cost=movement_cost,
                requested_end_position=self.requested_end_position,
                termination_reason=self.termination_reason.value,
                controller_revalidation=self.controller_revalidation,
                controller_revalidation_reason=self.controller_revalidation_reason,
            )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=data,
            success=True
        )


@dataclass(frozen=True)
class MovementCostAvailable:
    """A movement cost's affordability check, as data: the mode the cost was built for.

    A bound method of the Move here made every Move and its own Cost a reference cycle.
    """

    movement_mode: MovementMode

    def __call__(self, entity_uuid: UUID, cost_type: CostType, cost: int) -> bool:
        entity = Entity.get(entity_uuid)
        return entity is not None and entity.action_economy.movement_remaining(self.movement_mode) >= cost


@_core_action_identity(
    content_id="action.move",
    display_name="Move",
    description="Move along a traversable battlefield path.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Movement and Position",
    sort_order=10,
)

class Move(BaseAction):
    """Path-based movement action that walks cell by cell.

    When used as a template (template=True), end_position can be None and should be set via set_target_position()
    before pre_validate() or instantiate().
    """

    name: str = Field(default="Move", description="Human-readable movement action name.")
    description: str = Field(default="Move to a position", description="Movement action description.")
    target_type: TargetType = Field(default=TargetType.POSITION_PATH, description="Move targets a path-reachable position.")
    action_category: ActionCategory = Field(default=ActionCategory.MOVEMENT, description="Movement action category.")
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="Requested movement destination.")
    path: Optional[List[Tuple[int, int]]] = Field(default=None, description="Resolved path from source to destination.")
    use_movement_cost: bool = Field(default=True, description="Whether movement costs are generated from the path.")
    movement_allowance_feet: int | None = Field(default=None, ge=0,
        description="Independent granted movement budget; steps retain ordinary reactions and terrain costs.")
    prefer_safe: bool = Field(default=True, description="Whether a safe path is preferred when available.")
    movement_mode: MovementMode = Field(default=MovementMode.WALKING, description="Movement mode used for terrain costs and transitions.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.end_position is not None and not self.template:
            self._setup_path()
            self._setup_costs_from_path()

    def describe_discovery(self) -> ActionDiscoveryDescription:
        return ActionDiscoveryDescription(fixed_facets=(ActionVariantFacet(key="movement",
            value=self.movement_mode.value, label=self.movement_mode.value.title()),))

    def get_movement_mode(self) -> MovementMode:
        return self.movement_mode

    def current_selection(self) -> ActionSelection:
        """The route preference is part of a move's selection."""
        return replace(super().current_selection(), prefer_safe=self.prefer_safe)

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        """A destination's route: the known safe route when preferred and affordable, else the known route."""
        overrides = super()._selection_overrides(selection)
        overrides["prefer_safe"] = selection.prefer_safe
        if selection.positions:
            overrides["path"] = self._route_to(selection.positions[0], prefer_safe=selection.prefer_safe)
        return overrides

    def _route_to(self, end_position: Tuple[int, int], *, prefer_safe: bool) -> Optional[List[Tuple[int, int]]]:
        mover = Entity.get(self.source_entity_uuid)
        if mover is None:
            return None
        safe = route(mover.senses.safe_paths, end_position) if self.movement_mode is MovementMode.WALKING else None
        if (prefer_safe and safe is not None and mover.movement_path_cost_feet(safe, MovementMode.WALKING)
                <= mover.action_economy.movement_remaining()):
            return safe
        if self.movement_mode is MovementMode.WALKING:
            return route(mover.senses.paths, end_position)
        return route(get_map().compute_paths(mover.position, requesting_entity_uuid=mover.uuid,
            movement_mode=self.movement_mode, subjective=True), end_position)

    def _setup_costs_from_path(self) -> None:
        """Rebuild the movement cost from the resolved path and terrain."""
        if self.path is not None and self.use_movement_cost:
            grid = get_map()
            total_cost = 0

            source_entity = Entity.get(self.source_entity_uuid)
            ign_terrain = source_entity.ignore_difficult_terrain if source_entity else False

            for from_position, to_position in zip(self.path, self.path[1:]):
                total_cost += self._get_step_cost_units(
                    grid,
                    from_position,
                    to_position,
                    source_entity,
                    ign_terrain,
                    self.movement_mode,
                )

            feet_cost = int(total_cost * 5)
            self.costs.append(
                Cost(
                    name="Movement Cost",
                    cost_type="movement",
                    cost=feet_cost,
                    evaluator=MovementCostAvailable(self.movement_mode),
                )
            )

    @staticmethod
    def _get_step_cost_units(
        grid,
        from_position: Tuple[int, int],
        to_position: Tuple[int, int],
        source_entity: Optional[Entity],
        ignore_difficult_terrain: bool,
        movement_mode: MovementMode,
    ) -> float:
        """Return movement-cost units for one step in this action's mode.

        Args:
            grid: Objective Tile and movement-edge owner.
            from_position: Current support position.
            to_position: Destination support position.
            source_entity: Entity paying the movement cost.
            ignore_difficult_terrain: Whether difficult-terrain costs are capped.

        Returns:
            Movement cost in grid cost units before conversion to feet.
        """
        cost = grid.movement_edge_cost_units(
            from_position,
            to_position,
            movement_mode,
            ignore_difficult_terrain=ignore_difficult_terrain,
        )

        if (
            movement_mode == MovementMode.SWIMMING
            and source_entity is not None
            and source_entity.swimming_speed <= 0
            and not source_entity.ignore_underwater_penalties
        ):
            cost *= 2

        return cost

    def _setup_path(self) -> None:
        """Resolve the movement path from current senses data."""
        if self.path is None and self.end_position is not None:
            self.path = self._path_to(self.end_position)

    def _path_to(self, end_position: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        """The mover's known path to one destination, without binding it."""
        source_entity = Entity.get(self.source_entity_uuid)
        if source_entity is None:
            return None
        if self.movement_mode == MovementMode.WALKING and self.prefer_safe and has_route(source_entity.senses.safe_paths, end_position):
            return route(source_entity.senses.safe_paths, end_position)
        if self.movement_mode == MovementMode.WALKING:
            return route(source_entity.senses.paths, end_position)
        return route(get_map().compute_paths(
            source_entity.position,
            requesting_entity_uuid=source_entity.uuid,
            movement_mode=self.movement_mode,
            subjective=True,
        ), end_position)

    def set_target_position(self, position: Tuple[int, int]) -> None:
        """Set target position and compute path/costs for validation.

        Overrides base implementation to also compute path and costs,
        so that pre_validate() can properly check movement affordability.
        """
        self.path = None
        self.costs = []

        super().set_target_position(position)

        self._setup_path()
        self._setup_costs_from_path()

    def instantiate(self, **overrides) -> "Move":
        """A new executable Move; path and costs are recomputed for its destination unless given.

        Uses model_copy() to preserve object types.
        """
        registered_template_uuid = self.registered_template_uuid or self.uuid
        update_dict: dict = {
            "uuid": uuid4(),
            "template": False,
            "use_register": False,
            "path": None,
            "costs": [],
        }
        update_dict.update(overrides)
        update_dict["registered_template_uuid"] = registered_template_uuid

        instance = self.model_copy(deep=True, update=update_dict)

        if instance.end_position is not None:
            instance._setup_path()
            instance._setup_costs_from_path()

        return instance

    @staticmethod
    def path_error(
        path: Optional[List[Tuple[int, int]]],
        end_position: Tuple[int, int],
        source_entity_uuid: UUID,
        movement_mode: MovementMode = MovementMode.WALKING,
    ) -> Optional[str]:
        """Why a path cannot carry the mover to one destination, or None when it can.

        Args:
            path: Cells from the mover's position to the destination.
            end_position: Selected destination.
            source_entity_uuid: Moving entity UUID.
            movement_mode: Movement mode required for each transition.
        """
        source_entity = Entity.get(source_entity_uuid)
        if source_entity is None:
            return "Source entity not found"
        if not path:
            return "No valid path found"
        grid = get_map()
        if movement_mode is MovementMode.FLYING:
            if source_entity.action_economy.current_speed(movement_mode) <= 0:
                return "Flying movement is unavailable"
            if any(grid.get_tile(*position) is None for position in path):
                return "Flight requires supported positions"
        if path[0] != source_entity.position:
            return "Invalid path start"
        if path[-1] != end_position:
            return "Invalid path end"
        if not source_entity.can_end_movement_at(end_position, subjective=True):
            return "Movement destination is occupied"
        for from_pos, to_pos in zip(path, path[1:]):
            if (max(abs(from_pos[0] - to_pos[0]), abs(from_pos[1] - to_pos[1])) != 1
                    or not grid.can_transition(from_pos, to_pos, source_entity.uuid, movement_mode, subjective=True)):
                return f"Invalid {movement_mode.value} transition at position {to_pos}"
        return None

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for the movement action.

        For templates, this computes the path and costs on the fly based on the
        current end_position.
        """
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity or not isinstance(source_entity, Entity):
            return None

        if self.end_position is None:
            return None

        end_position: Tuple[int, int] = self.end_position

        path = self.path
        if path is None and self.movement_mode == MovementMode.WALKING and has_route(source_entity.senses.paths, end_position):
            path = route(source_entity.senses.paths, end_position)
        elif path is None and self.movement_mode != MovementMode.WALKING:
            grid = get_map()
            path = route(grid.compute_paths(
                source_entity.position,
                requesting_entity_uuid=source_entity.uuid,
                movement_mode=self.movement_mode,
                subjective=True,
            ), end_position)

        costs = list(self.costs)
        if path is not None and self.use_movement_cost:
            has_movement_cost = any(c.cost_type == "movement" for c in costs)
            if not has_movement_cost:
                grid = get_map()
                total_cost = 0

                for from_position, to_position in zip(path, path[1:]):
                    total_cost += self._get_step_cost_units(
                        grid,
                        from_position,
                        to_position,
                        source_entity,
                        source_entity.ignore_difficult_terrain,
                        self.movement_mode,
                    )

                feet_cost = int(total_cost * 5)
                costs.append(Cost(name="Movement Cost", cost_type="movement", cost=feet_cost, evaluator=MovementCostAvailable(self.movement_mode)))

        return MovementEvent(
            name=f"{self.name}",
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            start_position=source_entity.position,
            movement_mode=self.movement_mode,
            start_layer=source_entity.occupancy_layer,
            end_layer=source_entity.occupancy_layer,
            end_position=end_position,
            requested_end_position=end_position,
            path=path,
            costs=[BaseCost(name=cost.name, cost_type=cost.cost_type, cost=cost.cost,
                resource_name=cost.resource_name, resource_cost=cost.resource_cost) for cost in costs],
            use_register=use_register,
            source_entity_name=source_entity.name,
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A usable path from the mover to the selected destination."""
        if not selection.positions:
            return "Choose a destination"
        end_position = selection.positions[0]
        path = self.path if self.path is not None else self._path_to(end_position)
        return Move.path_error(path, end_position, self.source_entity_uuid, self.movement_mode)

    def _apply(self, execution_event: MovementEvent) -> MovementEvent:
        """Apply the movement action using cell-by-cell movement.

        Iterates through path, firing StepMovementEvent for each cell transition.
        This allows OA handlers and terrain effects to interrupt movement.
        """
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity or not isinstance(source_entity, Entity):
            return execution_event.cancel(status_message=f"Source entity not found for {execution_event.name}")

        if self.path is None and execution_event.path is None:
            return execution_event.cancel(status_message=f"No path found for {execution_event.name}")
        elif self.path is None and execution_event.path is not None:
            self.path = execution_event.path
            if self.use_movement_cost:
                self._setup_costs_from_path()
            execution_event = execution_event.post(
                path=self.path,
                status_message=f"Added paths to {execution_event.uuid}"
            )

        started = time.perf_counter()
        # Stored movement facts own finite values, never a callback back to this
        # executable action. Validation of a Cost instance would retain it.
        costs = [BaseCost(name=cost.name, cost_type=cost.cost_type, cost=cost.cost,
            resource_name=cost.resource_name, resource_cost=cost.resource_cost) for cost in self.costs]
        record_action_timing("movement.validate_cost_models_ms", started)
        started = time.perf_counter()
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            costs=costs,
            status_message=f"Added costs to {execution_event.uuid}"
        )
        record_action_timing("movement.phase_to_effect_ms", started)
        if effect_event.canceled:
            return effect_event

        grid = get_map()
        path = self.path or []
        total_path_length = len(path)
        actual_end_position = source_entity.position
        traversed_path = [source_entity.position]
        traversed_movement_cost = 0
        interrupted_by_condition = False
        termination_reason = MovementTerminationReason.COMPLETED
        controller_revalidation_reason: Optional[str] = None
        transition_check_seconds = 0.0
        step_post_seconds = 0.0
        update_position_seconds = 0.0
        step_completion_seconds = 0.0
        consume_movement_seconds = 0.0
        step_cost_seconds = 0.0

        try:
            for i in range(1, total_path_length):
                from_pos = path[i - 1]
                to_pos = path[i]
                step_source_cursor_start = EventQueue.event_cursor()

                phase_started = time.perf_counter()
                endpoint_occupied = (i == total_path_length - 1
                    and not source_entity.can_end_movement_at(to_pos))
                if endpoint_occupied or not grid.can_transition(from_pos, to_pos, source_entity.uuid, self.movement_mode):
                    transition_check_seconds += time.perf_counter() - phase_started
                    if grid.can_transition(from_pos, to_pos, source_entity.uuid, self.movement_mode, subjective=True):
                        cell_blocked = endpoint_occupied or not grid.is_walkable_for(to_pos[0], to_pos[1], source_entity.uuid, self.movement_mode)
                        directions = []
                        from_tile = grid.get_tile(*from_pos)
                        if from_tile:
                            directions = list(from_tile.directions_toward(to_pos))
                        senses = source_entity.senses
                        if cell_blocked:
                            senses.collision_blocked = remember_blocked_cell(senses.collision_blocked, to_pos)
                        elif directions:
                            senses.directional_collision_blocked = remember_blocked_sides(
                                senses.directional_collision_blocked, from_pos, directions)
                        collision_event = SpatialChangeEvent.movement_collision(
                            position=to_pos, mover_uuid=source_entity.uuid,
                            parent_event=effect_event.uuid,
                            transition_from=from_pos,
                            transition_to=to_pos,
                            directional_position=from_pos if directions else None,
                            directional_directions=directions or None,
                            directional_channels=[WorldEdgeChannel.MOVEMENT] if directions and not cell_blocked else None,
                            )
                        grid.publish_spatial_event(collision_event)
                    termination_reason = MovementTerminationReason.COLLISION
                    break
                transition_check_seconds += time.perf_counter() - phase_started

                phase_started = time.perf_counter()
                step_cost_units = self._get_step_cost_units(
                    grid,
                    from_pos,
                    to_pos,
                    source_entity,
                    source_entity.ignore_difficult_terrain,
                    self.movement_mode,
                )
                step_cost_feet = int(step_cost_units * 5)
                step_cost_seconds += time.perf_counter() - phase_started

                remaining_movement = (self.movement_allowance_feet - traversed_movement_cost
                    if self.movement_allowance_feet is not None
                    else source_entity.action_economy.movement_remaining(self.movement_mode))
                if remaining_movement < step_cost_feet:
                    termination_reason = MovementTerminationReason.INSUFFICIENT_MOVEMENT
                    break

                step_event = StepMovementEvent(
                    source_entity_uuid=self.source_entity_uuid,
                    source_entity_name=source_entity.name,
                    from_position=from_pos,
                    to_position=to_pos,
                    path_index=i,
                    total_path_length=total_path_length,
                    movement_cost=step_cost_feet,
                    trajectory=execution_event.trajectory,
                    movement_mode=self.movement_mode,
                    from_layer=source_entity.occupancy_layer,
                    to_layer=source_entity.occupancy_layer,
                    disclosed_path=(from_pos, to_pos),
                    from_elevation_feet=grid.get_support_elevation_feet(from_pos),
                    to_elevation_feet=grid.get_support_elevation_feet(to_pos),
                    provocation_policy=MovementProvocationPolicy.ORDINARY_EXIT,
                    phase=EventPhase.EFFECT,
                    parent_event=effect_event.uuid,
                    use_register=False
                )
                phase_started = time.perf_counter()
                processed_step = step_event.post(use_register=True)
                step_post_seconds += time.perf_counter() - phase_started

                if processed_step.canceled:
                    termination_reason = MovementTerminationReason.STEP_CANCELED
                    break

                if not source_entity.can_take_actions():
                    interrupted_by_condition = True
                    termination_reason = (
                        MovementTerminationReason.DEAD
                        if source_entity.health.life_state is LifeState.DEAD
                        else MovementTerminationReason.INCAPACITATED
                    )
                    processed_step.phase_to(
                        EventPhase.COMPLETION,
                        committed=False,
                        status_message=f"Movement step interrupted before entering {to_pos}",
                    )
                    break

                phase_started = time.perf_counter()
                if ((i == total_path_length - 1 and not source_entity.can_end_movement_at(to_pos))
                        or not grid.can_transition(from_pos, to_pos, source_entity.uuid, self.movement_mode)):
                    transition_check_seconds += time.perf_counter() - phase_started
                    termination_reason = MovementTerminationReason.COLLISION
                    processed_step.phase_to(
                        EventPhase.COMPLETION,
                        committed=False,
                        status_message=f"Movement step blocked before entering {to_pos}",
                    )
                    break
                transition_check_seconds += time.perf_counter() - phase_started

                resolved_speed_feet = source_entity.action_economy.current_speed(self.movement_mode)
                if (self.movement_allowance_feet is None
                        and source_entity.action_economy.movement_remaining(self.movement_mode) < step_cost_feet):
                    interrupted_by_condition = True
                    termination_reason = MovementTerminationReason.INSUFFICIENT_MOVEMENT
                    processed_step.phase_to(EventPhase.COMPLETION, committed=False,
                        status_message="Movement grant changed before entering the next position")
                    break
                phase_started = time.perf_counter()
                if self.movement_allowance_feet is None:
                    source_entity.action_economy.consume("movement", step_cost_feet, movement_mode=self.movement_mode)
                consume_movement_seconds += time.perf_counter() - phase_started

                phase_started = time.perf_counter()
                Entity.update_entity_position(source_entity, to_pos, parent_event=processed_step.uuid)
                actual_end_position = source_entity.position
                traversed_path.append(to_pos)
                traversed_movement_cost += step_cost_feet
                update_position_seconds += time.perf_counter() - phase_started

                phase_started = time.perf_counter()
                processed_step.phase_to(EventPhase.COMPLETION, committed=True,
                                        resolved_speed_feet=resolved_speed_feet)
                step_completion_seconds += time.perf_counter() - phase_started

                if resolve_paid_entry_retreats(source_entity, since_cursor=step_source_cursor_start, parent_event=effect_event):
                    interrupted_by_condition = True
                    actual_end_position = source_entity.position
                    termination_reason = (MovementTerminationReason.POSITION_DIVERGED
                        if actual_end_position != to_pos else MovementTerminationReason.STEP_CANCELED)
                    break

                if source_entity.position != to_pos:
                    interrupted_by_condition = True
                    actual_end_position = source_entity.position
                    termination_reason = MovementTerminationReason.POSITION_DIVERGED
                    break

                if not source_entity.can_take_actions():
                    termination_reason = (
                        MovementTerminationReason.DEAD
                        if source_entity.health.life_state is LifeState.DEAD
                        else MovementTerminationReason.INCAPACITATED
                    )
                    break

                continuation = revalidate_after_committed_movement_step(
                    MovementStepBoundary(
                        actor_uuid=source_entity.uuid,
                        movement_event_uuid=effect_event.uuid,
                        movement_lineage_uuid=effect_event.lineage_uuid,
                        step_event_uuid=processed_step.uuid,
                        from_position=from_pos,
                        to_position=to_pos,
                        objective_position=source_entity.position,
                        step_movement_cost=step_cost_feet,
                        traversed_path=tuple(traversed_path),
                        movement_spent=traversed_movement_cost,
                        movement_remaining=(
                            source_entity.action_economy.movement_remaining(self.movement_mode)
                        ),
                        source_event_cursor_start=step_source_cursor_start,
                        source_event_cursor_end=EventQueue.event_cursor(),
                    )
                )
                if continuation.decision is MovementContinuationDecision.INTERRUPT:
                    controller_revalidation_reason = continuation.reason
                    if to_pos != execution_event.end_position:
                        termination_reason = (
                            MovementTerminationReason.SUBJECTIVE_REVALIDATION
                        )
                    break

        finally:
            record_action_elapsed("movement.transition_checks_ms", transition_check_seconds)
            record_action_elapsed("movement.step_costs_ms", step_cost_seconds)
            record_action_elapsed("movement.step_event_post_ms", step_post_seconds)
            record_action_elapsed("movement.update_position_ms", update_position_seconds)
            record_action_elapsed("movement.step_completion_ms", step_completion_seconds)
            record_action_elapsed("movement.consume_movement_ms", consume_movement_seconds)
            started = time.perf_counter()
            source_entity.materialize_navigation_after_movement(self.movement_mode)
            record_action_timing("movement.final_update_senses_ms", started)

        completion_costs = [
            cost for cost in effect_event.costs
            if cost.cost_type != "movement"
        ]
        if self.use_movement_cost:
            completion_costs.append(BaseCost(
                name="Movement Cost",
                cost_type="movement",
                cost=traversed_movement_cost,
            ))
        completion_updates = {
            "end_position": actual_end_position,
            "end_layer": source_entity.occupancy_layer,
            "requested_end_position": execution_event.requested_end_position,
            "path": traversed_path,
            "costs": completion_costs,
            "termination_reason": termination_reason,
            "controller_revalidation": controller_revalidation_reason is not None,
            "controller_revalidation_reason": controller_revalidation_reason,
            "outcome_code": (
                "movement.subjective_revalidation"
                if controller_revalidation_reason is not None
                else effect_event.outcome_code
            ),
        }

        if source_entity.position == execution_event.start_position:
            if interrupted_by_condition:
                started = time.perf_counter()
                result = effect_event.with_updates(
                    status_message=f"Partial movement for {execution_event.name}, stopped at {source_entity.position}",
                    **completion_updates,
                )
                record_action_timing("movement.phase_to_completion_ms", started)
                return result
            started = time.perf_counter()
            result = effect_event.cancel(status_message=f"Failed to move for {execution_event.name}")
            record_action_timing("movement.cancel_failed_move_ms", started)
            return result
        elif source_entity.position != execution_event.end_position:
            started = time.perf_counter()
            result = effect_event.with_updates(
                status_message=f"Partial movement for {execution_event.name}, stopped at {source_entity.position}",
                **completion_updates,
            )
            record_action_timing("movement.phase_to_completion_ms", started)
            return result

        started = time.perf_counter()
        result = effect_event.with_updates(
            status_message=f"Applied movement for {execution_event.name}",
            **completion_updates,
        )
        record_action_timing("movement.phase_to_completion_ms", started)
        return result

    def _apply_costs(self, execution_event: MovementEvent) -> Optional[MovementEvent]:
        """Apply costs - movement is already consumed per-step in _apply().

        Skip movement cost here since cell-by-cell movement already deducts
        movement per step. Only apply non-movement costs (if any).
        """
        cost_event = _consume_entity_action_economy_costs(
            execution_event,
            self.source_entity_uuid,
            excluded_cost_types=frozenset({"movement"}),
        )
        if cost_event.canceled:
            return cost_event
        return cost_event

    def apply(self, parent_event: Optional[Event] = None) -> Optional[MovementEvent]:
        """Override to provide specific return type."""
        result = super().apply(parent_event)
        return cast(MovementEvent, result) if result else None


@_core_action_identity(
    content_id="action.swim",
    display_name="Swim",
    description="Move through water using swimming movement.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Adventuring: Special Types of Movement — Swimming",
    sort_order=20,
)
class Swim(Move):
    """Path-based swimming action that uses swimming terrain costs."""

    name: str = Field(default="Swim", description="Human-readable swimming action name.")
    description: str = Field(default="Swim to a water position", description="Swimming action description.")
    movement_mode: MovementMode = Field(default=MovementMode.SWIMMING, description="Movement mode used for terrain costs and transitions.")


class TraverseConnectorEvent(ActionEvent):
    """Typed transaction facts for one oriented connector transfer."""

    name: str = Field(default="Traverse Connector")
    event_type: EventType = Field(default=EventType.MOVEMENT)
    costs: List[BaseCost] = Field(default_factory=list)
    connector_uuid: UUID
    connector_authored_id: str
    connector_kind: TraversalConnectorKind
    connector_presentation_key: str
    connector_revision: StrictInt = Field(ge=1)
    connector_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    connector_provocation_policy: ConnectorProvocationPolicy
    connector_bidirectional: StrictBool
    start_position: Tuple[StrictInt, StrictInt]
    requested_end_position: Tuple[StrictInt, StrictInt]
    end_position: Tuple[StrictInt, StrictInt]
    objective_end_position: Tuple[StrictInt, StrictInt]
    start_elevation_feet: StrictInt
    requested_end_elevation_feet: StrictInt
    end_elevation_feet: StrictInt
    movement_cost_feet: StrictInt = Field(ge=0)
    action_cost_type: Optional[ConnectorActionCostType] = None
    action_cost_amount: StrictInt = Field(default=0, ge=0)
    termination_reason: MovementTerminationReason = Field(
        default=MovementTerminationReason.COMPLETED,
    )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        return {self.start_position, self.requested_end_position}

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate the committed connector transfer from carried facts."""
        source_name = self.source_entity_name or "Unknown"
        path = [self.start_position, self.end_position]
        distance_feet = support_distance_feet(
            self.start_position,
            self.start_elevation_feet,
            self.end_position,
            self.end_elevation_feet,
        )
        compact = (
            f"{md_color(source_name, 'cyan')} traverses "
            f"{md_color(self.connector_presentation_key, 'yellow')} to "
            f"{md_color(str(self.end_position), 'green')}"
        )
        verbose = (
            f"{compact} ({self.start_elevation_feet}ft → "
            f"{self.end_elevation_feet}ft)"
        )
        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact,
            verbose=verbose,
            detailed=verbose,
            data=ConnectorMovementLogData(
                movement_type='connector',
                entity_name=source_name,
                entity_uuid=str(self.source_entity_uuid),
                start_position=self.start_position,
                requested_end_position=self.requested_end_position,
                objective_end_position=self.objective_end_position,
                end_position=self.end_position,
                path=path,
                start_elevation_feet=self.start_elevation_feet,
                requested_end_elevation_feet=self.requested_end_elevation_feet,
                end_elevation_feet=self.end_elevation_feet,
                distance_feet=distance_feet,
                movement_cost=self.movement_cost_feet,
                connector_uuid=self.connector_uuid,
                connector_authored_id=self.connector_authored_id,
                connector_kind=self.connector_kind,
                connector_presentation_key=self.connector_presentation_key,
                connector_provocation_policy=self.connector_provocation_policy,
                termination_reason=self.termination_reason.value,
            ),
            success=(
                self.termination_reason is MovementTerminationReason.COMPLETED
                and self.end_position == self.objective_end_position
            ),
        )


class TraverseConnector(BaseAction):
    """One endpoint-indexed SELF action shared by every connector kind."""

    name: str = Field(default="Traverse Connector")
    description: str = Field(default="Traverse the selected connector")
    target_type: TargetType = Field(default=TargetType.SELF)
    action_category: ActionCategory = Field(default=ActionCategory.MOVEMENT)
    costs: List[Cost] = Field(default_factory=empty_list)
    connector_traversal: Optional[ConnectorTraversalDiscovery] = None

    @staticmethod
    def _oriented_connector(
        connector: TraversalConnector,
        source_position: Tuple[int, int],
    ) -> Optional[Tuple[TraversalConnectorEndpoint, TraversalConnectorEndpoint]]:
        first, second = connector.endpoints
        if source_position == first.position:
            return first, second
        if source_position == second.position and connector.bidirectional:
            return second, first
        return None

    @staticmethod
    def _variant_costs(connector: TraversalConnector, movement_cost: int) -> List[Cost]:
        costs: List[Cost] = []
        if connector.action_cost_type is not None:
            costs.append(Cost(
                name="Connector Action Cost",
                cost_type=connector.action_cost_type.value,
                cost=connector.action_cost_amount,
                evaluator=entity_action_economy_cost_evaluator,
            ))
        if movement_cost > 0:
            costs.append(Cost(
                name="Connector Movement Cost",
                cost_type="movement",
                cost=movement_cost,
                evaluator=entity_action_economy_cost_evaluator,
            ))
        return costs

    @staticmethod
    def _destination_status(
        entity: Entity,
        destination: Tuple[int, int],
    ) -> ConnectorDestinationStatus:
        if not cell_visible(entity.senses.cells, destination):
            return ConnectorDestinationStatus.UNKNOWN
        if get_map().is_walkable_for(
            destination[0],
            destination[1],
            entity.uuid,
            subjective=True,
        ):
            return ConnectorDestinationStatus.KNOWN_CLEAR
        return ConnectorDestinationStatus.KNOWN_BLOCKED

    def discovery_selections(self, scan: ActorScan) -> Tuple[ActionSelection, ...]:
        """One row per enabled connector the traverser stands at an entry of, whose passage it can pay."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return ()
        own = self.current_selection()
        return tuple(replace(own, target_uuids=(connector.uuid,))
                     for connector in get_map().get_connectors_at(entity.position)
                     if self._traversal(entity, connector) is not None)

    def _traversal(self, entity: Entity, connector: TraversalConnector) -> Optional[ConnectorTraversalDiscovery]:
        """The traverser's declared passage through one connector from its cell, as it perceives it."""
        if not connector.enabled:
            return None
        oriented = self._oriented_connector(connector, entity.position)
        if oriented is None:
            return None
        source_endpoint, destination_endpoint = oriented
        movement_cost = get_map().connector_movement_cost(
            connector, entity.position, entity.uuid, entity.size, subjective=True,
            ignore_difficult_terrain=entity.ignore_difficult_terrain)
        if movement_cost is None:
            return None
        return ConnectorTraversalDiscovery(
            command=TraversalConnectorCommand(
                connector_uuid=connector.uuid,
                connector_revision=connector.revision,
                connector_digest=connector.objective_digest,
                source_position=source_endpoint.position,
                destination_position=destination_endpoint.position,
            ),
            authored_id=connector.authored_id,
            kind=connector.kind,
            presentation_key=connector.presentation_key,
            source_elevation_feet=source_endpoint.elevation_feet,
            destination_elevation_feet=destination_endpoint.elevation_feet,
            movement_cost_feet=movement_cost,
            action_cost_type=connector.action_cost_type,
            action_cost_amount=connector.action_cost_amount,
            bidirectional=connector.bidirectional,
            provocation_policy=connector.provocation_policy,
            destination_status=self._destination_status(entity, destination_endpoint.position),
        )

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        """The selected connector's declared passage and its costs; the traverser is its own target."""
        overrides = super()._selection_overrides(selection)
        entity = Entity.get(self.source_entity_uuid)
        connector = get_map().get_connector(selection.target_uuids[0]) if selection.target_uuids else None
        traversal = self._traversal(entity, connector) if entity is not None and connector is not None else None
        if traversal is None:
            raise ValueError("The selected connector cannot be traversed from here")
        overrides.update(connector_traversal=traversal, costs=self._variant_costs(connector, traversal.movement_cost_feet))
        return overrides

    def get_discovery_display_name(self) -> str:
        discovery = self.connector_traversal
        return (
            f"Traverse {discovery.presentation_key}"
            if discovery is not None
            else self.name
        )

    def get_connector_traversal_discovery(
        self,
    ) -> Optional[ConnectorTraversalDiscovery]:
        return self.connector_traversal

    def _current_connector(
        self,
        source: Entity,
        *, subjective: bool,
    ) -> Optional[TraversalConnector]:
        """The connector exactly as this traversal declared it, or None once it changed."""
        discovery = self.connector_traversal
        if discovery is None:
            return None
        command = discovery.command
        grid = get_map()
        connector = grid.get_connector(command.connector_uuid)
        if (
            connector is None
            or not grid.connector_supports_are_current(connector)
            or not connector.enabled
            or connector.authored_id != discovery.authored_id
            or connector.kind is not discovery.kind
            or connector.presentation_key != discovery.presentation_key
            or connector.revision != command.connector_revision
            or connector.objective_digest != command.connector_digest
            or grid.connector_movement_cost(
                connector, source.position, source.uuid, source.size, subjective=subjective,
                ignore_difficult_terrain=source.ignore_difficult_terrain) != discovery.movement_cost_feet
            or connector.action_cost_type is not discovery.action_cost_type
            or connector.action_cost_amount != discovery.action_cost_amount
            or connector.provocation_policy is not discovery.provocation_policy
            or connector.bidirectional is not discovery.bidirectional
            or source.position != command.source_position
        ):
            return None
        oriented = self._oriented_connector(connector, command.source_position)
        if oriented is None:
            return None
        source_endpoint, destination_endpoint = oriented
        if (
            destination_endpoint.position != command.destination_position
            or source_endpoint.elevation_feet != discovery.source_elevation_feet
            or destination_endpoint.elevation_feet
            != discovery.destination_elevation_feet
        ):
            return None
        return connector

    def _create_declaration_event(
        self,
        parent_event: Optional[Event] = None,
        use_register: bool = True,
    ) -> Optional[TraverseConnectorEvent]:
        source = Entity.get(self.source_entity_uuid)
        discovery = self.connector_traversal
        if source is None or discovery is None:
            return None
        command = discovery.command
        return TraverseConnectorEvent(
            source_entity_uuid=source.uuid,
            target_entity_uuid=source.uuid,
            source_entity_name=source.name,
            parent_event=parent_event.uuid if parent_event is not None else None,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            connector_uuid=command.connector_uuid,
            connector_authored_id=discovery.authored_id,
            connector_kind=discovery.kind,
            connector_presentation_key=discovery.presentation_key,
            connector_revision=command.connector_revision,
            connector_digest=command.connector_digest,
            connector_provocation_policy=discovery.provocation_policy,
            connector_bidirectional=discovery.bidirectional,
            start_position=command.source_position,
            requested_end_position=command.destination_position,
            end_position=command.source_position,
            objective_end_position=command.source_position,
            start_elevation_feet=discovery.source_elevation_feet,
            requested_end_elevation_feet=discovery.destination_elevation_feet,
            end_elevation_feet=discovery.source_elevation_feet,
            movement_cost_feet=discovery.movement_cost_feet,
            action_cost_type=discovery.action_cost_type,
            action_cost_amount=discovery.action_cost_amount,
            phase=EventPhase.DECLARATION,
            use_register=use_register,
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A living, acting traverser at the declared connector endpoint, whose passage still costs what it declared."""
        source = Entity.get(self.source_entity_uuid)
        if (
            source is None
            or source.health.life_state is not LifeState.ALIVE
            or not source.can_take_actions()
            or self._current_connector(source, subjective=scan.subjective) is None
        ):
            return "Connector traversal is no longer valid"
        return None

    def _apply_costs(
        self,
        execution_event: TraverseConnectorEvent,
    ) -> TraverseConnectorEvent:
        """Commit connector costs only after the provoking Step is accepted."""
        return execution_event

    @staticmethod
    def _stop_effect(
        effect: TraverseConnectorEvent,
        source: Entity,
        reason: MovementTerminationReason,
    ) -> TraverseConnectorEvent:
        return cast(TraverseConnectorEvent, effect.with_updates(
            end_position=effect.start_position,
            objective_end_position=source.position,
            end_elevation_feet=effect.start_elevation_feet,
            termination_reason=reason,
            outcome_code=f"movement.{reason.value}",
            status_message=f"Connector transfer stopped: {reason.value}",
        ))

    def _apply(
        self,
        execution_event: TraverseConnectorEvent,
    ) -> TraverseConnectorEvent:
        source = Entity.get(self.source_entity_uuid)
        if source is None:
            return execution_event.cancel(status_message="Entity not found")
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Applying connector transfer",
        )
        if effect.canceled:
            return effect
        connector = self._current_connector(source, subjective=False)
        destination = effect.requested_end_position
        grid = get_map()
        if connector is None:
            return self._stop_effect(
                effect, source, MovementTerminationReason.INVALID_PATH
            )

        channel_costs: List[ActionEconomyChannelCost] = []
        if effect.action_cost_type is not None:
            channel_costs.append(ActionEconomyChannelCost(
                cost_type=effect.action_cost_type.value,
                amount=effect.action_cost_amount,
                name="Connector Action Cost",
            ))
        if effect.movement_cost_feet > 0:
            channel_costs.append(ActionEconomyChannelCost(
                cost_type="movement",
                amount=effect.movement_cost_feet,
                name="Connector Movement Cost",
            ))

        if not grid.is_walkable_for(destination[0], destination[1], source.uuid):
            return self._stop_effect(
                effect, source, MovementTerminationReason.COLLISION
            )
        if not all(
            source.action_economy.can_afford(cost.cost_type, cost.amount)
            for cost in channel_costs
        ):
            return self._stop_effect(
                effect, source, MovementTerminationReason.INSUFFICIENT_MOVEMENT
            )

        step = StepMovementEvent(
            source_entity_uuid=source.uuid,
            source_entity_name=source.name,
            from_position=effect.start_position,
            to_position=destination,
            path_index=1,
            total_path_length=2,
            movement_cost=effect.movement_cost_feet,
            trajectory=MovementTrajectory.CONNECTOR_TRANSFER,
            from_layer=source.occupancy_layer,
            to_layer=source.occupancy_layer,
            disclosed_path=(effect.start_position, destination),
            from_elevation_feet=effect.start_elevation_feet,
            to_elevation_feet=effect.requested_end_elevation_feet,
            provocation_policy=(
                MovementProvocationPolicy.ORDINARY_EXIT
                if effect.connector_provocation_policy
                is ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT
                else MovementProvocationPolicy.DOES_NOT_PROVOKE
            ),
            committed=False,
            phase=EventPhase.EFFECT,
            parent_event=effect.uuid,
            use_register=False,
        )
        processed_step = cast(StepMovementEvent, step.post(use_register=True))
        if processed_step.canceled or not source.can_take_actions():
            if not processed_step.canceled:
                processed_step.phase_to(EventPhase.COMPLETION, committed=False)
            return self._stop_effect(
                effect, source, MovementTerminationReason.STEP_CANCELED
            )
        if (
            self._current_connector(source, subjective=False) is None
            or not grid.is_walkable_for(
                destination[0], destination[1], source.uuid
            )
        ):
            processed_step.phase_to(EventPhase.COMPLETION, committed=False)
            return self._stop_effect(
                effect, source, MovementTerminationReason.INVALID_PATH
            )

        resolved_speed_feet = source.action_economy.current_speed()
        receipt = source.action_economy.consume_aggregate_with_receipt(
            tuple(channel_costs)
        )
        try:
            Entity.update_entity_position(
                source,
                destination,
                parent_event=processed_step.uuid,
            )
        except Exception:
            source.action_economy.undo_prevalidated_debit(receipt)
            raise
        processed_step.phase_to(
            EventPhase.COMPLETION,
            committed=True,
            resolved_speed_feet=resolved_speed_feet,
            status_message=f"Connector transfer arrived at {destination}",
        )
        return cast(TraverseConnectorEvent, effect.with_updates(
            end_position=destination,
            objective_end_position=source.position,
            end_elevation_feet=effect.requested_end_elevation_feet,
            termination_reason=MovementTerminationReason.COMPLETED,
            outcome_code="movement.completed",
            status_message=f"Connector transfer completed at {destination}",
        ))


class AttackEvent(ActionEvent):
    """Event payload for one weapon attack lifecycle."""

    name: str = Field(default="Attack", description="Human-readable attack event label.")
    target_kind: Literal["creature", "object"] = "creature"
    target_position: Optional[tuple[int, int]] = None
    target_base_height_steps: Optional[int] = None
    attack_source_kind: Literal["equipped", "unarmed", "natural"] = "equipped"
    natural_weapon: Optional[NaturalWeaponSpec] = None
    shield_attack: Optional[ShieldAttackSpec] = None
    additional_damages: List[Damage] = Field(default_factory=list)
    costs: List[BaseCost] = Field(default_factory=list, description="Costs attached to this attack event.")
    weapon_slot: WeaponSlot = Field(description="Weapon slot used for the attack.")
    range: Optional[Range] = Field(default=None, description="Range band used by the attack.")
    is_long_range: bool = Field(default=False, description="Whether the target is beyond normal range.")
    is_threatened: bool = Field(default=False, description="Whether a hostile creature threatens the attacker.")
    attack_bonus: Optional[ValueReading] = Field(default=None, description="Evaluated attack-roll bonus used for this attack.")
    ac: Optional[ValueReading] = Field(default=None, description="Evaluated target armor class used for this attack.")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="Attack d20 roll after result handlers.")
    attack_outcome: Optional[AttackOutcome] = Field(default=None, description="Resolved attack outcome.")
    intercepted_by_condition_uuid: UUID | None = None
    projectile_deflection_position: tuple[float, float] | None = None
    damages: Optional[List[Damage]] = Field(default=None, description="Damage packets used on hit.")
    damage_rolls: Optional[List[DiceRoll]] = Field(default=None, description="Damage rolls after result handlers.")
    event_type: EventType = Field(default=EventType.ATTACK, description="Event category for attacks.")
    weapon_name: Optional[str] = Field(default=None, description="Display name of the weapon used.")
    attack_is_magical: bool = False
    override_ability: Optional[AbilityName] = Field(
        default=None,
        description="Ability override for attack and damage rolls.",
    )
    damage_types: List[DamageType] = Field(
        default_factory=list,
        description="Damage types exposed to visual effects and clients.",
    )

    def phase_to(self, new_phase: Optional[EventPhase] = None, status_message: Optional[str] = None, **updates: Any) -> Self:
        """Override to auto-update damage_types when damages are set."""
        if 'damages' in updates and updates['damages'] and 'damage_types' not in updates:
            updates['damage_types'] = list(dict.fromkeys(d.damage_type for d in updates['damages']))
        return super().phase_to(new_phase, status_message, **updates)

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this attack event.

        Uses self.* fields only - no external lookups. Entity names and weapon name
        must be populated when the event is created.
        """
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"
        weapon_name = self.weapon_name or "Unarmed"

        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        attack_roll = DiceRollDisplay(
            dice_str="d20",
            results=[],
            bonus=0,
            total=0
        )

        if self.dice_roll:
            results = self.dice_roll.results
            if isinstance(results, list):
                attack_roll.results = list(results)
                attack_roll.all_d20_rolls = list(results)

                adv_status = self.dice_roll.advantage_status
                if adv_status:
                    adv_value = adv_status.value.lower()
                    attack_roll.advantage_status = adv_value
                    if len(results) >= 2:
                        if adv_value == "advantage":
                            attack_roll.d20_used = max(results)
                        elif adv_value == "disadvantage":
                            attack_roll.d20_used = min(results)
                        else:
                            attack_roll.d20_used = results[0]
                    elif len(results) == 1:
                        attack_roll.d20_used = results[0]
                else:
                    attack_roll.d20_used = results[0] if results else 0
            elif isinstance(results, int):
                attack_roll.results = [results]
                attack_roll.d20_used = results

            attack_roll.bonus = self.dice_roll.bonus
            attack_roll.total = self.dice_roll.total

        attack_breakdown = value_log_rows(self.attack_bonus.breakdown) if self.attack_bonus else []
        advantage_breakdown = advantage_log_rows(self.attack_bonus.advantage_breakdown) if self.attack_bonus else []

        target_ac = 0
        if self.ac:
            target_ac = self.ac.normalized_score
        elif target_entity:
            target_ac = target_entity.ac_bonus().normalized_score

        ac_breakdown = value_log_rows(self.ac.breakdown) if self.ac else []

        outcome = "unknown"
        is_hit = False
        is_crit = False
        if self.attack_outcome:
            outcome_value = self.attack_outcome.value
            outcome = outcome_value.lower()
            is_hit = outcome in ("hit", "crit")
            is_crit = outcome == "crit"

        damage_roll_displays: List[DamageRollDisplay] = []

        if self.damage_rolls and self.damages:
            for i, dr in enumerate(self.damage_rolls):
                damage = self.damages[i] if i < len(self.damages) else None
                damage_type = damage.damage_type.value if damage else "unknown"

                dice_results = []
                if dr.results is not None:
                    if isinstance(dr.results, list):
                        dice_results = list(dr.results)
                    elif isinstance(dr.results, int):
                        dice_results = [dr.results]

                damage_bonus_breakdown = (value_log_rows(value_breakdown(damage.damage_bonus))
                                          if damage and damage.damage_bonus else [])

                num_dice = len(dice_results)
                dice_size = damage.damage_dice if damage else 6
                dice_str = f"{num_dice}d{dice_size}"

                damage_roll_displays.append(DamageRollDisplay(
                    dice_str=dice_str,
                    dice_results=dice_results,
                    bonus=dr.bonus,
                    total=dr.total,
                    damage_type=damage_type,
                    bonus_breakdown=damage_bonus_breakdown
                ))

        total_damage = self.total_damage if is_hit else 0

        target_hp = target_entity.get_hp() if target_entity else None

        is_opportunity_attack = "opportunity" in (self.name or "").lower()

        compact_text = format_attack_compact(
            source_name, target_name, outcome, total_damage
        )

        verbose_text = format_attack_verbose(
            source_name, target_name, weapon_name,
            attack_roll, target_ac, outcome,
            damage_roll_displays, total_damage,
            is_opportunity_attack
        )

        detailed_text = format_attack_detailed(
            source_name, target_name, weapon_name,
            attack_roll, attack_breakdown,
            target_ac, ac_breakdown, outcome,
            damage_roll_displays, total_damage,
            is_opportunity_attack
        )

        data = AttackLogData(
                attacker_name=source_name,
                attacker_uuid=str(self.source_entity_uuid),
                target_name=target_name,
                target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else '',
                weapon_name=weapon_name,
                weapon_slot=self.weapon_slot.value if self.weapon_slot else None,
                attack_roll=attack_roll,
                attack_breakdown=attack_breakdown,
                advantage_breakdown=advantage_breakdown,
                target_ac=target_ac,
                ac_breakdown=ac_breakdown,
                outcome=outcome,
                is_hit=is_hit,
                is_crit=is_crit,
                damage_rolls=damage_roll_displays,
                total_damage=total_damage,
                target_hp=target_hp,
                is_opportunity_attack=is_opportunity_attack,
                is_long_range=self.is_long_range,
                is_threatened=self.is_threatened,
            )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ATTACK,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=data,
            success=is_hit
        )


def create_weapon_attack_declaration_event(
    *,
    action_name: str,
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID],
    weapon_slot: WeaponSlot,
    costs: Iterable[BaseCost],
    parent_event: Optional[Event] = None,
    use_register: bool = True,
    override_ability: Optional[AbilityName] = None,
    append_weapon_to_name: bool = False,
) -> AttackEvent:
    """Snapshot one equipped or unarmed attack into a cold declaration.

    All ordinary weapon-attack actions use this boundary so a miss retains the
    same weapon name and damage-type metadata as a hit. Damage packets are
    resolved later and cannot be the source of presentation identity.
    """
    source_entity = Entity.get(source_entity_uuid)
    target_entity = (
        BaseBlock.get(target_entity_uuid)
        if target_entity_uuid is not None
        else None
    )
    weapon_name: Optional[str] = None
    damage_types: List[DamageType] = []
    source_item_uuid: Optional[UUID] = None
    source_item_presentation = None
    if source_entity is not None:
        source_metadata = source_entity.equipment.snapshot_attack_source_metadata(weapon_slot)
        weapon_name = source_metadata.name
        damage_types = list(source_metadata.damage_types)
        source_item_uuid = source_metadata.item_uuid
        weapon = source_entity.equipment.get_weapon(weapon_slot)
        if weapon is not None:
            source_item_presentation = weapon.to_item_presentation_state()

    event_name = (
        f"{action_name} ({weapon_name})"
        if append_weapon_to_name and weapon_name is not None
        else action_name
    )
    is_object = isinstance(target_entity, BaseItem)
    placement = get_map().get_object_placement(target_entity.uuid) if isinstance(target_entity, BaseItem) else None
    contact = None
    if source_entity is not None and isinstance(target_entity, BaseItem):
        weapon_range = source_entity.get_weapon_range(weapon_slot)
        if weapon_range is not None:
            contact = get_map().attack_object_contact(source_entity.uuid, target_entity.uuid,
                range_feet=weapon_range.long or weapon_range.normal,
                access=source_entity.get_weapon_physical_access(weapon_slot), subjective=True)
    return AttackEvent(
        target_kind="object" if is_object else "creature",
        target_position=contact if is_object else (target_entity.position if target_entity else None),
        target_base_height_steps=placement.base_height_steps if placement else None,
        attack_source_kind="equipped" if source_item_uuid else "unarmed",
        name=event_name,
        parent_event=parent_event.uuid if parent_event else None,
        phase=EventPhase.DECLARATION,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid,
        weapon_slot=weapon_slot,
        costs=[BaseCost.model_validate(cost) for cost in costs],
        use_register=use_register,
        source_entity_name=(
            source_entity.name
            if source_entity is not None
            else None
        ),
        target_entity_name=(
            target_entity.name
            if target_entity is not None
            else None
        ),
        weapon_name=weapon_name,
        override_ability=override_ability,
        attack_is_magical=(weapon.attack_is_magical(source_entity_uuid) if source_entity is not None and weapon is not None else False),
        damage_types=damage_types,
        source_item_uuid=source_item_uuid,
        source_item_presentation=source_item_presentation,
    )



def weapon_slot_is_eligible(source: Entity, weapon_slot: WeaponSlot, target_uuid: Optional[UUID]) -> bool:
    """The weapon in one slot may attack one target with the actor's hands."""
    weapon = source.equipment.get_weapon(weapon_slot)
    if weapon is not None and weapon.spell_attack_profile is not None:
        if weapon.spell_attack_profile.wielder_uuid!=source.uuid or not weapon.contributions_active():
            return False
        target=BaseBlock.get(target_uuid) if target_uuid else None
        if target is not None and SpellProtectionRegistry.is_protected(target.position,source.position,weapon.spell_attack_profile.effect_origin.base_spell_level or 2):
            return False
    return weapon is None or weapon_slot in source.equipment.compatible_slots_for_actor(weapon)


def weapon_attack_range(
    source: Entity, weapon_slot: WeaponSlot, natural: Optional[NaturalWeaponSpec],
    shield_attack: Optional[ShieldAttackSpec] = None,
) -> Range:
    """The range one weapon attack is measured against: the shield attack's or the natural weapon's, else the
    slot's weapon or unarmed reach."""
    if shield_attack is not None:
        return shield_attack.range
    return natural.range if natural is not None else source.get_weapon_range(weapon_slot)


def weapon_reach(
    source: Entity, weapon_slot: WeaponSlot, natural: Optional[NaturalWeaponSpec],
    target_uuid: Optional[UUID], name: str, shield_attack: Optional[ShieldAttackSpec] = None,
) -> Tuple[Optional[str], Optional[Range], Optional[Tuple[int, int]], bool, Optional[ObjectContact]]:
    """One weapon's reach to one target: (error, weapon range, attacked position, long range, object contact).

    Ranged attacks inside normal range are allowed; between normal and long
    range they are long-range attacks. Melee attacks require distance within
    weapon reach. An object is attacked at its physical contact position,
    traced from the attacker's position with what it perceives; the trace is
    returned with its query (None for a creature target).
    """
    creature = Entity.get(target_uuid) if target_uuid is not None else None
    target = BaseBlock.get(target_uuid) if target_uuid is not None else None
    weapon_range = weapon_attack_range(source, weapon_slot, natural, shield_attack)
    if weapon_range is None:
        return f"Weapon range not found for {name}", None, None, False, None
    contact: Optional[ObjectContact] = None
    if creature is not None:
        target_position = creature.position
    elif isinstance(target, BaseItem):
        if not target.is_active or not target.is_targetable:
            return "Object cannot be attacked", weapon_range, None, False, None
        access = ((PhysicalAccess.PROJECTILE if weapon_range.type is RangeType.RANGE else PhysicalAccess.NATURAL)
                  if natural is not None else PhysicalAccess.WEAPON if shield_attack is not None
                  else source.get_weapon_physical_access(weapon_slot))
        range_feet, origin = weapon_range.long or weapon_range.normal, source.position
        contact = ObjectContact(source.uuid, target.uuid, range_feet, access, True, origin, get_map().attack_object_contact(
            source.uuid, target.uuid, range_feet=range_feet, access=access, subjective=True, origin=origin))
        if contact.position is None:
            return "Object is out of physical reach", weapon_range, None, False, contact
        target_position = contact.position
    else:
        return f"Target entity not found for {name}", weapon_range, None, False, None
    distance_feet = source.senses.get_feet_distance(target_position)
    if weapon_range.type == RangeType.RANGE:
        if distance_feet <= weapon_range.normal:
            return None, weapon_range, target_position, False, contact
        if weapon_range.long is not None and distance_feet <= weapon_range.long:
            return None, weapon_range, target_position, True, contact
        return f"Target entity not in range for {name}", weapon_range, target_position, False, contact
    if weapon_range.type == RangeType.REACH and distance_feet > weapon_range.normal:
        return f"Target entity not in reach for {name}", weapon_range, target_position, False, contact
    return None, weapon_range, target_position, False, contact


def weapon_attack_admission(
    scan: ActorScan, source: Entity, weapon_slot: WeaponSlot, natural: Optional[NaturalWeaponSpec],
    target_uuid: Optional[UUID], name: str, shield_attack: Optional[ShieldAttackSpec] = None,
) -> Tuple[Optional[str], Optional[ObjectContact]]:
    """Shield or hand permission, range or reach, and sight of a creature target for one weapon attack,
    with the object contact `weapon_reach` traced."""
    if shield_attack is not None and not source.equipment.shield_attack_is_eligible(shield_attack):
        return "Declared shield is no longer equipped", None
    if natural is None and shield_attack is None and not weapon_slot_is_eligible(source, weapon_slot, target_uuid):
        return "Declared weapon or hand permission is unavailable", None
    error, _, _, _, contact = weapon_reach(source, weapon_slot, natural, target_uuid, name, shield_attack)
    if error is not None or target_uuid is None or Entity.get(target_uuid) is None:
        return error, contact
    record = scan.creatures.get(target_uuid)
    if record is None or not record.visual:
        return f"Target entity not in line of sight for {name}", None
    return None, None


def weapon_attack_error(
    scan: ActorScan, source: Entity, weapon_slot: WeaponSlot, natural: Optional[NaturalWeaponSpec],
    target_uuid: Optional[UUID], name: str,
) -> Optional[str]:
    """The error of `weapon_attack_admission`."""
    return weapon_attack_admission(scan, source, weapon_slot, natural, target_uuid, name)[0]


def grant_weapon_attack_batch(source_uuid: UUID,declaration: ActionEvent,execution: ActionEvent) -> None:
    """Grant native Extra Attack credit for one paid weapon-attempt action."""
    source=Entity.get(source_uuid)
    if source is None or not source.action_economy.grant_attack_batch(execution.lineage_uuid):
        return
    if "ExtraAttacksGranted" not in source.active_conditions:
        source.add_condition(ExtraAttacksGranted(source_entity_uuid=source.uuid,target_entity_uuid=source.uuid),
            parent_event=declaration)


@_core_action_identity(
    content_id="action.attack",
    display_name="Attack",
    description="Make a weapon attack against a creature.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Actions in Combat — Attack",
    sort_order=30,
)


class Attack(BaseAction):
    """Weapon attack action.

    Validation requires the target to be visible and inside the equipped weapon's
    range or reach. Off-hand attacks cost a bonus action instead of an action.
    Templates should receive a target through `set_target_entity()` before
    `pre_validate()` or `instantiate()`.
    """
    creates = (ExtraAttacksGranted,)

    ordinary_off_hand_default: ClassVar[bool] = True
    declaration_name: ClassVar[str | None] = None
    append_weapon_to_name: ClassVar[bool] = False

    name: str = Field(default="Attack", description="Human-readable attack action name.")
    description: str = Field(default="Attack a target", description="Attack action description.")
    target_type: TargetType = Field(default=TargetType.CREATURE_OR_OBJECT, description="Attack targets one entity.")
    # Attack may strike an invulnerable target. Its ordinary targetability,
    # sight and reach checks still apply; HP only determines damage response.
    object_target_policy: Literal["damageable", "active"] = "active"
    weapon_slot: WeaponSlot = Field(description="Weapon slot used by the attack.")
    action_category: ActionCategory = Field(default=ActionCategory.ATTACK, description="Attack action category.")
    restricted_action_kinds: ClassVar[frozenset[RestrictedActionKind]] = (
        frozenset({RestrictedActionKind.WEAPON_ATTACK})
    )
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(name="Attack Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
        ],
        description="Action economy costs required by this attack.",
    )
    override_ability: Optional[AbilityName] = Field(
        default=None,
        description="Ability override for attack and damage rolls.",
    )




    additional_damages: List[Damage] = Field(default_factory=empty_list)

    def get_natural_weapon(self) -> Optional[NaturalWeaponSpec]:
        return None

    def get_shield_attack(self) -> Optional[ShieldAttackSpec]:
        return None

    def get_attack_source_metadata(self) -> Optional[AttackSourceMetadata]:
        source = Entity.get(self.source_entity_uuid)
        if source is None:
            return None
        shield = self.get_shield_attack()
        if shield is not None:
            return AttackSourceMetadata(kind="equipped", weapon_slot=self.weapon_slot,
                name=shield.name, damage_types=(shield.damage_type,), item_uuid=shield.item_uuid)
        natural = self.get_natural_weapon()
        if natural is not None:
            return AttackSourceMetadata(kind="natural", weapon_slot=self.weapon_slot,
                name=natural.name, damage_types=(natural.damage_type,), magical=natural.magical)
        return source.equipment.snapshot_attack_source_metadata(self.weapon_slot)


    def get_range(self) -> Optional[Range]:
        source = Entity.get(self.source_entity_uuid)
        return source.get_weapon_range(self.weapon_slot) if source is not None else None

    def target_reach_feet(self) -> Optional[int]:
        """The larger of the weapon range's normal and long distances: `weapon_reach` admits no target beyond it."""
        source = Entity.get(self.source_entity_uuid)
        if source is None:
            return None
        weapon_range = weapon_attack_range(source, self.weapon_slot, self.get_natural_weapon(), self.get_shield_attack())
        return max(weapon_range.normal, weapon_range.long or 0)

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        if self.get_shield_attack() is not None:
            return PhysicalAccess.WEAPON
        source = Entity.get(self.source_entity_uuid)
        return source.get_weapon_physical_access(self.weapon_slot) if source is not None else None

    @model_validator(mode="after")
    def adjust_cost_for_off_hand(self) -> Self:
        """Select the ordinary off-hand cost unless the caller supplied one.

        Composite rules such as Multiattack deliberately construct child
        attacks with ``costs=[]`` because the parent action owns the cost.
        Reaction and restricted-action callers may likewise supply another
        explicit budget.  Slot-based defaulting must not overwrite either.
        """
        if (
            self.ordinary_off_hand_default
            and self.weapon_slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF)
            and "costs" not in self.model_fields_set
        ):
            owner = Entity.get(self.source_entity_uuid)
            weapon = owner.equipment.get_weapon(self.weapon_slot) if owner else None
            if weapon is None or not weapon.is_body_attack:
                self.costs = [Cost(name="Off-Hand Attack Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)]
        return self

    def get_outcome_profile(self) -> Optional[ActionOutcomeProfile]:
        """Return the actor-baseline stochastic profile for this weapon attack."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        profile = build_weapon_attack_outcome_profile(
            actor,
            self.weapon_slot,
            self.override_ability,
            natural_weapon=self.get_natural_weapon(), shield_attack=self.get_shield_attack(),
        )
        if profile is None:
            return profile
        extra_damage_rolls: list[DamageRollProfile] = []
        for condition in actor.active_conditions.values():
            if not condition.contributions_active():
                continue
            for damage_profile in condition.get_action_damage_roll_profiles(self):
                if isinstance(damage_profile, DamageRollProfile):
                    extra_damage_rolls.append(damage_profile)
        if not extra_damage_rolls:
            return profile
        return profile.model_copy(update={
            "damage_rolls": tuple(profile.damage_rolls) + tuple(extra_damage_rolls),
        })

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Return target-effect riders contributed by active actor traits."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        profiles: list[ActionTargetEffectProfile] = []
        for condition in actor.active_conditions.values():
            profile = condition.get_action_target_effect_profile(self)
            if isinstance(profile, ActionTargetEffectProfile):
                profiles.append(profile)
        if not profiles:
            return None
        if len(profiles) == 1:
            return profiles[0]
        branches = []
        seen_effect_ids: set[str] = set()
        for profile in profiles:
            for branch in profile.branches:
                if branch.effect_id in seen_effect_ids:
                    continue
                seen_effect_ids.add(branch.effect_id)
                branches.append(branch)
        return ActionTargetEffectProfile(
            semantic_id="attack.weapon.hit_riders",
            branches=tuple(branches),
        )

    @staticmethod
    def equipped_source_is_eligible(event: AttackEvent, source: Entity) -> bool:
        """Recheck the declared physical weapon and actor-owned hand permission."""
        if event.shield_attack is not None:
            return (event.weapon_slot is WeaponSlot.MELEE_OFF
                and event.source_item_uuid == event.shield_attack.item_uuid
                and source.equipment.shield_attack_is_eligible(event.shield_attack))
        if event.natural_weapon is not None:
            return True
        weapon = source.equipment.get_weapon(event.weapon_slot)
        if event.source_item_uuid is not None and (weapon is None or weapon.uuid != event.source_item_uuid):
            return False
        return weapon_slot_is_eligible(source, event.weapon_slot, event.target_entity_uuid)

    @staticmethod
    def attack_consequences(execution_event: AttackEvent, source_entity_uuid: UUID, *,
                            physical_access: Optional[PhysicalAccess] = None,
                            on_hit: Callable[[AttackEvent], AttackEvent] | None = None) -> Optional[AttackEvent]:
            """
            Resolve an attack roll, damage rolls, and damage application.

            Args:
                execution_event: Execution-phase attack event.
                source_entity_uuid: Attacking entity UUID.

            Returns:
                Completed attack event, canceled event, or `None`.
            """
            started = time.perf_counter()
            source_entity = Entity.get(source_entity_uuid)
            target_entity_uuid = execution_event.target_entity_uuid
            weapon_slot = execution_event.weapon_slot
            if not source_entity:
                return execution_event.cancel(status_message=f"Source entity not found for {execution_event.name}")
            if not isinstance(source_entity, Entity):
                return execution_event.cancel(status_message=f"Source entity not found for {execution_event.name}")
            if not Attack.equipped_source_is_eligible(execution_event, source_entity):
                return execution_event.cancel(status_message="Declared weapon or hand permission is no longer available")
            if not target_entity_uuid:
                return execution_event.cancel(status_message=f"Target entity uuid not present for {execution_event.name}")
            target_entity = BaseBlock.get(target_entity_uuid)
            if not target_entity:
                return execution_event.cancel(status_message=f"Target entity not found for {execution_event.name}")
            if not isinstance(target_entity, (Entity, BaseItem)):
                return execution_event.cancel(status_message=f"Target entity not found for {execution_event.name}")
            record_action_timing("attack.resolve_entities_ms", started)

            return Attack._resolve_attack(
                execution_event=execution_event,
                source_entity=source_entity,
                target_entity=target_entity,
                target_entity_uuid=target_entity_uuid,
                weapon_slot=weapon_slot,
                physical_access=physical_access,
                on_hit=on_hit,
            )

    @staticmethod
    def _resolve_attack(
        *,
        execution_event: AttackEvent,
        source_entity: Entity,
        target_entity: Entity | BaseItem,
        target_entity_uuid: UUID,
        weapon_slot: WeaponSlot,
        physical_access: Optional[PhysicalAccess],
        on_hit: Callable[[AttackEvent], AttackEvent] | None = None,
    ) -> AttackEvent:
            """Resolve one attack: both sides read against each other, then roll, outcome and damage."""
            source_entity_uuid = source_entity.uuid
            started = time.perf_counter()
            override_ability = execution_event.override_ability
            weapon = None if execution_event.natural_weapon else source_entity.equipment.get_weapon(weapon_slot)
            attack_value, attack_value_context = source_entity.weapon_attack_value(
                ValueRead(source_entity_uuid, target_entity_uuid), weapon_slot,
                override_ability=override_ability, natural_weapon=execution_event.natural_weapon, shield_attack=execution_event.shield_attack)
            ac_value = (target_entity.armor_class_value(ValueRead(target_entity_uuid, source_entity_uuid))
                        if isinstance(target_entity, Entity)
                        else parts(ModifiableValue(source_entity_uuid=target_entity.uuid,
                            base=target_entity.armor_class, name="Object AC", use_register=False)))
            attack_context: Dict[str, Any] = {
                **(attack_value_context or {}),
                "weapon_slot": weapon_slot.value,
                "weapon_name": execution_event.weapon_name or "Unarmed",
                "range_type": execution_event.range.type.value if execution_event.range else None,
                "is_long_range": execution_event.is_long_range,
            }
            record_action_timing("attack.compute_attack_bonus_ac_ms", started)

            started = time.perf_counter()
            is_ranged = execution_event.range is not None and execution_event.range.type == RangeType.RANGE

            if is_ranged and execution_event.is_long_range:
                attack_value = with_rows(attack_value, (Row(Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
                        name="Long Range",
                        value=AdvantageStatus.DISADVANTAGE,
                        source_entity_uuid=source_entity_uuid,
                        target_entity_uuid=target_entity_uuid
                    )),))

            if is_ranged and execution_event.is_threatened:
                attack_value = with_rows(attack_value, (Row(Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
                        name="Threatened (Ranged)",
                        value=AdvantageStatus.DISADVANTAGE,
                        source_entity_uuid=source_entity_uuid,
                        target_entity_uuid=target_entity_uuid
                    )),))
            record_action_timing("attack.ranged_disadvantage_modifiers_ms", started)

            started = time.perf_counter()
            # The armor class reads the attacker's outgoing rows in the attack value's
            # composition context; the attack's own rows read the attack context: that
            # composition context (attack ability, range) under the attack's own facts,
            # whose range type (the attack's, from `weapon_reach`) replaces the weapon's.
            attack_event = execution_event.phase_to(
                new_phase=EventPhase.EXECUTION,
                status_message="Rolling attack",
                attack_bonus=read_value(attack_value, ValueRead(source_entity_uuid, target_entity_uuid, attack_context,
                    outgoing_of(ac_value, None))),
                ac=read_value(ac_value, ValueRead(target_entity_uuid, source_entity_uuid, None,
                    outgoing_of(attack_value, attack_value_context))),
            )
            record_action_timing("attack.phase_to_roll_ms", started)

            if attack_event.shield_attack is not None and not Attack.equipped_source_is_eligible(attack_event, source_entity):
                return attack_event.cancel(status_message="Declared shield is no longer equipped")
            if not attack_event.canceled and not Attack._contact_remains_reachable(
                attack_event, source_entity, target_entity,
                physical_access or source_entity.get_weapon_physical_access(weapon_slot),
            ):
                attack_event = attack_event.cancel(status_message="A physical barrier interrupted the attack")
            if attack_event.canceled:
                return attack_event
            # Reactions at EXECUTION (Parry, Protection) replace the reads on the event.
            attack_reading, ac_reading = attack_event.attack_bonus, attack_event.ac
            if attack_reading is None or ac_reading is None:
                raise RuntimeError("An attack lost its attack bonus or armor class read")

            started = time.perf_counter()
            dice_roll = source_entity.roll_d20(
                attack_reading,
                RollType.ATTACK,
                weapon_slot=weapon_slot,
                parent_event=attack_event.uuid,
            )
            record_action_timing("attack.roll_d20_ms", started)
            started = time.perf_counter()
            crit_threshold = (source_entity.get_spell_crit_threshold() if weapon is not None and weapon.spell_attack_profile is not None
                else source_entity.get_crit_threshold(weapon_slot))
            attack_outcome = determine_attack_outcome(dice_roll, ac_reading.normalized_score, crit_threshold)
            weapon = source_entity.equipment.get_weapon(weapon_slot)
            missile_size = (execution_event.natural_weapon.missile_size if execution_event.natural_weapon is not None
                            else weapon.missile_size if weapon is not None else "ordinary")
            interceptor = (get_map().missile_interceptor(source_entity.position,
                execution_event.target_position or target_entity.position, missile_size)
                if is_ranged else None)
            if interceptor is not None:
                attack_outcome = AttackOutcome.MISS
            record_action_timing("attack.determine_outcome_ms", started)

            started = time.perf_counter()
            attack_event = attack_event.post(
                dice_roll=dice_roll,
                attack_outcome=attack_outcome,
                intercepted_by_condition_uuid=interceptor[0] if interceptor is not None else None,
                projectile_deflection_position=interceptor[1] if interceptor is not None else None,
                status_message=("Wind deflected the missile" if interceptor is not None
                                else f"Attack rolled {dice_roll.total} and {attack_outcome}")
            )
            record_action_timing("attack.post_attack_roll_ms", started)
            if attack_event.shield_attack is not None and not Attack.equipped_source_is_eligible(attack_event, source_entity):
                return attack_event.cancel(status_message="Declared shield is no longer equipped")
            if not attack_event.canceled and not Attack._contact_remains_reachable(
                attack_event, source_entity, target_entity,
                physical_access or source_entity.get_weapon_physical_access(weapon_slot),
            ):
                attack_event = attack_event.cancel(status_message="A physical barrier interrupted the attack")

            if attack_event.canceled:
                return attack_event

            if attack_event.attack_outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
                started = time.perf_counter()
                attack_event = attack_event.phase_to(
                    EventPhase.EFFECT,
                    status_message=f"Attack missed"
                )
                if not attack_event.canceled:
                    source_entity.equipment.active_weapon_set = (source_entity.equipment.weapon_set_for_slot(weapon_slot)
                        if execution_event.attack_source_kind == "equipped" else WeaponSet.NONE)
                completion_event = attack_event.with_updates(
                    status_message=f"Attack missed"
                )
                record_action_timing("attack.miss_completion_ms", started)
                return completion_event

            if on_hit is not None:
                attack_event=on_hit(attack_event)
                if attack_event.canceled:
                    return attack_event
            started = time.perf_counter()
            damages = source_entity.get_damages(weapon_slot, target_entity_uuid, override_ability=override_ability, natural_weapon=execution_event.natural_weapon, shield_attack=execution_event.shield_attack)
            magical_attack = execution_event.attack_is_magical
            for damage in damages: damage.attack_magical = magical_attack
            damages.extend(attack_event.additional_damages)
            record_action_timing("attack.get_damages_ms", started)
            started = time.perf_counter()
            attack_event = attack_event.phase_to(
                EventPhase.EFFECT,
                is_last=False,
                status_message=f"Damages: {[(damage.dice_numbers,damage.damage_dice,damage.read_bonus().normalized_score if damage.damage_bonus else 0,damage.damage_type) for damage in damages]}",
                damages=damages
            )
            record_action_timing("attack.phase_to_damage_effect_ms", started)

            if attack_event.canceled:
                return attack_event
            source_entity.equipment.active_weapon_set = (source_entity.equipment.weapon_set_for_slot(weapon_slot)
                        if execution_event.attack_source_kind == "equipped" else WeaponSet.NONE)

            if attack_event.attack_outcome is not None and attack_event.attack_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
                started = time.perf_counter()
                crit_extra_dice = (source_entity.get_spell_crit_extra_dice() if weapon is not None and weapon.spell_attack_profile is not None
                    else source_entity.get_crit_extra_dice(weapon_slot))
                damage_packets = []
                for damage in damages:
                    dice = damage.get_dice(attack_outcome=attack_event.attack_outcome, crit_extra_dice=crit_extra_dice)
                    roll = dice.roll
                    roll = finalize_spell_damage_roll(damage,roll,parent_event=attack_event)
                    damage_packets.append(
                        DamageRollPacket(
                            damage=damage,
                            original_roll=roll,
                            final_roll=roll,
                        )
                    )
                record_action_timing("attack.roll_damage_dice_ms", started)

                started = time.perf_counter()
                damage_roll_event = DamageRollResultEvent(
                    source_entity_uuid=source_entity.uuid,
                    target_entity_uuid=target_entity.uuid,
                    source_entity_name=source_entity.name,
                    target_entity_name=target_entity.name,
                    weapon_slot=None if weapon is not None and weapon.spell_attack_profile is not None else weapon_slot,
                    attack_kind=("spell" if weapon is not None and weapon.spell_attack_profile is not None else "natural" if execution_event.natural_weapon else
                        "weapon" if execution_event.shield_attack is not None else "unarmed" if weapon is None or weapon.is_body_attack else "weapon"),
                    source_item_uuid=execution_event.shield_attack.item_uuid if execution_event.shield_attack is not None else weapon.uuid if weapon is not None else None,
                    attack_outcome=attack_event.attack_outcome,
                    attack_advantage=dice_roll.advantage_status,
                    damage_packets=damage_packets,
                    parent_event=attack_event.uuid,
                    phase=EventPhase.DECLARATION
                )
                record_action_timing("attack.create_damage_roll_event_ms", started)

                started = time.perf_counter()
                damage_roll_event = damage_roll_event.phase_to(
                    EventPhase.EFFECT,
                    status_message="Damage dice rolled"
                )
                record_action_timing("attack.damage_roll_effect_ms", started)

                if damage_roll_event.canceled:
                    return attack_event.cancel(
                        status_message=damage_roll_event.status_message or "Damage application interrupted",
                    )

                damage_rolls = [
                    packet.final_roll
                    for packet in damage_roll_event.damage_packets
                ]

                started = time.perf_counter()
                damage_roll_event.phase_to(EventPhase.COMPLETION)
                record_action_timing("attack.damage_roll_completion_ms", started)
                damages = [
                    packet.damage
                    for packet in damage_roll_event.damage_packets
                ]
                started = time.perf_counter()
                total_damage = sum(roll.total for roll in damage_rolls)
                record_action_timing("attack.sum_damage_ms", started)

                started = time.perf_counter()
                if isinstance(target_entity, BaseItem):
                    actual_damage = target_entity.receive_damage(
                        total_damage, damages[0].damage_type, source_entity.uuid,
                        parent_event=attack_event, damage_rolls=damage_rolls, damages=damages)
                else:
                    actual_damage = target_entity.receive_damage(
                        amount=total_damage,
                        damage_type=damages[0].damage_type,
                        source_entity_uuid=source_entity.uuid,
                        damage_rolls=damage_rolls,
                        damages=damages,
                        parent_event=attack_event.uuid,
                        critical_hit=attack_event.attack_outcome == AttackOutcome.CRIT,
                        effect_origin=weapon.spell_attack_profile.effect_origin if weapon is not None and weapon.spell_attack_profile is not None else None,
                        impact_direction=(target_entity.position[0] - source_entity.position[0],
                                          target_entity.position[1] - source_entity.position[1]),
                    )
                record_action_timing("attack.receive_damage_ms", started)

                started = time.perf_counter()
                attack_event = attack_event.phase_to(
                    new_phase=EventPhase.EFFECT,
                    is_first=False,
                    damage_rolls=damage_rolls,
                    damages=damages,
                    total_damage=actual_damage,
                    status_message=f"Damages taken: {[damage.total for damage in damage_rolls]}"
                )
                record_action_timing("attack.phase_to_post_damage_effect_ms", started)
            else:
                damage_rolls = None

            started = time.perf_counter()
            completion_event = attack_event.with_updates(
                status_message="Attack completed",
                damage_rolls=damage_rolls,
            )
            record_action_timing("attack.final_completion_ms", started)
            return completion_event

    @staticmethod
    def _contact_remains_reachable(event: AttackEvent, source: Entity,
                                   target: Entity | BaseItem, access: PhysicalAccess) -> bool:
        grid = get_map()
        if isinstance(target, BaseItem):
            limit = (event.range.long or event.range.normal) if event.range else 5
            return target.is_active and target.is_targetable and grid.attack_object_contact(
                source.uuid, target.uuid, range_feet=limit, access=access) is not None
        return grid.can_reach_between(source.position, target.position, access, source.uuid)

    def _on_costs_committed(self, declaration: ActionEvent, execution: ActionEvent) -> None:
        super()._on_costs_committed(declaration, execution)
        if not any(cost.cost_type == "actions" and cost.cost > 0 for cost in self.effective_costs):
            return
        grant_weapon_attack_batch(self.source_entity_uuid,declaration,execution)

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for the attack action, with the weapon's range facts.

        The attack roll reads `range`, `is_long_range`, `target_position` and
        `is_threatened` from the execution event.
        """
        event = create_weapon_attack_declaration_event(
            action_name=self.declaration_name or self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            weapon_slot=self.weapon_slot,
            costs=self.effective_costs,
            parent_event=parent_event,
            use_register=use_register,
            override_ability=self.override_ability,
            append_weapon_to_name=self.append_weapon_to_name,
        )
        shield = self.get_shield_attack()
        if shield is not None:
            source = Entity.get(self.source_entity_uuid)
            item = source.equipment.get_equipped_shield() if source is not None else None
            event = event.model_copy(update={"shield_attack": shield, "range": shield.range,
                "weapon_name": shield.name, "attack_source_kind": "equipped",
                "source_item_uuid": shield.item_uuid,
                "source_item_presentation": item.to_item_presentation_state() if item is not None else None,
                "damage_types": [shield.damage_type], "attack_is_magical": False})
        natural = self.get_natural_weapon()
        if natural is not None:
            event = event.model_copy(update={"natural_weapon": natural, "range": natural.range,
                "weapon_name": natural.name, "attack_source_kind": "natural",
                "source_item_uuid": None, "source_item_presentation": None,
                "damage_types": [natural.damage_type], "attack_is_magical": natural.magical})
        update: dict = {
            "additional_damages": list(self.additional_damages),
            "damage_types": list(dict.fromkeys([*event.damage_types, *(damage.damage_type for damage in self.additional_damages)]))}
        source = Entity.get(self.source_entity_uuid)
        if source is not None:
            _, weapon_range, target_position, is_long_range, _ = weapon_reach(source, self.weapon_slot, natural,
                event.target_entity_uuid, self.declaration_name or self.name, shield)
            update.update(target_position=target_position, range=weapon_range, is_long_range=is_long_range,
                is_threatened=weapon_range is not None and weapon_range.type == RangeType.RANGE and source.is_threatened())
        return event.model_copy(update=update)

    @final
    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """The error of `rule_admission`, which an attack form overrides instead."""
        return self.rule_admission(scan, selection)[0]

    def rule_admission(self, scan: ActorScan, selection: ActionSelection) -> Tuple[Optional[str], Optional[ObjectContact]]:
        """Weapon and hand permission, range or reach, and sight of a creature target, with the object contact
        the weapon's reach traced."""
        source = Entity.get(self.source_entity_uuid)
        if source is None:
            return "Declared weapon or hand permission is unavailable", None
        return weapon_attack_admission(scan, source, self.weapon_slot, self.get_natural_weapon(),
            selection.target_uuids[0] if selection.target_uuids else None, self.declaration_name or self.name,
            self.get_shield_attack())

    def _apply(self, execution_event: AttackEvent) -> Optional[AttackEvent]:
        """Apply the attack action."""
        return Attack.attack_consequences(execution_event, self.source_entity_uuid, physical_access=self.get_physical_access())

    def _apply_costs(self, execution_event: AttackEvent) -> Optional[AttackEvent]:
        """Commit attack costs before execution is published."""
        source = Entity.get(self.source_entity_uuid)
        if source is None or not Attack.equipped_source_is_eligible(execution_event, source):
            return execution_event.cancel(status_message="Declared weapon or hand permission is no longer available")
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)



    def apply(self, parent_event: Optional[Event] = None) -> Optional[AttackEvent]:
        """Override to provide specific return type."""
        result = super().apply(parent_event)
        return cast(AttackEvent, result) if result else None


@_core_action_identity(
    content_id="action.dash",
    display_name="Dash",
    description="Gain additional movement equal to current speed.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Actions in Combat — Dash",
    sort_order=40,
)
class Dash(BaseAction):
    """Dash action that grants extra movement for the current turn.

    Applies the Dashing condition which adds movement equal to current speed.
    Lasts until the start of your next turn (duration=1, advanced at turn start).
    """
    creates = (Dashing,)

    name: str = Field(default="Dash", description="Human-readable dash action name.")
    description: str = Field(default="Gain extra movement equal to your speed", description="Dash action description.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Dash targets self")
    restricted_action_kinds: ClassVar[frozenset[RestrictedActionKind]] = (
        frozenset({RestrictedActionKind.DASH})
    )
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Dash Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Dash.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for Dash."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Dash",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name,
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply Dashing for one round."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        dashing = Dashing(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        dashing.duration.duration_type = DurationType.ROUNDS
        dashing.duration.duration = 1

        entity.add_condition(dashing, parent_event=execution_event)

        current_speed = entity.action_economy.current_speed()
        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Applied Dashing - gained {current_speed}ft extra movement"
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply Dash action costs."""
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


@_core_action_identity(
    content_id="action.dodge",
    display_name="Dodge",
    description="Focus on defense until the start of the next turn.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Actions in Combat — Dodge",
    sort_order=50,
)
class Dodge(BaseAction):
    """Dodge action that applies the Dodging condition for one round.

    Applies the Dodging condition which gives:
    - Disadvantage on attack rolls against you (if you can see the attacker)
    - Advantage on Dexterity saving throws

    Lasts until the start of your next turn (duration=1, advanced at turn start).
    """
    creates = (Dodging,)

    name: str = Field(default="Dodge", description="Human-readable dodge action name.")
    description: str = Field(default="Attackers have disadvantage, advantage on DEX saves", description="Dodge action description.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Dodge targets self")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Dodge Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Dodge.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for Dodge."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Dodge",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name,
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply Dodging for one round."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        dodging = Dodging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        dodging.duration.duration_type = DurationType.ROUNDS
        dodging.duration.duration = 1

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message="Applying Dodging condition"
        )

        entity.add_condition(dodging, parent_event=effect_event)

        return effect_event.with_updates(
            status_message="Applied Dodging - attackers have disadvantage"
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply Dodge action costs."""
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


@_core_action_identity(
    content_id="action.disengage",
    display_name="Disengage",
    description="Move without provoking opportunity attacks for the turn.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Actions in Combat — Disengage",
    sort_order=60,
)
class Disengage(BaseAction):
    """Disengage action that suppresses opportunity attacks for one round.

    Applies the Disengaging condition which prevents opportunity attacks.
    Lasts until the start of your next turn (duration=1, advanced at turn start).
    """
    creates = (Disengaging,)

    name: str = Field(default="Disengage", description="Human-readable disengage action name.")
    description: str = Field(default="Movement doesn't provoke opportunity attacks", description="Disengage action description.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Disengage targets self")
    restricted_action_kinds: ClassVar[frozenset[RestrictedActionKind]] = (
        frozenset({RestrictedActionKind.DISENGAGE})
    )
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Disengage Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Disengage.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for Disengage."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Disengage",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name,
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply Disengaging for one round."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        disengaging = Disengaging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        disengaging.duration.duration_type = DurationType.ROUNDS
        disengaging.duration.duration = 1

        entity.add_condition(disengaging, parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message="Applied Disengaging - movement won't provoke OAs"
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply Disengage action costs."""
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


@_core_action_identity(
    content_id="action.drop_concentration",
    display_name="Drop Concentration",
    description="Voluntarily end concentration on an active spell.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Spellcasting: Concentration",
    sort_order=70,
)
class DropConcentration(BaseAction):
    """Drop concentration on a spell voluntarily.

    D&D 5e allows ending concentration at any time (no action required).
    If target_spell is set, drops only that spell's slot (multi-slot support).
    Otherwise removes the entire Concentrating condition and all linked spell effects.
    """

    name: str = Field(default="Drop Concentration", description="Action name for voluntarily ending concentration.")
    description: str = Field(
        default="End concentration on current spell",
        description="Action description shown for voluntary concentration removal.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="DropConcentration targets the concentrating caster.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ABILITY,
        description="DropConcentration is a utility ability action.",
    )
    costs: List[Cost] = Field(
        default_factory=empty_list,
        description="No-cost payload because dropping concentration is free.",
    )
    target_spell: Optional[str] = Field(default=None, description="Specific spell to drop (multi-slot). None = drop all.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the action declaration event for voluntary concentration drop."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Drop Concentration",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None or "Concentrating" not in entity.active_conditions:
            return "Not concentrating on any spell"
        return None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Remove the requested concentration slot or the whole condition."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        if self.target_spell:
            conc = entity.active_conditions.get("Concentrating")
            if conc and isinstance(conc, Concentrating):
                slot_uuid = conc.get_slot_by_spell_name(self.target_spell)
                if slot_uuid is not None:
                    if not conc.drop_slot(
                        slot_uuid,
                        parent_event=execution_event,
                    ):
                        return execution_event.cancel(
                            status_message="Concentration resisted removal",
                        )
        else:
            if not entity.remove_condition(
                "Concentrating",
                parent_event=execution_event,
            ):
                return execution_event.cancel(
                    status_message="Concentration resisted removal",
                )

        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Dropped concentration{' on ' + self.target_spell if self.target_spell else ''}"
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        """Return the execution proposal unchanged; this action is free."""
        return execution_event


@_core_action_identity(
    content_id="action.shake_awake",
    display_name="Shake Awake",
    description="Use an action to wake an adjacent magically sleeping creature.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Spell Descriptions: Sleep",
    sort_order=80,
)
class ShakeAwake(BaseAction):
    """Wake a magically sleeping creature by spending an action."""
    name: str = Field(default="Shake Awake", description="Action name for waking a sleeping creature.")
    description: str = Field(
        default="Wake an adjacent creature affected by magical sleep",
        description="Rules-facing action summary.",
    )
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Creature target to wake.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Utility action category.")
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(name="Shake Awake Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
        ],
        description="Action cost paid to wake the sleeper.",
    )
    valid_target_filter: str = Field(default="all", description="Allow any visible creature to be considered.")

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        return PhysicalAccess.HAND

    @staticmethod
    def _wakeable_condition_uuids(target: Entity) -> tuple[UUID, ...]:
        """Return conditions that explicitly declare external waking support."""
        return tuple(
            sorted(
                (
                    condition.uuid
                    for condition in target.active_conditions_by_uuid.values()
                    if ConditionRemovalTrigger.SHAKE_AWAKE
                    in condition.removal_triggers
                ),
                key=lambda condition_uuid: condition_uuid.hex,
            )
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """An adjacent other creature with a wakeable condition."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if not source or not target:
            return "Source or target not found"
        if source.uuid == target.uuid:
            return "Cannot shake yourself awake"
        if source.senses.get_feet_distance(target.position) > 5:
            return "Target is not adjacent"
        if not self._wakeable_condition_uuids(target):
            return "Target has no condition that can be shaken off"
        return None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply external assistance to every condition that declares support."""
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not target:
            return execution_event.cancel(status_message="Target not found")
        wakeable_condition_uuids = self._wakeable_condition_uuids(target)
        if not wakeable_condition_uuids:
            return execution_event.cancel(
                status_message="Target has no condition that can be shaken off"
            )
        for condition_uuid in wakeable_condition_uuids:
            if condition_uuid in target.active_conditions_by_uuid:
                target.remove_condition_by_uuid(
                    condition_uuid,
                    parent_event=execution_event,
                )
        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{target.name} wakes up"
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply the action cost for waking the sleeper."""
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


@_core_action_identity(content_id="action.ally_help",display_name="Help",
    description="Help an allied creature remove an effect that permits assistance.",
    source_anchor="BG3 adapted ally assistance",sort_order=85)
class AllyHelp(ShakeAwake):
    name: str = "Help"
    description: str = "Remove eligible spell effects from an ally within 7 feet."
    valid_target_filter: str = "allies"

    def get_range(self) -> Range:
        return Range(type=RangeType.REACH,normal=7)

    @staticmethod
    def _wakeable_condition_uuids(target: Entity) -> tuple[UUID,...]:
        return tuple(condition.uuid for condition in target.active_conditions_by_uuid.values()
            if ConditionRemovalTrigger.ALLY_HELP in condition.removal_triggers)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        caster=Entity.get(self.source_entity_uuid)
        target=Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if caster is None or target is None or caster.uuid==target.uuid or not caster.is_ally(target):
            return "Help requires another allied creature"
        if caster.senses.get_feet_distance(target.position)>7 or not self._wakeable_condition_uuids(target):
            return "No eligible effect within Help reach"
        return None


@_core_action_identity(
    content_id="action.help_attack",
    display_name="Help Attack",
    description="Distract an adjacent enemy to aid one selected ally's next attack.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Actions in Combat — Help",
    sort_order=86,
)
class HelpAttack(BaseAction):
    """Select the adjacent enemy, then the allied attacker to assist."""

    creates = (AttackAssistance,)
    name: str = "Help Attack"
    description: str = "Help an ally's next attack against an enemy within 5 feet."
    target_type: TargetType = TargetType.MULTI_ENTITY
    action_category: ActionCategory = ActionCategory.ABILITY
    valid_target_filter: str = "all"
    allow_same_target: bool = False
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Help Attack Cost", cost_type="actions", cost=1,
            evaluator=entity_action_economy_cost_evaluator)])

    def get_multi_target_count(self) -> int:
        return 2

    def get_all_targets(self) -> List[UUID]:
        # The enemy owns the one effect; the second selection identifies who
        # may use it and must not create an empty ally application.
        return [self.target_entity_uuid] if self.target_entity_uuid is not None else []

    def _declared_target_entity_uuids(self) -> List[UUID]:
        return list(self.current_selection().target_uuids)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        targets: tuple[UUID, ...] = selection.target_uuids
        if len(targets) not in (1, 2):
            return "Select an adjacent enemy and an allied attacker"
        helper = Entity.get(self.source_entity_uuid)
        enemy = Entity.get(targets[0])
        if helper is None or enemy is None or not helper.is_enemy(enemy):
            return "Help Attack requires an enemy"
        if helper.senses.get_feet_distance(enemy.position) > 5:
            return "Help Attack enemy is not adjacent"
        if len(targets) == 1:
            return None if scan.subjective and self.template else "Select an allied attacker"
        ally = Entity.get(targets[-1])
        if ally is None or ally.uuid == helper.uuid or not helper.is_ally(ally):
            return "Help Attack requires another allied attacker"
        return None

    def _apply(self, event: ActionEvent) -> ActionEvent:
        helper = Entity.get(self.source_entity_uuid)
        enemy = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if helper is None or enemy is None or len(self.extra_target_entity_uuids) != 1:
            return event.cancel(status_message="Help Attack selection is no longer available")
        ally = Entity.get(self.extra_target_entity_uuids[0])
        if (not helper.is_enemy(enemy) or helper.senses.get_feet_distance(enemy.position) > 5
                or ally is None or ally.uuid == helper.uuid or not helper.is_ally(ally)):
            return event.cancel(status_message="Help Attack pair is no longer eligible")
        result = enemy.add_condition(AttackAssistance(source_entity_uuid=helper.uuid,
            target_entity_uuid=enemy.uuid, assisted_ally_uuid=self.extra_target_entity_uuids[0]), parent_event=event)
        if result is None or result.canceled:
            return event.cancel(status_message="Attack assistance was refused")
        return event.phase_to(EventPhase.EFFECT, status_message=f"Distracted {enemy.name} for an ally")

    def _apply_costs(self, event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)


@_core_action_identity(
    content_id="action.search",
    display_name="Search",
    description="Make a Wisdom (Perception) check to find hidden things within 10 feet.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Actions in Combat — Search; BG3 adapted trap search",
    sort_order=92,
)
class Search(BaseAction):
    """Search: one rolled Wisdom (Perception) check against every hidden thing within 10 feet.

    It looks, in the cells the searcher sees, for every hidden thing its party doesn't know and it has
    not searched for already: traps and hazards on the floor, on a tile or anchored to an object, and
    objects hidden by presence or by what they do (a lever in an alcove, a secret door). Hidden contents
    are Search Inside's. A total that meets a DC makes the searcher's party know that thing; a miss is
    the searcher's for good, one try per hidden thing. The check publishes no DC, so a failed search
    tells nothing.
    """
    name: str = Field(default="Search", description="Human-readable search action name.")
    description: str = Field(default="Search within 10 feet for anything hidden (Perception check)",
                             description="Player-facing search action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Search targets self")
    search_feet: ClassVar[int] = 10
    searched_aspects: ClassVar[frozenset[ConcealedAspect]] = frozenset({ConcealedAspect.HAZARD, *NOTICED_ON_OBJECTS})
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Search Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid when searching.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        source_entity = Entity.get(self.source_entity_uuid)
        return ActionEvent(
            name=self.name or "Search", description=self.description,
            parent_event=parent_event.uuid if parent_event else None, phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register, source_entity_name=source_entity.name if source_entity else None,
        )

    def _hidden_nearby(self, entity: Entity) -> List[ConcealmentHolder]:
        """Hidden things this searcher may still find, in seen cells within reach of the search."""
        grid = get_map()
        reach = self.search_feet // 5
        x, y = entity.position
        near: dict[UUID, ConcealmentHolder] = {}
        for position in ((x + dx, y + dy) for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1)):
            if not cell_visible(entity.senses.cells, position) or entity.senses.get_feet_distance(position) > self.search_feet:
                continue
            tile = grid.get_tile(*position)
            objects = grid.get_objects_at(position) | grid.get_boundary_objects_facing(position)
            blocks = [block for block in [tile, *(BaseBlock.get(identity) for identity in sorted(objects, key=str))]
                      if block is not None]
            holders: List[ConcealmentHolder] = [*grid.get_spatial_conditions_at(position),
                                                *(holder for block in blocks for holder in block.concealment_holders())]
            for holder in holders:
                record = holder.concealment
                if (record is not None and record.aspect in self.searched_aspects
                        and not knows(record, entity.faction, entity.uuid) and entity.uuid not in record.failed_by):
                    near[holder.uuid] = holder
        return [near[identity] for identity in sorted(near, key=str)]

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        roll = entity.roll_d20(entity.skill_bonus(target_entity_uuid=None, skill_name="perception"),
                               RollType.CHECK, skill_name="perception", parent_event=effect.uuid)
        writes: List[Tuple[ConcealmentHolder, Concealment]] = []
        found: List[UUID] = []
        for holder in self._hidden_nearby(entity):
            record = holder.concealment
            assert record is not None
            if roll.total >= record.dc:
                writes.append((holder, with_knowers(record, (knower_key(record, entity.faction, entity.uuid),))))
                found.append(holder.uuid)
            else:
                writes.append((holder, with_failure(record, entity.uuid)))
        if writes:
            get_map().record_concealment(writes)
        if found:  # the searcher's own view now shows each find, which its sensory update names
            entity.update_entity_senses(parent_event=effect, found=frozenset(found))
        return effect.with_updates(status_message=(
            f"{entity.name} finds {len(found)} hidden thing{'s' if len(found) != 1 else ''}" if found
            else f"{entity.name} finds nothing"))


@_core_action_identity(
    content_id="action.hide",
    display_name="Hide",
    description="Attempt a Dexterity (Stealth) check to become hidden.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Actions in Combat — Hide",
    sort_order=90,
)
class Hide(BaseAction):
    """Take the Hide action - roll Stealth to become Hidden.

    Applies the Hidden condition with stealth_result = d20 + Stealth bonus.
    Hidden entities are not perceivable by observers with passive perception
    below the stealth result. Hidden also grants Unseen Attacker advantage.

    Hidden is removed automatically when the entity attacks, takes damage,
    or becomes incapacitated.
    """
    creates = (Hidden,)
    name: str = Field(default="Hide", description="Human-readable hide action name.")
    description: str = Field(default="Attempt to hide (Stealth check)", description="Player-facing hide action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Hide targets self")
    restricted_action_kinds: ClassVar[frozenset[RestrictedActionKind]] = (
        frozenset({RestrictedActionKind.HIDE})
    )
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Hide Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid when taking the Hide action.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Hide",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return "Entity not found"

        grid = get_map()
        tile = grid.get_tile(*entity.position)
        if tile:
            light = tile.resolved_light_level
            if light == LightLevel.VERY_BRIGHT:
                return "Cannot hide in very bright light"
            if light.value <= LightLevel.DIM_LIGHT.value:
                return None

        subscribers = spatial_senses_system.observers_granted((entity.position,))
        for sub_uuid in subscribers:
            if sub_uuid == entity.uuid:
                continue
            if scan.subjective and sub_uuid not in scan.creatures:
                continue  # An enemy the hider does not perceive cannot be known to see it.
            sub = Entity.get(sub_uuid)
            if sub and entity.is_enemy(sub):
                if (
                    (contact := sub.senses.entities.get(entity.uuid)) is not None
                    and contact.visual
                    and not entity.is_obscured_by_larger_creature_from(sub, subjective=scan.subjective)
                ):
                    return "Cannot hide - visible to enemies"
        return None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")

        skill_bonus = entity.skill_bonus(target_entity_uuid=None, skill_name="stealth")
        stealth_roll = entity.roll_d20(skill_bonus, RollType.CHECK, skill_name="stealth", parent_event=execution_event.uuid)
        stealth_result = stealth_roll.total

        check_event = SkillCheckEvent(
            name="Stealth Check",
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            skill_name="stealth",
            bonus=skill_bonus,
            dice_roll=stealth_roll,
            parent_event=execution_event.uuid,
            source_entity_name=entity.name,
            phase=EventPhase.EFFECT,
        )
        check_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Stealth check: {stealth_result}"
        )

        hidden = Hidden(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            stealth_result=stealth_result
        )
        entity.add_condition(hidden, parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Applied Hidden (Stealth DC {stealth_result})"
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)

class StandUp(BaseAction):
    """
    Stand up from prone - costs half your movement speed.

    Removes the Prone condition. Can only be used while Prone.
    """
    name: str = Field(default="Stand Up", description="Human-readable stand-up action name.")
    description: str = Field(default="Stand up from prone", description="Player-facing stand-up action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Stand Up targets self")

    reaction_stand: bool = False

    def model_post_init(self, __context: Any) -> None:
        """Set movement or explicitly granted reaction standing cost."""
        super().model_post_init(__context)
        if self.reaction_stand:
            self.costs = [Cost(name="Stand reaction", cost_type="reactions", cost=1,
                evaluator=entity_action_economy_cost_evaluator)]
            return
        entity = Entity.get(self.source_entity_uuid)
        if entity:
            base_movement = entity.action_economy.get_base_value("movement")
            half_movement = base_movement // 2
            self.costs = [Cost(
                name="Stand Up Cost",
                cost_type="movement",
                cost=half_movement,
                evaluator=entity_action_economy_cost_evaluator
            )]
        else:
            default_half_movement = 15
            self.costs = [Cost(
                name="Stand Up Cost",
                cost_type="movement",
                cost=default_half_movement,
                evaluator=entity_action_economy_cost_evaluator
            )]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the stand-up declaration event."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Stand Up",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None or "Prone" not in entity.active_conditions:
            return "Not prone - cannot stand up"
        return None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        entity.remove_condition("Prone", parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message="Stood up from prone"
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


class DropProne(BaseAction):
    """
    Drop prone - free action (no cost).

    Applies the Prone condition. Can only be used while not Prone.
    """
    creates = (Prone,)
    name: str = Field(default="Drop Prone", description="Human-readable drop-prone action name.")
    description: str = Field(default="Drop to the ground", description="Player-facing drop-prone action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Drop Prone targets self")
    costs: List[Cost] = Field(default_factory=empty_list, description="Drop Prone has no action economy cost.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the drop-prone declaration event."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Drop Prone",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None or "Prone" in entity.active_conditions:
            return "Already prone"
        return None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        prone = Prone(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        entity.add_condition(prone, parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message="Dropped prone"
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        """Return the execution proposal unchanged; this action is free."""
        return execution_event


class JumpEvent(ActionEvent):
    """Event payload for a jump movement."""

    name: str = Field(default="Jump", description="Human-readable jump event label.")
    event_type: EventType = Field(default=EventType.MOVEMENT, description="Movement event category.")
    costs: List[BaseCost] = Field(default_factory=list, description="Serialized jump costs.")
    movement_mode: Optional[MovementMode] = None
    start_layer: Optional[OccupancyLayer] = None
    end_layer: Optional[OccupancyLayer] = None
    start_position: Tuple[int, int] = Field(description="Position occupied before the jump starts.")
    end_position: Tuple[int, int] = Field(description="Intended or actual landing position.")
    requested_end_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Landing position requested before any partial jump.",
    )
    objective_end_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Position occupied after the last committed jump step.",
    )
    start_elevation_feet: StrictInt = Field(default=0)
    requested_end_elevation_feet: StrictInt = Field(default=0)
    end_elevation_feet: StrictInt = Field(default=0)
    jump_distance: int = Field(default=0, description="Jump distance in feet.")
    path: Optional[List[Tuple[int, int]]] = Field(default=None, description="Straight-line airborne cell path.")
    trajectory: MovementTrajectory = Field(
        default=MovementTrajectory.DIRECT_ARC,
        description="Typed trajectory used for each committed jump step.",
    )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return jump path positions relevant to spatial handlers."""
        positions = {self.start_position, self.end_position}
        if self.path:
            positions.update(self.path)
        return positions

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this jump event."""
        source_name = self.source_entity_name or "Unknown"

        end_pos = f"({self.end_position[0]},{self.end_position[1]})"
        start_pos = f"({self.start_position[0]},{self.start_position[1]})"

        compact_text = f"{md_color(source_name, 'cyan')} {md_color('jumps', 'yellow')} {md_color(f'{self.jump_distance}ft', 'green')} to {md_color(end_pos, 'yellow')}"
        verbose_text = f"{md_color(source_name, 'cyan')} {md_color('jumps', 'yellow')} {start_pos} → {md_color(end_pos, 'green')} ({self.jump_distance}ft)"

        detailed_text = verbose_text
        if self.path and len(self.path) > 2:
            path_str = " -> ".join(f"({p[0]},{p[1]})" for p in self.path)
            detailed_text += f"\n  Air path: {path_str}"

        data = JumpMovementLogData(
                entity_name=source_name,
                entity_uuid=str(self.source_entity_uuid),
                start_position=self.start_position,
                end_position=self.end_position,
                path=self.path or [self.start_position, self.end_position],
                distance_feet=self.jump_distance,
                movement_cost=self.jump_distance,
                requested_end_position=self.requested_end_position or self.end_position,
                objective_end_position=self.objective_end_position or self.end_position,
                start_elevation_feet=self.start_elevation_feet,
                requested_end_elevation_feet=self.requested_end_elevation_feet,
                end_elevation_feet=self.end_elevation_feet,
            )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=data,
            success=True
        )


@_core_action_identity(
    content_id="action.jump",
    display_name="Jump",
    description="Jump to a visible landing position.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Adventuring: Special Types of Movement — Jumping",
    sort_order=100,
)
class Jump(BaseAction):
    """Jump to a visible position using bonus action and movement.

    Jump range = 15ft base + STR bonus (5ft per point of STR modifier above 10).
    This is a simplified implementation combining long jump and high jump concepts.

    Key differences from Move:
    - Uses POSITION_LOS targeting (visible positions, not path-reachable)
    - Can bypass obstacles, difficult terrain, and gaps
    - Still costs movement equal to distance jumped
    - Landing position must be walkable and unoccupied

    When used as a template (template=True), end_position should be set via set_target_position()
    before pre_validate() or instantiate().
    """
    creates = (Prone, Move)

    name: str = Field(default="Jump", description="Human-readable jump action name.")
    description: str = Field(default="Jump to a visible position", description="Jump action description.")
    target_type: TargetType = Field(default=TargetType.POSITION_LOS, description="Jump targets visible positions.")
    action_category: ActionCategory = Field(default=ActionCategory.MOVEMENT, description="Movement action category.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=lambda: PositionDiscoveryContract(
            requires_subjective_walkable=True,
            requires_subjective_unoccupied=True,
            bounded_by_remaining_movement=True,
            distance_is_movement_cost=True,
        ),
        description="Subjective landing prerequisites for jump discovery.",
    )
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="Requested landing position.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Jump Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Jump.")

    def get_target_dynamic_costs(self) -> List[Cost]:
        """Declare the selected landing distance as a typed movement cost."""
        if self.end_position is None:
            return []
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return []
        distance = entity.senses.get_feet_distance(self.end_position)
        return [
            Cost(
                name="Jump Movement Cost",
                cost_type="movement",
                cost=int(distance),
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]

    def get_range(self) -> Optional[Range]:
        """Calculate jump range: (15 + STR_bonus + additive) * multiplier.

        STR component computed dynamically (like AC reads DEX).
        jump_distance_additive (base=0): extra flat bonus from spells/conditions.
        jump_distance_multiplier (base=1): Jump spell adds +2 → 3x.

        Examples (no modifiers):
        - STR 10 (mod +0): 15ft
        - STR 14 (mod +2): 25ft
        - STR 20 (mod +5): 40ft
        With Jump spell (multiplier=3): all values tripled.
        """
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return Range(type=RangeType.REACH, normal=15)
        return Range(type=RangeType.REACH, normal=entity.jump_distance_feet())

    def get_valid_positions(self) -> List[Tuple[int, int]]:
        """Get valid landing positions for jump.

        Valid if:
        1. Visible (LOS)
        2. Within jump range
        3. Within available movement
        4. Walkable tile
        5. Unoccupied by other entities
        """
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return []

        action_range = self.get_range()
        max_range = action_range.normal if action_range else 15
        movement_available = entity.action_economy.movement_remaining()
        grid = get_map()
        valid: List[Tuple[int, int]] = []

        for pos in visible_positions(entity.senses.cells):
            if pos == entity.senses.position:
                continue

            distance = entity.senses.get_feet_distance(pos)
            if distance > max_range:
                continue

            if distance > movement_available:
                continue

            if not grid.is_walkable_for(pos[0], pos[1], entity.uuid):
                continue

            if not grid.raycast_clear(entity.position, pos, channel=WorldEdgeChannel.PROPAGATION):
                continue

            valid.append(pos)

        return valid

    def get_disclosed_movement_path(
        self,
        start_position: Tuple[int, int],
        end_position: Tuple[int, int],
    ) -> Optional[List[Tuple[int, int]]]:
        """Return the straight-line cells traversed by jump execution."""
        start = start_position
        end = end_position
        x0, y0 = start
        x1, y1 = end
        path: List[Tuple[int, int]] = []

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            path.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

        return path

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[JumpEvent]:
        """Create the declaration event for the jump action."""
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return None

        if self.end_position is None:
            return None

        end_position: Tuple[int, int] = self.end_position
        distance = source_entity.senses.get_feet_distance(end_position)

        line_path = self.get_disclosed_movement_path(
            source_entity.position,
            end_position,
        )
        if line_path is None:
            return None

        grid = get_map()
        return JumpEvent(
            name=self.name,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            start_position=source_entity.position,
            movement_mode=MovementMode.WALKING,
            start_layer=source_entity.occupancy_layer,
            end_layer=source_entity.occupancy_layer,
            end_position=end_position,
            requested_end_position=end_position,
            objective_end_position=source_entity.position,
            start_elevation_feet=grid.get_support_elevation_feet(
                source_entity.position
            ),
            requested_end_elevation_feet=grid.get_support_elevation_feet(
                end_position
            ),
            end_elevation_feet=grid.get_support_elevation_feet(
                source_entity.position
            ),
            jump_distance=int(distance),
            path=line_path,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_entity.name
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A visible, walkable landing within jump range with a clear line from the jumper."""
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return "Entity not found"

        if source_entity.occupancy_layer is not OccupancyLayer.GROUND:
            return "Jump requires ground contact"

        if not selection.positions:
            return "Choose a landing position"
        end_pos = selection.positions[0]
        grid = get_map()

        if end_pos not in scan.visible:
            return f"Position {end_pos} not visible"

        max_range = scan.jump_feet
        distance = source_entity.senses.get_feet_distance(end_pos)
        if distance > max_range:
            return f"Position {end_pos} out of jump range ({distance}ft > {max_range}ft)"

        if not grid.is_walkable_for(end_pos[0], end_pos[1], source_entity.uuid, subjective=scan.subjective):
            return f"Position {end_pos} not walkable or occupied"

        if not grid.raycast_clear(source_entity.position, end_pos, channel=WorldEdgeChannel.PROPAGATION):
            return f"Path to {end_pos} is blocked"

        return None

    def _apply(self, execution_event: JumpEvent) -> JumpEvent:
        """Apply the jump - step through path cells firing StepMovementEvents.

        Like Move, iterates cell-by-cell so opportunity attacks and reactions
        can fire at each step. Unlike Move, intermediate cells are NOT checked
        for walkability (the entity is airborne). Movement is consumed per-step.
        """
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return execution_event.cancel(status_message="Entity not found")

        grid = get_map()
        path = execution_event.path or []
        total_path_length = len(path)
        actual_end_position = source_entity.position
        traversed_path = [source_entity.position]
        interrupted_by_condition = False

        try:
            effect_event = execution_event.phase_to(
                new_phase=EventPhase.EFFECT,
                status_message=f"Jumping to {execution_event.end_position}"
            )
            if effect_event.canceled:
                return effect_event

            for i in range(1, total_path_length):
                from_pos = path[i - 1]
                to_pos = path[i]
                step_source_cursor_start = EventQueue.event_cursor()

                step_cost_feet = 5
                remaining_movement = source_entity.action_economy.movement_remaining()
                if remaining_movement < step_cost_feet:
                    break

                step_event = StepMovementEvent(
                    source_entity_uuid=self.source_entity_uuid,
                    source_entity_name=source_entity.name,
                    from_position=from_pos,
                    to_position=to_pos,
                    path_index=i,
                    total_path_length=total_path_length,
                    movement_cost=step_cost_feet,
                    trajectory=execution_event.trajectory,
                    movement_mode=MovementMode.WALKING,
                    from_layer=source_entity.occupancy_layer,
                    to_layer=(OccupancyLayer.GROUND if i == total_path_length - 1
                              else OccupancyLayer.AIR),
                    disclosed_path=(from_pos, to_pos),
                    from_elevation_feet=grid.get_support_elevation_feet(
                        from_pos
                    ),
                    to_elevation_feet=grid.get_support_elevation_feet(to_pos),
                    provocation_policy=MovementProvocationPolicy.ORDINARY_EXIT,
                    phase=EventPhase.EFFECT,
                    parent_event=effect_event.uuid,
                    use_register=False
                )
                processed_step = step_event.post(use_register=True)

                if processed_step.canceled:
                    break

                if not source_entity.can_take_actions():
                    interrupted_by_condition = True
                    processed_step.phase_to(
                        EventPhase.COMPLETION,
                        committed=False,
                        status_message=f"Jump step interrupted before entering {to_pos}",
                    )
                    break

                if source_entity.occupancy_layer is OccupancyLayer.GROUND:
                    Entity.update_entity_position(
                        source_entity, source_entity.position,
                        parent_event=processed_step.uuid, occupancy_layer=OccupancyLayer.AIR,
                    )
                    if (not source_entity.can_take_actions()
                            or source_entity.action_economy.movement_remaining() < step_cost_feet):
                        interrupted_by_condition = True
                        processed_step.phase_to(EventPhase.COMPLETION, committed=False)
                        break

                resolved_speed_feet = source_entity.action_economy.current_speed()
                source_entity.action_economy.consume("movement", step_cost_feet)
                Entity.update_entity_position(
                    source_entity, to_pos, parent_event=processed_step.uuid,
                    occupancy_layer=OccupancyLayer.AIR,
                )
                if i == total_path_length - 1:
                    Entity.update_entity_position(
                        source_entity, to_pos, parent_event=processed_step.uuid,
                        occupancy_layer=OccupancyLayer.GROUND,
                    )
                    resolve_fall_damage(source_entity,
                        drop_feet=execution_event.start_elevation_feet - grid.get_support_elevation_feet(to_pos),
                        source_entity_uuid=source_entity.uuid, parent_event=processed_step)
                actual_end_position = source_entity.position
                traversed_path.append(to_pos)

                processed_step.phase_to(EventPhase.COMPLETION, committed=True,
                                        resolved_speed_feet=resolved_speed_feet)

                if resolve_paid_entry_retreats(source_entity, since_cursor=step_source_cursor_start, parent_event=effect_event):
                    interrupted_by_condition = True
                    actual_end_position = source_entity.position
                    break

                if source_entity.position != to_pos:
                    interrupted_by_condition = True
                    break

                if not source_entity.can_take_actions():
                    break

            # A partial jump settles at its actual committed endpoint. Earlier
            # airborne cell entries are never reinterpreted as ground contact.
            if source_entity.occupancy_layer is OccupancyLayer.AIR:
                settlement_cursor = EventQueue.event_cursor()
                landing_position = source_entity.position
                Entity.update_entity_position(
                    source_entity, landing_position, parent_event=effect_event.uuid,
                    occupancy_layer=OccupancyLayer.GROUND,
                )
                resolve_fall_damage(source_entity,
                    drop_feet=execution_event.start_elevation_feet - grid.get_support_elevation_feet(landing_position),
                    source_entity_uuid=source_entity.uuid, parent_event=effect_event)
                if resolve_paid_entry_retreats(source_entity, since_cursor=settlement_cursor, parent_event=effect_event):
                    interrupted_by_condition = True
            actual_end_position = source_entity.position
            effect_event = effect_event.with_updates(end_layer=source_entity.occupancy_layer)

            if source_entity.position == execution_event.start_position:
                if interrupted_by_condition:
                    return effect_event.with_updates(
                        status_message=f"Partial jump, stopped at {source_entity.position}",
                        end_position=actual_end_position,
                        objective_end_position=actual_end_position,
                        end_elevation_feet=grid.get_support_elevation_feet(
                            actual_end_position
                        ),
                        path=traversed_path,
                        jump_distance=(len(traversed_path) - 1) * 5,
                    )
                return effect_event.cancel(status_message=f"Failed to jump")
            elif source_entity.position != execution_event.end_position:
                return effect_event.with_updates(
                    status_message=f"Partial jump, stopped at {source_entity.position}",
                    end_position=actual_end_position,
                    objective_end_position=actual_end_position,
                    end_elevation_feet=grid.get_support_elevation_feet(
                        actual_end_position
                    ),
                    path=traversed_path,
                    jump_distance=(len(traversed_path) - 1) * 5,
                )

            return effect_event.with_updates(
                status_message=f"Jumped to {execution_event.end_position}",
                objective_end_position=actual_end_position,
                end_elevation_feet=grid.get_support_elevation_feet(
                    actual_end_position
                ),
                path=traversed_path,
                jump_distance=(len(traversed_path) - 1) * 5,
            )
        finally:
            source_entity.materialize_navigation(max_distance=20)

    def _apply_costs(self, execution_event: JumpEvent) -> JumpEvent:
        """Apply the costs of the jump (bonus action). Movement consumed per-step in _apply()."""
        return _consume_entity_action_economy_costs(
            execution_event,
            self.source_entity_uuid,
            excluded_cost_types=frozenset({"movement"}),
        )


POUNDS_PER_KILOGRAM = 2.2046226218487757
BG3_SHOVE_WEIGHT_MULTIPLIER_KG = 12.0
BG3_SHOVE_CURVE_CONSTANT = 65.0
BG3_SHOVE_MIN_DISTANCE_METERS = 1.0
BG3_SHOVE_MAX_DISTANCE_METERS = 6.0
BG3_GRID_CELL_METERS = 1.5
ENGINE_GRID_CELL_FEET = 5


class ShoveEvent(ActionEvent):
    """Event payload for a BG3-style shove action.

    Shove is a BG3-style bonus action that pushes adjacent enemies.
    Key mechanics:
    - Cost: Bonus Action
    - Range: 5ft (adjacent only)
    - Contest: Shover's Athletics CHECK vs target's passive skill DC
    - Allies: Auto-succeed (no check required)
    - Weight limit: Strength score x 12 kilograms
    """

    name: str = Field(default="Shove", description="Human-readable shove event label.")
    event_type: EventType = Field(default=EventType.BASE_ACTION, description="Base action event category.")
    costs: List[BaseCost] = Field(default_factory=list, description="Serialized shove costs.")
    target_weight: int = Field(default=0, description="Target's weight in pounds")
    max_shove_weight: int = Field(default=0, description="Maximum weight shover can push in pounds.")
    shover_athletics: Optional[ValueReading] = Field(default=None, description="Shover's evaluated Athletics bonus")
    target_passive: int = Field(default=10, description="Target's passive Athletics or Acrobatics")
    target_resistance_skill: str = Field(default="athletics", description="Target skill used for passive resistance.")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="Shover's Athletics check roll")
    contest_success: Optional[bool] = Field(default=None, description="Whether the shove contest succeeded.")
    push_distance: int = Field(default=0, description="Distance actually pushed in feet.")
    push_direction: Tuple[int, int] = Field(default=(0, 0), description="Push direction as grid delta.")
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="Target's final position after push.")
    knocked_prone: bool = Field(default=False, description="Whether target was knocked prone instead of pushed.")
    blocked_by: Optional[str] = Field(default=None, description="Obstacle or entity that blocked the push.")
    is_ally: bool = Field(default=False, description="Whether target is an ally and auto-succeeds.")

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return final shove position relevant to spatial handlers."""
        positions = super().get_affected_positions()
        if self.end_position:
            positions.add(self.end_position)
        return positions

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for a shove event."""
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"

        if self.contest_success is False:
            compact_text = f"{md_color(source_name, 'cyan')} fails to shove {md_color(target_name, 'yellow')}"
        elif self.knocked_prone:
            compact_text = f"{md_color(source_name, 'cyan')} knocks {md_color(target_name, 'yellow')} {md_color('prone', 'red')}!"
        elif self.push_distance > 0:
            pos_str = f"→ {self.end_position}" if self.end_position else ""
            compact_text = f"{md_color(source_name, 'cyan')} shoves {md_color(target_name, 'yellow')} {md_color(f'{self.push_distance}ft', 'green')} {pos_str}"
        else:
            blocked_suffix = f" (blocked by {self.blocked_by})" if self.blocked_by else " (blocked)"
            compact_text = f"{md_color(source_name, 'cyan')} shoves {md_color(target_name, 'yellow')}{blocked_suffix}"

        verbose_text = compact_text
        if not self.is_ally and self.dice_roll is not None:
            roll_total = self.dice_roll.total
            success_str = md_color("success", "green") if self.contest_success else md_color("fail", "red")
            verbose_text += f"\n  Athletics: d20({md_color(str(roll_total), 'cyan')}) vs DC {self.target_passive} → {success_str}"
        elif self.is_ally:
            verbose_text += f" ({md_color('ally', 'green')})"

        detailed_text = verbose_text
        if self.contest_success:
            if self.knocked_prone:
                detailed_text += f"\n  Effect: Target knocked {md_color('prone', 'red')}"
            else:
                detailed_text += f"\n  Direction: {self.push_direction}"
                detailed_text += f"\n  Weight: {self.target_weight}lbs (max: {self.max_shove_weight}lbs)"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=ShoveLogData(
                action_type='shove',
                target_weight=self.target_weight,
                max_shove_weight=self.max_shove_weight,
                contest_success=self.contest_success,
                push_distance=self.push_distance,
                push_direction=self.push_direction,
                end_position=self.end_position,
                knocked_prone=self.knocked_prone,
                blocked_by=self.blocked_by,
                is_ally=self.is_ally,
            ),
            success=self.contest_success or False
        )


@_core_action_identity(
    content_id="action.shove",
    display_name="Shove",
    description="Contest an adjacent creature to push it or knock it prone.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Making an Attack — Shoving a Creature",
    sort_order=110,
)
class Shove(BaseAction):
    """BG3-style shove action that pushes or knocks prone.

    Costs a bonus action. Push distance depends on Strength and target weight.

    Mechanics (BG3-style):
    - Range: 5ft (adjacent only)
    - Contest: Shover's Athletics CHECK vs target's passive DC
    - Target DC: 10 + max(Athletics, Acrobatics) bonus + advantage modifier
    - Allies: Auto-succeed (no check required)
    - Weight limit: Strength score x 12 kilograms
    - Distance: Weight-sensitive BG3 force curve, clamped to 1-6 metres
      and quantized to the engine's 5-foot grid

    Forced movement does NOT trigger opportunity attacks.
    """
    creates = (Prone, Move)

    name: str = Field(default="Shove", description="Human-readable shove action name.")
    description: str = Field(default="Push an adjacent enemy", description="Shove action description.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Shove targets one entity.")
    knock_prone: bool = Field(default=False, description="Whether shove knocks prone instead of pushing.")
    include_allies: bool = Field(default=True, description="Whether allies are valid shove targets.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Shove Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Shove.")

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        return PhysicalAccess.BODY

    @staticmethod
    def get_max_shove_weight(entity: Entity) -> int:
        """Calculate the maximum BG3 shove weight in engine pounds.

        Args:
            entity: Entity attempting the shove.

        Returns:
            Maximum whole-pound target weight the entity can shove.
        """
        strength_score = entity.ability_scores.strength.ability_score.score
        maximum_kg = strength_score * BG3_SHOVE_WEIGHT_MULTIPLIER_KG
        return int(maximum_kg * POUNDS_PER_KILOGRAM)

    @staticmethod
    def get_push_distance(entity: Entity, target: Entity) -> int:
        """Calculate BG3-calibrated shove distance on the engine grid.

        BG3 exposes a target-weight-dependent ``ShoveDistance``, a curve
        constant of 65, and a 1-6 metre clamp, but keeps the native arithmetic
        private. The engine uses the direct force-margin interpretation of
        those constants. Entity weights are converted from pounds to kilograms
        before the result is rounded to the nearest 5-foot grid cell.

        Args:
            entity: Entity attempting the shove.
            target: Entity being shoved.

        Returns:
            Push distance in feet.
        """
        strength_score = entity.ability_scores.strength.ability_score.score
        shove_capacity_kg = strength_score * BG3_SHOVE_WEIGHT_MULTIPLIER_KG
        target_weight_kg = target.weight / POUNDS_PER_KILOGRAM
        distance_meters = (
            shove_capacity_kg - target_weight_kg
        ) / BG3_SHOVE_CURVE_CONSTANT
        distance_meters = min(
            BG3_SHOVE_MAX_DISTANCE_METERS,
            max(BG3_SHOVE_MIN_DISTANCE_METERS, distance_meters),
        )
        distance_cells = int(distance_meters / BG3_GRID_CELL_METERS + 0.5)
        minimum_cells = 1
        maximum_cells = int(BG3_SHOVE_MAX_DISTANCE_METERS / BG3_GRID_CELL_METERS)
        distance_cells = min(maximum_cells, max(minimum_cells, distance_cells))
        return distance_cells * ENGINE_GRID_CELL_FEET

    @staticmethod
    def get_push_direction(source_pos: Tuple[int, int], target_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Calculate push direction as unit vector from source to target.

        Args:
            source_pos: Shoving entity position.
            target_pos: Target entity position.

        Returns:
            Unit direction as `(dx, dy)`.
        """
        dx = target_pos[0] - source_pos[0]
        dy = target_pos[1] - source_pos[1]

        if dx != 0:
            dx = 1 if dx > 0 else -1
        if dy != 0:
            dy = 1 if dy > 0 else -1

        return (dx, dy)

    @staticmethod
    def calculate_final_position(
        start: Tuple[int, int],
        direction: Tuple[int, int],
        distance_feet: int,
        target_uuid: 'UUID'
    ) -> Tuple[Tuple[int, int], int, bool, Optional[str]]:
        """Calculate where target lands after being pushed.

        Walks cells in push direction until:
        - Reached desired distance, OR
        - Hit unwalkable tile, OR
        - Hit cell occupied by another entity

        Target MUST land on a walkable tile.

        Args:
            start: Target's current position
            direction: Push direction as (dx, dy)
            distance_feet: How far to push in feet.
            target_uuid: UUID of entity being pushed, excluded from occupancy checks.

        Returns:
            Final position, actual distance, blocked flag, and blocker label.
        """
        grid = get_map()
        target = Entity.get(target_uuid)
        current = start
        cells_to_move = distance_feet // 5
        actual_cells = 0
        blocked = False
        blocked_by: Optional[str] = None

        for _ in range(cells_to_move):
            next_pos = (current[0] + direction[0], current[1] + direction[1])

            landing = grid.admit_forced_step(current, next_pos, target_uuid)
            if landing is None or (target is not None and not target.can_end_movement_at(next_pos)):
                blocked = True
                blocked_by = grid.identify_blocker_at(next_pos, target_uuid)
                break

            current = next_pos
            actual_cells += 1
            if landing is LandingKind.FALL:
                break

        return current, actual_cells * 5, blocked, blocked_by

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ShoveEvent]:
        """Create declaration event for shove."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source or not target:
            return None

        return ShoveEvent(
            name=self.name,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source.name,
            target_entity_name=target.name,
            target_weight=target.weight,
            max_shove_weight=self.get_max_shove_weight(source),
            is_ally=source.is_ally(target)
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """An adjacent, visible body light enough to shove."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None

        if not source or not target:
            return "Entity not found"

        if source.cannot_manipulate_bodies or target.cannot_manipulate_bodies:
            return "This body cannot shove or be shoved"
        distance = source.senses.get_feet_distance(target.position)
        if distance > 5:
            return f"Target not adjacent ({distance}ft)"

        max_shove_weight = self.get_max_shove_weight(source)
        if target.weight > max_shove_weight:
            return f"Target too heavy ({target.weight}lbs > {max_shove_weight}lbs)"

        record = scan.creatures.get(target.uuid)
        if record is None or not record.visual:
            return "Target not visible"

        return None

    def _apply(self, execution_event: ShoveEvent) -> ShoveEvent:
        """Resolve the shove contest and apply push or prone effects."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not source or not target:
            return execution_event.cancel(status_message="Entity not found")

        if source.is_ally(target):
            contest_success = True
            dice_roll = None
            target_passive = 0
            target_skill = "none"
        else:
            athletics_bonus = source.skill_bonus(target.uuid, "athletics")

            passive_athletics = target.passive_skill("athletics")
            passive_acrobatics = target.passive_skill("acrobatics")

            if passive_athletics >= passive_acrobatics:
                target_passive = passive_athletics
                target_skill = "athletics"
            else:
                target_passive = passive_acrobatics
                target_skill = "acrobatics"

            dice_roll = source.roll_d20(
                athletics_bonus,
                RollType.CHECK,
                skill_name="athletics",
                parent_event=execution_event.uuid,
            )
            contest_success = dice_roll.total >= target_passive

        execution_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            shover_athletics=athletics_bonus if not source.is_ally(target) else None,
            dice_roll=dice_roll,
            target_passive=target_passive,
            target_resistance_skill=target_skill,
            contest_success=contest_success,
            status_message=f"Contest {'succeeded' if contest_success else 'failed'}"
        )

        if execution_event.canceled:
            return execution_event

        if not contest_success:
            return execution_event.with_updates(
                status_message="Shove failed - target resisted"
            )

        if self.knock_prone:
            prone_condition = Prone(
                source_entity_uuid=source.uuid,
                target_entity_uuid=target.uuid
            )
            target.add_condition(prone_condition, parent_event=execution_event)

            return execution_event.with_updates(
                knocked_prone=True,
                status_message=f"{target.name} knocked prone"
            )

        direction = self.get_push_direction(source.position, target.position)
        distance = self.get_push_distance(source, target)
        final_pos, actual_dist, blocked, blocked_by = self.calculate_final_position(
            target.position, direction, distance, target.uuid
        )

        push_direction = direction
        push_distance = actual_dist

        if actual_dist > 0:
            forced_event = ForcedMovementEvent(
                source_entity_uuid=source.uuid,
                target_entity_uuid=target.uuid,
                source_entity_name=source.name,
                target_entity_name=target.name,
                start_position=target.position,
                end_position=final_pos,
                direction=direction,
                intended_distance=distance,
                actual_distance=actual_dist,
                blocked_by_obstacle=blocked,
                blocked_by=blocked_by,
                cause="shove",
                phase=EventPhase.DECLARATION,
                parent_event=execution_event.uuid
            )

            forced_event = forced_event.phase_to(EventPhase.EXECUTION)
            forced_event = forced_event.phase_to(EventPhase.EFFECT)

            forced_event = commit_forced_movement(target, forced_event, parent_event=execution_event,
                                                 stop_on_incapacitation=True)
            push_distance = forced_event.actual_distance
            blocked, blocked_by = forced_event.blocked_by_obstacle, forced_event.blocked_by
            final_pos = target.position

        return execution_event.with_updates(
            push_distance=push_distance,
            push_direction=push_direction,
            end_position=final_pos,
            blocked_by=blocked_by,
            status_message=f"Shoved {target.name} {push_distance}ft" + (f" (blocked by {blocked_by})" if blocked and blocked_by else " (blocked)" if blocked else "")
        )

    def _apply_costs(self, execution_event: ShoveEvent) -> ShoveEvent:
        """Apply shove costs (bonus action)."""
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)

class SpellEvent(ActionEvent):
    def harmful_direct_recipients(self) -> tuple[UUID, ...]:
        if self.target_type in (TargetType.ENTITY, TargetType.CREATURE_OR_OBJECT, TargetType.MULTI_ENTITY):
            return tuple(self.harmful_target_entity_uuids)
        return ()

    spellcasting_source_id: UUID | None = None
    maximize_damage_dice: bool = False
    can_deal_damage: bool = False
    weapon_attack_slot: WeaponSlot | None = None
    """Event payload for spell casting and spell effect logs."""

    target_kind: Literal["creature", "object"] = "creature"
    summon_application: SummonApplication | None = None
    magical_transfer: bool = False
    authored_spell_id: str | None = None
    target_position: Optional[tuple[int, int]] = None
    target_base_height_steps: Optional[int] = None
    name: str = Field(default="Spell Cast", description="A spell cast event")
    event_type: EventType = Field(default=EventType.CAST_SPELL, description="The type of event")
    spell_id: Optional[str] = Field(default=None, description="Stable spell catalog id")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Native targeting mode captured before interception.")
    harmful: bool = Field(default=False, description="Whether this cast includes an authored harmful effect.")
    harmful_target_entity_uuids: List[UUID] = Field(default_factory=list, description="Declared recipients to whom this cast's native effects are harmful.")
    effect_id: Optional[str] = Field(default=None, description="Authored subeffect within the owning spell, when distinct from the cast.")
    prismatic_roll: Annotated[int, Field(ge=1, le=8)] | None = None
    prismatic_colors: tuple[Annotated[int, Field(ge=1, le=7)], ...] = ()
    spell_level: int = Field(default=0, description="Base spell level (0 = cantrip)")
    cast_at_level: int = Field(default=0, description="Actual slot level used (0 = cantrip)")
    spell_school: str = Field(default="evocation", description="School of magic")
    verbal: bool = Field(default=True, description="Whether spell has a verbal component")
    cast_origin: Literal["actor", "source_item"] = Field(
        default="actor", description="Whether this cast originates from its actor or placed source item.",
    )
    effect_source_position: Optional[Tuple[int, int]] = Field(
        default=None, description="Immutable spell emission position, including a placed device's origin.",
    )
    suppressions: tuple[SpellSuppression, ...] = ()
    area_propagation: AreaPropagation = "line_of_effect"
    source_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Caster position captured when the spell was declared.",
    )
    area_geometry: Optional[AoEPresentationGeometry] = Field(
        default=None,
        discriminator="shape",
        description="Exact immutable area geometry captured when the spell was declared.",
    )

    attack_bonus: Optional[ValueReading] = Field(default=None, description="The evaluated spell attack bonus")
    ac: Optional[ValueReading] = Field(default=None, description="The target's evaluated AC")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="The attack roll result")
    attack_outcome: Optional[AttackOutcome] = Field(default=None, description="The attack outcome")
    is_threatened: bool = Field(
        default=False,
        description="Whether a visible hostile threatens the caster during a ranged spell attack.",
    )

    save_ability: Optional[AbilityName] = Field(default=None, description="Ability for saving throw")
    save_dc: Optional[int] = Field(default=None, description="Save DC")
    save_success: Optional[bool] = Field(default=None, description="Whether the save succeeded")
    save_roll: Optional[DiceRoll] = Field(default=None, description="The save roll result")
    save_bonus: Optional[int] = Field(default=None, description="Target's save bonus")

    damages: Optional[List[Damage]] = Field(default=None, description="The damages dealt")
    damage_rolls: Optional[List[DiceRoll]] = Field(default=None, description="The damage roll results")

    aoe_shape_type: Optional[str] = Field(default=None, description="AoE shape: sphere, cone, line, cube, cylinder")
    aoe_radius_ft: Optional[int] = Field(default=None, description="AoE size in feet")
    range_type: Optional[str] = Field(default=None, description="Delivery type: self, touch, ranged")
    range_ft: Optional[int] = Field(default=None, description="Spell range in feet")
    projectile_type: Optional[str] = Field(default=None, description="Visual projectile delivery type")
    damage_types: List[DamageType] = Field(default_factory=list, description="Damage types for VFX (populated at declaration, updated on hit)")

    retained_effect_origin: EffectOrigin | None = None

    def to_effect_origin(self) -> EffectOrigin:
        """Return dependency-neutral provenance for a persistent spell effect."""
        if self.retained_effect_origin is not None:
            return self.retained_effect_origin
        return EffectOrigin.spell(
            source_id=self.authored_spell_id or self.spell_id,
            source_event_lineage_uuid=str(self.lineage_uuid),
            source_position=self.effect_source_position or self.source_position,
            base_spell_level=self.spell_level,
            effective_spell_level=self.cast_at_level,
            spell_school=self.spell_school,
            spellcasting_source_id=self.spellcasting_source_id,
            harmful=self.harmful,
            area_application=self.target_type is TargetType.POSITION_AOE or self.area_geometry is not None,
            maximize_damage_dice=self.maximize_damage_dice,
        )

    def get_effect_origin(self) -> EffectOrigin:
        """Expose spell provenance through the neutral Event interface."""
        return self.to_effect_origin()

    def phase_to(self, new_phase: Optional[EventPhase] = None, status_message: Optional[str] = None, **updates: Any) -> Self:
        """Override to auto-update damage_types when damages are set."""
        if 'damages' in updates and updates['damages'] and 'damage_types' not in updates:
            updates['damage_types'] = list(dict.fromkeys(d.damage_type for d in updates['damages']))
        return super().phase_to(new_phase, status_message, **updates)

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for spell effects.

        Returns:
            Spell-specific combat log entry for multi-target, saving throw,
            spell attack, auto-hit, or generic cast events.
        """
        if self.total_targets > 0:
            return self._generate_multi_target_log()

        if self.save_dc is not None and self.save_success is not None:
            return self._generate_save_spell_log()

        if self.attack_outcome is not None:
            return self._generate_attack_spell_log()

        if self.damage_rolls and self.target_entity_name:
            return self._generate_autohit_spell_log()

        parent_log = super().generate_combat_log()
        if parent_log is not None:
            return parent_log
        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=self.source_entity_name or "Unknown",
            source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            compact=f"{self.source_entity_name or 'Unknown'} casts {self.name or 'spell'}",
            verbose=f"{self.source_entity_name or 'Unknown'} casts {self.name or 'spell'}",
            detailed=f"{self.source_entity_name or 'Unknown'} casts {self.name or 'spell'}",
            data=EmptyLogData(
            ),
            success=True
        )

    def _generate_save_spell_log(self) -> CombatLogEntry:
        """Generate a combat log entry for a single-target save spell."""
        target_name = self.target_entity_name or "Unknown"
        caster_name = self.source_entity_name or "Unknown"
        spell_name = self.name or "Spell"
        ability = (self.save_ability or "dexterity").upper()[:3]
        dc = self.save_dc or 10
        success = self.save_success or False
        total_dmg = self.total_damage or 0

        save_roll_display = DiceRollDisplay(dice_str="d20", results=[], bonus=0, total=0)
        if self.save_roll:
            results = self.save_roll.results
            if isinstance(results, list):
                results_list = list(results)
            else:
                results_list = [results] if results else []
            save_roll_display = DiceRollDisplay(
                dice_str="d20",
                results=results_list,
                bonus=self.save_bonus or 0,
                total=self.save_roll.total,
                d20_used=results_list[0] if results_list else None
            )

        damage_displays: List[DamageRollDisplay] = []
        damage_type = "damage"
        base_damage = 0
        if self.damage_rolls:
            for i, dr in enumerate(self.damage_rolls):
                dmg_type = self.damages[i].damage_type.value if self.damages and i < len(self.damages) else "damage"
                damage_type = dmg_type
                dr_results = dr.results
                if isinstance(dr_results, list):
                    dice_results = list(dr_results)
                else:
                    dice_results = [dr_results] if dr_results else []
                base_damage = dr.total
                damage_displays.append(DamageRollDisplay(
                    dice_str=f"{len(dice_results)}d{self.damages[i].damage_dice if self.damages and i < len(self.damages) else 6}",
                    dice_results=dice_results,
                    bonus=0,
                    total=dr.total,
                    damage_type=dmg_type
                ))

        outcome_str = md_color("SAVE", "green") if success else md_color("FAIL", "red")
        half_note = " (half)" if success and total_dmg > 0 else ""
        compact = f"{md_color(target_name, 'yellow')}: {ability} save {outcome_str}, {md_color(str(total_dmg), 'red')} {damage_type}{half_note}"

        verbose_lines = [compact]
        if save_roll_display.total > 0:
            d20_val = save_roll_display.d20_used or (save_roll_display.results[0] if save_roll_display.results else "?")
            bonus_str = f"+{save_roll_display.bonus}" if save_roll_display.bonus >= 0 else str(save_roll_display.bonus)
            verbose_lines.append(f"  Save: d20({d20_val}) {bonus_str} = {save_roll_display.total} vs DC {dc}")
        if damage_displays:
            dr = damage_displays[0]
            dice_str = ",".join(str(d) for d in dr.dice_results) if dr.dice_results else "?"
            verbose_lines.append(f"  Damage: {dr.dice_str}({dice_str}) = {dr.total} {dr.damage_type}")
        verbose = "\n".join(verbose_lines)

        detailed = verbose

        save_bonus_breakdown: List[ModifierBreakdown] = []
        save_advantage_breakdown: List[ModifierBreakdown] = []

        data = SpellSaveLogData(
                caster_name=caster_name,
                caster_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else '',
                target_name=target_name,
                target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else '',
                spell_name=spell_name,
                spell_level=self.spell_level,
                save_ability=self.save_ability or 'dexterity',
                save_dc=dc,
                save_roll=save_roll_display,
                save_bonus_breakdown=save_bonus_breakdown,
                save_advantage_breakdown=save_advantage_breakdown,
                save_success=success,
                damage_rolls=damage_displays,
                base_damage=base_damage,
                final_damage=total_dmg,
                damage_type=damage_type,
            )

        spell_effect_succeeded = not success
        return CombatLogEntry(
            entry_type=CombatLogEntryType.SPELL_SAVE,
            source_name=caster_name,
            source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            compact=compact,
            verbose=verbose,
            detailed=detailed,
            data=data,
            success=spell_effect_succeeded
        )

    def _generate_attack_spell_log(self) -> CombatLogEntry:
        """Generate combat log for attack-based spell (Fire Bolt, Guiding Bolt, etc.).

        Follows AttackEvent.generate_combat_log() pattern but uses spell name
        instead of weapon name.
        """
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"
        spell_name = self.name or "Spell"

        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        attack_roll = DiceRollDisplay(dice_str="d20", results=[], bonus=0, total=0)
        if self.dice_roll:
            results = self.dice_roll.results
            if isinstance(results, list):
                attack_roll.results = list(results)
                attack_roll.all_d20_rolls = list(results)
                adv_status = self.dice_roll.advantage_status
                if adv_status:
                    adv_value = adv_status.value.lower()
                    attack_roll.advantage_status = adv_value
                    if len(results) >= 2:
                        if adv_value == "advantage":
                            attack_roll.d20_used = max(results)
                        elif adv_value == "disadvantage":
                            attack_roll.d20_used = min(results)
                        else:
                            attack_roll.d20_used = results[0]
                    elif len(results) == 1:
                        attack_roll.d20_used = results[0]
                else:
                    attack_roll.d20_used = results[0] if results else 0
            elif isinstance(results, int):
                attack_roll.results = [results]
                attack_roll.d20_used = results
            attack_roll.bonus = self.dice_roll.bonus
            attack_roll.total = self.dice_roll.total

        attack_breakdown = value_log_rows(self.attack_bonus.breakdown) if self.attack_bonus else []
        advantage_breakdown = advantage_log_rows(self.attack_bonus.advantage_breakdown) if self.attack_bonus else []

        target_ac = 0
        if self.ac:
            target_ac = self.ac.normalized_score
        elif target_entity:
            target_ac = target_entity.ac_bonus().normalized_score

        ac_breakdown = value_log_rows(self.ac.breakdown) if self.ac else []

        outcome = "unknown"
        is_hit = False
        is_crit = False
        if self.attack_outcome:
            outcome_value = self.attack_outcome.value
            outcome = outcome_value.lower()
            is_hit = outcome in ("hit", "crit")
            is_crit = outcome == "crit"

        damage_roll_displays: List[DamageRollDisplay] = []
        total_damage = 0
        if self.damage_rolls and self.damages:
            for i, dr in enumerate(self.damage_rolls):
                damage = self.damages[i] if i < len(self.damages) else None
                damage_type = damage.damage_type.value if damage else "unknown"
                dice_results = []
                if dr.results is not None:
                    if isinstance(dr.results, list):
                        dice_results = list(dr.results)
                    elif isinstance(dr.results, int):
                        dice_results = [dr.results]
                damage_bonus_breakdown = (value_log_rows(value_breakdown(damage.damage_bonus))
                                          if damage and damage.damage_bonus else [])
                num_dice = len(dice_results)
                dice_size = damage.damage_dice if damage else 6
                dice_str = f"{num_dice}d{dice_size}"
                damage_roll_displays.append(DamageRollDisplay(
                    dice_str=dice_str,
                    dice_results=dice_results,
                    bonus=dr.bonus,
                    total=dr.total,
                    damage_type=damage_type,
                    bonus_breakdown=damage_bonus_breakdown
                ))
                total_damage += dr.total

        compact_text = format_attack_compact(
            source_name, target_name, outcome, total_damage
        )
        verbose_text = format_attack_verbose(
            source_name, target_name, spell_name,
            attack_roll, target_ac, outcome,
            damage_roll_displays, total_damage
        )
        detailed_text = format_attack_detailed(
            source_name, target_name, spell_name,
            attack_roll, attack_breakdown,
            target_ac, ac_breakdown, outcome,
            damage_roll_displays, total_damage
        )

        target_hp = target_entity.get_hp() if target_entity else None
        data = AttackLogData(
                attacker_name=source_name,
                attacker_uuid=str(self.source_entity_uuid),
                target_name=target_name,
                target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else '',
                weapon_name=spell_name,
                attack_roll=attack_roll,
                attack_breakdown=attack_breakdown,
                advantage_breakdown=advantage_breakdown,
                target_ac=target_ac,
                ac_breakdown=ac_breakdown,
                outcome=outcome,
                is_hit=is_hit,
                is_crit=is_crit,
                damage_rolls=damage_roll_displays,
                total_damage=total_damage,
                target_hp=target_hp,
                is_threatened=self.is_threatened,
            )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ATTACK,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=data,
            success=is_hit
        )

    def _generate_autohit_spell_log(self) -> CombatLogEntry:
        """Generate a combat log entry for an auto-hit damaging spell."""
        target_name = self.target_entity_name or "Unknown"
        caster_name = self.source_entity_name or "Unknown"
        spell_name = self.name or "Spell"
        total_dmg = self.total_damage or 0

        damage_type = "force"
        if self.damages and len(self.damages) > 0:
            damage_type = self.damages[0].damage_type.value

        dice_str = ""
        if self.damage_rolls and len(self.damage_rolls) > 0:
            dr = self.damage_rolls[0]
            results = dr.results if isinstance(dr.results, list) else [dr.results]
            num_dice = len(results)
            die_size = self.damages[0].damage_dice if self.damages else 4
            bonus = self.damages[0].read_bonus().normalized_score if self.damages and self.damages[0].damage_bonus else 1
            dice_part = f"{num_dice}d{die_size}"
            if bonus != 0:
                dice_part += f"+{bonus}"
            results_str = "+".join(str(r) for r in results)
            if bonus != 0:
                results_str += f"+{bonus}"
            dice_str = f" ({dice_part}: {results_str})"

        compact = f"{md_color(spell_name, 'yellow')} {md_color('hits', 'green')} {md_color(target_name, 'cyan')} for {md_color(str(total_dmg), 'red')} {damage_type} damage"

        verbose = compact + dice_str

        detailed = verbose

        return CombatLogEntry(
            entry_type=CombatLogEntryType.SPELL_DAMAGE,
            source_name=caster_name,
            source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            compact=compact,
            verbose=verbose,
            detailed=detailed,
            data=SpellDamageLogData(
                spell_name=spell_name,
                target_name=target_name,
                damage=total_dmg,
                damage_type=damage_type,
            ),
            success=True
        )


class SpellAttackResolution(BaseModel):
    """Resolved spell attack roll and the values that produced it."""

    attack_bonus: ValueReading = Field(description="Evaluated spell attack bonus used for the roll.")
    target_ac: ValueReading = Field(description="Evaluated target armor class used to determine the outcome.")
    dice_roll: DiceRoll = Field(description="Completed d20 spell attack roll.")
    outcome: AttackOutcome = Field(description="Hit, miss, or critical outcome of the roll.")
    is_threatened: bool = Field(
        description="Whether ranged-attack disadvantage was applied because a visible hostile threatened the caster.",
    )


@dataclass
class PreparedSpellConcentration:
    owner: BaseBlock
    condition: Concentrating
    application: PreparedConditionApplication | None
    parent_event: Event


def resolve_spell_attack_values(caster:Entity,target:Entity|BaseItem,parent_event_uuid:UUID,*,
    ranged:bool,spellcasting_source_id:UUID|None=None,casting_ability:AbilityName|None=None,
    extra_advantage_modifiers:Tuple[AdvantageModifier,...]=(),attack_origin_position:tuple[int,int]|None=None)->SpellAttackResolution:
    """Native spell-roll mechanics shared by spells and intrinsic spell attacks."""
    attack_value = caster.spell_attack_value(
        ValueRead(caster.uuid, target.uuid),
        spellcasting_source_id=spellcasting_source_id,
        casting_ability=casting_ability,
    )
    ac_value = (target.armor_class_value(ValueRead(target.uuid, caster.uuid)) if isinstance(target, Entity)
        else parts(ModifiableValue(source_entity_uuid=target.uuid, base=target.armor_class, name="Object AC",
                                   use_register=False)))
    context = {"attack_origin_position": attack_origin_position} if attack_origin_position is not None else None
    attack_value = with_rows(attack_value, tuple(Row(Channel.SELF_STATIC, Kind.ADVANTAGE, modifier)
                                                 for modifier in extra_advantage_modifiers))

    is_threatened = ranged and caster.is_threatened()
    if is_threatened:
        attack_value = with_rows(attack_value, (Row(Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
                name="Threatened (Ranged)",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
            )),))

    attack_bonus = read_value(attack_value, ValueRead(caster.uuid, target.uuid, context,
        outgoing_of(ac_value, context)))
    target_ac = read_value(ac_value, ValueRead(target.uuid, caster.uuid, context,
        outgoing_of(attack_value, context)))
    dice_roll = caster.roll_d20(
        attack_bonus,
        RollType.ATTACK,
        parent_event=parent_event_uuid,
    )
    outcome = determine_attack_outcome(
        dice_roll,
        target_ac.normalized_score,
        caster.get_spell_crit_threshold(),
    )
    return SpellAttackResolution(
        attack_bonus=attack_bonus,
        target_ac=target_ac,
        dice_roll=dice_roll,
        outcome=outcome,
        is_threatened=is_threatened,
    )

class SpellAction(BaseAction):
    creates = (Concentrating,)
    magical_transfer: bool = False
    """Base class for all spells. Handles metadata and variant generation.

    Spell subclasses implement their own `_apply()` logic. This base class
    provides spell metadata, upcast variant generation, action and slot costs,
    concentration bookkeeping, and client-facing declaration metadata.
    """

    action_category: ActionCategory = Field(default=ActionCategory.SPELL, description="Classifies this action as a spell.")


    spell_level: int = Field(default=0, description="Base spell level (0 = cantrip)")
    spell_school: str = Field(default="evocation", description="School of magic")
    concentration: bool = Field(default=False, description="Whether spell requires concentration")
    verbal: bool = Field(default=True, description="Whether spell has a verbal component")

    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range of the spell"
    )

    cast_at_level: int = Field(default=0, description="Actual slot level used (0 = cantrip)")
    is_variant: bool = Field(default=False, description="Whether this is an upcast variant")
    castable_levels: tuple[int, ...] = Field(default=(), description=(
        "Slot levels a discovery row of this spell can be cast at (plan D17); empty outside discovery."))

    caster_level: int = Field(default=1, description="Level of the caster (for cantrip scaling)")
    cast_cost_grant_id: UUID | None = Field(default=None, description="Exact native grant paying this base-rank cast instead of a spell slot.")
    cast_cost_label: str | None = None
    retained_casting_ability: AbilityName | None = None
    spellcasting_source_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Exact registered spellcasting source that owns this spell. "
            "None retains the legacy default spellcasting ability."
        ),
    )

    cast_concentrating_uuid: Optional[UUID] = Field(
        default=None,
        exclude=True,
        description="Concentrating condition UUID reused across one convolution cast.",
    )

    alt_range: Optional[int] = Field(default=None, description="Override spell_range.normal")
    cast_origin: Literal["actor", "source_item"] = Field(
        default="actor", description="Actor or placed item supplying the spell's range and launch origin.",
    )
    target_sector_degrees: Optional[float] = Field(
        default=None, gt=0, le=360,
        description="Optional total target-sector width around the operator-to-item direction.",
    )

    projectile_type: Optional[str] = Field(default=None, description="VFX projectile delivery type")
    physical_access: Optional[PhysicalAccess] = Field(
        default=None, description="Authored physical path required to reach a spell target; independent of VFX.",
    )
    spell_damage_type: Optional[DamageType] = Field(default=None, description="Primary native damage type, also available to presentation.")
    harmful: Optional[bool] = Field(default=None, description="Explicit harmful intent for rules without damage or target-effect profiles; otherwise derive from those native declarations.")
    saving_throw_effect_id: Optional[str] = Field(
        default=None,
        description=(
            "Stable authored effect identity for saves requested by this "
            "spell; defaults to the exact spell content identity."
        ),
    )
    saving_throw_effect_tags: Tuple[SavingThrowEffectTag, ...] = Field(
        default=(),
        description="Closed origin-rule tags carried by this spell's saves.",
    )

    costs: List[Cost] = Field(
        default_factory=lambda: [Cost(name="Cast Spell", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)],
        description="Action cost for casting"
    )

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        if self.physical_access is not None:
            return self.physical_access
        spell_range = self.get_range()
        return PhysicalAccess.HAND if spell_range is not None and spell_range.type is RangeType.REACH else None

    def spell_execution_scope(self):
        """Open the cast-local context used by low-level damage contributors."""

        binding = self.behavior_binding
        cause_id = binding.behavior_id if binding is not None else None
        saving_throw_effect_id = self.saving_throw_effect_id
        if saving_throw_effect_id is None and cause_id is not None:
            saving_throw_effect_id = (
                f"{cause_id}.saving_throw"
            )
        return spell_execution_scope(
            source_entity_uuid=self.source_entity_uuid,
            damage_type=self.spell_damage_type,
            cause_id=cause_id,
            saving_throw_effect_id=saving_throw_effect_id,
            saving_throw_effect_tags=self.saving_throw_effect_tags,
        )

    def bind_spell_execution_lineage(self, lineage_uuid: UUID) -> None:
        """Bind the active cast context to its authoritative event lineage."""

        bind_spell_execution_lineage(lineage_uuid)

    def apply(self, parent_event: Optional[Event] = None) -> Optional[Event]:
        """Apply the spell within one isolated, bounded cast context."""

        with self.spell_execution_scope() as execution:
            try:
                return super().apply(parent_event)
            finally:
                self._release_spell_execution(execution)

    def _release_spell_execution(
        self,
        execution: SpellExecutionState,
    ) -> None:
        """Release ephemeral contribution claims after the cast completes."""

        if execution.lineage_uuid is None:
            return
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return
        caster.spellcasting.release_spell_damage_affinity_execution(
            execution.lineage_uuid,
        )

    def model_post_init(self, __context: Any) -> None:
        """Set concentration flags and append slot costs for leveled spells."""
        super().model_post_init(__context)
        if self.concentration:
            self.requires_concentration = True
        if self.spell_level > 0:
            if self.cast_at_level == 0:
                self.cast_at_level = self.spell_level
            has_slot_cost = any(c.cost_type.startswith("spell_slot") for c in self.costs)
            if not has_slot_cost:
                cost_type = spell_slot_cost_type(self.cast_at_level)
                self.costs.append(Cost(
                    name=f"Spell Slot L{self.cast_at_level}",
                    cost_type=cost_type,
                    cost=1,
                    evaluator=entity_action_economy_cost_evaluator
                ))

    @property
    def effective_range(self) -> int:
        """Spell range with alt override applied."""
        if self.alt_range is not None:
            return self.alt_range
        return self.spell_range.normal

    def _object_recipient_contact(self, source: Entity, target: BaseItem) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
        """(error, contact position) of one object this spell would target."""
        if (self.effective_target_type is not TargetType.CREATURE_OR_OBJECT or not (
                target.is_active if self.object_target_policy == "active" else target.is_breakable())):
            return "This spell cannot target this object", None
        contact = get_map().attack_object_contact(source.uuid, target.uuid,
            range_feet=self.effective_range, access=self.get_physical_access() or PhysicalAccess.PROJECTILE,
            subjective=True, origin=self.get_target_origin())
        return (None, contact) if contact is not None else ("Object is out of spell reach", None)

    def single_recipient_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """One creature or object recipient, read from the selection: the spell's single-recipient rule."""
        source = Entity.get(self.source_entity_uuid)
        target_uuid = selection.target_uuids[0] if selection.target_uuids else None
        target = BaseBlock.get(target_uuid) if target_uuid is not None else None
        if source is None or target is None:
            return "Caster or target not found"
        if isinstance(target, BaseItem):
            return self._object_recipient_contact(source, target)[0]
        if target.uuid == source.uuid:
            return None if self.include_self else "This spell does not allow self targeting"
        if Entity.get(target.uuid) is None:
            return f"Target entity not found for {self.name}"
        record = scan.creatures.get(target.uuid)
        if record is None or not record.visual:
            return f"Target entity not in line of sight for {self.name}"
        if self.get_target_distance(target.position) > self.effective_range:
            return "Target is out of spell range"
        return None

    def get_range(self) -> Range:
        """Return spell range with alt_range override for position filtering."""
        return Range(type=self.spell_range.type, normal=self.effective_range, long=self.spell_range.long)

    def get_target_origin(self) -> Optional[Tuple[int, int]]:
        if self.cast_origin == "actor":
            return super().get_target_origin()
        return get_map().get_object_position(self.source_item_uuid) if self.source_item_uuid is not None else None

    def _source_item_targeting_error(self) -> Optional[str]:
        if self.cast_origin == "actor":
            return None if self.target_sector_degrees is None else "A firing sector requires a source-item origin"
        actor = Entity.get(self.source_entity_uuid)
        origin = self.get_target_origin()
        if actor is None or origin is None:
            return "Spell source item is not placed"
        if self.source_item_uuid not in actor.senses.objects:
            return "Spell source item is not perceived"
        if origin == actor.position or grid_distance_feet(actor.position, origin) > 5:
            return "Operator must stand beside the spell source item"
        return None

    def target_position_error(self, position: Tuple[int, int]) -> Optional[str]:
        error = self._source_item_targeting_error() or super().target_position_error(position)
        if error is not None or self.target_sector_degrees is None:
            return error
        origin = self.get_target_origin()
        actor_origin = super().get_target_origin()
        if origin is None or actor_origin is None:
            return "Spell targeting origin is not placed"
        forward = (origin[0] - actor_origin[0], origin[1] - actor_origin[1])
        if not position_in_sector(origin, forward, position, self.target_sector_degrees):
            return "Target is outside the device firing sector"
        return None

    def _family_admission_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Casting entitlement, device concentration capacity, the source-item origin and its firing sector."""
        return (self.casting_entitlement_error() or self._concentration_capacity_error()
                or self._source_item_targeting_error() or self.spell_targeting_error(selection))

    def spell_targeting_error(self, selection: ActionSelection) -> Optional[str]:
        """Range and firing sector of the selected center or recipients from a source-item origin.

        Every spell shares it, so it is not this family's `rule_error`: a
        spell's own rule never has to compose it.
        """
        if self.cast_origin == "actor" and self.target_sector_degrees is None:
            return None
        # Test selected centers/recipients, never secondary area occupants.
        if self.effective_target_type in (TargetType.POSITION, TargetType.POSITION_LOS,
                                          TargetType.POSITION_PATH, TargetType.POSITION_AOE):
            positions = list(selection.positions[:1])
        elif self.effective_target_type in (TargetType.ENTITY, TargetType.MULTI_ENTITY,
                                           TargetType.CREATURE_OR_OBJECT):
            positions = []
            for identity in selection.target_uuids:
                target = BaseBlock.get(identity)
                if isinstance(target, BaseItem):
                    contact = get_map().attack_object_contact(self.source_entity_uuid,
                        identity, range_feet=self.effective_range,
                        access=self.get_physical_access() or PhysicalAccess.PROJECTILE,
                        subjective=True, origin=self.get_target_origin())
                    if contact is None:
                        return "Object is out of spell reach"
                    positions.append(contact)
                elif target is not None:
                    positions.append(target.position)
        else:
            positions = []
        for position in positions:
            if (error := self.target_position_error(position)) is not None:
                return error
        return None

    def get_upcast_bonus(self) -> int:
        """Get levels above base spell level (for upcast scaling)."""
        return max(0, self.cast_at_level - self.spell_level)

    def spell_attack_outcome_profile(
        self,
        caster: Entity,
        *,
        dice_count: int,
        die_size: int,
        damage_type: DamageType,
        applications: int = 1,
        flat_bonus: Optional[int] = None,
    ) -> ActionOutcomeProfile:
        """Build the actor-baseline model for a spell attack rule."""
        baseline = caster.spell_attack_outcome_baseline(
            spellcasting_source_id=self.spellcasting_source_id,
            casting_ability=self.retained_casting_ability,
        )
        advantage = baseline.advantage
        if self.get_range().type is RangeType.RANGE and caster.is_threatened():
            advantage = (
                AdvantageStatus.NONE
                if advantage is AdvantageStatus.ADVANTAGE
                else AdvantageStatus.DISADVANTAGE
            )
        bonus = caster.spell_damage_outcome_bonus() if flat_bonus is None else flat_bonus
        return ActionOutcomeProfile(
            resolution=OutcomeResolution.ATTACK_ROLL,
            applications=applications,
            damage_rolls=[DamageRollProfile(
                dice_count=dice_count,
                die_size=die_size,
                flat_bonus=bonus,
                damage_type=damage_type.value,
            )],
            attack_bonus=baseline.attack_bonus,
            advantage=advantage,
            critical_threshold=baseline.critical_threshold,
            critical_extra_dice=baseline.critical_extra_dice,
        )

    def resolve_spell_attack(
        self,
        caster: Entity,
        target: Entity | BaseItem,
        parent_event_uuid: UUID,
        *,
        extra_advantage_modifiers: Tuple[AdvantageModifier, ...] = (),
        attack_origin_position: tuple[int,int] | None = None,
    ) -> SpellAttackResolution:
        """Resolve one spell attack through the shared ranged-threat rule.

        Args:
            caster: Entity making the spell attack.
            target: Entity whose armor class opposes the attack.
            parent_event_uuid: Parent spell event for the d20 result event.
            extra_advantage_modifiers: Spell-specific roll modifiers to include.

        Returns:
            Typed spell attack values, roll, outcome, and threat state.
        """
        return resolve_spell_attack_values(caster,target,parent_event_uuid,
            ranged=self.get_range().type is RangeType.RANGE,spellcasting_source_id=self.spellcasting_source_id,
            casting_ability=self.retained_casting_ability,
            extra_advantage_modifiers=extra_advantage_modifiers,attack_origin_position=attack_origin_position)

    def automatic_damage_outcome_profile(
        self,
        *,
        dice_count: int,
        die_size: int,
        flat_bonus: int,
        damage_type: DamageType,
        applications: int = 1,
        effect_id: Optional[str] = None,
    ) -> ActionOutcomeProfile:
        """Build an automatic-hit damage model declared by a spell rule."""
        return ActionOutcomeProfile(
            effect_id=effect_id,
            resolution=OutcomeResolution.AUTOMATIC,
            applications=applications,
            damage_rolls=[DamageRollProfile(
                dice_count=dice_count,
                die_size=die_size,
                flat_bonus=flat_bonus,
                damage_type=damage_type.value,
            )],
        )

    def saving_throw_damage_outcome_profile(
        self,
        caster: Entity,
        *,
        dice_count: int,
        die_size: int,
        damage_type: DamageType,
        save_ability: str,
        half_damage_on_save: bool,
        application_scope: OutcomeApplicationScope = OutcomeApplicationScope.ALLOCATED_TARGETS,
        applications: int = 1,
        flat_bonus: Optional[int] = None,
    ) -> ActionOutcomeProfile:
        """Build an actor-known saving-throw damage rule for policy estimates."""
        bonus = caster.spell_damage_outcome_bonus() if flat_bonus is None else flat_bonus
        return ActionOutcomeProfile(
            resolution=OutcomeResolution.SAVING_THROW,
            applications=applications,
            application_scope=application_scope,
            damage_rolls=[DamageRollProfile(
                dice_count=dice_count,
                die_size=die_size,
                flat_bonus=bonus,
                damage_type=damage_type.value,
            )],
            save_dc=caster.spell_save_dc(
                spellcasting_source_id=self.spellcasting_source_id,
            ),
            save_ability=save_ability,
            half_damage_on_save=half_damage_on_save,
        )

    def resolve_saving_throw(
        self,
        execution_event: SpellEvent,
        *,
        caster: Entity,
        target: Entity,
        ability_name: AbilityName,
        dc: int,
    ) -> Tuple[SpellEvent, DiceRoll, bool]:
        """Resolve a child save and synchronize its result onto the spell event."""
        ability_display = ability_name.upper()[:3]
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability=ability_name,
            save_dc=dc,
            status_message=f"Requesting {ability_display} save DC {dc}",
        )
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=ability_name,
            dc=dc,
            parent_event=effect_event.uuid,
        )
        _, save_roll, success = target.saving_throw(save_request)
        synced_event = effect_event.post(
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_roll.bonus,
            status_message=(
                f"{ability_display} save: {save_roll.total} vs DC {dc} - "
                f"{'Success' if success else 'Failure'}"
            ),
        )
        return synced_event, save_roll, success

    def describe_discovery(self) -> ActionDiscoveryDescription:
        actor = Entity.get(self.source_entity_uuid)
        source = actor.spellcasting.sources.get(self.spellcasting_source_id) if actor is not None else None
        return ActionDiscoveryDescription(spell_level=self.spell_level, cast_at_level=self.cast_at_level,
            cast_levels=self.castable_levels, is_spell_variant=self.is_variant, cast_cost_label=self.cast_cost_label,
            spellcasting_source_id=self.spellcasting_source_id,
            spellcasting_provider_id=source.provider_id if source is not None else None,
            spellcasting_ability=source.ability if source is not None else None,
            damage_types=(self.spell_damage_type,) if self.spell_damage_type is not None else ())

    def get_concentration_owner(self) -> Entity | BaseItem | None:
        """Resolve the actual sustainer independently of casting attribution."""
        item = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid is not None else None
        if isinstance(item, BaseItem) and item.concentration_capacity > 0:
            return item
        return Entity.get(self.source_entity_uuid)

    def _concentration_capacity_error(self) -> Optional[str]:
        if not self.concentration:
            return None
        owner = self.get_concentration_owner()
        if not isinstance(owner, BaseItem):
            return None
        existing = owner.active_conditions.get("Concentrating")
        if (isinstance(existing, Concentrating) and existing.uuid != self.cast_concentrating_uuid
                and len(existing.concentration_slots) >= owner.concentration_capacity):
            return "Device concentration capacity is full"
        return None

    def prepare_concentration(self, parent_event: Event) -> PreparedSpellConcentration | Event | None:
        """Prepare this cast's optional sustainer without replacing the live graph."""
        if not self.concentration:
            return None
        owner = self.get_concentration_owner()
        if owner is None:
            return parent_event.cancel(status_message="Concentration owner no longer exists")
        current = owner.active_conditions_by_uuid.get(self.cast_concentrating_uuid) if self.cast_concentrating_uuid else None
        if isinstance(current, Concentrating):
            return PreparedSpellConcentration(owner, current, None, parent_event)
        if self.cast_concentrating_uuid is not None:
            # This cast's concentration already ended mid-batch: later targets
            # are not re-sustained by a new one (bug J).
            return parent_event.cancel(status_message="The cast's concentration has ended")
        condition = self._new_concentration(owner, parent_event)
        application = owner.prepare_condition_application(condition, parent_event=parent_event)
        if not isinstance(application, PreparedConditionApplication):
            return application or parent_event.cancel(status_message="Concentration was not admitted")
        return PreparedSpellConcentration(owner, condition, application, parent_event)

    def commit_prepared_concentration(self, prepared: PreparedSpellConcentration,
                                     target_owner: BaseBlock, effect: BaseCondition) -> None:
        prepared.condition.add_linked_condition(target_owner.uuid, effect.uuid)
        if prepared.application is not None:
            prepared.owner.commit_condition_application(prepared.application)
        self.cast_concentrating_uuid = prepared.condition.uuid

    @staticmethod
    def publish_prepared_concentration(prepared: PreparedSpellConcentration) -> None:
        if prepared.application is not None:
            prepared.owner.publish_condition_application(prepared.application)
        else:
            prepared.condition.publish_owner_state(prepared.parent_event)

    def apply_owned_condition(self, event: SpellEvent, effect: BaseCondition) -> SpellEvent:
        """Admit both memberships and the exact sustain link before completion."""
        target = BaseBlock.get(effect.target_entity_uuid) if effect.target_entity_uuid else None
        if target is None:
            return event.cancel(status_message="Spell recipient no longer exists")
        if event.canceled:
            target._discard_uncommitted_condition_tree(effect)
            return event
        with BaseBlock.condition_removal_scope():
            application = target.prepare_condition_application(effect, parent_event=event)
            if not isinstance(application, PreparedConditionApplication):
                return event.cancel(status_message="Spell effect was not admitted")
            try:
                concentration = self.prepare_concentration(event)
            except BaseException:
                target.cancel_condition_application(application, "Concentration admission raised")
                raise
            if isinstance(concentration, Event):
                target.cancel_condition_application(application, "Concentration was not admitted")
                return event.cancel(status_message="Concentration was not admitted")
            if concentration is not None:
                self.commit_prepared_concentration(concentration, target, effect)
            target.commit_condition_application(application)
            errors: list[BaseException] = []
            if concentration is not None:
                try:
                    self.publish_prepared_concentration(concentration)
                except BaseException as error:
                    errors.append(error)
            try:
                target.publish_condition_application(application)
            except BaseException as error:
                errors.append(error)
            if errors:
                raise BaseExceptionGroup("Committed spell condition publication failed", errors)
        return event

    def _new_concentration(self, owner: Entity | BaseItem, parent_event: Event) -> "Concentrating":
        conc = Concentrating(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=owner.uuid,
            spell_name=self.name or "Unknown",
            spell_id=self.behavior_binding.behavior_id if self.behavior_binding is not None else self.semantic_key,
        )
        conc.record_cast_owner(parent_event.application.lineage_uuid if isinstance(parent_event, ActionEvent)
            and parent_event.application is not None else parent_event.lineage_uuid)
        return conc

    def ensure_concentration(self, parent_event: Event) -> "Concentrating":
        """Create or reuse Concentrating for this cast. Safe for convolution loop.

        The first call for a cast creates Concentrating and replaces any older
        concentration. Later calls in the same convolution loop reuse the UUID
        created by the first target.
        """
        owner = self.get_concentration_owner()
        if owner is None:
            raise ValueError("Concentration owner not found")

        if self.cast_concentrating_uuid:
            existing = owner.active_conditions_by_uuid.get(self.cast_concentrating_uuid)
            if existing and isinstance(existing, Concentrating):
                return existing

        conc = self._new_concentration(owner, parent_event)
        owner.add_condition(conc, parent_event=parent_event)
        self.cast_concentrating_uuid = conc.uuid
        result = owner.active_conditions["Concentrating"]
        assert isinstance(result, Concentrating)
        return result

    def _cleanup_concentration(self, effect_event: ActionEvent) -> None:
        """Close empty concentration state before the action terminal.

        Also clean up empty slots in multi-slot scenarios."""
        if not self.cast_concentrating_uuid:
            return
        owner = self.get_concentration_owner()
        if not owner or "Concentrating" not in owner.active_conditions:
            return
        conc = owner.active_conditions["Concentrating"]
        if not isinstance(conc, Concentrating) or conc.uuid != self.cast_concentrating_uuid:
            return
        conc.cleanup_if_no_effects(parent_event=effect_event)
        if "Concentrating" in owner.active_conditions:
            empty_slot_uuids = [slot_uuid for slot_uuid, slot in conc.concentration_slots.items() if not slot.linked_entries]
            for slot_uuid in empty_slot_uuids:
                conc.concentration_slots[slot_uuid].remove_from_register()
                del conc.concentration_slots[slot_uuid]
            if empty_slot_uuids:
                conc._sync_spell_name()
            conc.publish_owner_state(effect_event)

    def _get_range_type(self) -> Optional[str]:
        """Map spell range type to VFX delivery string."""
        rt = self.get_range().type
        if rt == RangeType.SELF:
            return "self"
        if rt == RangeType.REACH:
            return "touch"
        if rt == RangeType.RANGE:
            return "ranged"
        return None

    @property
    def casts_without_slot(self) -> bool:
        """A cantrip, a spell cast without a slot, or one an item pays for."""
        return self.spell_level == 0 or self.alt_skip_slot or self.source_item_uuid is not None

    def discovery_selections(self, scan: ActorScan) -> Tuple[ActionSelection, ...]:
        """A slotless spell as registered; otherwise one row per spell (plan D17) and one per free cast.

        The slot row is at the lowest level with a slot available now and
        carries every such level; with slot capacity but none available, it is
        one unaffordable row at the lowest capacity.
        """
        own = self.current_selection()
        if self.casts_without_slot:
            return (own,)
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return ()
        capacity = [level for level in range(self.spell_level, 10) if caster.has_spell_slot_capacity(level)]
        available = [level for level in capacity if caster.has_spell_slot(level)]
        rows = [replace(own, cast_at_level=(available or capacity)[0])] if capacity else []
        rows.extend(replace(own, cast_at_level=self.spell_level, cost_source=CostSource(free_cast_grant_uuid=grant.grant_id))
            for grant in caster.spellcasting.free_cast_grants.values()
            if grant.source_id == self.spellcasting_source_id and grant.spell_id == self.get_authored_spell_id()
            and grant.cast_rank == self.spell_level
            and (not grant.outside_encounter_only or caster.active_encounter_uuid is None))
        return tuple(rows)

    def current_selection(self) -> ActionSelection:
        """The cast level and free cast are part of a spell's selection; a registered spell has chosen neither."""
        own = super().current_selection()
        return replace(own, cast_at_level=None if self.template else self.cast_at_level,
            cost_source=replace(own.cost_source, free_cast_grant_uuid=self.cast_cost_grant_id))

    def _free_cast_costs(self, grant: FreeSpellCastGrant) -> List[Cost]:
        """The base-rank cast's costs when one free-cast grant pays instead of a slot."""
        costs = [cost for cost in self._get_costs_for_level(self.spell_level) if not cost.cost_type.startswith("spell_slot")]
        if grant.resource_name is not None:
            costs.append(Cost(name=grant.label, cost_type="actions", cost=0, resource_name=grant.resource_name,
                resource_cost=1, resource_evaluator=entity_resource_cost_evaluator))
        return costs

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        """A spell's level and payment come from the selection too.

        A spell cast without a slot casts as provided. A slot or free cast stores normalized
        executable costs, so the registered cost transforms are not applied a
        second time.
        """
        overrides = super()._selection_overrides(selection)
        free_cast = selection.cost_source.free_cast_grant_uuid
        if self.casts_without_slot and free_cast is None:
            return overrides
        level = selection.cast_at_level if selection.cast_at_level is not None else self.cast_at_level
        caster = Entity.get(self.source_entity_uuid)
        overrides.update(cast_at_level=level, is_variant=True, alt_cost_type=None, alt_extra_costs=[], alt_skip_slot=False)
        if free_cast is not None:
            grant = caster.spellcasting.free_cast_grants.get(free_cast) if caster is not None else None
            if grant is None:
                raise ValueError("The selected free cast is not available")
            overrides.update(costs=self._free_cast_costs(grant), cast_cost_grant_id=grant.grant_id,
                cast_cost_label=grant.label, castable_levels=())
        else:
            overrides.update(costs=self._get_costs_for_level(level), cast_cost_grant_id=None, cast_cost_label=None,
                castable_levels=tuple(castable for castable in range(self.spell_level, 10) if caster is not None
                    and caster.has_spell_slot_capacity(castable) and caster.has_spell_slot(castable)))
        return overrides

    def casting_entitlement_error(self) -> str | None:
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return "Caster is missing"
        authored = self.get_authored_spell_id()
        if self.spellcasting_source_id is not None and authored is not None and authored.startswith("spell."):
            if self.spellcasting_source_id not in caster.spellcasting.sources:
                return "The casting source is no longer available"
            entitlements = caster.spellcasting.spell_entitlements.get(self.spellcasting_source_id)
            if entitlements is not None and authored not in entitlements:
                return "This spell is no longer prepared by this source"
        if self.cast_cost_grant_id is not None:
            grant = caster.spellcasting.free_cast_grants.get(self.cast_cost_grant_id)
            if (grant is None or grant.source_id != self.spellcasting_source_id or grant.spell_id != authored
                    or grant.cast_rank != self.cast_at_level
                    or grant.outside_encounter_only and caster.active_encounter_uuid is not None):
                return "The selected casting cost is no longer available"
        return None


    def get_discovery_display_name(self) -> str:
        """Return a human-facing label for this spell discovery row."""
        base_name = self.name or "Unknown"
        if self.cast_cost_grant_id is not None:
            return f"{base_name} ({self.cast_cost_label})"
        if self.is_variant and self.spell_level > 0:
            return f"{base_name} (Level {self.cast_at_level})"
        return base_name

    def _get_costs_for_level(self, level: int) -> List[Cost]:
        """Get costs for casting at a specific level.

        Preserves the spell's actual action cost type (action vs bonus_action).
        Respects alt overrides (alt_cost_type, alt_skip_slot, alt_extra_costs).

        Args:
            level: The spell slot level (0 for cantrips)

        Returns:
            List of Cost objects (action/bonus_action + spell slot if level > 0)
        """
        base_cost = self.costs[0] if self.costs else Cost(
            name="Cast Spell", cost_type="actions", cost=1,
            evaluator=entity_action_economy_cost_evaluator
        )
        cost = base_cost.model_copy()
        if self.alt_cost_type is not None and cost.cost_type == "actions":
            cost = cost.model_copy(update={"cost_type": self.alt_cost_type})
        costs = [cost]
        if level > 0 and not self.alt_skip_slot:
            slot_cost_type = spell_slot_cost_type(level)
            costs.append(Cost(name=f"Spell Slot L{level}", cost_type=slot_cost_type, cost=1, evaluator=entity_action_economy_cost_evaluator))
        costs.extend(self.alt_extra_costs)
        return costs

    def get_effect_origin_for_preview(self) -> EffectOrigin | None:
        caster=Entity.get(self.source_entity_uuid)
        if caster is None:
            return None
        harmful,_=self.get_harmful_intent(caster,[])
        return EffectOrigin.spell(source_id=self.get_authored_spell_id(),source_event_lineage_uuid=None,
            source_position=caster.position,base_spell_level=self.spell_level,effective_spell_level=self.cast_at_level,
            spell_school=self.spell_school,spellcasting_source_id=self.spellcasting_source_id,
            harmful=harmful,area_application=self.effective_target_type is TargetType.POSITION_AOE
                or self.get_selection_geometry() is not None)

    def get_harmful_intent(
        self,
        caster: Entity,
        targets: List[UUID],
    ) -> Tuple[bool, List[UUID]]:
        """Resolve native intent once, preserving conditional recipient branches."""
        if self.harmful is not None:
            return self.harmful, list(dict.fromkeys(targets)) if self.harmful else []
        if self.spell_damage_type is not None:
            return True, list(dict.fromkeys(targets))
        profile = self.get_target_effect_profile()
        branches = tuple(
            branch for branch in profile.branches
            if branch.disposition is TargetEffectDisposition.HARMFUL
        ) if profile is not None else ()
        if not branches:
            return False, []
        recipients: List[UUID] = []
        for target_uuid in dict.fromkeys(targets):
            target = Entity.get(target_uuid)
            if target is None:
                continue
            creature_type = target.creature_type.value
            if any(
                (not branch.included_creature_types or creature_type in branch.included_creature_types)
                and creature_type not in branch.excluded_creature_types
                for branch in branches
            ):
                recipients.append(target_uuid)
        return bool(branches), recipients

    def get_spell_weapon_attack_slot(self) -> WeaponSlot | None:
        return None

    def get_authored_spell_id(self) -> str | None:
        """Return exact authored identity without relying on a presentation name."""
        if self.behavior_binding is not None:
            return self.behavior_binding.behavior_id
        try:
            return get_content_declaration(type(self)).ref.content_id
        except ValueError:
            return self.semantic_key

    def has_authored_damage(self) -> bool:
        if self.spell_damage_type is not None:
            return True
        try:
            return bool(get_spell_catalog_metadata(type(self)).damage_types)
        except ValueError:
            return False

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for this spell."""
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        declared_targets = self._declared_target_entity_uuids()
        harmful, harmful_targets = (
            self.get_harmful_intent(source_entity, declared_targets)
            if source_entity is not None else (False, [])
        )

        source_name = source_entity.name if source_entity else None
        target_name = target_entity.name if target_entity else None

        contact = None
        placement = None
        if isinstance(target_entity, BaseItem):
            placement = get_map().get_object_placement(target_entity.uuid)
            access = self.get_physical_access()
            if access is not None:
                contact = get_map().attack_object_contact(self.source_entity_uuid,
                    target_entity.uuid, range_feet=self.effective_range, access=access,
                    subjective=True, origin=self.get_target_origin())
        event = SpellEvent(
            event_type=EventType.CAST_SPELL if self.is_spell else EventType.BASE_ACTION,
            weapon_attack_slot=self.get_spell_weapon_attack_slot(),
            target_kind="object" if isinstance(target_entity, BaseItem) else "creature",
            target_position=(self.end_position if self.effective_target_type in (TargetType.POSITION,TargetType.POSITION_LOS)
                else contact if isinstance(target_entity, BaseItem) else target_entity.position if target_entity else None),
            target_base_height_steps=placement.base_height_steps if placement else None,
            name=f"{self.name}",
            spell_id=normalize_spell_id(self.name or ""),
            authored_spell_id=self.get_authored_spell_id(),
            target_type=self.effective_target_type,
            harmful=harmful,
            harmful_target_entity_uuids=harmful_targets,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name,
            target_entity_name=target_name,
            spell_level=self.spell_level,
            cast_at_level=self.cast_at_level,
            spell_school=self.spell_school,
            can_deal_damage=self.has_authored_damage(),
            magical_transfer=self.magical_transfer,
            spellcasting_source_id=self.spellcasting_source_id,
            verbal=self.verbal,
            cast_origin=self.cast_origin,
            effect_source_position=self.get_target_origin(),
            area_propagation=self.aoe_shape.propagation if self.aoe_shape is not None else "line_of_effect",
            source_position=source_entity.position if source_entity else None,
            area_geometry=(
                self.aoe_shape.presentation_geometry(self.end_position, source_entity.position)
                if self.aoe_shape is not None and self.end_position is not None and source_entity is not None
                else None
            ),
            aoe_position=self.end_position if self.effective_target_type == TargetType.POSITION_AOE else None,
            aoe_shape_type=self.aoe_shape.kind if self.aoe_shape is not None else None,
            aoe_radius_ft=self.aoe_shape.extent_feet() if self.aoe_shape is not None else None,
            range_type=self._get_range_type(),
            range_ft=self.effective_range,
            projectile_type=self.projectile_type,
            damage_types=[self.spell_damage_type] if self.spell_damage_type else [],
            source_item_uuid=self.source_item_uuid,
            source_item_presentation=self.source_item_presentation,
            item_charge_cost=self.charge_cost if self.source_item_uuid is not None else 0,
            item_charge_action_lineage_uuid=None,
            declared_target_entity_uuids=declared_targets,
        )
        event.item_charge_action_lineage_uuid = event.lineage_uuid
        if current_spell_execution() is not None:
            self.bind_spell_execution_lineage(event.lineage_uuid)
        return event

    def _apply_costs(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply the costs of the spell."""
        error = self.casting_entitlement_error()
        if error:
            return execution_event.cancel(status_message=error)
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)

    def _get_cantrip_dice_count(self, caster_level: int) -> int:
        """Get number of damage dice for cantrips based on caster level.

        Cantrips scale at levels 5, 11, and 17.
        """
        if caster_level >= 17:
            return 4
        if caster_level >= 11:
            return 3
        if caster_level >= 5:
            return 2
        return 1


@_core_action_identity(
    content_id="action.pick_up",
    display_name="Pick Up",
    description="Pick up an adjacent portable object.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Other Activity on Your Turn",
    sort_order=120,
)
class PickUp(BaseAction):
    """Pick up an item from the ground. Free action (no cost).

    Uses target_entity_uuid to hold the item UUID (items are BaseBlocks
    registered in _registry, so BaseBlock.get(uuid) finds them).
    """
    name: str = Field(default="Pick Up", description="Action name for ground-item pickup.")
    description: str = Field(
        default="Pick up an item from the ground",
        description="Action description shown for ground-item pickup.",
    )
    target_type: TargetType = Field(
        default=TargetType.OBJECT,
        description="PickUp targets a floor object.",
    )
    costs: List[Cost] = Field(
        default_factory=empty_list,
        description="No-cost action-economy payload for pickup.",
    )

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        return PhysicalAccess.HAND

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return "Entity not found"

        item = BaseBlock.get(selection.target_uuids[0]) if selection.target_uuids else None
        if not isinstance(item, BaseItem) or not item.is_pickable:
            return "Cannot pick up this object"

        if not entity.inventory.can_add(item):
            return "Inventory full"

        if get_map().get_object_position(item.uuid) is None:
            return "Item not on the ground"

        return None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not entity or not isinstance(item, BaseItem):
            return execution_event.cancel(status_message="Entity or item not found")

        if get_map().manual_object_contact(entity.uuid, item.uuid) is None:
            return execution_event.cancel(status_message="Object is out of reach")
        if not item.is_pickable or not entity.inventory.can_add(item):
            return execution_event.cancel(status_message="Cannot pick up this object")

        if not entity.loot_item(item, parent_event=execution_event):
            return execution_event.cancel(status_message="Item transfer was rejected")
        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Picked up {item.name}"
        )



class Drop(BaseAction):
    """Drop an item from inventory onto the ground at a position.

    Position-target action (POSITION_LOS) bound to a specific item.
    Valid positions: entity's own cell + adjacent cells (range 5ft).

    The item_uuid is bound at creation time (one Drop per item).
    """
    name: str = Field(default="Drop", description="Action name for dropping an inventory item.")
    interaction_affordance: ActionAffordance = Field(default_factory=lambda: ActionAffordance(
        surface="inventory", binding="source_item"))
    description: str = Field(
        default="Drop an item from inventory",
        description="Action description shown for inventory item drops.",
    )
    target_type: TargetType = Field(
        default=TargetType.POSITION_LOS,
        description="Drop targets a visible position.",
    )
    costs: List[Cost] = Field(
        default_factory=empty_list,
        description="No-cost action-economy payload for item drops.",
    )
    item_uuid: Optional[UUID] = Field(default=None, description="UUID of the item to drop (bound at creation)")
    charge_cost: int = Field(default=0, description="Dropping an item does not use its charges.")

    def discovery_selections(self, scan: ActorScan) -> Tuple[ActionSelection, ...]:
        """One row per inventory item the actor may drop."""
        entity = Entity.get(self.source_entity_uuid)
        own = self.current_selection()
        return tuple(replace(own, source_item_uuid=item.uuid) for item in entity.inventory.items.values()
                     if item.intrinsic_owner_uuid is None) if entity is not None else ()

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "item_uuid": selection.source_item_uuid}

    def get_discovery_display_name(self) -> str:
        item = BaseBlock.get(self.item_uuid) if self.item_uuid is not None else None
        return f"Drop ({item.name})" if item is not None else (self.name or "Drop")

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        return PhysicalAccess.BODY

    def get_range(self) -> Optional[Range]:
        return Range(type=RangeType.REACH, normal=5)

    def get_valid_positions(self) -> List[Tuple[int, int]]:
        """Return own and visible adjacent positions within 5 feet."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return []
        valid: List[Tuple[int, int]] = [entity.position]
        for pos in visible_positions(entity.senses.cells):
            if pos == entity.position:
                continue
            if entity.senses.get_feet_distance(pos) <= 5:
                valid.append(pos)
        return valid

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return "Entity not found"

        if self.item_uuid is None:
            return "No item specified"
        if not entity.inventory.has_item(self.item_uuid):
            return "Item not in inventory"

        if not selection.positions:
            return "No drop position specified"
        drop_position = selection.positions[0]

        if abs(drop_position[0] - entity.position[0]) > 1 or abs(drop_position[1] - entity.position[1]) > 1:
            return "Drop position too far (max 5ft)"

        return None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or self.item_uuid is None:
            return execution_event.cancel(status_message="Entity or item not found")

        dropped = entity.drop_item(
            self.item_uuid,
            position=self.end_position,
            parent_event=execution_event,
        )
        if dropped is None:
            return execution_event.cancel(status_message="Failed to drop item")

        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Dropped {dropped.name}"
        )


_CORE_STANDARD_ACTION_TYPES = (
        Move,
        Swim,
        Attack,
        Dash,
        Dodge,
        Disengage,
        DropConcentration,
        ShakeAwake,
        AllyHelp,
        HelpAttack,
        Hide,
        Search,
        Jump,
        Shove,
        PickUp,
)
CORE_STANDARD_ACTION_DECLARATIONS_BY_CLASS = MappingProxyType({
    action_type: get_content_declaration(action_type)
    for action_type in _CORE_STANDARD_ACTION_TYPES
})
CORE_STANDARD_ACTION_DECLARATIONS = tuple(
    CORE_STANDARD_ACTION_DECLARATIONS_BY_CLASS[action_type]
    for action_type in _CORE_STANDARD_ACTION_TYPES
)
