from fractions import Fraction
from math import prod

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator
from typing import Any, Callable, ClassVar, Dict, Iterable, List, NamedTuple, Optional, Self, Sequence, Tuple, Union
from uuid import UUID, uuid4, uuid5
from dnd.core.base_object import BaseObject, PASSIVE_EVENT_REPLAY
from dnd.core.creature_types import DamageType, Size
from dnd.core.modifiers import (
    naming_callable,
    NumericalModifier,
    ArithmeticFactor,
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


def _clamped(total: int | Fraction, minimum: int | None, maximum: int | None) -> int | Fraction:
    """Apply an upper then a lower bound; the lower bound wins when they cross."""
    if maximum is not None:
        total = min(total, maximum)
    if minimum is not None:
        total = max(total, minimum)
    return total


class BaseValue(BaseModel):
    """Base model for UUID-addressable values.

    A value is data: its modifiers, its owner and its normalizer. It holds no
    read state; who reads it, against whom and in which situation is the
    `ValueRead` passed to the read.
    """

    _registry: ClassVar[Dict[UUID, 'BaseValue']] = {}
    model_config = ConfigDict(arbitrary_types_allowed=True)

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
    use_register: bool = Field(
        default=True,
        description="Whether to register this value in the value registry."
    )
    score_normalizer: Callable[[int], int] = Field(
        default=identity,
        exclude=True,
        description="Callable that converts raw scores into normalized scores."
    )
    generated_from: Tuple[UUID, ...] = Field(
        default=(),
        description="Value UUIDs that were combined or copied to produce this value."
    )
    global_normalizer: bool = Field(
        default=True,
        description="Whether this value's normalizer also applies to numerical modifiers."
    )

    def model_post_init(self, __context: Any) -> None:
        """Register the value by UUID when registry participation is enabled."""
        if __context is not PASSIVE_EVENT_REPLAY and self.use_register:
            self.__class__._registry[self.uuid] = self

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

    @classmethod
    def unregister(cls, uuid: UUID) -> None:
        """Remove a value from the value registry."""
        cls._registry.pop(uuid, None)

    def remove_from_register(self) -> None:
        """Remove this value from the registry and disable registration."""
        self.__class__._registry.pop(self.uuid, None)
        self.use_register = False

    def set_source_entity(self, source_entity_uuid: UUID, source_entity_name: Optional[str] = None) -> None:
        """Set the owning entity of this value."""
        self.source_entity_uuid = source_entity_uuid
        self.source_entity_name = source_entity_name

    def validate_source_id(self, source_id: UUID) -> None:
        """Raise unless `source_id` owns this value."""
        if self.source_entity_uuid != source_id:
            raise ValueError("Source entity UUIDs do not match")

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

    factor_modifiers: Dict[UUID, ArithmeticFactor] = Field(default_factory=dict)

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
        if not self.is_outgoing_modifier:
            return self
        for modifiers in (self.value_modifiers, self.factor_modifiers, self.min_constraints, self.max_constraints):
            for modifier in modifiers.values():
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

    def add_factor(self, modifier: ArithmeticFactor) -> UUID:
        self.factor_modifiers[modifier.uuid] = modifier
        return modifier.uuid

    def arithmetic_factor(self, excluded: frozenset[UUID] = frozenset()) -> Fraction:
        return prod((Fraction(f.numerator, f.denominator)
            for key, f in self.factor_modifiers.items() if key not in excluded and f.contributions_active()), start=Fraction(1))

    def additive_score(self, normalized: bool = False, excluded: frozenset[UUID] = frozenset()) -> int:
        return sum((modifier.normalized_value if normalized else modifier.value)
            for key, modifier in self.value_modifiers.items() if key not in excluded and modifier.contributions_active())

    def remove_modifier(self, uuid: UUID) -> None:
        """Remove a modifier UUID from every static modifier bucket.

        Args:
            uuid: UUID of the modifier to remove.
        """
        self.factor_modifiers.pop(uuid, None)
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
        return min((constraint.value for constraint in self.min_constraints.values() if constraint.contributions_active()), default=None)

    @computed_field
    @property
    def max(self) -> Optional[int]:
        """Return the highest active maximum score constraint.

        Returns:
            Maximum constraint value when present, otherwise `None`.
        """
        if not self.max_constraints:
            return None
        return max((constraint.value for constraint in self.max_constraints.values() if constraint.contributions_active()), default=None)

    def bounded_score(self, normalized: bool = False,
                      excluded: frozenset[UUID] = frozenset()) -> tuple[int, int | None, int | None]:
        """Channel score with the bounds that clamped it; every contribution is read once.

        Args:
            normalized: Whether to read each modifier's normalized value.
            excluded: Owned contribution UUIDs omitted from this read.

        Returns:
            Score after factors and constraints, lowest active minimum, highest active maximum.
        """
        total: int | Fraction = self.additive_score(normalized, excluded)
        if self.factor_modifiers:
            total *= self.arithmetic_factor(excluded)
        minimum, maximum = self.score_bounds(excluded)
        return int(_clamped(total, minimum, maximum)), minimum, maximum

    def _score(self, normalized: bool = False) -> int:
        """Calculate the channel score after numerical modifiers and constraints.

        Args:
            normalized: Whether to read each modifier's normalized value.

        Returns:
            Final score after minimum and maximum constraints are applied.
        """
        return self.bounded_score(normalized)[0]

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

    def score_bounds(self, excluded: frozenset[UUID] = frozenset()) -> tuple[int | None, int | None]:
        """Return the lowest active minimum and highest active maximum, each constraint read once."""
        minimum = min((value.value for key, value in self.min_constraints.items()
            if key not in excluded and value.contributions_active()), default=None) if self.min_constraints else None
        maximum = max((value.value for key, value in self.max_constraints.items()
            if key not in excluded and value.contributions_active()), default=None) if self.max_constraints else None
        return minimum, maximum

    @computed_field
    @property
    def advantage_sum(self) -> int:
        """Return the signed aggregate of advantage modifiers.

        Returns:
            Positive values mean advantage, negative values mean disadvantage.
        """
        return sum(modifier.numerical_value for modifier in self.advantage_modifiers.values() if modifier.contributions_active())

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
        if CriticalStatus.NOCRIT in (mod.value for mod in self.critical_modifiers.values() if mod.contributions_active()):
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in (mod.value for mod in self.critical_modifiers.values() if mod.contributions_active()):
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
        if AutoHitStatus.AUTOMISS in (mod.value for mod in self.auto_hit_modifiers.values() if mod.contributions_active()):
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in (mod.value for mod in self.auto_hit_modifiers.values() if mod.contributions_active()):
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

        sizes = [modifier.value for modifier in self.size_modifiers.values() if modifier.contributions_active()]
        if not sizes:
            return Size.MEDIUM
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
            if not modifier.contributions_active():
                continue
            type_counts[modifier.value] = type_counts.get(modifier.value, 0) + 1

        if not type_counts:
            return []
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
            if not modifier.contributions_active():
                continue
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

    def combine_values(self, others: List['StaticValue'], naming_callable: Optional[naming_callable] = None,
                       *, use_register: bool = True) -> 'StaticValue':
        """Combine this value with other static values.

        Args:
            others: Static values to merge with this value.
            naming_callable: Optional function that names the combined value
                from the source value names.
            use_register: Register the newly combined value.

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
            use_register=use_register,
            name=naming_callable([self.name] + [other.name for other in others]),
            factor_modifiers={**self.factor_modifiers, **{k: v for other in others for k, v in other.factor_modifiers.items()}},
            value_modifiers={**self.value_modifiers, **{k: v for other in others for k, v in other.value_modifiers.items()}},
            min_constraints={**self.min_constraints, **{k: v for other in others for k, v in other.min_constraints.items()}},
            max_constraints={**self.max_constraints, **{k: v for other in others for k, v in other.max_constraints.items()}},
            advantage_modifiers={**self.advantage_modifiers, **{k: v for other in others for k, v in other.advantage_modifiers.items()}},
            critical_modifiers={**self.critical_modifiers, **{k: v for other in others for k, v in other.critical_modifiers.items()}},
            auto_hit_modifiers={**self.auto_hit_modifiers, **{k: v for other in others for k, v in other.auto_hit_modifiers.items()}},
            size_modifiers={**self.size_modifiers, **{k: v for other in others for k, v in other.size_modifiers.items()}},
            damage_type_modifiers={**self.damage_type_modifiers, **{k: v for other in others for k, v in other.damage_type_modifiers.items()}},
            resistance_modifiers={**self.resistance_modifiers, **{k: v for other in others for k, v in other.resistance_modifiers.items()}},
            generated_from=(self.uuid, *(other.uuid for other in others)),
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
        return (list(self.factor_modifiers.keys()) + list(self.value_modifiers.keys()) +
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
        self.factor_modifiers.clear()
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

def _contextual_numbers(
    modifiers: Dict[UUID, ContextualNumericalModifier], source: UUID,
    target: Optional[UUID], context: Optional[Dict[str, Any]],
) -> tuple[int, int]:
    """Raw and normalized totals of contextual numerical rows; each callable is evaluated once."""
    raw = normalized = 0
    for modifier in modifiers.values():
        result = modifier.evaluate(source, target, context)
        if isinstance(result, NumericalModifier):
            raw += result.value
            normalized += result.normalized_value
    return raw, normalized


def _contextual_constraint_values(
    modifiers: Dict[UUID, ContextualNumericalModifier], source: UUID,
    target: Optional[UUID], context: Optional[Dict[str, Any]],
) -> List[int]:
    results = [modifier.evaluate(source, target, context) for modifier in modifiers.values()]
    return [result.value for result in results if isinstance(result, NumericalModifier)]


def _contextual_advantage_results(modifiers: Dict[UUID, ContextualAdvantageModifier], source: UUID,
                                  target: Optional[UUID], context: Optional[Dict[str, Any]],
                                  ) -> list[tuple[ContextualAdvantageModifier, Any]]:
    """Each contextual advantage row with its result in one read situation."""
    return [(modifier, modifier.evaluate(source, target, context)) for modifier in modifiers.values()]


def _advantage_total(results: list[tuple[ContextualAdvantageModifier, Any]]) -> int:
    return sum(result.numerical_value for _, result in results if isinstance(result, AdvantageModifier))


def _advantage_status(total: int) -> AdvantageStatus:
    if total > 0:
        return AdvantageStatus.ADVANTAGE
    if total < 0:
        return AdvantageStatus.DISADVANTAGE
    return AdvantageStatus.NONE


def _critical_status(statuses: Sequence[CriticalStatus]) -> CriticalStatus:
    if CriticalStatus.NOCRIT in statuses:
        return CriticalStatus.NOCRIT
    if CriticalStatus.AUTOCRIT in statuses:
        return CriticalStatus.AUTOCRIT
    return CriticalStatus.NONE


def _resistance_statuses(sums: Dict[DamageType, int]) -> Dict[DamageType, ResistanceStatus]:
    statuses = {}
    for damage_type, sum_value in sums.items():
        if sum_value > 1:
            statuses[damage_type] = ResistanceStatus.IMMUNITY
        elif sum_value == 1:
            statuses[damage_type] = ResistanceStatus.RESISTANCE
        elif sum_value == 0:
            statuses[damage_type] = ResistanceStatus.NONE
        else:
            statuses[damage_type] = ResistanceStatus.VULNERABILITY
    return statuses


def _auto_hit_status(statuses: Sequence[AutoHitStatus]) -> AutoHitStatus:
    if AutoHitStatus.AUTOMISS in statuses:
        return AutoHitStatus.AUTOMISS
    if AutoHitStatus.AUTOHIT in statuses:
        return AutoHitStatus.AUTOHIT
    return AutoHitStatus.NONE


class ContextualValue(BaseValue):
    """Context-sensitive modifier bucket for one value channel.

    `ContextualValue` stores callable modifiers that are evaluated against the
    current source, target, context dictionary, and event lineage before being
    aggregated.
    """

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

    def bounds_in(self, target: Optional[UUID], context: Optional[Dict[str, Any]]) -> tuple[int | None, int | None]:
        """Lowest evaluated minimum and highest evaluated maximum in one read situation."""
        minimum = min(_contextual_constraint_values(self.min_constraints, self.source_entity_uuid, target, context),
                      default=None) if self.min_constraints else None
        maximum = max(_contextual_constraint_values(self.max_constraints, self.source_entity_uuid, target, context),
                      default=None) if self.max_constraints else None
        return minimum, maximum

    def numbers_in(self, target: Optional[UUID], context: Optional[Dict[str, Any]]) -> tuple[int, int]:
        """Raw and normalized additive totals in one read situation."""
        return _contextual_numbers(self.value_modifiers, self.source_entity_uuid, target, context)

    def advantage_sum_in(self, target: Optional[UUID], context: Optional[Dict[str, Any]]) -> int:
        """Signed advantage total in one read situation."""
        return _advantage_total(_contextual_advantage_results(self.advantage_modifiers, self.source_entity_uuid,
                                                              target, context))

    def critical_in(self, target: Optional[UUID], context: Optional[Dict[str, Any]]) -> CriticalStatus:
        """Critical override in one read situation; NOCRIT takes precedence."""
        results = [modifier.evaluate(self.source_entity_uuid, target, context)
                   for modifier in self.critical_modifiers.values()]
        return _critical_status([result.value for result in results if isinstance(result, CriticalModifier)])

    def auto_hit_in(self, target: Optional[UUID], context: Optional[Dict[str, Any]]) -> AutoHitStatus:
        """Hit override in one read situation; AUTOMISS takes precedence."""
        results = [modifier.evaluate(self.source_entity_uuid, target, context)
                   for modifier in self.auto_hit_modifiers.values()]
        return _auto_hit_status([result.value for result in results if isinstance(result, AutoHitModifier)])

    @computed_field
    @property
    def min(self) -> Optional[int]:
        """Return the lowest active contextual minimum constraint read with no target or context."""
        return self.bounds_in(None, None)[0]

    @computed_field
    @property
    def max(self) -> Optional[int]:
        """Return the highest active contextual maximum constraint read with no target or context."""
        return self.bounds_in(None, None)[1]

    def _score(self, normalized: bool = False) -> int:
        """The channel score read with no target or context: its rows clamped by its own bounds."""
        raw, scaled = self.numbers_in(None, None)
        return int(_clamped(scaled if normalized else raw, *self.bounds_in(None, None)))

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
        """Return the signed aggregate of active advantage modifiers read with no target or context."""
        return self.advantage_sum_in(None, None)

    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """Return the final contextual advantage state.

        Returns:
            Advantage, disadvantage, or none after signed aggregation.
        """
        return _advantage_status(self.advantage_sum)

    @computed_field
    @property
    def critical(self) -> CriticalStatus:
        """Return the final contextual critical-hit override state read with no target or context."""
        return self.critical_in(None, None)

    @computed_field
    @property
    def auto_hit(self) -> AutoHitStatus:
        """Return the final contextual hit override state read with no target or context."""
        return self.auto_hit_in(None, None)

    def size_in(self, target: Optional[UUID], context: Optional[Dict[str, Any]]) -> Size:
        """Effective size of the contextual size rows in one read situation."""
        if not self.size_modifiers:
            return Size.MEDIUM
        size_modifiers = [modifier.evaluate(self.source_entity_uuid, target, context)
                          for modifier in self.size_modifiers.values()]
        sizes = [modifier.value for modifier in size_modifiers if isinstance(modifier, SizeModifier)]
        if self.largest_size_priority:
            return max(sizes, key=lambda s: list(Size).index(s)) if len(sizes) > 0 else Size.MEDIUM
        else:
            return min(sizes, key=lambda s: list(Size).index(s)) if len(sizes) > 0 else Size.MEDIUM

    def damage_types_in(self, target: Optional[UUID], context: Optional[Dict[str, Any]]) -> List[DamageType]:
        """Most common contextual damage types in one read situation."""
        if not self.damage_type_modifiers:
            return []
        type_counts = {}
        for modifier in self.damage_type_modifiers.values():
            result = modifier.evaluate(self.source_entity_uuid, target, context)
            if isinstance(result, DamageTypeModifier):
                type_counts[result.value] = type_counts.get(result.value, 0) + 1
        if not type_counts:
            return []
        max_count = max(type_counts.values())
        return [dt for dt, count in type_counts.items() if count == max_count]

    def resistance_sum_in(self, target: Optional[UUID], context: Optional[Dict[str, Any]]) -> Dict[DamageType, int]:
        """Signed contextual resistance totals by damage type in one read situation."""
        resistance_sum = {damage_type: 0 for damage_type in DamageType}
        for modifier in self.resistance_modifiers.values():
            result = modifier.evaluate(self.source_entity_uuid, target, context)
            if result is not None and isinstance(result, ResistanceModifier):
                resistance_sum[result.damage_type] += result.numerical_value
        return resistance_sum

    @computed_field
    @property
    def size(self) -> Size:
        """Return the effective size from active contextual size modifiers read with no target or context."""
        return self.size_in(None, None)

    @computed_field
    @property
    def damage_types(self) -> List[DamageType]:
        """Return the most common active contextual damage types read with no target or context."""
        return self.damage_types_in(None, None)

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
        """Return signed contextual resistance totals by damage type read with no target or context."""
        return self.resistance_sum_in(None, None)

    @computed_field
    @property
    def resistance(self) -> Dict[DamageType, ResistanceStatus]:
        """Return final contextual resistance states by damage type.

        Returns:
            Damage type to vulnerability, none, resistance, or immunity.
        """
        return _resistance_statuses(self.resistance_sum)

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

    def combine_values(self, others: List['ContextualValue'], naming_callable: Optional[naming_callable] = None,
                       *, use_register: bool = True) -> 'ContextualValue':
        """Combine this value with other contextual values.

        Args:
            others: Contextual values to merge with this value.
            naming_callable: Optional function that names the combined value
                from the source value names.
            use_register: Register the newly combined value.

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
            use_register=use_register,
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
            generated_from=(self.uuid, *(other.uuid for other in others)),
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
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
        """Set the score normalizer on this channel; contextual rows produce their own normalized values.

        Args:
            normalizer: Normalizer function to apply.
        """
        self.score_normalizer = normalizer

class OpponentOutgoing(NamedTuple):
    """The opponent's outgoing channels in an opposed read and the context their rows are read in."""

    static: StaticValue
    contextual: ContextualValue
    context: Optional[Dict[str, Any]] = None


class ValueRead(NamedTuple):
    """One read of a value: its owner, the target, the situation and the opponent's outgoing channels.

    The owner's contextual rows are read with (target, context). The opponent's
    outgoing contextual rows are read with (owner, opponent context).
    """

    source_entity_uuid: UUID
    target_entity_uuid: Optional[UUID] = None
    context: Optional[Dict[str, Any]] = None
    opponent: Optional[OpponentOutgoing] = None


def outgoing_of(values: Sequence['ModifiableValue'], context: Optional[Dict[str, Any]]) -> OpponentOutgoing:
    """The opponent side of an opposed read: its components' outgoing channels, merged in order."""
    first, rest = values[0], values[1:]
    if not rest:
        return OpponentOutgoing(first.to_target_static, first.to_target_contextual, context)
    return OpponentOutgoing(
        first.to_target_static.combine_values([value.to_target_static for value in rest], use_register=False),
        first.to_target_contextual.combine_values([value.to_target_contextual for value in rest], use_register=False),
        context,
    )


_DISPLAY_NAMES = {
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


def _display_name(raw_name: str) -> str:
    """Normalize an internal modifier name for breakdown display."""
    if raw_name in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[raw_name]
    cleaned = raw_name
    for suffix in ["_base_value", "_bonus", "_modifier", " Bonus", " Modifier"]:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
    if " Ability Score" in cleaned:
        cleaned = cleaned.replace(" Ability Score", "")
    return cleaned.replace("_", " ").title()


class ValueBreakdownRow(BaseModel):
    """One displayed static numerical row: a flat value or a multiplying factor."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Display name of the contribution.")
    source: str = Field(description="'self' for the owner's rows, 'from_target' for the opponent's outgoing rows.")
    value: int = Field(default=0, description="Normalized flat value; 0 for factor rows.")
    numerator: Optional[int] = Field(default=None, description="Factor numerator for multiplying rows.")
    denominator: Optional[int] = Field(default=None, description="Factor denominator for multiplying rows.")
    operation: Optional[str] = Field(default=None, description="'multiply' for factor rows.")


class AdvantageBreakdownRow(BaseModel):
    """One displayed advantage row; contextual rows record whether they applied in the read."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Display name of the contribution.")
    value: str = Field(description="'advantage', 'disadvantage', a lower-cased contextual status, or 'inactive'.")
    source: str = Field(description="'self', 'from_target', 'self_contextual' or 'from_target_contextual'.")
    active: Optional[bool] = Field(default=None, description="Whether a contextual row applied; None for static rows.")


class ValueChannelReading(BaseModel):
    """One channel's numerical aggregate in a read: totals, bounds and factor."""

    model_config = ConfigDict(frozen=True)

    raw: int = Field(description="Sum of the active raw contributions.")
    normalized: int = Field(description="Sum of the active normalized contributions.")
    minimum: Optional[int] = Field(default=None, description="Lowest active minimum constraint.")
    maximum: Optional[int] = Field(default=None, description="Highest active maximum constraint.")
    factor_numerator: int = Field(default=1, description="Numerator of the product of active factors.")
    factor_denominator: int = Field(default=1, description="Denominator of the product of active factors.")
    factor_keyed: bool = Field(default=False, description="Whether the channel holds factor rows, which select the factor rule.")


class _ChannelNumbers(NamedTuple):
    raw: int
    normalized: int
    minimum: Optional[int]
    maximum: Optional[int]
    factor: Optional[Fraction]
    factor_keyed: bool


def _score_of(channels: Sequence[_ChannelNumbers], normalized: bool) -> int:
    """Sum the channels, multiply once when any factor row exists, then bound.

    Without factors each channel is clamped by its own bounds before the sum, and
    the sum by the lowest minimum and highest maximum of all channels.
    """
    keyed = False
    total = 0
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    for channel in channels:
        low, high = channel.minimum, channel.maximum
        if low is not None and (minimum is None or low < minimum):
            minimum = low
        if high is not None and (maximum is None or high > maximum):
            maximum = high
        keyed = keyed or channel.factor_keyed
    if keyed:
        factor = Fraction(1)
        for channel in channels:
            total += channel.normalized if normalized else channel.raw
            if channel.factor is not None:
                factor *= channel.factor
        return int(_clamped(total * factor, minimum, maximum))
    for channel in channels:
        number = channel.normalized if normalized else channel.raw
        if channel.minimum is not None or channel.maximum is not None:
            number = int(_clamped(number, channel.minimum, channel.maximum))
        total += number
    return int(_clamped(total, minimum, maximum))


def _static_buckets(channel: StaticValue) -> Dict[str, Dict[UUID, Any]]:
    return {"factor_modifiers": dict(channel.factor_modifiers), "min_constraints": dict(channel.min_constraints),
            "max_constraints": dict(channel.max_constraints), "advantage_modifiers": dict(channel.advantage_modifiers),
            "critical_modifiers": dict(channel.critical_modifiers), "auto_hit_modifiers": dict(channel.auto_hit_modifiers),
            "size_modifiers": dict(channel.size_modifiers), "damage_type_modifiers": dict(channel.damage_type_modifiers),
            "resistance_modifiers": dict(channel.resistance_modifiers)}


def _contextual_buckets(channel: ContextualValue) -> Dict[str, Dict[UUID, Any]]:
    return {"value_modifiers": dict(channel.value_modifiers), "min_constraints": dict(channel.min_constraints),
            "max_constraints": dict(channel.max_constraints), "advantage_modifiers": dict(channel.advantage_modifiers),
            "critical_modifiers": dict(channel.critical_modifiers), "auto_hit_modifiers": dict(channel.auto_hit_modifiers),
            "size_modifiers": dict(channel.size_modifiers), "damage_type_modifiers": dict(channel.damage_type_modifiers),
            "resistance_modifiers": dict(channel.resistance_modifiers)}


def _value_rows(channel: StaticValue, source: str) -> List[ValueBreakdownRow]:
    rows = [ValueBreakdownRow(name=_display_name(modifier.name or "Factor"), source=source,
                              numerator=modifier.numerator, denominator=modifier.denominator, operation="multiply")
            for modifier in channel.factor_modifiers.values()]
    for modifier in channel.value_modifiers.values():
        value = modifier.normalized_value
        if value != 0:
            rows.append(ValueBreakdownRow(name=_display_name(modifier.name or "Unknown"), source=source, value=value))
    return rows


def _static_advantage_rows(modifiers: Iterable[AdvantageModifier], source: str) -> List[AdvantageBreakdownRow]:
    rows = []
    for modifier in modifiers:
        if modifier.value == AdvantageStatus.ADVANTAGE:
            rows.append(AdvantageBreakdownRow(name=modifier.name or "Unknown", value="advantage", source=source))
        elif modifier.value == AdvantageStatus.DISADVANTAGE:
            rows.append(AdvantageBreakdownRow(name=modifier.name or "Unknown", value="disadvantage", source=source))
    return rows


def _contextual_advantage(channel: ContextualValue, target: Optional[UUID], context: Optional[Dict[str, Any]],
                          source: str) -> tuple[int, List[AdvantageBreakdownRow]]:
    """Signed advantage total and display rows of one contextual channel; each callable is evaluated once."""
    total = 0
    rows = []
    for modifier, result in _contextual_advantage_results(channel.advantage_modifiers, channel.source_entity_uuid,
                                                          target, context):
        if isinstance(result, AdvantageModifier):
            total += result.numerical_value
            rows.append(AdvantageBreakdownRow(name=modifier.name or "Unknown", value=result.value.value.lower(),
                                              source=source, active=True))
        else:
            rows.append(AdvantageBreakdownRow(name=modifier.name or "Unknown", value="inactive",
                                              source=source, active=False))
    return total, rows


def _insert_after_source(rows: tuple, row: BaseModel, source: str, static_only: bool) -> tuple:
    at = 0
    for index, existing in enumerate(rows):
        if existing.source == source and (not static_only or existing.active is None):
            at = index + 1
    return rows[:at] + (row,) + rows[at:]


class ValueReading(BaseModel):
    """A value evaluated once in one read situation: the record that dice, events and logs keep.

    Rows a reaction adds during an attack (Shield, Parry, Protection) enter the
    owner's static channel, so the totals recompute as they did on the composed value.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Name of the value that was read.")
    source_entity_uuid: UUID = Field(description="Entity that owns the value.")
    target_entity_uuid: Optional[UUID] = Field(default=None, description="Entity the value was read against.")
    fixed_score: Optional[int] = Field(default=None, description="Active fixed score, which replaces the channels.")
    fixed_normalized_score: Optional[int] = Field(default=None, description="Normalized active fixed score.")
    channels: tuple[ValueChannelReading, ...] = Field(
        description="Owner static, owner contextual, then opponent contextual and static channels.")
    advantage_sum: int = Field(description="Signed total of the active advantage rows.")
    critical: CriticalStatus = Field(description="Critical override, NOCRIT first.")
    auto_hit: AutoHitStatus = Field(description="Hit override, AUTOMISS first.")
    breakdown: tuple[ValueBreakdownRow, ...] = Field(default=(), description="Static numerical rows, owner first.")
    advantage_breakdown: tuple[AdvantageBreakdownRow, ...] = Field(
        default=(), description="Static advantage rows, then contextual rows with whether they applied.")

    def _total(self, normalized: bool) -> int:
        if self.fixed_score is not None and self.fixed_normalized_score is not None:
            return self.fixed_normalized_score if normalized else self.fixed_score
        return _score_of([_ChannelNumbers(channel.raw, channel.normalized, channel.minimum, channel.maximum,
                                          Fraction(channel.factor_numerator, channel.factor_denominator),
                                          channel.factor_keyed) for channel in self.channels], normalized)

    @computed_field
    @property
    def score(self) -> int:
        """Raw total of the read."""
        return self._total(False)

    @computed_field
    @property
    def normalized_score(self) -> int:
        """Normalized total of the read; what dice add."""
        return self._total(True)

    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """Advantage state of the read."""
        return _advantage_status(self.advantage_sum)


class ModifiableValue(BaseValue):
    """A value composed of the owner's channels and the channels it exports to opponents.

    A read takes a `ValueRead`. Properties read with no target, no context and
    no opponent; `read_value` evaluates the value once in a situation.
    """

    fixed_scores: Dict[UUID, NumericalModifier] = Field(default_factory=dict)

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
    global_normalizer: bool = Field(
        default=True,
        description="Whether this value propagates its normalizer into nested numerical channels."
    )

    def retire_owned_state(self) -> None:
        """Release this value's exact owned channels."""
        for identity in self.fixed_scores:
            BaseObject.unregister(identity)
        self.fixed_scores.clear()
        for component in (self.self_static, self.to_target_static,
                          self.self_contextual, self.to_target_contextual):
            for identity in component.get_all_modifier_uuids():
                BaseObject.unregister(identity)
            component.remove_all_modifiers()
            component.remove_from_register()
        self.remove_from_register()

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
               base_value: int = 0, value_name: str = "Value", score_normalizer: Optional[Callable[[int], int]] = None,
               global_normalizer: bool = True, identity_uuid: Optional[UUID] = None,
               *, use_register: bool = True) -> 'ModifiableValue':
        """Create a value whose primary channels share source metadata.

        Args:
            source_entity_uuid: Entity UUID that owns the value.
            source_entity_name: Optional display name for the source entity.
            base_value: Base numerical score stored in `self_static`.
            value_name: Human-readable value name.
            score_normalizer: Optional normalizer for scores and numerical
                modifiers.
            global_normalizer: Whether to propagate the normalizer into child
                channels.
            identity_uuid: Optional stable identity root. When supplied, the
                value, its four locally owned channels, and its base modifier
                receive identities derived from this UUID.
            use_register: Register the new value, its channels and base modifier.

        Returns:
            New modifiable value with initialized self and outgoing channels.
        """
        normalizer = score_normalizer if score_normalizer is not None else identity

        def owned_uuid(name: str) -> UUID:
            if identity_uuid is None:
                return uuid4()
            return uuid5(identity_uuid, name)

        base_modifier = NumericalModifier(
            use_register=use_register,
            uuid=owned_uuid("base_modifier"),
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid,
            value=base_value,
            name=f"{value_name}_base_value",
            score_normalizer=normalizer
        )

        return cls(
            use_register=use_register,
            uuid=identity_uuid or uuid4(),
            name=value_name,
            source_entity_uuid=source_entity_uuid,
            source_entity_name=source_entity_name,
            self_static=StaticValue(
                use_register=use_register,
                uuid=owned_uuid("self_static"),
                source_entity_uuid=source_entity_uuid,
                source_entity_name=source_entity_name,
                value_modifiers={base_modifier.uuid: base_modifier},
                score_normalizer=normalizer,
                global_normalizer=global_normalizer
            ),
            to_target_static=StaticValue(
                use_register=use_register,
                uuid=owned_uuid("to_target_static"),
                source_entity_uuid=source_entity_uuid,
                source_entity_name=source_entity_name,
                is_outgoing_modifier=True,
                score_normalizer=normalizer,
                global_normalizer=global_normalizer
            ),
            self_contextual=ContextualValue(
                use_register=use_register,
                uuid=owned_uuid("self_contextual"),
                source_entity_uuid=source_entity_uuid,
                source_entity_name=source_entity_name,
                score_normalizer=normalizer,
                global_normalizer=global_normalizer
            ),
            to_target_contextual=ContextualValue(
                use_register=use_register,
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
        """Return the lowest active minimum constraint of the owner's channels."""
        return min((low for low in (self.self_static.min, self.self_contextual.min) if low is not None), default=None)

    @computed_field
    @property
    def max(self) -> Optional[int]:
        """Return the highest active maximum constraint of the owner's channels."""
        return max((high for high in (self.self_static.max, self.self_contextual.max) if high is not None), default=None)

    def add_fixed_score(self, modifier: NumericalModifier) -> UUID:
        self.validate_modifier_target(modifier)
        self.fixed_scores[modifier.uuid] = modifier
        return modifier.uuid

    @computed_field
    @property
    def score(self) -> int:
        """Return the raw aggregate score read with no target or context."""
        return value_score(self, ValueRead(self.source_entity_uuid), normalized=False)

    @computed_field
    @property
    def normalized_score(self) -> int:
        """Return the normalized aggregate score read with no target or context."""
        return value_score(self, ValueRead(self.source_entity_uuid), normalized=True)

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
        return value_score(self, ValueRead(self.source_entity_uuid), normalized=True,
                           excluded=frozenset(modifier_uuids))

    @computed_field
    @property
    def advantage_sum(self) -> int:
        """Return the signed aggregate of active advantage modifiers read with no target or context."""
        return _value_advantage_sum(self, ValueRead(self.source_entity_uuid))

    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """Return the final advantage state read with no target or context."""
        return _advantage_status(self.advantage_sum)

    @computed_field
    @property
    def critical(self) -> CriticalStatus:
        """Return the critical-hit override read with no target or context."""
        return _value_critical(self, ValueRead(self.source_entity_uuid))

    @computed_field
    @property
    def auto_hit(self) -> AutoHitStatus:
        """Return the hit override read with no target or context."""
        return _value_auto_hit(self, ValueRead(self.source_entity_uuid))

    @computed_field
    @property
    def size(self) -> Size:
        """Return the effective size read with no target or context."""
        return value_size(self, ValueRead(self.source_entity_uuid))

    @computed_field
    @property
    def damage_types(self) -> List[DamageType]:
        """Return the most common active damage types read with no target or context."""
        return value_damage_types(self, ValueRead(self.source_entity_uuid))

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
        """Return signed resistance totals by damage type read with no target or context."""
        return value_resistance_sum(self, ValueRead(self.source_entity_uuid))

    @computed_field
    @property
    def resistance(self) -> Dict[DamageType, ResistanceStatus]:
        """Return final resistance states by damage type read with no target or context."""
        return _resistance_statuses(self.resistance_sum)

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

    def combine_values(self, others: List['ModifiableValue'], naming_callable: Optional[naming_callable] = None,
                       *, use_register: bool = True) -> 'ModifiableValue':
        """Combine this value with other modifiable values.

        Args:
            others: Modifiable values to merge with this value.
            naming_callable: Optional function that names the combined value
                from the source value names.
            use_register: Register the newly combined value and its channels.

        Returns:
            New modifiable value containing merged component channels.

        Raises:
            ValueError: If any other value has a different source entity UUID.
        """
        if naming_callable is None:
            naming_callable = lambda names: "_".join(names)

        for other in others:
            self.validate_source_id(other.source_entity_uuid)

        return ModifiableValue(
            use_register=use_register,
            fixed_scores={**self.fixed_scores, **{k: v for other in others for k, v in other.fixed_scores.items()}},
            name=naming_callable([self.name] + [other.name for other in others]),
            self_static=self.self_static.combine_values([other.self_static for other in others], use_register=use_register),
            to_target_static=self.to_target_static.combine_values([other.to_target_static for other in others], use_register=use_register),
            self_contextual=self.self_contextual.combine_values([other.self_contextual for other in others], use_register=use_register),
            to_target_contextual=self.to_target_contextual.combine_values([other.to_target_contextual for other in others], use_register=use_register),
            generated_from=(self.uuid, *(other.uuid for other in others)),
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            score_normalizer=self.score_normalizer,
            global_normalizer=False,
        )

    def renormalized(self, normalizer: Callable[[int], int]) -> 'ModifiableValue':
        """This value with its numerical rows scaled by `normalizer` (a proficiency rule), sharing every other row.

        The returned value is unregistered and keeps this value's identity. Its row
        buckets are fresh dicts holding the same row objects, except the scaled
        numerical rows, which are copies with the new normalizer.
        """
        def static(channel: StaticValue) -> StaticValue:
            return channel.model_copy(update={**_static_buckets(channel), "score_normalizer": normalizer,
                "value_modifiers": {key: modifier.model_copy(update={"score_normalizer": normalizer})
                                    for key, modifier in channel.value_modifiers.items()}})

        def contextual(channel: ContextualValue) -> ContextualValue:
            return channel.model_copy(update={**_contextual_buckets(channel), "score_normalizer": normalizer})

        return self.model_copy(update={
            "score_normalizer": normalizer,
            "fixed_scores": dict(self.fixed_scores),
            "generated_from": list(self.generated_from),
            "self_static": static(self.self_static),
            "to_target_static": static(self.to_target_static),
            "self_contextual": contextual(self.self_contextual),
            "to_target_contextual": contextual(self.to_target_contextual),
        })

    def get_breakdown(self) -> List[ValueBreakdownRow]:
        """Return the owner's static numerical rows for display."""
        return _value_rows(self.self_static, "self")

    def remove_modifier(self, uuid: UUID) -> None:
        """Remove a modifier UUID from every channel.

        Args:
            uuid: Modifier UUID to remove.
        """
        self.fixed_scores.pop(uuid, None)
        self.self_static.remove_modifier(uuid)
        self.self_contextual.remove_modifier(uuid)
        self.to_target_static.remove_modifier(uuid)
        self.to_target_contextual.remove_modifier(uuid)

    def remove_all_modifiers(self) -> None:
        """Clear every modifier bucket on every channel."""
        self.fixed_scores.clear()
        self.self_static.remove_all_modifiers()
        self.self_contextual.remove_all_modifiers()
        self.to_target_static.remove_all_modifiers()
        self.to_target_contextual.remove_all_modifiers()

    def get_all_modifier_uuids(self) -> List[UUID]:
        """Return all modifier UUIDs stored in any channel.

        Returns:
            UUIDs from self and outgoing channels.
        """
        uuids = list(self.fixed_scores)
        for component in [self.self_static, self.to_target_static, self.self_contextual, self.to_target_contextual]:
            uuids.extend(component.get_all_modifier_uuids())
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

        return self

    @model_validator(mode="after")
    def align_channel_sources(self) -> Self:
        """Give every primary channel this value's source.

        Returns:
            This value after alignment.
        """
        for component in [self.self_static, self.to_target_static, self.self_contextual, self.to_target_contextual]:
            if component.source_entity_uuid != self.source_entity_uuid:
                component.source_entity_uuid = self.source_entity_uuid
        return self

    @computed_field
    @property
    def outgoing_advantage_sum(self) -> int:
        """Return the signed advantage total exported to targeters, read with no target or context."""
        return self.to_target_static.advantage_sum + self.to_target_contextual.advantage_sum

    @computed_field
    @property
    def outgoing_advantage(self) -> AdvantageStatus:
        """Return the advantage state exported to targeters."""
        return _advantage_status(self.outgoing_advantage_sum)

    @computed_field
    @property
    def outgoing_critical(self) -> CriticalStatus:
        """Return the critical-hit override exported to targeters; NOCRIT takes precedence."""
        return _critical_status([self.to_target_static.critical, self.to_target_contextual.critical])

    @computed_field
    @property
    def outgoing_auto_hit(self) -> AutoHitStatus:
        """Return the hit override exported to targeters; AUTOMISS takes precedence."""
        return _auto_hit_status([self.to_target_static.auto_hit, self.to_target_contextual.auto_hit])


def _fixed_score(value: 'ModifiableValue', excluded: frozenset[UUID]) -> Optional[int]:
    if not value.fixed_scores:
        return None
    fixed = [modifier.value for identity, modifier in value.fixed_scores.items()
             if identity not in excluded and modifier.contributions_active()]
    return min(fixed) if fixed else None


def _static_numbers(channel: StaticValue, excluded: frozenset[UUID], sides: tuple[bool, bool]) -> _ChannelNumbers:
    """A static channel's totals (raw and/or normalized, as `sides` asks), bounds and factor."""
    factors = channel.factor_modifiers
    return _ChannelNumbers(channel.additive_score(False, excluded) if sides[0] else 0,
                           channel.additive_score(True, excluded) if sides[1] else 0,
                           *channel.score_bounds(excluded),
                           channel.arithmetic_factor(excluded) if factors else None,
                           any(key not in excluded for key in factors) if factors else False)


def _contextual_channel_numbers(channel: ContextualValue, target: Optional[UUID],
                                context: Optional[Dict[str, Any]]) -> _ChannelNumbers:
    """A contextual channel's totals and bounds in one read situation; each callable is evaluated once."""
    return _ChannelNumbers(*channel.numbers_in(target, context), *channel.bounds_in(target, context), None, False)


def _channel_numbers(value: 'ModifiableValue', read: ValueRead, excluded: frozenset[UUID],
                     sides: tuple[bool, bool]) -> List[_ChannelNumbers]:
    """Each channel's totals in this read, in score order (owner static, owner contextual, opponent)."""
    opponent = read.opponent
    channels = [_static_numbers(value.self_static, excluded, sides),
                _contextual_channel_numbers(value.self_contextual, read.target_entity_uuid, read.context)]
    if opponent is not None:
        channels.append(_contextual_channel_numbers(opponent.contextual, read.source_entity_uuid, opponent.context))
        channels.append(_static_numbers(opponent.static, excluded, sides))
    return channels


def value_score(value: 'ModifiableValue', read: ValueRead, *, normalized: bool,
                excluded: frozenset[UUID] = frozenset()) -> int:
    """A value's total in a read: channels summed, multiplied exactly once, then bounded (and normalized)."""
    fixed = _fixed_score(value, excluded)
    if fixed is not None:
        return value.score_normalizer(fixed) if normalized else fixed
    return _score_of(_channel_numbers(value, read, excluded, (not normalized, normalized)), normalized)


def _value_advantage_sum(value: 'ModifiableValue', read: ValueRead) -> int:
    total = value.self_static.advantage_sum + value.self_contextual.advantage_sum_in(read.target_entity_uuid, read.context)
    if read.opponent is not None:
        total += read.opponent.static.advantage_sum + read.opponent.contextual.advantage_sum_in(
            read.source_entity_uuid, read.opponent.context)
    return total


def _value_critical(value: 'ModifiableValue', read: ValueRead) -> CriticalStatus:
    statuses = [value.self_static.critical, value.self_contextual.critical_in(read.target_entity_uuid, read.context)]
    if read.opponent is not None:
        statuses += [read.opponent.contextual.critical_in(read.source_entity_uuid, read.opponent.context),
                     read.opponent.static.critical]
    return _critical_status(statuses)


def _value_auto_hit(value: 'ModifiableValue', read: ValueRead) -> AutoHitStatus:
    statuses = [value.self_static.auto_hit, value.self_contextual.auto_hit_in(read.target_entity_uuid, read.context)]
    if read.opponent is not None:
        statuses += [read.opponent.contextual.auto_hit_in(read.source_entity_uuid, read.opponent.context),
                     read.opponent.static.auto_hit]
    return _auto_hit_status(statuses)


def value_size(value: 'ModifiableValue', read: ValueRead) -> Size:
    """Effective size of a value in a read: the largest (or smallest) non-medium size of its channels."""
    sizes = [size for size in (value.self_static.size, value.self_contextual.size_in(read.target_entity_uuid, read.context))
             if size != Size.MEDIUM]
    if read.opponent is not None:
        sizes += [size for size in (read.opponent.contextual.size_in(read.source_entity_uuid, read.opponent.context),
                                    read.opponent.static.size) if size != Size.MEDIUM]
    if not sizes:
        return Size.MEDIUM
    if value.self_static.largest_size_priority:
        return max(sizes, key=lambda s: list(Size).index(s))
    return min(sizes, key=lambda s: list(Size).index(s))


def value_damage_types(value: 'ModifiableValue', read: ValueRead) -> List[DamageType]:
    """Most common damage types of a value in a read, over its own, outgoing and opponent channels."""
    groups = [value.self_static.damage_types, value.to_target_static.damage_types,
              value.self_contextual.damage_types_in(read.target_entity_uuid, read.context),
              value.to_target_contextual.damage_types_in(read.target_entity_uuid, read.context)]
    if read.opponent is not None:
        groups += [read.opponent.static.damage_types,
                   read.opponent.contextual.damage_types_in(read.source_entity_uuid, read.opponent.context)]
    type_counts: Dict[DamageType, int] = {}
    for group in groups:
        for damage_type in group:
            type_counts[damage_type] = type_counts.get(damage_type, 0) + 1
    if not type_counts:
        return []
    max_count = max(type_counts.values())
    return [damage_type for damage_type, count in type_counts.items() if count == max_count]


def value_resistance_sum(value: 'ModifiableValue', read: ValueRead) -> Dict[DamageType, int]:
    """Signed resistance totals of a value in a read, over its own, outgoing and opponent channels."""
    sums = [value.self_static.resistance_sum, value.to_target_static.resistance_sum,
            value.self_contextual.resistance_sum_in(read.target_entity_uuid, read.context),
            value.to_target_contextual.resistance_sum_in(read.target_entity_uuid, read.context)]
    if read.opponent is not None:
        sums += [read.opponent.static.resistance_sum,
                 read.opponent.contextual.resistance_sum_in(read.source_entity_uuid, read.opponent.context)]
    total = {damage_type: 0 for damage_type in DamageType}
    for row in sums:
        for damage_type, amount in row.items():
            total[damage_type] += amount
    return total


def value_resistance(value: 'ModifiableValue', read: ValueRead) -> Dict[DamageType, ResistanceStatus]:
    """Resistance states of a value in a read."""
    return _resistance_statuses(value_resistance_sum(value, read))


def read_value(value: 'ModifiableValue', read: ValueRead) -> ValueReading:
    """Evaluate this value once in a read situation; the frozen record dice and events keep."""
    opponent = read.opponent
    fixed = _fixed_score(value, frozenset())
    own_total, own_rows = _contextual_advantage(value.self_contextual, read.target_entity_uuid, read.context,
                                                "self_contextual")
    advantage_sum = value.self_static.advantage_sum + own_total
    breakdown = _value_rows(value.self_static, "self")
    static_rows = _static_advantage_rows(value.self_static.advantage_modifiers.values(), "self")
    contextual_rows = own_rows
    if opponent is not None:
        opponent_total, opponent_rows = _contextual_advantage(opponent.contextual, read.source_entity_uuid,
                                                              opponent.context, "from_target_contextual")
        advantage_sum += opponent.static.advantage_sum + opponent_total
        breakdown += _value_rows(opponent.static, "from_target")
        static_rows += _static_advantage_rows(opponent.static.advantage_modifiers.values(), "from_target")
        contextual_rows += opponent_rows
    return ValueReading(
        name=value.name, source_entity_uuid=value.source_entity_uuid, target_entity_uuid=read.target_entity_uuid,
        fixed_score=fixed, fixed_normalized_score=value.score_normalizer(fixed) if fixed is not None else None,
        channels=tuple(ValueChannelReading(raw=channel.raw, normalized=channel.normalized, minimum=channel.minimum,
            maximum=channel.maximum,
            factor_numerator=channel.factor.numerator if channel.factor is not None else 1,
            factor_denominator=channel.factor.denominator if channel.factor is not None else 1,
            factor_keyed=channel.factor_keyed)
            for channel in _channel_numbers(value, read, frozenset(), (True, True))),
        advantage_sum=advantage_sum,
        critical=_value_critical(value, read), auto_hit=_value_auto_hit(value, read),
        breakdown=tuple(breakdown), advantage_breakdown=tuple(static_rows + contextual_rows))


def reading_with_value_row(reading: ValueReading, modifier: NumericalModifier) -> ValueReading:
    """The read with one more owner static numerical row (a reaction's AC bonus)."""
    own = reading.channels[0]
    if modifier.contributions_active():
        own = own.model_copy(update={"raw": own.raw + modifier.value,
                                     "normalized": own.normalized + modifier.normalized_value})
    rows = reading.breakdown
    if modifier.normalized_value != 0:
        rows = _insert_after_source(rows, ValueBreakdownRow(name=_display_name(modifier.name or "Unknown"),
                                    source="self", value=modifier.normalized_value), "self", False)
    return reading.model_copy(update={"channels": (own, *reading.channels[1:]), "breakdown": rows})


def reading_with_advantage_row(reading: ValueReading, modifier: AdvantageModifier) -> ValueReading:
    """The read with one more owner static advantage row (a reaction's disadvantage)."""
    total = reading.advantage_sum + (modifier.numerical_value if modifier.contributions_active() else 0)
    rows = reading.advantage_breakdown
    for row in _static_advantage_rows((modifier,), "self"):
        rows = _insert_after_source(rows, row, "self", True)
    return reading.model_copy(update={"advantage_sum": total, "advantage_breakdown": rows})


def has_static_advantage_row(reading: ValueReading, name: str) -> bool:
    """Whether the owner's static rows of the read hold an advantage row with this name."""
    return any(row.source == "self" and row.active is None and row.name == name
               for row in reading.advantage_breakdown)


def composed_passive_score(
    proficiency: ModifiableValue,
    skill: ModifiableValue,
    ability_score: ModifiableValue,
    ability_bonus: ModifiableValue,
    ability_source_uuid: UUID,
    proficiency_normalizer: Callable[[int], int],
    ability_normalizer: Callable[[int], int],
) -> Optional[int]:
    """Read a passive score (no target, no context, no opponent) without constructing temporary values.

    Inputs this scalar form does not cover (contextual proficiency rows, fixed
    scores, invalid outgoing rows) return None and take the composed read. All
    other rows are merged in the native order, independently in each channel,
    and each channel's bounds are read once, as in `value_score`.
    """
    for channel in (proficiency.self_contextual, proficiency.to_target_contextual):
        if channel.value_modifiers:
            return None
    if (proficiency.self_contextual.min_constraints or proficiency.self_contextual.max_constraints
            or proficiency.self_contextual.advantage_modifiers):
        return None
    # Rebuilding outgoing channels also validates their targets, even though
    # they do not contribute to this score. Preserve that validation for rows
    # installed through mutable modifier owners after channel construction.
    for value in (proficiency, skill, ability_bonus):
        channel = value.to_target_static
        if any(modifier.target_entity_uuid == channel.source_entity_uuid
               for modifiers in (channel.value_modifiers, channel.factor_modifiers,
                                 channel.min_constraints, channel.max_constraints)
               for modifier in modifiers.values()):
            return None

    if any(value.fixed_scores for value in (proficiency, skill, ability_bonus)):
        return None
    ability_base = ability_normalizer(ability_score.score)
    ability_bonus.validate_source_id(ability_source_uuid)
    proficiency.validate_source_id(skill.source_entity_uuid)
    proficiency.validate_source_id(ability_source_uuid)
    values = (proficiency, skill, ability_bonus)
    # The synthetic ability value has the ability owner's source in all primary
    # channels; the two native combinations enforce those same source identities.
    for channels in (
        tuple(value.self_static for value in values),
        tuple(value.to_target_static for value in values),
        tuple(value.self_contextual for value in values),
        tuple(value.to_target_contextual for value in values),
    ):
        channels[-1].validate_source_id(ability_source_uuid)
        for channel in channels[1:]:
            channels[0].validate_source_id(channel.source_entity_uuid)

    def static_inputs(channels):
        numbers, factors, minima, maxima, advantages = {}, {}, {}, {}, {}
        first = None
        for channel, normalizer in channels:
            if channel is None:
                continue
            if first is None:
                first = channel
            else:
                first.validate_source_id(channel.source_entity_uuid)
            numbers.update((key, (modifier, normalizer)) for key, modifier in channel.value_modifiers.items())
            factors.update(channel.factor_modifiers)
            minima.update(channel.min_constraints)
            maxima.update(channel.max_constraints)
            advantages.update(channel.advantage_modifiers)
        return numbers, factors, minima, maxima, advantages

    def contextual_inputs(channels):
        numbers, minima, maxima, advantages = {}, {}, {}, {}
        first = None
        for channel in channels:
            if channel is None:
                continue
            if first is None:
                first = channel
            else:
                first.validate_source_id(channel.source_entity_uuid)
            numbers.update(channel.value_modifiers)
            minima.update(channel.min_constraints)
            maxima.update(channel.max_constraints)
            advantages.update(channel.advantage_modifiers)
        if first is None:
            return None
        return numbers, minima, maxima, advantages, first.source_entity_uuid

    own_static = static_inputs([(value.self_static,
        proficiency_normalizer if index == 0 else None) for index, value in enumerate(values)])
    own_context = contextual_inputs([value.self_contextual for value in values])

    def static_additive(inputs, base=0):
        numbers, _, _, _, _ = inputs
        return base + sum((normalizer(modifier.value) if normalizer is not None else modifier.normalized_value)
            for modifier, normalizer in numbers.values() if modifier.contributions_active())

    def static_bounds(inputs):
        _, _, minima, maxima, _ = inputs
        return (min((modifier.value for modifier in minima.values() if modifier.contributions_active()), default=None),
                max((modifier.value for modifier in maxima.values() if modifier.contributions_active()), default=None))

    def static_factor(inputs):
        _, factors, _, _, _ = inputs
        return prod((Fraction(modifier.numerator, modifier.denominator)
            for modifier in factors.values() if modifier.contributions_active()), start=Fraction(1))

    def context_additive(inputs):
        if inputs is None:
            return 0
        numbers, _, _, _, source = inputs
        return _contextual_numbers(numbers, source, None, None)[1]

    def context_bounds(inputs):
        if inputs is None:
            return None, None
        _, minima, maxima, _, source = inputs
        return (min(_contextual_constraint_values(minima, source, None, None), default=None),
                max(_contextual_constraint_values(maxima, source, None, None), default=None))

    # Factor presence selects the aggregate-first rule even when a retained
    # factor is currently suppressed. Evaluate factors before additive callbacks.
    if own_static[1]:
        factor = static_factor(own_static)
        total = sum((static_additive(own_static, ability_base), context_additive(own_context))) * factor
        bounds = (static_bounds(own_static), context_bounds(own_context))
    else:
        # Native channel order; each channel is clamped by the bounds the aggregate then reads.
        own_static_total, own_static_bounds = static_additive(own_static, ability_base), static_bounds(own_static)
        own_context_total, own_context_bounds = context_additive(own_context), context_bounds(own_context)
        total = (int(_clamped(own_static_total, *own_static_bounds))
                 + _clamped(own_context_total, *own_context_bounds))
        bounds = (own_static_bounds, own_context_bounds)
    minimum = min((lower for lower, _ in bounds if lower is not None), default=None)
    maximum = max((upper for _, upper in bounds if upper is not None), default=None)
    score = 10 + int(_clamped(total, minimum, maximum))

    def advantage_sum():
        _, _, _, _, advantages = own_static
        result = sum(modifier.numerical_value for modifier in advantages.values() if modifier.contributions_active())
        if own_context is not None:
            _, _, _, contextual_advantages, source = own_context
            result += _advantage_total(_contextual_advantage_results(contextual_advantages, source, None, None))
        return result

    if advantage_sum() > 0:
        return score + 5
    if advantage_sum() < 0:
        return score - 5
    return score
