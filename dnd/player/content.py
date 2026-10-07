"""Passive content identities passed to the UI asset validator."""

from pydantic import BaseModel, ConfigDict

from dnd.core.content.descriptors import ContentDescriptor
from dnd.core.content.identities import ContentRef


class UIContentManifest(BaseModel):
    """Passive native catalog identities used to validate local UI artwork."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    content: tuple[tuple[ContentRef, ContentDescriptor], ...]
    feature_ids: frozenset[str]
    item_ids: frozenset[str]

