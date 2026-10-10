"""Passive UI authoring values shared by desktop and browser export."""

from pydantic import BaseModel, ConfigDict, NonNegativeInt, model_validator

from dnd.core.content.descriptors import ContentPresentation
from dnd.core.content.identities import ContentRef


class PresentationRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    label: str
    presentation: ContentPresentation
    approximation: str | None = None


class UIPresentationDocument(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    direct_features: dict[str, PresentationRecord]
    direct_items: dict[str, PresentationRecord]
    portrait_choices: dict[str, PresentationRecord]
    common: dict[str, PresentationRecord]


class ChoiceRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    owner: ContentRef
    # A discovery facet or a native configuration field selects this artwork.
    # Existing Pygame records use facets only; field-only choices have no facet.
    facet: str | None
    value: str | int
    icon_key: str
    label: str
    # Facet records name prerequisite facets; field-only records name fields.
    requirements: dict[str, str | int]
    field: str | None = None
    # Usually identical to value. Spirit Guardians' native enum uses uppercase
    # values while its discovery facet uses lowercase values.
    field_value: str | int | None = None

    @model_validator(mode='after')
    def selection_address(self) -> 'ChoiceRecord':
        if self.facet is None and self.field is None:
            raise ValueError('UI choice requires a facet or configuration field')
        if self.field_value is not None and self.field is None:
            raise ValueError('UI choice field_value requires a configuration field')
        return self


class SkinSource(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    resource_id: str
    inset: tuple[NonNegativeInt, NonNegativeInt, NonNegativeInt, NonNegativeInt]


# Existing system-font choices; no private font files are installed by this UI.
UI_FONT_FAMILIES = {
    'body': ('DejaVu Sans', 'Segoe UI', 'Arial'),
    'mono': ('Consolas', 'DejaVu Sans Mono'),
}
