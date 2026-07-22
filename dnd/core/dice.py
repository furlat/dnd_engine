import random
from collections import deque
from contextlib import contextmanager
from enum import Enum
from functools import cached_property
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Iterator,
    List,
    Literal,
    Optional,
    Self,
    Tuple,
    Union,
)
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field, model_validator

from dnd.core.values import (
    AdvantageStatus,
    AutoHitStatus,
    CriticalStatus,
    ModifiableValue,
)


def _default_randint(low: int, high: int) -> int:
    """Return a die face from Python's active random generator."""
    return random.randint(low, high)

_randint: Callable[[int, int], int] = _default_randint


@contextmanager
def fixed_dice_faces(*faces: int) -> Iterator[None]:
    """Use predetermined die faces while resolving dice expressions.

    Args:
        faces: Die faces to return in order. Each face must fit the die being
            rolled when it is consumed.

    Raises:
        RuntimeError: If the dice expression asks for more faces than were
            provided.
        ValueError: If a provided face is outside the requested die range.
    """
    global _randint

    queued_faces = deque(faces)
    previous_randint = _randint

    def next_fixed_face(low: int, high: int) -> int:
        if not queued_faces:
            raise RuntimeError("No fixed dice face remains for this roll")

        face = queued_faces.popleft()
        if face < low or face > high:
            raise ValueError(
                f"Fixed dice face {face} is outside the requested range {low}-{high}"
            )
        return face

    _randint = next_fixed_face
    try:
        yield
    finally:
        _randint = previous_randint


class AttackOutcome(str, Enum):
    HIT = "Hit"
    MISS = "Miss"
    CRIT = "Crit"
    CRIT_MISS = "Crit Miss"


class RollType(str, Enum):
    DAMAGE = "Damage"
    ATTACK = "Attack"
    SAVE = "Save"
    CHECK = "Check"
    HEAL = "Heal"


class DiceRoll(BaseModel):
    """Stores one concrete roll result and the modifier state used for it."""

    _registry: ClassVar[Dict[UUID, 'DiceRoll']] = {}

    roll_uuid: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this concrete roll result.",
    )
    dice_uuid: UUID = Field(
        ...,
        description="Unique identifier of the dice expression that produced this result.",
    )
    die_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of faces on each die, retained for portable roll analytics.",
    )
    effective_dice_count: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Number of selected dice contributing to the natural result. A d20 "
            "with advantage still contributes one selected die."
        ),
    )
    random_faces_rolled: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of random die faces generated, including advantage alternatives.",
    )
    roll_type: RollType = Field(
        ...,
        description="Rules category for the roll result.",
    )
    results: Union[List[int], int] = Field(
        ...,
        description=(
            "Recorded dice values: selected d20 for normal rolls, both d20s for "
            "advantage or disadvantage, or every die for damage and healing."
        ),
    )
    total: int = Field(
        ...,
        description="Final numeric roll total after adding the normalized bonus.",
    )
    bonus: int = Field(
        ...,
        description="Normalized modifier value applied to this roll.",
    )
    advantage_status: AdvantageStatus = Field(
        ...,
        description="Advantage state captured when the roll was created.",
    )
    critical_status: CriticalStatus = Field(
        ...,
        description="Critical state captured when the roll was created.",
    )
    auto_hit_status: AutoHitStatus = Field(
        ...,
        description="Automatic hit or miss state captured when the roll was created.",
    )
    source_entity_uuid: UUID = Field(
        ...,
        description="Entity that made the roll.",
    )
    target_entity_uuid: Optional[UUID] = Field(
        default=None,
        description="Target entity for contested or targeted rolls, when present.",
    )
    attack_outcome: Optional[AttackOutcome] = Field(
        default=None,
        description="Attack outcome associated with damage rolls, when applicable.",
    )

    def model_post_init(self, __context: Any) -> None:
        self.__class__._registry[self.roll_uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['DiceRoll']:
        """Return the registered roll result for a UUID.

        Args:
            uuid: Roll result UUID to look up.

        Returns:
            The matching roll result, or ``None`` when no result is registered.
        """
        return cls._registry.get(uuid)


class Dice(BaseModel):
    """Describes a dice expression and produces one cached ``DiceRoll``."""

    _registry: ClassVar[Dict[UUID, 'Dice']] = {}

    uuid: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this dice expression.",
    )
    count: int = Field(
        ...,
        description="Number of dice in the base expression.",
        ge=1,
    )
    value: Literal[4, 6, 8, 10, 12, 20] = Field(
        ...,
        description="Number of sides on each die.",
    )
    bonus: ModifiableValue = Field(
        ...,
        description="Modifiable value that supplies score, advantage, critical, and auto-hit state.",
    )
    roll_type: RollType = Field(
        default=RollType.ATTACK,
        description="Rules category for rolls produced by this dice expression.",
    )
    attack_outcome: Optional[AttackOutcome] = Field(
        default=None,
        description="Required attack outcome for damage rolls; absent for other roll types.",
    )
    crit_extra_dice: int = Field(
        default=0,
        description="Extra critical-hit dice added after doubling the base dice count.",
    )

    def model_post_init(self, __context: Any) -> None:
        self.__class__._registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['Dice']:
        """Return the registered dice expression for a UUID.

        Args:
            uuid: Dice expression UUID to look up.

        Returns:
            The matching dice expression, or ``None`` when no expression is registered.
        """
        return cls._registry.get(uuid)

    @model_validator(mode="after")
    def check_attack_outcome(self) -> Self:
        """Validate that only damage rolls carry an attack outcome.

        Returns:
            The validated dice expression.

        Raises:
            ValueError: If a damage roll omits an outcome or a non-damage roll
                provides one.
        """
        if self.roll_type == RollType.DAMAGE and self.attack_outcome is None:
            raise ValueError("Attack outcome must be provided for damage rolls")
        elif self.roll_type != RollType.DAMAGE and self.attack_outcome is not None:
            raise ValueError("Attack outcome must be None for non-damage rolls")
        return self

    @model_validator(mode="after")
    def check_num_dice(self) -> Self:
        """Validate that non-damage d20-style rolls use a single die.

        Returns:
            The validated dice expression.

        Raises:
            ValueError: If an attack, save, or check tries to roll more than one die.
        """
        if self.roll_type not in (RollType.DAMAGE, RollType.HEAL) and self.count > 1:
            raise ValueError("Cannot have more than one die for non-damage/heal rolls")
        return self

    @computed_field
    @property
    def source_entity_uuid(self) -> UUID:
        """Return the source entity from the dice bonus.

        Returns:
            Source entity UUID.
        """
        return self.bonus.source_entity_uuid

    @computed_field
    @property
    def target_entity_uuid(self) -> Optional[UUID]:
        """Return the target entity from the dice bonus when present.

        Returns:
            Target entity UUID, or ``None`` when the bonus has no target.
        """
        return self.bonus.target_entity_uuid

    def _roll_with_advantage(self) -> Tuple[int, List[int]]:
        """Roll two dice and select the higher result.

        Returns:
            Selected value and both raw rolls.
        """
        rolls = [_randint(1, self.value) for _ in range(2)]
        return max(rolls), rolls

    def _roll_with_disadvantage(self) -> Tuple[int, List[int]]:
        """Roll two dice and select the lower result.

        Returns:
            Selected value and both raw rolls.
        """
        rolls = [_randint(1, self.value) for _ in range(2)]
        return min(rolls), rolls

    def _roll(self, crit: bool = False) -> List[Tuple[int, List[int]]]:
        """Roll the configured dice with advantage and critical handling.

        Args:
            crit: Whether to double the base dice count and add critical extras.

        Returns:
            One tuple per effective die. The tuple contains the selected value
            and, for advantage or disadvantage, both raw rolls.
        """
        count = self.count if not crit else (self.count * 2 + self.crit_extra_dice)
        advantage_status = self.bonus.advantage
        if advantage_status == AdvantageStatus.ADVANTAGE:
            return [self._roll_with_advantage() for _ in range(count)]
        elif advantage_status == AdvantageStatus.DISADVANTAGE:
            return [self._roll_with_disadvantage() for _ in range(count)]
        else:
            return [(_randint(1, self.value), []) for _ in range(count)]

    @computed_field
    @cached_property
    def roll(self) -> DiceRoll:
        """Produce and cache the concrete roll result.

        Returns:
            The dice roll result. Re-reading this property returns the same
            object for the lifetime of this ``Dice`` instance.
        """
        effective_dice_count = self.count
        random_faces_rolled = self.count
        if self.roll_type in (RollType.DAMAGE, RollType.HEAL):
            effective_dice_count = (
                self.count * 2 + self.crit_extra_dice
                if self.attack_outcome == AttackOutcome.CRIT
                else self.count
            )
            random_faces_rolled = effective_dice_count
            results = [
                roll[0]
                for roll in self._roll(crit=(self.attack_outcome == AttackOutcome.CRIT))
            ]
            total = sum(results) + self.bonus.normalized_score
        else:
            roll_result = self._roll()[0]
            selected_value = roll_result[0]
            all_rolls = roll_result[1]
            results = all_rolls if all_rolls else [selected_value]
            total = selected_value + self.bonus.normalized_score
            effective_dice_count = 1
            random_faces_rolled = len(all_rolls) if all_rolls else 1

        return DiceRoll(
            dice_uuid=self.uuid,
            die_size=self.value,
            effective_dice_count=effective_dice_count,
            random_faces_rolled=random_faces_rolled,
            roll_type=self.roll_type,
            results=results,
            total=total,
            bonus=self.bonus.normalized_score,
            advantage_status=self.bonus.advantage,
            critical_status=self.bonus.critical,
            auto_hit_status=self.bonus.auto_hit,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            attack_outcome=self.attack_outcome,
        )
