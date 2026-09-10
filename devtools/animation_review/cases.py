"""A finite catalog over existing public gameplay scenario producers."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from dnd.core.equipment_types import WeaponSlot
from game.combat_demo import iter_combat_demo
from game.presentation import CompletedLineage, PresentationTarget
from tests.game.creature_scenarios import creature_history
from tests.game.equipment_scenarios import equipment_sequence_history
from tests.game.movement_scenarios import movement_history
from tests.game.scenarios import (
    attack_history, dodge_expiry_history, healing_history, lifecycle_history, movement_with_paralysis, paralysis_lifecycle,
)


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
    uses_death_saves: bool = False


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


class ParalysisLifecycleCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["paralysis-lifecycle"]
    repeat_save_seeds: tuple[int, ...] = (0,)
    movement_behavior: Literal["action.move", "action.jump"] = "action.move"
    resume: bool = True


class DodgeExpiryCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["dodge-expiry"]


class HealingCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["healing"]
    dying: bool = False


class LifecycleCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["lifecycle"]
    save_seeds: tuple[int, ...] = (0,)
    heal_after: bool = False
    revive_after: bool = False


class CreatureCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["creature"]
    creature_identity: str
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN
    seed: int = 17


class EquipmentCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["equipment"]
    replacement: Literal["weapon", "wardrobe"] = "weapon"
    attacks: bool = True


class MovementCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["movement"]
    route: tuple[tuple[int, int], ...]
    battlefield_id: str = "battlefield.open_floor_bright"
    behavior: Literal["action.move", "action.jump"] = "action.move"
    boost: Literal["none", "haste", "bonus-dash"] = "none"


class ReviewCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str
    tags: tuple[str, ...]
    description: str
    scenario: Annotated[AttackCase | ParalysisCase | CastCase | ParalysisLifecycleCase | DodgeExpiryCase | HealingCase | LifecycleCase
                        | CreatureCase | EquipmentCase | MovementCase,
                        Field(discriminator="kind")]
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
        case CreatureCase() as scenario:
            before, lineages = creature_history(scenario.creature_identity, weapon_slot=scenario.weapon_slot,
                                                seed=scenario.seed)
            return ReviewSequence(before, lineages)
        case EquipmentCase() as scenario:
            before, lineages = equipment_sequence_history(replacement=scenario.replacement, attacks=scenario.attacks)
            return ReviewSequence(before, lineages)
        case MovementCase() as scenario:
            before, lineages = movement_history(route=scenario.route, battlefield_id=scenario.battlefield_id,
                                                behavior=scenario.behavior, boost=scenario.boost)
            return ReviewSequence(before, lineages)
        case AttackCase() as scenario:
            before, lineage = attack_history(
                scenario.weapon, scenario.seed, opportunity=scenario.opportunity,
                whole_movement=scenario.opportunity, destination=scenario.destination,
                maximum_hp=scenario.maximum_hp, movement_behavior=scenario.movement_behavior,
                watcher_positions=scenario.watcher_positions, weapon_slot=scenario.weapon_slot,
                goblin_source=scenario.goblin_source, uses_death_saves=scenario.uses_death_saves,
            )
            return ReviewSequence(before, (lineage,))
        case ParalysisCase() as scenario:
            before, lineage = movement_with_paralysis(
                scenario.seed, scenario.maximum_hp, movement_behavior=scenario.movement_behavior,
            )
            return ReviewSequence(before, (lineage,))
        case ParalysisLifecycleCase() as scenario:
            before, lineages = paralysis_lifecycle(
                repeat_save_seeds=scenario.repeat_save_seeds,
                movement_behavior=scenario.movement_behavior, resume=scenario.resume,
            )
            return ReviewSequence(before, lineages)
        case DodgeExpiryCase():
            before, lineages = dodge_expiry_history()
            return ReviewSequence(before, lineages)
        case HealingCase() as scenario:
            before, lineage = healing_history(dying=scenario.dying)
            return ReviewSequence(before, (lineage,))
        case LifecycleCase() as scenario:
            before, lineages = lifecycle_history(save_seeds=scenario.save_seeds,
                heal_after=scenario.heal_after, revive_after=scenario.revive_after)
            return ReviewSequence(before, lineages)
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
