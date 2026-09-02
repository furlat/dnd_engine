from pydantic import Field, computed_field, model_validator
from typing import List, Optional, Dict, Any, Callable, ClassVar, Union, Self
from uuid import UUID, uuid4, uuid5
from dnd.core.base_object import BaseObject
from dnd.core.creature_types import DamageType, Size
from dnd.core.modifiers import (
    naming_callable,
    NumericalModifier,
    AdvantageModifier,
    CriticalModifier,
    AutoHitModifier,
    AdvantageStatus,
    CriticalStatus,
    AutoHitStatus,
    SizeModifier,
    DamageTypeModifier,
    ContextualNumericalModifier,
    ContextualAdvantageModifier,
    ContextualCriticalModifier,
    ContextualAutoHitModifier,
    ContextualSizeModifier,
    ContextualDamageTypeModifier,
    ResistanceModifier,
    ContextualResistanceModifier,
    ResistanceStatus,
)
import random


def identity(x: int) -> int:
    """Return an integer unchanged.

    Args:
        x: Integer to return.

    Returns:
        The same integer.
    """
    return x

class BaseValue(BaseObject):
    """Base model for UUID-addressable values.

    Values extend `BaseObject` with score normalization and generation-chain
    metadata. Concrete subclasses define how modifiers are stored and
    aggregated.
    """

    _registry: ClassVar[Dict[UUID, 'BaseValue']] = {}

    name: str = Field(
        default="A Value",
        description="Human-readable name used in breakdowns and serialized value metadata."
    )
    uuid: UUID = Field(
        default_factory=uuid4,
        description="Stable UUID used for value registry lookup and modifier ownership."
    )
    source_entity_uuid: UUID = Field(
        ...,
        description="Entity UUID that owns or produced this value."
    )
    source_entity_name: Optional[str] = Field(
        default=None,
        description="Optional display name for the value's source entity."
    )
    target_entity_uuid: Optional[UUID] = Field(
        default=None,
        description="Entity UUID currently targeted while evaluating this value, if any."
    )
    target_entity_name: Optional[str] = Field(
        default=None,
        description="Optional display name for the current target entity."
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Runtime context used by contextual modifiers during evaluation."
    )
    score_normalizer: Callable[[int], int] = Field(
        default=identity,
        exclude=True,
        description="Callable that converts raw scores into normalized scores."
    )
    generated_from: List[UUID] = Field(
        default_factory=list,
        description="Value UUIDs that were combined or copied to produce this value."
    )
    global_normalizer: bool = Field(
        default=True,
        description="Whether this value's normalizer also applies to numerical modifiers."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['BaseValue']:
        """Retrieve a value from the value registry by UUID.

        Args:
            uuid: UUID of the value to retrieve.

        Returns:
            The registered value when found, otherwise `None`.

        Raises:
            ValueError: If the UUID resolves to a non-value object.
        """
        value = cls._registry.get(uuid)
        if value is None:
            return None
        elif isinstance(value, BaseValue):
            return value
        else:
            raise ValueError(f"Value with UUID {uuid} is not a BaseValue, but {type(value)}")

    def validate_modifier_target(self, modifier: Union[NumericalModifier, AdvantageModifier, CriticalModifier, AutoHitModifier, SizeModifier, DamageTypeModifier, ResistanceModifier, ContextualNumericalModifier, ContextualAdvantageModifier, ContextualCriticalModifier, ContextualAutoHitModifier, ContextualSizeModifier, ContextualDamageTypeModifier, ContextualResistanceModifier]) -> None:
        """Validate whether a modifier can be attached to this value.

        Args:
            modifier: Modifier candidate.
        """
        pass

class StaticValue(BaseValue):
    """Non-contextual modifier bucket for one value channel.

    `StaticValue` stores numerical modifiers, constraints, advantage,
    critical, auto-hit, size, damage-type, and resistance modifiers that are
    always considered when the channel is aggregated.
    """

    value_modifiers: Dict[UUID, NumericalModifier] = Field(
        default_factory=dict,
        description="Flat numerical bonuses or penalties that contribute to the channel score."
    )
    min_constraints: Dict[UUID, NumericalModifier] = Field(
        default_factory=dict,
        description="Lower bounds applied after numerical modifiers are summed."
    )
    max_constraints: Dict[UUID, NumericalModifier] = Field(
        default_factory=dict,
        description="Upper bounds applied after numerical modifiers are summed."
    )
    advantage_modifiers: Dict[UUID, AdvantageModifier] = Field(
        default_factory=dict,
        description="Advantage and disadvantage modifiers aggregated by numerical sign."
    )
    critical_modifiers: Dict[UUID, CriticalModifier] = Field(
        default_factory=dict,
        description="Critical-hit outcome modifiers such as autocrit or critical immunity."
    )
    auto_hit_modifiers: Dict[UUID, AutoHitModifier] = Field(
        default_factory=dict,
        description="Forced hit and forced miss modifiers for attack outcome resolution."
    )
    is_outgoing_modifier: bool = Field(
        default=False,
        description="Whether this bucket stores modifiers intended to affect another entity's value."
    )
    size_modifiers: Dict[UUID, SizeModifier] = Field(
        default_factory=dict,
        description="Size modifiers used when a value needs an effective creature or object size."
    )
    damage_type_modifiers: Dict[UUID, DamageTypeModifier] = Field(
        default_factory=dict,
        description="Damage type modifiers used to derive one or more effective damage types."
    )
    resistance_modifiers: Dict[UUID, ResistanceModifier] = Field(
        default_factory=dict,
        description="Resistance, vulnerability, and immunity modifiers keyed by modifier UUID."
    )
    largest_size_priority: bool = Field(
        default=True,
        description="Whether size aggregation chooses the largest size instead of the smallest size."
    )

    @model_validator(mode="after")
    def validate_value_source_corresponds_to_modifiers_target(self) -> Self:
        """Validate outgoing numerical modifiers do not target their own source.

        Returns:
            This value after validation.

        Raises:
            ValueError: If an outgoing modifier targets the value source.
        """
        for modifier in list(self.value_modifiers.values()) + list(self.min_constraints.values()) + list(self.max_constraints.values()):
            if self.is_outgoing_modifier:
                if modifier.target_entity_uuid == self.source_entity_uuid:
                    raise ValueError(f"Outgoing modifier target ({modifier.target_entity_uuid}) should not be the same as the value source ({self.source_entity_uuid})")

        return self

    @classmethod
    def get(cls, uuid: UUID) -> 'StaticValue':
        """Retrieve a static value by UUID.

        Args:
            uuid: UUID of the value to retrieve.

        Returns:
            The registered static value.

        Raises:
            ValueError: If the UUID does not resolve to a `StaticValue`.
        """
        value = cls._registry.get(uuid)
        if not isinstance(value, StaticValue):
            raise ValueError(f"Value with UUID {uuid} is not a StaticValue, but {type(value)}")
        return value

    def add_value_modifier(self, modifier: NumericalModifier) -> UUID:
        """Add a numerical modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        self.value_modifiers[modifier.uuid] = modifier
        return modifier.uuid

    def remove_value_modifier(self, uuid: UUID) -> None:
        """Remove a numerical modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        self.value_modifiers.pop(uuid, None)

    def add_min_constraint(self, constraint: NumericalModifier) -> UUID:
        """Add a minimum score constraint.

        Args:
            constraint: Constraint to add.

        Returns:
            UUID of the added constraint.
        """
        self.min_constraints[constraint.uuid] = constraint
        return constraint.uuid

    def remove_min_constraint(self, uuid: UUID) -> None:
        """Remove a minimum score constraint.

        Args:
            uuid: UUID of the constraint to remove.
        """
        self.min_constraints.pop(uuid, None)

    def add_max_constraint(self, constraint: NumericalModifier) -> UUID:
        """Add a maximum score constraint.

        Args:
            constraint: Constraint to add.

        Returns:
            UUID of the added constraint.
        """
        self.max_constraints[constraint.uuid] = constraint
        return constraint.uuid

    def remove_max_constraint(self, uuid: UUID) -> None:
        """Remove a maximum score constraint.

        Args:
            uuid: UUID of the constraint to remove.
        """
        self.max_constraints.pop(uuid, None)

    def add_advantage_modifier(self, modifier: AdvantageModifier) -> UUID:
        """Add an advantage or disadvantage modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        self.advantage_modifiers[modifier.uuid] = modifier
        return modifier.uuid

    def remove_advantage_modifier(self, uuid: UUID) -> None:
        """Remove an advantage or disadvantage modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        self.advantage_modifiers.pop(uuid, None)

    def add_critical_modifier(self, modifier: CriticalModifier) -> UUID:
        """Add a critical outcome modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        self.critical_modifiers[modifier.uuid] = modifier
        return modifier.uuid

    def remove_critical_modifier(self, uuid: UUID) -> None:
        """Remove a critical outcome modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        self.critical_modifiers.pop(uuid, None)

    def add_auto_hit_modifier(self, modifier: AutoHitModifier) -> UUID:
        """Add an auto-hit or auto-miss modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        self.auto_hit_modifiers[modifier.uuid] = modifier
        return modifier.uuid

    def remove_auto_hit_modifier(self, uuid: UUID) -> None:
        """Remove an auto-hit or auto-miss modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        self.auto_hit_modifiers.pop(uuid, None)

    def add_size_modifier(self, modifier: SizeModifier) -> UUID:
        """Add a size modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        self.size_modifiers[modifier.uuid] = modifier
        return modifier.uuid

    def remove_size_modifier(self, uuid: UUID) -> None:
        """Remove a size modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        self.size_modifiers.pop(uuid, None)

    def add_damage_type_modifier(self, modifier: DamageTypeModifier) -> UUID:
        """Add a damage type modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        self.damage_type_modifiers[modifier.uuid] = modifier
        return modifier.uuid

    def remove_damage_type_modifier(self, uuid: UUID) -> None:
        """Remove a damage type modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        self.damage_type_modifiers.pop(uuid, None)

    def add_resistance_modifier(self, modifier: ResistanceModifier) -> UUID:
        """Add a resistance, vulnerability, or immunity modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        self.resistance_modifiers[modifier.uuid] = modifier
        return modifier.uuid

    def remove_resistance_modifier(self, uuid: UUID) -> None:
        """Remove a resistance, vulnerability, or immunity modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        self.resistance_modifiers.pop(uuid, None)

    def remove_modifier(self, uuid: UUID) -> None:
        """Remove a modifier UUID from every static modifier bucket.

        Args:
            uuid: UUID of the modifier to remove.
        """
        self.remove_value_modifier(uuid)
        self.remove_min_constraint(uuid)
        self.remove_max_constraint(uuid)
        self.remove_advantage_modifier(uuid)
        self.remove_critical_modifier(uuid)
        self.remove_auto_hit_modifier(uuid)
        self.remove_size_modifier(uuid)
        self.remove_damage_type_modifier(uuid)
        self.remove_resistance_modifier(uuid)

    @computed_field
    @property
    def min(self) -> Optional[int]:
        """Return the lowest active minimum score constraint.

        Returns:
            Minimum constraint value when present, otherwise `None`.
        """
        if not self.min_constraints:
            return None
        return min(constraint.value for constraint in self.min_constraints.values())

    @computed_field
    @property
    def max(self) -> Optional[int]:
        """Return the highest active maximum score constraint.

        Returns:
            Maximum constraint value when present, otherwise `None`.
        """
        if not self.max_constraints:
            return None
        return max(constraint.value for constraint in self.max_constraints.values())

    def _score(self, normalized: bool = False) -> int:
        """Calculate the channel score after numerical modifiers and constraints.

        Args:
            normalized: Whether to read each modifier's normalized value.

        Returns:
            Final score after minimum and maximum constraints are applied.
        """
        modifier_sum = sum(modifier.value if not normalized else modifier.normalized_value for modifier in self.value_modifiers.values())
        if self.max is not None and self.min is not None:
            return max(self.min, min(modifier_sum, self.max))
        elif self.max is not None:
            return min(modifier_sum, self.max)
        elif self.min is not None:
            return max(self.min, modifier_sum)
        else:
            return modifier_sum

    @computed_field
    @property
    def score(self) -> int:
        """Return the raw channel score.

        Returns:
            Final score before normalizing numerical modifiers.
        """
        return self._score()

    @computed_field
    @property
    def normalized_score(self) -> int:
        """Return the score using normalized numerical modifiers.

        Returns:
            Score computed from each modifier's normalized value.
        """
        return self._score(normalized=True)

    def normalized_score_excluding(self, modifier_uuids: set[UUID]) -> int:
        """Return the normalized static score without selected value modifiers.

        Args:
            modifier_uuids: Numerical modifier UUIDs omitted from the sum.

        Returns:
            Filtered score with this channel's constraints still applied.
        """
        modifier_sum = sum(
            modifier.normalized_value
            for modifier_uuid, modifier in self.value_modifiers.items()
            if modifier_uuid not in modifier_uuids
        )
        if self.max is not None and self.min is not None:
            return max(self.min, min(modifier_sum, self.max))
        if self.max is not None:
            return min(modifier_sum, self.max)
        if self.min is not None:
            return max(self.min, modifier_sum)
        return modifier_sum

    @computed_field
    @property
    def advantage_sum(self) -> int:
        """Return the signed aggregate of advantage modifiers.

        Returns:
            Positive values mean advantage, negative values mean disadvantage.
        """
        return sum(modifier.numerical_value for modifier in self.advantage_modifiers.values())

    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """Return the final advantage state.

        Returns:
            Advantage, disadvantage, or none after signed aggregation.
        """
        if self.advantage_sum > 0:
            return AdvantageStatus.ADVANTAGE
        elif self.advantage_sum < 0:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE

    @computed_field
    @property
    def critical(self) -> CriticalStatus:
        """Return the final critical-hit override state.

        Returns:
            `NOCRIT`, `AUTOCRIT`, or `NONE`, with `NOCRIT` taking precedence.
        """
        if CriticalStatus.NOCRIT in (mod.value for mod in self.critical_modifiers.values()):
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in (mod.value for mod in self.critical_modifiers.values()):
            return CriticalStatus.AUTOCRIT
        else:
            return CriticalStatus.NONE

    @computed_field
    @property
    def auto_hit(self) -> AutoHitStatus:
        """Return the final hit override state.

        Returns:
            `AUTOMISS`, `AUTOHIT`, or `NONE`, with `AUTOMISS` taking precedence.
        """
        if AutoHitStatus.AUTOMISS in (mod.value for mod in self.auto_hit_modifiers.values()):
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in (mod.value for mod in self.auto_hit_modifiers.values()):
            return AutoHitStatus.AUTOHIT
        else:
            return AutoHitStatus.NONE

    @computed_field
    @property
    def size(self) -> Size:
        """Return the effective size from static size modifiers.

        Returns:
            Effective size, defaulting to `MEDIUM` when no modifiers exist.
        """
        if not self.size_modifiers:
            return Size.MEDIUM

        sizes = [modifier.value for modifier in self.size_modifiers.values()]
        if self.largest_size_priority:
            return max(sizes, key=lambda s: list(Size).index(s))
        else:
            return min(sizes, key=lambda s: list(Size).index(s))

    @computed_field
    @property
    def damage_types(self) -> List[DamageType]:
        """Return the most common damage types in this channel.

        Returns:
            Damage types tied for highest occurrence.
        """
        if not self.damage_type_modifiers:
            return []

        type_counts = {}
        for modifier in self.damage_type_modifiers.values():
            type_counts[modifier.value] = type_counts.get(modifier.value, 0) + 1

        max_count = max(type_counts.values())
        if max_count == 0:
            return []
        most_common_types = [dt for dt, count in type_counts.items() if count == max_count]

        return most_common_types

    @computed_field
    @property
    def damage_type(self) -> Optional[DamageType]:
        """Return one representative damage type.

        Returns:
            Randomly selected damage type from the most common types, or `None`.
        """
        most_common_types = self.damage_types
        if not most_common_types:
            return None
        return random.choice(most_common_types)

    @computed_field
    @property
    def resistance_sum(self) -> Dict[DamageType, int]:
        """Return signed resistance totals by damage type.

        Returns:
            Damage type to signed resistance total.
        """
        resistance_sum = {damage_type: 0 for damage_type in DamageType}
        for modifier in self.resistance_modifiers.values():
            resistance_sum[modifier.damage_type] += modifier.numerical_value
        return resistance_sum

    @computed_field
    @property
    def resistance(self) -> Dict[DamageType, ResistanceStatus]:
        """Return final resistance states by damage type.

        Returns:
            Damage type to vulnerability, none, resistance, or immunity.
        """
        resistance = {}
        for damage_type, sum_value in self.resistance_sum.items():
            if sum_value > 1:
                resistance[damage_type] = ResistanceStatus.IMMUNITY
            elif sum_value == 1:
                resistance[damage_type] = ResistanceStatus.RESISTANCE
            elif sum_value == 0:
                resistance[damage_type] = ResistanceStatus.NONE
            else:
                resistance[damage_type] = ResistanceStatus.VULNERABILITY
        return resistance

    def combine_values(self, others: List['StaticValue'], naming_callable: Optional[naming_callable] = None) -> 'StaticValue':
        """Combine this value with other static values.

        Args:
            others: Static values to merge with this value.
            naming_callable: Optional function that names the combined value
                from the source value names.

        Returns:
            New static value containing all modifier buckets from each source.

        Raises:
            ValueError: If any other value has a different source entity UUID.
        """
        if naming_callable is None:
            naming_callable = lambda names: "_".join(names)

        for other in others:
            self.validate_source_id(other.source_entity_uuid)

        return StaticValue(
            name=naming_callable([self.name] + [other.name for other in others]),
            value_modifiers={**self.value_modifiers, **{k: v for other in others for k, v in other.value_modifiers.items()}},
            min_constraints={**self.min_constraints, **{k: v for other in others for k, v in other.min_constraints.items()}},
            max_constraints={**self.max_constraints, **{k: v for other in others for k, v in other.max_constraints.items()}},
            advantage_modifiers={**self.advantage_modifiers, **{k: v for other in others for k, v in other.advantage_modifiers.items()}},
            critical_modifiers={**self.critical_modifiers, **{k: v for other in others for k, v in other.critical_modifiers.items()}},
            auto_hit_modifiers={**self.auto_hit_modifiers, **{k: v for other in others for k, v in other.auto_hit_modifiers.items()}},
            size_modifiers={**self.size_modifiers, **{k: v for other in others for k, v in other.size_modifiers.items()}},
            damage_type_modifiers={**self.damage_type_modifiers, **{k: v for other in others for k, v in other.damage_type_modifiers.items()}},
            resistance_modifiers={**self.resistance_modifiers, **{k: v for other in others for k, v in other.resistance_modifiers.items()}},
            generated_from=[self.uuid] + [other.uuid for other in others],
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            score_normalizer=self.score_normalizer,
            is_outgoing_modifier=self.is_outgoing_modifier,
            global_normalizer=False
        )

    def get_all_modifier_uuids(self) -> List[UUID]:
        """Return all modifier UUIDs stored in this value.

        Returns:
            UUIDs from every static modifier bucket.
        """
        return (list(self.value_modifiers.keys()) +
                list(self.min_constraints.keys()) +
                list(self.max_constraints.keys()) +
                list(self.advantage_modifiers.keys()) +
                list(self.critical_modifiers.keys()) +
                list(self.auto_hit_modifiers.keys()) +
                list(self.size_modifiers.keys()) +
                list(self.damage_type_modifiers.keys()) +
                list(self.resistance_modifiers.keys()))

    def remove_all_modifiers(self) -> None:
        """Clear every static modifier bucket."""
        self.value_modifiers.clear()
        self.min_constraints.clear()
        self.max_constraints.clear()
        self.advantage_modifiers.clear()
        self.critical_modifiers.clear()
        self.auto_hit_modifiers.clear()
        self.size_modifiers.clear()
        self.damage_type_modifiers.clear()
        self.resistance_modifiers.clear()

    def _set_normalizer_recursive(self, normalizer: Callable[[int], int]) -> None:
        """Set the score normalizer on this value and numerical modifiers.

        Args:
            normalizer: Normalizer function to apply.
        """
        self.score_normalizer = normalizer

        for modifier in self.value_modifiers.values():
            modifier.score_normalizer = normalizer

    @model_validator(mode='after')
    def apply_global_normalizer(self) -> Self:
        """Apply the value normalizer to numerical modifiers when enabled.

        Returns:
            This value after normalizer propagation.
        """
        if self.global_normalizer and self.score_normalizer is not None:
            self._set_normalizer_recursive(self.score_normalizer)
        return self

class ContextualValue(BaseValue):
    """Context-sensitive modifier bucket for one value channel.

    `ContextualValue` stores callable modifiers that are evaluated against the
    current source, target, context dictionary, and event lineage before being
    aggregated.
    """

    event_lineage_uuid: Optional[UUID] = Field(
        default=None,
        exclude=True,
        description="Current event lineage UUID used by contextual modifier cache keys."
    )

    value_modifiers: Dict[UUID, ContextualNumericalModifier] = Field(
        default_factory=dict,
        description="Contextual numerical modifiers evaluated into score bonuses or penalties."
    )
    min_constraints: Dict[UUID, ContextualNumericalModifier] = Field(
        default_factory=dict,
        description="Contextual minimum score constraints evaluated after numerical modifiers."
    )
    max_constraints: Dict[UUID, ContextualNumericalModifier] = Field(
        default_factory=dict,
        description="Contextual maximum score constraints evaluated after numerical modifiers."
    )
    advantage_modifiers: Dict[UUID, ContextualAdvantageModifier] = Field(
        default_factory=dict,
        description="Contextual advantage and disadvantage modifiers aggregated by numerical sign."
    )
    critical_modifiers: Dict[UUID, ContextualCriticalModifier] = Field(
        default_factory=dict,
        description="Contextual critical outcome modifiers, with NOCRIT taking precedence."
    )
    auto_hit_modifiers: Dict[UUID, ContextualAutoHitModifier] = Field(
        default_factory=dict,
        description="Contextual hit and miss overrides, with AUTOMISS taking precedence."
    )
    is_outgoing_modifier: bool = Field(
        default=False,
        description="Whether this bucket stores modifiers intended to affect another entity's value."
    )
    size_modifiers: Dict[UUID, ContextualSizeModifier] = Field(
        default_factory=dict,
        description="Contextual size modifiers evaluated into an effective creature or object size."
    )
    damage_type_modifiers: Dict[UUID, ContextualDamageTypeModifier] = Field(
        default_factory=dict,
        description="Contextual damage type modifiers used to derive one or more effective damage types."
    )
    resistance_modifiers: Dict[UUID, ContextualResistanceModifier] = Field(
        default_factory=dict,
        description="Contextual resistance, vulnerability, and immunity modifiers by damage type."
    )
    largest_size_priority: bool = Field(
        default=True,
        description="Whether size aggregation chooses the largest size instead of the smallest size."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ContextualValue']:
        """Retrieve a contextual value by UUID.

        Args:
            uuid: UUID of the value to retrieve.

        Returns:
            The registered contextual value when found, otherwise `None`.

        Raises:
            ValueError: If the UUID resolves to a non-contextual value.
        """
        value = cls._registry.get(uuid)
        if value is None:
            return None
        elif isinstance(value, ContextualValue):
            return value
        else:
            raise ValueError(f"Value with UUID {uuid} is not a ContextualValue, but {type(value)}")

    @computed_field
    @property
    def min(self) -> Optional[int]:
        """Return the lowest active contextual minimum constraint.

        Returns:
            Minimum evaluated constraint value when present, otherwise `None`.
        """
        if not self.min_constraints:
            return None
        constraints = [constraint.evaluate(self.source_entity_uuid, self.target_entity_uuid, self.context,
                        event_lineage_uuid=self.event_lineage_uuid) for constraint in self.min_constraints.values()]
        values = [constraint.value for constraint in constraints if isinstance(constraint, NumericalModifier)]
        return min(values) if len(values) > 0 else None

    @computed_field
    @property
    def max(self) -> Optional[int]:
        """Return the highest active contextual maximum constraint.

        Returns:
            Maximum evaluated constraint value when present, otherwise `None`.
        """
        if not self.max_constraints:
            return None
        constraints = [constraint.evaluate(self.source_entity_uuid, self.target_entity_uuid, self.context,
                        event_lineage_uuid=self.event_lineage_uuid) for constraint in self.max_constraints.values()]
        values = [constraint.value for constraint in constraints if isinstance(constraint, NumericalModifier)]
        return max(values) if len(values) > 0 else None

    def _score(self, normalized: bool = False) -> int:
        """Calculate the contextual score after modifiers and constraints.

        Args:
            normalized: Whether to read each evaluated modifier's normalized
                value.

        Returns:
            Final score after active minimum and maximum constraints are applied.
        """
        modifier_sum = 0
        for context_aware_modifier in self.value_modifiers.values():
            result = context_aware_modifier.evaluate(self.source_entity_uuid, self.target_entity_uuid, self.context,
                                                      event_lineage_uuid=self.event_lineage_uuid)
            if result is None:
                continue
            if not isinstance(result, NumericalModifier):
                continue
            modifier_sum += result.value if not normalized else result.normalized_value

        if self.max is not None and self.min is not None:
            return max(self.min, min(modifier_sum, self.max))
        elif self.max is not None:
            return min(modifier_sum, self.max)
        elif self.min is not None:
            return max(self.min, modifier_sum)
        else:
            return modifier_sum

    @computed_field
    @property
    def score(self) -> int:
        """Return the raw contextual channel score.

        Returns:
            Score computed from active contextual numerical modifiers.
        """
        return self._score()

    @computed_field
    @property
    def normalized_score(self) -> int:
        """Return the contextual score using normalized modifiers.

        Returns:
            Score computed from each active modifier's normalized value.
        """
        return self._score(normalized=True)

    @computed_field
    @property
    def advantage_sum(self) -> int:
        """Return the signed aggregate of active advantage modifiers.

        Returns:
            Positive values mean advantage, negative values mean disadvantage.
        """
        modifiers = [modifier.evaluate(self.source_entity_uuid, self.target_entity_uuid, self.context,
                      event_lineage_uuid=self.event_lineage_uuid) for modifier in self.advantage_modifiers.values()]
        values = [modifier.numerical_value for modifier in modifiers if isinstance(modifier, AdvantageModifier)]
        return sum(values) if len(values) > 0 else 0

    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """Return the final contextual advantage state.

        Returns:
            Advantage, disadvantage, or none after signed aggregation.
        """
        if self.advantage_sum > 0:
            return AdvantageStatus.ADVANTAGE
        elif self.advantage_sum < 0:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE

    @computed_field
    @property
    def critical(self) -> CriticalStatus:
        """Return the final contextual critical-hit override state.

        Returns:
            `NOCRIT`, `AUTOCRIT`, or `NONE`, with `NOCRIT` taking precedence.
        """
        critical_modifiers = [modifier.evaluate(self.source_entity_uuid, self.target_entity_uuid, self.context,
                              event_lineage_uuid=self.event_lineage_uuid) for modifier in self.critical_modifiers.values()]
        values = [modifier.value for modifier in critical_modifiers if isinstance(modifier, CriticalModifier)]
        if CriticalStatus.NOCRIT in values:
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in values:
            return CriticalStatus.AUTOCRIT
        else:
            return CriticalStatus.NONE

    @computed_field
    @property
    def auto_hit(self) -> AutoHitStatus:
        """Return the final contextual hit override state.

        Returns:
            `AUTOMISS`, `AUTOHIT`, or `NONE`, with `AUTOMISS` taking precedence.
        """
        auto_hit_modifiers = [modifier.evaluate(self.source_entity_uuid, self.target_entity_uuid, self.context,
                              event_lineage_uuid=self.event_lineage_uuid) for modifier in self.auto_hit_modifiers.values()]
        values = [modifier.value for modifier in auto_hit_modifiers if isinstance(modifier, AutoHitModifier)]
        if AutoHitStatus.AUTOMISS in values:
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in values:
            return AutoHitStatus.AUTOHIT
        else:
            return AutoHitStatus.NONE

    @computed_field
    @property
    def size(self) -> Size:
        """Return the effective size from active contextual size modifiers.

        Returns:
            Effective size, defaulting to `MEDIUM` when no modifier applies.
        """
        if not self.size_modifiers:
            return Size.MEDIUM
        size_modifiers = [modifier.evaluate(self.source_entity_uuid, self.target_entity_uuid, self.context,
                          event_lineage_uuid=self.event_lineage_uuid) for modifier in self.size_modifiers.values()]
        sizes = [modifier.value for modifier in size_modifiers if isinstance(modifier, SizeModifier)]
        if self.largest_size_priority:
            return max(sizes, key=lambda s: list(Size).index(s)) if len(sizes) > 0 else Size.MEDIUM
        else:
            return min(sizes, key=lambda s: list(Size).index(s)) if len(sizes) > 0 else Size.MEDIUM

    @computed_field
    @property
    def damage_types(self) -> List[DamageType]:
        """Return the most common active contextual damage types.

        Returns:
            Damage types tied for highest occurrence.
        """
        if not self.damage_type_modifiers:
            return []

        type_counts = {}
        for modifier in self.damage_type_modifiers.values():
            result = modifier.evaluate(self.source_entity_uuid, self.target_entity_uuid, self.context,
                                        event_lineage_uuid=self.event_lineage_uuid)
            if isinstance(result, DamageTypeModifier):
                type_counts[result.value] = type_counts.get(result.value, 0) + 1

        if not type_counts:
            return []

        max_count = max(type_counts.values())
        most_common_types = [dt for dt, count in type_counts.items() if count == max_count]

        return most_common_types

    @computed_field
    @property
    def damage_type(self) -> Optional[DamageType]:
        """Return one representative contextual damage type.

        Returns:
            Randomly selected damage type from the most common types, or `None`.
        """
        most_common_types = self.damage_types
        if not most_common_types:
            return None
        return random.choice(most_common_types)

    @computed_field
    @property
    def resistance_sum(self) -> Dict[DamageType, int]:
        """Return signed contextual resistance totals by damage type.

        Returns:
            Damage type to signed resistance total.
        """
        resistance_sum = {damage_type: 0 for damage_type in DamageType}
        for modifier in self.resistance_modifiers.values():
            result = modifier.evaluate(self.source_entity_uuid, self.target_entity_uuid, self.context,
                                        event_lineage_uuid=self.event_lineage_uuid)
            if result is not None and isinstance(result, ResistanceModifier):
                resistance_sum[result.damage_type] += result.numerical_value
        return resistance_sum

    @computed_field
    @property
    def resistance(self) -> Dict[DamageType, ResistanceStatus]:
        """Return final contextual resistance states by damage type.

        Returns:
            Damage type to vulnerability, none, resistance, or immunity.
        """
        resistance = {}
        for damage_type, sum_value in self.resistance_sum.items():
            if sum_value > 1:
                resistance[damage_type] = ResistanceStatus.IMMUNITY
            elif sum_value == 1:
                resistance[damage_type] = ResistanceStatus.RESISTANCE
            elif sum_value == 0:
                resistance[damage_type] = ResistanceStatus.NONE
            else:
                resistance[damage_type] = ResistanceStatus.VULNERABILITY
        return resistance

    def add_value_modifier(self, modifier: ContextualNumericalModifier) -> UUID:
        """Add a contextual numerical modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        uuid = modifier.uuid
        self.value_modifiers[uuid] = modifier
        return uuid

    def remove_value_modifier(self, uuid: UUID) -> None:
        """Remove a contextual numerical modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        if uuid in self.value_modifiers:
            del self.value_modifiers[uuid]

    def add_min_constraint(self, constraint: ContextualNumericalModifier) -> UUID:
        """Add a contextual minimum score constraint.

        Args:
            constraint: Constraint to add.

        Returns:
            UUID of the added constraint.
        """
        uuid = constraint.uuid
        self.min_constraints[uuid] = constraint
        return uuid

    def remove_min_constraint(self, uuid: UUID) -> None:
        """Remove a contextual minimum score constraint.

        Args:
            uuid: UUID of the constraint to remove.
        """

        if uuid in self.min_constraints:
            del self.min_constraints[uuid]

    def add_max_constraint(self, constraint: ContextualNumericalModifier) -> UUID:
        """Add a contextual maximum score constraint.

        Args:
            constraint: Constraint to add.

        Returns:
            UUID of the added constraint.
        """
        uuid = constraint.uuid
        self.max_constraints[uuid] = constraint
        return uuid

    def remove_max_constraint(self, uuid: UUID) -> None:
        """Remove a contextual maximum score constraint.

        Args:
            uuid: UUID of the constraint to remove.
        """
        if uuid in self.max_constraints:
            del self.max_constraints[uuid]

    def add_advantage_modifier(self, modifier: ContextualAdvantageModifier) -> UUID:
        """Add a contextual advantage or disadvantage modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        uuid = modifier.uuid
        self.advantage_modifiers[uuid] = modifier
        return uuid

    def remove_advantage_modifier(self, uuid: UUID) -> None:
        """Remove a contextual advantage or disadvantage modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        if uuid in self.advantage_modifiers:
            del self.advantage_modifiers[uuid]

    def add_critical_modifier(self, modifier: ContextualCriticalModifier) -> UUID:
        """Add a contextual critical outcome modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        uuid = modifier.uuid
        self.critical_modifiers[uuid] = modifier
        return uuid

    def remove_critical_modifier(self, uuid: UUID) -> None:
        """Remove a contextual critical outcome modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        if uuid in self.critical_modifiers:
            del self.critical_modifiers[uuid]

    def add_auto_hit_modifier(self, modifier: ContextualAutoHitModifier) -> UUID:
        """Add a contextual auto-hit or auto-miss modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        uuid = modifier.uuid
        self.auto_hit_modifiers[uuid] = modifier
        return uuid

    def remove_auto_hit_modifier(self, uuid: UUID) -> None:
        """Remove a contextual auto-hit or auto-miss modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        if uuid in self.auto_hit_modifiers:
            del self.auto_hit_modifiers[uuid]

    def add_size_modifier(self, modifier: ContextualSizeModifier) -> UUID:
        """Add a contextual size modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        self.size_modifiers[modifier.uuid] = modifier
        return modifier.uuid

    def remove_size_modifier(self, uuid: UUID) -> None:
        """Remove a contextual size modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        if uuid in self.size_modifiers:
            del self.size_modifiers[uuid]

    def add_damage_type_modifier(self, modifier: ContextualDamageTypeModifier) -> UUID:
        """Add a contextual damage type modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        self.damage_type_modifiers[modifier.uuid] = modifier
        return modifier.uuid

    def remove_damage_type_modifier(self, uuid: UUID) -> None:
        """Remove a contextual damage type modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        if uuid in self.damage_type_modifiers:
            del self.damage_type_modifiers[uuid]

    def add_resistance_modifier(self, modifier: ContextualResistanceModifier) -> UUID:
        """Add a contextual resistance, vulnerability, or immunity modifier.

        Args:
            modifier: Modifier to add.

        Returns:
            UUID of the added modifier.
        """
        self.resistance_modifiers[modifier.uuid] = modifier
        return modifier.uuid

    def remove_resistance_modifier(self, uuid: UUID) -> None:
        """Remove a contextual resistance, vulnerability, or immunity modifier.

        Args:
            uuid: UUID of the modifier to remove.
        """
        if uuid in self.resistance_modifiers:
            del self.resistance_modifiers[uuid]

    def remove_modifier(self, uuid: UUID) -> None:
        """Remove a modifier UUID from every contextual modifier bucket.

        Args:
            uuid: UUID of the modifier to remove.
        """
        self.remove_value_modifier(uuid)
        self.remove_min_constraint(uuid)
        self.remove_max_constraint(uuid)
        self.remove_advantage_modifier(uuid)
        self.remove_critical_modifier(uuid)
        self.remove_auto_hit_modifier(uuid)
        self.remove_size_modifier(uuid)
        self.remove_damage_type_modifier(uuid)
        self.remove_resistance_modifier(uuid)

    def combine_values(self, others: List['ContextualValue'], naming_callable: Optional[naming_callable] = None) -> 'ContextualValue':
        """Combine this value with other contextual values.

        Args:
            others: Contextual values to merge with this value.
            naming_callable: Optional function that names the combined value
                from the source value names.

        Returns:
            New contextual value containing all modifier buckets from each
            source.

        Raises:
            ValueError: If any other value has a different source entity UUID.
        """
        if naming_callable is None:
            naming_callable = lambda names: "_".join(names)

        for other in others:
            self.validate_source_id(other.source_entity_uuid)

        def merge_dicts(*dicts):
            return {k: v for d in dicts for k, v in d.items()}

        return ContextualValue(
            name=naming_callable([self.name] + [other.name for other in others]),
            value_modifiers=merge_dicts(self.value_modifiers, *(other.value_modifiers for other in others)),
            min_constraints=merge_dicts(self.min_constraints, *(other.min_constraints for other in others)),
            max_constraints=merge_dicts(self.max_constraints, *(other.max_constraints for other in others)),
            advantage_modifiers=merge_dicts(self.advantage_modifiers, *(other.advantage_modifiers for other in others)),
            critical_modifiers=merge_dicts(self.critical_modifiers, *(other.critical_modifiers for other in others)),
            auto_hit_modifiers=merge_dicts(self.auto_hit_modifiers, *(other.auto_hit_modifiers for other in others)),
            size_modifiers=merge_dicts(self.size_modifiers, *(other.size_modifiers for other in others)),
            damage_type_modifiers=merge_dicts(self.damage_type_modifiers, *(other.damage_type_modifiers for other in others)),
            resistance_modifiers=merge_dicts(self.resistance_modifiers, *(other.resistance_modifiers for other in others)),
            generated_from=[self.uuid] + [other.uuid for other in others],
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            target_entity_uuid=self.target_entity_uuid,
            target_entity_name=self.target_entity_name,
            context=self.context,
            score_normalizer=self.score_normalizer,
            is_outgoing_modifier=self.is_outgoing_modifier,
            global_normalizer=False
        )

    def get_all_modifier_uuids(self) -> List[UUID]:
        """Return all modifier UUIDs stored in this value.

        Returns:
            UUIDs from every contextual modifier bucket.
        """
        return (list(self.value_modifiers.keys()) +
                list(self.min_constraints.keys()) +
                list(self.max_constraints.keys()) +
                list(self.advantage_modifiers.keys()) +
                list(self.critical_modifiers.keys()) +
                list(self.auto_hit_modifiers.keys()) +
                list(self.size_modifiers.keys()) +
                list(self.damage_type_modifiers.keys()) +
                list(self.resistance_modifiers.keys()))

    def remove_all_modifiers(self) -> None:
        """Clear every contextual modifier bucket."""
        self.value_modifiers.clear()
        self.min_constraints.clear()
        self.max_constraints.clear()
        self.advantage_modifiers.clear()
        self.critical_modifiers.clear()
        self.auto_hit_modifiers.clear()
        self.size_modifiers.clear()
        self.damage_type_modifiers.clear()
        self.resistance_modifiers.clear()

    def _set_normalizer_recursive(self, normalizer: Callable[[int], int]) -> None:
        """Set the score normalizer on this value and numerical callables.

        Args:
            normalizer: Normalizer function to apply.
        """
        self.score_normalizer = normalizer

        for modifier in self.value_modifiers.values():
            modifier.callable.score_normalizer = normalizer

    @model_validator(mode='after')
    def apply_global_normalizer(self) -> Self:
        """Apply the value normalizer to contextual numerical callables.

        Returns:
            This value after normalizer propagation.
        """
        if self.global_normalizer and self.score_normalizer is not None:
            self._set_normalizer_recursive(self.score_normalizer)
        return self

class ModifiableValue(BaseValue):
    """Public value composed from self, outgoing, and imported channels.

    `ModifiableValue` is the value object exposed to higher-level engine
    systems. It aggregates always-on and contextual self channels, keeps
    outgoing target channels separate, and can import a target's outgoing
    channels with `set_from_target()`.
    """

    self_static: StaticValue = Field(
        default_factory=lambda: StaticValue(source_entity_uuid=uuid4()),
        description="Always-on static modifiers that affect this value's owner."
    )
    to_target_static: StaticValue = Field(
        default_factory=lambda: StaticValue(source_entity_uuid=uuid4(), is_outgoing_modifier=True),
        description="Always-on static modifiers this value exports to entities targeting its owner."
    )
    self_contextual: ContextualValue = Field(
        default_factory=lambda: ContextualValue(source_entity_uuid=uuid4()),
        description="Contextual modifiers that affect this value's owner."
    )
    to_target_contextual: ContextualValue = Field(
        default_factory=lambda: ContextualValue(source_entity_uuid=uuid4(), is_outgoing_modifier=True),
        description="Contextual modifiers this value exports to entities targeting its owner."
    )
    from_target_contextual: Optional[ContextualValue] = Field(
        default=None,
        description="Contextual outgoing modifiers imported from the current target."
    )
    from_target_static: Optional[StaticValue] = Field(
        default=None,
        description="Static outgoing modifiers imported from the current target."
    )
    global_normalizer: bool = Field(
        default=True,
        description="Whether this value propagates its normalizer into nested numerical channels."
    )

    def get_base_modifier(self) -> Optional[NumericalModifier]:
        """Return the generated base numerical modifier when present.

        Returns:
            The `self_static` modifier whose name contains `"_base_value"`, or
            `None`.
        """
        for modifier in self.self_static.value_modifiers.values():
            if modifier.name and "_base_value" in modifier.name:
                return modifier
        return None

    @classmethod
    def create(cls, source_entity_uuid: UUID, source_entity_name: Optional[str] = None,
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None,
               base_value: int = 0, value_name: str = "Value", score_normalizer: Optional[Callable[[int], int]] = None,
               global_normalizer: bool = True, identity_uuid: Optional[UUID] = None) -> 'ModifiableValue':
        """Create a value whose primary channels share source metadata.

        Args:
            source_entity_uuid: Entity UUID that owns the value.
            source_entity_name: Optional display name for the source entity.
            target_entity_uuid: Optional initial target entity UUID.
            target_entity_name: Optional display name for the target entity.
            base_value: Base numerical score stored in `self_static`.
            value_name: Human-readable value name.
            score_normalizer: Optional normalizer for scores and numerical
                modifiers.
            global_normalizer: Whether to propagate the normalizer into child
                channels.
            identity_uuid: Optional stable identity root. When supplied, the
                value, its four locally owned channels, and its base modifier
                receive identities derived from this UUID.

        Returns:
            New modifiable value with initialized self and outgoing channels.
        """
        normalizer = score_normalizer if score_normalizer is not None else lambda x: x

        def owned_uuid(name: str) -> UUID:
            if identity_uuid is None:
                return uuid4()
            return uuid5(identity_uuid, name)

        base_modifier = NumericalModifier(
            uuid=owned_uuid("base_modifier"),
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid,
            value=base_value,
            name=f"{value_name}_base_value",
            score_normalizer=normalizer
        )

        obj = cls(
            uuid=identity_uuid or uuid4(),
            name=value_name,
            source_entity_uuid=source_entity_uuid,
            source_entity_name=source_entity_name,
            self_static=StaticValue(
                uuid=owned_uuid("self_static"),
                source_entity_uuid=source_entity_uuid,
                source_entity_name=source_entity_name,
                value_modifiers={base_modifier.uuid: base_modifier},
                score_normalizer=normalizer,
                global_normalizer=global_normalizer
            ),
            to_target_static=StaticValue(
                uuid=owned_uuid("to_target_static"),
                source_entity_uuid=source_entity_uuid,
                source_entity_name=source_entity_name,
                is_outgoing_modifier=True,
                score_normalizer=normalizer,
                global_normalizer=global_normalizer
            ),
            self_contextual=ContextualValue(
                uuid=owned_uuid("self_contextual"),
                source_entity_uuid=source_entity_uuid,
                source_entity_name=source_entity_name,
                score_normalizer=normalizer,
                global_normalizer=global_normalizer
            ),
            to_target_contextual=ContextualValue(
                uuid=owned_uuid("to_target_contextual"),
                source_entity_uuid=source_entity_uuid,
                source_entity_name=source_entity_name,
                is_outgoing_modifier=True,
                score_normalizer=normalizer,
                global_normalizer=global_normalizer
            ),
            score_normalizer=normalizer,
            global_normalizer=global_normalizer
        )

        if target_entity_uuid is not None:
            obj.set_target_entity(target_entity_uuid, target_entity_name)

        return obj

    def get_typed_modifiers(self) -> List[Union[StaticValue, ContextualValue]]:
        """Return active self and imported target channels.

        Returns:
            Non-`None` static and contextual channels that contribute to this
            value's own aggregates.
        """
        modifiers = [self.self_static, self.self_contextual, self.from_target_contextual, self.from_target_static]
        return [modifier for modifier in modifiers if modifier is not None]

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ModifiableValue']:
        """Retrieve a modifiable value by UUID.

        Args:
            uuid: UUID of the value to retrieve.

        Returns:
            The registered modifiable value when found, otherwise `None`.

        Raises:
            ValueError: If the UUID resolves to a different value type.
        """
        value = cls._registry.get(uuid)
        if value is None:
            return None
        elif isinstance(value, ModifiableValue):
            return value
        else:
            raise ValueError(f"Value with UUID {uuid} is not a ModifiableValue, but {type(value)}")

    @computed_field
    @property
    def min(self) -> Optional[int]:
        """Return the lowest active minimum constraint across channels.

        Returns:
            Minimum constraint value when present, otherwise `None`.
        """
        typed_modifiers = self.get_typed_modifiers()
        modifiers_min = [modifier.min for modifier in typed_modifiers if modifier.min is not None]
        if len(modifiers_min) == 0:
            return None
        return min(modifiers_min)

    @computed_field
    @property
    def max(self) -> Optional[int]:
        """Return the highest active maximum constraint across channels.

        Returns:
            Maximum constraint value when present, otherwise `None`.
        """
        typed_modifiers = self.get_typed_modifiers()
        modifiers_max = [modifier.max for modifier in typed_modifiers if modifier.max is not None]
        if len(modifiers_max) == 0:
            return None
        return max(modifiers_max)

    def _score(self, normalized: bool = False) -> int:
        """Calculate the aggregate score after modifiers and constraints.

        Args:
            normalized: Whether to use each channel's normalized score.

        Returns:
            Final score after active minimum and maximum constraints are applied.
        """
        typed_modifiers = self.get_typed_modifiers()
        if self.max is not None and self.min is not None:
            return max(self.min, min(sum(modifier.score if not normalized else modifier.normalized_score for modifier in typed_modifiers), self.max))
        elif self.max is not None:
            return min(sum(modifier.score if not normalized else modifier.normalized_score for modifier in typed_modifiers), self.max)
        elif self.min is not None:
            return max(self.min, sum(modifier.score if not normalized else modifier.normalized_score for modifier in typed_modifiers))
        else:
            return sum(modifier.score if not normalized else modifier.normalized_score for modifier in typed_modifiers)

    @computed_field
    @property
    def score(self) -> int:
        """Return the raw aggregate score.

        Returns:
            Score computed from active self and imported target channels.
        """
        return self._score(normalized=False)

    @computed_field
    @property
    def normalized_score(self) -> int:
        """Return the aggregate score using normalized channels.

        Returns:
            Score computed from each active channel's normalized score.
        """
        return self._score(normalized=True)

    def normalized_score_excluding_static_modifiers(
        self,
        modifier_uuids: set[UUID],
    ) -> int:
        """Return the aggregate normalized score without selected static modifiers.

        Args:
            modifier_uuids: Static numerical modifier UUIDs omitted from every
                active static channel.

        Returns:
            Filtered aggregate with channel and value constraints preserved.
        """
        channel_scores = [
            channel.normalized_score_excluding(modifier_uuids)
            if isinstance(channel, StaticValue)
            else channel.normalized_score
            for channel in self.get_typed_modifiers()
        ]
        score = sum(channel_scores)
        if self.max is not None and self.min is not None:
            return max(self.min, min(score, self.max))
        if self.max is not None:
            return min(score, self.max)
        if self.min is not None:
            return max(self.min, score)
        return score

    @computed_field
    @property
    def advantage_sum(self) -> int:
        """Return the signed aggregate of active advantage modifiers.

        Returns:
            Positive values mean advantage, negative values mean disadvantage.
        """
        sums = []
        for source in [self.self_static, self.from_target_static, self.self_contextual, self.from_target_contextual]:
            if source is not None:
                sum_val = source.advantage_sum
                sums.append(sum_val)
        total = sum(sums)
        return total

    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """Return the final advantage state.

        Returns:
            Advantage, disadvantage, or none after signed aggregation.
        """
        total_sum = self.advantage_sum
        if total_sum > 0:
            return AdvantageStatus.ADVANTAGE
        elif total_sum < 0:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE

    @computed_field
    @property
    def critical(self) -> CriticalStatus:
        """Return the final critical-hit override state.

        Returns:
            `NOCRIT`, `AUTOCRIT`, or `NONE`, with `NOCRIT` taking precedence.
        """
        typed_modifiers = self.get_typed_modifiers()
        all_critical_modifiers = [modifier.critical for modifier in typed_modifiers]
        if CriticalStatus.NOCRIT in all_critical_modifiers:
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in all_critical_modifiers:
            return CriticalStatus.AUTOCRIT
        else:
            return CriticalStatus.NONE

    @computed_field
    @property
    def auto_hit(self) -> AutoHitStatus:
        """Return the final hit override state.

        Returns:
            `AUTOMISS`, `AUTOHIT`, or `NONE`, with `AUTOMISS` taking precedence.
        """
        typed_modifiers = self.get_typed_modifiers()
        all_auto_hit_modifiers = [modifier.auto_hit for modifier in typed_modifiers]
        if AutoHitStatus.AUTOMISS in all_auto_hit_modifiers:
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in all_auto_hit_modifiers:
            return AutoHitStatus.AUTOHIT
        else:
            return AutoHitStatus.NONE

    @computed_field
    @property
    def size(self) -> Size:
        """Return the effective size from active size modifiers.

        Returns:
            Effective size, defaulting to `MEDIUM` when no modifier applies.
        """
        sizes: List[Size] = []
        components = self.get_typed_modifiers()
        for component in components:
            if component.size != Size.MEDIUM:
                sizes.append(component.size)
        if self.from_target_static and self.from_target_static.size != Size.MEDIUM:
            sizes.append(self.from_target_static.size)
        if self.from_target_contextual and self.from_target_contextual.size != Size.MEDIUM:
            sizes.append(self.from_target_contextual.size)

        if not sizes:
            return Size.MEDIUM

        largest_size_priority = self.self_static.largest_size_priority

        if largest_size_priority:
            return max(sizes, key=lambda s: list(Size).index(s))
        else:
            return min(sizes, key=lambda s: list(Size).index(s))

    @computed_field
    @property
    def damage_types(self) -> List[DamageType]:
        """Return the most common active damage types.

        Returns:
            Damage types tied for highest occurrence.
        """
        type_counts = {}
        for component in [self.self_static, self.to_target_static, self.self_contextual, self.to_target_contextual]:
            for dt in component.damage_types:
                type_counts[dt] = type_counts.get(dt, 0) + 1
        if self.from_target_static:
            for dt in self.from_target_static.damage_types:
                type_counts[dt] = type_counts.get(dt, 0) + 1
        if self.from_target_contextual:
            for dt in self.from_target_contextual.damage_types:
                type_counts[dt] = type_counts.get(dt, 0) + 1

        if not type_counts:
            return []

        max_count = max(type_counts.values())
        most_common_types = [dt for dt, count in type_counts.items() if count == max_count]

        return most_common_types

    @computed_field
    @property
    def damage_type(self) -> Optional[DamageType]:
        """Return one representative damage type.

        Returns:
            Randomly selected damage type from the most common types, or `None`.
        """
        most_common_types = self.damage_types
        if not most_common_types:
            return None
        return random.choice(most_common_types)

    @computed_field
    @property
    def resistance_sum(self) -> Dict[DamageType, int]:
        """Return signed resistance totals by damage type.

        Returns:
            Damage type to signed resistance total.
        """
        resistance_sum = {damage_type: 0 for damage_type in DamageType}
        for component in [self.self_static, self.to_target_static, self.self_contextual, self.to_target_contextual]:
            for damage_type, value in component.resistance_sum.items():
                resistance_sum[damage_type] += value
        if self.from_target_static:
            for damage_type, value in self.from_target_static.resistance_sum.items():
                resistance_sum[damage_type] += value
        if self.from_target_contextual:
            for damage_type, value in self.from_target_contextual.resistance_sum.items():
                resistance_sum[damage_type] += value
        return resistance_sum

    @computed_field
    @property
    def resistance(self) -> Dict[DamageType, ResistanceStatus]:
        """Return final resistance states by damage type.

        Returns:
            Damage type to vulnerability, none, resistance, or immunity.
        """
        resistance = {}
        for damage_type, sum_value in self.resistance_sum.items():
            if sum_value > 1:
                resistance[damage_type] = ResistanceStatus.IMMUNITY
            elif sum_value == 1:
                resistance[damage_type] = ResistanceStatus.RESISTANCE
            elif sum_value == 0:
                resistance[damage_type] = ResistanceStatus.NONE
            else:
                resistance[damage_type] = ResistanceStatus.VULNERABILITY
        return resistance

    def set_source_entity(self, source_entity_uuid: UUID, source_entity_name: Optional[str]=None) -> None:
        """Set the source entity on this value and primary channels.

        Args:
            source_entity_uuid: Entity UUID to assign as source.
            source_entity_name: Optional display name for the source entity.
        """
        self.source_entity_uuid = source_entity_uuid
        self.source_entity_name = source_entity_name
        self.self_static.set_source_entity(source_entity_uuid, source_entity_name)
        self.to_target_static.set_source_entity(source_entity_uuid, source_entity_name)
        self.self_contextual.set_source_entity(source_entity_uuid, source_entity_name)
        self.to_target_contextual.set_source_entity(source_entity_uuid, source_entity_name)

    def set_target_entity(self, target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None:
        """Set the target entity on this value and primary channels.

        Args:
            target_entity_uuid: Entity UUID to assign as target.
            target_entity_name: Optional display name for the target entity.

        Raises:
            ValueError: If `target_entity_uuid` is not a UUID.
        """
        if not isinstance(target_entity_uuid, UUID):
            raise ValueError("target_entity_uuid must be a UUID")
        self.target_entity_uuid = target_entity_uuid
        self.target_entity_name = target_entity_name
        self.self_contextual.set_target_entity(target_entity_uuid, target_entity_name)
        self.self_static.set_target_entity(target_entity_uuid, target_entity_name)
        self.to_target_static.set_target_entity(target_entity_uuid, target_entity_name)
        self.to_target_contextual.set_target_entity(target_entity_uuid, target_entity_name)

    def clear_target_entity(self) -> None:
        """Clear target metadata and imported target channels."""
        self.target_entity_uuid = None
        self.target_entity_name = None
        self.self_contextual.clear_target_entity()
        self.self_static.clear_target_entity()
        self.to_target_contextual.clear_target_entity()
        self.to_target_static.clear_target_entity()
        self.from_target_contextual = None
        self.from_target_static = None

    def set_context(self, context: Dict[str,Any]) -> None:
        """Set runtime context on this value and contextual primary channels.

        Args:
            context: Runtime context dictionary.
        """
        self.context = context
        self.to_target_contextual.set_context(context)
        self.self_contextual.set_context(context)

    def clear_context(self) -> None:
        """Clear runtime context on this value and contextual primary channels."""
        self.context = None
        self.to_target_contextual.clear_context()
        self.self_contextual.clear_context()

    def set_from_target_contextual(self, contextual: ContextualValue) -> None:
        """Import contextual outgoing modifiers from the current target.

        Args:
            contextual: Target-owned outgoing contextual channel.

        Raises:
            ValueError: If source/target UUID relationships do not match.
        """
        self.validate_target_id(contextual.source_entity_uuid)
        if contextual.target_entity_uuid is None:
            raise ValueError("Contextual value target entity UUID cannot be None when being assigned to a ModifiableValue")
        self.validate_source_id(contextual.target_entity_uuid)
        self.from_target_contextual = contextual.model_copy(update={"target_entity_uuid": self.source_entity_uuid, "target_entity_name": self.source_entity_name})

    def set_from_target_static(self, static: StaticValue) -> None:
        """Import static outgoing modifiers from the current target.

        Args:
            static: Target-owned outgoing static channel.

        Raises:
            ValueError: If source/target UUID relationships do not match.
        """
        self.validate_target_id(static.source_entity_uuid)
        self.from_target_static = static.model_copy(update={"target_entity_uuid": self.source_entity_uuid, "target_entity_name": self.source_entity_name})

    def set_from_target(self, target_value: 'ModifiableValue') -> None:
        """Import both outgoing target channels from another value.

        Args:
            target_value: The current target's value.
        """
        self.set_from_target_contextual(target_value.to_target_contextual)
        self.set_from_target_static(target_value.to_target_static)

    def reset_from_target(self) -> None:
        """Clear imported target channels."""
        self.from_target_contextual = None
        self.from_target_static = None

    def set_event_lineage(self, lineage_uuid: UUID) -> None:
        """Set event lineage UUID for cache indexing on all contextual channels."""
        self.self_contextual.event_lineage_uuid = lineage_uuid
        if self.from_target_contextual:
            self.from_target_contextual.event_lineage_uuid = lineage_uuid
        self.to_target_contextual.event_lineage_uuid = lineage_uuid

    def clear_event_lineage(self) -> None:
        """Clear event lineage UUID from all contextual channels."""
        self.self_contextual.event_lineage_uuid = None
        if self.from_target_contextual:
            self.from_target_contextual.event_lineage_uuid = None
        self.to_target_contextual.event_lineage_uuid = None

    def combine_values(self, others: List['ModifiableValue'], naming_callable: Optional[naming_callable] = None) -> 'ModifiableValue':
        """Combine this value with other modifiable values.

        Args:
            others: Modifiable values to merge with this value.
            naming_callable: Optional function that names the combined value
                from the source value names.

        Returns:
            New modifiable value containing merged component channels.

        Raises:
            ValueError: If any other value has a different source entity UUID.
        """
        if naming_callable is None:
            naming_callable = lambda names: "_".join(names)

        for other in others:
            self.validate_source_id(other.source_entity_uuid)

        other_from_target_static_values = [other.from_target_static for other in others if other.from_target_static is not None]
        other_from_target_contextual_values = [other.from_target_contextual for other in others if other.from_target_contextual is not None]
        if self.from_target_static is not None:
            new_from_target_static = self.from_target_static.combine_values(other_from_target_static_values)
        elif len(other_from_target_static_values) > 0:
            new_from_target_static = other_from_target_static_values[0].combine_values(other_from_target_static_values[1:])
        else:
            new_from_target_static = None

        if self.from_target_contextual is not None:
            new_from_target_contextual = self.from_target_contextual.combine_values(other_from_target_contextual_values)
        elif len(other_from_target_contextual_values) > 0:
            new_from_target_contextual = other_from_target_contextual_values[0].combine_values(other_from_target_contextual_values[1:])
        else:
            new_from_target_contextual = None
        if new_from_target_static is not None:
            new_from_target_static.set_target_entity(self.source_entity_uuid, self.source_entity_name)
        if new_from_target_contextual is not None:
            new_from_target_contextual.set_target_entity(self.source_entity_uuid, self.source_entity_name)

        new_value= ModifiableValue(
            name=naming_callable([self.name] + [other.name for other in others]),
            self_static=self.self_static.combine_values([other.self_static for other in others]),
            to_target_static=self.to_target_static.combine_values([other.to_target_static for other in others]),
            self_contextual=self.self_contextual.combine_values([other.self_contextual for other in others]),
            to_target_contextual=self.to_target_contextual.combine_values([other.to_target_contextual for other in others]),
            from_target_static=new_from_target_static,
            from_target_contextual=new_from_target_contextual,
            generated_from=[self.uuid] + [other.uuid for other in others],
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            target_entity_uuid=self.target_entity_uuid,
            target_entity_name=self.target_entity_name,
            context=self.context,
            score_normalizer=self.score_normalizer,
            global_normalizer=False,
        )
        if self.target_entity_uuid is not None:
            new_value.set_target_entity(self.target_entity_uuid, self.target_entity_name)
        return new_value

    def get_breakdown(self) -> List[Dict[str, Any]]:
        """Return static numerical modifier entries for display.

        Combined values already have their static modifiers merged into
        `self_static` and `from_target_static`, so this method reads those
        channels directly rather than traversing `generated_from`.

        Returns:
            Display dictionaries containing `name`, `value`, and `source`.
        """
        name_cleanup = {
            "proficiency_bonus_base_value": "Prof",
            "Value_base_value": "Prof",
            "Attack Bonus_base_value": "Base",
            "Melee Attack Bonus_base_value": "Melee",
            "Ranged Attack Bonus_base_value": "Ranged",
            "Damage Bonus_base_value": "Base",
            "strength_modifier_base_value": "STR",
            "dexterity_modifier_base_value": "DEX",
            "constitution_modifier_base_value": "CON",
            "intelligence_modifier_base_value": "INT",
            "wisdom_modifier_base_value": "WIS",
            "charisma_modifier_base_value": "CHA",
            "strength Ability Score_base_value": "STR",
            "dexterity Ability Score_base_value": "DEX",
            "constitution Ability Score_base_value": "CON",
            "intelligence Ability Score_base_value": "INT",
            "wisdom Ability Score_base_value": "WIS",
            "charisma Ability Score_base_value": "CHA",
            "strength Modifier Bonus_base_value": "STR Mod",
            "dexterity Modifier Bonus_base_value": "DEX Mod",
            "constitution Modifier Bonus_base_value": "CON Mod",
            "intelligence Modifier Bonus_base_value": "INT Mod",
            "wisdom Modifier Bonus_base_value": "WIS Mod",
            "charisma Modifier Bonus_base_value": "CHA Mod",
            "ac_bonus_base_value": "Base AC",
            "AC Bonus_base_value": "Base AC",
            "Armor Class_base_value": "Armor",
            "Armor Class Bonus_base_value": "AC Bonus",
            "Max Dex Bonus_base_value": "Max DEX",
        }

        def clean_name(raw_name: str) -> str:
            """Normalize internal modifier names for display."""
            if raw_name in name_cleanup:
                return name_cleanup[raw_name]
            cleaned = raw_name
            for suffix in ["_base_value", "_bonus", "_modifier", " Bonus", " Modifier"]:
                if cleaned.endswith(suffix):
                    cleaned = cleaned[:-len(suffix)]
            if " Ability Score" in cleaned:
                cleaned = cleaned.replace(" Ability Score", "")
            return cleaned.replace("_", " ").title()

        result: List[Dict[str, Any]] = []

        static_components = [
            (self.self_static, "self"),
            (self.from_target_static, "from_target"),
        ]

        for component, source in static_components:
            if component is None:
                continue
            for modifier in component.value_modifiers.values():
                value = modifier.normalized_value
                if value == 0:
                    continue
                result.append({
                    "name": clean_name(modifier.name or "Unknown"),
                    "value": value,
                    "source": source
                })

        return result

    def get_advantage_breakdown(self) -> List[Dict[str, Any]]:
        """Return static advantage modifier entries for display.

        Contextual modifiers are excluded because their cached results can be
        invalidated by context changes.

        Returns:
            Display dictionaries containing `name`, `value`, and `source`.
        """
        result: List[Dict[str, Any]] = []

        static_components = [
            (self.self_static, "self"),
            (self.from_target_static, "from_target"),
        ]

        for component, source in static_components:
            if component is None:
                continue
            for modifier in component.advantage_modifiers.values():
                if modifier.value == AdvantageStatus.ADVANTAGE:
                    result.append({
                        "name": modifier.name or "Unknown",
                        "value": "advantage",
                        "source": source
                    })
                elif modifier.value == AdvantageStatus.DISADVANTAGE:
                    result.append({
                        "name": modifier.name or "Unknown",
                        "value": "disadvantage",
                        "source": source
                    })

        return result

    def get_full_breakdown(self) -> List[Dict[str, Any]]:
        """Return static and cached contextual numerical entries for display.

        Returns:
            Display dictionaries from static numerical modifiers and cached
            contextual numerical modifiers.
        """
        result = self.get_breakdown()

        contextual_components: List[tuple[Optional[ContextualValue], str]] = [
            (self.self_contextual, "self_contextual"),
            (self.from_target_contextual, "from_target_contextual"),
        ]
        for component, source in contextual_components:
            if component is None:
                continue
            lineage = component.event_lineage_uuid
            key = f"{component.source_entity_uuid}|{component.target_entity_uuid or 'none'}|{lineage or 'none'}"
            for modifier in component.value_modifiers.values():
                cached = modifier.cached_results.get(key)
                if cached is not None and isinstance(cached, NumericalModifier):
                    value = cached.normalized_value
                    if value != 0:
                        result.append({
                            "name": modifier.name or "Unknown",
                            "value": value,
                            "source": source,
                            "contextual": True
                        })
        return result

    def get_full_advantage_breakdown(self) -> List[Dict[str, Any]]:
        """Return static and cached contextual advantage entries for display.

        Returns:
            Display dictionaries from static advantage modifiers and cached
            contextual advantage modifiers.
        """
        result = self.get_advantage_breakdown()

        contextual_components: List[tuple[Optional[ContextualValue], str]] = [
            (self.self_contextual, "self_contextual"),
            (self.from_target_contextual, "from_target_contextual"),
        ]
        for component, source in contextual_components:
            if component is None:
                continue
            lineage = component.event_lineage_uuid
            key = f"{component.source_entity_uuid}|{component.target_entity_uuid or 'none'}|{lineage or 'none'}"
            for modifier in component.advantage_modifiers.values():
                cached = modifier.cached_results.get(key)
                if cached is not None and isinstance(cached, AdvantageModifier):
                    result.append({
                        "name": modifier.name or "Unknown",
                        "value": cached.value.value.lower(),
                        "source": source,
                        "active": True
                    })
                else:
                    result.append({
                        "name": modifier.name or "Unknown",
                        "value": "inactive",
                        "source": source,
                        "active": False
                    })
        return result

    def remove_modifier(self, uuid: UUID) -> None:
        """Remove a modifier UUID from every channel.

        Args:
            uuid: Modifier UUID to remove.
        """
        self.self_static.remove_modifier(uuid)
        self.self_contextual.remove_modifier(uuid)
        self.to_target_static.remove_modifier(uuid)
        self.to_target_contextual.remove_modifier(uuid)
        if self.from_target_static is not None:
            self.from_target_static.remove_modifier(uuid)
        if self.from_target_contextual is not None:
            self.from_target_contextual.remove_modifier(uuid)

    def remove_all_modifiers(self) -> None:
        """Clear every modifier bucket on every channel."""
        self.self_static.remove_all_modifiers()
        self.self_contextual.remove_all_modifiers()
        self.to_target_static.remove_all_modifiers()
        self.to_target_contextual.remove_all_modifiers()
        if self.from_target_static:
            self.from_target_static.remove_all_modifiers()
        if self.from_target_contextual:
            self.from_target_contextual.remove_all_modifiers()

    def get_all_modifier_uuids(self) -> List[UUID]:
        """Return all modifier UUIDs stored in any channel.

        Returns:
            UUIDs from self, outgoing, and imported target channels.
        """
        uuids = []
        for component in [self.self_static, self.to_target_static, self.self_contextual, self.to_target_contextual]:
            uuids.extend(component.get_all_modifier_uuids())
        if self.from_target_static:
            uuids.extend(self.from_target_static.get_all_modifier_uuids())
        if self.from_target_contextual:
            uuids.extend(self.from_target_contextual.get_all_modifier_uuids())
        return uuids

    def update_normalizers(self, new_normalizer: Optional[Callable[[int], int]] = None) -> None:
        """Propagate the active normalizer into every channel.

        Args:
            new_normalizer: Optional replacement normalizer to set before
                propagation.
        """
        if new_normalizer is not None:
            self.score_normalizer = new_normalizer

        self.self_static._set_normalizer_recursive(self.score_normalizer)
        self.self_contextual._set_normalizer_recursive(self.score_normalizer)

        self.to_target_static._set_normalizer_recursive(self.score_normalizer)
        self.to_target_contextual._set_normalizer_recursive(self.score_normalizer)

        if self.from_target_static is not None:
            self.from_target_static._set_normalizer_recursive(self.score_normalizer)
        if self.from_target_contextual is not None:
            self.from_target_contextual._set_normalizer_recursive(self.score_normalizer)

    @model_validator(mode="after")
    def validate_outgoing_modifier_flags(self) -> Self:
        """Validate outgoing-channel flags on all component channels.

        Returns:
            This value after validation.

        Raises:
            ValueError: If a channel's outgoing flag contradicts its role.
        """
        if self.self_static.is_outgoing_modifier:
            raise ValueError("self_static should not have is_outgoing_modifier set to True")
        if self.self_contextual.is_outgoing_modifier:
            raise ValueError("self_contextual should not have is_outgoing_modifier set to True")

        if not self.to_target_static.is_outgoing_modifier:
            raise ValueError("to_target_static should have is_outgoing_modifier set to True")
        if not self.to_target_contextual.is_outgoing_modifier:
            raise ValueError("to_target_contextual should have is_outgoing_modifier set to True")

        if self.from_target_static is not None and not self.from_target_static.is_outgoing_modifier:
            raise ValueError("from_target_static should have is_outgoing_modifier set to True")
        if self.from_target_contextual is not None and not self.from_target_contextual.is_outgoing_modifier:
            raise ValueError("from_target_contextual should have is_outgoing_modifier set to True")

        return self

    @model_validator(mode="after")
    def validate_source_and_target_consistency(self) -> Self:
        """Align primary channel sources and validate imported target channels.

        Returns:
            This value after validation.

        Raises:
            ValueError: If imported target channel source/target UUIDs are
                inconsistent with this value.
        """
        for component in [self.self_static, self.to_target_static, self.self_contextual, self.to_target_contextual]:
            if component.source_entity_uuid != self.source_entity_uuid:
                component.source_entity_uuid = self.source_entity_uuid

        if self.from_target_static is not None:
            if self.from_target_static.target_entity_uuid != self.source_entity_uuid:
                raise ValueError(
                    f"from_target_static target UUID ({self.from_target_static.target_entity_uuid}) "
                    f"should be the same as ModifiableValue source UUID ({self.source_entity_uuid})"
                )
            if self.from_target_static.source_entity_uuid == self.source_entity_uuid:
                raise ValueError(f"from_target_static source UUID ({self.from_target_static.source_entity_uuid}) "
                                 f"should not be the same as ModifiableValue source UUID ({self.source_entity_uuid})")

        if self.from_target_contextual is not None:
            if self.from_target_contextual.target_entity_uuid != self.source_entity_uuid:
                raise ValueError(f"from_target_contextual target UUID ({self.from_target_contextual.target_entity_uuid}) "
                                 f"should be the same as ModifiableValue source UUID ({self.source_entity_uuid})")
            if self.from_target_contextual.source_entity_uuid == self.source_entity_uuid:
                raise ValueError(f"from_target_contextual source UUID ({self.from_target_contextual.source_entity_uuid}) "
                                 f"should not be the same as ModifiableValue source UUID ({self.source_entity_uuid})")

        return self

    @computed_field
    @property
    def outgoing_advantage_sum(self) -> int:
        """Return the signed advantage total exported to targeters.

        Returns:
            Positive values mean exported advantage, negative values mean
            exported disadvantage.
        """
        sums = []
        for source in [self.to_target_static, self.to_target_contextual]:
            if source is not None:
                sum_val = source.advantage_sum
                sums.append(sum_val)
        return sum(sums)

    @computed_field
    @property
    def outgoing_advantage(self) -> AdvantageStatus:
        """Return the advantage state exported to targeters.

        Returns:
            Advantage, disadvantage, or none after signed aggregation.
        """
        total_sum = self.outgoing_advantage_sum
        if total_sum > 0:
            return AdvantageStatus.ADVANTAGE
        elif total_sum < 0:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE

    @computed_field
    @property
    def outgoing_critical(self) -> CriticalStatus:
        """Return the critical-hit override exported to targeters.

        Returns:
            `NOCRIT`, `AUTOCRIT`, or `NONE`, with `NOCRIT` taking precedence.
        """
        critical_modifiers = []
        for source in [self.to_target_static, self.to_target_contextual]:
            if source is not None:
                critical_modifiers.append(source.critical)

        if CriticalStatus.NOCRIT in critical_modifiers:
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in critical_modifiers:
            return CriticalStatus.AUTOCRIT
        else:
            return CriticalStatus.NONE

    @computed_field
    @property
    def outgoing_auto_hit(self) -> AutoHitStatus:
        """Return the hit override exported to targeters.

        Returns:
            `AUTOMISS`, `AUTOHIT`, or `NONE`, with `AUTOMISS` taking precedence.
        """
        auto_hit_modifiers = []
        for source in [self.to_target_static, self.to_target_contextual]:
            if source is not None:
                auto_hit_modifiers.append(source.auto_hit)

        if AutoHitStatus.AUTOMISS in auto_hit_modifiers:
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in auto_hit_modifiers:
            return AutoHitStatus.AUTOHIT
        else:
            return AutoHitStatus.NONE
