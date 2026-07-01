"""Action templates, cost models, execution events, and discovery DTOs."""

from pydantic import BaseModel, Field, ConfigDict, computed_field
from dnd.core.events import Event, EventType, EventPhase, EventProcessor, Range, EventQueue
from dnd.core.base_object import BaseObject
from dnd.core.base_block import BaseBlock
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, SelfActionLogData, MultiEntityLogData, md_color
from dnd.core.aoe import AoEShape
from dnd.blocks.sensory import Senses
from typing import Any, Optional, Callable, OrderedDict, List, Dict, Literal, Set, Tuple, cast
from uuid import UUID, uuid4
from enum import Enum

CostType = Literal[
    "actions", "bonus_actions", "reactions", "movement",
    "spell_slot_1", "spell_slot_2", "spell_slot_3", "spell_slot_4",
    "spell_slot_5", "spell_slot_6", "spell_slot_7", "spell_slot_8", "spell_slot_9"
]

SPELL_SLOT_COST_TYPES: Dict[int, CostType] = {
    1: "spell_slot_1", 2: "spell_slot_2", 3: "spell_slot_3",
    4: "spell_slot_4", 5: "spell_slot_5", 6: "spell_slot_6",
    7: "spell_slot_7", 8: "spell_slot_8", 9: "spell_slot_9",
}
SPELL_SLOT_TEMPLATE_SEPARATOR = "__slot_"


def spell_slot_cost_type(level: int) -> CostType:
    """Convert a spell slot level to an action-economy cost type.

    Args:
        level: Spell slot level from 1 through 9.

    Returns:
        Cost type matching the requested spell slot level.

    Raises:
        ValueError: If `level` is outside the implemented spell-slot range.
    """
    result = SPELL_SLOT_COST_TYPES.get(level)
    if result is None:
        raise ValueError(f"Invalid spell slot level: {level}")
    return result


class ActionCategory(str, Enum):
    """Classification of action types."""

    ABILITY = "ability"
    ATTACK = "attack"
    SPELL = "spell"
    MOVEMENT = "movement"


class TargetType(str, Enum):
    """Target routing categories used by discovery and execution."""

    SELF = "self"
    ENTITY = "entity"
    POSITION = "position"
    POSITION_PATH = "position_path"
    POSITION_LOS = "position_los"
    POSITION_AOE = "position_aoe"
    MULTI_ENTITY = "multi_entity"
    OBJECT = "object"

CostEvaluator = Callable[[UUID, CostType, int], bool]
ResourceCostEvaluator = Callable[[UUID, str, int], bool]


class BaseCost(BaseModel):
    """Serializable action cost without executable callbacks."""

    name: str = Field(default="A Cost", description="Human-readable cost label.")
    cost_type: CostType = Field(description="Action economy bucket consumed by this cost.")
    cost: int = Field(description="Amount consumed from the action economy bucket.")
    resource_name: Optional[str] = Field(
        default=None,
        description="Optional named resource consumed in addition to the action economy bucket.",
    )
    resource_cost: int = Field(default=0, description="Amount consumed from the named resource.")


class Cost(BaseCost):
    """Runtime action cost with optional affordability callbacks."""

    evaluator: Optional[CostEvaluator] = Field(
        default=None,
        exclude=True,
        description="Callback that checks action-economy affordability.",
    )
    resource_evaluator: Optional[ResourceCostEvaluator] = Field(
        default=None,
        exclude=True,
        description="Callback that checks named-resource affordability.",
    )


class ActionEvent(Event):
    """Event emitted by the base action pipeline."""

    costs: List[BaseCost] = Field(default_factory=list, description="Serializable action costs.")
    event_type: EventType = Field(default=EventType.BASE_ACTION, description="Base action event type.")
    description: str = Field(default="", description="Action description for combat log generation")
    total_targets: int = Field(
        default=0,
        description="Number of targets affected by a multi-target or AoE action.",
    )
    total_damage: int = Field(
        default=0,
        description="Total damage dealt across all per-target child events.",
    )
    aoe_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Grid position targeted by a position-AoE action.",
    )

    def add_cost(self, cost: Cost) -> None:
        """Append a serializable copy of a runtime action cost.

        Args:
            cost: Runtime cost to store without executable callbacks.
        """
        base_cost = BaseCost.model_validate(cost)
        self.costs.append(base_cost)

    @classmethod
    def from_costs(
        cls,
        costs: List[Cost],
        source_entity_uuid: UUID,
        target_entity_uuid: Optional[UUID] = None,
        parent_event: Optional[Event] = None,
        use_register: bool = True,
    ) -> "ActionEvent":
        """Create an action event from runtime costs.

        Args:
            costs: Runtime costs to serialize on the event.
            source_entity_uuid: Acting entity UUID.
            target_entity_uuid: Optional primary target UUID.
            parent_event: Optional parent event for event-tree nesting.
            use_register: Whether the event should be registered immediately.

        Returns:
            Newly created action event.
        """
        base_costs = [BaseCost.model_validate(cost) for cost in costs]
        return cls(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=target_entity_uuid,
            costs=base_costs,
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return positions that spatial handlers should inspect for this event."""
        positions: Set[Tuple[int, int]] = set()
        if self.aoe_position:
            positions.add(self.aoe_position)
        return positions

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate a combat log entry for generic actions.

        Uses self.name and self.description. Subclasses (AttackEvent,
        MovementEvent, SpellEvent) override with specific implementations.

        For multi-target actions (total_targets > 0), generates a summary log.
        Sub-entries come from _collect_child_combat_logs() via parent_event relationship.

        Returns:
            CombatLogEntry for self-targeting actions, or None for base events.
        """
        if self.total_targets > 0:
            return self._generate_multi_target_log()

        source_name = self.source_entity_name or "Unknown"
        action_name = self.name or "Action"
        effect_desc = self.description or ""

        compact = f"{{cyan:{source_name}}} uses {{bold:{action_name}}}"
        verbose = compact + (f"\n  {effect_desc}" if effect_desc else "")
        detailed = verbose

        data = SelfActionLogData(
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            action_name=action_name,
            effect_description=effect_desc
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact,
            verbose=verbose,
            detailed=detailed,
            data=data.model_dump(),
            success=True
        )

    def _generate_multi_target_log(self) -> CombatLogEntry:
        """Generate summary log for multi-target actions.

        Per-target details are child event logs collected into sub-entries by
        the completion phase.

        Returns:
            Multi-entity combat-log summary.
        """
        source_name = self.source_entity_name or "Unknown"
        n_targets = self.total_targets
        total_dmg = self.total_damage or 0

        action_name = self.name or 'Action'
        if self.aoe_position:
            location = f" at ({self.aoe_position[0]}, {self.aoe_position[1]})"
        else:
            location = ""
        summary = f"{md_color(source_name, 'cyan')} uses {md_color(action_name, 'yellow')}{location} → {n_targets} targets, {md_color(str(total_dmg), 'red')} total damage"

        data = MultiEntityLogData(
            action_name=self.name or "Action",
            caster_name=source_name,
            total_targets=n_targets,
            total_damage=total_dmg,
            aoe_center=self.aoe_position
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MULTI_ENTITY_ACTION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            compact=summary,
            verbose=summary,
            detailed=summary,
            data=data.model_dump(),
            success=n_targets > 0
        )


class BaseAction(BaseObject):
    """Base class for executable action templates and instances.

    Actions can be created as templates (template=True) which are bound to a source entity
    with fixed configuration (e.g., weapon_slot), but without a specific target. Templates
    support pre_validate() but cannot be applied directly - use instantiate() to create
    an executable instance with a specific target.
    """

    description: str = Field(default="", description="UI and combat-log description for this action.")
    parent_event: Optional[Event] = Field(
        default=None,
        description="Optional parent event used to nest action-created events.",
    )
    costs: List[Cost] = Field(default_factory=list, description="Runtime costs required by this action.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Target category used by discovery and instantiation.",
    )
    template: bool = Field(
        default=False,
        description="True when this action is a reusable template instead of an executable instance.",
    )
    include_self: bool = Field(
        default=False,
        description="Whether the acting entity can be included in this action's target set.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ABILITY,
        description="Broad action classification used by discovery and UI layers.",
    )

    @property
    def is_attack(self) -> bool:
        """Whether this action is categorized as an attack."""
        return self.action_category == ActionCategory.ATTACK

    @property
    def is_spell(self) -> bool:
        """Whether this action is categorized as a spell."""
        return self.action_category == ActionCategory.SPELL

    @property
    def is_movement(self) -> bool:
        """Whether this action is categorized as movement."""
        return self.action_category == ActionCategory.MOVEMENT

    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the item providing this action when it is an item-use action.",
    )
    charge_cost: int = Field(default=1, description="Charges consumed when this action is used from an item")
    end_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Grid position selected for position-targeted actions.",
    )
    aoe_shape: Optional[AoEShape] = Field(
        default=None,
        description="Shape template used to resolve affected cells and entities for AoE actions.",
    )
    extra_target_entity_uuids: List[UUID] = Field(
        default_factory=list,
        description="Additional target UUIDs beyond the primary target for multi-entity actions.",
    )
    allow_same_target: bool = Field(
        default=True,
        description="Whether a multi-entity action can target the same entity more than once.",
    )
    valid_target_filter: str = Field(
        default="enemies",
        description="Entity relationship filter: enemies, allies, self_or_allies, or all.",
    )
    include_dead: bool = Field(
        default=False,
        description="Whether dead entities remain eligible targets.",
    )
    aoe_require_targets: bool = Field(
        default=True,
        description="Whether AoE discovery requires at least one affected entity before exposing a position.",
    )
    requires_concentration: bool = Field(
        default=False,
        description="Whether action completion invokes the concentration cleanup hook.",
    )
    alt_cost_type: Optional[str] = Field(default=None, description="Temporary replacement for primary action cost type.")
    alt_extra_costs: List[Cost] = Field(default_factory=list, description="Temporary additional costs.")
    alt_target_type: Optional[TargetType] = Field(default=None, description="Temporary replacement target type.")
    alt_target_count: Optional[int] = Field(default=None, description="Temporary multi-target count override.")
    alt_skip_slot: bool = Field(default=False, description="Whether temporary overrides skip spell-slot costs.")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def effective_target_type(self) -> TargetType:
        """Target type with alt override applied."""
        return self.alt_target_type if self.alt_target_type is not None else self.target_type

    @property
    def effective_costs(self) -> List["Cost"]:
        """Build costs incorporating all active overrides."""
        costs = list(self.costs)
        if self.alt_cost_type is not None:
            costs = [c.model_copy(update={"cost_type": self.alt_cost_type})
                     if c.cost_type == "actions" else c for c in costs]
        if self.alt_skip_slot:
            costs = [c for c in costs if not c.cost_type.startswith("spell_slot")]
        costs.extend(self.alt_extra_costs)
        return costs

    def set_target_entity(self, target_uuid: UUID) -> None:
        """Set target entity for ENTITY, MULTI_ENTITY, or OBJECT type actions.

        Used with templates to set the target before pre_validate() or instantiate().
        For MULTI_ENTITY, this sets the primary target.
        For OBJECT, this sets the item UUID (items are BaseBlocks in _registry).
        """
        if self.effective_target_type not in (TargetType.ENTITY, TargetType.MULTI_ENTITY, TargetType.OBJECT):
            raise ValueError(f"Action {self.name} doesn't target entities (target_type={self.effective_target_type})")
        self.target_entity_uuid = target_uuid

    def set_target_position(self, position: Tuple[int, int]) -> None:
        """Set target position for POSITION type actions.

        Used with templates to set the target before pre_validate() or instantiate().
        Supports POSITION, POSITION_PATH, POSITION_LOS, and POSITION_AOE target types.
        """
        if self.effective_target_type not in (TargetType.POSITION, TargetType.POSITION_PATH, TargetType.POSITION_LOS, TargetType.POSITION_AOE):
            raise ValueError(f"Action {self.name} doesn't target positions (target_type={self.effective_target_type})")
        self.end_position = position

    def get_range(self) -> Optional[Range]:
        """Get the range of this action.

        Override in subclasses to provide dynamic range calculation.
        Returns Range object with type/normal/long, or None if unlimited.

        For actions with dynamic range (like Jump), override this method.
        """
        return None

    def get_valid_positions(self) -> List[Tuple[int, int]]:
        """Get valid target positions for POSITION_LOS and POSITION_AOE actions.

        Override in subclasses to provide custom position filtering.
        Default implementation uses senses.visible + get_range().

        Returns:
            List of valid positions this action can target.
        """
        if self.effective_target_type not in (TargetType.POSITION_LOS, TargetType.POSITION_AOE):
            return []

        entity = BaseBlock.get(self.source_entity_uuid)
        if entity is None:
            return []

        senses_block = entity.get_senses()
        if not isinstance(senses_block, Senses):
            return []

        action_range = self.get_range()
        max_range = action_range.normal if action_range else 0

        valid: List[Tuple[int, int]] = []
        visible = senses_block.visible
        position = senses_block.position

        if not visible:
            return []

        for pos, is_visible in visible.items():
            if not is_visible:
                continue
            if pos == position:
                continue
            if max_range > 0:
                distance = senses_block.get_feet_distance(pos)
                if distance > max_range:
                    continue
            valid.append(pos)
        return valid

    def get_multi_target_count(self) -> Optional[int]:
        """Get the number of targets/projectiles for MULTI_ENTITY actions.

        Returns None for non-MULTI_ENTITY actions.
        Returns 1 as default for MULTI_ENTITY actions.
        Alt override takes priority when set.
        Subclasses override to return their specific count.
        """
        if self.alt_target_count is not None:
            return self.alt_target_count
        if self.effective_target_type != TargetType.MULTI_ENTITY:
            return None
        return 1

    def get_all_targets(self) -> List[UUID]:
        """Get all target UUIDs for multi-target actions.

        Position AoE actions compute targets from their shape and end position.
        Multi-entity actions return the primary target followed by extra targets.
        Subclasses may override this to provide custom target resolution.

        Returns:
            Target UUIDs in processing order.
        """
        if self.effective_target_type == TargetType.POSITION_AOE:
            if self.aoe_shape and self.end_position:
                source_block = BaseBlock.get(self.source_entity_uuid)
                if source_block:
                    shape = self.aoe_shape.model_copy(update={'target': self.end_position})
                    shape.compute_objective(source_block.position)
                    targets = list(shape.affected_entity_uuids)
                    if not self.include_self:
                        targets = [uid for uid in targets if uid != self.source_entity_uuid]
                    targets = self._filter_targets_by_faction(source_block, targets)
                    if not self.include_dead:
                        targets = [
                            uid for uid in targets
                            if (block := BaseBlock.get(uid)) and block.is_active
                        ]
                    return targets
            return []

        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        targets.extend(self.extra_target_entity_uuids)
        return targets

    def _filter_targets_by_faction(self, source_block: BaseBlock, targets: List[UUID]) -> List[UUID]:
        """Filter targets based on valid_target_filter for AoE spells.

        Args:
            source_block: Block that owns the action.
            targets: Candidate target UUIDs.

        Returns:
            Candidate targets that match this action's relationship filter.
        """
        if self.valid_target_filter == "all":
            return targets

        source_faction = source_block.faction

        filtered: List[UUID] = []
        for target_uuid in targets:
            target = BaseBlock.get(target_uuid)
            if target is None:
                continue

            same = target_uuid == self.source_entity_uuid
            ally = same or (source_faction is not None and target.faction is not None and source_faction == target.faction)
            enemy = not same and (source_faction is None or target.faction is None or source_faction != target.faction)

            if self.valid_target_filter == "enemies":
                if enemy:
                    filtered.append(target_uuid)
            elif self.valid_target_filter == "allies":
                if not same and ally:
                    filtered.append(target_uuid)
            elif self.valid_target_filter == "self_or_allies":
                if ally:
                    filtered.append(target_uuid)
            else:
                filtered.append(target_uuid)

        return filtered

    def _validate_target_filter(self, all_targets: List[UUID]) -> Optional[str]:
        """Validate that all targets match the valid_target_filter.

        Position-AoE targets are already filtered during target resolution.
        Explicit multi-entity targets are validated here.

        Args:
            all_targets: Target UUIDs to validate.

        Returns:
            Error message if validation fails, otherwise `None`.
        """
        if self.effective_target_type == TargetType.POSITION_AOE:
            return None

        source_block = BaseBlock.get(self.source_entity_uuid)
        if source_block is None:
            return "Source entity not found"

        senses: Optional[Senses] = getattr(source_block, 'senses', None)
        if senses is not None:
            for target_uuid in all_targets:
                if target_uuid == self.source_entity_uuid:
                    continue
                if target_uuid not in senses.entities:
                    target = BaseBlock.get(target_uuid)
                    target_name = target.name if target else str(target_uuid)
                    return f"{target_name} is not visible"

        source_faction = source_block.faction

        for target_uuid in all_targets:
            target = BaseBlock.get(target_uuid)
            if target is None:
                return f"Target {target_uuid} not found"

            same = target_uuid == self.source_entity_uuid
            ally = same or (source_faction is not None and target.faction is not None and source_faction == target.faction)
            enemy = not same and (source_faction is None or target.faction is None or source_faction != target.faction)

            if self.valid_target_filter == "enemies":
                if not enemy:
                    return f"{target.name} is not an enemy"
            elif self.valid_target_filter == "allies":
                if same or not ally:
                    return f"{target.name} is not an ally"
            elif self.valid_target_filter == "self_or_allies":
                if not ally:
                    return f"{target.name} is not self or an ally"

        return None

    def instantiate(self, **overrides) -> "BaseAction":
        """Create an executable instance from this template.

        Uses model_copy() to preserve object types (e.g., AoE shape subclasses).
        Instances are not registered (ephemeral, used once for apply()).

        Args:
            **overrides: Fields to override (target_entity_uuid, end_position, aoe_shape, etc.)

        Returns:
            BaseAction: A new instance that can be applied

        Raises:
            ValueError: If this is not a template
        """
        if not self.template:
            raise ValueError("Can only instantiate from a template")

        update_dict: dict = {
            "uuid": uuid4(),
            "template": False,
            "use_register": False,
        }
        update_dict.update(overrides)

        return self.model_copy(deep=True, update=update_dict)

    def get_discovery_variants(self, entity: Any) -> List["BaseAction"]:
        """Return action forms that should appear in action discovery.

        Args:
            entity: Entity requesting available actions.

        Returns:
            Discovery actions for this template. Non-variant actions expose
            themselves.
        """
        return [self]

    def get_discovery_template_name(self) -> str:
        """Return the machine-facing action name used for execution."""
        return self.name or "Unknown"

    def get_discovery_display_name(self) -> str:
        """Return the human-facing action name used by UIs."""
        return self.get_discovery_template_name()

    def check_costs(self) -> bool:
        """Check whether the acting entity can afford all effective costs."""
        for cost in self.effective_costs:
            if cost.evaluator is not None and not cost.evaluator(self.source_entity_uuid, cost.cost_type, cost.cost):
                return False
            if cost.resource_cost > 0 and cost.resource_name:
                if cost.resource_evaluator is not None:
                    if not cost.resource_evaluator(self.source_entity_uuid, cost.resource_name, cost.resource_cost):
                        return False
        return True

    def _create_declaration_event(
        self,
        parent_event: Optional[Event] = None,
        use_register: bool = True,
    ) -> Optional[ActionEvent]:
        """Create the declaration event for this action.

        Args:
            parent_event: Optional parent event for event-tree nesting.
            use_register: Whether to register the declaration event.

        Returns:
            Declaration event, or `None` if a subclass declines creation.
        """
        event = ActionEvent.from_costs(
            self.effective_costs,
            self.source_entity_uuid,
            self.target_entity_uuid,
            parent_event,
            use_register=use_register,
        )
        event.name = self.name or "Action"
        event.description = self.description
        source_block = BaseBlock.get(self.source_entity_uuid)
        if source_block is not None:
            event.source_entity_name = source_block.name
        return event

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate whether this action can be performed.

        Multi-entity actions require explicit targets and may forbid duplicate
        targets. Multi-entity and position-AoE actions both apply the configured
        relationship target filter.

        Args:
            declaration_event: Declaration-phase event to advance or cancel.

        Returns:
            Execution event on success, canceled event on validation failure, or
            `None` if a subclass declines validation.
        """
        effective_tt = self.effective_target_type
        if effective_tt in (TargetType.MULTI_ENTITY, TargetType.POSITION_AOE):
            all_targets = self.get_all_targets()

            if not all_targets:
                if effective_tt == TargetType.MULTI_ENTITY:
                    return declaration_event.cancel(status_message="No targets specified")

            if effective_tt == TargetType.MULTI_ENTITY and not self.allow_same_target:
                if len(set(all_targets)) != len(all_targets):
                    return declaration_event.cancel(
                        status_message="This action cannot target the same entity multiple times"
                    )

            filter_error = self._validate_target_filter(all_targets)
            if filter_error:
                return declaration_event.cancel(status_message=filter_error)

        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Succesfully validated action{self.name} for {declaration_event.source_entity_uuid}"
        )

    def pre_validate(self)-> bool:
        """Validate the action without registering a declaration event."""
        if not self.check_costs():
            return False
        declaration_event = self._create_declaration_event(parent_event=None, use_register=False)
        if declaration_event is None:
            return False
        if declaration_event.phase != EventPhase.DECLARATION:
            return False
        validation_event = self._validate(declaration_event)
        if validation_event is None or validation_event.canceled:
            return False
        return True
    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply the action's effects.

        Args:
            execution_event: Execution-phase event for this action.

        Returns:
            Completion event, canceled event, or `None`.
        """
        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applying effect for {self.name}"
        )
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Succesfully applied action {self.name} for {execution_event.source_entity_uuid}"
        )

    def _finalize_aoe(self, effect_event: ActionEvent) -> None:
        """Post-convolution hook for POSITION_AOE actions. Override for terrain/zone setup.

        Called after all per-target _apply() calls complete, before COMPLETION phase.
        Only called when target_type is POSITION_AOE.
        """
        pass

    def _cleanup_concentration(self, completion_event: ActionEvent) -> None:
        """Post-completion concentration cleanup hook. Override in SpellAction."""
        pass

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply action costs after successful completion.

        Subclasses that consume action economy override this method.
        """
        return completion_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Succesfully applied costs for {self.name} for {completion_event.source_entity_uuid}"
        )

    def apply(self, parent_event: Optional[Event] = None) -> Optional[Event]:
        """Main entry point for applying an action. This method orchestrates the flow
        through declaration, validation, and application phases.

        For MULTI_ENTITY actions, this runs convolution: calls _apply() for each target
        in get_all_targets(), collecting results into a final completion event.

        Raises:
            ValueError: If this is a template (use instantiate() first)
        """
        if self.template:
            raise ValueError(f"Cannot apply template action '{self.name}' - use instantiate() first")
        if not self.check_costs():
            return None

        declaration_event = self._create_declaration_event(parent_event)
        if declaration_event is None:
            return None
        elif declaration_event.canceled:
            return declaration_event

        if declaration_event.phase != EventPhase.DECLARATION:
            raise ValueError(f"Action {self.name} can only be validated in the declaration phase")
        execution_event = self._validate(declaration_event)
        if execution_event is None or execution_event.canceled:
            return execution_event
        if execution_event.phase not in [EventPhase.EXECUTION]:
            raise ValueError(f"Action {self.name} can only be applied in the execution phase")

        if self.effective_target_type in (TargetType.MULTI_ENTITY, TargetType.POSITION_AOE):
            all_target_uuids = self.get_all_targets()
            original_target = self.target_entity_uuid
            total_damage = 0

            for target_uuid in all_target_uuids:
                self.target_entity_uuid = target_uuid

                target_block = BaseBlock.get(target_uuid)
                target_entity_name = target_block.name if target_block else None

                per_target_event = execution_event.model_copy(update={
                    'uuid': uuid4(),
                    'lineage_uuid': uuid4(),
                    'parent_event': execution_event.uuid,
                    'target_entity_uuid': target_uuid,
                    'target_entity_name': target_entity_name,
                    'children_events': [],
                    'lineage_children_events': [],
                })
                per_target_event = cast(ActionEvent, EventQueue.register(per_target_event))

                if per_target_event.canceled:
                    continue

                result_event = self._apply(per_target_event)
                if result_event:
                    damage = result_event.total_damage or 0
                    total_damage += damage

            self.target_entity_uuid = original_target

            effect_event = execution_event.phase_to(
                EventPhase.EFFECT,
                total_targets=len(all_target_uuids),
                total_damage=total_damage,
                aoe_position=self.end_position,
                status_message=f"{self.name} affected {len(all_target_uuids)} targets for {total_damage} total damage"
            )

            if self.effective_target_type == TargetType.POSITION_AOE:
                self._finalize_aoe(effect_event)

            completion_event = effect_event.phase_to(
                EventPhase.COMPLETION,
                status_message=f"{self.name} completed"
            )
        else:
            completion_event = self._apply(execution_event)

        if completion_event is None or completion_event.canceled:
            return completion_event
        if completion_event.phase not in [EventPhase.COMPLETION]:
            raise ValueError(f"Action {self.name} can only be completed in the completion phase")
        if self.requires_concentration:
            self._cleanup_concentration(completion_event)
        cost_event = self._apply_costs(completion_event)
        if cost_event is None or cost_event.canceled:
            return cost_event
        if cost_event.phase not in [EventPhase.COMPLETION]:
            raise ValueError(f"Action {self.name} can only be completed in the completion phase")
        return cost_event


class StructuredAction(BaseAction):
    """Action implementation backed by prerequisite and consequence processors."""

    prerequisites: OrderedDict[str,EventProcessor] = Field(
        default_factory=OrderedDict,
        exclude=True,
        description="Ordered prerequisite processors keyed by prerequisite name.",
    )
    consequences: OrderedDict[str,EventProcessor] = Field(
        default_factory=OrderedDict,
        exclude=True,
        description="Ordered consequence processors keyed by consequence name.",
    )
    revalidate_prerequisites: bool = Field(
        default=True,
        description="Whether prerequisites are revalidated after each consequence.",
    )
    cost_applier: Optional[EventProcessor] = Field(
        default=None,
        exclude=True,
        description="Optional processor used to apply action costs.",
    )

    @computed_field
    @property
    def prerequisite_names(self) -> List[str]:
        """Serializable list of prerequisite names."""
        return list(self.prerequisites.keys())

    @computed_field
    @property
    def consequence_names(self) -> List[str]:
        """Serializable list of consequence names."""
        return list(self.consequences.keys())

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Run the prerequisite checking pipeline."""
        if declaration_event.phase != EventPhase.DECLARATION:
            raise ValueError(f"Action {self.name} prerequisites can only be checked in declaration phase")

        current_event = declaration_event
        for prerequisite_name, prerequisite_function in self.prerequisites.items():
            prerequisite_event = prerequisite_function(current_event, current_event.source_entity_uuid)
            if prerequisite_event is None:
                return current_event.cancel(status_message=f"Prerequisite {prerequisite_name} failed for {self.name}")
            if prerequisite_event.canceled:
                return prerequisite_event
            current_event = prerequisite_event

        return current_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Successfully validated structured action {self.name} for {current_event.source_entity_uuid}"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Run the consequence application pipeline."""
        if execution_event.phase != EventPhase.EXECUTION:
            raise ValueError(f"Action {self.name} consequences can only be applied in execution phase")

        current_event = execution_event
        effect_event = current_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applying consequences for {self.name}"
        )
        if effect_event.canceled:
            return effect_event

        current_event = effect_event
        for consequence_name, consequence_function in self.consequences.items():
            consequence_event = consequence_function(current_event, current_event.source_entity_uuid)
            if consequence_event is None:
                return current_event.cancel(status_message=f"Consequence {consequence_name} failed for {self.name}")
            elif consequence_event.canceled:
                return consequence_event

            if self.revalidate_prerequisites:
                if consequence_event.phase not in [EventPhase.EXECUTION, EventPhase.EFFECT]:
                    raise ValueError(f"Consequence {consequence_name} returned event in invalid phase {consequence_event.phase}")
                validated_event = self._validate(consequence_event)
                if validated_event is None or validated_event.canceled:
                    return validated_event
                current_event = validated_event
            else:
                current_event = consequence_event

        return current_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Successfully completed structured action {self.name} for {current_event.source_entity_uuid}"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply costs through the configured processor when present."""
        if self.cost_applier is not None:
            return self.cost_applier(completion_event, self.source_entity_uuid)
        return completion_event


class AvailableTarget(BaseModel):
    """A valid target for an action, with index for selection.

    Used in CLI/UI patterns like 'attack 0' or 'move 3' to select targets.
    """

    index: int = Field(description="Index for selection (e.g., 'attack 0')")
    target_uuid: Optional[UUID] = Field(default=None, description="For ENTITY actions")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Grid cell for POSITION targets and entity/object target cells")
    target_name: Optional[str] = Field(default=None, description="Entity name if ENTITY action")
    distance: Optional[int] = Field(default=None, description="Distance in feet")
    path_cost: Optional[int] = Field(default=None, description="Movement cost if POSITION action")
    extra_target_uuids: Optional[List[UUID]] = Field(default=None, description="Additional targets for MULTI_ENTITY actions")
    is_path_hazardous: bool = Field(default=False, description="Whether shortest path crosses a hazardous tile")
    safe_path_cost: Optional[int] = Field(default=None, description="Movement cost of safe alternative path (None if no safe path)")
    path: Optional[List[Tuple[int, int]]] = Field(default=None, description="Shortest path to this target")
    safe_path: Optional[List[Tuple[int, int]]] = Field(default=None, description="Safe alternative path avoiding hazards")
    affected_entity_uuids: Optional[List[UUID]] = Field(default=None, description="UUIDs of entities affected by AoE")
    affected_entity_names: Optional[List[str]] = Field(default=None, description="Names of entities affected by AoE")
    affected_count: Optional[int] = Field(default=None, description="Number of entities affected by AoE")
    affected_positions: Optional[List[Tuple[int, int]]] = Field(default=None, description="All positions in AoE shape (for map preview)")


class AvailableActionInfo(BaseModel):
    """Information about an available action and its valid targets.

    This is returned by Entity.get_available_actions() and contains everything
    needed to display the action in UI and execute it.
    """
    template_name: str = Field(description="Name of the template for execution")
    target_type: TargetType = Field(description="What kind of target this action needs")
    valid_targets: List[AvailableTarget] = Field(default_factory=list, description="All valid targets with indices")
    can_afford: bool = Field(description="Can afford base cost (action/bonus/etc)")
    display_name: str = Field(description="Human-readable name (e.g., 'Scimitar')")
    description: str = Field(default="", description="Action description")
    cost_type: CostType = Field(description="Type of cost (actions, bonus_actions, etc.)")
    cost_amount: int = Field(default=1, description="Cost amount (usually 1)")
    weapon_slot: Optional[str] = Field(default=None, description="Weapon slot for attacks")
    weapon_name: Optional[str] = Field(default=None, description="Weapon name for display (e.g., 'Scimitar')")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Classification of this action")
    base_template_name: Optional[str] = Field(
        default=None,
        description="Registered template name that produced this discovery row when it differs from template_name.",
    )
    spell_level: Optional[int] = Field(default=None, description="Base spell level for spell actions.")
    cast_at_level: Optional[int] = Field(default=None, description="Spell slot level used by this action row.")
    is_spell_variant: bool = Field(default=False, description="Whether this row represents a generated spell variant.")

    @property
    def is_attack(self) -> bool:
        """Whether this available action is categorized as an attack."""
        return self.action_category == ActionCategory.ATTACK

    @property
    def is_spell(self) -> bool:
        """Whether this available action is categorized as a spell."""
        return self.action_category == ActionCategory.SPELL

    num_projectiles: Optional[int] = Field(default=None, description="Number of projectiles/targets for MULTI_ENTITY actions")
    allow_same_target: Optional[bool] = Field(default=None, description="Whether same target can be selected multiple times")
    is_item_use: bool = Field(default=False, description="True for use actions from items")
    source_item_uuid: Optional[UUID] = Field(default=None, description="Item providing this action")
    item_stack_count: Optional[int] = Field(default=None, description="Stack count of source item (for display, only set when > 1)")


class AvailableActionsResult(BaseModel):
    """Complete available actions query result.

    Returned by Entity.get_available_actions(). Groups actions by type for
    easy iteration and UI rendering.
    """
    entity_uuid: UUID = Field(description="UUID of the entity these actions are for")
    entity_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting entities (Attack)")
    position_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting positions (Move)")
    self_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Self-targeting actions (Dash, Dodge, etc.)")
    object_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting objects (Pick Up, Attack Object)")
    remaining_movement: int = Field(default=0, description="Remaining movement in feet")
    handler_details: List[dict] = Field(default_factory=list, description="Event handlers with enabled state [{name, uuid, enabled, trigger_event}]")

    @property
    def all_actions(self) -> List[AvailableActionInfo]:
        """Get all available actions as a flat list."""
        return self.entity_actions + self.position_actions + self.self_actions + self.object_actions
