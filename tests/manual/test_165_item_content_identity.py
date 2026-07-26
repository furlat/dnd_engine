"""Runtime items bind exact authored content identity without transport coupling."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.blocks.base_item import BaseItem
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.materialization import ItemBuildContext


def _ref(
    kind: ContentDefinitionKind = ContentDefinitionKind.ITEM,
) -> ContentRef:
    return ContentRef(
        pack_id="content.srd_5_1_cc",
        definition_kind=kind,
        content_id="item.club",
        content_version=1,
        definition_contract_hash="a" * 64,
    )


def test_content_ref_owns_semantic_identity_without_changing_runtime_dump() -> None:
    """A migrated item never falls back to its class path or stale legacy key."""
    source_uuid = uuid4()
    content_ref = _ref()
    item = BaseItem(
        source_entity_uuid=source_uuid,
        name="Club",
        semantic_key="legacy.club",
        content_ref=content_ref,
    )

    assert item.get_semantic_key() == content_ref.identity_key
    presentation = item.to_item_presentation_state()
    assert presentation.semantic_key == content_ref.identity_key
    assert presentation.content_ref is not None
    assert presentation.content_ref.model_dump(mode="json") == (
        content_ref.model_dump(mode="json")
    )
    assert "content_ref" not in item.model_dump()
    with pytest.raises(ValidationError):
        item.content_ref = content_ref.model_copy(
            update={"content_id": "item.dagger"},
        )

    legacy = BaseItem(
        source_entity_uuid=source_uuid,
        semantic_key="legacy.club",
    )
    assert legacy.get_semantic_key() == "legacy.club"
    assert legacy.to_item_presentation_state().content_ref is None


def test_item_build_context_accepts_only_item_owned_definition_families() -> None:
    """Creature/action references cannot accidentally enter an item factory."""
    source_uuid = uuid4()
    context = ItemBuildContext(
        source_entity_uuid=source_uuid,
        requested_ref=_ref(),
    )
    assert context.source_entity_uuid == source_uuid
    assert context.requested_ref == _ref()

    ItemBuildContext(
        source_entity_uuid=source_uuid,
        requested_ref=_ref(ContentDefinitionKind.ENVIRONMENT_OBJECT),
    )
    with pytest.raises(ValidationError, match="item or environment_object"):
        ItemBuildContext(
            source_entity_uuid=source_uuid,
            requested_ref=_ref(ContentDefinitionKind.CREATURE),
        )
