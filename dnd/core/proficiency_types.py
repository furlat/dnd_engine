"""Dependency-neutral proficiency grants used by character progression."""

from enum import Enum
from typing import Callable, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class ProficiencyMode(str, Enum):
    """Closed proficiency contribution modes.

    Contributions never add together.  The strongest applicable result wins,
    which matches the rules distinction between half proficiency, ordinary
    proficiency, and expertise.
    """

    HALF_ROUND_DOWN = "half_round_down"
    HALF_ROUND_UP = "half_round_up"
    FULL = "full"
    EXPERTISE = "expertise"


class ProficiencySourceSet(BaseModel):
    """Exact source-owned proficiency contributions."""

    sources: Dict[UUID, ProficiencyMode] = Field(
        default_factory=dict,
        description="Proficiency contribution keyed by the owning grant UUID.",
    )

    def add(self, source_id: UUID, mode: ProficiencyMode) -> None:
        """Add one source, rejecting an identity reused with different rules."""
        existing = self.sources.get(source_id)
        if existing is not None and existing != mode:
            raise ValueError(
                f"proficiency source {source_id} already exists as {existing.value}"
            )
        self.sources[source_id] = mode

    def remove(self, source_id: UUID) -> bool:
        """Remove exactly one source and report whether it existed."""
        return self.sources.pop(source_id, None) is not None

    def has_mode(self, mode: ProficiencyMode) -> bool:
        """Return whether an exact source owns the requested mode."""
        return mode in self.sources.values()

    @property
    def is_proficient(self) -> bool:
        """Return whether at least one source grants full proficiency."""
        return self.has_mode(ProficiencyMode.FULL)

    @property
    def has_expertise(self) -> bool:
        """Return whether full proficiency and expertise are both owned."""
        return (
            self.is_proficient
            and self.has_mode(ProficiencyMode.EXPERTISE)
        )

    def apply(self, proficiency_bonus: int) -> int:
        """Return the strongest contribution for a proficiency bonus."""
        has_full = self.is_proficient
        candidates = [0]
        for mode in self.sources.values():
            if mode == ProficiencyMode.HALF_ROUND_DOWN:
                candidates.append(proficiency_bonus // 2)
            elif mode == ProficiencyMode.HALF_ROUND_UP:
                candidates.append((proficiency_bonus + 1) // 2)
            elif mode == ProficiencyMode.FULL:
                candidates.append(proficiency_bonus)
            elif mode == ProficiencyMode.EXPERTISE and has_full:
                candidates.append(2 * proficiency_bonus)
        return max(candidates)

    def converter(self) -> Callable[[int], int]:
        """Return the converter shape consumed by existing roll pipelines."""
        return self.apply
