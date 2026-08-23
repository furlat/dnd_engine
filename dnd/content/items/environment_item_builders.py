"""Direct constructors for authored world objects used by battlefields."""

from uuid import UUID, uuid4

from dnd.actions.standard import SpellAction
from dnd.blocks.base_item import UsableItem
from dnd.core.base_actions import BaseAction
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.items.environment_interactables import (
    ActivateDeviceAction,
    ArcaneDevice,
    CookAction,
    DoorObject,
    LootAllAction,
    PullLeverAction,
    RestAction,
    StorageChest,
    TrapLever,
)
from dnd.items.spell_items import SpellGrantingItem
from dnd.items.torches import WallTorch
from dnd.spells.evocation import Fireball
from dnd.spells.evocation import MagicMissile
from dnd.types.world import CardinalDirection, WorldEdgeChannel


def _bind_item_behavior(item_id: str, action: BaseAction) -> None:
    action.provided_by_id = item_id
    action.origin_root_id = item_id
    action.bind_behavior_owner(origin_root_id=item_id)


def build_directional_wall(
    *,
    display_name: str = "Directional Wall",
    blocked_directions: tuple[CardinalDirection, ...],
    blocked_channels: tuple[WorldEdgeChannel, ...],
) -> DirectionalWall:
    """Construct one fixed directional wall from direct topology facts."""
    return DirectionalWall(
        source_entity_uuid=uuid4(),
        semantic_key="environment.directional_wall",
        name=display_name,
        blocked_directions=blocked_directions,
        blocked_channels=blocked_channels,
    )


def build_directional_door(
    *,
    display_name: str = "Directional Door",
    blocked_directions: tuple[CardinalDirection, ...],
    blocked_channels: tuple[WorldEdgeChannel, ...],
    is_open: bool = False,
) -> DirectionalDoor:
    """Construct one fixed directional door from direct topology facts."""
    return DirectionalDoor(
        source_entity_uuid=uuid4(),
        semantic_key="environment.directional_door",
        name=display_name,
        blocked_directions=blocked_directions,
        blocked_channels=blocked_channels,
        is_open=is_open,
    )


def build_door(
    source_entity_uuid: UUID,
    *,
    is_open: bool = False,
) -> DoorObject:
    """Construct one fixed door with state-derived open/close actions."""
    return DoorObject(
        source_entity_uuid=source_entity_uuid,
        semantic_key="environment.door",
        is_open=is_open,
        blocks_movement=not is_open,
        blocks_optics_field=not is_open,
        blocks_propagation_field=not is_open,
    )


def build_wall_torch() -> WallTorch:
    """Construct one fixed wall-mounted light source."""
    return WallTorch(
        source_entity_uuid=uuid4(),
        semantic_key="environment.wall_torch",
    )


def build_campfire(source_entity_uuid: UUID) -> UsableItem:
    """Construct one fixed campfire with direct rest/cook behaviors."""
    item_id = "environment.campfire"
    actions = [
        RestAction(
            source_entity_uuid=source_entity_uuid,
            template=True,
            semantic_key="action.environment.campfire.rest",
            behavior_id="action.environment.campfire.rest",
        ),
        CookAction(
            source_entity_uuid=source_entity_uuid,
            template=True,
            semantic_key="action.environment.campfire.cook",
            behavior_id="action.environment.campfire.cook",
        ),
    ]
    campfire = UsableItem(
        source_entity_uuid=source_entity_uuid,
        semantic_key=item_id,
        name="Campfire",
        description="A fixed camp object that supports resting and cooking.",
        is_pickable=False,
        map_char="*",
        use_action_templates=actions,
    )
    for action in actions:
        _bind_item_behavior(item_id, action)
    return campfire


def build_arcane_device(
    source_entity_uuid: UUID,
    *,
    heal_amount: int = 5,
) -> ArcaneDevice:
    """Construct one Arcana-gated healing device directly."""
    if heal_amount < 0:
        raise ValueError("arcane device heal_amount cannot be negative")
    item_id = "environment.arcane_device"
    action = ActivateDeviceAction(
        source_entity_uuid=source_entity_uuid,
        heal_amount=heal_amount,
        template=True,
        semantic_key="action.environment.arcane_device.activate",
        behavior_id="action.environment.arcane_device.activate",
    )
    device = ArcaneDevice(
        source_entity_uuid=source_entity_uuid,
        semantic_key=item_id,
        use_action_templates=[action],
    )
    _bind_item_behavior(item_id, action)
    return device


def build_arcane_machine_gun(
    source_entity_uuid: UUID,
) -> SpellGrantingItem:
    """Construct one fixed unlimited-use Magic Missile device."""
    item_id = "environment.arcane_machine_gun"
    action = MagicMissile(
        source_entity_uuid=source_entity_uuid,
        caster_level=1,
        cast_at_level=1,
        template=True,
        semantic_key="spell.magic_missile",
        behavior_id="spell.magic_missile",
    )
    device = SpellGrantingItem(
        source_entity_uuid=source_entity_uuid,
        semantic_key=item_id,
        name="Arcane Machine Gun",
        description="A fixed device with unlimited Magic Missile uses.",
        scroll_cast_level=1,
        charges=-1,
        is_pickable=False,
        is_consumable=False,
        use_action_templates=[action],
    )
    _bind_item_behavior(item_id, action)
    return device


def build_trap_lever(
    trap_condition_uuid: UUID,
    *,
    charges: int = 1,
) -> TrapLever:
    """Construct one lever linked to an active spike condition."""
    item_id = "environment.trap_lever"
    lever = TrapLever(
        source_entity_uuid=uuid4(),
        semantic_key=item_id,
        charges=charges,
        use_action_templates=[],
    )
    action = PullLeverAction(
        source_entity_uuid=lever.uuid,
        trap_condition_uuid=trap_condition_uuid,
        template=True,
        semantic_key="action.environment.trap_lever.pull",
        behavior_id="action.environment.trap_lever.pull",
    )
    _bind_item_behavior(item_id, action)
    lever.use_action_templates.append(action)
    return lever


def build_storage_chest(
    display_name: str,
    *,
    include_loot_all_action: bool,
) -> StorageChest:
    """Construct one fixed container; callers own its exact contents."""
    item_id = "environment.storage_chest"
    chest = StorageChest(
        source_entity_uuid=uuid4(),
        semantic_key=item_id,
        name=display_name,
        use_action_templates=[],
    )
    if include_loot_all_action:
        action = LootAllAction(
            source_entity_uuid=chest.uuid,
            source_item_uuid=chest.uuid,
            template=True,
            semantic_key="action.environment.storage_chest.loot_all",
            behavior_id="action.environment.storage_chest.loot_all",
        )
        _bind_item_behavior(item_id, action)
        chest.use_action_templates.append(action)
    return chest


def build_fireball_cannon(*, charges: int = 3) -> SpellGrantingItem:
    """Construct one fixed finite-charge Fireball device."""
    item_id = "environment.fireball_cannon"
    action: SpellAction = Fireball(
        source_entity_uuid=uuid4(),
        caster_level=5,
        cast_at_level=3,
        template=True,
        semantic_key="spell.fireball",
        behavior_id="spell.fireball",
    )
    cannon = SpellGrantingItem(
        source_entity_uuid=uuid4(),
        semantic_key=item_id,
        name="Fireball Cannon",
        scroll_cast_level=3,
        charges=charges,
        max_charges=charges,
        is_pickable=False,
        is_consumable=False,
        use_action_templates=[action],
    )
    _bind_item_behavior(item_id, action)
    return cannon


__all__ = [
    "build_arcane_device",
    "build_arcane_machine_gun",
    "build_campfire",
    "build_door",
    "build_directional_door",
    "build_directional_wall",
    "build_fireball_cannon",
    "build_storage_chest",
    "build_trap_lever",
    "build_wall_torch",
]
