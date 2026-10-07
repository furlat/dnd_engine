"""Local native-process envelopes around the existing public player values.

No live events, executable templates or registry objects cross this boundary.
The request identity also identifies an asynchronous preview's exact prefix.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from player_server.framing import MAX_PACKET_BYTES as MAX_PACKET_BYTES, read_packet as read_packet, write_packet as write_packet

from dnd.content.characters.build_types import CharacterBuild
from dnd.core.base_actions import AvailableActionsResult, AvailableSelectionPreview
from dnd.player.commands import ActionSelection, EquipItem, UnequipItem, ToggleHandler
from dnd.player.facts import CombatLogAppend, PlayerHUDSnapshot, PlayerInitialization, PlayerLineage
from dnd.player.content import UIContentManifest
from dnd.core.content.descriptors import ContentDescriptor


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
    content_additions: tuple[ContentDescriptor, ...] = ()
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
