"""Private process control and metadata; encoded public records follow as frames."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from dnd.core.content.encounters import EncounterRecipe
from dnd.player.audience import PlayerAudience, SeatAssignment
from server.protocol import BoundaryState, ChoicesRequest, CommandRequest, PlayerCursor, PreviewRequest, RejectionReason


class Start(BaseModel):
    kind: Literal['start'] = 'start'
    game_id: str
    game_epoch: UUID
    audience_ids: dict[str, UUID]
    encounter_id: str | None
    recipe: EncounterRecipe | None
    assignments: tuple[SeatAssignment, ...] | None
    test_seed: int | None


class Advance(BaseModel):
    kind: Literal['advance'] = 'advance'


class Choices(BaseModel):
    kind: Literal['choices'] = 'choices'
    seat_id: str
    request: ChoicesRequest


class Preview(BaseModel):
    kind: Literal['preview'] = 'preview'
    seat_id: str
    request: PreviewRequest


class Command(BaseModel):
    kind: Literal['command'] = 'command'
    seat_id: str
    request: CommandRequest


class Close(BaseModel):
    kind: Literal['close'] = 'close'


class EndGame(BaseModel):
    kind: Literal['end_game'] = 'end_game'
    game_epoch: UUID


Request = Annotated[Start | Advance | Choices | Preview | Command | EndGame | Close, Field(discriminator='kind')]
REQUEST_CODEC: TypeAdapter[Request] = TypeAdapter(Request)


class Publication(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    seat_id: str
    cursor: PlayerCursor
    state_revision: str
    boundary: BoundaryState
    audience: PlayerAudience
    content_revision: str


class Reply(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    publications: tuple[Publication, ...] = ()
    has_response: bool = False
    rejection: RejectionReason | None = None
    query_error: Literal["response_too_large"] | None = None
    encounter_name: str | None = None
    needs_advance: bool = False
    elapsed_ms: float = 0
    ended_epoch: UUID | None = None
