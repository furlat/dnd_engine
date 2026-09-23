"""Authored condition attachments; native membership owns their lifetime."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping
from uuid import UUID

from game.asset_types import AssetSpec, image_resources
from game.condition_types import ConditionLayer


ACTIVITIES = frozenset(("idle", "move", "jump", "forced_move", "attack", "cast", "act", "hit"))


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
    document = json.loads(path.read_text())
    rows = json.loads(resources_path.read_text())["resources"]
    selected = {asset for layer in document["layers"].values() for asset in layer.get("images_by_facing", {}).values()}
    resources = image_resources({identity: rows[identity] for identity in selected}, root)
    return MappingProxyType({identity: ConditionLayerMedia(row["category"], row["animation"],
        MappingProxyType({facing: resources[asset] for facing, asset in row.get("images_by_facing", {}).items()}),
        row.get("asset_id"), row.get("application_asset_id"), tuple(row.get("application_fade_ms", (1500, 2000))),
        row.get("removal_fade_ms", 0), row.get("scale", .5), row.get("world_basis"),
        row.get("application_mode", "crossfade"), row.get("removal_mask_asset_id"), row.get("sustain_start_ms", 0))
        for identity, row in document["layers"].items()})


def supported_layer(layer: ConditionLayer, media: Mapping[str, ConditionLayerMedia]) -> bool:
    """Static images and paged neutral-color media share the authored selectors."""
    asset = media.get(layer.assetId)
    return (asset is not None and layer.attachment in ("body", "ground", "head", "face")
        and frozenset(layer.activeDuring) <= ACTIVITIES
        and (asset.category, asset.animation) == (layer.category, layer.animation)
        and layer.colors.primary == layer.colors.secondary == layer.colors.tertiary == 0xFFFFFF)
