"""Replacing standard attacks releases their old live action identities."""

from uuid import uuid4

from dnd.actions_functional import setup_standard_actions
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_object import BaseObject
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventQueue
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime


def test_equipment_refresh_and_standard_reset_release_replaced_templates():
    reset_engine_runtime(grid_size=(4, 4))
    try:
        actor = Entity.create(uuid4(), "Fighter")
        actor.compose_entity()
        setup_standard_actions(actor)
        before = tuple(actor.registered_actions)
        dagger = build_authored_item("weapon.dagger", actor.uuid)
        assert actor.loot_item(dagger)
        assert actor.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
        after = {action.uuid for action in actor.registered_actions}
        replaced = [action for action in before if action.uuid not in after]
        assert replaced
        assert all(BaseObject.get(action.uuid) is None for action in replaced)
        current = tuple(actor.registered_actions)
        setup_standard_actions(actor)
        assert all(BaseObject.get(action.uuid) is None for action in current)
        handlers = EventQueue.get_handlers_by_source_entity(actor.uuid)
        refresh = [handler for handler in handlers if handler.name in (
            f"WeaponEquipHandler_{actor.uuid}", f"WeaponUnequipHandler_{actor.uuid}")]
        assert len(refresh) == 2
        assert all(handler.uuid in actor.event_handlers for handler in refresh)
    finally:
        reset_engine_runtime()
