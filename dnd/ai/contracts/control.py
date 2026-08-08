"""Decision-epoch and command contracts independent of engine and runtime code."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Final, Iterator, Literal, Mapping, Optional, Self, Sequence, Tuple, overload
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, SerializationInfo, SkipValidation, TypeAdapter, model_serializer, model_validator

from dnd.ai.contracts.semantics import (
    ActionSemantics,
    action_semantics_ref,
    unknown_action_semantics,
)
from dnd.ai.contracts.immutable import FrozenDict
from dnd.core.action_outcomes import (
    ActionOutcomeProfile as ActionOutcomeProfile,
    DamageRollProfile as DamageRollProfile,
    OutcomeApplicationScope as OutcomeApplicationScope,
    OutcomeResolution as OutcomeResolution,
)
from dnd.core.traversal_connectors import ConnectorTraversalDiscovery


ActionBucket = Literal[
    "entity_actions",
    "position_actions",
    "self_actions",
    "object_actions",
    "special_commands",
]
END_TURN_ROW_ID: Final = "special|End Turn|index=0"


class ControlModel(BaseModel):
    """Immutable base for controller-facing protocol values."""

    model_config = ConfigDict(frozen=True)

    def model_post_init(self, __context: Any) -> None:
        """Freeze nested protocol collections after validation."""
        self._freeze_collections()

    def model_copy(
        self,
        *,
        update: Optional[Mapping[str, Any]] = None,
        deep: bool = False,
    ) -> Self:
        """Preserve nested immutability when copying with updates."""
        copied = super().model_copy(update=update, deep=deep)
        copied._freeze_collections()
        return copied

    def _freeze_collections(self) -> None:
        """Freeze subclass-owned collections in place."""


class ResourcePool(ControlModel):
    """Current and maximum values for one expendable resource."""

    current: int = Field(description="Current available resource amount.")
    max: int = Field(description="Maximum resource amount.")


class EconomyGate(ControlModel):
    """Named constraint affecting available commands."""

    name: str = Field(description="Machine-readable gate name.")
    reason: str = Field(description="Human-readable explanation.")
    active: bool = Field(default=True, description="Whether the gate currently applies.")


class ActionCostProfile(ControlModel):
    """Action economy and resource cost profile for one affordance row."""

    action_cost: int = Field(default=0, description="Actions consumed.")
    bonus_action_cost: int = Field(default=0, description="Bonus actions consumed.")
    reaction_cost: int = Field(default=0, description="Reactions consumed.")
    movement_cost: int = Field(default=0, description="Movement consumed in feet.")
    consumes_attack_slot: bool = Field(default=False, description="Whether the row consumes an attack slot.")
    spell_slot_cost: Optional[int] = Field(default=None, description="Spell slot level consumed, if any.")
    resource_costs: Dict[str, int] = Field(default_factory=dict, description="Named resources consumed.")
    item_charge_costs: Dict[str, int] = Field(default_factory=dict, description="Item charges consumed by item UUID.")
    affordability: Literal["affordable", "unaffordable", "conditional"] = Field(
        default="affordable",
        description="Affordability state at epoch computation time.",
    )
    affordability_reasons: Sequence[str] = Field(
        default_factory=tuple,
        description="Reasons the row is unavailable or conditional.",
    )

    def _freeze_collections(self) -> None:
        """Freeze named cost mappings and diagnostic reasons."""
        object.__setattr__(self, "resource_costs", FrozenDict(self.resource_costs))
        object.__setattr__(self, "item_charge_costs", FrozenDict(self.item_charge_costs))
        object.__setattr__(self, "affordability_reasons", tuple(self.affordability_reasons))


class ActionEconomyState(ControlModel):
    """Current action economy and resources for an active actor."""

    actor_uuid: str = Field(description="Actor UUID whose economy is represented.")
    actions: int = Field(default=0, description="Actions remaining.")
    bonus_actions: int = Field(default=0, description="Bonus actions remaining.")
    reactions: int = Field(default=0, description="Reactions remaining.")
    movement_remaining: int = Field(default=0, description="Movement remaining in feet.")
    extra_attacks: int = Field(default=0, description="Extra attack resource remaining.")
    spell_slots: Dict[int, ResourcePool] = Field(default_factory=dict, description="Spell slots keyed by level.")
    resources: Dict[str, ResourcePool] = Field(default_factory=dict, description="Named class or feature resources.")
    item_charges: Dict[str, ResourcePool] = Field(
        default_factory=dict,
        description="Known item charges keyed by item UUID.",
    )
    gates: Sequence[EconomyGate] = Field(default_factory=tuple, description="Active action-economy gates.")
    meaningful_commands_remaining: bool = Field(
        default=False,
        description="Whether useful non-end-turn rows are available.",
    )

    def _freeze_collections(self) -> None:
        """Freeze resource-pool mappings and economy gates."""
        object.__setattr__(self, "spell_slots", FrozenDict(self.spell_slots))
        object.__setattr__(self, "resources", FrozenDict(self.resources))
        object.__setattr__(self, "item_charges", FrozenDict(self.item_charges))
        object.__setattr__(self, "gates", tuple(self.gates))


class OpportunityAttackExposure(ControlModel):
    """Subjectively disclosed threat boundary crossed by a movement route."""

    reactor_uuid: str = Field(description="Visible hostile that may react to the route.")
    reactor_name: str = Field(description="Subjectively known reactor display name.")
    from_position: Tuple[int, int] = Field(description="Last route cell inside the hostile threat area.")
    to_position: Tuple[int, int] = Field(description="First route cell outside the hostile threat area.")


class ActionTarget(ControlModel):
    """Selectable target for one affordance row."""

    index: int = Field(description="Engine target index for execution.")
    target_uuid: Optional[str] = Field(default=None, description="Target entity or object UUID.")
    target_name: Optional[str] = Field(default=None, description="Known target display name.")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Target grid position.")
    distance: Optional[int] = Field(default=None, description="Distance in feet when supplied by the engine.")
    path_cost: Optional[int] = Field(default=None, description="Movement path cost.")
    safe_path_cost: Optional[int] = Field(default=None, description="Safe movement path cost.")
    is_path_hazardous: bool = Field(default=False, description="Whether the path crosses known hazards.")
    path: Sequence[Tuple[int, int]] = Field(default_factory=tuple, description="Path cells.")
    safe_path: Sequence[Tuple[int, int]] = Field(default_factory=tuple, description="Known safe path cells.")
    opportunity_attack_exposures: Sequence[OpportunityAttackExposure] = Field(
        default_factory=tuple,
        description="Potential reactions disclosed for the ordinary route.",
    )
    safe_path_opportunity_attack_exposures: Sequence[OpportunityAttackExposure] = Field(
        default_factory=tuple,
        description="Potential reactions disclosed for the safe alternative route.",
    )
    affected_entity_uuids: Sequence[str] = Field(
        default_factory=tuple,
        description="Affected entity UUIDs for AoE rows.",
    )
    affected_positions: Sequence[Tuple[int, int]] = Field(
        default_factory=tuple,
        description="Affected positions for AoE rows.",
    )

    def _freeze_collections(self) -> None:
        """Freeze paths and affected-set collections."""
        object.__setattr__(self, "path", tuple(self.path))
        object.__setattr__(self, "safe_path", tuple(self.safe_path))
        object.__setattr__(self, "opportunity_attack_exposures", tuple(self.opportunity_attack_exposures))
        object.__setattr__(
            self,
            "safe_path_opportunity_attack_exposures",
            tuple(self.safe_path_opportunity_attack_exposures),
        )
        object.__setattr__(self, "affected_entity_uuids", tuple(self.affected_entity_uuids))
        object.__setattr__(self, "affected_positions", tuple(self.affected_positions))


class ActionSourceDefinition(ControlModel):
    """Action metadata shared by executable rows from one discovered action."""

    source_action_id: str = Field(description="Epoch-local discovered-action identity.")
    bucket: ActionBucket = Field(description="Affordance bucket containing the source rows.")
    template_name: str = Field(description="Engine action template name.")
    semantic_key: str = Field(
        default="action.unclassified",
        description="Stable action-definition key used to select semantic meaning.",
    )
    base_template_name: Optional[str] = Field(
        default=None,
        description="Stable registered template family before generated spell or item variants.",
    )
    display_name: str = Field(description="Human-readable action name.")
    description: Optional[str] = Field(default=None, description="Action description.")
    action_category: str = Field(description="Engine action category.")
    target_type: str = Field(description="Engine target type.")
    can_afford: bool = Field(description="Whether the actor can pay the cost.")
    cost: ActionCostProfile = Field(default_factory=ActionCostProfile, description="Cost profile.")
    target_options: Sequence[ActionTarget] = Field(
        default_factory=tuple,
        description="All legal targets from the source action row before this executable row was flattened.",
    )
    connector_traversal: Optional[ConnectorTraversalDiscovery] = Field(
        default=None,
        description="Exact actor-subjective connector command and destination semantics.",
    )
    num_projectiles: Optional[int] = Field(
        default=None,
        description="Number of targets or projectiles selectable by a multi-entity action.",
    )
    allow_same_target: Optional[bool] = Field(
        default=None,
        description="Whether a multi-entity action may select the same target more than once.",
    )
    is_item_use: bool = Field(default=False, description="Whether this affordance is provided by an item or object.")
    source_item_uuid: Optional[str] = Field(default=None, description="Item or object UUID providing the affordance.")
    weapon_slot: Optional[str] = Field(default=None, description="Weapon slot associated with this row.")
    weapon_name: Optional[str] = Field(default=None, description="Weapon name associated with this row.")
    damage_types: Sequence[str] = Field(
        default_factory=tuple,
        description="Damage type labels this row can deal when known.",
    )
    outcome_profile: Optional[ActionOutcomeProfile] = Field(
        default=None,
        description="Actor-baseline stochastic outcome model declared by the action rule.",
    )
    spell_level: Optional[int] = Field(default=None, description="Base spell level.")
    cast_at_level: Optional[int] = Field(default=None, description="Spell slot level used for a variant.")
    is_spell_variant: bool = Field(default=False, description="Whether this row is a generated spell-level variant.")
    requires_concentration: bool = Field(
        default=False,
        description="Whether execution starts or replaces concentration.",
    )
    semantic_id: str = Field(default="action.unknown", description="Stable action-family identifier.")
    semantics_ref: str = Field(
        default_factory=lambda: action_semantics_ref(unknown_action_semantics()),
        description="Reference into the containing affordance set's semantic catalog.",
    )
    tags: Sequence[str] = Field(default_factory=tuple, description="Policy-facing tactical tags.")

    def _freeze_collections(self) -> None:
        """Freeze policy-facing source metadata."""
        object.__setattr__(self, "target_options", tuple(self.target_options))
        object.__setattr__(self, "damage_types", tuple(self.damage_types))
        object.__setattr__(self, "tags", tuple(self.tags))


class ActionRowReference(ControlModel):
    """Compact wire reference to one executable target selection."""

    row_id: str = Field(description="Stable row id within the decision epoch.")
    source_action_id: str = Field(description="Referenced action-source identity.")
    targets: Sequence[ActionTarget] = Field(default_factory=tuple, description="Targets selected by this row.")
    target_indices: Sequence[int] = Field(
        default_factory=tuple,
        description="Epoch-local target-catalog indices used by the compact wire form.",
    )

    @model_validator(mode="after")
    def _validate_target_representation(self) -> "ActionRowReference":
        """Reject rows that mix expanded targets with compact references."""
        if self.targets and self.target_indices:
            raise ValueError("action row reference cannot contain both targets and target_indices")
        if any(index < 0 for index in self.target_indices):
            raise ValueError("action row target indices must be non-negative")
        return self

    def _freeze_collections(self) -> None:
        """Freeze the executable target selection."""
        object.__setattr__(self, "targets", tuple(self.targets))
        object.__setattr__(self, "target_indices", tuple(self.target_indices))


_ACTION_SOURCE_SEQUENCE_ADAPTER = TypeAdapter(Tuple[ActionSourceDefinition, ...])
_ACTION_ROW_REFERENCE_SEQUENCE_ADAPTER = TypeAdapter(Tuple[ActionRowReference, ...])
_ACTION_TARGET_SEQUENCE_ADAPTER = TypeAdapter(Tuple[ActionTarget, ...])


class ActionAffordance(ControlModel):
    """One executable row referencing immutable discovered-action metadata."""

    row_id: str = Field(description="Stable row id within the decision epoch.")
    source: ActionSourceDefinition = Field(
        description="Shared metadata for the discovered action that produced this row."
    )
    targets: Sequence[ActionTarget] = Field(
        default_factory=tuple,
        description="Exact target selection authorized by this row.",
    )

    @model_validator(mode="before")
    @classmethod
    def _factor_flat_input(cls, value: Any) -> Any:
        """Normalize the public flat row shape into the canonical factored model."""
        if not isinstance(value, Mapping) or "source" in value:
            return value
        payload = dict(value)
        row_id = payload.pop("row_id")
        targets = payload.pop("targets", ())
        source_payload = {
            field_name: payload.pop(field_name)
            for field_name in ActionSourceDefinition.model_fields
            if field_name in payload
        }
        source_payload.setdefault("source_action_id", row_id)
        return {
            "row_id": row_id,
            "source": source_payload,
            "targets": targets,
        }

    @model_serializer(mode="wrap")
    def _serialize_flat(self, handler: Any) -> Dict[str, Any]:
        """Preserve the public flat row shape outside an affordance set."""
        payload = handler(self)
        source = payload.pop("source")
        row_id = payload.pop("row_id")
        targets = payload.pop("targets", ())
        return {
            "row_id": row_id,
            **source,
            "targets": targets,
        }

    def model_copy(
        self,
        *,
        update: Optional[Mapping[str, Any]] = None,
        deep: bool = False,
    ) -> Self:
        """Copy row-local fields or immutably project shared source metadata."""
        if not update:
            return super().model_copy(update=update, deep=deep)
        source_updates = {
            field_name: field_value
            for field_name, field_value in update.items()
            if field_name in ActionSourceDefinition.model_fields
        }
        row_updates = {
            field_name: field_value
            for field_name, field_value in update.items()
            if field_name in type(self).model_fields
        }
        if source_updates:
            updated_row_id = row_updates.get("row_id")
            if (
                "source_action_id" not in source_updates
                and isinstance(updated_row_id, str)
                and updated_row_id != self.row_id
            ):
                source_updates["source_action_id"] = updated_row_id
            row_updates["source"] = self.source.model_copy(
                update=source_updates,
                deep=deep,
            )
        return super().model_copy(update=row_updates, deep=deep)

    def _freeze_collections(self) -> None:
        """Freeze the row-local target selection."""
        object.__setattr__(self, "targets", tuple(self.targets))

    @property
    def source_action_id(self) -> str:
        """Return the shared epoch-local source identity."""
        return self.source.source_action_id

    @property
    def bucket(self) -> ActionBucket:
        """Return the source action bucket."""
        return self.source.bucket

    @property
    def template_name(self) -> str:
        """Return the engine template name."""
        return self.source.template_name

    @property
    def semantic_key(self) -> str:
        """Return the stable action-definition key."""
        return self.source.semantic_key

    @property
    def base_template_name(self) -> Optional[str]:
        """Return the registered template family name."""
        return self.source.base_template_name

    @property
    def display_name(self) -> str:
        """Return the human-readable action name."""
        return self.source.display_name

    @property
    def description(self) -> Optional[str]:
        """Return the action description."""
        return self.source.description

    @property
    def action_category(self) -> str:
        """Return the engine action category."""
        return self.source.action_category

    @property
    def target_type(self) -> str:
        """Return the engine target type."""
        return self.source.target_type

    @property
    def can_afford(self) -> bool:
        """Return whether the actor can currently pay the action cost."""
        return self.source.can_afford

    @property
    def cost(self) -> ActionCostProfile:
        """Return the shared action-cost profile."""
        return self.source.cost

    @property
    def target_options(self) -> Sequence[ActionTarget]:
        """Return all legal source-level target options when retained."""
        return self.source.target_options

    @property
    def num_projectiles(self) -> Optional[int]:
        """Return the selectable target or projectile count."""
        return self.source.num_projectiles

    @property
    def allow_same_target(self) -> Optional[bool]:
        """Return whether repeated target allocation is legal."""
        return self.source.allow_same_target

    @property
    def is_item_use(self) -> bool:
        """Return whether an item or object provides the action."""
        return self.source.is_item_use

    @property
    def source_item_uuid(self) -> Optional[str]:
        """Return the providing item or object UUID."""
        return self.source.source_item_uuid

    @property
    def weapon_slot(self) -> Optional[str]:
        """Return the associated weapon slot."""
        return self.source.weapon_slot

    @property
    def weapon_name(self) -> Optional[str]:
        """Return the associated weapon name."""
        return self.source.weapon_name

    @property
    def damage_types(self) -> Sequence[str]:
        """Return known damage type labels."""
        return self.source.damage_types

    @property
    def outcome_profile(self) -> Optional[ActionOutcomeProfile]:
        """Return the actor-baseline outcome model."""
        return self.source.outcome_profile

    @property
    def spell_level(self) -> Optional[int]:
        """Return the base spell level."""
        return self.source.spell_level

    @property
    def cast_at_level(self) -> Optional[int]:
        """Return the selected spell-slot level."""
        return self.source.cast_at_level

    @property
    def is_spell_variant(self) -> bool:
        """Return whether the action is a generated spell-level variant."""
        return self.source.is_spell_variant

    @property
    def requires_concentration(self) -> bool:
        """Return whether execution starts or replaces concentration."""
        return self.source.requires_concentration

    @property
    def semantic_id(self) -> str:
        """Return the stable semantic action family."""
        return self.source.semantic_id

    @property
    def semantics_ref(self) -> str:
        """Return the semantic-catalog reference."""
        return self.source.semantics_ref

    @property
    def tags(self) -> Sequence[str]:
        """Return policy-facing tactical tags."""
        return self.source.tags

    def validated_extra_target_uuids(
        self,
        extra_target_uuids: Sequence[str],
    ) -> Tuple[str, ...]:
        """Validate a multi-target allocation against subjective epoch facts."""
        selected = tuple(extra_target_uuids)
        if not selected:
            return tuple()
        if self.target_type != "multi_entity" or self.num_projectiles is None:
            raise ValueError("Additional targets require a multi-entity affordance")
        if len(selected) + 1 > self.num_projectiles:
            raise ValueError("Additional targets exceed the affordance allocation count")
        legal_target_uuids = {
            target.target_uuid
            for target in (*self.targets, *self.target_options)
            if target.target_uuid is not None
        }
        if any(target_uuid not in legal_target_uuids for target_uuid in selected):
            raise ValueError("Additional target is absent from the affordance target options")
        primary_target_uuids = tuple(
            target.target_uuid
            for target in self.targets
            if target.target_uuid is not None
        )
        allocation = (*primary_target_uuids, *selected)
        if self.allow_same_target is False and len(set(allocation)) != len(allocation):
            raise ValueError("Affordance requires unique target allocation")
        return selected


@dataclass(frozen=True, slots=True)
class CanonicalActionRow:
    """Compact immutable row value retained by an affordance set."""

    row_id: str
    source: ActionSourceDefinition
    targets: Tuple[ActionTarget, ...]


class ActionBucketRows(Sequence[ActionAffordance]):
    """Ordered compact rows that materialize public affordances on demand."""

    __slots__ = ("_references", "_row_index", "_resolved")

    def __init__(self, references: Sequence[CanonicalActionRow] = ()) -> None:
        self._references = tuple(references)
        self._row_index = {
            reference.row_id: index
            for index, reference in enumerate(self._references)
        }
        self._resolved: Dict[int, ActionAffordance] = {}

    @property
    def references(self) -> Tuple[CanonicalActionRow, ...]:
        """Return compact canonical row values without materializing views."""
        return self._references

    def row_by_id(self, row_id: str) -> Optional[ActionAffordance]:
        """Resolve one public row view by its epoch-local identity."""
        index = self._row_index.get(row_id)
        return self._resolve(index) if index is not None else None

    def _resolve(self, index: int) -> ActionAffordance:
        cached = self._resolved.get(index)
        if cached is not None:
            return cached
        reference = self._references[index]
        resolved = ActionAffordance.model_construct(
            row_id=reference.row_id,
            source=reference.source,
            targets=reference.targets,
        )
        self._resolved[index] = resolved
        return resolved

    def __len__(self) -> int:
        return len(self._references)

    @overload
    def __getitem__(self, index: int) -> ActionAffordance:
        ...

    @overload
    def __getitem__(self, index: slice) -> Tuple[ActionAffordance, ...]:
        ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> ActionAffordance | Tuple[ActionAffordance, ...]:
        if isinstance(index, slice):
            return tuple(self._resolve(row_index) for row_index in range(*index.indices(len(self))))
        normalized = index if index >= 0 else len(self) + index
        if normalized < 0 or normalized >= len(self):
            raise IndexError(index)
        return self._resolve(normalized)

    def __iter__(self) -> Iterator[ActionAffordance]:
        for index in range(len(self._references)):
            yield self._resolve(index)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ActionBucketRows):
            return self._references == other._references
        if isinstance(other, Sequence):
            return tuple(self) == tuple(other)
        return False


class CombinedActionRows(Sequence[ActionAffordance]):
    """Read-only concatenation preserving each bucket's lazy row cache."""

    __slots__ = ("_buckets", "_length")

    def __init__(self, buckets: Sequence[ActionBucketRows]) -> None:
        self._buckets = tuple(buckets)
        self._length = sum(len(bucket) for bucket in self._buckets)

    def __len__(self) -> int:
        return self._length

    @overload
    def __getitem__(self, index: int) -> ActionAffordance:
        ...

    @overload
    def __getitem__(self, index: slice) -> Tuple[ActionAffordance, ...]:
        ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> ActionAffordance | Tuple[ActionAffordance, ...]:
        if isinstance(index, slice):
            return tuple(self)[index]
        normalized = index if index >= 0 else self._length + index
        if normalized < 0 or normalized >= self._length:
            raise IndexError(index)
        for bucket in self._buckets:
            if normalized < len(bucket):
                return bucket[normalized]
            normalized -= len(bucket)
        raise IndexError(index)

    def __iter__(self) -> Iterator[ActionAffordance]:
        for bucket in self._buckets:
            yield from bucket

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CombinedActionRows):
            return self._buckets == other._buckets
        if isinstance(other, Sequence):
            return tuple(self) == tuple(other)
        return False


class ActionCapability(ControlModel):
    """Actor-owned action possibility without current execution authority."""

    capability_id: str = Field(description="Stable identity for this actor-owned action configuration.")
    semantic_key: str = Field(description="Stable action-definition key.")
    action_category: str = Field(description="Engine action category.")
    target_type: str = Field(description="Configured target-allocation type.")
    cost: ActionCostProfile = Field(description="Current cost and affordability profile.")
    range_type: Optional[str] = Field(default=None, description="Reach, ranged, or self range class.")
    normal_range_feet: Optional[int] = Field(default=None, ge=0, description="Normal reach or range in feet.")
    long_range_feet: Optional[int] = Field(default=None, ge=0, description="Optional long range in feet.")
    requires_line_of_sight: bool = Field(description="Whether target legality normally requires a visible line.")
    valid_target_filter: str = Field(description="Configured relationship filter for potential targets.")
    weapon_slot: Optional[str] = Field(default=None, description="Configured weapon slot when applicable.")
    base_spell_level: Optional[int] = Field(
        default=None,
        ge=0,
        description="Intrinsic spell level used by rules that scale from the base spell.",
    )
    cast_at_level: Optional[int] = Field(default=None, description="Configured spell-slot variant level.")
    source_item_uuid: Optional[str] = Field(default=None, description="Actor-owned item providing this capability.")
    outcome_profile: Optional[ActionOutcomeProfile] = Field(
        default=None,
        description="Actor-baseline stochastic outcome model without target or execution authority.",
    )
    semantic_id: str = Field(description="Stable semantic action family.")
    semantics_ref: str = Field(description="Reference into the containing semantic catalog.")
    tags: Sequence[str] = Field(default_factory=tuple, description="Typed semantic capability tags.")

    def _freeze_collections(self) -> None:
        """Freeze policy-facing capability metadata."""
        object.__setattr__(self, "tags", tuple(self.tags))


_ACTION_CAPABILITY_SEQUENCE_ADAPTER = TypeAdapter(Tuple[ActionCapability, ...])
_ACTION_SEMANTIC_CATALOG_ADAPTER = TypeAdapter(Dict[str, ActionSemantics])


class AffordanceSet(ControlModel):
    """Legal command rows for one active actor and decision epoch."""

    actor_uuid: str = Field(description="Active actor UUID.")
    computed_at_observation_cursor: int = Field(description="Observation cursor used for computation.")
    entity_actions: SkipValidation[Sequence[ActionAffordance]] = Field(
        default_factory=ActionBucketRows,
        description="Entity-targeting rows resolved lazily from canonical references.",
    )
    position_actions: SkipValidation[Sequence[ActionAffordance]] = Field(
        default_factory=ActionBucketRows,
        description="Position-targeting rows resolved lazily from canonical references.",
    )
    self_actions: SkipValidation[Sequence[ActionAffordance]] = Field(
        default_factory=ActionBucketRows,
        description="Self-targeting rows resolved lazily from canonical references.",
    )
    object_actions: SkipValidation[Sequence[ActionAffordance]] = Field(
        default_factory=ActionBucketRows,
        description="Object-targeting rows resolved lazily from canonical references.",
    )
    special_commands: SkipValidation[Sequence[ActionAffordance]] = Field(
        default_factory=ActionBucketRows,
        description="Runtime special commands resolved lazily from canonical references.",
    )
    capabilities: Sequence[ActionCapability] = Field(
        default_factory=tuple,
        description="Actor-owned action possibilities that carry no execution authority.",
    )
    semantic_catalog: Dict[str, ActionSemantics] = Field(
        default_factory=dict,
        description="Deduplicated typed action contracts keyed by affordance semantics reference.",
    )
    _all_rows: Sequence[ActionAffordance] = PrivateAttr(default_factory=tuple)
    _row_buckets_by_id: Dict[str, ActionBucketRows] = PrivateAttr(default_factory=dict)
    _action_sources: Tuple[ActionSourceDefinition, ...] = PrivateAttr(default_factory=tuple)

    @model_validator(mode="before")
    @classmethod
    def _inflate_wire_rows(cls, value: Any) -> Any:
        """Inflate compact wire rows into the canonical in-memory affordances."""
        if not isinstance(value, Mapping) or "action_sources" not in value:
            return value
        payload = dict(value)
        source_rows = payload.pop("action_sources")
        raw_target_catalog = payload.pop("target_catalog", ())
        target_catalog = _ACTION_TARGET_SEQUENCE_ADAPTER.validate_python(
            raw_target_catalog
        )
        canonical_targets = {target: target for target in target_catalog}
        normalized_source_rows: list[Any] = []
        for raw_source in source_rows:
            if isinstance(raw_source, ActionSourceDefinition):
                normalized_source_rows.append(raw_source)
                continue
            if not isinstance(raw_source, Mapping):
                normalized_source_rows.append(raw_source)
                continue
            source_payload = dict(raw_source)
            target_option_indices = source_payload.pop("target_option_indices", ())
            if target_option_indices and source_payload.get("target_options"):
                raise ValueError(
                    "action source cannot contain target options and target-option indices"
                )
            if target_option_indices:
                try:
                    source_payload["target_options"] = tuple(
                        target_catalog[target_index]
                        for target_index in target_option_indices
                    )
                except (IndexError, TypeError) as exc:
                    raise ValueError(
                        "action source references a target outside the epoch target catalog"
                    ) from exc
            normalized_source_rows.append(source_payload)
        sources: Dict[str, ActionSourceDefinition] = {}
        for source in _ACTION_SOURCE_SEQUENCE_ADAPTER.validate_python(
            normalized_source_rows
        ):
            if source.source_action_id in sources:
                raise ValueError(f"duplicate action source {source.source_action_id!r}")
            canonical_options = tuple(
                canonical_targets.setdefault(option, option)
                for option in source.target_options
            )
            if any(
                canonical is not original
                for canonical, original in zip(
                    canonical_options,
                    source.target_options,
                )
            ):
                source = source.model_copy(
                    update={"target_options": canonical_options},
                )
            sources[source.source_action_id] = source
        for bucket in _ACTION_BUCKET_ORDER:
            inflated: list[CanonicalActionRow] = []
            references = _ACTION_ROW_REFERENCE_SEQUENCE_ADAPTER.validate_python(
                payload.get(bucket, ())
            )
            for reference in references:
                source = sources.get(reference.source_action_id)
                if source is None:
                    raise ValueError(
                        f"affordance row {reference.row_id!r} references unknown action source "
                        f"{reference.source_action_id!r}"
                    )
                if source.bucket != bucket:
                    raise ValueError(
                        f"affordance row {reference.row_id!r} is in {bucket!r} but references "
                        f"a {source.bucket!r} source"
                    )
                targets = reference.targets
                if reference.target_indices:
                    try:
                        targets = tuple(
                            target_catalog[target_index]
                            for target_index in reference.target_indices
                        )
                    except IndexError as exc:
                        raise ValueError(
                            f"affordance row {reference.row_id!r} references a target outside "
                            "the epoch target catalog"
                        ) from exc
                inflated.append(CanonicalActionRow(
                    row_id=reference.row_id,
                    source=source,
                    targets=tuple(targets),
                ))
            payload[bucket] = ActionBucketRows(inflated)
        return payload

    @model_serializer(mode="wrap")
    def _serialize_transport(self, handler: Any, info: SerializationInfo) -> Dict[str, Any]:
        """Factor repeated row metadata when serializing the controller wire format."""
        if info.mode != "json":
            return handler(self)

        sources: Dict[str, ActionSourceDefinition] = {}
        compact_buckets: Dict[str, list[Dict[str, Any]]] = {}
        target_catalog: list[ActionTarget] = []
        target_indices: Dict[ActionTarget, int] = {}

        def register_target(target: ActionTarget) -> int:
            target_index = target_indices.get(target)
            if target_index is not None:
                return target_index
            target_index = len(target_catalog)
            target_indices[target] = target_index
            target_catalog.append(target)
            return target_index

        for bucket in _ACTION_BUCKET_ORDER:
            compact_rows: list[Dict[str, Any]] = []
            for row in getattr(self, bucket):
                source_action_id = row.source_action_id
                previous = sources.get(source_action_id)
                if previous is None:
                    source = row.source
                    sources[source_action_id] = source
                elif previous != row.source:
                    raise ValueError(
                        f"action source {source_action_id!r} has inconsistent shared metadata"
                    )
                row_target_indices = [
                    register_target(target)
                    for target in row.targets
                ]
                compact_rows.append({
                    "row_id": row.row_id,
                    "source_action_id": source_action_id,
                    **(
                        {"target_indices": row_target_indices}
                        if row_target_indices
                        else {}
                    ),
                })
            compact_buckets[bucket] = compact_rows
        for source in sources.values():
            for target in source.target_options:
                register_target(target)
        source_payloads = _ACTION_SOURCE_SEQUENCE_ADAPTER.dump_python(
            tuple(sources.values()),
            mode="json",
            exclude_defaults=True,
            exclude_none=True,
        )
        for source, source_payload in zip(
            sources.values(),
            source_payloads,
            strict=True,
        ):
            source_payload.pop("target_options", None)
            source_target_indices = [
                register_target(target)
                for target in source.target_options
            ]
            if source_target_indices:
                source_payload["target_option_indices"] = source_target_indices
        serialized = {
            "actor_uuid": self.actor_uuid,
            "computed_at_observation_cursor": self.computed_at_observation_cursor,
            "action_sources": source_payloads,
            **compact_buckets,
            "capabilities": _ACTION_CAPABILITY_SEQUENCE_ADAPTER.dump_python(
                tuple(self.capabilities),
                mode="json",
                exclude_defaults=True,
                exclude_none=True,
            ),
            "semantic_catalog": _ACTION_SEMANTIC_CATALOG_ADAPTER.dump_python(
                dict(self.semantic_catalog),
                mode="json",
            ),
        }
        if target_catalog:
            serialized["target_catalog"] = _ACTION_TARGET_SEQUENCE_ADAPTER.dump_python(
                tuple(target_catalog),
                mode="json",
                exclude_defaults=True,
                exclude_none=True,
            )
        return serialized

    def _freeze_collections(self) -> None:
        """Freeze rows, canonicalize shared sources, and build lookup indexes."""
        sources: Dict[str, ActionSourceDefinition] = {}
        row_buckets_by_id: Dict[str, ActionBucketRows] = {}
        canonical_buckets: Dict[str, ActionBucketRows] = {}
        for bucket in _ACTION_BUCKET_ORDER:
            raw_rows = getattr(self, bucket)
            if isinstance(raw_rows, ActionBucketRows):
                references = raw_rows.references
            else:
                references = tuple(
                    CanonicalActionRow(
                        row_id=row.row_id,
                        source=row.source,
                        targets=tuple(row.targets),
                    )
                    for raw_row in raw_rows
                    for row in (
                        raw_row
                        if isinstance(raw_row, ActionAffordance)
                        else ActionAffordance.model_validate(raw_row),
                    )
                )
            canonical_references: list[CanonicalActionRow] = []
            for reference in references:
                previous_source = sources.get(reference.source.source_action_id)
                if previous_source is None:
                    source = reference.source
                    sources[source.source_action_id] = source
                elif previous_source != reference.source:
                    raise ValueError(
                        f"action source {reference.source.source_action_id!r} has inconsistent shared metadata"
                    )
                else:
                    source = previous_source
                canonical_references.append(CanonicalActionRow(
                    row_id=reference.row_id,
                    source=source,
                    targets=reference.targets,
                ))
            canonical_bucket = ActionBucketRows(canonical_references)
            for reference in canonical_references:
                row_buckets_by_id.setdefault(reference.row_id, canonical_bucket)
            canonical_buckets[bucket] = canonical_bucket
        for bucket, rows in canonical_buckets.items():
            object.__setattr__(self, bucket, rows)
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "semantic_catalog", FrozenDict(self.semantic_catalog))
        object.__setattr__(self, "_all_rows", CombinedActionRows(tuple(canonical_buckets.values())))
        object.__setattr__(self, "_row_buckets_by_id", FrozenDict(row_buckets_by_id))
        object.__setattr__(self, "_action_sources", tuple(sources.values()))

    @property
    def all_rows(self) -> Sequence[ActionAffordance]:
        """Return all rows in deterministic execution-search order."""
        return self._all_rows

    @property
    def action_sources(self) -> Tuple[ActionSourceDefinition, ...]:
        """Return canonical discovered-action definitions in row order."""
        return self._action_sources

    def row_by_id(self, row_id: str) -> Optional[ActionAffordance]:
        """Return an executable row without scanning or allocating all buckets."""
        bucket = self._row_buckets_by_id.get(row_id)
        return bucket.row_by_id(row_id) if bucket is not None else None

    def semantics_for(self, row: ActionAffordance) -> ActionSemantics:
        """Resolve one row's semantic contract with an explicit unknown fallback."""
        return self.semantic_catalog.get(row.semantics_ref, unknown_action_semantics())


_ACTION_BUCKET_ORDER: Tuple[ActionBucket, ...] = (
    "entity_actions",
    "position_actions",
    "self_actions",
    "object_actions",
    "special_commands",
)


class DecisionEpochReason(str, Enum):
    """Reason a decision epoch was emitted."""

    TURN_START = "turn_start"
    ACTION_COMPLETED = "action_completed"
    ACTION_CANCELED = "action_canceled"
    ACTION_REJECTED = "action_rejected"
    ACTION_STALE = "action_stale"
    RESYNC = "resync"
    REACTION_PROMPT = "reaction_prompt"
    MOVEMENT_REVALIDATION = "movement_revalidation"
    SNAPSHOT = "snapshot"


class DecisionEpoch(ControlModel):
    """Decision point containing legal affordances and action economy."""

    epoch_id: str = Field(description="Stable epoch id.")
    epoch_index: int = Field(description="Monotonic epoch index for this session.")
    basis_observation_cursor: int = Field(description="Observation cursor represented by this epoch.")
    reason: DecisionEpochReason = Field(description="Why the epoch was emitted.")
    actor_uuid: str = Field(description="Active controlled actor UUID.")
    round_number: int = Field(description="Encounter round number.")
    turn_index: int = Field(description="Encounter turn index.")
    economy: ActionEconomyState = Field(description="Current actor action economy.")
    affordances: AffordanceSet = Field(description="Legal command rows.")


class CommandResultStatus(str, Enum):
    """Result status for an agent command."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STALE = "stale"
    ERROR = "error"


class ActionResolutionStatus(str, Enum):
    """Gameplay resolution of a command admitted by the controller protocol."""

    COMPLETED = "completed"
    CANCELED = "canceled"
    INTERRUPTED = "interrupted"


class CommandResult(ControlModel):
    """Result of executing or rejecting an epoch-based command."""

    status: CommandResultStatus = Field(description="Command result status.")
    command_id: Optional[str] = Field(default=None, description="Controller command id for request/result correlation.")
    session_id: str = Field(description="Session UUID.")
    actor_uuid: Optional[str] = Field(default=None, description="Actor UUID.")
    requested_epoch_id: Optional[str] = Field(default=None, description="Epoch id supplied by the client.")
    current_epoch_id: Optional[str] = Field(default=None, description="Current epoch id at validation time.")
    row_id: Optional[str] = Field(default=None, description="Requested row id.")
    action_resolution: Optional[ActionResolutionStatus] = Field(
        default=None,
        description="Gameplay resolution for an accepted command.",
    )
    outcome_code: Optional[str] = Field(
        default=None,
        description="Stable machine-readable engine outcome, if any.",
    )
    revalidation_required: bool = Field(
        default=False,
        description="Whether new subjective information requires a fresh decision.",
    )
    revalidation_reason: Optional[str] = Field(
        default=None,
        description="Typed subjective change that required a fresh decision.",
    )
    message: str = Field(default="", description="Human-readable result.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Serialized server payload.")
    resync_required: bool = Field(default=False, description="Whether the client should refresh snapshot state.")
    accepted_at_observation_cursor: Optional[int] = Field(
        default=None,
        description="Observation cursor where the command result was published.",
    )
    result_expected_after_cursor: Optional[int] = Field(
        default=None,
        description="Cursor after which clients should expect result frames.",
    )

    @property
    def action_completed(self) -> bool:
        """Return whether an admitted gameplay action explicitly completed."""
        return (
            self.status is CommandResultStatus.ACCEPTED
            and self.action_resolution is ActionResolutionStatus.COMPLETED
        )

    @property
    def action_effect_committed(self) -> bool:
        """Return whether an admitted action committed complete or partial effects."""
        return (
            self.status is CommandResultStatus.ACCEPTED
            and self.action_resolution in {
                ActionResolutionStatus.COMPLETED,
                ActionResolutionStatus.INTERRUPTED,
            }
        )


class AgentExecuteCommandRequest(ControlModel):
    """Request to execute one decision-epoch row."""

    command_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Client command id for result correlation.",
    )
    actor_uuid: str = Field(description="Actor UUID expected to own the current decision epoch.")
    basis_epoch_id: str = Field(description="Epoch id used to select the row.")
    row_id: str = Field(description="Affordance row id selected by the controller.")
    extra_target_uuids: Optional[Sequence[str]] = Field(
        default=None,
        description="Optional extra target UUIDs for multi-target rows.",
    )
    prefer_safe: bool = Field(
        default=True,
        description="Whether movement should prefer safe paths when the engine supports it.",
    )
    include_diagnostics: bool = Field(
        default=False,
        description="Whether this command samples deep engine and projection phase timing.",
    )

    def _freeze_collections(self) -> None:
        """Freeze optional multi-target command selections."""
        if self.extra_target_uuids is not None:
            object.__setattr__(self, "extra_target_uuids", tuple(self.extra_target_uuids))


class AgentEndTurnCommandRequest(ControlModel):
    """Request to end the active decision-epoch actor turn."""

    command_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Client command id for result correlation.",
    )
    actor_uuid: str = Field(description="Actor UUID expected to own the current decision epoch.")
    basis_epoch_id: str = Field(description="Epoch id used by the controller.")
    include_diagnostics: bool = Field(
        default=False,
        description="Whether this command samples deep advancement and epoch phase timing.",
    )
