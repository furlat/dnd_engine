"""Invalid equipment destinations are ordinary player-command rejections."""

import random

import pytest

from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventQueue
from dnd.player.commands import CommandRejected
from dnd.player.session import (
    advance_controller, close_session, create_session, equip_player_item,
    unequip_player_item,
)


def test_incompatible_equipment_slot_is_rejected_without_native_dispatch() -> None:
    random_state = random.getstate()
    random.seed(0)
    session = create_session()
    try:
        for _ in range(40):
            operation = advance_controller(session)
            assert operation.boundary is not None
            if operation.boundary.status == "waiting_for_human":
                break
        else:
            pytest.fail("Encounter did not reach a human decision")
        actor = session.encounter.get_current_entity()
        assert actor is not None
        weapon = actor.equipment.weapon_melee_main
        assert weapon is not None
        unequip_player_item(session, actor.uuid, WeaponSlot.MELEE_MAIN)
        before = EventQueue.event_cursor(), random.getstate()

        with pytest.raises(CommandRejected):
            equip_player_item(session, actor.uuid, weapon.uuid, BodyPart.HEAD)

        assert (EventQueue.event_cursor(), random.getstate()) == before
        assert weapon.uuid in actor.inventory.items
        assert actor.equipment.weapon_melee_main is None
    finally:
        close_session(session)
        random.setstate(random_state)
