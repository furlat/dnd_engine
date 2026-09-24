"""Authored condition attachments; native membership owns their lifetime."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, model_validator

from game.asset_types import AssetSpec, image_resources
from game.condition_types import ConditionLayer


ACTIVITIES = frozenset(("idle", "move", "jump", "forced_move", "attack", "cast", "act", "hit"))


class ConditionMediaSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    category: str
    animation: str
    images_by_facing: dict[Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"], str] = Field(default_factory=dict)
    asset_id: str | None = None
    application_asset_id: str | None = None
    application_fade_ms: tuple[NonNegativeFloat, NonNegativeFloat] = (1500, 2000)
    removal_fade_ms: NonNegativeFloat = 0
    scale: PositiveFloat = .5
    world_basis: Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"] | None = None
    application_mode: Literal["crossfade", "sequence"] = "crossfade"
    removal_mask_asset_id: str | None = None
    sustain_start_ms: NonNegativeFloat = 0

    @model_validator(mode="after")
    def ordered_fade(self) -> "ConditionMediaSource":
        if self.application_fade_ms[1] < self.application_fade_ms[0]:
            raise ValueError("application fade end must follow its start")
        return self


class ConditionMediaDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_name: Literal["dnd.conditionLayerMedia"] = Field(alias="schema")
    version: Literal[1]
    layers: dict[str, ConditionMediaSource]


@dataclass(frozen=True, slots=True)
class ConditionLayerMedia:
    category: str
    animation: str
    images_by_facing: Mapping[str, AssetSpec] = field(default_factory=lambda: MappingProxyType({}))
    asset_id: str | None = None
    application_asset_id: str | None = None
    application_fade_ms: tuple[float, float] = (1500, 2000)
    removal_fade_ms: float = 0
    scale: float = .5
    # Orbit exports keep a fixed world basis, independent of the wearer's facing.
    world_basis: str | None = None
    application_mode: Literal["crossfade", "sequence"] = "crossfade"
    removal_mask_asset_id: str | None = None
    # Local loop origin when application and hold overlap. Reacquired owners
    # have no witnessed application and enter the ordinary quiet-loop clock.
    sustain_start_ms: float = 0


@dataclass(frozen=True, slots=True)
class ResolvedConditionLayer:
    layer: ConditionLayer
    media: ConditionLayerMedia
    owner_uuid: UUID | None = None
    age_ms: float = 0
    application: bool = False
    alpha: float = 1
    finite: bool = False
    fade_in_age_ms: float | None = None
    removal_age_ms: float | None = None


def load_condition_media(path: Path, resources_path: Path, root: Path) -> Mapping[str, ConditionLayerMedia]:
    document = ConditionMediaDocument.model_validate_json(path.read_text())
    rows = json.loads(resources_path.read_text())["resources"]
    selected = {asset for layer in document.layers.values() for asset in layer.images_by_facing.values()}
    resources = image_resources({identity: rows[identity] for identity in selected}, root)
    return MappingProxyType({identity: ConditionLayerMedia(row.category, row.animation,
        MappingProxyType({facing: resources[asset] for facing, asset in row.images_by_facing.items()}),
        row.asset_id, row.application_asset_id, row.application_fade_ms,
        row.removal_fade_ms, row.scale, row.world_basis, row.application_mode,
        row.removal_mask_asset_id, row.sustain_start_ms)
        for identity, row in document.layers.items()})


def supported_layer(layer: ConditionLayer, media: Mapping[str, ConditionLayerMedia]) -> bool:
    """Static images and paged neutral-color media share the authored selectors."""
    asset = media.get(layer.assetId)
    return (asset is not None and layer.attachment in ("body", "ground", "head", "face")
        and frozenset(layer.activeDuring) <= ACTIVITIES
        and (asset.category, asset.animation) == (layer.category, layer.animation)
        and layer.colors.primary == layer.colors.secondary == layer.colors.tertiary == 0xFFFFFF)
