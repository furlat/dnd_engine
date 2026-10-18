"""Exact authored identity on player action and reaction affordances."""

from __future__ import annotations

from uuid import uuid4

import pytest

from dnd.core.base_actions import (
    ActionAvailabilityStatus,
    AvailableTarget,
    BaseAction,
    TargetType,
)
from dnd.entity import Entity


def test_action_discovery_rejects_an_unbound_execution_template() -> None:
    """A custom action cannot leak through names when it has no exact binding."""
    entity = Entity.create(source_entity_uuid=uuid4(), name="Identity Probe")
    action = BaseAction(
        name="Unbound Custom Action",
        source_entity_uuid=entity.uuid,
        target_type=TargetType.SELF,
        use_register=False,
    )

    with pytest.raises(ValueError, match="authored behavior binding"):
        entity._make_action_info(
            template_name="Unbound Custom Action",
            target_type=TargetType.SELF,
            valid_targets=[AvailableTarget(index=0)],
            can_afford=True,
            availability_status=ActionAvailabilityStatus.AVAILABLE,
            template=action,
        )
