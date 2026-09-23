"""Shared native target operations for handles and physical sensors."""

from uuid import UUID

from dnd.core.base_block import BaseBlock
from dnd.core.events import Event
from dnd.core.gridmap import get_map
from dnd.items.environment import DirectionalDoor
from dnd.items.torches import WallTorch
from dnd.types.controls import ControlLink


def linked_item(link: ControlLink) -> WallTorch | DirectionalDoor | None:
    if get_map().get_object_placement(link.target_item_uuid) is None:
        return None
    target = BaseBlock.get(link.target_item_uuid)
    if link.target_kind == "light" and isinstance(target, WallTorch) and target.is_active:
        return target
    if link.target_kind == "door" and isinstance(target, DirectionalDoor) and target.is_active:
        return target
    return None


def control_value(target: WallTorch | DirectionalDoor) -> bool:
    return target.is_lit if isinstance(target, WallTorch) else target.is_open


def request_control(link: ControlLink, engaged: bool, *, controller_uuid: UUID,
                    parent_event: Event) -> bool:
    """A sensor requests a value without inventing a creature or its action."""
    target = linked_item(link)
    value = link.engaged_value if engaged else not link.engaged_value
    if target is None:
        return False
    if isinstance(target, DirectionalDoor):
        return target.request_open(value, parent_event=parent_event,
                                   controller_uuid=controller_uuid, defer_close=True)
    if value:
        target.light(parent_event=parent_event.uuid)
    else:
        target.put_out(parent_event=parent_event.uuid)
    return target.is_lit is value
