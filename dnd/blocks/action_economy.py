"""Action economy resources, turn costs, and spell slot values."""

from typing import Optional, List, Tuple, Dict, Union, Sequence
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, StrictInt
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import NumericalModifier
from dnd.types.actions import (
    CostType,
    HasteActionPolicy,
    RestrictedActionGrant,
    spell_slot_cost_type,
)
from dnd.core.feature_grants import AttackMultiplicityGrant

from dnd.core.base_block import BaseBlock


class RechargeType(str, Enum):
    """When a resource recharges to its maximum value."""

    SHORT_REST = "short_rest"
    LONG_REST = "long_rest"
    TURN_START = "turn_start"
    NEVER = "never"


class ResourceCapacityPolicy(str, Enum):
    """How multiple owned contributions determine one resource maximum."""

    SUM = "sum"
    MAXIMUM = "maximum"


class ActionEconomyChannelCost(BaseModel):
    """One exact value-channel debit with no named-resource ambiguity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cost_type: CostType
    amount: StrictInt = Field(ge=0)
    name: Optional[str] = None


class NamedResourceCost(BaseModel):
    """One exact named-resource debit kept outside modifier channels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    amount: StrictInt = Field(ge=1)


class ActionEconomyDebitHandle(BaseModel):
    """Exact installed modifier evidence for one aggregated channel."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cost_type: CostType
    modifier_uuid: UUID
    amount: StrictInt = Field(ge=0)
    modifier_name: str


class ActionEconomyDebitReceipt(BaseModel):
    """One-use receipt for modifiers installed by one aggregate commit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    receipt_uuid: UUID = Field(default_factory=uuid4)
    owner_uuid: UUID
    handles: Tuple[ActionEconomyDebitHandle, ...]


class FixedCostCommitReceipt(BaseModel):
    """Successful fixed-cost evidence retained by Jump or a connector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    channel_receipt: ActionEconomyDebitReceipt
    resources: Tuple[NamedResourceCost, ...]


class FixedCostCommitError(RuntimeError):
    """A synchronous no-dispatch fixed-cost commit failed and was unwound."""


class ResourceRecoveryContribution(BaseModel):
    """One exact source-owned partial recovery rule."""

    model_config = ConfigDict(frozen=True)

    trigger: RechargeType = Field(
        description="Recovery boundary that activates this contribution.",
    )
    amount: int = Field(
        ge=1,
        description="Uses restored at that boundary, capped by maximum.",
    )


class Resource(BaseModel):
    """Limited-use named resource such as Second Wind or Rage.

    Attributes:
        name: Resource identifier.
        current: Current uses remaining.
        maximum: Maximum uses.
        recharge_type: When the resource recharges.
    """

    name: str = Field(description="Resource identifier.")
    current: int = Field(description="Current uses remaining.")
    maximum: int = Field(description="Maximum uses after recharge.")
    recharge_type: RechargeType = Field(description="Rest or turn timing that restores this resource.")
    capacity_policy: ResourceCapacityPolicy = Field(
        default=ResourceCapacityPolicy.MAXIMUM,
        description="Rule used to combine independently owned capacity grants.",
    )
    capacity_contributions: Dict[str, int] = Field(
        default_factory=dict,
        description="Capacity by exact source identity.",
    )
    recovery_contributions: Dict[str, ResourceRecoveryContribution] = Field(
        default_factory=dict,
        description="Partial recovery rules by exact source identity.",
    )

    @property
    def spent(self) -> int:
        """Return uses spent from the currently available capacity."""
        return max(0, self.maximum - self.current)

    def set_capacity_contribution(
        self,
        source_id: Union[str, UUID],
        maximum: int,
    ) -> None:
        """Add or replace one source while preserving already-spent uses."""
        if maximum < 0:
            raise ValueError("resource contribution maximum cannot be negative")
        spent = self.spent
        self.capacity_contributions[str(source_id)] = maximum
        self._recompute_capacity(spent)

    def remove_capacity_contribution(
        self,
        source_id: Union[str, UUID],
    ) -> bool:
        """Remove one source while preserving already-spent uses."""
        source_key = str(source_id)
        if source_key not in self.capacity_contributions:
            return False
        spent = self.spent
        del self.capacity_contributions[source_key]
        self._recompute_capacity(spent)
        return True

    def _recompute_capacity(self, spent: int) -> None:
        """Resolve maximum from sources and carry expenditure across rebuild."""
        capacities = tuple(self.capacity_contributions.values())
        if not capacities:
            self.maximum = 0
        elif self.capacity_policy == ResourceCapacityPolicy.SUM:
            self.maximum = sum(capacities)
        else:
            self.maximum = max(capacities)
        self.current = max(0, self.maximum - spent)

    def can_afford(self, amount: int = 1) -> bool:
        """Return whether the resource has enough uses."""
        return self.current >= amount

    def consume(self, amount: int = 1) -> bool:
        """Consume uses if available.

        Returns:
            True if the resource had enough uses and was consumed.
        """
        if not self.can_afford(amount):
            return False
        self.current -= amount
        return True

    def recharge(self) -> None:
        """Restore resource to maximum."""
        self.current = self.maximum

    def set_recovery_contribution(
        self,
        source_id: Union[str, UUID],
        *,
        trigger: RechargeType,
        amount: int,
    ) -> None:
        """Add or replace one exact partial recovery contribution."""
        self.recovery_contributions[str(source_id)] = (
            ResourceRecoveryContribution(
                trigger=trigger,
                amount=amount,
            )
        )

    def remove_recovery_contribution(
        self,
        source_id: Union[str, UUID],
    ) -> bool:
        """Remove one exact partial recovery contribution."""
        return self.recovery_contributions.pop(str(source_id), None) is not None

    def recover_for(self, trigger: RechargeType) -> None:
        """Apply base recharge or all partial contributions for one boundary."""
        recharges_fully = self.recharge_type == trigger
        if trigger is RechargeType.LONG_REST:
            recharges_fully = self.recharge_type in {
                RechargeType.SHORT_REST,
                RechargeType.LONG_REST,
            }
        if recharges_fully:
            self.recharge()
            return
        recovered = sum(
            contribution.amount
            for contribution in self.recovery_contributions.values()
            if contribution.trigger is trigger
        )
        self.current = min(self.maximum, self.current + recovered)


class NormalSpellSlotCapacityReceipt(BaseModel):
    """Exact runtime handles for the one shared normal spell-slot capacity."""

    model_config = ConfigDict(frozen=True)

    source_id: UUID = Field(
        description="Exact runtime source that owns this aggregate capacity.",
    )
    capacities: Tuple[Tuple[int, int], ...] = Field(
        description="Non-zero slot counts in ascending spell-rank order.",
    )
    capacity_modifier_uuids: Tuple[Tuple[int, UUID], ...] = Field(
        description="Exact capacity modifier handle for every normal slot rank.",
    )


class ActionEconomyConfig(BaseModel):
    """Configuration for turn resources, named resources, and spell slots."""

    actions: int = Field(default=1, description="Number of standard actions available")
    actions_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the actions")
    bonus_actions: int = Field(default=1, description="Number of bonus actions available")
    bonus_actions_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the bonus actions")
    reactions: int = Field(default=1, description="Number of reactions available")
    reactions_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the reactions")
    movement: int = Field(default=30, description="Amount of movement available")
    movement_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the movement")
    spell_slots: Dict[int, int] = Field(
        default_factory=dict,
        description="Spell slot counts by level (1-9). E.g., {1: 4, 2: 3} for 4 L1 slots and 3 L2 slots"
    )
    haste_action_policy: HasteActionPolicy = Field(
        default=HasteActionPolicy.BG3_HONOUR,
        description=(
            "Rules policy governing which ordinary actions may spend Haste's "
            "independent turn budget."
        ),
    )


class ActionEconomy(BaseBlock):
    """Turn resources, named resources, movement, and spell slots for an entity.

    Spell slots are stored as `ModifiableValue`s here, with base value 0 for
    non-casters. Spending a slot adds a negative cost modifier; long rest clears
    those spell-slot cost modifiers.
    """

    name: str = Field(default="ActionEconomy", description="Display name for this action economy block.")
    actions: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Actions"
        ),
        description="Standard action count available this turn.",
    )
    bonus_actions: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Bonus Actions"
        ),
        description="Bonus action count available this turn.",
    )
    reactions: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Reactions"
        ),
        description="Reaction count available before recharge.",
    )
    movement: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=30,
            value_name="Movement"
        ),
        description="Movement budget in feet.",
    )
    action_permission: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Action Permission",
        ),
        description="Neutral 1/0 gate for whether this entity may take actions.",
    )
    provokes_opportunity_attacks: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=1,
            value_name="Provokes Opportunity Attacks",
        ),
        description="Neutral 1/0 gate for voluntary-movement opportunity attacks.",
    )
    spell_slot_1: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 1"),
        description="Available level 1 spell slots.",
    )
    spell_slot_2: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 2"),
        description="Available level 2 spell slots.",
    )
    spell_slot_3: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 3"),
        description="Available level 3 spell slots.",
    )
    spell_slot_4: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 4"),
        description="Available level 4 spell slots.",
    )
    spell_slot_5: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 5"),
        description="Available level 5 spell slots.",
    )
    spell_slot_6: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 6"),
        description="Available level 6 spell slots.",
    )
    spell_slot_7: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 7"),
        description="Available level 7 spell slots.",
    )
    spell_slot_8: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 8"),
        description="Available level 8 spell slots.",
    )
    spell_slot_9: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0, value_name="Spell Slot 9"),
        description="Available level 9 spell slots.",
    )
    resources: Dict[str, Resource] = Field(
        default_factory=dict,
        description="Named limited-use resources keyed by resource name.",
    )
    haste_action_policy: HasteActionPolicy = Field(
        default=HasteActionPolicy.BG3_HONOUR,
        description="Rules policy consumed when a Haste effect grants its action.",
    )
    _restricted_action_grants: Dict[str, RestrictedActionGrant] = PrivateAttr(
        default_factory=dict,
    )
    _attack_multiplicity_grants: Dict[
        UUID,
        AttackMultiplicityGrant,
    ] = PrivateAttr(default_factory=dict)
    _normal_spell_slot_capacity_receipt: Optional[
        NormalSpellSlotCapacityReceipt
    ] = PrivateAttr(default=None)
    _normal_spell_slot_floor_modifier_uuids: Dict[int, UUID] = PrivateAttr(
        default_factory=dict,
    )
    _used_debit_receipts: set[UUID] = PrivateAttr(default_factory=set)

    def add_restricted_action_grant(
        self,
        grant: RestrictedActionGrant,
    ) -> None:
        """Install one owned restricted budget at full turn uses."""
        existing = self._restricted_action_grants.get(grant.grant_id)
        if existing is not None:
            existing_contract = (
                existing.resource_name,
                existing.display_name,
                existing.allowed_kinds,
                existing.replaced_cost_types,
                existing.uses_per_turn,
            )
            incoming_contract = (
                grant.resource_name,
                grant.display_name,
                grant.allowed_kinds,
                grant.replaced_cost_types,
                grant.uses_per_turn,
            )
            if existing_contract != incoming_contract:
                raise ValueError(
                    f"restricted action grant {grant.grant_id!r} "
                    "already exists with a different contract"
                )
        elif grant.resource_name in self.resources:
            raise ValueError(
                f"restricted action resource {grant.resource_name!r} "
                "already exists without this grant"
            )
        resource_owner = next(
            (
                item
                for item in self._restricted_action_grants.values()
                if item.grant_id != grant.grant_id
                and item.resource_name == grant.resource_name
            ),
            None,
        )
        if resource_owner is not None:
            raise ValueError(
                f"restricted action resource {grant.resource_name!r} "
                f"is owned by {resource_owner.grant_id!r}"
            )
        self._restricted_action_grants[grant.grant_id] = grant
        self.add_resource_contribution(
            grant.resource_name,
            grant.grant_id,
            maximum=grant.uses_per_turn,
            recharge_type=RechargeType.TURN_START,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )

    def remove_restricted_action_grant(
        self,
        grant_id: str,
        owner_uuid: UUID,
    ) -> None:
        """Remove a grant only when the requesting condition still owns it."""
        grant = self._restricted_action_grants.get(grant_id)
        if grant is None or grant.owner_uuid != owner_uuid:
            return
        del self._restricted_action_grants[grant_id]
        self.remove_resource_contribution(grant.resource_name, grant.grant_id)

    def get_restricted_action_grants(
        self,
    ) -> tuple[RestrictedActionGrant, ...]:
        """Return current grants in deterministic identity order."""
        return tuple(
            self._restricted_action_grants[grant_id]
            for grant_id in sorted(self._restricted_action_grants)
        )

    def add_attack_multiplicity_grant(
        self,
        grant: AttackMultiplicityGrant,
    ) -> None:
        """Install one exact ranked Attack-action entitlement."""
        existing = self._attack_multiplicity_grants.get(grant.grant_id)
        if existing is not None and existing != grant:
            raise ValueError(
                f"attack multiplicity grant {grant.grant_id} already exists "
                "with a different contract",
            )
        self._attack_multiplicity_grants[grant.grant_id] = grant

    def remove_attack_multiplicity_grant(self, grant_id: UUID) -> bool:
        """Remove one exact ranked Attack-action entitlement."""
        return self._attack_multiplicity_grants.pop(
            grant_id,
            None,
        ) is not None

    def resolve_attacks_per_attack_action(self) -> int:
        """Resolve the strongest owned grant without adding class ranks."""
        grants = tuple(self._attack_multiplicity_grants.values())
        if not grants:
            return 1
        winner = min(
            grants,
            key=lambda grant: (
                -grant.attacks_per_attack_action,
                grant.acquisition_ordinal,
                str(grant.grant_id),
            ),
        )
        return winner.attacks_per_attack_action

    def get_attack_multiplicity_grants(
        self,
    ) -> tuple[AttackMultiplicityGrant, ...]:
        """Return ranked grants in deterministic acquisition order."""
        return tuple(
            sorted(
                self._attack_multiplicity_grants.values(),
                key=lambda grant: (
                    grant.acquisition_ordinal,
                    str(grant.grant_id),
                ),
            ),
        )

    def add_resource_contribution(
        self,
        name: str,
        source_id: Union[str, UUID],
        *,
        maximum: int,
        recharge_type: RechargeType,
        capacity_policy: ResourceCapacityPolicy = ResourceCapacityPolicy.SUM,
    ) -> None:
        """Add one exact source-owned capacity contribution.

        Existing expenditure is preserved when a rebuild changes the resolved
        maximum.  All contributors to a named resource must agree on recharge
        timing and combination policy.
        """
        resource = self.resources.get(name)
        if resource is None:
            resource = Resource(
                name=name,
                current=0,
                maximum=0,
                recharge_type=recharge_type,
                capacity_policy=capacity_policy,
            )
            self.resources[name] = resource
        elif resource.recharge_type != recharge_type:
            raise ValueError(
                f"resource {name!r} already uses "
                f"{resource.recharge_type.value} recharge"
            )
        elif resource.capacity_policy != capacity_policy:
            raise ValueError(
                f"resource {name!r} already uses "
                f"{resource.capacity_policy.value} capacity policy"
            )
        resource.set_capacity_contribution(source_id, maximum)

    def remove_resource_contribution(
        self,
        name: str,
        source_id: Union[str, UUID],
    ) -> bool:
        """Remove one source-owned capacity contribution."""
        resource = self.resources.get(name)
        if resource is None:
            return False
        removed = resource.remove_capacity_contribution(source_id)
        if removed and not resource.capacity_contributions:
            del self.resources[name]
        return removed

    def add_resource_recovery_contribution(
        self,
        name: str,
        source_id: Union[str, UUID],
        *,
        trigger: RechargeType,
        amount: int,
    ) -> None:
        """Add one partial recovery rule to an existing named resource."""
        resource = self.resources.get(name)
        if resource is None:
            raise ValueError(
                f"resource {name!r} must exist before recovery is granted",
            )
        resource.set_recovery_contribution(
            source_id,
            trigger=trigger,
            amount=amount,
        )

    def remove_resource_recovery_contribution(
        self,
        name: str,
        source_id: Union[str, UUID],
    ) -> bool:
        """Remove one exact source-owned partial recovery rule."""
        resource = self.resources.get(name)
        if resource is None:
            return False
        return resource.remove_recovery_contribution(source_id)

    def has_resource(self, name: str) -> bool:
        """Check if a resource exists."""
        return name in self.resources

    def can_afford_resource(self, name: str, amount: int = 1) -> bool:
        """Check if a resource has enough uses remaining."""
        resource = self.resources.get(name)
        if resource is None:
            return False
        return resource.can_afford(amount)

    def consume_resource(self, name: str, amount: int = 1) -> bool:
        """Consume uses of a resource. Returns True if successful."""
        resource = self.resources.get(name)
        if resource is None:
            return False
        return resource.consume(amount)

    def get_resource_current(self, name: str) -> int:
        """Get current uses of a resource. Returns 0 if not found."""
        resource = self.resources.get(name)
        return resource.current if resource else 0

    def on_short_rest(self) -> None:
        """Recharge resources that recharge on short rest."""
        for resource in self.resources.values():
            resource.recover_for(RechargeType.SHORT_REST)

    def on_long_rest(self) -> None:
        """Recharge resources that recharge on short or long rest."""
        for resource in self.resources.values():
            resource.recover_for(RechargeType.LONG_REST)

    def on_turn_start(self) -> None:
        """Recharge resources that recharge on turn start."""
        for resource in self.resources.values():
            resource.recover_for(RechargeType.TURN_START)

    def spell_slot_value(self, level: int) -> ModifiableValue:
        """Get the ModifiableValue for a spell slot level."""
        slot_map = {
            1: self.spell_slot_1, 2: self.spell_slot_2, 3: self.spell_slot_3,
            4: self.spell_slot_4, 5: self.spell_slot_5, 6: self.spell_slot_6,
            7: self.spell_slot_7, 8: self.spell_slot_8, 9: self.spell_slot_9,
        }
        if level not in slot_map:
            raise ValueError(f"Invalid spell slot level: {level}")
        return slot_map[level]

    @staticmethod
    def _validate_normal_spell_slot_capacities(
        capacities: Dict[int, int],
    ) -> Tuple[Tuple[int, int], ...]:
        """Validate and canonicalize one aggregate normal-slot capacity."""
        canonical: List[Tuple[int, int]] = []
        for rank, count in capacities.items():
            if (
                isinstance(rank, bool)
                or not isinstance(rank, int)
                or rank < 1
                or rank > 9
            ):
                raise ValueError(
                    f"normal spell-slot rank must be an integer from 1 to 9: "
                    f"{rank!r}"
                )
            if (
                isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
            ):
                raise ValueError(
                    f"normal spell-slot count must be a non-negative integer: "
                    f"{count!r}"
                )
            if count > 0:
                canonical.append((rank, count))
        canonical.sort()
        return tuple(canonical)

    def _validate_installed_normal_spell_slot_capacity(self) -> None:
        """Fail closed if an installed receipt no longer owns its modifiers."""
        receipt = self._normal_spell_slot_capacity_receipt
        if receipt is None:
            return
        for rank, modifier_uuid in receipt.capacity_modifier_uuids:
            value = self.spell_slot_value(rank)
            if modifier_uuid not in value.self_static.value_modifiers:
                raise RuntimeError(
                    "installed normal spell-slot capacity lost an owned "
                    f"modifier for rank {rank}"
                )

    def _ensure_normal_spell_slot_floor(self, rank: int) -> UUID:
        """Install the infrastructure floor that prevents negative slots."""
        value = self.spell_slot_value(rank)
        existing_uuid = self._normal_spell_slot_floor_modifier_uuids.get(rank)
        if existing_uuid is not None:
            existing = value.self_static.min_constraints.get(existing_uuid)
            if (
                existing is None
                or existing.name != "Normal Spell Slot Availability Floor"
                or existing.value != 0
            ):
                raise RuntimeError(
                    "normal spell-slot availability floor ownership conflict "
                    f"for rank {rank}"
                )
            return existing_uuid
        floor = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid,
            name="Normal Spell Slot Availability Floor",
            value=0,
        )
        value.self_static.add_min_constraint(floor)
        self._normal_spell_slot_floor_modifier_uuids[rank] = floor.uuid
        return floor.uuid

    def set_normal_spell_slot_capacity(
        self,
        source_id: UUID,
        capacities: Dict[int, int],
    ) -> NormalSpellSlotCapacityReceipt:
        """Set the one shared normal spell-slot capacity.

        This is an authoritative aggregate, not another spell-slot pool.
        Installing a different source replaces the prior aggregate through its
        exact modifier handles. Existing cost modifiers remain in place, so
        already-spent slots survive level, multiclass, and respec rebuilds.
        Reusing one source with a different contract is rejected.
        """
        if not isinstance(source_id, UUID):
            raise ValueError("normal spell-slot capacity source must be a UUID")
        canonical = self._validate_normal_spell_slot_capacities(capacities)
        existing = self._normal_spell_slot_capacity_receipt
        self._validate_installed_normal_spell_slot_capacity()
        if existing is not None and existing.source_id == source_id:
            if existing.capacities == canonical:
                return existing
            raise ValueError(
                f"source {source_id} already owns a different normal "
                "spell-slot capacity"
            )

        old_handles = (
            dict(existing.capacity_modifier_uuids)
            if existing is not None
            else {}
        )
        desired_by_rank = dict(canonical)
        baselines: Dict[int, int] = {}
        for rank in range(1, 10):
            excluded_modifier_uuids = {
                modifier.uuid
                for modifier in self.get_cost_modifiers(
                    spell_slot_cost_type(rank)
                )
            }
            old_handle = old_handles.get(rank)
            if old_handle is not None:
                excluded_modifier_uuids.add(old_handle)
            baselines[rank] = self.spell_slot_value(
                rank
            ).normalized_score_excluding_static_modifiers(
                excluded_modifier_uuids
            )

        for rank, modifier_uuid in old_handles.items():
            self.spell_slot_value(rank).self_static.remove_value_modifier(
                modifier_uuid
            )

        new_handles: List[Tuple[int, UUID]] = []
        for rank in range(1, 10):
            self._ensure_normal_spell_slot_floor(rank)
            capacity_modifier = NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name=(
                    "Normal Spell Slot Capacity "
                    f"{source_id} Rank {rank}"
                ),
                value=desired_by_rank.get(rank, 0) - baselines[rank],
            )
            self.spell_slot_value(rank).self_static.add_value_modifier(
                capacity_modifier
            )
            new_handles.append((rank, capacity_modifier.uuid))

        receipt = NormalSpellSlotCapacityReceipt(
            source_id=source_id,
            capacities=canonical,
            capacity_modifier_uuids=tuple(new_handles),
        )
        self._normal_spell_slot_capacity_receipt = receipt
        return receipt

    def get_normal_spell_slot_capacity_source(self) -> Optional[UUID]:
        """Return the exact owner of the active aggregate, when installed."""
        receipt = self._normal_spell_slot_capacity_receipt
        return receipt.source_id if receipt is not None else None

    def get_normal_spell_slot_capacities(self) -> Dict[int, int]:
        """Return the authoritative installed aggregate by spell-slot rank."""
        self._validate_installed_normal_spell_slot_capacity()
        receipt = self._normal_spell_slot_capacity_receipt
        return dict(receipt.capacities) if receipt is not None else {}

    def remove_normal_spell_slot_capacity(self, source_id: UUID) -> bool:
        """Remove the aggregate only when the requesting source still owns it."""
        receipt = self._normal_spell_slot_capacity_receipt
        if receipt is None or receipt.source_id != source_id:
            return False
        self._validate_installed_normal_spell_slot_capacity()
        for rank, modifier_uuid in receipt.capacity_modifier_uuids:
            self.spell_slot_value(rank).self_static.remove_value_modifier(
                modifier_uuid
            )
        self._normal_spell_slot_capacity_receipt = None
        return True

    def _get_value_for_cost_type(self, cost_type: CostType) -> ModifiableValue:
        """Get the ModifiableValue for a cost type."""
        if cost_type == "actions":
            return self.actions
        elif cost_type == "bonus_actions":
            return self.bonus_actions
        elif cost_type == "reactions":
            return self.reactions
        elif cost_type == "movement":
            return self.movement
        elif cost_type.startswith("spell_slot_"):
            level = int(cost_type.split("_")[-1])
            return self.spell_slot_value(level)
        else:
            raise ValueError(f"Unknown cost type: {cost_type}")

    def get_base_value(self, cost_type: CostType) -> int:
        """Get the base value for a given action type."""
        value = self._get_value_for_cost_type(cost_type)
        base_mod = value.get_base_modifier()
        return base_mod.normalized_value if base_mod else 0

    def get_cost_modifiers(self, cost_type: CostType) -> List[NumericalModifier]:
        """Get all cost modifiers (negative values) for a given action type."""
        value = self._get_value_for_cost_type(cost_type)
        return [mod for mod in value.self_static.value_modifiers.values()
                if mod.name is not None and "cost" in mod.name]

    def current_speed(self) -> int:
        """Return movement speed before spending movement or applying Dash.

        Returns:
            Current constrained speed including ordinary speed modifiers while
            excluding turn expenditure and existing Dash budget modifiers.
        """
        excluded_modifier_uuids = {
            modifier.uuid
            for modifier in self.get_cost_modifiers("movement")
        }
        excluded_modifier_uuids.update(
            modifier.uuid
            for modifier in self.movement.self_static.value_modifiers.values()
            if modifier.name == "Dashing"
        )
        return max(
            0,
            self.movement.normalized_score_excluding_static_modifiers(
                excluded_modifier_uuids
            ),
        )

    def can_afford(self, cost_type: CostType, amount: int) -> bool:
        """Check if the entity can afford a given action type and amount.

        Uses value.normalized_score which accounts for all modifiers including
        max constraints from conditions like Incapacitated.
        """
        value = self._get_value_for_cost_type(cost_type)
        return value.normalized_score - amount >= 0

    def reset_all_costs(self) -> None:
        """Reset turn-based costs (actions, bonus_actions, reactions, movement).

        Called at the start of each turn. Does NOT reset spell slot costs -
        use reset_spell_slot_costs() for long rest.
        """
        turn_based_types: List[CostType] = ["actions", "bonus_actions", "reactions", "movement"]
        for cost_type in turn_based_types:
            value = self._get_value_for_cost_type(cost_type)
            for modifier in self.get_cost_modifiers(cost_type):
                value.self_static.remove_value_modifier(modifier.uuid)

    def reset_spell_slot_costs(self) -> None:
        """Reset spell slot costs (restore all spell slots).

        Called on long rest.
        """
        for level in range(1, 10):
            cost_type = spell_slot_cost_type(level)
            value = self.spell_slot_value(level)
            for modifier in self.get_cost_modifiers(cost_type):
                value.self_static.remove_value_modifier(modifier.uuid)

    def consume(self, cost_type: CostType, amount: int, cost_name: Optional[str] = None) -> None:
        """Consume a turn resource, named action bucket, or spell slot.

        Uses the full `normalized_score` rather than only static modifiers so
        contextual bonuses and constraints affect affordability consistently.
        """
        self.consume_aggregate_with_receipt((ActionEconomyChannelCost(
            cost_type=cost_type,
            amount=amount,
            name=cost_name,
        ),))

    def consume_prevalidated(
        self,
        cost_type: CostType,
        amount: int,
        cost_name: Optional[str] = None,
    ) -> None:
        """Commit a cost that was admitted before the action's causal effects.

        Action application validates affordability before publishing its
        declaration. A reaction during that action may then incapacitate or
        kill the actor, installing capability constraints before the terminal
        cost is recorded. Rechecking the post-effect normalized value would
        reject an already-admitted action and break its event lifecycle.

        Callers must use this method only at that committed action boundary;
        ordinary callers use :meth:`consume`, which performs affordability
        validation.
        """
        self.install_prevalidated_aggregate_with_receipt((
            ActionEconomyChannelCost(
                cost_type=cost_type,
                amount=amount,
                name=cost_name,
            ),
        ))

    @staticmethod
    def _aggregate_channel_costs(
        costs: Sequence[ActionEconomyChannelCost],
    ) -> Tuple[ActionEconomyChannelCost, ...]:
        """Validate and combine repeated typed channels deterministically."""
        totals: Dict[CostType, int] = {}
        labels: Dict[CostType, set[str]] = {}
        for cost in costs:
            if type(cost) is not ActionEconomyChannelCost:
                raise TypeError("aggregate debits accept ActionEconomyChannelCost only")
            totals[cost.cost_type] = totals.get(cost.cost_type, 0) + cost.amount
            if cost.name:
                labels.setdefault(cost.cost_type, set()).add(cost.name)
        return tuple(
            ActionEconomyChannelCost(
                cost_type=cost_type,
                amount=totals[cost_type],
                name=(
                    " + ".join(sorted(labels.get(cost_type, set())))
                    or None
                ),
            )
            for cost_type in sorted(totals)
            if totals[cost_type] > 0
        )

    def install_prevalidated_aggregate_with_receipt(
        self,
        costs: Sequence[ActionEconomyChannelCost],
    ) -> ActionEconomyDebitReceipt:
        """Install an admitted aggregate without rechecking affordability."""
        aggregated = self._aggregate_channel_costs(costs)
        installed: List[ActionEconomyDebitHandle] = []
        pending_modifier: Optional[NumericalModifier] = None
        pending_cost_type: Optional[CostType] = None
        try:
            for cost in aggregated:
                value = self._get_value_for_cost_type(cost.cost_type)
                modifier_name = (
                    f"{cost.name}_cost" if cost.name is not None else "cost"
                )
                modifier = NumericalModifier.create(
                    source_entity_uuid=self.source_entity_uuid,
                    name=modifier_name,
                    value=-cost.amount,
                )
                pending_modifier = modifier
                pending_cost_type = cost.cost_type
                value.self_static.add_value_modifier(modifier)
                installed.append(ActionEconomyDebitHandle(
                    cost_type=cost.cost_type,
                    modifier_uuid=modifier.uuid,
                    amount=cost.amount,
                    modifier_name=modifier_name,
                ))
                pending_modifier = None
                pending_cost_type = None
        except Exception:
            if pending_modifier is not None and pending_cost_type is not None:
                pending_value = self._get_value_for_cost_type(pending_cost_type)
                pending_value.self_static.remove_value_modifier(
                    pending_modifier.uuid
                )
                pending_modifier.remove_from_register()
            for handle in reversed(installed):
                value = self._get_value_for_cost_type(handle.cost_type)
                modifier = value.self_static.value_modifiers.get(
                    handle.modifier_uuid
                )
                value.self_static.remove_value_modifier(handle.modifier_uuid)
                if modifier is not None:
                    modifier.remove_from_register()
            raise
        return ActionEconomyDebitReceipt(
            owner_uuid=self.uuid,
            handles=tuple(installed),
        )

    def consume_aggregate_with_receipt(
        self,
        costs: Sequence[ActionEconomyChannelCost],
    ) -> ActionEconomyDebitReceipt:
        """Prove current aggregate affordability and install it exactly once."""
        aggregated = self._aggregate_channel_costs(costs)
        unaffordable = next(
            (
                cost
                for cost in aggregated
                if not self.can_afford(cost.cost_type, cost.amount)
            ),
            None,
        )
        if unaffordable is not None:
            raise ValueError(
                f"Not enough {unaffordable.cost_type} to consume "
                f"{unaffordable.amount} aggregate cost"
            )
        return self.install_prevalidated_aggregate_with_receipt(aggregated)

    def undo_prevalidated_debit(
        self,
        receipt: ActionEconomyDebitReceipt,
    ) -> None:
        """Remove only still-exact modifiers from one unused owned receipt."""
        if type(receipt) is not ActionEconomyDebitReceipt:
            raise TypeError("debit undo requires an ActionEconomyDebitReceipt")
        if (
            type(receipt.receipt_uuid) is not UUID
            or type(receipt.owner_uuid) is not UUID
            or type(receipt.handles) is not tuple
        ):
            raise TypeError("debit receipt has malformed identity or handles")
        if receipt.owner_uuid != self.uuid:
            raise ValueError("debit receipt belongs to another action economy")
        if receipt.receipt_uuid in self._used_debit_receipts:
            raise ValueError("debit receipt has already been used")

        exact_modifiers: List[Tuple[ActionEconomyDebitHandle, NumericalModifier]] = []
        for handle in receipt.handles:
            if (
                type(handle) is not ActionEconomyDebitHandle
                or type(handle.cost_type) is not str
                or type(handle.modifier_uuid) is not UUID
                or type(handle.amount) is not int
                or handle.amount < 0
                or type(handle.modifier_name) is not str
            ):
                raise TypeError("debit handle has malformed typed evidence")
            value = self._get_value_for_cost_type(handle.cost_type)
            modifier = value.self_static.value_modifiers.get(handle.modifier_uuid)
            if (
                type(modifier) is not NumericalModifier
                or modifier.name != handle.modifier_name
                or modifier.value != -handle.amount
                or modifier.source_entity_uuid != self.source_entity_uuid
            ):
                raise ValueError("debit receipt no longer names exact installed state")
            exact_modifiers.append((handle, modifier))

        for handle, modifier in exact_modifiers:
            value = self._get_value_for_cost_type(handle.cost_type)
            value.self_static.remove_value_modifier(handle.modifier_uuid)
            modifier.remove_from_register()
        self._used_debit_receipts.add(receipt.receipt_uuid)

    def commit_fixed_costs_without_dispatch(
        self,
        *,
        channel_costs: Sequence[ActionEconomyChannelCost],
        resource_costs: Sequence[NamedResourceCost],
    ) -> FixedCostCommitReceipt:
        """Synchronously commit disjoint fixed channels and named resources."""
        aggregated_channels = self._aggregate_channel_costs(channel_costs)
        resource_totals: Dict[str, int] = {}
        for cost in resource_costs:
            if type(cost) is not NamedResourceCost:
                raise TypeError("fixed resources accept NamedResourceCost only")
            resource_totals[cost.name] = resource_totals.get(cost.name, 0) + cost.amount
        aggregated_resources = tuple(
            NamedResourceCost(name=name, amount=resource_totals[name])
            for name in sorted(resource_totals)
        )

        if any(
            not self.can_afford(cost.cost_type, cost.amount)
            for cost in aggregated_channels
        ) or any(
            not self.can_afford_resource(cost.name, cost.amount)
            for cost in aggregated_resources
        ):
            raise FixedCostCommitError("fixed costs are no longer affordable")

        try:
            channel_receipt = self.install_prevalidated_aggregate_with_receipt(
                aggregated_channels
            )
        except Exception as exc:
            raise FixedCostCommitError("failed to install fixed channel costs") from exc

        consumed_resources: List[Tuple[Resource, int]] = []
        try:
            for cost in aggregated_resources:
                resource = self.resources[cost.name]
                previous = resource.current
                consumed_resources.append((resource, previous))
                if not resource.consume(cost.amount):
                    raise RuntimeError("prevalidated resource became unavailable")
        except Exception as exc:
            for resource, previous in reversed(consumed_resources):
                resource.current = previous
            self.undo_prevalidated_debit(channel_receipt)
            raise FixedCostCommitError("failed to install fixed resource costs") from exc

        return FixedCostCommitReceipt(
            channel_receipt=channel_receipt,
            resources=aggregated_resources,
        )

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "ActionEconomy", source_entity_name: Optional[str] = None,
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None,
               config: Optional[ActionEconomyConfig] = None) -> 'ActionEconomy':
        """Create an action economy block from optional configuration."""
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name,
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            actions = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.actions, value_name="Actions")
            for modifier in config.actions_modifiers:
                actions.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))

            bonus_actions = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.bonus_actions, value_name="Bonus Actions")
            for modifier in config.bonus_actions_modifiers:
                bonus_actions.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))

            reactions = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.reactions, value_name="Reactions")
            for modifier in config.reactions_modifiers:
                reactions.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))

            movement = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.movement, value_name="Movement")
            for modifier in config.movement_modifiers:
                movement.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))

            spell_slot_1 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(1, 0), value_name="Spell Slot 1")
            spell_slot_2 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(2, 0), value_name="Spell Slot 2")
            spell_slot_3 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(3, 0), value_name="Spell Slot 3")
            spell_slot_4 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(4, 0), value_name="Spell Slot 4")
            spell_slot_5 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(5, 0), value_name="Spell Slot 5")
            spell_slot_6 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(6, 0), value_name="Spell Slot 6")
            spell_slot_7 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(7, 0), value_name="Spell Slot 7")
            spell_slot_8 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(8, 0), value_name="Spell Slot 8")
            spell_slot_9 = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.spell_slots.get(9, 0), value_name="Spell Slot 9")

            return cls(
                source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name,
                target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name,
                actions=actions, bonus_actions=bonus_actions, reactions=reactions, movement=movement,
                spell_slot_1=spell_slot_1, spell_slot_2=spell_slot_2, spell_slot_3=spell_slot_3,
                spell_slot_4=spell_slot_4, spell_slot_5=spell_slot_5, spell_slot_6=spell_slot_6,
                spell_slot_7=spell_slot_7, spell_slot_8=spell_slot_8, spell_slot_9=spell_slot_9,
                haste_action_policy=config.haste_action_policy,
            )
