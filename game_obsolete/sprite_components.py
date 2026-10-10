"""Authored source-pixel roles, independent of rig actions and material effects.

Keys in the catalog are resolved image URLs, so semantic clip aliases share the
same classification and library sheets need no invented creature or action binding.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from game.asset_types import ImageRegionSource, SourceRGBABounds


ComponentRole = Literal['body', 'shadow', 'accent']


class WholeSheetComponent(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['whole'] = 'whole'
    role: ComponentRole


class SourceRGBARule(SourceRGBABounds):
    """Inclusive straight source RGBA bytes, before filtering/tint/lighting."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    role: ComponentRole


class RGBASheetComponents(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['source_rgba'] = 'source_rgba'
    # First match wins. Alpha-zero samples are empty regardless of these rules.
    rules: Annotated[tuple[SourceRGBARule, ...], Field(min_length=1)]
    remainder: ComponentRole = 'body'


class MaskedSheetComponents(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['mask'] = 'mask'
    # One lossless label byte: 0 empty, 1 body, 2 shadow, 3 accent. Never interpolate.
    mask: ImageRegionSource


class SelectedAccentMaterial(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['selection'] = 'selection'


class MaskedAccentMaterial(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['image'] = 'image'
    # L8 material influence (0..255), not exclusive component labels/depth.
    mask: ImageRegionSource


class SourceInteractionComposition(BaseModel):
    """Original C/B/S/E sources with explicitly controlled overlap treatment."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['source_interaction'] = 'source_interaction'
    has_accent: bool


class SheetComponents(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    selection: Annotated[
        WholeSheetComponent | RGBASheetComponents | MaskedSheetComponents,
        Field(discriminator='kind'),
    ] | None = None
    composition: SourceInteractionComposition | None = None
    # Available independent source layers, not new draw/animation instructions.
    source_layers: dict[ComponentRole, str] = Field(default_factory=dict)
    # Apply the existing palette treatment to original RGB through this mask.
    # Original alpha/occlusion remain untouched; this can overlap body samples.
    accent_material_mask: Annotated[
        SelectedAccentMaterial | MaskedAccentMaterial, Field(discriminator='kind'),
    ] | None = None
    # Partitioning a flattened image does not recover effects hidden/blended
    # into body colour. Consumers must not promise independently switchable layers.
    limitations: tuple[Literal[
        'visible_partition_only', 'source_body_pose_mismatch', 'accent_body_overlap',
    ], ...] = ()

    @model_validator(mode='after')
    def component_method(self):
        if (self.selection is None) == (self.composition is None):
            raise ValueError('Choose source selection or source interaction composition')
        if self.composition is not None:
            required = {'body', 'shadow'}
            if self.composition.has_accent:
                required.add('accent')
            if not required <= self.source_layers.keys():
                raise ValueError('Source interaction composition requires registered component sources')
        return self
