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


def test_every_public_condition_class_declares_name_and_description() -> None:
    """Reachable public condition types cannot fall back to missing tooltip text."""
    import_dnd_modules()
    seen: set[type[BaseCondition]] = set()
    pending = list(BaseCondition.__subclasses__())
    failures: list[str] = []

    while pending:
        condition_type = pending.pop()
        pending.extend(condition_type.__subclasses__())
        if condition_type in seen:
            continue
        seen.add(condition_type)
        fields = condition_type.model_fields
        category = fields["condition_category"].get_default(
            call_default_factory=True,
        )
        if category is ConditionCategory.INTERNAL:
            continue
        name = fields["name"].get_default(call_default_factory=True)
        description = fields["description"].get_default(
            call_default_factory=True,
        )
        if not isinstance(name, str) or not name.strip():
            failures.append(f"{condition_type.__module__}.{condition_type.__name__}: name")
        if not isinstance(description, str) or not description.strip():
            failures.append(
                f"{condition_type.__module__}.{condition_type.__name__}: description"
            )

    assert failures == []
