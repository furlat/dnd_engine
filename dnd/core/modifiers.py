import logging

from pydantic import Field, computed_field, model_validator
from typing import List, Optional, Dict, Any, Callable, TypeVar, Union, Tuple, Self
from uuid import UUID

from dnd.core.base_object import BaseObject
from dnd.types import creatures as creature_types
from dnd.types import damage as damage_types
from dnd.types import rolls as roll_types

logger = logging.getLogger(__name__)

T_co = TypeVar('T_co', covariant=True)

ContextAwareCallable = Callable[[UUID, Optional[UUID], Optional[Dict[str, Any]]], Optional[T_co]]


class NumericalModifier(BaseObject):
    """Flat numerical bonus, penalty, or constraint payload."""

    value: int = Field(
        ...,
        description="Raw integer contribution applied by the modifier."
    )
    score_normalizer: Optional[Callable[[int], int]] = Field(
        default=None,
        exclude=True,
        description="Optional callable that converts the raw value for normalized-score calculations."
    )

    @computed_field
    @property
    def normalized_value(self) -> int:
        """Return the raw value after applying the optional normalizer."""
        if self.score_normalizer is None:
            return self.value
        return self.score_normalizer(self.value)

    @classmethod
    def create(
        cls,
        source_entity_uuid: UUID,
        source_entity_name: Optional[str] = None,
        target_entity_uuid: Optional[UUID] = None,
        target_entity_name: Optional[str] = None,
        name: str = "Numerical Modifier",
        value: int = 0,
        score_normalizer: Optional[Callable[[int], int]] = None,
    ) -> 'NumericalModifier':
        """Create a numerical modifier.

        Args:
            source_entity_uuid: Entity UUID that produced this modifier.
            source_entity_name: Optional display name for the source entity.
            target_entity_uuid: Optional entity UUID this modifier targets.
            target_entity_name: Optional display name for the target entity.
            name: Human-readable modifier name.
            value: Raw integer modifier value.
            score_normalizer: Optional normalizer for this modifier value.

        Returns:
            New numerical modifier.
        """
        return cls(
            source_entity_uuid=source_entity_uuid,
            source_entity_name=source_entity_name,
            target_entity_uuid=target_entity_uuid,
            target_entity_name=target_entity_name,
            name=name,
            value=value,
            score_normalizer=score_normalizer,
        )


class AdvantageModifier(BaseObject):
    """Advantage, disadvantage, or neutral roll-state payload."""

    value: roll_types.AdvantageStatus = Field(
        ...,
        description="Roll-state contribution applied by this modifier."
    )

    @computed_field
    @property
    def numerical_value(self) -> int:
        """Return the signed aggregation value for this roll state.

        Returns:
            `1` for advantage, `-1` for disadvantage, and `0` for none.
        """
        if self.value == roll_types.AdvantageStatus.ADVANTAGE:
            return 1
        elif self.value == roll_types.AdvantageStatus.DISADVANTAGE:
            return -1
        else:
            return 0


class CriticalModifier(BaseObject):
    """Critical-hit override payload."""

    value: roll_types.CriticalStatus = Field(
        ...,
        description="Critical-hit override contributed by this modifier."
    )

class AutoHitModifier(BaseObject):
    """Automatic hit or miss override payload."""

    value: roll_types.AutoHitStatus = Field(
        ...,
        description="Hit override contributed by this modifier."
    )

ContextAwareCondition = ContextAwareCallable[bool]
ContextAwareAdvantage = ContextAwareCallable[AdvantageModifier]
ContextAwareCritical = ContextAwareCallable[CriticalModifier]
ContextAwareAutoHit = ContextAwareCallable[AutoHitModifier]
ContextAwareNumerical = ContextAwareCallable[NumericalModifier]

score_normaliziation_method = Callable[[int], int]
naming_callable = Callable[[List[str]], str]


class ContextualModifier(BaseObject):
    """Callable modifier evaluated against source, target, and context."""

    callable: Union[ContextAwareNumerical, ContextAwareAdvantage, ContextAwareCritical, ContextAwareAutoHit] = Field(
        ...,
        exclude=True,
        description="Excluded callable with signature `(source_uuid, target_uuid, context)`; `evaluate()` catches exceptions."
    )
    callable_arguments: Optional[Tuple[UUID, Optional[UUID], Optional[Dict[str, Any]]]] = Field(
        default=None,
        description="Arguments used by strict `execute_callable()` rather than normal contextual aggregation."
    )
    cached_results: Dict[str, Optional[Any]] = Field(
        default_factory=dict,
        description="Evaluation cache keyed by `source|target|lineage`; values may be `None`."
    )

    @model_validator(mode="after")
    def validate_callable_source_iid(self) -> Self:
        """Validate stored callable arguments when they are present.

        Returns:
            This modifier after validation.
        """
        self.callable_validation_function()
        return self

    def callable_validation_function(self) -> None:
        """Validate strict callable arguments against this modifier's target."""
        if self.callable_arguments is not None:
            source_entity_uuid, _, _ = self.callable_arguments
            if source_entity_uuid != self.target_entity_uuid:
                raise ValueError("Callable argument Source entity UUID does not match target entity UUID of the modifier")

    def setup_callable_arguments(
        self,
        source_entity_uuid: UUID,
        target_entity_uuid: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store strict-call arguments for later `execute_callable()` use.

        Args:
            source_entity_uuid: Source UUID passed to the callable.
            target_entity_uuid: Optional target UUID passed to the callable.
            context: Optional context dictionary passed to the callable.

        Raises:
            ValueError: If the stored source UUID conflicts with this
                modifier's target UUID.
        """
        self.callable_arguments = (source_entity_uuid, target_entity_uuid, context)
        self.callable_validation_function()

    def evaluate(
        self,
        source_entity_uuid: UUID,
        target_entity_uuid: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None,
        event_lineage_uuid: Optional[UUID] = None,
    ) -> Optional[Union[
        NumericalModifier,
        AdvantageModifier,
        CriticalModifier,
        AutoHitModifier,
        'SizeModifier',
        'DamageTypeModifier',
        'ResistanceModifier',
    ]]:
        """Evaluate the callable through the fail-soft aggregation boundary.

        Args:
            source_entity_uuid: Source UUID passed to the callable.
            target_entity_uuid: Optional target UUID passed to the callable.
            context: Optional context dictionary passed to the callable.
            event_lineage_uuid: Optional event lineage UUID used in the cache key.

        Returns:
            Callable result, or ``None`` when the rule does not apply or its
            contextual evaluator fails. Failures are logged; strict callers
            use :meth:`execute_callable`.
        """
        try:
            result = self.callable(
                source_entity_uuid,
                target_entity_uuid,
                context,
            )
        except Exception:
            logger.exception(
                "Contextual modifier %s (%s) failed during aggregation",
                self.name,
                self.uuid,
            )
            return None
        key = f"{source_entity_uuid}|{target_entity_uuid or 'none'}|{event_lineage_uuid or 'none'}"
        self.cached_results[key] = result
        return result

    def execute_callable(self) -> Union[
        NumericalModifier,
        AdvantageModifier,
        CriticalModifier,
        AutoHitModifier,
        'SizeModifier',
        'DamageTypeModifier',
        'ResistanceModifier',
    ]:
        """Execute the callable strictly using stored arguments.

        Unlike `evaluate()`, this method raises for missing arguments or a
        return type that does not match the contextual modifier subclass.

        Returns:
            Modifier returned by the callable.

        Raises:
            ValueError: If arguments are missing or the return type is wrong.
        """
        if self.callable_arguments is None:
            raise ValueError("Callable arguments not set")
        result = self.callable(*self.callable_arguments)
        expected_type = self._get_expected_return_type()
        if not isinstance(result, expected_type):
            raise ValueError(f"Callable returned unexpected type. Expected {expected_type.__name__}, got {type(result).__name__}")
        return result

    def _get_expected_return_type(self):
        """Return the strict callable return type for supported subclasses."""
        if isinstance(self, ContextualNumericalModifier):
            return NumericalModifier
        elif isinstance(self, ContextualAdvantageModifier):
            return AdvantageModifier
        elif isinstance(self, ContextualCriticalModifier):
            return CriticalModifier
        elif isinstance(self, ContextualAutoHitModifier):
            return AutoHitModifier
        elif isinstance(self, ContextualSizeModifier):
            return SizeModifier
        elif isinstance(self, ContextualDamageTypeModifier):
            return DamageTypeModifier
        elif isinstance(self, ContextualResistanceModifier):
            return ResistanceModifier
        else:
            raise ValueError(f"Unknown ContextualModifier subclass: {self.__class__.__name__}")

class ContextualAdvantageModifier(ContextualModifier):
    """Contextual callable that returns an advantage modifier."""

    callable: ContextAwareAdvantage = Field(
        ...,
        exclude=True,
        description="Excluded contextual callable that returns an `AdvantageModifier`."
    )

class ContextualCriticalModifier(ContextualModifier):
    """Contextual callable that returns a critical-hit modifier."""

    callable: ContextAwareCritical = Field(
        ...,
        exclude=True,
        description="Excluded contextual callable that returns a `CriticalModifier`."
    )

class ContextualAutoHitModifier(ContextualModifier):
    """Contextual callable that returns an automatic hit modifier."""

    callable: ContextAwareAutoHit = Field(
        ...,
        exclude=True,
        description="Excluded contextual callable that returns an `AutoHitModifier`."
    )

class ContextualNumericalModifier(ContextualModifier):
    """Contextual callable that returns a numerical modifier."""

    callable: ContextAwareNumerical = Field(
        ...,
        exclude=True,
        description="Excluded contextual callable that returns a `NumericalModifier`."
    )

class SizeModifier(BaseObject):
    """Creature or object size payload."""

    value: creature_types.Size = Field(
        ...,
        description="Size value contributed by this modifier."
    )

class DamageTypeModifier(BaseObject):
    """Damage type payload."""

    value: damage_types.DamageType = Field(
        ...,
        description="Damage type contributed by this modifier."
    )

ContextAwareSize = ContextAwareCallable[SizeModifier]
ContextAwareDamageType = ContextAwareCallable[DamageTypeModifier]

class ContextualSizeModifier(ContextualModifier):
    """Contextual callable that returns a size modifier."""

    callable: ContextAwareSize = Field(
        ...,
        exclude=True,
        description="Excluded contextual callable that returns a `SizeModifier`."
    )

class ContextualDamageTypeModifier(ContextualModifier):
    """Contextual callable that returns a damage type modifier."""

    callable: ContextAwareDamageType = Field(
        ...,
        exclude=True,
        description="Excluded contextual callable that returns a `DamageTypeModifier`."
    )

class ResistanceModifier(BaseObject):
    """Resistance, immunity, or vulnerability payload for one damage type."""

    value: damage_types.ResistanceStatus = Field(
        ...,
        description="Resistance state contributed by this modifier."
    )
    damage_type: damage_types.DamageType = Field(
        ...,
        description="Damage type affected by this resistance modifier."
    )

    @computed_field
    @property
    def numerical_value(self) -> int:
        """Return the signed aggregation value for this resistance state.

        Returns:
            `2` for immunity, `1` for resistance, `0` for none, and `-1`
            for vulnerability.
        """
        if self.value == damage_types.ResistanceStatus.IMMUNITY:
            return 2
        elif self.value == damage_types.ResistanceStatus.RESISTANCE:
            return 1
        elif self.value == damage_types.ResistanceStatus.VULNERABILITY:
            return -1
        else:
            return 0

ContextAwareResistance = ContextAwareCallable[ResistanceModifier]

class ContextualResistanceModifier(ContextualModifier):
    """Contextual callable that returns a resistance modifier."""

    callable: ContextAwareResistance = Field(
        ...,
        exclude=True,
        description="Excluded contextual callable that returns a `ResistanceModifier`."
    )
