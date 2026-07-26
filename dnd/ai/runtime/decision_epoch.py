"""Canonical decision-epoch construction from one live engine actor."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import gc
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional

from dnd.actions_functional import get_available_actions
from dnd.action_timing import reset_action_timing_recorder, set_action_timing_recorder
from dnd.blocks.base_item import UsableItem
from dnd.core.base_block import BaseBlock
from dnd.core.base_actions import (
    ActionAvailabilityStatus,
    AvailableActionInfo,
    AvailableActionsResult,
    AvailableTarget,
    BaseAction,
    TargetType,
)
from dnd.entity import Entity

from dnd.ai.contracts.control import (
    ActionAffordance,
    ActionBucket,
    ActionBucketRows,
    ActionCapability,
    ActionCostProfile,
    ActionEconomyState,
    ActionOutcomeProfile,
    ActionSourceDefinition,
    ActionTarget,
    AffordanceSet,
    CanonicalActionRow,
    DecisionEpoch,
    DecisionEpochReason,
    END_TURN_ROW_ID,
    EconomyGate,
    OpportunityAttackExposure,
    ResourcePool,
)
from dnd.ai.contracts.semantics import (
    ActionSemantics,
    ActionTag,
    action_semantics_ref,
    clear_action_semantics_ref_cache,
)
from dnd.ai.runtime.action_semantics import (
    action_semantics_for_available_action,
    end_turn_action_semantics,
)


@dataclass(frozen=True)
class DecisionEpochBuild:
    """Decision epoch plus the engine action result used to build it."""

    epoch: DecisionEpoch
    available_actions: AvailableActionsResult
    execution_authority: "DecisionEpochExecutionAuthority"


@dataclass(frozen=True)
class ActionExecutionBinding:
    """Private engine objects authorizing one exact decision-epoch row."""

    action_info: AvailableActionInfo
    target: Optional[AvailableTarget]


@dataclass(frozen=True)
class DecisionEpochExecutionAuthority:
    """Private exact action sources and target references for one epoch."""

    action_info_by_source_id: Mapping[str, AvailableActionInfo]
    target_by_row_id: Mapping[str, Optional[AvailableTarget]]

    def binding_for(
        self,
        affordance: ActionAffordance,
    ) -> Optional[ActionExecutionBinding]:
        """Resolve exact engine objects only for the selected public row."""
        action_info = self.action_info_by_source_id.get(affordance.source_action_id)
        if action_info is None or affordance.row_id not in self.target_by_row_id:
            return None
        return ActionExecutionBinding(
            action_info=action_info,
            target=self.target_by_row_id[affordance.row_id],
        )


@dataclass(frozen=True)
class _ActionRowDescriptor:
    """Build-local semantic and cost values shared by two epoch views."""

    semantics: ActionSemantics
    semantics_ref: str
    cost: ActionCostProfile
    outcome_profile: Optional[ActionOutcomeProfile]
    capability_tags: tuple[str, ...]
    affordance_tags: tuple[str, ...]


_CAPABILITY_VALUE_CACHE_MAX_SIZE = 4096
_capability_value_cache: OrderedDict[tuple[Any, ...], ActionCapability] = OrderedDict()
_ROW_DESCRIPTOR_CACHE_MAX_SIZE = 4096
_row_descriptor_cache: OrderedDict[tuple[Any, ...], _ActionRowDescriptor] = OrderedDict()


def clear_epoch_value_caches() -> None:
    """Clear bounded immutable values interned across decision epochs."""
    _capability_value_cache.clear()
    _row_descriptor_cache.clear()
    clear_action_semantics_ref_cache()


def build_decision_epoch(
    actor: Entity,
    *,
    epoch_namespace: str,
    round_number: int,
    turn_index: int,
    observation_cursor: int,
    reason: DecisionEpochReason = DecisionEpochReason.SNAPSHOT,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> Optional[DecisionEpochBuild]:
    """Build public rows and private authority for one authorized live actor."""
    started = time.perf_counter()
    if not actor.has_hp:
        _record_timing(record_timing, "resolve_actor_entity_ms", started)
        return None
    _record_timing(record_timing, "resolve_actor_entity_ms", started)

    started = time.perf_counter()
    if record_timing is None:
        available = get_available_actions(actor, legal_only=True)
    else:
        token = set_action_timing_recorder(record_timing)
        try:
            available = get_available_actions(actor, legal_only=True)
        finally:
            reset_action_timing_recorder(token)
    _record_timing(record_timing, "get_available_actions_ms", started)

    started = time.perf_counter()
    affordances, execution_authority = _build_affordance_set_and_execution_authority_from_actions(
        actor,
        available,
        observation_cursor,
        record_timing=record_timing,
    )
    _record_timing(record_timing, "build_affordance_set_ms", started)

    started = time.perf_counter()
    economy = _build_action_economy_state_from_actor(actor, available, affordances, record_timing)
    _record_timing(record_timing, "build_action_economy_ms", started)
    started = time.perf_counter()
    epoch_id = (
        f"{epoch_namespace}:actor={actor.uuid}:round={round_number}:"
        f"turn={turn_index}:obs={observation_cursor}:reason={reason.value}"
    )
    _record_timing(record_timing, "build_epoch_id_ms", started)
    started = time.perf_counter()
    epoch = DecisionEpoch.model_construct(
        epoch_id=epoch_id,
        epoch_index=observation_cursor,
        basis_observation_cursor=observation_cursor,
        reason=reason,
        actor_uuid=str(actor.uuid),
        round_number=round_number,
        turn_index=turn_index,
        economy=economy,
        affordances=affordances,
    )
    _record_timing(record_timing, "construct_epoch_model_ms", started)
    return DecisionEpochBuild(
        epoch=epoch,
        available_actions=available,
        execution_authority=execution_authority,
    )


def _record_timing(
    record_timing: Optional[Callable[[str, float], None]],
    phase: str,
    started_at: float,
) -> None:
    """Record an optional epoch-building timing phase."""
    if record_timing is not None:
        record_timing(phase, started_at)


def _register_semantic_contract(
    semantics: ActionSemantics,
    semantic_catalog: dict[str, ActionSemantics],
    semantic_references: dict[str, list[tuple[ActionSemantics, str]]],
) -> str:
    """Intern one structurally equal semantic contract before hashing it."""
    family = semantic_references.setdefault(semantics.semantic_id, [])
    for existing, existing_ref in family:
        if semantics == existing:
            return existing_ref
    semantics_ref = action_semantics_ref(semantics)
    family.append((semantics, semantics_ref))
    semantic_catalog[semantics_ref] = semantics
    return semantics_ref


def _build_affordance_set_from_actions(
    actor: Entity,
    actions: AvailableActionsResult,
    observation_cursor: int,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> AffordanceSet:
    """Flatten engine action objects directly into decision-epoch rows."""
    affordances, _authority = _build_affordance_set_and_execution_authority_from_actions(
        actor,
        actions,
        observation_cursor,
        record_timing=record_timing,
    )
    return affordances


def _build_affordance_set_and_execution_authority_from_actions(
    actor: Entity,
    actions: AvailableActionsResult,
    observation_cursor: int,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> tuple[AffordanceSet, DecisionEpochExecutionAuthority]:
    """Build public affordances and private exact execution authority together."""
    gc_was_enabled = gc.isenabled()
    if gc_was_enabled:
        gc.disable()
    try:
        semantic_catalog: dict[str, ActionSemantics] = {}
        semantic_references: dict[str, list[tuple[ActionSemantics, str]]] = {}
        target_values: dict[int, ActionTarget] = {}
        action_info_by_source_id: dict[str, AvailableActionInfo] = {}
        target_by_row_id: dict[str, Optional[AvailableTarget]] = {}
        used_row_ids: set[str] = set()
        started = time.perf_counter()
        row_descriptors = _build_action_row_descriptors(
            actions.all_actions,
            semantic_catalog,
            semantic_references,
        )
        _record_timing(record_timing, "build_row_descriptors_ms", started)
        capabilities = _build_action_capabilities(
            actor,
            semantic_catalog,
            semantic_references=semantic_references,
            registered_actions=actions.registered_action_variants,
            inventory_use_actions=actions.inventory_use_action_sources,
            available_action_rows=tuple(actions.all_actions),
            available_row_descriptors={
                _capability_row_lookup_key(row): row_descriptors[id(row)]
                for row in actions.all_actions
            },
            record_timing=record_timing,
        )
        affordances = _affordance_set_from_buckets(
            actor_uuid=str(actor.uuid),
            observation_cursor=observation_cursor,
            entity_actions=_build_affordance_rows_from_actions(
                "entity_actions",
                actions.entity_actions,
                semantic_catalog,
                semantic_references,
                row_descriptors,
                target_values,
                action_info_by_source_id,
                target_by_row_id,
                used_row_ids,
            ),
            position_actions=_build_affordance_rows_from_actions(
                "position_actions",
                actions.position_actions,
                semantic_catalog,
                semantic_references,
                row_descriptors,
                target_values,
                action_info_by_source_id,
                target_by_row_id,
                used_row_ids,
            ),
            self_actions=_build_affordance_rows_from_actions(
                "self_actions",
                actions.self_actions,
                semantic_catalog,
                semantic_references,
                row_descriptors,
                target_values,
                action_info_by_source_id,
                target_by_row_id,
                used_row_ids,
            ),
            object_actions=_build_affordance_rows_from_actions(
                "object_actions",
                actions.object_actions,
                semantic_catalog,
                semantic_references,
                row_descriptors,
                target_values,
                action_info_by_source_id,
                target_by_row_id,
                used_row_ids,
            ),
            capabilities=capabilities,
            semantic_catalog=semantic_catalog,
            semantic_references=semantic_references,
        )
        return affordances, DecisionEpochExecutionAuthority(
            action_info_by_source_id=MappingProxyType(action_info_by_source_id),
            target_by_row_id=MappingProxyType(target_by_row_id),
        )
    finally:
        if gc_was_enabled:
            gc.enable()


def _affordance_set_from_buckets(
    actor_uuid: str,
    observation_cursor: int,
    entity_actions: list[ActionAffordance] | ActionBucketRows,
    position_actions: list[ActionAffordance] | ActionBucketRows,
    self_actions: list[ActionAffordance] | ActionBucketRows,
    object_actions: list[ActionAffordance] | ActionBucketRows,
    capabilities: Optional[list[ActionCapability]] = None,
    semantic_catalog: Optional[dict[str, ActionSemantics]] = None,
    semantic_references: Optional[
        dict[str, list[tuple[ActionSemantics, str]]]
    ] = None,
) -> AffordanceSet:
    """Build an affordance set from already-flattened action buckets."""
    catalog = dict(semantic_catalog or {})
    references = semantic_references if semantic_references is not None else {}
    semantics = end_turn_action_semantics()
    semantics_ref = _register_semantic_contract(semantics, catalog, references)
    special_source = ActionSourceDefinition.model_construct(
        source_action_id="special_commands|source=0",
        bucket="special_commands",
        template_name="End Turn",
        semantic_key="runtime.command.EndTurn",
        base_template_name="End Turn",
        display_name="End Turn",
        description="End the active actor turn.",
        action_category="special",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile.model_construct(
            action_cost=0,
            bonus_action_cost=0,
            reaction_cost=0,
            movement_cost=0,
            consumes_attack_slot=False,
            spell_slot_cost=None,
            resource_costs={},
            item_charge_costs={},
            affordability="affordable",
            affordability_reasons=[],
        ),
        target_options=(),
        num_projectiles=None,
        allow_same_target=None,
        is_item_use=False,
        source_item_uuid=None,
        weapon_slot=None,
        weapon_name=None,
        damage_types=(),
        outcome_profile=None,
        spell_level=None,
        cast_at_level=None,
        is_spell_variant=False,
        requires_concentration=False,
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics_ref,
        tags=tuple(_display_tags("special", "self", semantics)),
    )
    special = CanonicalActionRow(
        row_id=END_TURN_ROW_ID,
        source=special_source,
        targets=(ActionTarget.model_construct(
            index=0,
            target_uuid=None,
            target_name=None,
            position=None,
            distance=None,
            path_cost=None,
            safe_path_cost=None,
            is_path_hazardous=False,
            path=(),
            safe_path=(),
            opportunity_attack_exposures=(),
            safe_path_opportunity_attack_exposures=(),
            affected_entity_uuids=(),
            affected_positions=(),
        ),),
    )
    return AffordanceSet.model_construct(
        actor_uuid=actor_uuid,
        computed_at_observation_cursor=observation_cursor,
        entity_actions=_as_action_bucket_rows(entity_actions),
        position_actions=_as_action_bucket_rows(position_actions),
        self_actions=_as_action_bucket_rows(self_actions),
        object_actions=_as_action_bucket_rows(object_actions),
        special_commands=ActionBucketRows((special,)),
        capabilities=tuple(capabilities or ()),
        semantic_catalog=catalog,
    )


def _as_action_bucket_rows(
    rows: list[ActionAffordance] | ActionBucketRows,
) -> ActionBucketRows:
    """Return compact canonical rows without materializing lazy bucket views."""
    if isinstance(rows, ActionBucketRows):
        return rows
    return ActionBucketRows(tuple(
        CanonicalActionRow(
            row_id=row.row_id,
            source=row.source,
            targets=tuple(row.targets),
        )
        for row in rows
    ))


def _build_action_capabilities(
    actor: Entity,
    semantic_catalog: dict[str, ActionSemantics],
    *,
    semantic_references: Optional[
        dict[str, list[tuple[ActionSemantics, str]]]
    ] = None,
    registered_actions: Optional[tuple[BaseAction, ...]] = None,
    inventory_use_actions: Optional[tuple[BaseAction, ...]] = None,
    available_action_rows: Optional[tuple[AvailableActionInfo, ...]] = None,
    available_row_descriptors: Optional[
        dict[tuple[str, str, Optional[str]], _ActionRowDescriptor]
    ] = None,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> list[ActionCapability]:
    """Describe actor-owned action configurations independently of legal rows.

    Args:
        actor: Active entity whose own actions are being described.
        semantic_catalog: Epoch catalog updated with capability semantics.

    Returns:
        Deterministically ordered capabilities containing no targets or row IDs.
    """
    total_started = time.perf_counter()
    started = time.perf_counter()
    registered_variants = (
        registered_actions
        if registered_actions is not None
        else tuple(
            variant
            for template in actor.registered_actions
            for variant in template.get_discovery_variants(actor)
        )
    )
    registered_sources = [(variant, None) for variant in registered_variants]
    _record_timing(record_timing, "build_capabilities.registered_variants_ms", started)

    started = time.perf_counter()
    item_actions = (
        inventory_use_actions
        if inventory_use_actions is not None
        else tuple(actor.inventory.get_all_use_actions(actor.uuid))
    )
    item_sources = [
        (
            template,
            str(template.source_item_uuid) if template.source_item_uuid else None,
        )
        for template in item_actions
    ]
    _record_timing(record_timing, "build_capabilities.inventory_sources_ms", started)

    started = time.perf_counter()
    environment_sources = [
        (template, str(object_uuid))
        for object_uuid in sorted(actor.senses.objects, key=str)
        for obj in [BaseBlock.get(object_uuid)]
        if isinstance(obj, UsableItem)
        and obj.should_include_in_available_object_actions()
        for template in obj.get_use_actions(actor.uuid)
    ]
    _record_timing(record_timing, "build_capabilities.environment_sources_ms", started)

    capabilities: dict[str, ActionCapability] = {}
    references = semantic_references if semantic_references is not None else {}
    available_rows_by_source = {
        _capability_row_lookup_key(row): row
        for row in available_action_rows or ()
    }
    descriptors_by_source = available_row_descriptors or {}
    started = time.perf_counter()
    for template, source_item_uuid in (
        *registered_sources,
        *item_sources,
        *environment_sources,
    ):
        source_key = _capability_template_lookup_key(template, source_item_uuid)
        capability = _action_capability_from_template(
            actor,
            template,
            source_item_uuid=source_item_uuid,
            semantic_catalog=semantic_catalog,
            semantic_references=references,
            available_row=available_rows_by_source.get(source_key),
            available_row_descriptor=descriptors_by_source.get(source_key),
        )
        capabilities[capability.capability_id] = capability
    _record_timing(record_timing, "build_capabilities.metadata_and_models_ms", started)
    result = [capabilities[key] for key in sorted(capabilities)]
    _record_timing(record_timing, "build_capabilities.total_ms", total_started)
    return result


def _capability_template_lookup_key(
    template: BaseAction,
    source_item_uuid: Optional[str],
) -> tuple[str, str, Optional[str]]:
    """Return the discovery identity shared by a variant and its legal row."""
    return (
        template.get_discovery_template_name(),
        _enum_value(template.effective_target_type) or "unknown",
        source_item_uuid,
    )


def _capability_row_lookup_key(
    row: AvailableActionInfo,
) -> tuple[str, str, Optional[str]]:
    """Return the discovery identity of one already-built action row."""
    return (
        row.template_name,
        _enum_value(row.target_type) or "unknown",
        str(row.source_item_uuid) if row.source_item_uuid is not None else None,
    )


def _action_capability_from_template(
    actor: Entity,
    template: BaseAction,
    *,
    source_item_uuid: Optional[str],
    semantic_catalog: dict[str, ActionSemantics],
    semantic_references: dict[str, list[tuple[ActionSemantics, str]]],
    available_row: Optional[AvailableActionInfo] = None,
    available_row_descriptor: Optional[_ActionRowDescriptor] = None,
) -> ActionCapability:
    """Build one non-executable capability from an actor-owned template."""
    weapon_slot_value = getattr(template, "weapon_slot", None)
    weapon_slot = _enum_value(weapon_slot_value) if weapon_slot_value is not None else None
    row = available_row
    if row is None:
        can_afford = template.check_target_independent_costs()
        row = actor._make_action_info(
            template_name=template.get_discovery_template_name(),
            target_type=template.effective_target_type,
            valid_targets=[],
            can_afford=can_afford,
            availability_status=(
                ActionAvailabilityStatus.NO_VALID_TARGETS
                if can_afford
                else ActionAvailabilityStatus.SOURCE_UNAFFORDABLE
            ),
            template=template,
            display_name=template.get_discovery_display_name(),
            weapon_slot=weapon_slot,
            is_item_use=source_item_uuid is not None,
            source_item_uuid=template.source_item_uuid,
        )
    descriptor = available_row_descriptor
    if descriptor is None:
        descriptor = _describe_action_row(
            row,
            semantic_catalog,
            semantic_references,
        )
    action_range = template.get_range()
    if action_range is None and weapon_slot_value is not None:
        action_range = actor.get_weapon_range(weapon_slot_value)
    target_type = template.effective_target_type
    base_spell_level = getattr(template, "spell_level", None) if template.is_spell else None
    cast_at_level = getattr(template, "cast_at_level", None) if template.is_spell else None
    capability_id = "|".join(
        (
            row.semantic_key,
            _enum_value(target_type) or "unknown",
            weapon_slot or "none",
            str(cast_at_level) if cast_at_level is not None else "none",
            source_item_uuid or "none",
        )
    )
    action_category = _enum_value(template.action_category) or "unknown"
    target_type_value = _enum_value(target_type) or "unknown"
    range_type = _enum_value(action_range.type) if action_range is not None else None
    normal_range_feet = action_range.normal if action_range is not None else None
    long_range_feet = action_range.long if action_range is not None else None
    requires_line_of_sight = target_type in {
        TargetType.ENTITY,
        TargetType.MULTI_ENTITY,
        TargetType.POSITION_LOS,
        TargetType.POSITION_AOE,
    }
    capability_tags = tuple(descriptor.capability_tags)
    cache_key = (
        str(actor.uuid),
        capability_id,
        row.semantic_key,
        action_category,
        target_type_value,
        _action_cost_profile_cache_key(descriptor.cost),
        range_type,
        normal_range_feet,
        long_range_feet,
        requires_line_of_sight,
        template.valid_target_filter,
        weapon_slot,
        base_spell_level,
        cast_at_level,
        source_item_uuid,
        descriptor.outcome_profile,
        descriptor.semantics.semantic_id,
        descriptor.semantics_ref,
        capability_tags,
    )
    cached = _capability_value_cache.get(cache_key)
    if cached is not None:
        _capability_value_cache.move_to_end(cache_key)
        return cached
    capability = ActionCapability.model_construct(
        capability_id=capability_id,
        semantic_key=row.semantic_key,
        action_category=action_category,
        target_type=target_type_value,
        cost=descriptor.cost,
        range_type=range_type,
        normal_range_feet=normal_range_feet,
        long_range_feet=long_range_feet,
        requires_line_of_sight=requires_line_of_sight,
        valid_target_filter=template.valid_target_filter,
        weapon_slot=weapon_slot,
        base_spell_level=base_spell_level,
        cast_at_level=cast_at_level,
        source_item_uuid=source_item_uuid,
        outcome_profile=descriptor.outcome_profile,
        semantic_id=descriptor.semantics.semantic_id,
        semantics_ref=descriptor.semantics_ref,
        tags=capability_tags,
    )
    _capability_value_cache[cache_key] = capability
    if len(_capability_value_cache) > _CAPABILITY_VALUE_CACHE_MAX_SIZE:
        _capability_value_cache.popitem(last=False)
    return capability


def _action_cost_profile_cache_key(cost: ActionCostProfile) -> tuple[Any, ...]:
    """Return the complete immutable value key for one capability cost."""
    return (
        cost.action_cost,
        cost.bonus_action_cost,
        cost.reaction_cost,
        cost.movement_cost,
        cost.consumes_attack_slot,
        cost.spell_slot_cost,
        tuple(sorted(cost.resource_costs.items())),
        tuple(sorted(cost.item_charge_costs.items())),
        cost.affordability,
        tuple(cost.affordability_reasons),
    )


def _build_action_row_descriptors(
    rows: list[AvailableActionInfo],
    semantic_catalog: dict[str, ActionSemantics],
    semantic_references: dict[str, list[tuple[ActionSemantics, str]]],
) -> dict[int, _ActionRowDescriptor]:
    """Describe each available source row once within one epoch build."""
    return {
        id(row): _describe_action_row(row, semantic_catalog, semantic_references)
        for row in rows
    }


def _describe_action_row(
    row: AvailableActionInfo,
    semantic_catalog: dict[str, ActionSemantics],
    semantic_references: dict[str, list[tuple[ActionSemantics, str]]],
) -> _ActionRowDescriptor:
    """Derive immutable semantic and cost values for one source action row."""
    cache_key = _action_row_descriptor_cache_key(row)
    cached = _row_descriptor_cache.get(cache_key)
    if cached is not None:
        _row_descriptor_cache.move_to_end(cache_key)
        semantics_ref = _register_semantic_contract(
            cached.semantics,
            semantic_catalog,
            semantic_references,
        )
        if semantics_ref == cached.semantics_ref:
            return cached
        return _ActionRowDescriptor(
            semantics=cached.semantics,
            semantics_ref=semantics_ref,
            cost=cached.cost,
            outcome_profile=cached.outcome_profile,
            capability_tags=cached.capability_tags,
            affordance_tags=cached.affordance_tags,
        )

    semantics = action_semantics_for_available_action(row)
    semantics_ref = _register_semantic_contract(
        semantics,
        semantic_catalog,
        semantic_references,
    )
    descriptor = _ActionRowDescriptor(
        semantics=semantics,
        semantics_ref=semantics_ref,
        cost=_action_cost_profile_from_action(row),
        outcome_profile=(
            ActionOutcomeProfile.model_validate(row.outcome_profile.model_dump(mode="json"))
            if row.outcome_profile is not None
            else None
        ),
        capability_tags=tuple(sorted(tag.value for tag in semantics.tags)),
        affordance_tags=tuple(_affordance_tags_from_action(row, semantics)),
    )
    _row_descriptor_cache[cache_key] = descriptor
    if len(_row_descriptor_cache) > _ROW_DESCRIPTOR_CACHE_MAX_SIZE:
        _row_descriptor_cache.popitem(last=False)
    return descriptor


def _action_row_descriptor_cache_key(row: AvailableActionInfo) -> tuple[Any, ...]:
    """Return the complete public value key for row descriptor derivation."""
    return (
        row.template_name,
        row.semantic_key,
        _enum_value(row.target_type),
        row.can_afford,
        row.description,
        _enum_value(row.cost_type),
        row.cost_amount,
        tuple(
            (
                cost.name,
                _enum_value(cost.cost_type),
                cost.cost,
                cost.resource_name,
                cost.resource_cost,
            )
            for cost in row.costs
        ),
        row.weapon_slot,
        row.weapon_name,
        tuple(row.damage_types),
        _frozen_model_key(row.outcome_profile),
        _frozen_model_key(row.self_setup_profile),
        _frozen_model_key(row.target_effect_profile),
        _frozen_model_key(row.world_effect_profile),
        _enum_value(row.action_category),
        row.base_template_name,
        row.spell_level,
        row.cast_at_level,
        row.is_spell_variant,
        row.requires_concentration,
        row.num_projectiles,
        row.allow_same_target,
        row.is_item_use,
        str(row.source_item_uuid) if row.source_item_uuid is not None else None,
        row.item_stack_count,
        row.item_charge_cost,
        row.fixed_healing,
    )


def _frozen_model_key(value: Any) -> Any:
    """Return a hashable JSON-mode value for a small Pydantic model."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return _freeze_json_value(value.model_dump(mode="json"))
    return _freeze_json_value(value)


def _freeze_json_value(value: Any) -> Any:
    """Turn JSON-like model data into a hashable deterministic structure."""
    if isinstance(value, dict):
        return tuple(
            (key, _freeze_json_value(item))
            for key, item in sorted(value.items(), key=lambda row: str(row[0]))
        )
    if isinstance(value, list):
        return tuple(_freeze_json_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_json_value(item) for item in value)
    return value


def _build_affordance_rows_from_actions(
    bucket: ActionBucket,
    rows: list[AvailableActionInfo],
    semantic_catalog: Optional[dict[str, ActionSemantics]] = None,
    semantic_references: Optional[
        dict[str, list[tuple[ActionSemantics, str]]]
    ] = None,
    row_descriptors: Optional[dict[int, _ActionRowDescriptor]] = None,
    target_values: Optional[dict[int, ActionTarget]] = None,
    action_info_by_source_id: Optional[dict[str, AvailableActionInfo]] = None,
    target_by_row_id: Optional[dict[str, Optional[AvailableTarget]]] = None,
    used_row_ids: Optional[set[str]] = None,
) -> ActionBucketRows:
    """Flatten one engine action bucket without JSON round-tripping."""
    affordances: list[CanonicalActionRow] = []
    references = semantic_references if semantic_references is not None else {}
    for action_index, row in enumerate(rows):
        targets = row.valid_targets
        if not targets and target_by_row_id is not None:
            # Public decision epochs are executable command surfaces. Discovery
            # may retain an affordable action definition with no currently
            # legal targets for diagnostics, but there is no private target
            # authority that could execute such a row.
            continue
        source_action_id = f"{bucket}|source={action_index}"
        if action_info_by_source_id is not None:
            action_info_by_source_id[source_action_id] = row
        target_type = _enum_value(row.target_type)
        target_options = tuple(
            _action_target_from_available_target(target, target_values)
            for target in targets
        ) if _should_keep_target_options_for_action(bucket, row) else ()
        action_category = _enum_value(row.action_category)
        descriptor = row_descriptors.get(id(row)) if row_descriptors is not None else None
        if descriptor is None:
            if semantic_catalog is not None:
                descriptor = _describe_action_row(row, semantic_catalog, references)
            else:
                semantics = action_semantics_for_available_action(row)
                descriptor = _ActionRowDescriptor(
                    semantics=semantics,
                    semantics_ref=action_semantics_ref(semantics),
                    cost=_action_cost_profile_from_action(row),
                    outcome_profile=(
                        ActionOutcomeProfile.model_validate(row.outcome_profile.model_dump(mode="json"))
                        if row.outcome_profile is not None
                        else None
                    ),
                    capability_tags=tuple(sorted(tag.value for tag in semantics.tags)),
                    affordance_tags=tuple(_affordance_tags_from_action(row, semantics)),
                )
        source_item_uuid = str(row.source_item_uuid) if row.source_item_uuid else None
        display_name = row.display_name or row.template_name
        source = _action_source_from_action(
            bucket,
            row,
            target_options,
            source_action_id=source_action_id,
            cost=descriptor.cost,
            action_category=action_category,
            target_type=target_type,
            tags=descriptor.affordance_tags,
            semantic_id=descriptor.semantics.semantic_id,
            semantics_ref=descriptor.semantics_ref,
            source_item_uuid=source_item_uuid,
            display_name=display_name,
            outcome_profile=descriptor.outcome_profile,
        )
        if not targets:
            placeholder_target = AvailableTarget(index=0)
            row_id = _reserve_affordance_row_id(
                _affordance_row_id_from_action(
                    bucket,
                    row,
                    placeholder_target,
                    action_index,
                    0,
                ),
                source_action_id,
                0,
                used_row_ids,
            )
            affordances.append(_affordance_from_source(
                source,
                None,
                row_id,
            ))
            if target_by_row_id is not None:
                target_by_row_id[row_id] = None
            continue
        for target_index, target in enumerate(targets):
            normalized_target = _action_target_from_available_target(
                target,
                target_values,
            )
            row_id = _reserve_affordance_row_id(
                _affordance_row_id_from_action(
                    bucket,
                    row,
                    target,
                    action_index,
                    target_index,
                ),
                source_action_id,
                target_index,
                used_row_ids,
            )
            affordances.append(_affordance_from_source(
                source,
                normalized_target,
                row_id,
            ))
            if target_by_row_id is not None:
                target_by_row_id[row_id] = target
    return ActionBucketRows(affordances)


def _reserve_affordance_row_id(
    candidate: str,
    source_action_id: str,
    target_index: int,
    used_row_ids: Optional[set[str]],
) -> str:
    """Reserve a unique opaque command identity inside one decision epoch."""
    if used_row_ids is None:
        return candidate
    if candidate not in used_row_ids:
        used_row_ids.add(candidate)
        return candidate
    disambiguated = f"{candidate}|{source_action_id}|target={target_index}"
    suffix = 1
    while disambiguated in used_row_ids:
        disambiguated = (
            f"{candidate}|{source_action_id}|target={target_index}|duplicate={suffix}"
        )
        suffix += 1
    used_row_ids.add(disambiguated)
    return disambiguated


def _action_source_from_action(
    bucket: ActionBucket,
    row: AvailableActionInfo,
    target_options: tuple[ActionTarget, ...],
    *,
    source_action_id: str,
    cost: ActionCostProfile,
    action_category: str,
    target_type: str,
    tags: tuple[str, ...],
    semantic_id: str,
    semantics_ref: str,
    source_item_uuid: Optional[str],
    display_name: str,
    outcome_profile: Optional[ActionOutcomeProfile],
) -> ActionSourceDefinition:
    """Build metadata shared by all target rows of one discovered action."""
    return ActionSourceDefinition.model_construct(
        source_action_id=source_action_id,
        bucket=bucket,
        template_name=row.template_name,
        semantic_key=row.semantic_key,
        base_template_name=row.base_template_name or row.template_name,
        display_name=display_name,
        description=row.description,
        action_category=action_category,
        target_type=target_type,
        can_afford=row.can_afford,
        cost=cost,
        target_options=target_options,
        num_projectiles=row.num_projectiles,
        allow_same_target=row.allow_same_target,
        is_item_use=row.is_item_use,
        source_item_uuid=source_item_uuid,
        weapon_slot=row.weapon_slot,
        weapon_name=row.weapon_name,
        damage_types=tuple(row.damage_types),
        outcome_profile=outcome_profile,
        spell_level=row.spell_level,
        cast_at_level=row.cast_at_level,
        is_spell_variant=row.is_spell_variant,
        requires_concentration=row.requires_concentration,
        semantic_id=semantic_id,
        semantics_ref=semantics_ref,
        tags=tags,
    )


def _affordance_from_source(
    source: ActionSourceDefinition,
    target: Optional[ActionTarget],
    row_id: str,
) -> CanonicalActionRow:
    """Build one executable row from shared source metadata and one target."""
    return CanonicalActionRow(
        row_id=row_id,
        source=source,
        targets=(target,) if target is not None else (),
    )


def _should_keep_target_options_for_action(bucket: ActionBucket, row: AvailableActionInfo) -> bool:
    """Return whether direct affordance rows should carry all source targets."""
    return _action_row_needs_target_options(
        _enum_value(row.target_type),
        row.num_projectiles,
        row.allow_same_target,
    )


def _action_row_needs_target_options(
    target_type: Optional[str],
    num_projectiles: Optional[int],
    allow_same_target: Optional[bool],
) -> bool:
    """Return whether one flattened row needs the source target-option set."""
    if target_type == "multi_entity":
        return True
    if num_projectiles is not None and num_projectiles > 1:
        return True
    return allow_same_target is not None


def _action_target_from_available_target(
    target: AvailableTarget,
    target_values: Optional[dict[int, ActionTarget]] = None,
) -> ActionTarget:
    """Build or reuse one immutable subjective value for an engine target."""
    target_identity = id(target)
    if target_values is not None:
        cached = target_values.get(target_identity)
        if cached is not None:
            return cached
    result = ActionTarget.model_construct(
        index=target.index,
        target_uuid=str(target.target_uuid) if target.target_uuid else None,
        target_name=target.target_name,
        position=target.position,
        distance=target.distance,
        path_cost=target.path_cost,
        safe_path_cost=target.safe_path_cost,
        is_path_hazardous=target.is_path_hazardous,
        path=tuple(target.path or ()),
        safe_path=tuple(target.safe_path or ()),
        opportunity_attack_exposures=tuple(
            OpportunityAttackExposure.model_validate(
                exposure.model_dump(mode="json")
            )
            for exposure in target.opportunity_attack_exposures
        ),
        safe_path_opportunity_attack_exposures=tuple(
            OpportunityAttackExposure.model_validate(
                exposure.model_dump(mode="json")
            )
            for exposure in target.safe_path_opportunity_attack_exposures
        ),
        affected_entity_uuids=tuple(
            str(uuid) for uuid in (target.affected_entity_uuids or ())
        ),
        affected_positions=tuple(target.affected_positions or ()),
    )
    if target_values is not None:
        target_values[target_identity] = result
    return result


def _action_cost_profile_from_action(row: AvailableActionInfo) -> ActionCostProfile:
    """Build a normalized cost profile from an engine action row."""
    if row.costs:
        profile = _action_cost_profile_from_cost_rows(
            row.costs,
            can_afford=row.can_afford,
        )
    else:
        cost_type = _enum_value(row.cost_type)
        cost_amount = int(row.cost_amount or 0)
        profile = _action_cost_profile_from_values(cost_type, cost_amount, row.can_afford)
    if row.source_item_uuid is None or row.item_charge_cost <= 0:
        return profile
    return profile.model_copy(update={
        "item_charge_costs": {
            str(row.source_item_uuid): row.item_charge_cost,
        },
    })


def _action_cost_profile_from_values(
    cost_type: Optional[str],
    cost_amount: int,
    can_afford: bool,
) -> ActionCostProfile:
    """Build a normalized cost profile from primitive values."""
    affordability = "affordable" if can_afford else "unaffordable"
    kwargs: dict[str, Any] = {
        "action_cost": 0,
        "bonus_action_cost": 0,
        "reaction_cost": 0,
        "movement_cost": 0,
        "consumes_attack_slot": False,
        "spell_slot_cost": None,
        "resource_costs": {},
        "item_charge_costs": {},
        "affordability": affordability,
        "affordability_reasons": [] if affordability == "affordable" else ["engine reported the row as unaffordable"],
    }
    if cost_type == "actions":
        kwargs["action_cost"] = cost_amount
    elif cost_type == "bonus_actions":
        kwargs["bonus_action_cost"] = cost_amount
    elif cost_type == "reactions":
        kwargs["reaction_cost"] = cost_amount
    elif cost_type == "movement":
        kwargs["movement_cost"] = cost_amount
    elif isinstance(cost_type, str) and cost_type.startswith("spell_slot_"):
        kwargs["spell_slot_cost"] = int(cost_type.removeprefix("spell_slot_"))
    return ActionCostProfile.model_construct(**kwargs)


def _action_cost_profile_from_cost_rows(
    costs: list[Any],
    *,
    can_afford: bool,
) -> ActionCostProfile:
    """Build a normalized cost profile from full engine cost rows."""
    affordability = "affordable" if can_afford else "unaffordable"
    kwargs: dict[str, Any] = {
        "action_cost": 0,
        "bonus_action_cost": 0,
        "reaction_cost": 0,
        "movement_cost": 0,
        "consumes_attack_slot": False,
        "spell_slot_cost": None,
        "resource_costs": {},
        "item_charge_costs": {},
        "affordability": affordability,
        "affordability_reasons": [] if affordability == "affordable" else ["engine reported the row as unaffordable"],
    }
    for cost in costs:
        if isinstance(cost, dict):
            cost_type = cost.get("cost_type")
            amount = int(cost.get("cost") or 0)
            resource_name = cost.get("resource_name")
            resource_cost = int(cost.get("resource_cost") or 0)
        else:
            cost_type = _enum_value(getattr(cost, "cost_type", None))
            amount = int(getattr(cost, "cost", 0) or 0)
            resource_name = getattr(cost, "resource_name", None)
            resource_cost = int(getattr(cost, "resource_cost", 0) or 0)
        _merge_cost_profile_kwargs(kwargs, cost_type, amount, resource_name, resource_cost)
    return ActionCostProfile.model_construct(**kwargs)


def _merge_cost_profile_kwargs(
    kwargs: dict[str, Any],
    cost_type: Optional[str],
    amount: int,
    resource_name: Any,
    resource_cost: int,
) -> None:
    """Merge one engine cost row into an action cost profile payload."""
    if cost_type == "actions":
        kwargs["action_cost"] = int(kwargs.get("action_cost", 0)) + amount
    elif cost_type == "bonus_actions":
        kwargs["bonus_action_cost"] = int(kwargs.get("bonus_action_cost", 0)) + amount
    elif cost_type == "reactions":
        kwargs["reaction_cost"] = int(kwargs.get("reaction_cost", 0)) + amount
    elif cost_type == "movement":
        kwargs["movement_cost"] = int(kwargs.get("movement_cost", 0)) + amount
    elif isinstance(cost_type, str) and cost_type.startswith("spell_slot_"):
        kwargs["spell_slot_cost"] = int(cost_type.removeprefix("spell_slot_"))
    if resource_name == "extra_attacks" and resource_cost > 0:
        kwargs["consumes_attack_slot"] = True
    elif resource_name is not None and resource_cost > 0:
        resources = kwargs.setdefault("resource_costs", {})
        resources[str(resource_name)] = int(resources.get(str(resource_name), 0)) + resource_cost


def _affordance_row_id_from_action(
    bucket: ActionBucket,
    row: AvailableActionInfo,
    target: AvailableTarget,
    action_index: int,
    target_index: int,
) -> str:
    """Build a deterministic row id from engine action objects."""
    bucket_label = bucket.removesuffix("_actions")
    template_name = row.template_name or row.base_template_name or row.semantic_key
    if target.target_uuid:
        semantic = f"uuid={target.target_uuid}"
    elif target.position is not None:
        semantic = f"pos={target.position[0]},{target.position[1]}"
    elif row.source_item_uuid:
        semantic = f"uuid={row.source_item_uuid}"
    else:
        semantic = f"index={target.index if target.index is not None else target_index}"
    if not template_name:
        template_name = f"row_{action_index}"
    return f"{bucket_label}|{template_name}|{semantic}"


def _affordance_tags_from_action(
    row: AvailableActionInfo,
    semantics: ActionSemantics,
) -> list[str]:
    """Derive lightweight tactical tags from one engine action row."""
    tags = _display_tags(
        _enum_value(row.action_category),
        _enum_value(row.target_type),
        semantics,
    )
    if row.is_item_use:
        tags.append("item_use")
    return list(dict.fromkeys(tag for tag in tags if tag))


def _display_tags(
    action_category: str,
    target_type: str,
    semantics: ActionSemantics,
) -> list[str]:
    """Return flat display tags derived from the typed semantic contract."""
    tags = [
        action_category,
        target_type,
        *(tag.value for tag in sorted(semantics.tags, key=lambda value: value.value)),
    ]
    if ActionTag.INTERACTION_DOOR_OPEN in semantics.tags or ActionTag.INTERACTION_DOOR_CLOSE in semantics.tags:
        tags.append("door")
    if ActionTag.TURN_END in semantics.tags:
        tags.append("turn_boundary")
    return list(dict.fromkeys(tag for tag in tags if tag))


def _build_action_economy_state_from_actor(
    actor: Entity,
    actions: AvailableActionsResult,
    affordances: AffordanceSet,
    record_timing: Optional[Callable[[str, float], None]] = None,
) -> ActionEconomyState:
    """Build action-economy state directly from the actor and action result."""
    started = time.perf_counter()
    ae = actor.action_economy
    _record_timing(record_timing, "action_economy.resolve_block_ms", started)

    started = time.perf_counter()
    spell_slots = {}
    for level in range(1, 10):
        slot_started = time.perf_counter()
        slot_attr = getattr(ae, f"spell_slot_{level}", None)
        _record_timing(record_timing, f"action_economy.spell_slot_{level}.resolve_ms", slot_started)
        if slot_attr is None:
            continue
        slot_started = time.perf_counter()
        base_mod = slot_attr.get_base_modifier()
        _record_timing(record_timing, f"action_economy.spell_slot_{level}.base_modifier_ms", slot_started)
        max_val = base_mod.value if base_mod else 0
        if max_val > 0:
            slot_started = time.perf_counter()
            current = slot_attr.normalized_score
            _record_timing(record_timing, f"action_economy.spell_slot_{level}.normalized_score_ms", slot_started)
            spell_slots[level] = ResourcePool.model_construct(current=current, max=max_val)
    _record_timing(record_timing, "action_economy.spell_slots_total_ms", started)

    started = time.perf_counter()
    resources = {}
    for name, resource in ae.resources.items():
        if name == "extra_attacks":
            continue
        resources[str(name)] = ResourcePool.model_construct(current=int(resource.current), max=int(resource.maximum))
    _record_timing(record_timing, "action_economy.resources_ms", started)

    started = time.perf_counter()
    item_charges = {
        str(item_uuid): ResourcePool.model_construct(
            current=current,
            max=maximum,
        )
        for item_uuid, (current, maximum) in actions.item_charge_pools.items()
    }
    _record_timing(record_timing, "action_economy.item_charges_ms", started)

    started = time.perf_counter()
    meaningful_rows = any(
        source.bucket != "special_commands" and source.can_afford
        for source in affordances.action_sources
    )
    _record_timing(record_timing, "action_economy.meaningful_rows_ms", started)

    started = time.perf_counter()
    gates = []
    if not meaningful_rows:
        gates.append(EconomyGate.model_construct(
            name="no_meaningful_commands",
            reason="No affordable non-end-turn command is currently exposed by the engine.",
            active=True,
        ))
    _record_timing(record_timing, "action_economy.gates_ms", started)

    started = time.perf_counter()
    actions_remaining = int(ae.actions.normalized_score)
    _record_timing(record_timing, "action_economy.actions_normalized_score_ms", started)

    started = time.perf_counter()
    bonus_actions_remaining = int(ae.bonus_actions.normalized_score)
    _record_timing(record_timing, "action_economy.bonus_actions_normalized_score_ms", started)

    started = time.perf_counter()
    reactions_remaining = int(ae.reactions.normalized_score)
    _record_timing(record_timing, "action_economy.reactions_normalized_score_ms", started)

    started = time.perf_counter()
    extra_attacks_remaining = int(ae.get_resource_current("extra_attacks"))
    _record_timing(record_timing, "action_economy.extra_attacks_resource_ms", started)

    started = time.perf_counter()
    result = ActionEconomyState.model_construct(
        actor_uuid=str(actor.uuid),
        actions=actions_remaining,
        bonus_actions=bonus_actions_remaining,
        reactions=reactions_remaining,
        movement_remaining=actions.remaining_movement,
        extra_attacks=extra_attacks_remaining,
        spell_slots=spell_slots,
        resources=resources,
        item_charges=item_charges,
        gates=gates,
        meaningful_commands_remaining=meaningful_rows,
    )
    _record_timing(record_timing, "action_economy.construct_model_ms", started)
    return result


def _enum_value(value: Any) -> str:
    """Return enum `.value` when present, otherwise a string value."""
    raw_value = getattr(value, "value", value)
    return str(raw_value)
