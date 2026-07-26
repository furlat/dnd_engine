"""Explicit authored identity fixtures for synthetic transport rows."""

from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.runtime import AuthoredBehaviorAttribution


def synthetic_action_attribution(
    content_id: str,
) -> AuthoredBehaviorAttribution:
    """Return one exact test-pack action attribution for a synthetic row."""
    ref = ContentRef(
        pack_id="tests.synthetic",
        definition_kind=ContentDefinitionKind.ACTION,
        content_id=content_id,
        content_version=1,
        definition_contract_hash="f" * 64,
    )
    return AuthoredBehaviorAttribution(
        definition_ref=ref,
        provided_by_ref=ref,
    )


__all__ = ["synthetic_action_attribution"]
