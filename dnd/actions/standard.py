"""Concrete action implementations for combat, movement, spells, and objects."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime

from dnd.core.base_actions import (
    ActionCategory,
    ActionOutcomeProfile,
    BaseAction,
    Cost,
    DamageRollProfile,
    OutcomeApplicationScope,
    OutcomeResolution,
    PositionDiscoveryContract,
    RESTRICTED_ACTION_TEMPLATE_SEPARATOR,
    SPELL_SLOT_TEMPLATE_SEPARATOR,
    SpellDiscoveryMetadata,
    TargetType,
    ActionTargetEffectProfile,
)
from dnd.core.events.action_events import (
    ActionEvent,
    BaseCost,
    JumpEvent,
    ShoveEvent,
    TraverseConnectorEvent,
    _copy_observer_map,
)
from dnd.core.values import ModifiableValue
from dnd.types.conditions import ConditionRemovalTrigger, DurationType
from dnd.core.modifiers import AdvantageModifier
from dnd.types.rolls import AdvantageStatus

from dnd.core.dice import DiceRoll
from dnd.types.rolls import AttackOutcome, RollType
from dnd.core.events.resolution_events import (
    RangeType,
    Range,
    Damage,
    DamageRollPacket,
    DamageRollResultEvent,
)
from dnd.core.events.events_registry import (
    Event,
    EventQueue,
    EventType,
    EventPhase,
)
from dnd.core.events.world_events import (
    StepMovementEvent,
    ForcedMovementEvent,
    SpatialChangeEvent,
    MovementTrajectory,
)
from dnd.core.events.check_events import (
    SkillCheckEvent,
)
from dnd.types.abilities import AbilityName, SkillName
from dnd.core.elevation import support_distance_feet
from dnd.types.equipment import WeaponSlot
from dnd.types.effects import EffectOrigin
from dnd.types.actions import CostType, RestrictedActionKind, spell_slot_cost_type
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
from dnd.types.behaviors import RuntimeBehaviorKind
from dnd.types.life import LifeState
from dnd.core.spell_execution import (
    SpellExecutionState,
    bind_spell_execution_lineage,
    current_spell_execution,
    spell_execution_scope,
)
from dnd.types.saving_throws import SavingThrowEffectTag
from dnd.core.action_execution import (
    MovementContinuationDecision,
    MovementProvocationPolicy,
    MovementStepBoundary,
    MovementTerminationReason,
    revalidate_after_committed_movement_step,
)
from dnd.types.rolls import DieSize
from dnd.types.damage import DamageType
from dnd.core.gridmap import GridMap, get_map
from dnd.core.positioning import PositionCommitError, PositionPublicationError
from dnd.core.traversal_connectors import (
    CONNECTOR_AUTHORED_ID_PATTERN,
    CONNECTOR_PRESENTATION_KEY_PATTERN,
    ConnectorActionCostType,
    ConnectorDestinationStatus,
    ConnectorProvocationPolicy,
    ConnectorTraversalDiscovery,
    TraversalConnector,
    TraversalConnectorCommand,
    TraversalConnectorEndpoint,
    TraversalConnectorKind,
)
from dnd.core.aoe import (
    Sphere,
    Cone,
    Line,
    Cube,
    Cylinder,
    snapshot_aoe_presentation_geometry,
)
from dnd.core.presentation_geometry import AoEPresentationGeometry
from dnd.core.naming import normalize_spell_id
from dnd.core.base_block import BaseBlock
from dnd.types.world import MovementMode
from dnd.types.world import LightLevel
from dnd.core.combat_log import (
    CombatLogEntry, CombatLogEntryType, ModifierBreakdown, DiceRollDisplay,
    DamageRollDisplay, AttackLogData, MovementLogData, SpellSaveLogData,
    format_attack_compact, format_attack_verbose, format_attack_detailed,
    md_color,
)
from pydantic import BaseModel, Field, StrictBool, StrictInt, TypeAdapter, model_validator
from typing import Any, Callable, ClassVar, Dict, Iterable, Mapping, Optional, List, Set, TypeVar, Tuple, Self, cast
from uuid import UUID, uuid4
from dnd.entities.entity import Entity, determine_attack_outcome
from dnd.blocks.action_economy import (
    ActionEconomyChannelCost,
    FixedCostCommitError,
    NamedResourceCost,
)
from dnd.blocks.base_item import (
    BaseItem,
)
from dnd.blocks.sensory import spatial_senses_system
from dnd.conditions import Dashing, Dodging, Disengaging, Prone, Hidden, Concentrating


_CoreActionDefinition = TypeVar("_CoreActionDefinition")


@dataclass(frozen=True, slots=True)
class IntrinsicAttackSource:
    """Cold damage facts for an attack supplied by the creature itself.

    Intrinsic attacks use the ordinary attack resolver and all of its event,
    modifier, reaction, and combat-log machinery.  They differ only in where
    the primary damage formula comes from: authored creature data rather than
    a temporarily impersonated equipment slot.
    """

    damage_die: DieSize
    dice_count: int
    damage_type: DamageType


def _step_intent_position_evidence(
    from_position: tuple[int, int],
    to_position: tuple[int, int],
) -> dict[str, set[str]]:
    """Freeze which observers perceived both endpoints when a step began."""
    return spatial_senses_system.position_observer_evidence(
        {from_position, to_position},
    )


@dataclass(frozen=True, slots=True)
class AttackDamageContribution:
    """Immutable action-owned damage added to an ordinary weapon attack."""

    dice_count: int
    damage_die: DieSize
    damage_type: DamageType
    flat_bonus: int = 0
    label: str = "Additional Attack Damage"


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
    actor: Any,
    weapon_slot: WeaponSlot,
    override_ability: Optional[AbilityName] = None,
) -> Optional[ActionOutcomeProfile]:
    """Build one actor-baseline weapon profile for all attack wrappers.

    Args:
        actor: Entity discovering the weapon attack.
        weapon_slot: Equipment slot used by the attack rule.
        override_ability: Optional ability selected by the action rule.

    Returns:
        Actor-owned stochastic data, or ``None`` for an invalid actor or slot.
    """
    if not isinstance(actor, Entity):
        return None
    baseline = actor.weapon_attack_outcome_baseline(
        weapon_slot,
        override_ability,
    )
    damage_rolls = actor.weapon_damage_outcome_baseline(
        weapon_slot,
        override_ability,
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


def validate_line_of_sight(declaration_event: PolymorphicActionEvent, source_entity_uuid: UUID) -> Optional[PolymorphicActionEvent]:
    """Validate that the action target is visible to the source entity.

    Args:
        declaration_event: Declaration event being validated.
        source_entity_uuid: Acting entity UUID.

    Returns:
        Updated declaration event, canceled event, or `None` if a subclass does.
    """
    source_entity = Entity.get(source_entity_uuid)
    if not source_entity:
        return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
    if not isinstance(source_entity, Entity):
        return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
    if not declaration_event.target_entity_uuid:
        return declaration_event.cancel(status_message=f"Target entity uuid not present for {declaration_event.name}")
    target_entity = Entity.get(declaration_event.target_entity_uuid)
    if not target_entity:
        return declaration_event.cancel(status_message=f"Target entity not found for {declaration_event.name}")
    if not isinstance(target_entity, Entity):
        return declaration_event.cancel(status_message=f"Target entity not found for {declaration_event.name}")

    contact = source_entity.senses.entities.get(target_entity.uuid)
    if contact is None or not contact.visual:
        return declaration_event.cancel(status_message=f"Target entity not in line of sight for {declaration_event.name}")
    return declaration_event.with_updates(
        status_message=f"Validated line of sight for {declaration_event.name}"
    )


MovePosition = Tuple[StrictInt, StrictInt]
MovePath = Tuple[MovePosition, ...]
_MOVE_POSITION_ADAPTER = TypeAdapter(MovePosition)
_MOVE_PATH_ADAPTER = TypeAdapter(MovePath)


def _normalize_move_position(position: object) -> MovePosition:
    """Normalize one JSON-compatible coordinate to an exact integer tuple."""
    return _MOVE_POSITION_ADAPTER.validate_python(position)


def _normalize_move_path(path: object) -> MovePath:
    """Normalize one JSON-compatible route to immutable exact coordinates."""
    return _MOVE_PATH_ADAPTER.validate_python(path)


def _path_intent_position_evidence(
    path: Iterable[tuple[int, int]],
) -> dict[str, set[str]]:
    """Freeze per-cell observers for disclosed nonoccupancy geometry."""
    return spatial_senses_system.position_observer_evidence(set(path))


def _unsettled_move_cancel_updates(
    event: "MovementEvent",
    source: Optional[Entity],
    reason: MovementTerminationReason,
) -> Dict[str, object]:
    """Return truthful zero-settlement facts for a pre-EFFECT rejection."""
    return {
        "end_position": event.start_position,
        "objective_end_position": (
            source.position if source is not None else event.start_position
        ),
        "path": (event.start_position,),
        "costs": [],
        "termination_reason": reason,
        "controller_revalidation": False,
        "controller_revalidation_reason": None,
        "outcome_code": f"movement.{reason.value}",
    }

# EVENT-MIGRATION BLOCKER: Move this class to the core event package only
# after cancellation validation stops reading the live Entity registry.
# The completed event must carry the authoritative position facts itself.
class MovementEvent(ActionEvent):
    """Event payload for path-based movement actions."""

    name: str = Field(default="Movement", description="Human-readable movement event label.")
    event_type: EventType = Field(default=EventType.MOVEMENT, description="Movement event category.")
    costs: List[BaseCost] = Field(default_factory=list, description="Serialized movement costs.")
    start_position: MovePosition = Field(description="Position occupied before movement starts.")
    end_position: MovePosition = Field(description="Accepted or settled voluntary endpoint.")
    requested_end_position: Optional[MovePosition] = Field(
        default=None,
        description="Destination requested before any partial-path termination.",
    )
    objective_end_position: Optional[MovePosition] = Field(
        default=None,
        description="Actual actor position after synchronous child displacement.",
    )
    path: Optional[MovePath] = Field(default=None, description="Grid path used by the movement.")
    movement_mode: MovementMode = Field(
        default=MovementMode.WALKING,
        description="Accepted transition and terrain-cost mode for this lineage.",
    )
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

    def model_copy(
        self,
        *,
        update: Optional[Mapping[str, Any]] = None,
        deep: bool = False,
    ) -> Self:
        """Copy one small movement proposal without aliasing causal evidence."""
        del deep
        copied = super().model_copy(update=update, deep=True)
        if type(copied.costs) is list:
            copied.costs = [
                BaseCost.model_validate(cost.model_dump())
                if isinstance(cost, BaseCost)
                else deepcopy(cost)
                for cost in copied.costs
            ]
        if copied.context is not None:
            copied.context = deepcopy(copied.context)
        return copied

    def validate_handler_result(self, result: Event) -> Event:
        """Freeze Move-family mechanics before a handler version is stored."""
        active_proposal = EventQueue.is_active_handler_proposal(result)
        safe_status = (
            result.status_message
            if type(result.status_message) is str or result.status_message is None
            else self.status_message
        )

        def queue_owned_updates() -> Dict[str, object]:
            return {
                "children_events": list(self.children_events),
                "lineage_children_events": list(self.lineage_children_events),
                "children_lineages": list(self.children_lineages),
                "identified_entity_observer_uuids": _copy_observer_map(
                    self.identified_entity_observer_uuids
                ),
                "located_entity_observer_uuids": _copy_observer_map(
                    self.located_entity_observer_uuids
                ),
                "located_position_observer_uuids": _copy_observer_map(
                    self.located_position_observer_uuids
                ),
            }

        def normalized_cancellation(status_message: str) -> MovementEvent:
            cancellation = self.invalid_handler_result_cancellation(
                result,
                status_message=status_message,
            )
            updates = {
                **_unsettled_move_cancel_updates(
                    self,
                    Entity.get(self.source_entity_uuid),
                    MovementTerminationReason.CANCELED,
                ),
                **queue_owned_updates(),
                "use_register": False if active_proposal else self.use_register,
            }
            return cast(MovementEvent, cancellation.model_copy(update=updates))

        def normalized_effect_stop(status_message: str) -> MovementEvent:
            candidate = self.invalid_handler_result_cancellation(
                result,
                status_message=status_message,
            )
            return cast(MovementEvent, candidate.model_copy(update={
                **queue_owned_updates(),
                "phase": EventPhase.EFFECT,
                "canceled": False,
                "canceled_from_phase": self.canceled_from_phase,
                "termination_reason": MovementTerminationReason.CANCELED,
                "outcome_code": "movement.canceled",
                "use_register": False if active_proposal else self.use_register,
            }))

        def reject(status_message: str) -> MovementEvent:
            if self.phase is EventPhase.EFFECT:
                return normalized_effect_stop(status_message)
            return normalized_cancellation(status_message)

        if type(result) is not MovementEvent:
            return reject("Movement handler returned an incompatible event type")
        if not (
            type(result.uuid) is UUID
            and type(result.timestamp) is datetime
            and type(result.modified) is bool
            and type(result.use_register) is bool
            and (
                result.status_message is None
                or type(result.status_message) is str
            )
        ):
            return reject("Movement handler returned malformed queue evidence")

        lifecycle_candidate = result
        if (
            not active_proposal
            and result.use_register is False
            and self.use_register is True
        ):
            lifecycle_candidate = result.model_copy(update={"use_register": True})
        if not self.handler_result_preserves_lifecycle(lifecycle_candidate):
            return reject("Movement handler changed lifecycle evidence")

        if result.canceled:
            return reject(safe_status or "Movement canceled by handler")

        if (
            type(result.costs) is not list
            or any(
                type(cost) is not BaseCost
                or type(cost.cost) is not int
                or type(cost.resource_cost) is not int
                or cost.cost < 0
                or cost.resource_cost < 0
                for cost in result.costs
            )
            or result.path is not None
            and (
                type(result.path) is not tuple
                or any(
                    type(position) is not tuple
                    or len(position) != 2
                    or any(type(coordinate) is not int for coordinate in position)
                    for position in result.path
                )
            )
        ):
            return reject("Movement handler returned invalid path or cost shapes")

        allowed_fields = {
            "uuid",
            "timestamp",
            "modified",
            "status_message",
        }
        if any(
            getattr(result, field_name) != getattr(self, field_name)
            for field_name in type(self).model_fields
            if field_name not in allowed_fields
            and field_name != "use_register"
        ):
            return reject("Movement handler changed immutable causal evidence")

        if (
            not active_proposal
            and result.uuid == self.uuid
            and result.timestamp == self.timestamp
            and result.modified == self.modified
            and safe_status == self.status_message
        ):
            return self

        result_uuid = result.uuid
        result_changed = (
            safe_status != self.status_message
            or result.timestamp != self.timestamp
        )
        if result_uuid == self.uuid and result_changed:
            result_uuid = uuid4()
        accepted = self.model_copy(update={
            **queue_owned_updates(),
            "uuid": result_uuid,
            "timestamp": result.timestamp,
            "modified": result.modified or result_changed,
            "status_message": safe_status,
            "use_register": False if active_proposal else self.use_register,
        })
        return cast(MovementEvent, accepted)

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return movement positions relevant to spatial handlers."""
        positions = {self.start_position}
        if self.phase is EventPhase.COMPLETION and self.path:
            positions.update(self.path)
        return positions

    def handler_result_stops_dispatch(self, result: Event) -> bool:
        """Keep an EFFECT stop marker monotonic within one handler dispatch."""
        return (
            super().handler_result_stops_dispatch(result)
            or isinstance(result, MovementEvent)
            and result.phase is EventPhase.EFFECT
            and result.termination_reason is MovementTerminationReason.CANCELED
        )

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this movement event.

        Uses self.* fields only - no external lookups. Entity name must be
        populated when the event is created.
        """
        source_name = self.source_entity_name or "Unknown"

        path = list(self.path or ())
        committed_steps: List[StepMovementEvent] = []
        for lineage_uuid in self.children_lineages:
            completed_step = next(
                (
                    event
                    for event in reversed(
                        EventQueue._events_by_lineage.get(lineage_uuid, [])
                    )
                    if type(event) is StepMovementEvent
                    and event.phase is EventPhase.COMPLETION
                    and event.committed
                ),
                None,
            )
            if completed_step is not None:
                committed_steps.append(completed_step)
        distance_feet = (
            sum(
                support_distance_feet(
                    step.from_position,
                    step.from_elevation_feet,
                    step.to_position,
                    step.to_elevation_feet,
                )
                for step in committed_steps
            )
            if committed_steps
            else (len(path) - 1) * 5 if len(path) > 1 else 0
        )

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
            movement_type="move",
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            start_position=self.start_position,
            end_position=self.end_position,
            path=path,
            distance_feet=distance_feet,
            movement_cost=movement_cost,
            requested_end_position=self.requested_end_position,
            objective_end_position=self.objective_end_position,
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
            data=data.model_dump(),
            success=True
        )


@dataclass(frozen=True, slots=True)
class _MoveStepSettlement:
    """One voluntary edge's authoritative settlement result."""

    committed: bool
    path: Tuple[Tuple[int, int], ...]
    movement_spent: int
    objective_position: Tuple[int, int]
    termination_reason: Optional[MovementTerminationReason]
    continuation_decision: MovementContinuationDecision
    continuation_reason: Optional[str]


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
    end_position: Optional[MovePosition] = Field(default=None, description="Requested movement destination.")
    path: Optional[MovePath] = Field(default=None, description="Resolved path from source to destination.")
    use_movement_cost: bool = Field(default=True, description="Whether movement costs are generated from the path.")
    prefer_safe: bool = Field(default=True, description="Whether a safe path is preferred when available.")
    movement_mode: MovementMode = Field(default=MovementMode.WALKING, description="Movement mode used for terrain costs and transitions.")

    def get_discovery_movement_mode(self) -> MovementMode:
        """Return the traversal mode owned by this movement action."""
        return self.movement_mode

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.end_position is not None and not self.template:
            self._setup_path()
            self._setup_costs_from_path()

    def _setup_costs_from_path(self) -> None:
        """Rebuild the movement cost from the resolved path and terrain."""
        self.costs = [
            cost for cost in self.costs if cost.cost_type != "movement"
        ]
        if self.path is None or not self.use_movement_cost:
            return
        grid = get_map()
        total_cost = 0
        source_entity = Entity.get(self.source_entity_uuid)
        ignore_terrain = (
            source_entity.ignore_difficult_terrain
            if isinstance(source_entity, Entity)
            else False
        )
        for from_position, to_position in zip(self.path, self.path[1:]):
            total_cost += self._get_step_cost_units(
                grid,
                from_position,
                to_position,
                source_entity if isinstance(source_entity, Entity) else None,
                ignore_terrain,
                self.movement_mode,
            )
        feet_cost = int(total_cost * 5)
        self.costs.append(Cost(
            name="Movement Cost",
            cost_type="movement",
            cost=feet_cost,
            evaluator=entity_action_economy_cost_evaluator,
        ))

    @staticmethod
    def _get_step_cost_units(
        grid: GridMap,
        from_position: Tuple[int, int],
        to_position: Tuple[int, int],
        source_entity: Optional[Entity],
        ignore_difficult_terrain: bool,
        movement_mode: MovementMode,
    ) -> float:
        """Return movement-cost units for one step in the accepted mode.

        Args:
            grid: Objective tile and edge owner.
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
            source_entity = Entity.get(self.source_entity_uuid)
            if source_entity is None or not isinstance(source_entity, Entity):
                return None
            if self.movement_mode == MovementMode.WALKING and self.prefer_safe and self.end_position in source_entity.senses.safe_paths:
                self.path = _normalize_move_path(
                    source_entity.senses.safe_paths[self.end_position]
                )
            elif self.movement_mode == MovementMode.WALKING and self.end_position in source_entity.senses.paths:
                self.path = _normalize_move_path(
                    source_entity.senses.paths[self.end_position]
                )
            elif self.movement_mode != MovementMode.WALKING:
                grid = get_map()
                _, paths = grid.compute_paths(
                    source_entity.position,
                    requesting_entity_uuid=source_entity.uuid,
                    movement_mode=self.movement_mode,
                    subjective=True,
                    collision_blocked=source_entity.senses.collision_blocked,
                    directional_collision_blocked=(
                        source_entity.senses.directional_collision_blocked
                    ),
                )
                discovered = paths.get(self.end_position)
                self.path = (
                    _normalize_move_path(discovered)
                    if discovered is not None
                    else None
                )

    def set_target_position(self, position: Tuple[int, int]) -> None:
        """Set target position and compute path/costs for validation.

        Overrides base implementation to also compute path and costs,
        so that pre_validate() can properly check movement affordability.
        """
        normalized_position = _normalize_move_position(position)
        self.path = None
        self.costs = [
            cost for cost in self.costs if cost.cost_type != "movement"
        ]

        super().set_target_position(normalized_position)

        self._setup_path()
        self._setup_costs_from_path()

    def instantiate(self, **overrides) -> "Move":
        """Create an executable Move instance from this template.

        Uses model_copy() to preserve object types. Path/costs are reset
        for recomputation based on new end_position.
        """
        if not self.template:
            raise ValueError("Can only instantiate from a template")

        if "movement_mode" in overrides:
            raise ValueError("Move-family templates own their movement mode")
        if "end_position" in overrides and overrides["end_position"] is not None:
            overrides["end_position"] = _normalize_move_position(
                overrides["end_position"]
            )
        explicit_path = overrides.pop("path", None)
        explicit_costs = overrides.pop("costs", self.costs)
        fixed_costs = [
            cost.model_copy(deep=True)
            for cost in explicit_costs
            if isinstance(cost, Cost) and cost.cost_type != "movement"
        ]
        update_dict: Dict[str, object] = {
            "uuid": uuid4(),
            "template": False,
            "use_register": False,
            "path": (
                _normalize_move_path(explicit_path)
                if explicit_path is not None
                else None
            ),
            "costs": fixed_costs,
        }
        update_dict.update(overrides)

        instance = self.model_copy(deep=True, update=update_dict)

        if instance.end_position is not None and instance.path is None:
            instance._setup_path()
        if instance.path is not None:
            instance._setup_costs_from_path()

        return instance

    @staticmethod
    def _validate_admitted_costs(event: MovementEvent) -> bool:
        """Return whether Move-family cost evidence has one closed shape."""
        movement_cost_count = 0
        for cost in event.costs:
            if (
                type(cost) is not BaseCost
                or type(cost.cost) is not int
                or type(cost.resource_cost) is not int
                or cost.cost < 0
                or cost.resource_cost < 0
                or (
                    cost.resource_name is None
                    and cost.resource_cost != 0
                )
                or (
                    cost.resource_name is not None
                    and (
                        type(cost.resource_name) is not str
                        or not cost.resource_name.strip()
                        or cost.resource_cost <= 0
                    )
                )
            ):
                return False
            if cost.cost_type == "movement":
                movement_cost_count += 1
                if cost.resource_name is not None or cost.resource_cost != 0:
                    return False
        return movement_cost_count <= 1

    @staticmethod
    def _validate_route(
        event: MovementEvent,
        source: Entity,
    ) -> bool:
        """Validate the exact disclosed, bounded route accepted for execution."""
        path = event.path
        if path is None or len(path) < 2:
            return False
        if (
            path[0] != source.position
            or path[0] != event.start_position
            or path[-1] != event.end_position
            or len(set(path)) != len(path)
            or len(path) - 1
            > source.action_economy.movement.normalized_score // 5
        ):
            return False
        disclosed_positions = set(source.senses.visible) | set(source.senses.seen)
        if any(position not in disclosed_positions for position in path):
            return False
        if (
            event.movement_mode is MovementMode.WALKING
            and event.end_position not in source.senses.paths
        ):
            return False
        if (
            event.movement_mode is not MovementMode.WALKING
            and event.end_position not in source.senses.visible
        ):
            return False
        grid = get_map()
        return all(
            grid.can_transition(
                from_position,
                to_position,
                source.uuid,
                event.movement_mode,
                subjective=True,
                collision_blocked=source.senses.collision_blocked,
                directional_collision_blocked=(
                    source.senses.directional_collision_blocked
                ),
            )
            for from_position, to_position in zip(path, path[1:])
        )

    def _validate_move_prerequisites(
        self,
        event: MovementEvent,
        source: Entity,
    ) -> Optional[MovementTerminationReason]:
        """Return a current Move-family content failure, if any."""
        del event, source
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

        end_position = _normalize_move_position(self.end_position)

        path = self.path
        if path is None and self.movement_mode == MovementMode.WALKING and end_position in source_entity.senses.paths:
            path = _normalize_move_path(source_entity.senses.paths[end_position])
        elif path is None and self.movement_mode != MovementMode.WALKING:
            grid = get_map()
            _, paths = grid.compute_paths(
                source_entity.position,
                requesting_entity_uuid=source_entity.uuid,
                movement_mode=self.movement_mode,
                subjective=True,
                collision_blocked=source_entity.senses.collision_blocked,
                directional_collision_blocked=(
                    source_entity.senses.directional_collision_blocked
                ),
            )
            discovered = paths.get(end_position)
            path = (
                _normalize_move_path(discovered)
                if discovered is not None
                else None
            )

        if path is not None:
            self.path = _normalize_move_path(path)
            self._setup_costs_from_path()
            path = self.path

        costs = [
            BaseCost.model_validate(cost.model_dump())
            for cost in self.effective_costs
        ]

        return MovementEvent(
            name=f"{self.name}",
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            start_position=source_entity.position,
            end_position=end_position,
            requested_end_position=end_position,
            objective_end_position=None,
            path=path,
            movement_mode=self.movement_mode,
            costs=costs,
            use_register=use_register,
            source_entity_name=source_entity.name,
        )

    def _validate(self, declaration_event: MovementEvent) -> MovementEvent:
        """Validate the movement action."""
        source = Entity.get(declaration_event.source_entity_uuid)
        if not isinstance(source, Entity):
            return declaration_event.cancel(
                status_message=f"Source entity not found for {declaration_event.name}",
                **_unsettled_move_cancel_updates(
                    declaration_event,
                    None,
                    MovementTerminationReason.ACTION_DENIED,
                ),
            )
        if not self._validate_admitted_costs(declaration_event):
            return declaration_event.cancel(
                status_message=f"Invalid costs for {declaration_event.name}",
                **_unsettled_move_cancel_updates(
                    declaration_event,
                    source,
                    MovementTerminationReason.INVALID_COST,
                ),
            )
        if not self._validate_route(declaration_event, source):
            return declaration_event.cancel(
                status_message=f"Invalid path for {declaration_event.name}",
                **_unsettled_move_cancel_updates(
                    declaration_event,
                    source,
                    MovementTerminationReason.INVALID_PATH,
                ),
            )
        prerequisite_failure = self._validate_move_prerequisites(
            declaration_event,
            source,
        )
        if prerequisite_failure is not None:
            return declaration_event.cancel(
                status_message=f"Movement prerequisites failed for {declaration_event.name}",
                **_unsettled_move_cancel_updates(
                    declaration_event,
                    source,
                    prerequisite_failure,
                ),
            )
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {declaration_event.name}",
        )

    @staticmethod
    def _objective_move_failure(
        source: Entity,
        expected_position: Tuple[int, int],
        *,
        after_committed_arrival: bool = False,
    ) -> Optional[MovementTerminationReason]:
        """Return the highest-priority current objective movement failure."""
        if not after_committed_arrival and source.position != expected_position:
            return MovementTerminationReason.POSITION_DIVERGED
        if source.health.life_state is LifeState.DEAD:
            return MovementTerminationReason.DEAD
        if not source.can_take_actions():
            return MovementTerminationReason.ACTION_DENIED
        if source.position != expected_position:
            return MovementTerminationReason.POSITION_DIVERGED
        return None

    @staticmethod
    def _publish_hidden_movement_collision(
        grid: GridMap,
        source: Entity,
        root_event: MovementEvent,
        from_position: Tuple[int, int],
        to_position: Tuple[int, int],
        movement_mode: MovementMode,
    ) -> None:
        """Retain collision memory and its existing spatial reveal fact."""
        if not grid.can_transition(
            from_position,
            to_position,
            source.uuid,
            movement_mode,
            subjective=True,
            collision_blocked=source.senses.collision_blocked,
            directional_collision_blocked=(
                source.senses.directional_collision_blocked
            ),
        ):
            return
        cell_blocked = not grid.is_walkable_for(
            to_position[0],
            to_position[1],
            source.uuid,
            movement_mode,
        )
        directions: List[str] = []
        from_tile = grid.get_tile(*from_position)
        if from_tile is not None:
            directions = list(from_tile.directions_toward(to_position))
        if cell_blocked:
            source.senses.collision_blocked.add(to_position)
        else:
            for direction in directions:
                source.senses.directional_collision_blocked.add(
                    (from_position, direction)
                )
        collision_event = SpatialChangeEvent.movement_collision(
            position=to_position,
            mover_uuid=source.uuid,
            parent_event=root_event.uuid,
            transition_from=from_position,
            transition_to=to_position,
            directional_position=from_position if directions else None,
            directional_directions=directions or None,
            directional_channels=(
                ["movement"]
                if directions and not cell_blocked
                else None
            ),
        )
        grid._fire_spatial_event(collision_event)

    @staticmethod
    def _accepted_step_cost_feet(
        grid: GridMap,
        from_position: Tuple[int, int],
        to_position: Tuple[int, int],
        source: Entity,
        movement_mode: MovementMode,
    ) -> Optional[int]:
        """Return one exact positive edge debit, or None for invalid evidence."""
        units = Move._get_step_cost_units(
            grid,
            from_position,
            to_position,
            source,
            source.ignore_difficult_terrain,
            movement_mode,
        )
        if isinstance(units, bool) or not isinstance(units, (int, float)):
            return None
        feet = units * 5
        if feet <= 0 or int(feet) != feet:
            return None
        return int(feet)

    @staticmethod
    def _settle_fixed_move_costs(
        source: Entity,
        admitted_costs: Tuple[BaseCost, ...],
    ) -> Optional[Tuple[BaseCost, ...]]:
        """Atomically re-admit and consume fixed Move-family costs."""
        fixed_costs = tuple(
            BaseCost.model_validate(cost.model_dump())
            for cost in admitted_costs
            if cost.cost_type != "movement"
        )
        economy_totals: Dict[CostType, int] = {}
        resource_totals: Dict[str, int] = {}
        for cost in fixed_costs:
            if cost.cost > 0:
                economy_totals[cost.cost_type] = (
                    economy_totals.get(cost.cost_type, 0) + cost.cost
                )
            if cost.resource_name is not None and cost.resource_cost > 0:
                resource_totals[cost.resource_name] = (
                    resource_totals.get(cost.resource_name, 0)
                    + cost.resource_cost
                )
        try:
            source.action_economy.commit_fixed_costs_without_dispatch(
                channel_costs=tuple(
                    ActionEconomyChannelCost(
                        cost_type=cost_type,
                        amount=amount,
                        name="Movement fixed costs",
                    )
                    for cost_type, amount in sorted(economy_totals.items())
                ),
                resource_costs=tuple(
                    NamedResourceCost(name=name, amount=amount)
                    for name, amount in sorted(resource_totals.items())
                ),
            )
        except FixedCostCommitError:
            return None
        return fixed_costs

    @staticmethod
    def _complete_accepted_move_effect(
        effect_event: MovementEvent,
        source: Entity,
        voluntary_path: Tuple[Tuple[int, int], ...],
        movement_spent: int,
        settled_fixed_costs: Tuple[BaseCost, ...],
        termination_reason: MovementTerminationReason,
        continuation_decision: MovementContinuationDecision = (
            MovementContinuationDecision.CONTINUE
        ),
        continuation_reason: Optional[str] = None,
    ) -> MovementEvent:
        """Publish one truthful terminal fact for an accepted EFFECT."""
        actual_costs = [
            *(
                BaseCost.model_validate(cost.model_dump())
                for cost in settled_fixed_costs
            ),
            BaseCost(
                name="Movement Cost",
                cost_type="movement",
                cost=movement_spent,
            ),
        ]
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            end_position=voluntary_path[-1],
            objective_end_position=_normalize_move_position(source.position),
            path=_normalize_move_path(voluntary_path),
            costs=actual_costs,
            termination_reason=termination_reason,
            controller_revalidation=(
                continuation_decision is MovementContinuationDecision.INTERRUPT
            ),
            controller_revalidation_reason=continuation_reason,
            outcome_code=f"movement.{termination_reason.value}",
            status_message=(
                f"Applied movement at {voluntary_path[-1]}"
                if termination_reason is MovementTerminationReason.COMPLETED
                else (
                    f"Partial movement for {effect_event.name}, stopped at "
                    f"{voluntary_path[-1]}"
                )
            ),
        )

    def _commit_move_step(
        self,
        *,
        root_event: MovementEvent,
        source: Entity,
        grid: GridMap,
        step_event: StepMovementEvent,
        voluntary_path: Tuple[Tuple[int, int], ...],
        movement_spent: int,
        source_event_cursor_start: int,
    ) -> _MoveStepSettlement:
        """Settle one accepted voluntary edge in its exact causal order."""
        from_position = step_event.from_position
        to_position = step_event.to_position
        failure = self._objective_move_failure(source, from_position)
        if failure is not None:
            step_event.phase_to(
                EventPhase.COMPLETION,
                committed=False,
                status_message=f"Movement step rejected before {to_position}",
            )
            return _MoveStepSettlement(
                committed=False,
                path=voluntary_path,
                movement_spent=movement_spent,
                objective_position=source.position,
                termination_reason=failure,
                continuation_decision=MovementContinuationDecision.CONTINUE,
                continuation_reason=None,
            )

        if not grid.can_transition(
            from_position,
            to_position,
            source.uuid,
            root_event.movement_mode,
        ):
            self._publish_hidden_movement_collision(
                grid,
                source,
                root_event,
                from_position,
                to_position,
                root_event.movement_mode,
            )
            step_event.phase_to(
                EventPhase.COMPLETION,
                committed=False,
                status_message=f"Movement step blocked before {to_position}",
            )
            return _MoveStepSettlement(
                committed=False,
                path=voluntary_path,
                movement_spent=movement_spent,
                objective_position=source.position,
                termination_reason=MovementTerminationReason.COLLISION,
                continuation_decision=MovementContinuationDecision.CONTINUE,
                continuation_reason=None,
            )

        step_cost_feet = self._accepted_step_cost_feet(
            grid,
            from_position,
            to_position,
            source,
            root_event.movement_mode,
        )
        if step_cost_feet is None:
            step_event.phase_to(
                EventPhase.COMPLETION,
                committed=False,
                status_message=f"Invalid movement cost before {to_position}",
            )
            return _MoveStepSettlement(
                committed=False,
                path=voluntary_path,
                movement_spent=movement_spent,
                objective_position=source.position,
                termination_reason=MovementTerminationReason.INVALID_COST,
                continuation_decision=MovementContinuationDecision.CONTINUE,
                continuation_reason=None,
            )
        if source.action_economy.movement.normalized_score < step_cost_feet:
            step_event.phase_to(
                EventPhase.COMPLETION,
                committed=False,
                movement_cost=step_cost_feet,
                status_message=f"Insufficient movement before {to_position}",
            )
            return _MoveStepSettlement(
                committed=False,
                path=voluntary_path,
                movement_spent=movement_spent,
                objective_position=source.position,
                termination_reason=MovementTerminationReason.INSUFFICIENT_MOVEMENT,
                continuation_decision=MovementContinuationDecision.CONTINUE,
                continuation_reason=None,
            )

        voluntary_observer_evidence = _step_intent_position_evidence(
            from_position,
            to_position,
        )
        root_effect_snapshot = root_event.model_copy(deep=True)
        step_effect_snapshot = step_event.model_copy(deep=True)
        arrival_event_start = EventQueue.event_cursor()
        movement_receipt = source.action_economy.consume_aggregate_with_receipt((
            ActionEconomyChannelCost(
                cost_type="movement",
                amount=step_cost_feet,
                name="Movement Cost",
            ),
        ))
        try:
            Entity.update_entity_position(
                source,
                to_position,
                parent_event=step_event.uuid,
            )
        except PositionCommitError:
            source.action_economy.undo_prevalidated_debit(movement_receipt)
            raise
        except PositionPublicationError:
            authoritative_root = EventQueue.get_event_by_uuid(
                root_effect_snapshot.uuid
            )
            authoritative_step = EventQueue.get_event_by_uuid(
                step_effect_snapshot.uuid
            )
            if type(authoritative_root) is MovementEvent:
                EventQueue._restore_guarded_handler_input(
                    authoritative_root,
                    root_effect_snapshot,
                    arrival_event_start,
                )
            if type(authoritative_step) is StepMovementEvent:
                EventQueue._restore_guarded_handler_input(
                    authoritative_step,
                    step_effect_snapshot,
                    arrival_event_start,
                )
            raise
        committed_path = (*voluntary_path, to_position)
        committed_spent = movement_spent + step_cost_feet

        authoritative_step = EventQueue.get_event_by_uuid(step_effect_snapshot.uuid)
        authoritative_root = EventQueue.get_event_by_uuid(root_effect_snapshot.uuid)
        if authoritative_root is not None:
            EventQueue._restore_guarded_handler_input(
                authoritative_root,
                root_effect_snapshot,
                arrival_event_start,
            )
        if authoritative_step is not None:
            EventQueue._restore_guarded_handler_input(
                authoritative_step,
                step_effect_snapshot,
                arrival_event_start,
            )
        if (
            type(authoritative_step) is not StepMovementEvent
            or authoritative_step.lineage_uuid != step_event.lineage_uuid
            or authoritative_step.phase is not EventPhase.EFFECT
        ):
            raise RuntimeError("Stored movement Step changed before arrival settlement")
        completion_source = authoritative_step.model_copy(update={
            "located_position_observer_uuids": voluntary_observer_evidence,
        })
        completed_step = completion_source.phase_to(
            EventPhase.COMPLETION,
            committed=True,
            movement_cost=step_cost_feet,
            status_message=f"Committed movement step to {to_position}",
        )
        stored_completion = EventQueue.get_event_by_uuid(completed_step.uuid)
        if (
            stored_completion is not completed_step
            or type(completed_step) is not StepMovementEvent
            or completed_step.phase is not EventPhase.COMPLETION
            or not completed_step.committed
        ):
            raise RuntimeError("Committed movement Step completion was not stored")

        objective_position = source.position
        continuation = revalidate_after_committed_movement_step(
            MovementStepBoundary(
                actor_uuid=source.uuid,
                movement_event_uuid=root_event.uuid,
                movement_lineage_uuid=root_event.lineage_uuid,
                step_event_uuid=completed_step.uuid,
                from_position=from_position,
                to_position=to_position,
                objective_position=objective_position,
                step_movement_cost=step_cost_feet,
                traversed_path=committed_path,
                movement_spent=committed_spent,
                movement_remaining=(
                    source.action_economy.movement.normalized_score
                ),
                source_event_cursor_start=source_event_cursor_start,
                source_event_cursor_end=EventQueue.event_cursor(),
            )
        )
        return _MoveStepSettlement(
            committed=True,
            path=committed_path,
            movement_spent=committed_spent,
            objective_position=objective_position,
            termination_reason=self._objective_move_failure(
                source,
                to_position,
                after_committed_arrival=True,
            ),
            continuation_decision=continuation.decision,
            continuation_reason=continuation.reason,
        )

    def _apply(self, execution_event: MovementEvent) -> MovementEvent:
        """Apply the accepted Move-family transaction one voluntary edge at a time."""
        source = Entity.get(execution_event.source_entity_uuid)
        if not isinstance(source, Entity):
            return execution_event.cancel(
                status_message=f"Source entity not found for {execution_event.name}",
                **_unsettled_move_cancel_updates(
                    execution_event,
                    None,
                    MovementTerminationReason.ACTION_DENIED,
                ),
            )

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applying movement for {execution_event.name}",
        )

        try:
            objective_failure = self._objective_move_failure(
                source,
                effect_event.start_position,
            )
            if objective_failure is not None:
                return self._complete_accepted_move_effect(
                    effect_event,
                    source,
                    (effect_event.start_position,),
                    0,
                    (),
                    objective_failure,
                )
            if (
                effect_event.termination_reason
                is MovementTerminationReason.CANCELED
            ):
                return self._complete_accepted_move_effect(
                    effect_event,
                    source,
                    (effect_event.start_position,),
                    0,
                    (),
                    MovementTerminationReason.CANCELED,
                )

            prerequisite_failure = self._validate_move_prerequisites(
                effect_event,
                source,
            )
            if prerequisite_failure is not None:
                return self._complete_accepted_move_effect(
                    effect_event,
                    source,
                    (effect_event.start_position,),
                    0,
                    (),
                    prerequisite_failure,
                )

            execution_path = tuple(effect_event.path or ())
            admitted_costs = tuple(effect_event.costs)
            if len(execution_path) < 2:
                return self._complete_accepted_move_effect(
                    effect_event,
                    source,
                    (effect_event.start_position,),
                    0,
                    (),
                    MovementTerminationReason.INVALID_PATH,
                )
            settled_fixed_costs = self._settle_fixed_move_costs(
                source,
                admitted_costs,
            )
            if settled_fixed_costs is None:
                return self._complete_accepted_move_effect(
                    effect_event,
                    source,
                    (effect_event.start_position,),
                    0,
                    (),
                    MovementTerminationReason.INVALID_COST,
                )

            grid = get_map()
            voluntary_path: Tuple[Tuple[int, int], ...] = (
                effect_event.start_position,
            )
            movement_spent = 0
            termination_reason = MovementTerminationReason.COMPLETED
            continuation_decision = MovementContinuationDecision.CONTINUE
            continuation_reason: Optional[str] = None

            for path_index, (from_position, to_position) in enumerate(
                zip(execution_path, execution_path[1:]),
                start=1,
            ):
                objective_failure = self._objective_move_failure(
                    source,
                    from_position,
                )
                if objective_failure is not None:
                    termination_reason = objective_failure
                    break
                if not grid.can_transition(
                    from_position,
                    to_position,
                    source.uuid,
                    effect_event.movement_mode,
                ):
                    self._publish_hidden_movement_collision(
                        grid,
                        source,
                        effect_event,
                        from_position,
                        to_position,
                        effect_event.movement_mode,
                    )
                    termination_reason = MovementTerminationReason.COLLISION
                    break

                provisional_cost = self._accepted_step_cost_feet(
                    grid,
                    from_position,
                    to_position,
                    source,
                    effect_event.movement_mode,
                )
                if provisional_cost is None:
                    termination_reason = MovementTerminationReason.INVALID_COST
                    break

                pre_step_root_snapshot = effect_event.model_copy(deep=True)
                step_source_cursor_start = EventQueue.event_cursor()
                provisional_step = StepMovementEvent(
                    source_entity_uuid=source.uuid,
                    source_entity_name=source.name,
                    from_position=from_position,
                    to_position=to_position,
                    path_index=path_index,
                    total_path_length=len(execution_path),
                    movement_cost=provisional_cost,
                    trajectory=effect_event.trajectory,
                    disclosed_path=(from_position, to_position),
                    from_elevation_feet=(
                        grid.get_support_elevation_feet(from_position)
                    ),
                    to_elevation_feet=(
                        grid.get_support_elevation_feet(to_position)
                    ),
                    committed=False,
                    located_position_observer_uuids=(
                        _step_intent_position_evidence(
                            from_position,
                            to_position,
                        )
                    ),
                    phase=EventPhase.EFFECT,
                    parent_event=effect_event.uuid,
                    use_register=False,
                )
                expected_lineage = provisional_step.lineage_uuid
                try:
                    processed_step = provisional_step.post(use_register=True)
                finally:
                    authoritative_root = EventQueue.get_event_by_uuid(
                        pre_step_root_snapshot.uuid
                    )
                    if type(authoritative_root) is MovementEvent:
                        EventQueue._restore_guarded_handler_input(
                            authoritative_root,
                            pre_step_root_snapshot,
                            step_source_cursor_start,
                        )
                if (
                    type(authoritative_root) is not MovementEvent
                    or authoritative_root.lineage_uuid
                    != pre_step_root_snapshot.lineage_uuid
                    or authoritative_root.phase is not EventPhase.EFFECT
                ):
                    raise RuntimeError(
                        "Stored Move root changed during Step settlement"
                    )
                effect_event = authoritative_root
                stored_step = EventQueue.get_event_by_uuid(processed_step.uuid)
                if (
                    stored_step is not processed_step
                    or type(processed_step) is not StepMovementEvent
                    or processed_step.lineage_uuid != expected_lineage
                    or processed_step.event_type is not EventType.STEP_MOVEMENT
                    or processed_step.use_register is not True
                    or processed_step.parent_event != effect_event.uuid
                    or processed_step.source_entity_uuid != source.uuid
                    or processed_step.from_position != from_position
                    or processed_step.to_position != to_position
                    or processed_step.path_index != path_index
                    or processed_step.total_path_length != len(execution_path)
                    or processed_step.trajectory is not effect_event.trajectory
                    or processed_step.movement_cost != provisional_cost
                    or processed_step.committed
                    or processed_step.phase
                    not in (EventPhase.EFFECT, EventPhase.CANCEL)
                ):
                    raise RuntimeError("Movement Step handler result escaped validation")

                if processed_step.canceled:
                    termination_reason = (
                        self._objective_move_failure(source, from_position)
                        or MovementTerminationReason.STEP_CANCELED
                    )
                    break

                settlement = self._commit_move_step(
                    root_event=effect_event,
                    source=source,
                    grid=grid,
                    step_event=processed_step,
                    voluntary_path=voluntary_path,
                    movement_spent=movement_spent,
                    source_event_cursor_start=step_source_cursor_start,
                )
                voluntary_path = settlement.path
                movement_spent = settlement.movement_spent
                continuation_decision = settlement.continuation_decision
                continuation_reason = settlement.continuation_reason

                if settlement.termination_reason is not None:
                    termination_reason = settlement.termination_reason
                    break
                if (
                    continuation_decision
                    is MovementContinuationDecision.INTERRUPT
                ):
                    termination_reason = (
                        MovementTerminationReason.COMPLETED
                        if (
                            to_position == effect_event.end_position
                            and to_position == execution_path[-1]
                        )
                        else MovementTerminationReason.SUBJECTIVE_REVALIDATION
                    )
                    break

            return self._complete_accepted_move_effect(
                effect_event,
                source,
                voluntary_path,
                movement_spent,
                settled_fixed_costs,
                termination_reason,
                continuation_decision,
                continuation_reason,
            )
        finally:
            remaining_path_distance = max(
                0,
                (source.action_economy.movement.normalized_score + 4) // 5,
            )
            source.materialize_navigation(
                max_distance=20,
                path_max_distance=remaining_path_distance,
            )

    def _apply_costs(
        self,
        completion_event: MovementEvent,
    ) -> Optional[MovementEvent]:
        """Return the already-settled terminal event without double payment."""
        return completion_event
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


# EVENT-MIGRATION BLOCKER: Move this class to the core event package only
# after combat-log generation stops reading live target AC and HP from Entity.
# Those resolution facts must be frozen on the event before it becomes cold.
class AttackEvent(ActionEvent):
    """Event payload for one weapon attack lifecycle."""

    name: str = Field(default="Attack", description="Human-readable attack event label.")
    costs: List[BaseCost] = Field(default_factory=list, description="Costs attached to this attack event.")
    weapon_slot: WeaponSlot = Field(description="Weapon slot used for the attack.")
    range: Optional[Range] = Field(default=None, description="Range band used by the attack.")
    is_long_range: bool = Field(default=False, description="Whether the target is beyond normal range.")
    is_threatened: bool = Field(default=False, description="Whether a hostile creature threatens the attacker.")
    attack_bonus: Optional[ModifiableValue] = Field(default=None, description="Attack-roll bonus used for this attack.")
    ac: Optional[ModifiableValue] = Field(default=None, description="Target armor class used for this attack.")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="Attack d20 roll after result handlers.")
    attack_outcome: Optional[AttackOutcome] = Field(default=None, description="Resolved attack outcome.")
    damages: Optional[List[Damage]] = Field(default=None, description="Damage packets used on hit.")
    damage_rolls: Optional[List[DiceRoll]] = Field(default=None, description="Damage rolls after result handlers.")
    event_type: EventType = Field(default=EventType.ATTACK, description="Event category for attacks.")
    weapon_name: Optional[str] = Field(default=None, description="Display name of the weapon used.")
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

        attack_breakdown: List[ModifierBreakdown] = []
        if self.attack_bonus:
            for mod in self.attack_bonus.get_breakdown():
                attack_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        advantage_breakdown: List[ModifierBreakdown] = []
        if self.attack_bonus:
            for mod in self.attack_bonus.get_full_advantage_breakdown():
                adv_val = mod.get('value', 'inactive')
                if adv_val == 'advantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=1, source=mod.get('source', 'self')
                    ))
                elif adv_val == 'disadvantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=-1, source=mod.get('source', 'self')
                    ))

        target_ac = 0
        if self.ac:
            target_ac = self.ac.normalized_score
        elif target_entity:
            target_ac = target_entity.ac_bonus().normalized_score

        ac_breakdown: List[ModifierBreakdown] = []
        if self.ac:
            for mod in self.ac.get_breakdown():
                ac_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

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

                damage_bonus_breakdown: List[ModifierBreakdown] = []
                if damage and damage.damage_bonus:
                    for mod in damage.damage_bonus.get_breakdown():
                        damage_bonus_breakdown.append(ModifierBreakdown(
                            name=mod.get('name', 'Unknown'),
                            value=mod.get('value', 0),
                            source=mod.get('source', 'self')
                        ))

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
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
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
            is_threatened=self.is_threatened
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
            data=data.model_dump(),
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
    additional_damage_types: Iterable[DamageType] = (),
) -> AttackEvent:
    """Snapshot one equipped or unarmed attack into a cold declaration.

    All ordinary weapon-attack actions use this boundary so a miss retains the
    same weapon name and damage-type metadata as a hit. Damage packets are
    resolved later and cannot be the source of presentation identity.
    """
    source_entity = Entity.get(source_entity_uuid)
    target_entity = (
        Entity.get(target_entity_uuid)
        if target_entity_uuid is not None
        else None
    )
    weapon_name: Optional[str] = None
    damage_types: List[DamageType] = []
    source_item_uuid: Optional[UUID] = None
    source_item_state = None
    if source_entity is not None:
        weapon_name, immutable_damage_types = (
            source_entity.equipment.snapshot_attack_event_metadata(
                weapon_slot,
            )
        )
        damage_types = list(immutable_damage_types)
        weapon = source_entity.equipment.get_weapon(weapon_slot)
        if weapon is not None:
            source_item_uuid = weapon.uuid
            source_item_state = weapon.to_item_state()

    damage_types = list(dict.fromkeys((
        *damage_types,
        *additional_damage_types,
    )))
    event_name = (
        f"{action_name} ({weapon_name})"
        if append_weapon_to_name and weapon_name is not None
        else action_name
    )
    return AttackEvent(
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
        damage_types=damage_types,
        source_item_uuid=source_item_uuid,
        source_item_state=source_item_state,
    )


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

    name: str = Field(default="Attack", description="Human-readable attack action name.")
    description: str = Field(default="Attack a target", description="Attack action description.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Attack targets one entity.")
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
    additional_damage_contributions: Tuple[AttackDamageContribution, ...] = Field(
        default=(),
        description=(
            "Immutable action-owned damage resolved with this weapon attack "
            "without mutating the attacker's shared equipment state."
        ),
    )

    def get_discovery_weapon_slot(self) -> Optional[WeaponSlot]:
        """Return the equipped slot whose metadata describes this attack."""
        return self.weapon_slot

    @model_validator(mode="after")
    def adjust_cost_for_off_hand(self) -> Self:
        """Select the ordinary off-hand cost unless the caller supplied one.

        Composite rules such as Multiattack deliberately construct child
        attacks with ``costs=[]`` because the parent action owns the cost.
        Reaction and restricted-action callers may likewise supply another
        explicit budget.  Slot-based defaulting must not overwrite either.
        """
        if (
            self.weapon_slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF)
            and "costs" not in self.model_fields_set
        ):
            self.costs = [Cost(name="Off-Hand Attack Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)]
        return self

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return the actor-baseline stochastic profile for this weapon attack."""
        profile = build_weapon_attack_outcome_profile(
            actor,
            self.weapon_slot,
            self.override_ability,
        )
        if profile is None or not isinstance(actor, Entity):
            return profile
        extra_damage_rolls = [
            DamageRollProfile(
                dice_count=contribution.dice_count,
                die_size=contribution.damage_die,
                flat_bonus=contribution.flat_bonus,
                damage_type=contribution.damage_type.value,
            )
            for contribution in self.additional_damage_contributions
        ]
        for condition in actor.active_conditions.values():
            for damage_profile in condition.get_action_damage_roll_profiles(self, actor):
                if isinstance(damage_profile, DamageRollProfile):
                    extra_damage_rolls.append(damage_profile)
        if not extra_damage_rolls:
            return profile
        return profile.model_copy(update={
            "damage_rolls": tuple(profile.damage_rolls) + tuple(extra_damage_rolls),
        })

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Return target-effect riders contributed by active actor traits."""
        if not isinstance(actor, Entity):
            return None
        profiles: list[ActionTargetEffectProfile] = []
        for condition in actor.active_conditions.values():
            profile = condition.get_action_target_effect_profile(self, actor)
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
    def validate_range(declaration_event: AttackEvent, source_entity_uuid: UUID) -> Optional[AttackEvent]:
        """Validate if the source entity and target entity are in range.

        Ranged attacks inside normal range are allowed without the long-range
        flag. Ranged attacks between normal and long range are allowed with
        `is_long_range=True`. Melee attacks require distance within weapon reach.

        Args:
            declaration_event: Attack declaration event to validate.
            source_entity_uuid: Attacking entity UUID.

        Returns:
            Updated declaration event, canceled event, or `None`.
        """
        source_entity = Entity.get(source_entity_uuid)
        if not source_entity:
            return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
        if not isinstance(source_entity, Entity):
            return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
        if not declaration_event.target_entity_uuid:
            return declaration_event.cancel(status_message=f"Target entity uuid not present for {declaration_event.name}")
        target_entity = Entity.get(declaration_event.target_entity_uuid)
        if not target_entity or not isinstance(target_entity, Entity):
            return declaration_event.cancel(status_message=f"Target entity not found for {declaration_event.name}")

        weapon_range = source_entity.get_weapon_range(declaration_event.weapon_slot)
        if weapon_range is None:
            return declaration_event.cancel(status_message=f"Weapon range not found for {declaration_event.name}")

        distance_feet = source_entity.distance_to_entity(target_entity)
        is_long_range = False

        if weapon_range.type == RangeType.RANGE:
            if distance_feet <= weapon_range.normal:
                pass
            elif weapon_range.long is not None and distance_feet <= weapon_range.long:
                is_long_range = True
            else:
                return declaration_event.cancel(status_message=f"Target entity not in range for {declaration_event.name}")

        elif weapon_range.type == RangeType.REACH:
            if distance_feet > weapon_range.normal:
                return declaration_event.cancel(status_message=f"Target entity not in reach for {declaration_event.name}")

        return declaration_event.with_updates(
            status_message=f"Validated range for {declaration_event.name}",
            range=weapon_range,
            is_long_range=is_long_range
        )

    @staticmethod
    def check_ranged_conditions(declaration_event: AttackEvent, source_entity_uuid: UUID) -> Optional[AttackEvent]:
        """Check conditions that affect ranged attacks.

        Sets `is_threatened=True` for ranged attacks made while an enemy
        threatens the attacker.

        Args:
            declaration_event: Attack declaration event to inspect.
            source_entity_uuid: Attacking entity UUID.

        Returns:
            Updated declaration event, canceled event, or `None`.
        """
        source_entity = Entity.get(source_entity_uuid)
        if not source_entity or not isinstance(source_entity, Entity):
            return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")

        is_threatened = False

        if declaration_event.range and declaration_event.range.type == RangeType.RANGE:
            is_threatened = source_entity.is_threatened()

        return declaration_event.with_updates(
            status_message=f"Checked ranged conditions for {declaration_event.name}",
            is_threatened=is_threatened
        )

    @staticmethod
    def attack_consequences(
        execution_event: AttackEvent,
        source_entity_uuid: UUID,
        *,
        intrinsic_source: Optional[IntrinsicAttackSource] = None,
        additional_damage_contributions: Tuple[
            AttackDamageContribution,
            ...,
        ] = (),
    ) -> Optional[AttackEvent]:
            """
            Resolve an attack roll, damage rolls, and damage application.

            Args:
                execution_event: Execution-phase attack event.
                source_entity_uuid: Attacking entity UUID.

            Returns:
                Completed attack event, canceled event, or `None`.
            """
            source_entity = Entity.get(source_entity_uuid)
            target_entity_uuid = execution_event.target_entity_uuid
            weapon_slot = execution_event.weapon_slot
            if not source_entity:
                return execution_event.cancel(status_message=f"Source entity not found for {execution_event.name}")
            if not isinstance(source_entity, Entity):
                return execution_event.cancel(status_message=f"Source entity not found for {execution_event.name}")
            if not target_entity_uuid:
                return execution_event.cancel(status_message=f"Target entity uuid not present for {execution_event.name}")
            target_entity = Entity.get(target_entity_uuid)
            if not target_entity:
                return execution_event.cancel(status_message=f"Target entity not found for {execution_event.name}")
            if not isinstance(target_entity, Entity):
                return execution_event.cancel(status_message=f"Target entity not found for {execution_event.name}")

            with (
                source_entity._temporary_target(target_entity_uuid),
                target_entity._temporary_target(source_entity_uuid),
            ):
                return Attack._resolve_attack_with_target_context(
                    execution_event=execution_event,
                    source_entity=source_entity,
                    target_entity=target_entity,
                    target_entity_uuid=target_entity_uuid,
                    weapon_slot=weapon_slot,
                    intrinsic_source=intrinsic_source,
                    additional_damage_contributions=(
                        additional_damage_contributions
                    ),
                )

    @staticmethod
    def _resolve_attack_with_target_context(
        *,
        execution_event: AttackEvent,
        source_entity: Entity,
        target_entity: Entity,
        target_entity_uuid: UUID,
        weapon_slot: WeaponSlot,
        intrinsic_source: Optional[IntrinsicAttackSource],
        additional_damage_contributions: Tuple[
            AttackDamageContribution,
            ...,
        ],
    ) -> AttackEvent:
            """Resolve one attack while both contextual targets are bound."""
            source_entity_uuid = source_entity.uuid
            override_ability = execution_event.override_ability
            if intrinsic_source is None:
                attack_bonus = source_entity.attack_bonus(
                    weapon_slot=weapon_slot,
                    target_entity_uuid=target_entity_uuid,
                    override_ability=override_ability,
                )
            else:
                attack_bonus = source_entity.intrinsic_attack_bonus(
                    range_type=(
                        execution_event.range.type
                        if execution_event.range is not None
                        else RangeType.REACH
                    ),
                    target_entity_uuid=target_entity_uuid,
                    override_ability=override_ability,
                )
            ac = target_entity.ac_bonus(source_entity.uuid)
            ac.set_from_target(attack_bonus)
            attack_bonus.set_from_target(ac)
            attack_bonus.set_event_lineage(execution_event.lineage_uuid)
            ac.set_event_lineage(execution_event.lineage_uuid)
            weapon = source_entity.equipment._get_weapon_by_slot(weapon_slot)
            attack_context: Dict[str, Any] = {
                "weapon_slot": weapon_slot.value,
                "weapon_name": (
                    execution_event.weapon_name
                    if intrinsic_source is not None
                    else weapon.name if weapon else "Unarmed"
                ),
                "range_type": execution_event.range.type.value if execution_event.range else None,
                "is_long_range": execution_event.is_long_range,
            }
            attack_bonus.set_context(attack_context)

            ranged_disadvantage_modifiers: List[UUID] = []
            is_ranged = execution_event.range is not None and execution_event.range.type == RangeType.RANGE

            if is_ranged and execution_event.is_long_range:
                modifier_uuid = attack_bonus.self_static.add_advantage_modifier(
                    AdvantageModifier(
                        name="Long Range",
                        value=AdvantageStatus.DISADVANTAGE,
                        source_entity_uuid=source_entity_uuid,
                        target_entity_uuid=target_entity_uuid
                    )
                )
                ranged_disadvantage_modifiers.append(modifier_uuid)

            if is_ranged and execution_event.is_threatened:
                modifier_uuid = attack_bonus.self_static.add_advantage_modifier(
                    AdvantageModifier(
                        name="Threatened (Ranged)",
                        value=AdvantageStatus.DISADVANTAGE,
                        source_entity_uuid=source_entity_uuid,
                        target_entity_uuid=target_entity_uuid
                    )
                )
                ranged_disadvantage_modifiers.append(modifier_uuid)

            attack_event = execution_event.phase_to(
                new_phase=EventPhase.EXECUTION,
                status_message="Rolling attack",
                attack_bonus=attack_bonus,
                ac=ac
            )

            if attack_event.canceled:
                attack_bonus.clear_context()
                return attack_event

            dice_roll = source_entity.roll_d20(
                attack_bonus,
                RollType.ATTACK,
                weapon_slot=weapon_slot,
                parent_event=attack_event.uuid,
            )
            crit_threshold = source_entity.get_crit_threshold(weapon_slot)
            attack_outcome = determine_attack_outcome(dice_roll, ac, crit_threshold)

            attack_event = attack_event.post(
                dice_roll=dice_roll,
                attack_outcome=attack_outcome,
                status_message=f"Attack rolled {dice_roll.total} and {attack_outcome}"
            )
            ac.reset_from_target()
            attack_bonus.reset_from_target()
            attack_bonus.clear_event_lineage()
            ac.clear_event_lineage()
            attack_bonus.clear_context()

            if attack_event.canceled:
                return attack_event

            if attack_event.attack_outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
                attack_event = attack_event.phase_to(
                    EventPhase.EFFECT,
                    status_message=f"Attack missed"
                )
                if not attack_event.canceled:
                    if intrinsic_source is None:
                        source_entity.equipment.activate_weapon_slot(weapon_slot)
                completion_event = attack_event.phase_to(
                    new_phase=EventPhase.COMPLETION,
                    status_message=f"Attack missed"
                )
                return completion_event

            if intrinsic_source is None:
                damages = source_entity.get_damages(
                    weapon_slot,
                    target_entity_uuid,
                    override_ability=override_ability,
                )
            else:
                damages = source_entity.get_intrinsic_attack_damages(
                    damage_die=intrinsic_source.damage_die,
                    dice_count=intrinsic_source.dice_count,
                    damage_type=intrinsic_source.damage_type,
                    range_type=(
                        execution_event.range.type
                        if execution_event.range is not None
                        else RangeType.REACH
                    ),
                    target_entity_uuid=target_entity_uuid,
                    override_ability=override_ability,
                )
            damages.extend(
                Damage(
                    name=contribution.label,
                    source_entity_uuid=source_entity_uuid,
                    target_entity_uuid=target_entity_uuid,
                    damage_dice=contribution.damage_die,
                    dice_numbers=contribution.dice_count,
                    damage_bonus=ModifiableValue.create(
                        source_entity_uuid=source_entity_uuid,
                        base_value=contribution.flat_bonus,
                        value_name=f"{contribution.label} Bonus",
                    ),
                    damage_type=contribution.damage_type,
                )
                for contribution in additional_damage_contributions
            )
            attack_event = attack_event.phase_to(
                EventPhase.EFFECT,
                is_last=False,
                status_message=f"Damages: {[(damage.dice_numbers,damage.damage_dice,damage.damage_bonus.normalized_score if damage.damage_bonus else 0,damage.damage_type) for damage in damages]}",
                damages=damages
            )

            if attack_event.canceled:
                return attack_event
            if intrinsic_source is None:
                source_entity.equipment.activate_weapon_slot(weapon_slot)

            if attack_event.attack_outcome is not None and attack_event.attack_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
                crit_extra_dice = source_entity.get_crit_extra_dice(weapon_slot)
                damage_packets = []
                for damage in damages:
                    dice = damage.get_dice(attack_outcome=attack_event.attack_outcome, crit_extra_dice=crit_extra_dice)
                    roll = dice.roll
                    damage_packets.append(
                        DamageRollPacket(
                            damage=damage,
                            original_roll=roll,
                            final_roll=roll,
                        )
                    )

                damage_roll_event = DamageRollResultEvent(
                    source_entity_uuid=source_entity.uuid,
                    target_entity_uuid=target_entity.uuid,
                    source_entity_name=source_entity.name,
                    target_entity_name=target_entity.name,
                    weapon_slot=weapon_slot,
                    attack_outcome=attack_event.attack_outcome,
                    damage_packets=damage_packets,
                    parent_event=attack_event.uuid,
                    phase=EventPhase.DECLARATION
                )

                damage_roll_event = damage_roll_event.phase_to(
                    EventPhase.EFFECT,
                    status_message="Damage dice rolled"
                )

                damage_rolls = [
                    packet.final_roll
                    for packet in damage_roll_event.damage_packets
                ]

                damage_roll_event.phase_to(EventPhase.COMPLETION)
                damages = [
                    packet.damage
                    for packet in damage_roll_event.damage_packets
                ]
                total_damage = sum(roll.total for roll in damage_rolls)

                actual_damage = target_entity.receive_damage(
                    amount=total_damage,
                    damage_type=damages[0].damage_type,
                    source_entity_uuid=source_entity.uuid,
                    damage_rolls=damage_rolls,
                    damages=damages,
                    parent_event=attack_event.uuid,
                    critical_hit=execution_event.attack_outcome == AttackOutcome.CRIT
                )

                attack_event = attack_event.phase_to(
                    new_phase=EventPhase.EFFECT,
                    is_first=False,
                    damage_rolls=damage_rolls,
                    total_damage=actual_damage,
                    status_message=f"Damages taken: {[damage.total for damage in damage_rolls]}"
                )
            else:
                damage_rolls = None

            completion_event = attack_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message="Attack completed",
                damage_rolls=damage_rolls,
            )
            return completion_event

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for the attack action."""
        return create_weapon_attack_declaration_event(
            action_name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            weapon_slot=self.weapon_slot,
            costs=self.effective_costs,
            parent_event=parent_event,
            use_register=use_register,
            override_ability=self.override_ability,
            additional_damage_types=(
                contribution.damage_type
                for contribution in self.additional_damage_contributions
            ),
        )

    def _validate(self, declaration_event: AttackEvent) -> Optional[AttackEvent]:
        """Validate range, line of sight, and ranged-attack conditions."""
        range_validated_event = Attack.validate_range(declaration_event, self.source_entity_uuid)
        if range_validated_event is None:
            return declaration_event.cancel(status_message=f"Range validation returned None for {self.name}")
        elif range_validated_event.canceled:
            return range_validated_event

        line_of_sight_validated_event = validate_line_of_sight(range_validated_event, self.source_entity_uuid)
        if line_of_sight_validated_event is None:
            return declaration_event.cancel(status_message=f"Line of sight validation returned None for {self.name}")
        elif line_of_sight_validated_event.canceled:
            return line_of_sight_validated_event

        ranged_conditions_event = Attack.check_ranged_conditions(line_of_sight_validated_event, self.source_entity_uuid)
        if ranged_conditions_event is None:
            return declaration_event.cancel(status_message=f"Ranged conditions check returned None for {self.name}")
        elif ranged_conditions_event.canceled:
            return ranged_conditions_event

        return ranged_conditions_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Attack validated for {self.name}"
        )

    def _apply(self, execution_event: AttackEvent) -> Optional[AttackEvent]:
        """Apply the attack action."""
        return Attack.attack_consequences(
            execution_event,
            self.source_entity_uuid,
            additional_damage_contributions=self.additional_damage_contributions,
        )

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

    name: str = Field(default="Dash", description="Human-readable dash action name.")
    description: str = Field(default="Gain extra movement equal to your speed", description="Dash action description.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Dash targets self")
    restricted_action_kinds: ClassVar[frozenset[RestrictedActionKind]] = (
        frozenset({RestrictedActionKind.DASH})
    )
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Dash Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Dash.")

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
            new_phase=EventPhase.COMPLETION,
            status_message=f"Applied Dashing - gained {current_speed}ft extra movement"
        )

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

    name: str = Field(default="Dodge", description="Human-readable dodge action name.")
    description: str = Field(default="Attackers have disadvantage, advantage on DEX saves", description="Dodge action description.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Dodge targets self")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Dodge Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Dodge.")

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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message="Applied Dodging - attackers have disadvantage"
        )

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

    name: str = Field(default="Disengage", description="Human-readable disengage action name.")
    description: str = Field(default="Movement doesn't provoke opportunity attacks", description="Disengage action description.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Disengage targets self")
    restricted_action_kinds: ClassVar[frozenset[RestrictedActionKind]] = (
        frozenset({RestrictedActionKind.DISENGAGE})
    )
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Disengage Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Disengage.")

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
            new_phase=EventPhase.COMPLETION,
            status_message="Applied Disengaging - movement won't provoke OAs"
        )

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
        default_factory=list,
        description="No-cost payload because dropping concentration is free.",
    )
    target_spell: Optional[str] = Field(default=None, description="Specific spell to drop (multi-slot). None = drop all.")

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if "Concentrating" not in entity.active_conditions:
            return declaration_event.cancel(status_message="Not concentrating on any spell")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

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
                    conc.drop_slot(slot_uuid, parent_event=execution_event)
        else:
            entity.remove_condition("Concentrating", parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Dropped concentration{' on ' + self.target_spell if self.target_spell else ''}"
        )

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

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        """Validate an adjacent other creature with a wakeable condition."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not source or not target:
            return declaration_event.cancel(status_message="Source or target not found")
        if source.uuid == target.uuid:
            return declaration_event.cancel(status_message="Cannot shake yourself awake")
        if source.distance_to_entity(target) > 5:
            return declaration_event.cancel(status_message="Target is not adjacent")
        if not self._wakeable_condition_uuids(target):
            return declaration_event.cancel(
                status_message="Target has no condition that can be shaken off"
            )
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply external assistance to every condition that declares support."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
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
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} wakes up"
        )

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
    name: str = Field(default="Hide", description="Human-readable hide action name.")
    description: str = Field(default="Attempt to hide (Stealth check)", description="Player-facing hide action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Hide targets self")
    restricted_action_kinds: ClassVar[frozenset[RestrictedActionKind]] = (
        frozenset({RestrictedActionKind.HIDE})
    )
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Hide Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid when taking the Hide action.")

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        grid = get_map()
        tile = grid.get_tile(*entity.position)
        if tile:
            light = tile.resolved_light_level
            if light == LightLevel.VERY_BRIGHT:
                return declaration_event.cancel(
                    status_message="Cannot hide in very bright light"
                )
            if light.value <= LightLevel.DIM_LIGHT.value:
                return declaration_event.phase_to(
                    new_phase=EventPhase.EXECUTION,
                    status_message=f"Validated {self.name}"
                )

        subscribers = grid.get_subscribers_at(entity.position)
        for sub_uuid in subscribers:
            if sub_uuid == entity.uuid:
                continue
            sub = Entity.get(sub_uuid)
            if sub and isinstance(sub, Entity) and entity.is_enemy(sub):
                if (
                    (contact := sub.senses.entities.get(entity.uuid)) is not None
                    and contact.visual
                    and not entity.is_obscured_by_larger_creature_from(sub)
                ):
                    return declaration_event.cancel(
                        status_message="Cannot hide - visible to enemies"
                    )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")

        skill_bonus = entity.skill_bonus(target_entity_uuid=None, skill_name=SkillName.STEALTH)
        stealth_roll = entity.roll_d20(skill_bonus, RollType.CHECK, skill_name=SkillName.STEALTH, parent_event=execution_event.uuid)
        stealth_result = stealth_roll.total

        check_event = SkillCheckEvent(
            name="Stealth Check",
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            skill_name=SkillName.STEALTH,
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
            new_phase=EventPhase.COMPLETION,
            status_message=f"Applied Hidden (Stealth DC {stealth_result})"
        )

class StandUp(BaseAction):
    """
    Stand up from prone - costs half your movement speed.

    Removes the Prone condition. Can only be used while Prone.
    """
    name: str = Field(default="Stand Up", description="Human-readable stand-up action name.")
    description: str = Field(default="Stand up from prone", description="Player-facing stand-up action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Stand Up targets self")

    def model_post_init(self, __context: Any) -> None:
        """Set movement cost to half of the acting entity's base movement."""
        super().model_post_init(__context)
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

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if "Prone" not in entity.active_conditions:
            return declaration_event.cancel(status_message="Not prone - cannot stand up")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        entity.remove_condition("Prone", parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message="Stood up from prone"
        )

class DropProne(BaseAction):
    """
    Drop prone - free action (no cost).

    Applies the Prone condition. Can only be used while not Prone.
    """
    name: str = Field(default="Drop Prone", description="Human-readable drop-prone action name.")
    description: str = Field(default="Drop to the ground", description="Player-facing drop-prone action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Drop Prone targets self")
    costs: List[Cost] = Field(default_factory=list, description="Drop Prone has no action economy cost.")

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if "Prone" in entity.active_conditions:
            return declaration_event.cancel(status_message="Already prone")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

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
            new_phase=EventPhase.COMPLETION,
            status_message="Dropped prone"
        )


@_core_action_identity(
    content_id="action.traverse_connector",
    display_name="Traverse Connector",
    description="Use an authored connector from the current support cell.",
    source_anchor="Engine-authored atomic traversal connector rule",
    sort_order=35,
)
class TraverseConnector(BaseAction):
    """One endpoint-indexed SELF action shared by every connector kind."""

    name: str = "Traverse Connector"
    description: str = "Traverse the selected connector"
    target_type: TargetType = TargetType.SELF
    action_category: ActionCategory = ActionCategory.MOVEMENT
    costs: List[Cost] = Field(default_factory=list)
    connector_traversal: Optional[ConnectorTraversalDiscovery] = None

    @staticmethod
    def _oriented_connector(
        connector: TraversalConnector,
        source_position: Tuple[int, int],
    ) -> Optional[
        Tuple[TraversalConnectorEndpoint, TraversalConnectorEndpoint]
    ]:
        first, second = connector.endpoints
        if source_position == first.position:
            return first, second
        if source_position == second.position and connector.bidirectional:
            return second, first
        return None

    @staticmethod
    def _variant_costs(
        connector: TraversalConnector,
    ) -> List[Cost]:
        costs: List[Cost] = []
        if connector.action_cost_type is not None:
            costs.append(Cost(
                name="Connector Action Cost",
                cost_type=connector.action_cost_type.value,
                cost=connector.action_cost_amount,
                evaluator=entity_action_economy_cost_evaluator,
            ))
        if connector.movement_cost_feet > 0:
            costs.append(Cost(
                name="Connector Movement Cost",
                cost_type="movement",
                cost=connector.movement_cost_feet,
                evaluator=entity_action_economy_cost_evaluator,
            ))
        return costs

    @staticmethod
    def _destination_status(
        entity: Entity,
        destination: Tuple[int, int],
    ) -> ConnectorDestinationStatus:
        if not entity.senses.visible.get(destination, False):
            return ConnectorDestinationStatus.UNKNOWN
        grid = get_map()
        if grid.is_walkable_for(
            destination[0],
            destination[1],
            entity.uuid,
            subjective=True,
        ):
            return ConnectorDestinationStatus.KNOWN_CLEAR
        return ConnectorDestinationStatus.KNOWN_BLOCKED

    def get_discovery_variants(self, entity: Any) -> List[BaseAction]:
        """Return one typed variant per enabled direction at this endpoint."""
        if not isinstance(entity, Entity):
            return []
        variants: List[BaseAction] = []
        for connector in get_map().get_connectors_at(entity.position):
            if not connector.enabled:
                continue
            oriented = self._oriented_connector(connector, entity.position)
            if oriented is None:
                continue
            source_endpoint, destination_endpoint = oriented
            command = TraversalConnectorCommand(
                connector_uuid=connector.uuid,
                connector_revision=connector.revision,
                connector_digest=connector.objective_digest,
                source_position=source_endpoint.position,
                destination_position=destination_endpoint.position,
            )
            discovery = ConnectorTraversalDiscovery(
                command=command,
                authored_id=connector.authored_id,
                kind=connector.kind,
                presentation_key=connector.presentation_key,
                source_elevation_feet=source_endpoint.elevation_feet,
                destination_elevation_feet=destination_endpoint.elevation_feet,
                movement_cost_feet=connector.movement_cost_feet,
                action_cost_type=connector.action_cost_type,
                action_cost_amount=connector.action_cost_amount,
                bidirectional=connector.bidirectional,
                provocation_policy=connector.provocation_policy,
                destination_status=self._destination_status(
                    entity,
                    destination_endpoint.position,
                ),
            )
            variants.append(self.model_copy(deep=True, update={
                "uuid": uuid4(),
                "template": False,
                "use_register": False,
                "connector_traversal": discovery,
                "costs": self._variant_costs(connector),
            }))
        return variants

    def get_discovery_template_name(self) -> str:
        """Return a collision-free command token, never a parsed label."""
        discovery = self.connector_traversal
        if discovery is None:
            return self.name
        command = discovery.command
        source = command.source_position
        destination = command.destination_position
        return (
            f"Traverse Connector__connector_{command.connector_uuid}_"
            f"{command.connector_revision}_{command.connector_digest}_"
            f"{source[0]}_{source[1]}_{destination[0]}_{destination[1]}"
        )

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
        event: TraverseConnectorEvent,
        source: Entity,
    ) -> Optional[TraversalConnector]:
        grid = get_map()
        connector = grid.get_connector(event.connector_uuid)
        if (
            connector is None
            or not grid.connector_supports_are_current(connector)
            or not connector.enabled
            or connector.authored_id != event.connector_authored_id
            or connector.kind is not event.connector_kind
            or connector.presentation_key != event.connector_presentation_key
            or connector.revision != event.connector_revision
            or connector.objective_digest != event.connector_digest
            or connector.movement_cost_feet != event.movement_cost_feet
            or connector.action_cost_type is not event.action_cost_type
            or connector.action_cost_amount != event.action_cost_amount
            or connector.provocation_policy is not event.connector_provocation_policy
            or connector.bidirectional is not event.connector_bidirectional
            or source.position != event.start_position
        ):
            return None
        oriented = self._oriented_connector(connector, event.start_position)
        if oriented is None:
            return None
        first, second = oriented
        if (
            second.position != event.requested_end_position
            or first.elevation_feet != event.start_elevation_feet
            or second.elevation_feet != event.requested_end_elevation_feet
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
            name=self.name,
            description=self.description,
            source_entity_uuid=source.uuid,
            target_entity_uuid=source.uuid,
            source_entity_name=source.name,
            parent_event=parent_event.uuid if parent_event is not None else None,
            costs=[BaseCost.model_validate(cost.model_dump()) for cost in self.effective_costs],
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

    def _validate(
        self,
        declaration_event: TraverseConnectorEvent,
    ) -> TraverseConnectorEvent:
        source = Entity.get(self.source_entity_uuid)
        if (
            source is None
            or source.health.life_state is not LifeState.ALIVE
            or not source.can_take_actions()
            or self._current_connector(declaration_event, source) is None
        ):
            return declaration_event.cancel(
                status_message="Connector traversal admission is no longer valid"
            )
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Connector traversal validated",
        )

    @staticmethod
    def _completion(
        effect: TraverseConnectorEvent,
        source: Entity,
        reason: MovementTerminationReason,
        *,
        committed: bool,
        status_message: str,
    ) -> TraverseConnectorEvent:
        destination = effect.requested_end_position if committed else effect.start_position
        end_elevation = (
            effect.requested_end_elevation_feet
            if committed
            else effect.start_elevation_feet
        )
        return cast(TraverseConnectorEvent, effect.phase_to(
            EventPhase.COMPLETION,
            end_position=destination,
            objective_end_position=source.position,
            end_elevation_feet=end_elevation,
            termination_reason=reason,
            outcome_code=f"movement.{reason.value}",
            status_message=status_message,
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
        connector = self._current_connector(effect, source)
        destination = effect.requested_end_position
        grid = get_map()
        if connector is None:
            return self._completion(
                effect, source, MovementTerminationReason.INVALID_PATH,
                committed=False, status_message="Connector is stale or unavailable",
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

        def current_stop_reason() -> Optional[MovementTerminationReason]:
            if source.position != effect.start_position:
                return MovementTerminationReason.POSITION_DIVERGED
            if source.health.life_state is not LifeState.ALIVE:
                return MovementTerminationReason.DEAD
            if not source.can_take_actions():
                return MovementTerminationReason.ACTION_DENIED
            if self._current_connector(effect, source) is None:
                return MovementTerminationReason.INVALID_PATH
            if not grid.is_walkable_for(
                destination[0], destination[1], source.uuid
            ):
                return MovementTerminationReason.COLLISION
            if not all(
                source.action_economy.can_afford(cost.cost_type, cost.amount)
                for cost in channel_costs
            ):
                return MovementTerminationReason.INSUFFICIENT_MOVEMENT
            return None

        reason = current_stop_reason()
        if reason is not None:
            return self._completion(
                effect,
                source,
                reason,
                committed=False,
                status_message=f"Connector transfer stopped: {reason.value}",
            )
        pre_step_root_snapshot = effect.model_copy(deep=True)
        step_event_start = EventQueue.event_cursor()

        def restore_root_after_step_handlers() -> TraverseConnectorEvent:
            authoritative_root = EventQueue.get_event_by_uuid(
                pre_step_root_snapshot.uuid
            )
            if type(authoritative_root) is TraverseConnectorEvent:
                EventQueue._restore_guarded_handler_input(
                    authoritative_root,
                    pre_step_root_snapshot,
                    step_event_start,
                )
            if (
                type(authoritative_root) is not TraverseConnectorEvent
                or authoritative_root.lineage_uuid
                != pre_step_root_snapshot.lineage_uuid
                or authoritative_root.phase is not EventPhase.EFFECT
            ):
                raise RuntimeError(
                    "Stored connector root changed during Step settlement"
                )
            return authoritative_root

        step = StepMovementEvent(
            source_entity_uuid=source.uuid,
            source_entity_name=source.name,
            from_position=effect.start_position,
            to_position=destination,
            path_index=1,
            total_path_length=2,
            movement_cost=effect.movement_cost_feet,
            trajectory=MovementTrajectory.CONNECTOR_TRANSFER,
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
            located_position_observer_uuids=_step_intent_position_evidence(
                effect.start_position, destination
            ),
            parent_event=effect.uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
        try:
            step = EventQueue.publish_declaration(step)
        finally:
            effect = restore_root_after_step_handlers()
        if step.canceled:
            return self._completion(
                effect, source, MovementTerminationReason.STEP_CANCELED,
                committed=False, status_message="Connector Step declaration canceled",
            )
        try:
            step = step.phase_to(EventPhase.EXECUTION)
        finally:
            effect = restore_root_after_step_handlers()
        if step.canceled:
            return self._completion(
                effect, source, MovementTerminationReason.STEP_CANCELED,
                committed=False, status_message="Connector Step execution canceled",
            )
        try:
            step = step.phase_to(EventPhase.EFFECT)
        finally:
            effect = restore_root_after_step_handlers()
        if step.canceled or step.outcome_code == "movement.step_stopped":
            if not step.canceled:
                step.phase_to(EventPhase.COMPLETION, committed=False)
            return self._completion(
                effect, source, MovementTerminationReason.STEP_CANCELED,
                committed=False, status_message="Connector Step stopped",
            )

        reason = current_stop_reason()
        if reason is not None:
            step.phase_to(
                EventPhase.COMPLETION,
                committed=False,
                status_message=f"Connector transfer stopped: {reason.value}",
            )
            return self._completion(
                effect, source, reason,
                committed=False,
                status_message=f"Connector transfer stopped: {reason.value}",
            )

        receipt = source.action_economy.consume_aggregate_with_receipt(
            tuple(channel_costs)
        )
        root_effect_snapshot = effect.model_copy(deep=True)
        step_effect_snapshot = step.model_copy(deep=True)
        arrival_event_start = EventQueue.event_cursor()
        try:
            Entity.update_entity_position(
                source,
                destination,
                parent_event=step.uuid,
            )
        except PositionCommitError:
            source.action_economy.undo_prevalidated_debit(receipt)
            raise
        except PositionPublicationError:
            authoritative_root = EventQueue.get_event_by_uuid(
                root_effect_snapshot.uuid
            )
            authoritative_step = EventQueue.get_event_by_uuid(
                step_effect_snapshot.uuid
            )
            if type(authoritative_root) is TraverseConnectorEvent:
                EventQueue._restore_guarded_handler_input(
                    authoritative_root,
                    root_effect_snapshot,
                    arrival_event_start,
                )
            if type(authoritative_step) is StepMovementEvent:
                EventQueue._restore_guarded_handler_input(
                    authoritative_step,
                    step_effect_snapshot,
                    arrival_event_start,
                )
            raise
        authoritative_root = EventQueue.get_event_by_uuid(root_effect_snapshot.uuid)
        authoritative_step = EventQueue.get_event_by_uuid(step_effect_snapshot.uuid)
        if authoritative_root is not None:
            EventQueue._restore_guarded_handler_input(
                authoritative_root, root_effect_snapshot, arrival_event_start
            )
            effect = cast(TraverseConnectorEvent, authoritative_root)
        if authoritative_step is not None:
            EventQueue._restore_guarded_handler_input(
                authoritative_step, step_effect_snapshot, arrival_event_start
            )
            step = cast(StepMovementEvent, authoritative_step)
        step.phase_to(
            EventPhase.COMPLETION,
            committed=True,
            status_message=f"Connector transfer arrived at {destination}",
        )
        return self._completion(
            effect,
            source,
            MovementTerminationReason.COMPLETED,
            committed=True,
            status_message=f"Connector transfer completed at {destination}",
        )

    def _apply_costs(
        self,
        completion_event: TraverseConnectorEvent,
    ) -> TraverseConnectorEvent:
        """Connector execution already committed its accepted aggregate costs."""
        return completion_event


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
        distance = entity.distance_to_position(self.end_position)
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

        base = 15 + max(0, entity.ability_scores.strength.modifier) * 5
        additive = entity.jump_distance_additive.normalized_score
        multiplier = entity.jump_distance_multiplier.normalized_score
        total_range = (base + additive) * multiplier
        return Range(type=RangeType.REACH, normal=total_range)

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
        movement_available = entity.action_economy.movement.normalized_score
        grid = get_map()
        valid: List[Tuple[int, int]] = []

        for pos, is_visible in entity.senses.visible.items():
            if not is_visible:
                continue
            if pos == entity.senses.position:
                continue

            distance = entity.distance_to_position(pos)
            if distance > max_range:
                continue

            if distance > movement_available:
                continue

            if not grid.is_walkable_for(pos[0], pos[1], entity.uuid):
                continue

            if not grid.raycast_clear(
                entity.position,
                pos,
                channel="propagation",
                requester_uuid=entity.uuid,
            ):
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
        grid = get_map()
        start_elevation = grid.get_support_elevation_feet(source_entity.position)
        try:
            requested_elevation = grid.get_support_elevation_feet(end_position)
            distance = source_entity.distance_to_position(end_position)
        except ValueError:
            return None

        line_path = self.get_disclosed_movement_path(
            source_entity.position,
            end_position,
        )
        if line_path is None:
            return None

        return JumpEvent(
            name=self.name,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            start_position=source_entity.position,
            requested_end_position=end_position,
            end_position=source_entity.position,
            objective_end_position=source_entity.position,
            start_elevation_feet=start_elevation,
            requested_end_elevation_feet=requested_elevation,
            end_elevation_feet=start_elevation,
            jump_distance=int(distance),
            path=tuple(line_path),
            costs=[
                BaseCost.model_validate(cost.model_dump())
                for cost in self.effective_costs
            ],
            use_register=use_register,
            source_entity_name=source_entity.name
        )

    def _validate(self, declaration_event: JumpEvent) -> JumpEvent:
        """Validate the jump action."""
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return declaration_event.cancel(status_message="Entity not found")

        end_pos = declaration_event.requested_end_position
        if end_pos is None:
            return declaration_event.cancel(status_message="Jump landing is missing")
        grid = get_map()

        if source_entity.position != declaration_event.start_position:
            return declaration_event.cancel(status_message="Jumper left the declared takeoff")

        try:
            start_elevation = grid.get_support_elevation_feet(
                declaration_event.start_position
            )
            end_elevation = grid.get_support_elevation_feet(end_pos)
            _fixed, _resources, movement_cost = self._split_admitted_jump_costs(
                declaration_event.costs
            )
        except (TypeError, ValueError) as exc:
            return declaration_event.cancel(status_message=str(exc))

        disclosed_path = tuple(
            self.get_disclosed_movement_path(
                declaration_event.start_position,
                end_pos,
            )
            or ()
        )
        if (
            start_elevation != declaration_event.start_elevation_feet
            or end_elevation != declaration_event.requested_end_elevation_feet
            or disclosed_path != declaration_event.path
            or movement_cost != declaration_event.jump_distance
        ):
            return declaration_event.cancel(
                status_message="Jump admission evidence is no longer coherent"
            )

        if end_pos not in source_entity.senses.visible or not source_entity.senses.visible[end_pos]:
            return declaration_event.cancel(status_message=f"Position {end_pos} not visible")

        action_range = self.get_range()
        max_range = action_range.normal if action_range else 15
        distance = source_entity.distance_to_position(end_pos)
        if distance > max_range:
            return declaration_event.cancel(status_message=f"Position {end_pos} out of jump range ({distance}ft > {max_range}ft)")

        if not grid.is_walkable_for(end_pos[0], end_pos[1], source_entity.uuid):
            return declaration_event.cancel(status_message=f"Position {end_pos} not walkable or occupied")

        if not grid.raycast_clear(
            source_entity.position,
            end_pos,
            channel="propagation",
            requester_uuid=source_entity.uuid,
        ):
            return declaration_event.cancel(status_message=f"Path to {end_pos} is blocked")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated jump to {end_pos}"
        )

    @staticmethod
    def _split_admitted_jump_costs(
        costs: Iterable[BaseCost],
    ) -> tuple[
        tuple[ActionEconomyChannelCost, ...],
        tuple[NamedResourceCost, ...],
        int,
    ]:
        """Normalize disjoint fixed and movement facts from accepted evidence."""
        fixed_channels: list[ActionEconomyChannelCost] = []
        resources: list[NamedResourceCost] = []
        movement_cost = 0
        for cost in costs:
            if (
                type(cost) is not BaseCost
                or type(cost.cost) is not int
                or type(cost.resource_cost) is not int
                or cost.cost < 0
                or cost.resource_cost < 0
            ):
                raise ValueError("Jump costs must be exact nonnegative integers")
            if cost.resource_name is not None and (
                type(cost.resource_name) is not str or not cost.resource_name
            ):
                raise ValueError("Jump resource names must be nonempty strings")
            if cost.resource_cost > 0 and cost.resource_name is None:
                raise ValueError("Positive Jump resource cost requires a name")

            if cost.cost_type == "movement":
                movement_cost += cost.cost
            elif cost.cost > 0:
                fixed_channels.append(ActionEconomyChannelCost(
                    cost_type=cost.cost_type,
                    amount=cost.cost,
                    name=cost.name,
                ))
            if cost.resource_cost > 0:
                resources.append(NamedResourceCost(
                    name=cast(str, cost.resource_name),
                    amount=cost.resource_cost,
                ))
        return tuple(fixed_channels), tuple(resources), movement_cost

    @staticmethod
    def _fixed_jump_costs_are_affordable(
        source: Entity,
        channel_costs: tuple[ActionEconomyChannelCost, ...],
        resource_costs: tuple[NamedResourceCost, ...],
    ) -> bool:
        """Check aggregate fixed costs before the no-dispatch commit begins."""
        channel_totals: dict[CostType, int] = {}
        for cost in channel_costs:
            channel_totals[cost.cost_type] = (
                channel_totals.get(cost.cost_type, 0) + cost.amount
            )
        resource_totals: dict[str, int] = {}
        for cost in resource_costs:
            resource_totals[cost.name] = (
                resource_totals.get(cost.name, 0) + cost.amount
            )
        return all(
            source.action_economy.can_afford(cost_type, amount)
            for cost_type, amount in channel_totals.items()
        ) and all(
            source.action_economy.can_afford_resource(name, amount)
            for name, amount in resource_totals.items()
        )

    @staticmethod
    def _publish_jump_effect_stop(
        effect_event: JumpEvent,
        source: Entity,
        reason: MovementTerminationReason,
        status_message: str,
        *,
        fixed_costs_committed: bool,
    ) -> JumpEvent:
        """Store one handler-free accepted-EFFECT settlement marker."""
        stopped = effect_event.model_copy(update={
            "uuid": uuid4(),
            "timestamp": datetime.now(UTC),
            "modified": True,
            "status_message": status_message,
            "termination_reason": reason,
            "end_position": effect_event.start_position,
            "objective_end_position": source.position,
            "end_elevation_feet": effect_event.start_elevation_feet,
            "fixed_costs_committed": fixed_costs_committed,
            "movement_spent": 0,
            "outcome_code": f"movement.{reason.value}",
            "use_register": False,
        })
        return cast(JumpEvent, EventQueue.publish_preflighted(stopped))

    @classmethod
    def _complete_stopped_jump(
        cls,
        effect_event: JumpEvent,
        source: Entity,
        reason: MovementTerminationReason,
        status_message: str,
        *,
        fixed_costs_committed: bool,
    ) -> JumpEvent:
        """Publish the stop marker and final truthful Jump completion."""
        stopped = cls._publish_jump_effect_stop(
            effect_event,
            source,
            reason,
            status_message,
            fixed_costs_committed=fixed_costs_committed,
        )
        return cast(JumpEvent, stopped.phase_to(
            EventPhase.COMPLETION,
            status_message=status_message,
        ))

    def _landing_is_still_valid(
        self,
        event: JumpEvent,
        source: Entity,
        grid: GridMap,
    ) -> bool:
        """Revalidate exact landing, arc, elevation, range, and cost truth."""
        landing = event.requested_end_position
        if landing is None or source.position != event.start_position:
            return False
        try:
            landing_elevation = grid.get_support_elevation_feet(landing)
            start_elevation = grid.get_support_elevation_feet(event.start_position)
            distance = source.distance_to_position(landing)
        except ValueError:
            return False
        jump_range = self.get_range()
        disclosed_path = tuple(
            self.get_disclosed_movement_path(event.start_position, landing) or ()
        )
        return (
            start_elevation == event.start_elevation_feet
            and landing_elevation == event.requested_end_elevation_feet
            and distance == event.jump_distance
            and disclosed_path == event.path
            and jump_range is not None
            and distance <= jump_range.normal
            and grid.is_walkable_for(landing[0], landing[1], source.uuid)
            and grid.raycast_clear(
                event.start_position,
                landing,
                channel="propagation",
                requester_uuid=source.uuid,
            )
        )

    def _apply(self, execution_event: JumpEvent) -> JumpEvent:
        """Settle one atomic direct arc after takeoff-only reactions."""
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return execution_event.cancel(status_message="Entity not found")

        grid = get_map()
        try:
            effect_event = execution_event.phase_to(
                new_phase=EventPhase.EFFECT,
                status_message=f"Jumping to {execution_event.end_position}"
            )
            if effect_event.canceled:
                return effect_event

            try:
                fixed_channels, resource_costs, movement_cost = (
                    self._split_admitted_jump_costs(effect_event.costs)
                )
            except (TypeError, ValueError) as exc:
                return self._complete_stopped_jump(
                    effect_event,
                    source_entity,
                    MovementTerminationReason.INVALID_COST,
                    str(exc),
                    fixed_costs_committed=False,
                )
            if (
                movement_cost != effect_event.jump_distance
                or not self._fixed_jump_costs_are_affordable(
                    source_entity,
                    fixed_channels,
                    resource_costs,
                )
            ):
                return self._complete_stopped_jump(
                    effect_event,
                    source_entity,
                    MovementTerminationReason.INVALID_COST,
                    "Accepted Jump costs are no longer affordable",
                    fixed_costs_committed=False,
                )

            source_entity.action_economy.commit_fixed_costs_without_dispatch(
                channel_costs=fixed_channels,
                resource_costs=resource_costs,
            )

            landing = effect_event.requested_end_position
            disclosed_path = effect_event.path or ()
            if landing is None or not disclosed_path:
                return self._complete_stopped_jump(
                    effect_event,
                    source_entity,
                    MovementTerminationReason.INVALID_PATH,
                    "Jump landing or disclosed arc is missing",
                    fixed_costs_committed=True,
                )

            pre_step_root_snapshot = effect_event.model_copy(deep=True)
            step_event_start = EventQueue.event_cursor()

            def restore_root_after_step_handlers() -> JumpEvent:
                authoritative_root = EventQueue.get_event_by_uuid(
                    pre_step_root_snapshot.uuid
                )
                if type(authoritative_root) is JumpEvent:
                    EventQueue._restore_guarded_handler_input(
                        authoritative_root,
                        pre_step_root_snapshot,
                        step_event_start,
                    )
                if (
                    type(authoritative_root) is not JumpEvent
                    or authoritative_root.lineage_uuid
                    != pre_step_root_snapshot.lineage_uuid
                    or authoritative_root.phase is not EventPhase.EFFECT
                ):
                    raise RuntimeError(
                        "Stored Jump root changed during Step settlement"
                    )
                return authoritative_root

            step_declaration = StepMovementEvent(
                source_entity_uuid=self.source_entity_uuid,
                source_entity_name=source_entity.name,
                from_position=effect_event.start_position,
                to_position=landing,
                path_index=1,
                total_path_length=len(disclosed_path),
                movement_cost=effect_event.jump_distance,
                trajectory=MovementTrajectory.DIRECT_ARC,
                disclosed_path=disclosed_path,
                from_elevation_feet=effect_event.start_elevation_feet,
                to_elevation_feet=effect_event.requested_end_elevation_feet,
                provocation_policy=MovementProvocationPolicy.ORDINARY_EXIT,
                committed=False,
                located_position_observer_uuids=(
                    _path_intent_position_evidence(disclosed_path)
                ),
                phase=EventPhase.DECLARATION,
                parent_event=effect_event.uuid,
                use_register=False,
            )
            try:
                processed_step = EventQueue.publish_declaration(step_declaration)
            finally:
                effect_event = restore_root_after_step_handlers()
            if processed_step.canceled:
                return self._complete_stopped_jump(
                    effect_event,
                    source_entity,
                    MovementTerminationReason.STEP_CANCELED,
                    processed_step.status_message or "Jump step declaration canceled",
                    fixed_costs_committed=True,
                )
            try:
                processed_step = processed_step.phase_to(EventPhase.EXECUTION)
            finally:
                effect_event = restore_root_after_step_handlers()
            if processed_step.canceled:
                return self._complete_stopped_jump(
                    effect_event,
                    source_entity,
                    MovementTerminationReason.STEP_CANCELED,
                    processed_step.status_message or "Jump step execution canceled",
                    fixed_costs_committed=True,
                )
            try:
                processed_step = processed_step.phase_to(EventPhase.EFFECT)
            finally:
                effect_event = restore_root_after_step_handlers()
            if (
                processed_step.canceled
                or processed_step.outcome_code == "movement.step_stopped"
            ):
                if not processed_step.canceled:
                    processed_step.phase_to(
                        EventPhase.COMPLETION,
                        committed=False,
                    )
                return self._complete_stopped_jump(
                    effect_event,
                    source_entity,
                    MovementTerminationReason.STEP_CANCELED,
                    processed_step.status_message or "Jump step effect stopped",
                    fixed_costs_committed=True,
                )

            if source_entity.position != effect_event.start_position:
                reason = MovementTerminationReason.POSITION_DIVERGED
            elif source_entity.health.life_state is not LifeState.ALIVE:
                reason = MovementTerminationReason.DEAD
            elif not source_entity.can_take_actions():
                reason = MovementTerminationReason.ACTION_DENIED
            elif not self._landing_is_still_valid(effect_event, source_entity, grid):
                reason = MovementTerminationReason.INVALID_PATH
            elif not source_entity.action_economy.can_afford(
                "movement",
                effect_event.jump_distance,
            ):
                reason = MovementTerminationReason.INSUFFICIENT_MOVEMENT
            else:
                reason = None

            if reason is not None:
                processed_step.phase_to(
                    EventPhase.COMPLETION,
                    committed=False,
                    status_message=f"Jump landing stopped: {reason.value}",
                )
                return self._complete_stopped_jump(
                    effect_event,
                    source_entity,
                    reason,
                    f"Jump landing stopped: {reason.value}",
                    fixed_costs_committed=True,
                )

            movement_receipt = source_entity.action_economy.consume_aggregate_with_receipt((
                ActionEconomyChannelCost(
                    cost_type="movement",
                    amount=effect_event.jump_distance,
                    name="Jump Movement Cost",
                ),
            ))
            root_effect_snapshot = effect_event.model_copy(deep=True)
            step_effect_snapshot = processed_step.model_copy(deep=True)
            arrival_event_start = EventQueue.event_cursor()
            try:
                Entity.update_entity_position(
                    source_entity,
                    landing,
                    parent_event=processed_step.uuid,
                )
            except PositionCommitError:
                source_entity.action_economy.undo_prevalidated_debit(
                    movement_receipt
                )
                raise
            except PositionPublicationError:
                authoritative_root = EventQueue.get_event_by_uuid(
                    root_effect_snapshot.uuid
                )
                authoritative_step = EventQueue.get_event_by_uuid(
                    step_effect_snapshot.uuid
                )
                if type(authoritative_root) is JumpEvent:
                    EventQueue._restore_guarded_handler_input(
                        authoritative_root,
                        root_effect_snapshot,
                        arrival_event_start,
                    )
                if type(authoritative_step) is StepMovementEvent:
                    EventQueue._restore_guarded_handler_input(
                        authoritative_step,
                        step_effect_snapshot,
                        arrival_event_start,
                    )
                raise

            authoritative_root = EventQueue.get_event_by_uuid(
                root_effect_snapshot.uuid
            )
            authoritative_step = EventQueue.get_event_by_uuid(
                step_effect_snapshot.uuid
            )
            if authoritative_root is not None:
                EventQueue._restore_guarded_handler_input(
                    authoritative_root,
                    root_effect_snapshot,
                    arrival_event_start,
                )
                effect_event = cast(JumpEvent, authoritative_root)
            if authoritative_step is not None:
                EventQueue._restore_guarded_handler_input(
                    authoritative_step,
                    step_effect_snapshot,
                    arrival_event_start,
                )
                processed_step = cast(StepMovementEvent, authoritative_step)

            processed_step.phase_to(
                EventPhase.COMPLETION,
                committed=True,
                status_message=f"Jump landed at {landing}",
            )
            return cast(JumpEvent, effect_event.phase_to(
                EventPhase.COMPLETION,
                end_position=landing,
                objective_end_position=source_entity.position,
                end_elevation_feet=effect_event.requested_end_elevation_feet,
                movement_spent=effect_event.jump_distance,
                fixed_costs_committed=True,
                termination_reason=MovementTerminationReason.COMPLETED,
                outcome_code="movement.completed",
                status_message=f"Jumped to {landing}",
            ))
        finally:
            source_entity.materialize_navigation(max_distance=20)

    def _apply_costs(self, completion_event: JumpEvent) -> JumpEvent:
        """Return the transaction-settled Jump without paying it twice."""
        return completion_event


POUNDS_PER_KILOGRAM = 2.2046226218487757
BG3_SHOVE_WEIGHT_MULTIPLIER_KG = 12.0
BG3_SHOVE_CURVE_CONSTANT = 65.0
BG3_SHOVE_MIN_DISTANCE_METERS = 1.0
BG3_SHOVE_MAX_DISTANCE_METERS = 6.0
BG3_GRID_CELL_METERS = 1.5
ENGINE_GRID_CELL_FEET = 5


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

    name: str = Field(default="Shove", description="Human-readable shove action name.")
    description: str = Field(default="Push an adjacent enemy", description="Shove action description.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Shove targets one entity.")
    knock_prone: bool = Field(default=False, description="Whether shove knocks prone instead of pushing.")
    include_allies: bool = Field(default=True, description="Whether allies are valid shove targets.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Shove Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Shove.")

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
        current = start
        cells_to_move = distance_feet // 5
        actual_cells = 0
        blocked = False
        blocked_by: Optional[str] = None

        for _ in range(cells_to_move):
            next_pos = (current[0] + direction[0], current[1] + direction[1])

            if not grid.can_transition(current, next_pos, target_uuid):
                blocked = True
                blocked_by = grid.identify_blocker_at(next_pos, target_uuid)
                break

            current = next_pos
            actual_cells += 1

        return current, actual_cells * 5, blocked, blocked_by

    @staticmethod
    def calculate_forced_movement_path(
        start: Tuple[int, int],
        direction: Tuple[int, int],
        distance_feet: int
    ) -> List[Tuple[int, int]]:
        """Return every traversed cell for a straight forced displacement.

        Args:
            start: Position before forced movement begins.
            direction: Unit displacement direction as `(dx, dy)`.
            distance_feet: Distance to traverse in feet.

        Returns:
            Ordered destination cells, one per 5-foot transition.
        """
        path: List[Tuple[int, int]] = []
        current = start

        for _ in range(distance_feet // 5):
            current = (current[0] + direction[0], current[1] + direction[1])
            path.append(current)

        return path

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

    def _validate(self, declaration_event: ShoveEvent) -> ShoveEvent:
        """Validate the shove action."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(declaration_event.target_entity_uuid) if declaration_event.target_entity_uuid else None

        if not source or not target:
            return declaration_event.cancel(status_message="Entity not found")

        distance = source.distance_to_entity(target)
        if distance > 5:
            return declaration_event.cancel(status_message=f"Target not adjacent ({distance}ft)")

        if target.weight > declaration_event.max_shove_weight:
            return declaration_event.cancel(
                status_message=f"Target too heavy ({target.weight}lbs > {declaration_event.max_shove_weight}lbs)"
            )

        contact = source.senses.entities.get(target.uuid)
        if contact is None or not contact.visual:
            return declaration_event.cancel(status_message="Target not visible")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Shove validated"
        )

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
            athletics_bonus = source.skill_bonus(target.uuid, SkillName.ATHLETICS)

            passive_athletics = target.passive_skill(SkillName.ATHLETICS)
            passive_acrobatics = target.passive_skill(SkillName.ACROBATICS)

            if passive_athletics >= passive_acrobatics:
                target_passive = passive_athletics
                target_skill = "athletics"
            else:
                target_passive = passive_acrobatics
                target_skill = "acrobatics"

            dice_roll = source.roll_d20(
                athletics_bonus,
                RollType.CHECK,
                skill_name=SkillName.ATHLETICS,
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
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message="Shove failed - target resisted"
            )

        if self.knock_prone:
            prone_condition = Prone(
                source_entity_uuid=source.uuid,
                target_entity_uuid=target.uuid
            )
            target.add_condition(prone_condition, parent_event=execution_event)

            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
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
            movement_path = self.calculate_forced_movement_path(target.position, direction, actual_dist)
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
                parent_event=execution_event.uuid,
                use_register=False,
            )

            moved_cells = 0
            interrupted_by_condition = False

            forced_event = EventQueue.publish_declaration(forced_event)
            if not forced_event.canceled:
                forced_event = forced_event.phase_to(EventPhase.EXECUTION)
            if not forced_event.canceled:
                forced_event = forced_event.phase_to(EventPhase.EFFECT)
            if not forced_event.canceled:
                for next_pos in movement_path:
                    if not get_map().can_transition(
                        target.position,
                        next_pos,
                        target.uuid,
                    ):
                        blocked = True
                        blocked_by = get_map().identify_blocker_at(
                            next_pos,
                            target.uuid,
                        ) or "blocked path"
                        break
                    Entity.update_entity_position(
                        target,
                        next_pos,
                        parent_event=forced_event.uuid,
                    )
                    moved_cells += 1

                    if not target.can_take_actions():
                        interrupted_by_condition = True
                        break

            push_distance = moved_cells * 5
            final_pos = target.position

            if interrupted_by_condition:
                blocked = False
                blocked_by = None

            if not forced_event.canceled:
                forced_event.phase_to(
                    EventPhase.COMPLETION,
                    end_position=final_pos,
                    actual_distance=push_distance,
                    blocked_by_obstacle=blocked,
                    blocked_by=blocked_by,
                    status_message=(
                        f"Forced movement interrupted at {final_pos}"
                        if interrupted_by_condition
                        else f"Forced movement completed at {final_pos}"
                    )
                )

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            push_distance=push_distance,
            push_direction=push_direction,
            end_position=final_pos,
            blocked_by=blocked_by,
            status_message=f"Shoved {target.name} {push_distance}ft" + (f" (blocked by {blocked_by})" if blocked and blocked_by else " (blocked)" if blocked else "")
        )

# EVENT-MIGRATION BLOCKER: Move this class to the core event package only
# after spell combat logs stop reading live target AC and HP from Entity.
# Those resolution facts must be frozen on the event before it becomes cold.
class SpellEvent(ActionEvent):
    """Event payload for spell casting and spell effect logs."""

    name: str = Field(default="Spell Cast", description="A spell cast event")
    event_type: EventType = Field(default=EventType.CAST_SPELL, description="The type of event")
    spell_id: Optional[str] = Field(default=None, description="Stable spell catalog id")
    spell_level: int = Field(default=0, description="Base spell level (0 = cantrip)")
    cast_at_level: int = Field(default=0, description="Actual slot level used (0 = cantrip)")
    spell_school: str = Field(default="evocation", description="School of magic")
    verbal: bool = Field(default=True, description="Whether spell has a verbal component")
    source_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Caster position captured when the spell was declared.",
    )
    area_geometry: Optional[AoEPresentationGeometry] = Field(
        default=None,
        discriminator="shape",
        description="Exact immutable area geometry captured when the spell was declared.",
    )

    attack_bonus: Optional[ModifiableValue] = Field(default=None, description="The spell attack bonus")
    ac: Optional[ModifiableValue] = Field(default=None, description="The target's AC")
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

    def to_effect_origin(self) -> EffectOrigin:
        """Return dependency-neutral provenance for a persistent spell effect."""
        return EffectOrigin.spell(
            source_id=self.spell_id,
            source_event_lineage_uuid=str(self.lineage_uuid),
            source_position=self.source_position,
            base_spell_level=self.spell_level,
            effective_spell_level=self.cast_at_level,
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
            data={},
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
            caster_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            spell_name=spell_name,
            spell_level=self.spell_level,
            save_ability=self.save_ability or "dexterity",
            save_dc=dc,
            save_roll=save_roll_display,
            save_bonus_breakdown=save_bonus_breakdown,
            save_advantage_breakdown=save_advantage_breakdown,
            save_success=success,
            damage_rolls=damage_displays,
            base_damage=base_damage,
            final_damage=total_dmg,
            damage_type=damage_type
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
            data=data.model_dump(),
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

        attack_breakdown: List[ModifierBreakdown] = []
        if self.attack_bonus:
            for mod in self.attack_bonus.get_breakdown():
                attack_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        advantage_breakdown: List[ModifierBreakdown] = []
        if self.attack_bonus:
            for mod in self.attack_bonus.get_full_advantage_breakdown():
                adv_val = mod.get('value', 'inactive')
                if adv_val == 'advantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=1, source=mod.get('source', 'self')
                    ))
                elif adv_val == 'disadvantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=-1, source=mod.get('source', 'self')
                    ))

        target_ac = 0
        if self.ac:
            target_ac = self.ac.normalized_score
        elif target_entity:
            target_ac = target_entity.ac_bonus().normalized_score

        ac_breakdown: List[ModifierBreakdown] = []
        if self.ac:
            for mod in self.ac.get_breakdown():
                ac_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

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
                damage_bonus_breakdown: List[ModifierBreakdown] = []
                if damage and damage.damage_bonus:
                    for mod in damage.damage_bonus.get_breakdown():
                        damage_bonus_breakdown.append(ModifierBreakdown(
                            name=mod.get('name', 'Unknown'),
                            value=mod.get('value', 0),
                            source=mod.get('source', 'self')
                        ))
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
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
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
            data=data.model_dump(),
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
            bonus = self.damages[0].damage_bonus.normalized_score if self.damages and self.damages[0].damage_bonus else 1
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
            data={
                "spell_name": spell_name,
                "target_name": target_name,
                "damage": total_dmg,
                "damage_type": damage_type
            },
            success=True
        )


class SpellAttackResolution(BaseModel):
    """Resolved spell attack roll and the values that produced it."""

    attack_bonus: ModifiableValue = Field(description="Combined spell attack value used for the roll.")
    target_ac: ModifiableValue = Field(description="Target armor class used to determine the outcome.")
    dice_roll: DiceRoll = Field(description="Completed d20 spell attack roll.")
    outcome: AttackOutcome = Field(description="Hit, miss, or critical outcome of the roll.")
    is_threatened: bool = Field(
        description="Whether ranged-attack disadvantage was applied because a visible hostile threatened the caster.",
    )


class SpellAction(BaseAction):
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

    caster_level: int = Field(default=1, description="Level of the caster (for cantrip scaling)")
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

    projectile_type: Optional[str] = Field(default=None, description="VFX projectile delivery type")
    spell_damage_type: Optional[DamageType] = Field(default=None, description="Primary damage type for VFX")
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

    def get_spell_discovery_metadata(
        self,
    ) -> Optional[SpellDiscoveryMetadata]:
        """Return exact spell fields through the common action contract."""
        return SpellDiscoveryMetadata(
            spell_level=self.spell_level,
            cast_at_level=self.cast_at_level,
            is_variant=self.is_variant,
            damage_type=(
                self.spell_damage_type.value
                if self.spell_damage_type is not None
                else None
            ),
        )

    def spell_execution_scope(self):
        """Open the cast-local context used by low-level damage contributors."""

        saving_throw_effect_id = self.saving_throw_effect_id
        if saving_throw_effect_id is None:
            saving_throw_effect_id = f"{self.behavior_id}.saving_throw"
        return spell_execution_scope(
            source_entity_uuid=self.source_entity_uuid,
            damage_type=self.spell_damage_type,
            cause_id=self.behavior_id,
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

    def get_range(self) -> Range:
        """Return spell range with alt_range override for position filtering."""
        return Range(type=self.spell_range.type, normal=self.effective_range, long=self.spell_range.long)

    def _validate_entity_target_in_range_and_sight(
        self,
        declaration_event: SpellEvent,
    ) -> Optional[SpellEvent]:
        """Validate the shared entity-target spell geometry and lifecycle."""
        if self.target_entity_uuid is None:
            return declaration_event.cancel(
                status_message="Source or target entity not found",
            )
        return self._validate_entity_targets_in_range_and_sight(
            declaration_event,
            (self.target_entity_uuid,),
        )

    def _validate_entity_target_or_self_in_range_and_sight(
        self,
        declaration_event: SpellEvent,
    ) -> Optional[SpellEvent]:
        """Validate an optional entity target, defaulting omission to the caster."""
        target_entity_uuid = self.target_entity_uuid or self.source_entity_uuid
        return self._validate_entity_targets_in_range_and_sight(
            declaration_event,
            (target_entity_uuid,),
        )

    def _validate_entity_targets_in_range_and_sight(
        self,
        declaration_event: SpellEvent,
        target_entity_uuids: Iterable[UUID],
    ) -> Optional[SpellEvent]:
        """Validate common geometry for one or more selected spell targets."""
        source_entity = Entity.get(self.source_entity_uuid)
        if not isinstance(source_entity, Entity):
            return declaration_event.cancel(
                status_message="Source entity not found",
            )

        for target_uuid in dict.fromkeys(target_entity_uuids):
            target_entity = Entity.get(target_uuid)
            if not isinstance(target_entity, Entity):
                return declaration_event.cancel(
                    status_message="Target entity not found",
                )
            if (
                target_uuid != source_entity.uuid
                and (
                    (contact := source_entity.senses.entities.get(target_uuid)) is None
                    or not contact.visual
                )
            ):
                return declaration_event.cancel(
                    status_message=(
                        f"{target_entity.name} not in line of sight"
                    ),
                )

            distance = source_entity.distance_to_entity(target_entity)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=(
                        f"{target_entity.name} out of range "
                        f"({distance}ft > {self.effective_range}ft)"
                    ),
                )

        return cast(
            Optional[SpellEvent],
            super()._validate(declaration_event),
        )

    def _validate_visible_position_in_range(
        self,
        declaration_event: SpellEvent,
    ) -> Optional[SpellEvent]:
        """Validate the shared position-target spell geometry and lifecycle."""
        caster = Entity.get(self.source_entity_uuid)
        if not isinstance(caster, Entity):
            return declaration_event.cancel(status_message="Caster not found")

        target_position = self.end_position
        if target_position is None:
            return declaration_event.cancel(
                status_message="No target position specified",
            )
        if not caster.senses.visible.get(target_position, False):
            return declaration_event.cancel(
                status_message=f"Position {target_position} not visible",
            )

        distance = caster.distance_to_position(target_position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=(
                    f"Position out of range "
                    f"({distance}ft > {self.effective_range}ft)"
                ),
            )

        return cast(
            Optional[SpellEvent],
            super()._validate(declaration_event),
        )

    def _validate_self_cast(
        self,
        declaration_event: SpellEvent,
    ) -> Optional[SpellEvent]:
        """Validate the shared self-targeted spell lifecycle."""
        if Entity.get(self.source_entity_uuid) is None:
            return declaration_event.cancel(status_message="Caster not found")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Validated {self.name}",
        )

    def _validate_directional_self_cast(
        self,
        declaration_event: SpellEvent,
    ) -> Optional[SpellEvent]:
        """Validate a self-originating area spell with a chosen direction."""
        if Entity.get(self.source_entity_uuid) is None:
            return declaration_event.cancel(status_message="Caster not found")
        if self.end_position is None:
            return declaration_event.cancel(
                status_message="No direction specified for cone",
            )
        return cast(
            Optional[SpellEvent],
            super()._validate(declaration_event),
        )

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
        target: Entity,
        parent_event_uuid: UUID,
        *,
        extra_advantage_modifiers: Tuple[AdvantageModifier, ...] = (),
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
        attack_bonus = caster.spell_attack_bonus(
            target.uuid,
            spellcasting_source_id=self.spellcasting_source_id,
        )
        target_ac = target.ac_bonus(caster.uuid)
        for modifier in extra_advantage_modifiers:
            attack_bonus.self_static.add_advantage_modifier(modifier)

        is_threatened = self.get_range().type is RangeType.RANGE and caster.is_threatened()
        if is_threatened:
            attack_bonus.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name="Threatened (Ranged)",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=caster.uuid,
                    target_entity_uuid=target.uuid,
                )
            )

        attack_bonus.set_from_target(target_ac)
        target_ac.set_from_target(attack_bonus)
        dice_roll = caster.roll_d20(
            attack_bonus,
            RollType.ATTACK,
            parent_event=parent_event_uuid,
        )
        outcome = determine_attack_outcome(
            dice_roll,
            target_ac,
            caster.get_spell_crit_threshold(),
        )
        attack_bonus.reset_from_target()
        target_ac.reset_from_target()
        return SpellAttackResolution(
            attack_bonus=attack_bonus,
            target_ac=target_ac,
            dice_roll=dice_roll,
            outcome=outcome,
            is_threatened=is_threatened,
        )

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
        synced_event = effect_event.with_updates(
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_roll.bonus,
            status_message=(
                f"{ability_display} save: {save_roll.total} vs DC {dc} - "
                f"{'Success' if success else 'Failure'}"
            ),
        )
        return synced_event, save_roll, success

    def ensure_concentration(self, parent_event: Event) -> "Concentrating":
        """Create or reuse Concentrating for this cast. Safe for convolution loop.

        The first call for a cast creates Concentrating and replaces any older
        concentration. Later calls in the same convolution loop reuse the UUID
        created by the first target.
        """
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            raise ValueError("Caster not found")

        if self.cast_concentrating_uuid:
            existing = caster.active_conditions_by_uuid.get(self.cast_concentrating_uuid)
            if existing and isinstance(existing, Concentrating):
                return existing

        conc = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name=self.name or "Unknown",
        )
        caster.add_condition(conc, parent_event=parent_event)
        self.cast_concentrating_uuid = conc.uuid
        result = caster.active_conditions["Concentrating"]
        assert isinstance(result, Concentrating)
        return result

    def _cleanup_concentration(self, completion_event: ActionEvent) -> None:
        """Remove Concentrating if all targets saved (0-children bug fix).

        Also clean up empty slots in multi-slot scenarios."""
        if not self.cast_concentrating_uuid:
            return
        caster = Entity.get(self.source_entity_uuid)
        if not caster or "Concentrating" not in caster.active_conditions:
            return
        conc = caster.active_conditions["Concentrating"]
        if not isinstance(conc, Concentrating) or conc.uuid != self.cast_concentrating_uuid:
            return
        conc.cleanup_if_no_effects(parent_event=completion_event)
        if "Concentrating" in caster.active_conditions:
            empty_slot_uuids = [slot_uuid for slot_uuid, slot in conc.concentration_slots.items() if not slot.linked_entries]
            for slot_uuid in empty_slot_uuids:
                conc.concentration_slots[slot_uuid].remove_from_register()
                del conc.concentration_slots[slot_uuid]
            if empty_slot_uuids:
                conc._sync_spell_name()

    def _get_aoe_radius_ft(self) -> Optional[int]:
        """Extract AoE size in feet from aoe_shape for VFX metadata."""
        shape = self.aoe_shape
        if shape is None:
            return None
        if isinstance(shape, (Sphere, Cylinder)):
            return shape.radius_feet
        if isinstance(shape, Cone):
            return shape.length_feet
        if isinstance(shape, Line):
            return shape.length_feet
        if isinstance(shape, Cube):
            return shape.size_feet
        return None

    def _get_range_type(self) -> Optional[str]:
        """Map spell range type to VFX delivery string."""
        rt = self.spell_range.type
        if rt == RangeType.SELF:
            return "self"
        if rt == RangeType.REACH:
            return "touch"
        if rt == RangeType.RANGE:
            return "ranged"
        return None

    def generate_variants(self, entity: Entity) -> List['SpellAction']:
        """Generate spell variants for available spell slots.

        Cantrips return a single slotless variant. Leveled spells return one
        variant for each currently available spell slot at or above the base
        spell level.

        Args:
            entity: The entity that would cast the spell

        Returns:
            List of SpellAction variants with appropriate costs
        """
        variants: List['SpellAction'] = []

        if self.spell_level == 0:
            variants.append(self._create_variant(cast_at_level=0))
        else:
            for slot_level in range(self.spell_level, 10):
                if entity.has_spell_slot(slot_level):
                    variants.append(self._create_variant(cast_at_level=slot_level))

        return variants

    def get_discovery_variants(self, entity: Any) -> List[BaseAction]:
        """Return spell forms that should appear in action discovery.

        Args:
            entity: Entity requesting available actions.

        Returns:
            The registered cantrip or slotless override template, or generated
            slot-level variants for leveled spells.
        """
        spell_variants: List[BaseAction]
        if self.spell_level == 0 or self.alt_skip_slot:
            spell_variants = [self]
        else:
            spell_variants = list(self.generate_variants(entity))
        return [
            variant
            for spell_variant in spell_variants
            for variant in BaseAction.get_discovery_variants(
                spell_variant,
                entity,
            )
        ]

    def get_discovery_template_name(self) -> str:
        """Return a stable execution name for this spell discovery row."""
        base_name = self.name or "Unknown"
        if self.is_variant and self.spell_level > 0:
            base_name = (
                f"{base_name}{SPELL_SLOT_TEMPLATE_SEPARATOR}"
                f"{self.cast_at_level}"
            )
        grant = self._restricted_action_grant
        if grant is not None:
            return (
                f"{base_name}{RESTRICTED_ACTION_TEMPLATE_SEPARATOR}"
                f"{grant.grant_id}"
            )
        return base_name

    def get_discovery_display_name(self) -> str:
        """Return a human-facing label for this spell discovery row."""
        base_name = self.name or "Unknown"
        if self.is_variant and self.spell_level > 0:
            return f"{base_name} (Level {self.cast_at_level})"
        return base_name

    def _create_variant(self, cast_at_level: int, **overrides) -> 'SpellAction':
        """Create a lightweight read-only discovery variant for one slot level.

        Definition submodels are shared with the registered template while the
        variant is inspected during discovery. Execution subsequently creates
        one deep executable copy before any target or area state can mutate.

        Args:
            cast_at_level: The spell slot level to use (0 for cantrips)
            **overrides: Additional field overrides

        Returns:
            A new SpellAction instance configured for this cast level
        """
        update_dict: dict = {
            "uuid": uuid4(),
            "cast_at_level": cast_at_level,
            "is_variant": True,
            "template": False,
            "use_register": False,
            "costs": self._get_costs_for_level(cast_at_level),
            # Slot variants store normalized executable costs.  Retaining the
            # template's cost transforms would make ``effective_costs`` apply
            # them a second time, most critically duplicating named-resource
            # costs on generated/upcast spells.
            "alt_cost_type": None,
            "alt_extra_costs": [],
            "alt_skip_slot": False,
        }
        update_dict.update(overrides)

        return self.model_copy(deep=False, update=update_dict)

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

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for this spell."""
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = source_entity.name if source_entity else None
        target_name = target_entity.name if target_entity else None

        event = SpellEvent(
            name=f"{self.name}",
            spell_id=normalize_spell_id(self.name or ""),
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
            verbal=self.verbal,
            source_position=source_entity.position if source_entity else None,
            area_geometry=(
                snapshot_aoe_presentation_geometry(
                    self.aoe_shape,
                    source_entity.position,
                    target_override=self.end_position,
                )
                if self.aoe_shape is not None and source_entity is not None
                else None
            ),
            aoe_position=self.end_position if self.effective_target_type == TargetType.POSITION_AOE else None,
            aoe_shape_type=self.aoe_shape.name.lower() if self.aoe_shape and self.aoe_shape.name else None,
            aoe_radius_ft=self._get_aoe_radius_ft(),
            range_type=self._get_range_type(),
            range_ft=self.spell_range.normal,
            projectile_type=self.projectile_type,
            damage_types=[self.spell_damage_type] if self.spell_damage_type else [],
            source_item_uuid=self.source_item_uuid,
            source_item_state=self.source_item_state,
            item_charge_cost=self.charge_cost if self.source_item_uuid is not None else 0,
            item_charge_action_lineage_uuid=None,
            declared_target_entity_uuids=self._declared_target_entity_uuids(),
        )
        event.item_charge_action_lineage_uuid = event.lineage_uuid
        if current_spell_execution() is not None:
            self.bind_spell_execution_lineage(event.lineage_uuid)
        return event

    def _apply_execution_cancellation_costs(
        self,
        canceled_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        """Spend a committed cast when a reaction interrupts its execution."""
        return self._consume_costs(canceled_event)

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
        default_factory=list,
        description="No-cost action-economy payload for pickup.",
    )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(item, BaseItem) or not item.is_pickable:
            return declaration_event.cancel(status_message="Cannot pick up this object")

        if not entity.inventory.can_add(item):
            return declaration_event.cancel(status_message="Inventory full")

        item_pos = get_map().get_object_position(item.uuid)
        if item_pos is None:
            return declaration_event.cancel(status_message="Item not on the ground")
        item_distance = entity.distance_to_object(item)
        if item_distance is None or item_distance > 5:
            return declaration_event.cancel(status_message="Item too far away")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated Pick Up {item.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not entity or not isinstance(item, BaseItem):
            return execution_event.cancel(status_message="Entity or item not found")

        entity.loot_item(item, parent_event=execution_event)
        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Picked up {item.name}"
        )


@_core_action_identity(
    content_id="action.attack_object",
    display_name="Attack Object",
    description="Make a melee weapon attack against a breakable object.",
    source_anchor="SRD 5.1 (CC-BY-4.0), Combat: Actions in Combat — Attack",
    sort_order=130,
)
class AttackObject(BaseAction):
    """Attack a breakable object. Costs 1 action. Auto-hit, rolls weapon damage.

    Uses target_entity_uuid to hold the item UUID.
    """
    name: str = Field(default="Attack Object", description="Action name for attacking an object.")
    description: str = Field(
        default="Attack a breakable object",
        description="Action description shown for object attacks.",
    )
    target_type: TargetType = Field(
        default=TargetType.OBJECT,
        description="AttackObject targets a floor object.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ATTACK,
        description="Classifies object attacks as attack actions.",
    )
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Attack Object Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action cost for attacking a breakable object.")

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(item, BaseItem) or not item.is_targetable or not item.is_breakable():
            return declaration_event.cancel(status_message="Cannot attack this object")

        item_pos = get_map().get_object_position(item.uuid)
        if item_pos is None:
            return declaration_event.cancel(status_message="Object not on the ground")
        item_distance = entity.distance_to_object(item)
        if item_distance is None or item_distance > 5:
            return declaration_event.cancel(status_message="Object too far away")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated Attack Object {item.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not entity or not isinstance(item, BaseItem):
            return execution_event.cancel(status_message="Entity or item not found")

        weapon_slot = WeaponSlot.MELEE_MAIN
        damages = entity.equipment.get_damages(weapon_slot, entity.ability_scores)
        total_damage = 0
        for dmg in damages:
            dice = dmg.get_dice(AttackOutcome.HIT)
            total_damage += dice.roll.total
        main_type = entity.equipment.get_main_damage_type(weapon_slot)

        actual = item.receive_damage(
            total_damage,
            main_type,
            entity.uuid,
            parent_event=execution_event,
        )
        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Dealt {actual} {main_type.value} damage to {item.name}"
        )

class Drop(BaseAction):
    """Drop an item from inventory onto the ground at a position.

    Position-target action (POSITION_LOS) bound to a specific item.
    Valid positions: entity's own cell + adjacent cells (range 5ft).

    The item_uuid is bound at creation time (one Drop per item).
    """
    name: str = Field(default="Drop", description="Action name for dropping an inventory item.")
    description: str = Field(
        default="Drop an item from inventory",
        description="Action description shown for inventory item drops.",
    )
    target_type: TargetType = Field(
        default=TargetType.POSITION_LOS,
        description="Drop targets a visible position.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for item drops.",
    )
    item_uuid: Optional[UUID] = Field(default=None, description="UUID of the item to drop (bound at creation)")

    def get_range(self) -> Optional[Range]:
        return Range(type=RangeType.REACH, normal=5)

    def get_valid_positions(self) -> List[Tuple[int, int]]:
        """Return own and visible adjacent positions within 5 feet."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return []
        valid: List[Tuple[int, int]] = [entity.position]
        for pos, is_visible in entity.senses.visible.items():
            if not is_visible:
                continue
            if pos == entity.position:
                continue
            if entity.distance_to_position(pos) <= 5:
                valid.append(pos)
        return valid

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if self.item_uuid is None:
            return declaration_event.cancel(status_message="No item specified")
        if not entity.inventory.has_item(self.item_uuid):
            return declaration_event.cancel(status_message="Item not in inventory")

        if self.end_position is None:
            return declaration_event.cancel(status_message="No drop position specified")

        dx = abs(self.end_position[0] - entity.position[0])
        dy = abs(self.end_position[1] - entity.position[1])
        if dx > 1 or dy > 1:
            return declaration_event.cancel(status_message="Drop position too far (max 5ft)")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Validated Drop"
        )

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
            new_phase=EventPhase.COMPLETION,
            status_message=f"Dropped {dropped.name}"
        )


CORE_STANDARD_ACTION_DECLARATIONS = tuple(
    get_content_declaration(action_type)
    for action_type in (
        Move,
        Swim,
        Attack,
        Dash,
        Dodge,
        Disengage,
        DropConcentration,
        ShakeAwake,
        Hide,
        Jump,
        TraverseConnector,
        Shove,
        PickUp,
        AttackObject,
    )
)
