"""Passive review catalog and saved-input schemas; no native scenario imports."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from dnd.core.equipment_types import WeaponSlot
from game.player_facts import PlayerLineage, PlayerState


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
    route: tuple[tuple[Literal["observer", "subject"], tuple[int, int]], ...] = (("subject", (8, 10)),)
    hidden_change_after: int | None = None
    dash_before: bool = False


class MovementCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["movement"]
    route: tuple[tuple[int, int], ...]
    battlefield_id: str = "battlefield.open_floor_bright"
    behavior: Literal["action.move", "action.jump"] = "action.move"
    boost: Literal["none", "haste", "bonus-dash"] = "none"


class ConcealmentCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["concealment"]
    program: Literal["invisibility", "sight-expiry", "doorway", "hide-bright", "hide-dim", "stacked"] = "invisibility"
    allied: bool = False
    sight_grant: Literal["none", "spell", "potion"] = "none"
    stealth_face: int = Field(default=18, ge=1, le=20)
    reveal: Literal["none", "drop-concentration", "attack", "cast"] = "drop-concentration"


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
                        | CreatureCase | EquipmentCase | DiscoveryCase | VisibilityCase | MovementCase | ForcedMovementCase | ConcealmentCase,
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
