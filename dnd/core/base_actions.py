from pydantic import BaseModel, Field, ConfigDict
from dnd.core.events import Event, EventType, EventPhase, EventProcessor, Range, EventQueue
from dnd.core.base_object import BaseObject
from dnd.core.base_block import BaseBlock
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, SelfActionLogData, MultiEntityLogData, md_color
from dnd.core.aoe import AoEShape
from typing import Optional, Callable, OrderedDict, List, Literal, Tuple, cast
from uuid import UUID, uuid4
from enum import Enum

CostType = Literal[
    "actions", "bonus_actions", "reactions", "movement",
    "spell_slot_1", "spell_slot_2", "spell_slot_3", "spell_slot_4",
    "spell_slot_5", "spell_slot_6", "spell_slot_7", "spell_slot_8", "spell_slot_9"
]


class TargetType(str, Enum):
    """What kind of target an action requires."""
    SELF = "self"                    # Dash, Dodge, Disengage - no target needed
    ENTITY = "entity"                # Attack - targets another entity
    POSITION = "position"            # DEPRECATED: Use POSITION_PATH instead
    POSITION_PATH = "position_path"  # Move - requires contiguous path (uses senses.paths)
    POSITION_LOS = "position_los"    # Jump, Teleport - visible + range only (uses senses.visible)
    POSITION_AOE = "position_aoe"    # AoE spells - position + affected entities preview
    MULTI_ENTITY = "multi_entity"    # Multi-target spells/abilities - targets list of entities

CostEvaluator = Callable[[UUID,CostType,int],bool]

class BaseCost(BaseModel):
    """Cost for an action - can include both turn-based and resource costs."""
    name: str = Field(default="A Cost", description="The name of the cost")
    cost_type: CostType
    cost: int
    # Optional resource cost (can have both turn-based AND resource cost)
    resource_name: Optional[str] = Field(default=None, description="Name of resource to consume (e.g., 'second_wind')")
    resource_cost: int = Field(default=0, description="Amount of resource to consume")


class Cost(BaseCost):
    evaluator: Optional[CostEvaluator] = Field(default=None, description="The evaluator for the cost")

class ActionEvent(Event):
    costs: List[BaseCost] = Field(default_factory=list,description="A list of costs for the action")
    event_type: EventType = Field(default=EventType.BASE_ACTION,description="The type of event")
    description: str = Field(default="", description="Action description for combat log generation")

    # Multi-target summary fields (for MULTI_ENTITY actions)
    # Note: Per-target results are now children via parent_event, not stored here
    total_targets: int = Field(default=0, description="Number of targets affected")
    total_damage: int = Field(default=0, description="Total damage dealt across all targets")

    # Position for AoE actions (passed from BaseAction at execution time)
    aoe_position: Optional[Tuple[int, int]] = Field(default=None, description="Target position for AoE actions (for combat log)")

    def add_cost(self, cost: Cost):
        base_cost = BaseCost.model_validate(cost)
        self.costs.append(base_cost)

    @classmethod
    def from_costs(cls,costs: List[Cost], source_entity_uuid: UUID, target_entity_uuid: Optional[UUID] = None, parent_event: Optional[Event] = None, use_register: bool = True):
        base_costs = [BaseCost.model_validate(cost) for cost in costs]
        return cls(source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid, costs=base_costs, parent_event=parent_event.uuid if parent_event else None, use_register=use_register)

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate a combat log entry for generic actions.

        Uses self.name and self.description. Subclasses (AttackEvent,
        MovementEvent, SpellEvent) override with specific implementations.

        For multi-target actions (total_targets > 0), generates a summary log.
        Sub-entries come from _collect_child_combat_logs() via parent_event relationship.

        Returns:
            CombatLogEntry for self-targeting actions, or None for base events.
        """
        # Check if this is a multi-target action (total_targets set by convolution)
        if self.total_targets > 0:
            return self._generate_multi_target_log()

        # Original single-target logic
        source_name = self.source_entity_name or "Unknown"
        action_name = self.name or "Action"
        effect_desc = self.description or ""

        # Build three verbosity levels
        compact = f"{{cyan:{source_name}}} uses {{bold:{action_name}}}"
        verbose = compact + (f"\n  {effect_desc}" if effect_desc else "")
        detailed = verbose  # Same for generic actions

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

        This is just a summary line. Per-target details come from child events
        (via parent_event relationship) which are collected as sub_entries
        by _collect_child_combat_logs() in Event.phase_to().
        """
        source_name = self.source_entity_name or "Unknown"
        n_targets = self.total_targets
        total_dmg = self.total_damage or 0

        # Summary line with position if AoE
        action_name = self.name or 'Action'
        if self.aoe_position:
            location = f" at ({self.aoe_position[0]}, {self.aoe_position[1]})"
        else:
            location = ""
        summary = f"{md_color(source_name, 'cyan')} uses {md_color(action_name, 'yellow')}{location} → {n_targets} targets, {md_color(str(total_dmg), 'red')} total damage"

        # Data model for structured access (summary only, per-target data in sub_entries)
        data = MultiEntityLogData(
            action_name=self.name or "Action",
            caster_name=source_name,
            total_targets=n_targets,
            total_damage=total_dmg,
            aoe_center=self.aoe_position
        )

        # Summary only - sub_entries populated by _collect_child_combat_logs() in Event.phase_to()
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
    """Base class for all actions in the game. This class provides the basic structure
    for actions, allowing both direct implementation through _validate and _apply methods,
    as well as structured implementation through the StructuredAction subclass.

    Actions can be created as templates (template=True) which are bound to a source entity
    with fixed configuration (e.g., weapon_slot), but without a specific target. Templates
    support pre_validate() but cannot be applied directly - use instantiate() to create
    an executable instance with a specific target.
    """
    description: str = Field(default="", description="The description of the action, this is going to be displayed in the ui as a tooltip")
    parent_event: Optional[Event] = Field(default=None, description="The parent event of the action, the first event to be created in the action will be a child of this event used to keep track of sub-actions triggered by other events")
    costs: List[Cost] = Field(default_factory=list, description="A list of costs for the action")

    # Template system fields
    target_type: TargetType = Field(default=TargetType.SELF, description="What kind of target this action requires")
    template: bool = Field(default=False, description="If True, this is a template that cannot be applied directly - use instantiate()")
    include_self: bool = Field(default=False, description="If True and target_type=ENTITY, self is a valid target (for buff spells like Mage Armor)")
    is_attack: bool = Field(default=False, description="If True, action is a damage-dealing attack (Attack, Extra Attack, FrenziedStrike)")

    # For POSITION actions (like Move, Jump), stored separately from target_entity_uuid
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="Target position for POSITION type actions")

    # For AoE actions, the shape template to use (AoEShape: Sphere, Cone, Line, Cube)
    aoe_shape: Optional[AoEShape] = Field(default=None, description="AoE shape template (Sphere, Cone, Line, Cube)")

    # Multi-target fields (for MULTI_ENTITY actions)
    extra_target_entity_uuids: List[UUID] = Field(
        default_factory=list,
        description="Additional targets beyond primary target_entity_uuid (for MULTI_ENTITY)"
    )
    allow_same_target: bool = Field(
        default=True,
        description="If False, same entity cannot appear multiple times in target list"
    )
    valid_target_filter: str = Field(
        default="enemies",
        description="Which entities are valid targets: 'enemies', 'allies', 'self_or_allies', 'all'"
    )
    include_dead: bool = Field(
        default=False,
        description="If True, dead entities are valid targets (for resurrection, corpse explosion)"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def set_target_entity(self, target_uuid: UUID) -> None:
        """Set target entity for ENTITY or MULTI_ENTITY type actions.

        Used with templates to set the target before pre_validate() or instantiate().
        For MULTI_ENTITY, this sets the primary target.
        """
        if self.target_type not in (TargetType.ENTITY, TargetType.MULTI_ENTITY):
            raise ValueError(f"Action {self.name} doesn't target entities (target_type={self.target_type})")
        self.target_entity_uuid = target_uuid

    def set_target_position(self, position: Tuple[int, int]) -> None:
        """Set target position for POSITION type actions.

        Used with templates to set the target before pre_validate() or instantiate().
        Supports POSITION, POSITION_PATH, POSITION_LOS, and POSITION_AOE target types.
        """
        if self.target_type not in (TargetType.POSITION, TargetType.POSITION_PATH, TargetType.POSITION_LOS, TargetType.POSITION_AOE):
            raise ValueError(f"Action {self.name} doesn't target positions (target_type={self.target_type})")
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
        if self.target_type not in (TargetType.POSITION_LOS, TargetType.POSITION_AOE):
            return []

        # Get the entity
        entity = BaseBlock.get(self.source_entity_uuid)
        if entity is None:
            return []

        # Need senses attribute
        senses = getattr(entity, 'senses', None)
        if senses is None:
            return []

        action_range = self.get_range()
        max_range = action_range.normal if action_range else 0

        valid: List[Tuple[int, int]] = []
        visible = getattr(senses, 'visible', {})
        position = getattr(senses, 'position', None)
        get_feet_distance = getattr(senses, 'get_feet_distance', None)

        if not visible or position is None or get_feet_distance is None:
            return []

        for pos, is_visible in visible.items():
            if not is_visible:
                continue
            if pos == position:
                continue
            if max_range > 0:
                distance = get_feet_distance(pos)
                if distance > max_range:
                    continue
            valid.append(pos)
        return valid

    def get_all_targets(self) -> List[UUID]:
        """Get all target UUIDs for multi-target actions.

        For POSITION_AOE: Computes targets from shape + position.
        For MULTI_ENTITY: Returns primary target + extra targets.

        Override in subclasses to provide custom target resolution (e.g., Magic Missile
        filling remaining darts with primary target).

        Returns:
            List of target UUIDs in order they should be processed.
        """
        # POSITION_AOE: compute targets from shape
        if self.target_type == TargetType.POSITION_AOE:
            if self.aoe_shape and self.end_position:
                entity = BaseBlock.get(self.source_entity_uuid)
                if entity:
                    position = getattr(entity, 'position', None)
                    if position:
                        shape = self.aoe_shape.model_copy(update={'target': self.end_position})
                        shape.compute_objective(position)
                        # Return as list, using include_self to control caster inclusion
                        targets = list(shape.affected_entity_uuids)
                        if not self.include_self:  # Default False = exclude caster
                            targets = [uid for uid in targets if uid != self.source_entity_uuid]
                        # Apply valid_target_filter for AoE (filter, not validate)
                        # AoE targets a position - filter determines which entities are affected
                        targets = self._filter_targets_by_faction(entity, targets)
                        # Filter dead entities (unless include_dead=True)
                        if not self.include_dead:
                            targets = [
                                uid for uid in targets
                                if (ent := BaseBlock.get(uid)) and getattr(ent, 'get_hp', lambda: 1)() > 0
                            ]
                        return targets
            return []

        # MULTI_ENTITY: explicit targets (primary + extras)
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        targets.extend(self.extra_target_entity_uuids)
        return targets

    def _filter_targets_by_faction(self, source_entity: "BaseBlock", targets: List[UUID]) -> List[UUID]:
        """Filter targets based on valid_target_filter for AoE spells.

        For POSITION_AOE actions, this filters which entities in the area are affected.
        Unlike _validate_target_filter (which fails on non-matching targets),
        this removes non-matching targets from the list.

        Args:
            source_entity: The caster/source of the action
            targets: List of potential target UUIDs

        Returns:
            Filtered list of target UUIDs that match the filter criteria.
        """
        # "all" means no filtering
        if self.valid_target_filter == "all":
            return targets

        # Get faction methods
        is_ally = getattr(source_entity, 'is_ally', None)
        is_enemy = getattr(source_entity, 'is_enemy', None)

        if is_ally is None or is_enemy is None:
            return targets  # Can't filter without faction methods

        filtered: List[UUID] = []
        for target_uuid in targets:
            target = BaseBlock.get(target_uuid)
            if target is None:
                continue

            if self.valid_target_filter == "enemies":
                if is_enemy(target):
                    filtered.append(target_uuid)
            elif self.valid_target_filter == "allies":
                if target_uuid != self.source_entity_uuid and is_ally(target):
                    filtered.append(target_uuid)
            elif self.valid_target_filter == "self_or_allies":
                if target_uuid == self.source_entity_uuid or is_ally(target):
                    filtered.append(target_uuid)
            else:
                # Unknown filter, include target
                filtered.append(target_uuid)

        return filtered

    def _validate_target_filter(self, all_targets: List[UUID]) -> Optional[str]:
        """Validate that all targets match the valid_target_filter.

        For POSITION_AOE: Skip validation since targets are already filtered in get_all_targets().
        For MULTI_ENTITY: Validate that explicitly chosen targets match the filter.

        Args:
            all_targets: List of target UUIDs to validate

        Returns:
            Error message string if validation fails, None if all valid.
        """
        # POSITION_AOE already filtered targets in get_all_targets(), skip validation
        if self.target_type == TargetType.POSITION_AOE:
            return None

        # Import Entity locally to avoid circular import
        entity = BaseBlock.get(self.source_entity_uuid)
        if entity is None:
            return "Source entity not found"

        # Need is_ally, is_enemy methods
        is_ally = getattr(entity, 'is_ally', None)
        is_enemy = getattr(entity, 'is_enemy', None)

        if is_ally is None or is_enemy is None:
            return None  # Can't validate without faction methods, skip check

        for target_uuid in all_targets:
            target = BaseBlock.get(target_uuid)
            if target is None:
                return f"Target {target_uuid} not found"

            target_name = getattr(target, 'name', str(target_uuid))

            if self.valid_target_filter == "enemies":
                if not is_enemy(target):
                    return f"{target_name} is not an enemy"
            elif self.valid_target_filter == "allies":
                if target_uuid == self.source_entity_uuid or not is_ally(target):
                    return f"{target_name} is not an ally"
            elif self.valid_target_filter == "self_or_allies":
                if target_uuid != self.source_entity_uuid and not is_ally(target):
                    return f"{target_name} is not self or an ally"
            # "all" allows any target

        return None  # Validation passed

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

        # Instance config: new UUID, not a template, not registered (ephemeral)
        update_dict: dict = {
            "uuid": uuid4(),
            "template": False,
            "use_register": False,  # Instances are ephemeral, don't need registry
        }
        update_dict.update(overrides)

        # model_copy preserves object types (aoe_shape subclasses, etc.)
        return self.model_copy(deep=True, update=update_dict)

    def check_costs(self) -> bool:
        """Check if entity can afford all costs (turn-based and resource-based)."""
        for cost in self.costs:
            # Check turn-based cost via evaluator
            if cost.evaluator is not None and not cost.evaluator(self.source_entity_uuid, cost.cost_type, cost.cost):
                return False
            # Check resource cost if present
            if cost.resource_cost > 0 and cost.resource_name:
                # Use BaseBlock.get() since Entity registers in BaseBlock._registry
                entity = BaseBlock.get(self.source_entity_uuid)
                if entity is None:
                    return False
                # Entity has action_economy, use getattr for type safety
                action_economy = getattr(entity, 'action_economy', None)
                if action_economy is None:
                    return False
                if not action_economy.can_afford_resource(cost.resource_name, cost.resource_cost):
                    return False
        return True

    def _create_declaration_event(self,parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        """Create the declaration event for this action. Override in subclasses if needed."""
        event = ActionEvent.from_costs(self.costs,self.source_entity_uuid,self.target_entity_uuid,parent_event,use_register=use_register)
        # Populate event with action info for combat log generation
        event.name = self.name or "Action"
        event.description = self.description
        # Populate source entity name if available
        entity = BaseBlock.get(self.source_entity_uuid)
        if entity is not None:
            event.source_entity_name = getattr(entity, 'name', None)
        return event

    
    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate if the action can be performed. Override this in subclasses to implement
        custom validation logic. Similar to BaseCondition._apply pattern.

        For MULTI_ENTITY and POSITION_AOE actions, this also validates:
        - That there are targets
        - allow_same_target constraint (MULTI_ENTITY only - AoE uses set, no duplicates)
        - valid_target_filter constraint
        """
        # Multi-target validation (both MULTI_ENTITY and POSITION_AOE)
        if self.target_type in (TargetType.MULTI_ENTITY, TargetType.POSITION_AOE):
            all_targets = self.get_all_targets()

            # Check: Do we have targets?
            if not all_targets:
                return declaration_event.cancel(status_message="No targets specified")

            # Check: Same-target constraint (only for MULTI_ENTITY - AoE uses set, no duplicates)
            if self.target_type == TargetType.MULTI_ENTITY and not self.allow_same_target:
                if len(set(all_targets)) != len(all_targets):
                    return declaration_event.cancel(
                        status_message="This action cannot target the same entity multiple times"
                    )

            # Check: Target filter (enemies/allies/etc) - applies to both
            filter_error = self._validate_target_filter(all_targets)
            if filter_error:
                return declaration_event.cancel(status_message=filter_error)

        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Succesfully validated action{self.name} for {declaration_event.source_entity_uuid}"
        )
    
    def pre_validate(self)-> bool:
        """Pre-validate the action. creates a non-registered event that is not added to the event queue and calls _validate"""
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
        """Apply the action's effects. Override this in subclasses to implement
        custom application logic. Similar to BaseCondition._apply pattern."""
        
        #during the apply the effect is applied
        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applying effect for {self.name}"
        )
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Succesfully applied action {self.name} for {execution_event.source_entity_uuid}"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply the costs of the action - implemented in subclasses"""
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
        # Create declaration event
        declaration_event = self._create_declaration_event(parent_event)
        if declaration_event is None:
            return None
        elif declaration_event.canceled:
            return declaration_event

        # Validate (includes MULTI_ENTITY-specific checks)
        if declaration_event.phase != EventPhase.DECLARATION:
            raise ValueError(f"Action {self.name} can only be validated in the declaration phase")
        execution_event = self._validate(declaration_event)
        if execution_event is None or execution_event.canceled:
            return execution_event
        if execution_event.phase not in [EventPhase.EXECUTION]:
            raise ValueError(f"Action {self.name} can only be applied in the execution phase")

        # === MULTI_ENTITY / POSITION_AOE convolution ===
        if self.target_type in (TargetType.MULTI_ENTITY, TargetType.POSITION_AOE):
            all_target_uuids = self.get_all_targets()

            # Store original target for restoration after loop
            original_target = self.target_entity_uuid

            # CONVOLUTION: Call _apply() for each target IN ORDER
            # Each per-target event becomes a CHILD of execution_event (not a phase)
            total_damage = 0

            for target_uuid in all_target_uuids:
                # Set current target
                self.target_entity_uuid = target_uuid

                # Get target entity name for combat log
                target_entity = BaseBlock.get(target_uuid)
                target_entity_name = getattr(target_entity, 'name', None) if target_entity else None

                # Create CHILD event for this target (not a phase of execution_event)
                # Key: parent_event is set, and lineage_uuid is NEW (not shared)
                per_target_event = execution_event.model_copy(update={
                    'uuid': uuid4(),  # New UUID
                    'lineage_uuid': uuid4(),  # NEW lineage (isolated save/damage tracking)
                    'parent_event': execution_event.uuid,  # Child of parent
                    'target_entity_uuid': target_uuid,
                    'target_entity_name': target_entity_name,
                    'children_events': [],
                    'lineage_children_events': [],
                })
                per_target_event = cast(ActionEvent, EventQueue.register(per_target_event))

                # Call normal _apply() with the child event
                result_event = self._apply(per_target_event)
                if result_event:
                    # CONTRACT: _apply() must set total_damage if it deals damage
                    damage = getattr(result_event, 'total_damage', 0) or 0
                    total_damage += damage

            # Restore original target
            self.target_entity_uuid = original_target

            # Parent completion - _collect_child_combat_logs() will find per-target children
            # via parent_event relationship (no target_results field needed)
            completion_event = execution_event.phase_to(
                EventPhase.COMPLETION,
                total_targets=len(all_target_uuids),
                total_damage=total_damage,
                aoe_position=self.end_position,  # Pass AoE center for combat log
                status_message=f"{self.name} affected {len(all_target_uuids)} targets for {total_damage} total damage"
            )
        else:
            # Existing single-target flow
            completion_event = self._apply(execution_event)

        if completion_event is None or completion_event.canceled:
            return completion_event
        if completion_event.phase not in [EventPhase.COMPLETION]:
            raise ValueError(f"Action {self.name} can only be completed in the completion phase")
        cost_event = self._apply_costs(completion_event)
        if cost_event is None or cost_event.canceled:
            return cost_event
        if cost_event.phase not in [EventPhase.COMPLETION]:
            raise ValueError(f"Action {self.name} can only be completed in the completion phase")
        return cost_event


class StructuredAction(BaseAction):
    """Implementation of BaseAction that uses the structured pipeline approach with
    prerequisites, consequences, and cost checking through event processors."""
    prerequisites: OrderedDict[str,EventProcessor] = Field(
        default_factory=OrderedDict,
        description="A dictionary of prerequisites, the key is the name of the prerequisite and the value is a callable that returns a boolean"
    )
    consequences: OrderedDict[str,EventProcessor] = Field(
        default_factory=OrderedDict,
        description="A dictionary of consequences, the key is the name of the consequence and the value is a callable that returns an Event"
    )
    revalidate_prerequisites: bool = Field(
        default=True,
        description="If true, the prerequisites will be revalidated when the event is applied"
    )
    cost_applier: Optional[EventProcessor] = Field(
        default=None,
        description="The event processor that will be used to apply costs"
    )
    
    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Implements the prerequisite checking pipeline."""
        if declaration_event.phase != EventPhase.DECLARATION:
            raise ValueError(f"Action {self.name} prerequisites can only be checked in declaration phase")

        current_event = declaration_event
        # Apply the prerequisites
        for prerequisite_name, prerequisite_function in self.prerequisites.items():
            prerequisite_event = prerequisite_function(current_event, current_event.source_entity_uuid)
            if prerequisite_event is None:
                return current_event.cancel(status_message=f"Prerequisite {prerequisite_name} failed for {self.name}")
            if prerequisite_event.canceled:
                return prerequisite_event
            current_event = prerequisite_event

        # Move to execution phase after all validations pass
        return current_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Successfully validated structured action {self.name} for {current_event.source_entity_uuid}"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Implements the consequence application pipeline."""
        if execution_event.phase != EventPhase.EXECUTION:
            raise ValueError(f"Action {self.name} consequences can only be applied in execution phase")

        current_event = execution_event
        # Move to effect phase for applying consequences
        effect_event = current_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applying consequences for {self.name}"
        )
        if effect_event.canceled:
            return effect_event

        current_event = effect_event
        # Apply consequences
        for consequence_name, consequence_function in self.consequences.items():
            consequence_event = consequence_function(current_event, current_event.source_entity_uuid)
            if consequence_event is None:
                return current_event.cancel(status_message=f"Consequence {consequence_name} failed for {self.name}")
            elif consequence_event.canceled:
                return consequence_event
            
            # Validate the consequence result if needed
            if self.revalidate_prerequisites:
                if consequence_event.phase not in [EventPhase.EXECUTION, EventPhase.EFFECT]:
                    raise ValueError(f"Consequence {consequence_name} returned event in invalid phase {consequence_event.phase}")
                validated_event = self._validate(consequence_event)
                if validated_event is None or validated_event.canceled:
                    return validated_event
                current_event = validated_event
            else:
                current_event = consequence_event

        # Move to completion phase
        return current_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Successfully completed structured action {self.name} for {current_event.source_entity_uuid}"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply the costs using the cost_applier if provided"""
        if self.cost_applier is not None:
            return self.cost_applier(completion_event, self.source_entity_uuid)
        return completion_event


# =============================================================================
# Available Actions Data Models
# =============================================================================

class AvailableTarget(BaseModel):
    """A valid target for an action, with index for selection.

    Used in CLI/UI patterns like 'attack 0' or 'move 3' to select targets.
    """
    index: int = Field(description="Index for selection (e.g., 'attack 0')")
    target_uuid: Optional[UUID] = Field(default=None, description="For ENTITY actions")
    position: Optional[Tuple[int, int]] = Field(default=None, description="For POSITION actions")
    # Additional info for display
    target_name: Optional[str] = Field(default=None, description="Entity name if ENTITY action")
    distance: Optional[int] = Field(default=None, description="Distance in feet")
    path_cost: Optional[int] = Field(default=None, description="Movement cost if POSITION action")
    # MULTI_ENTITY: additional targets beyond primary (for spells like Magic Missile)
    extra_target_uuids: Optional[List[UUID]] = Field(default=None, description="Additional targets for MULTI_ENTITY actions")
    # AoE-specific fields (for POSITION_AOE actions)
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

    # Display info
    display_name: str = Field(description="Human-readable name (e.g., 'Scimitar')")
    description: str = Field(default="", description="Action description")
    cost_type: CostType = Field(description="Type of cost (actions, bonus_actions, etc.)")
    cost_amount: int = Field(default=1, description="Cost amount (usually 1)")

    # For attacks - optional weapon info
    weapon_slot: Optional[str] = Field(default=None, description="Weapon slot for attacks")
    weapon_name: Optional[str] = Field(default=None, description="Weapon name for display (e.g., 'Scimitar')")

    # Attack classification
    is_attack: bool = Field(default=False, description="True if action is a damage-dealing attack")
    is_spell: bool = Field(default=False, description="True if action is a spell (SpellAction)")


class AvailableActionsResult(BaseModel):
    """Complete available actions query result.

    Returned by Entity.get_available_actions(). Groups actions by type for
    easy iteration and UI rendering.
    """
    entity_uuid: UUID = Field(description="UUID of the entity these actions are for")

    # Grouped by target type for easy iteration
    entity_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting entities (Attack)")
    position_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting positions (Move)")
    self_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Self-targeting actions (Dash, Dodge, etc.)")

    # State info
    remaining_movement: int = Field(default=0, description="Remaining movement in feet")

    @property
    def all_actions(self) -> List[AvailableActionInfo]:
        """Get all available actions as a flat list."""
        return self.entity_actions + self.position_actions + self.self_actions
