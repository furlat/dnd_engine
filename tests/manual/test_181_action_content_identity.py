"""Exact authored identity and admission for every active action behavior."""

from __future__ import annotations

from collections.abc import Iterable

from devtools.generate_event_contract import import_dnd_modules


from dnd.actions import SpellAction
from dnd.core.base_actions import BaseAction
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.items.consumables import _PotionDrinkAction


EXPECTED_ABSTRACT_ACTION_MECHANISMS = frozenset({
    SpellAction,
    _PotionDrinkAction,
})


def _active_descendants(
    action_type: type[BaseAction],
) -> set[type[BaseAction]]:
    descendants: set[type[BaseAction]] = set()
    for child_type in action_type.__subclasses__():
        if child_type.__module__.startswith("dnd."):
            descendants.add(child_type)
        descendants.update(_active_descendants(child_type))
    return descendants


def _concrete_action_types(
    action_types: Iterable[type[BaseAction]],
) -> tuple[type[BaseAction], ...]:
    return tuple(sorted(
        set(action_types) - EXPECTED_ABSTRACT_ACTION_MECHANISMS,
        key=lambda action_type: (
            action_type.__module__,
            action_type.__qualname__,
        ),
    ))


def test_active_action_inventory_is_exact_and_fully_declared() -> None:
    """Only three composition bases remain non-authored runtime mechanisms."""
    import_dnd_modules()
    descendants = _active_descendants(BaseAction)
    assert EXPECTED_ABSTRACT_ACTION_MECHANISMS <= descendants

    concrete = _concrete_action_types(descendants)
    declarations = tuple(
        get_content_declaration(action_type)
        for action_type in concrete
    )

    assert len({
        declaration.ref.identity_key
        for declaration in declarations
    }) == len(concrete)
    assert all(
        declaration.runtime_behavior_kind
        in {
            RuntimeBehaviorKind.ACTION,
            RuntimeBehaviorKind.SPELL,
        }
        for declaration in declarations
    )
    for action_type in EXPECTED_ABSTRACT_ACTION_MECHANISMS:
        try:
            get_content_declaration(action_type)
        except ValueError:
            continue
        raise AssertionError(
            f"Abstract action mechanism acquired authored identity: {action_type!r}",
        )


