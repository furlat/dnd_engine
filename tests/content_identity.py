"""Explicit primitive behavior facts for synthetic discovery rows."""


def synthetic_action_identity(
    content_id: str,
) -> dict[str, str | None]:
    """Return direct primitive fields for one synthetic action row."""
    return {
        "behavior_id": content_id,
        "provided_by_id": content_id,
        "origin_root_id": None,
    }


__all__ = ["synthetic_action_identity"]
