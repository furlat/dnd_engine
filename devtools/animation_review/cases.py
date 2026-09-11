"""A finite catalog over existing public gameplay scenario producers."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from dnd.core.equipment_types import WeaponSlot
from game.combat_demo import capture_combat_demo
from game.replay import CapturedHistory
from game.player_facts import PlayerLineage, PlayerState
from tests.game.creature_scenarios import creature_history
from tests.game.discovery_scenarios import discovery_history
from tests.game.equipment_scenarios import equipment_sequence_history
from tests.game.forced_movement_scenarios import forced_movement_history
from tests.game.movement_scenarios import movement_history
from tests.game.visibility_scenarios import VisibilityRole, visibility_history
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
    replacement: Literal["weapon", "wardrobe", "remove-weapon"] = "weapon"
    attacks: bool = True


class DiscoveryCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["discovery"]
    mode: Literal["enter_view", "deploy_later"] = "enter_view"


class VisibilityCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["visibility"]
    battlefield_id: str = "battlefield.visibility_doorway_open"
    observer_position: tuple[int, int] = (5, 7)
    subject_position: tuple[int, int] = (8, 4)
    route: tuple[tuple[VisibilityRole, tuple[int, int]], ...] = (("subject", (8, 10)),)
    hidden_change_after: int | None = None
    dash_before: bool = False


class MovementCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["movement"]
    route: tuple[tuple[int, int], ...]
    battlefield_id: str = "battlefield.open_floor_bright"
    behavior: Literal["action.move", "action.jump"] = "action.move"
    boost: Literal["none", "haste", "bonus-dash"] = "none"


class ForcedMovementCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["forced-movement"]
    source_position: tuple[int, int] = (3, 3)
    target_position: tuple[int, int] = (4, 3)
    battlefield_id: str = "battlefield.open_floor_bright"
    seed: int = 0
    blocker_position: tuple[int, int] | None = None
    watcher_position: tuple[int, int] | None = None
    target_identity: str | None = None
    target_hp: Literal[4, 40] = 40
    mechanism: Literal["shove", "telekinesis"] = "shove"
    destination: tuple[int, int] | None = None


class ReviewCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str
    tags: tuple[str, ...]
    description: str
    scenario: Annotated[AttackCase | ParalysisCase | CastCase | ParalysisLifecycleCase | DodgeExpiryCase | HealingCase | LifecycleCase
                        | CreatureCase | EquipmentCase | DiscoveryCase | VisibilityCase | MovementCase | ForcedMovementCase,
                        Field(discriminator="kind")]
    pause_at_ms: float | None = Field(default=None, ge=0)
    pause_duration_ms: float = Field(default=750, gt=0)


@dataclass(frozen=True)
class ReviewSequence:
    before: PlayerState
    lineages: tuple[PlayerLineage, ...]


class ReviewPerspective(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    experiment_id: str
    role: str
    observer_uuid: UUID
    generation: UUID
    start_cursor: int
    end_cursor: int


class RecordedInput(BaseModel):
    """Saved gameplay input plus its capture provenance and review settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    kind: Literal["dnd-animation-input"] = "dnd-animation-input"
    case: ReviewCase
    captured_at: str
    sources: dict[str, JsonValue]
    sequence: JsonValue
    sequence_format: Literal["native-v2", "player-v1"] = "native-v2"
    perspective: ReviewPerspective | None = None


def load_cases(path: Path = Path(__file__).with_name("catalog.json")) -> tuple[ReviewCase, ...]:
    cases = TypeAdapter(tuple[ReviewCase, ...]).validate_json(path.read_text())
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("review case IDs must be unique")
    return cases


def produce(case: ReviewCase) -> CapturedHistory:
    """Run real rules once, then hand only retained values to the recorder."""
    match case.scenario:
        case ForcedMovementCase() as scenario:
            return forced_movement_history(
                source_position=scenario.source_position, target_position=scenario.target_position,
                battlefield_id=scenario.battlefield_id, seed=scenario.seed,
                blocker_position=scenario.blocker_position, watcher_position=scenario.watcher_position,
                target_identity=scenario.target_identity, target_hp=scenario.target_hp,
                mechanism=scenario.mechanism, destination=scenario.destination,
            )
        case CreatureCase() as scenario:
            return creature_history(scenario.creature_identity, weapon_slot=scenario.weapon_slot,
                                                seed=scenario.seed)
        case EquipmentCase() as scenario:
            return equipment_sequence_history(replacement=scenario.replacement, attacks=scenario.attacks)
        case DiscoveryCase() as scenario:
            return discovery_history(mode=scenario.mode)
        case VisibilityCase() as scenario:
            return visibility_history(battlefield_id=scenario.battlefield_id,
                observer_position=scenario.observer_position, subject_position=scenario.subject_position,
                route=scenario.route, hidden_change_after=scenario.hidden_change_after, dash_before=scenario.dash_before)
        case MovementCase() as scenario:
            return movement_history(route=scenario.route, battlefield_id=scenario.battlefield_id,
                                                behavior=scenario.behavior, boost=scenario.boost)
        case AttackCase() as scenario:
            return attack_history(
                scenario.weapon, scenario.seed, opportunity=scenario.opportunity,
                whole_movement=scenario.opportunity, destination=scenario.destination,
                maximum_hp=scenario.maximum_hp, movement_behavior=scenario.movement_behavior,
                watcher_positions=scenario.watcher_positions, weapon_slot=scenario.weapon_slot,
                goblin_source=scenario.goblin_source, uses_death_saves=scenario.uses_death_saves,
            )
        case ParalysisCase() as scenario:
            return movement_with_paralysis(
                scenario.seed, scenario.maximum_hp, movement_behavior=scenario.movement_behavior,
            )
        case ParalysisLifecycleCase() as scenario:
            return paralysis_lifecycle(
                repeat_save_seeds=scenario.repeat_save_seeds,
                movement_behavior=scenario.movement_behavior, resume=scenario.resume,
            )
        case DodgeExpiryCase():
            return dodge_expiry_history()
        case HealingCase() as scenario:
            return healing_history(dying=scenario.dying)
        case LifecycleCase() as scenario:
            return lifecycle_history(save_seeds=scenario.save_seeds,
                heal_after=scenario.heal_after, revive_after=scenario.revive_after)
        case CastCase() as scenario:
            return capture_combat_demo(
                caster_position=scenario.caster_position, second_attack_seed=scenario.second_attack_seed,
                goblin_recipient=scenario.goblin_recipient, replace_weapon=scenario.replace_weapon,
                magic_missile=scenario.magic_missile,
            )
