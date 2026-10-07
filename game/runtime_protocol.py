"""Local native-process envelopes around the existing public player values.

No live events, executable templates or registry objects cross this boundary.
The request identity also identifies an asynchronous preview's exact prefix.
"""

from typing import Annotated, IO, Literal
from uuid import UUID
import struct

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from dnd.content.characters.build_types import CharacterBuild
from dnd.core.base_actions import AvailableActionsResult, AvailableSelectionPreview
from game.player_commands import ActionSelection, EquipItem, UnequipItem, ToggleHandler
from game.player_facts import CombatLogAppend, PlayerHUDSnapshot, PlayerInitialization, PlayerLineage
from game.ui.content_types import UIContentManifest


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: int = Field(ge=0)


class StartRequest(Request):
    kind: Literal["start"] = "start"
    encounter_id: str | None = None
    player_positions: tuple[tuple[int, int], tuple[int, int]] = ((10, 10), (10, 12))
    enemy_positions: tuple[tuple[int, int], tuple[int, int]] = ((14, 10), (14, 12))
    player_builds: tuple[CharacterBuild, ...] | None = None
    test_seed: int | None = None


class SessionRequest(Request):
    generation: UUID


class AdvanceRequest(SessionRequest):
    kind: Literal["advance"] = "advance"


class DiscoverRequest(SessionRequest):
    kind: Literal["discover"] = "discover"
    actor_uuid: UUID
    force_attack: bool = False


class ChoiceRequest(SessionRequest):
    actor_uuid: UUID
    discovery_generation: int = Field(ge=1)


class PreviewRequest(ChoiceRequest):
    kind: Literal["preview"] = "preview"
    selection: ActionSelection


class ActionRequest(ChoiceRequest):
    kind: Literal["action"] = "action"
    selection: ActionSelection


class EndTurnRequest(ChoiceRequest):
    kind: Literal["end_turn"] = "end_turn"


class EquipRequest(ChoiceRequest):
    kind: Literal["equip"] = "equip"
    command: EquipItem


class UnequipRequest(ChoiceRequest):
    kind: Literal["unequip"] = "unequip"
    command: UnequipItem


class HandlerRequest(ChoiceRequest):
    kind: Literal["handler"] = "handler"
    command: ToggleHandler


class CloseRequest(SessionRequest):
    kind: Literal["close"] = "close"


RuntimeRequest = Annotated[
    StartRequest | AdvanceRequest | DiscoverRequest | PreviewRequest | ActionRequest
    | EndTurnRequest | EquipRequest | UnequipRequest | HandlerRequest | CloseRequest,
    Field(discriminator="kind"),
]


class Reply(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: int
    elapsed_ms: float = 0


class StartedReply(Reply):
    kind: Literal["started"] = "started"
    initialization: PlayerInitialization
    encounter_name: str
    ui_content: UIContentManifest


class OperationReply(Reply):
    kind: Literal["operation"] = "operation"
    generation: UUID
    start_cursor: int
    end_cursor: int
    lineages: tuple[PlayerLineage, ...]
    hud: PlayerHUDSnapshot | None
    combat_log_appends: tuple[CombatLogAppend, ...]
    boundary_status: str | None = None
    gaps: tuple[tuple[UUID, str], ...] = ()


class DiscoveryReply(Reply):
    kind: Literal["discovery"] = "discovery"
    generation: UUID
    choices: AvailableActionsResult
    force_attack: bool


class PreviewReply(Reply):
    kind: Literal["preview"] = "preview"
    generation: UUID
    preview: AvailableSelectionPreview


class RejectedReply(Reply):
    kind: Literal["rejected"] = "rejected"
    message: str


class ClosedReply(Reply):
    kind: Literal["closed"] = "closed"


RuntimeReply = Annotated[
    StartedReply | OperationReply | DiscoveryReply | PreviewReply | RejectedReply | ClosedReply,
    Field(discriminator="kind"),
]

REQUEST_CODEC: TypeAdapter[RuntimeRequest] = TypeAdapter(RuntimeRequest)
REPLY_CODEC: TypeAdapter[RuntimeReply] = TypeAdapter(RuntimeReply)
MAX_PACKET_BYTES = 64 * 1024 * 1024


def read_packet(stream: IO[bytes]) -> bytes | None:
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise EOFError("Truncated native reply header")
    size, = struct.unpack("!I", header)
    if size > MAX_PACKET_BYTES:
        raise ValueError("Native packet exceeds the bounded transport size")
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError("Truncated native packet")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def write_packet(stream: IO[bytes], payload: bytes) -> None:
    if len(payload) > MAX_PACKET_BYTES:
        raise ValueError("Native packet exceeds the bounded transport size")
    stream.write(struct.pack("!I", len(payload)))
    stream.write(payload)
    stream.flush()
