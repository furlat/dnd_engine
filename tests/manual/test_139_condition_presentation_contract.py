"""Focused contract tests for authoritative public condition presentation."""

import pytest

from devtools.generate_event_contract import import_dnd_modules
from dnd.conditions import ConcentrationActionMarker
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionCategory
from dnd.items.consumables import _WeaponCoatCondition
from dnd.monsters.traits import SimpleMarkerCondition


@pytest.mark.parametrize(
    "condition_type",
    (
        SimpleMarkerCondition,
        ConcentrationActionMarker,
        _WeaponCoatCondition,
    ),
)
def test_tracking_only_conditions_are_internal(
    condition_type: type[BaseCondition],
) -> None:
    """Lifecycle and already-triggered markers cannot become public tooltips."""
    category = condition_type.model_fields["condition_category"].get_default(
        call_default_factory=True,
    )
    assert category is ConditionCategory.INTERNAL
