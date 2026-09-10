"""A finite catalog over existing public gameplay scenario producers."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from dnd.core.equipment_types import WeaponSlot
from game.combat_demo import iter_combat_demo
from game.presentation import CompletedLineage, PresentationTarget
from tests.game.scenarios import attack_history, movement_with_paralysis


class AttackCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["attack"]
    weapon: str = "weapon.longsword"
    seed: int = 17
    opportunity: bool = False
    destination: tuple[int, int] = (2, 3)
    maximum_hp: Literal[4, 80] = 80
    movement_behavior: Literal["action.move", "action.jump"] = "action.move"
    watcher_positions: tuple[tuple[int, int], ...] = ((4, 3),)
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN
    goblin_source: bool = False


class ParalysisCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["paralysis"]
    seed: int
    maximum_hp: Literal[4, 80] = 80
    movement_behavior: Literal["action.move", "action.jump"] = "action.move"


class CastCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["cast"]
    caster_position: tuple[int, int] = (16, 22)
    second_attack_seed: int = 0
    goblin_recipient: bool = False
    replace_weapon: bool = False
    magic_missile: bool = False


class ReviewCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str
    tags: tuple[str, ...]
    description: str
    scenario: Annotated[AttackCase | ParalysisCase | CastCase, Field(discriminator="kind")]
    pause_at_ms: float | None = Field(default=None, ge=0)
    pause_duration_ms: float = Field(default=750, gt=0)


@dataclass(frozen=True)
class ReviewSequence:
    before: PresentationTarget
    lineages: tuple[CompletedLineage, ...]


def load_cases(path: Path = Path(__file__).with_name("catalog.json")) -> tuple[ReviewCase, ...]:
    cases = TypeAdapter(tuple[ReviewCase, ...]).validate_json(path.read_text())
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("review case IDs must be unique")
    return cases


def produce(case: ReviewCase) -> ReviewSequence:
    """Run real rules once, then hand only retained values to the recorder."""
    match case.scenario:
        case AttackCase() as scenario:
            before, lineage = attack_history(
                scenario.weapon, scenario.seed, opportunity=scenario.opportunity,
                whole_movement=scenario.opportunity, destination=scenario.destination,
                maximum_hp=scenario.maximum_hp, movement_behavior=scenario.movement_behavior,
                watcher_positions=scenario.watcher_positions, weapon_slot=scenario.weapon_slot,
                goblin_source=scenario.goblin_source,
            )
            return ReviewSequence(before, (lineage,))
        case ParalysisCase() as scenario:
            before, lineage = movement_with_paralysis(
                scenario.seed, scenario.maximum_hp, movement_behavior=scenario.movement_behavior,
            )
            return ReviewSequence(before, (lineage,))
        case CastCase() as scenario:
            script = iter_combat_demo(
                caster_position=scenario.caster_position, second_attack_seed=scenario.second_attack_seed,
                goblin_recipient=scenario.goblin_recipient, replace_weapon=scenario.replace_weapon,
                magic_missile=scenario.magic_missile,
            )
            try:
                before = next(script)
                if not isinstance(before, PresentationTarget):
                    raise ValueError("scenario must begin with its retained baseline")
                roots = tuple(script)
                if not all(isinstance(root, CompletedLineage) for root in roots):
                    raise ValueError("scenario must yield complete lineages after its baseline")
                return ReviewSequence(before, tuple(root for root in roots if isinstance(root, CompletedLineage)))
            finally:
                script.close()
