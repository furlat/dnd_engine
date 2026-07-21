"""Typed projection from a shared policy decision to controller execution data."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from ai.policy.contracts import (
    EndTurnIntent,
    ExecuteIntent,
    PolicyContext,
    PolicyDecision,
    PolicyGoal,
    TargetEffectOutcomeEvidence,
    WaitIntent,
)
from ai.policy.routines import RoutinePlan, RoutinePlanStatus, RoutinePurpose
from ai.protocol.control import ActionAffordance, ActionTarget
from ai.protocol.semantics import ActionSemantics, ActionTag, EffectDisposition


class AgentCommandType(str, Enum):
    """Command kinds emitted by a policy controller."""

    EXECUTE = "execute"
    END_TURN = "end_turn"
    WAIT = "wait"


class PolicyLogicalTag(str, Enum):
    """High-level meanings attached to a selected policy command."""

    ANTI_AOE_SPACING = "anti_aoe_spacing"
    CONTACT_MEMORY = "contact_memory"
    CONTROL_EFFECT = "control_effect"
    FOCUS_FIRE = "focus_fire"
    FORCED_MOVEMENT = "forced_movement"
    HAZARD_EXPLOIT = "hazard_exploit"
    INFORMATION_GAIN = "information_gain"
    MOBILITY_EXTENSION = "mobility_extension"
    PRESERVE_ACTION_ECONOMY = "preserve_action_economy"
    PRESSURE = "pressure"
    REVEAL_BOUNDARY = "reveal_boundary"
    RESOURCE_ACQUISITION = "resource_acquisition"
    RESOURCE_DISCIPLINE = "resource_discipline"
    ROUTE_PROGRESS = "route_progress"
    SELF_SETUP = "self_setup"
    SPACING_CONTROL = "spacing_control"
    SUPPORT_SETUP = "support_setup"
    TARGET_ALLOCATION = "target_allocation"


class AgentCommand(BaseModel):
    """Controller-ready projection of one shared policy intent."""

    command_type: AgentCommandType = Field(description="Selected command kind.")
    row_id: Optional[str] = Field(default=None, description="Decision-epoch row id for execution.")
    entity_uuid: Optional[str] = Field(default=None, description="Acting controlled entity UUID.")
    template_name: Optional[str] = Field(default=None, description="Selected action template name.")
    target_index: int = Field(default=0, description="Selected target index.")
    target_uuid: Optional[str] = Field(default=None, description="Selected entity or object UUID.")
    target_name: Optional[str] = Field(default=None, description="Selected target name when subjectively known.")
    target_position: Optional[Tuple[int, int]] = Field(default=None, description="Selected target position.")
    target_distance: Optional[int] = Field(default=None, description="Disclosed target distance in feet.")
    target_path_cost: Optional[int] = Field(default=None, description="Disclosed selected-path cost.")
    target_safe_path_cost: Optional[int] = Field(default=None, description="Disclosed safe-path cost.")
    target_path_hazardous: bool = Field(default=False, description="Whether the selected path crosses a known hazard.")
    target_path: List[Tuple[int, int]] = Field(default_factory=list, description="Disclosed selected path.")
    target_safe_path: List[Tuple[int, int]] = Field(default_factory=list, description="Disclosed safe selected path.")
    prefer_safe: bool = Field(default=True, description="Whether execution should prefer the disclosed safe path.")
    affected_entity_uuids: List[str] = Field(default_factory=list, description="Subjectively known affected entity UUIDs.")
    affected_entity_names: List[str] = Field(default_factory=list, description="Subjectively known affected entity names.")
    affected_entity_positions: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="Subjectively known affected entity positions.",
    )
    affected_enemy_count: int = Field(default=0, description="Known living hostiles affected by the selected target.")
    affected_controlled_count: int = Field(default=0, description="Known controlled entities affected by the selected target.")
    extra_target_uuids: Optional[List[str]] = Field(default=None, description="Additional selected target UUIDs.")
    extra_target_names: Optional[List[str]] = Field(default=None, description="Known names for additional targets.")
    extra_target_positions: Optional[List[Tuple[int, int]]] = Field(
        default=None,
        description="Known positions for additional targets.",
    )
    reference_entity_uuid: Optional[str] = Field(default=None, description="Entity used as non-target decision context.")
    reference_entity_name: Optional[str] = Field(default=None, description="Known name of the reference entity.")
    reference_entity_position: Optional[Tuple[int, int]] = Field(default=None, description="Known reference position.")
    reference_entity_distance_cells: Optional[int] = Field(default=None, description="Distance to the reference in cells.")
    spacing_floor_cells: Optional[int] = Field(default=None, description="Preferred hostile spacing floor.")
    spacing_anchor_position: Optional[Tuple[int, int]] = Field(default=None, description="Selected spacing anchor.")
    nearest_controlled_ally_distance_cells: Optional[int] = Field(
        default=None,
        description="Nearest controlled ally distance at the selected anchor.",
    )
    ally_spacing_floor_cells: Optional[int] = Field(default=None, description="Preferred controlled-ally spacing floor.")
    reason: str = Field(default="", description="Stable policy reason for selecting the command.")
    logical_tags: List[PolicyLogicalTag] = Field(default_factory=list, description="Inspectible command meanings.")
    routine_id: Optional[str] = Field(default=None, description="Routine that selected the command.")
    routine_step_id: Optional[str] = Field(default=None, description="Routine step realized by the command.")
    routine_next_step_id: Optional[str] = Field(default=None, description="Step stored after authoritative acceptance.")
    routine_target_uuid: Optional[str] = Field(default=None, description="Subjective routine target UUID.")
    routine_target_position: Optional[Tuple[int, int]] = Field(default=None, description="Known routine target position.")
    routine_started_epoch_index: Optional[int] = Field(default=None, description="Epoch where the routine began.")


def command_from_policy_decision(
    context: PolicyContext,
    decision: PolicyDecision,
    routine_plan: Optional[RoutinePlan] = None,
) -> Optional[AgentCommand]:
    """Project a shared decision without reconstructing world or action state."""
    context.validate_alignment()
    actor_uuid = context.facts.actor.actor_uuid
    intent = decision.selected.intent
    if isinstance(intent, EndTurnIntent):
        spacing = decision.selected.evidence.spacing
        logical_tags: list[PolicyLogicalTag] = []
        if decision.selected.goal is PolicyGoal.POSITION_AND_SURVIVAL and spacing is not None:
            logical_tags.append(PolicyLogicalTag.SPACING_CONTROL)
            if (
                spacing.nearest_controlled_ally_distance_cells is None
                or spacing.nearest_controlled_ally_distance_cells >= spacing.ally_spacing_floor_cells
            ):
                logical_tags.append(PolicyLogicalTag.ANTI_AOE_SPACING)
        reference = (
            context.world.known_entities.get(spacing.reference_entity_uuid)
            if spacing is not None and spacing.reference_entity_uuid is not None
            else None
        )
        return AgentCommand(
            command_type=AgentCommandType.END_TURN,
            entity_uuid=actor_uuid,
            reason=decision.selected.reason,
            logical_tags=logical_tags,
            reference_entity_uuid=spacing.reference_entity_uuid if spacing is not None else None,
            reference_entity_name=reference.name if reference is not None else None,
            reference_entity_position=spacing.reference_position if spacing is not None else None,
            reference_entity_distance_cells=spacing.current_distance_cells if spacing is not None else None,
            spacing_floor_cells=spacing.spacing_floor_cells if spacing is not None else None,
            spacing_anchor_position=spacing.anchor_position if spacing is not None else None,
            nearest_controlled_ally_distance_cells=(
                spacing.nearest_controlled_ally_distance_cells if spacing is not None else None
            ),
            ally_spacing_floor_cells=spacing.ally_spacing_floor_cells if spacing is not None else None,
        )
    if isinstance(intent, WaitIntent):
        return AgentCommand(
            command_type=AgentCommandType.WAIT,
            entity_uuid=actor_uuid,
            reason=intent.reason,
        )
    if not isinstance(intent, ExecuteIntent):
        return None

    action = context.facts.affordances.by_id.get(intent.row_id)
    if action is None or not context.execution_constraints.allows(action):
        return None
    if routine_plan is not None:
        if routine_plan.status is not RoutinePlanStatus.PROPOSED or routine_plan.proposal is None:
            raise ValueError("Policy command received a routine plan without a proposal")
        if routine_plan.proposal.intent != intent:
            raise ValueError("Policy command routine plan does not match the selected intent")
    target = _selected_target(action, routine_plan)
    extra_target_uuids = _validated_extra_targets(action, intent.extra_target_uuids)
    command = _execute_command_projection(
        context,
        action,
        target,
        decision,
        routine_plan,
        extra_target_uuids,
        prefer_safe=intent.prefer_safe,
    )
    if routine_plan is None:
        return command
    next_progress = routine_plan.next_progress_on_success
    return command.model_copy(update={
        "routine_id": routine_plan.routine_id,
        "routine_step_id": routine_plan.step_id,
        "routine_next_step_id": next_progress.step_id if next_progress is not None else None,
        "routine_target_uuid": routine_plan.target_uuid,
        "routine_target_position": routine_plan.target_position,
        "routine_started_epoch_index": (
            next_progress.started_epoch_index if next_progress is not None else None
        ),
    })


def _selected_target(action: ActionAffordance, routine_plan: Optional[RoutinePlan]) -> ActionTarget:
    """Resolve the exact target selected by a proposal or routine step."""
    selected_index = routine_plan.selected_target_index if routine_plan is not None else None
    if selected_index is not None:
        selected = next((target for target in action.targets if target.index == selected_index), None)
        if selected is None:
            raise ValueError("Routine target index is absent from the selected affordance")
        return selected
    if action.targets:
        return action.targets[0]
    return ActionTarget(index=0)


def _execute_command_projection(
    context: PolicyContext,
    action: ActionAffordance,
    target: ActionTarget,
    decision: PolicyDecision,
    routine_plan: Optional[RoutinePlan],
    extra_target_uuids: Tuple[str, ...],
    *,
    prefer_safe: bool,
) -> AgentCommand:
    """Project one execute intent using only its aligned subjective context."""
    affected_entity_uuids = _affected_entity_uuids(target, extra_target_uuids)
    entity_by_uuid = context.world.known_entities
    target_names_by_uuid = {
        option.target_uuid: option.target_name
        for option in (*action.targets, *action.target_options)
        if option.target_uuid is not None and option.target_name is not None
    }
    target_positions_by_uuid = {
        option.target_uuid: option.position
        for option in (*action.targets, *action.target_options)
        if option.target_uuid is not None and option.position is not None
    }

    def known_name(entity_uuid: str) -> Optional[str]:
        entity = entity_by_uuid.get(entity_uuid)
        return entity.name if entity is not None else target_names_by_uuid.get(entity_uuid)

    def known_position(entity_uuid: str) -> Optional[Tuple[int, int]]:
        entity = entity_by_uuid.get(entity_uuid)
        if entity is not None and entity.position is not None:
            return entity.position
        return target_positions_by_uuid.get(entity_uuid)

    affected_names = [
        name
        for entity_uuid in affected_entity_uuids
        for name in [known_name(entity_uuid)]
        if name is not None
    ]
    affected_positions = [
        position
        for entity_uuid in affected_entity_uuids
        for position in [known_position(entity_uuid)]
        if position is not None
    ]
    extra_names = [
        name
        for entity_uuid in extra_target_uuids
        for name in [known_name(entity_uuid)]
        if name is not None
    ] or None
    extra_positions = [
        position
        for entity_uuid in extra_target_uuids
        for position in [known_position(entity_uuid)]
        if position is not None
    ] or None
    hostile_uuids = set(context.facts.contacts.visible_hostile_uuids)
    controlled_uuids = {
        entity_uuid
        for entity_uuid in context.facts.contacts.controlled_entity_uuids
        for entity in [context.world.known_entities.get(entity_uuid)]
        if entity is not None and entity.is_dead is not True
    }
    affected_set = set(affected_entity_uuids)
    target_name = target.target_name
    if target_name is None and target.target_uuid is not None:
        known_entity = context.world.known_entities.get(target.target_uuid)
        known_object = context.world.known_objects.get(target.target_uuid)
        target_name = (
            known_entity.name
            if known_entity is not None
            else known_object.name if known_object is not None else None
        )
    logical_tags = _logical_tags(
        context.facts.affordances.semantics_by_row_id.get(action.row_id),
        decision.selected.goal,
        decision.selected.evidence.target_effects,
        routine_plan,
    )
    if len(affected_set & hostile_uuids) > 1 and PolicyLogicalTag.TARGET_ALLOCATION not in logical_tags:
        logical_tags.append(PolicyLogicalTag.TARGET_ALLOCATION)
    spacing = decision.selected.evidence.spacing
    if decision.selected.goal is PolicyGoal.POSITION_AND_SURVIVAL and spacing is not None:
        if PolicyLogicalTag.SPACING_CONTROL not in logical_tags:
            logical_tags.append(PolicyLogicalTag.SPACING_CONTROL)
        if (
            spacing.nearest_controlled_ally_distance_cells is not None
            and spacing.nearest_controlled_ally_distance_cells >= spacing.ally_spacing_floor_cells
            and PolicyLogicalTag.ANTI_AOE_SPACING not in logical_tags
        ):
            logical_tags.append(PolicyLogicalTag.ANTI_AOE_SPACING)
    reference = (
        context.world.known_entities.get(spacing.reference_entity_uuid)
        if spacing is not None and spacing.reference_entity_uuid is not None
        else None
    )
    return AgentCommand(
        command_type=AgentCommandType.EXECUTE,
        row_id=action.row_id,
        entity_uuid=context.facts.actor.actor_uuid,
        template_name=action.template_name,
        target_index=target.index,
        target_uuid=target.target_uuid,
        target_name=target_name,
        target_position=target.position,
        target_distance=target.distance,
        target_path_cost=target.path_cost,
        target_safe_path_cost=target.safe_path_cost,
        target_path_hazardous=target.is_path_hazardous,
        target_path=list(target.path),
        target_safe_path=list(target.safe_path),
        prefer_safe=prefer_safe,
        affected_entity_uuids=affected_entity_uuids,
        affected_entity_names=affected_names,
        affected_entity_positions=affected_positions,
        affected_enemy_count=len(affected_set & hostile_uuids),
        affected_controlled_count=len(affected_set & controlled_uuids),
        extra_target_uuids=list(extra_target_uuids) or None,
        extra_target_names=extra_names,
        extra_target_positions=extra_positions,
        reason=decision.selected.reason,
        logical_tags=logical_tags,
        reference_entity_uuid=spacing.reference_entity_uuid if spacing is not None else None,
        reference_entity_name=reference.name if reference is not None else None,
        reference_entity_position=spacing.reference_position if spacing is not None else None,
        reference_entity_distance_cells=spacing.current_distance_cells if spacing is not None else None,
        spacing_floor_cells=spacing.spacing_floor_cells if spacing is not None else None,
        spacing_anchor_position=spacing.anchor_position if spacing is not None else None,
        nearest_controlled_ally_distance_cells=(
            spacing.nearest_controlled_ally_distance_cells if spacing is not None else None
        ),
        ally_spacing_floor_cells=spacing.ally_spacing_floor_cells if spacing is not None else None,
    )


def _validated_extra_targets(
    action: ActionAffordance,
    extra_target_uuids: Tuple[str, ...],
) -> Tuple[str, ...]:
    """Reject an allocation that contradicts its authoritative affordance."""
    return action.validated_extra_target_uuids(extra_target_uuids)


def _affected_entity_uuids(target: ActionTarget, extra_target_uuids: Tuple[str, ...]) -> List[str]:
    """Return the stable union of disclosed and selected affected entities."""
    candidates = [
        *target.affected_entity_uuids,
        *([target.target_uuid] if target.target_uuid is not None else []),
        *extra_target_uuids,
    ]
    return list(dict.fromkeys(candidates))


def _logical_tags(
    semantics: Optional[ActionSemantics],
    goal: PolicyGoal,
    selected_target_effects: Tuple[TargetEffectOutcomeEvidence, ...] = tuple(),
    routine_plan: Optional[RoutinePlan] = None,
) -> List[PolicyLogicalTag]:
    """Map action capabilities and the selected policy purpose to command meanings."""
    semantic_tags = semantics.tags if semantics is not None else frozenset()
    selected_dispositions = {
        effect.disposition
        for effect in selected_target_effects
    }
    logical_tags: list[PolicyLogicalTag] = []

    def add(tag: PolicyLogicalTag) -> None:
        if tag not in logical_tags:
            logical_tags.append(tag)

    information_selected = (
        goal is PolicyGoal.INFORMATION_GATHERING
        or (
            routine_plan is not None
            and routine_plan.purpose is RoutinePurpose.SUBJECTIVE_DISCOVERY
        )
    )
    if information_selected and semantic_tags & {
        ActionTag.INFORMATION_REVEAL,
        ActionTag.INFORMATION_EXPLORE,
    }:
        add(PolicyLogicalTag.INFORMATION_GAIN)
    if information_selected and ActionTag.INFORMATION_REVEAL in semantic_tags:
        add(PolicyLogicalTag.REVEAL_BOUNDARY)
    if semantic_tags & {ActionTag.MOVEMENT_VOLUNTARY, ActionTag.MOVEMENT_TELEPORT}:
        add(PolicyLogicalTag.ROUTE_PROGRESS)
    if ActionTag.MOBILITY_EXTEND in semantic_tags:
        add(PolicyLogicalTag.MOBILITY_EXTENSION)
    if (
        semantic_tags & {ActionTag.SUPPORT_BUFF, ActionTag.SUPPORT_HEAL}
        and (
            not selected_target_effects
            or EffectDisposition.BENEFICIAL in selected_dispositions
        )
    ):
        add(PolicyLogicalTag.SUPPORT_SETUP)
    if ActionTag.SETUP_SELF in semantic_tags:
        add(PolicyLogicalTag.SELF_SETUP)
    if (
        semantic_tags & {ActionTag.CONTROL_HARD, ActionTag.CONTROL_SOFT}
        and (
            not selected_target_effects
            or EffectDisposition.HARMFUL in selected_dispositions
        )
    ):
        add(PolicyLogicalTag.CONTROL_EFFECT)
    if ActionTag.MOVEMENT_FORCED in semantic_tags:
        add(PolicyLogicalTag.FORCED_MOVEMENT)
    if ActionTag.RESOURCE_ACQUIRE in semantic_tags:
        add(PolicyLogicalTag.RESOURCE_ACQUISITION)
    if semantic_tags & {
        ActionTag.DAMAGE_SINGLE_TARGET,
        ActionTag.DAMAGE_MULTI_TARGET,
        ActionTag.DAMAGE_AREA,
        ActionTag.ATTACK_WEAPON,
        ActionTag.ATTACK_SPELL,
    }:
        add(PolicyLogicalTag.PRESSURE)
    if semantic_tags & {ActionTag.TARGET_MULTI, ActionTag.DAMAGE_MULTI_TARGET}:
        add(PolicyLogicalTag.TARGET_ALLOCATION)
    if (
        routine_plan is not None
        and routine_plan.purpose in {
            RoutinePurpose.OFFENSIVE_ENABLEMENT,
            RoutinePurpose.OFFENSIVE_AUGMENTATION,
            RoutinePurpose.OFFENSIVE_PURSUIT,
        }
        and routine_plan.step_id in {
            "enable",
            "augment",
            "approach",
            "extend_mobility",
        }
    ):
        add(PolicyLogicalTag.PRESSURE)
        add(PolicyLogicalTag.PRESERVE_ACTION_ECONOMY)
    if (
        routine_plan is not None
        and routine_plan.purpose is RoutinePurpose.SUBJECTIVE_DISCOVERY
        and routine_plan.step_id == "approach"
    ):
        add(PolicyLogicalTag.PRESERVE_ACTION_ECONOMY)
    return logical_tags
