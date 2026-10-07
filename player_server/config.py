"""Private launch configuration, never a player-facing discovery endpoint."""
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, model_validator
from dnd.core.content.encounters import EncounterRecipe
from dnd.player.audience import SeatAssignment


class SeatCredential(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    seat_id: str = Field(min_length=1)
    token: str = Field(min_length=24)


class ServiceLimits(BaseModel):
    """Operator resource budgets, independent of seat/entity assignment."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    max_workers: int = Field(default=4, ge=1)
    idle_workers: int = Field(default=2, ge=0)
    max_games: int = Field(default=64, ge=1)
    recording_budget_bytes: int = Field(default=64 * 1024 ** 3, ge=64 * 1024 ** 2)


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    game_id: str = 'encounter'
    encounter_id: str | None = 'encounter.lantern_crypt'
    recipe: EncounterRecipe | None = None
    assignments: tuple[SeatAssignment, ...] | None = None
    credentials: tuple[SeatCredential, ...]
    spool_directory: Path = Path('.runtime/player-server')
    allowed_origins: tuple[str, ...] = ()
    spool_limit_bytes: int = Field(default=1024 ** 3, ge=64 * 1024 ** 2)
    worker_timeout_seconds: float = Field(default=120, gt=0)
    test_seed: int | None = None  # private launch/test composition only

    @model_validator(mode='after')
    def distinct_credentials(self) -> 'ServerConfig':
        if (not self.credentials or len({row.seat_id for row in self.credentials}) != len(self.credentials)
                or len({row.token for row in self.credentials}) != len(self.credentials)):
            raise ValueError('Each seat needs a distinct credential')
        return self
