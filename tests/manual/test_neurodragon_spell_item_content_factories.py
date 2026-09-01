"""Maintained direct construction proof for spell-bearing items."""

from uuid import uuid4

from dnd.entity import Entity
from dnd.items.spell_items import build_fireball_scroll
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import Fireball


def test_scroll_materialization_preserves_stack_and_cast_variants() -> None:
    """Direct variants preserve stack compatibility and scroll cast level."""
    reset_engine_runtime(grid_size=(5, 4))
    owner = Entity.create(source_entity_uuid=uuid4(), name="Scroll bearer")
    first = build_fireball_scroll(owner.uuid, cast_level=3)
    second = build_fireball_scroll(owner.uuid, cast_level=3)
    higher = build_fireball_scroll(owner.uuid, cast_level=5)

    assert first.item_id == second.item_id == higher.item_id == (
        "spell_item.scroll_fireball"
    )
    assert first.stack_id == second.stack_id == "scroll_fireball_l3"
    assert higher.stack_id == "scroll_fireball_l5"
    assert higher.stack_id != first.stack_id
    first_action = first.get_use_actions(owner.uuid)[0]
    higher_action = higher.get_use_actions(owner.uuid)[0]
    assert isinstance(first_action, Fireball)
    assert isinstance(higher_action, Fireball)
    assert first_action.cast_at_level == 3
    assert higher_action.cast_at_level == 5
    assert first_action.source_item_uuid == first.uuid
