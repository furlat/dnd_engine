"""Direct constructors for authored world objects used by battlefields."""

from uuid import UUID, uuid4

from dnd.actions import SpellAction
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.core.creature_types import DamageType
from dnd.core.events import (
    Event,
    EventPhase,
    SpatialEffectInteractionEvent,
    TakeDamageEvent,
)
from dnd.items.environment import (
    DIRECTIONAL_CHANNELS,
    DirectionalDoor,
    DirectionalWall,
)
from dnd.items.environment_interactables import (
    ActivateDeviceAction,
    ArcaneDevice,
    CookAction,
    LootAllAction,
    PullLeverAction,
    RestAction,
    StorageChest,
    TrapLever,
)
from dnd.items.spell_items import SpellGrantingItem
from dnd.items.torches import StandingTorch, WallTorch
from dnd.spatial.environmental_conditions import OilSurface
from dnd.spells.evocation import Fireball
from dnd.spells.evocation import MagicMissile
from dnd.types.materials import Material
from dnd.types.world import WorldEdgeChannel
from dnd.types.spatial_effects import (
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
)


class OilBarrel(BaseItem):
    """Destructible barrel that spills oil at its committed position."""

    def _on_destroy(self, parent_event: Event | None) -> None:
        spill_position = self.get_position()
        if spill_position is None:
            return
        if parent_event is None:
            raise ValueError("Oil Barrel destruction requires a causal event")

        oil = OilSurface(
            source_entity_uuid=parent_event.source_entity_uuid,
            position=spill_position,
            affected_positions={spill_position},
        )
        activation = oil.activate(parent_event=parent_event)
        if activation is None or activation.canceled or not oil.applied:
            return
        if (
            not isinstance(parent_event, TakeDamageEvent)
            or not any(
                damage.damage_type is DamageType.FIRE
                for damage in parent_event.damages
            )
        ):
            return

        interaction = SpatialEffectInteractionEvent(
            source_entity_uuid=parent_event.source_entity_uuid,
            source_entity_name=parent_event.source_entity_name,
            target_entity_uuid=oil.uuid,
            operation=SpatialEffectInteractionOperation.IGNITE,
            positions=(spill_position,),
            intensity=SpatialEffectInteractionIntensity.STRONG,
            damage_type=DamageType.FIRE,
            source_object_uuid=self.uuid,
            source_item_id=self.item_id,
            parent_event=parent_event.uuid,
            phase=EventPhase.DECLARATION,
        )
        interaction = interaction.phase_to(EventPhase.EXECUTION)
        if interaction.canceled:
            return
        interaction = interaction.phase_to(EventPhase.EFFECT)
        if not interaction.canceled:
            interaction.phase_to(EventPhase.COMPLETION)


def build_directional_wall(
    *,
    display_name: str = "Directional Wall",
    blocked_channels: tuple[WorldEdgeChannel, ...] = DIRECTIONAL_CHANNELS,
    material: Material = Material.STONE,
) -> DirectionalWall:
    """Construct one fixed directional wall from direct topology facts."""
    return DirectionalWall(
        source_entity_uuid=uuid4(),
        item_id="environment.directional_wall",
        name=display_name,
        blocked_channels=blocked_channels,
        material=material,
    )


def build_cliff_face(*, display_name: str = "Cliff Face") -> DirectionalWall:
    """Construct one fixed movement-only cliff boundary."""
    return DirectionalWall(
        source_entity_uuid=uuid4(),
        item_id="environment.cliff_face",
        name=display_name,
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )


def build_directional_door(
    *,
    display_name: str = "Directional Door",
    blocked_channels: tuple[WorldEdgeChannel, ...] = DIRECTIONAL_CHANNELS,
    is_open: bool = False,
) -> DirectionalDoor:
    """Construct one fixed directional door from direct topology facts."""
    return DirectionalDoor(
        source_entity_uuid=uuid4(),
        item_id="environment.directional_door",
        name=display_name,
        blocked_channels=blocked_channels,
        is_open=is_open,
    )


def build_wall_torch() -> WallTorch:
    """Construct one fixed wall-mounted light source."""
    return WallTorch(
        source_entity_uuid=uuid4(),
        item_id="environment.wall_torch",
    )


def build_standing_torch() -> StandingTorch:
    """Construct one fixed freestanding light source."""
    return StandingTorch(
        source_entity_uuid=uuid4(),
        item_id="environment.standing_torch",
    )


def build_campfire(source_entity_uuid: UUID) -> UsableItem:
    """Construct one fixed campfire with direct rest/cook behaviors."""
    item_id = "environment.campfire"
    actions = [
        RestAction(
            source_entity_uuid=source_entity_uuid,
            template=True,
            semantic_key="action.environment.campfire.rest",
        ),
        CookAction(
            source_entity_uuid=source_entity_uuid,
            template=True,
            semantic_key="action.environment.campfire.cook",
        ),
    ]
    campfire = UsableItem(
        source_entity_uuid=source_entity_uuid,
        item_id=item_id,
        name="Campfire",
        description="A fixed camp object that supports resting and cooking.",
        is_pickable=False,
        map_char="*",
        use_action_templates=actions,
    )
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
    )
    device = ArcaneDevice(
        source_entity_uuid=source_entity_uuid,
        item_id=item_id,
        use_action_templates=[action],
    )
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
    )
    device = SpellGrantingItem(
        source_entity_uuid=source_entity_uuid,
        item_id=item_id,
        name="Arcane Machine Gun",
        description="A fixed device with unlimited Magic Missile uses.",
        scroll_cast_level=1,
        charges=-1,
        is_pickable=False,
        is_consumable=False,
        use_action_templates=[action],
    )
    return device


def build_trap_lever(
    trap_condition_uuid: UUID | None = None,
    *,
    charges: int = 1,
) -> TrapLever:
    """Construct one lever linked to an active spike condition."""
    item_id = "environment.trap_lever"
    lever = TrapLever(
        source_entity_uuid=uuid4(),
        item_id=item_id,
        charges=charges,
        use_action_templates=[],
    )
    if trap_condition_uuid is not None:
        lever.use_action_templates.append(PullLeverAction(
            source_entity_uuid=lever.uuid,
            trap_condition_uuid=trap_condition_uuid,
            template=True,
            semantic_key="action.environment.trap_lever.pull",
        ))
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
        item_id=item_id,
        name=display_name,
        use_action_templates=[],
    )
    if include_loot_all_action:
        action = LootAllAction(
            source_entity_uuid=chest.uuid,
            source_item_uuid=chest.uuid,
            template=True,
            semantic_key="action.environment.storage_chest.loot_all",
        )
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
    )
    cannon = SpellGrantingItem(
        source_entity_uuid=uuid4(),
        item_id=item_id,
        name="Fireball Cannon",
        scroll_cast_level=3,
        charges=charges,
        max_charges=charges,
        is_pickable=False,
        is_consumable=False,
        use_action_templates=[action],
    )
    return cannon


def build_oil_barrel(source_entity_uuid: UUID) -> OilBarrel:
    """Construct one destructible Oil Barrel with its direct spill mechanic."""
    return OilBarrel(
        source_entity_uuid=source_entity_uuid,
        item_id="environment.blocker.oil_barrel",
        name="Oil Barrel",
        is_pickable=False,
        is_targetable=True,
        health=OilBarrel.create_item_health(source_entity_uuid, 12),
        map_char="O",
        blocks_movement=True,
        blocks_optics_field=False,
        blocks_propagation_field=False,
    )


__all__ = [
    "build_arcane_device",
    "build_arcane_machine_gun",
    "build_campfire",
    "build_cliff_face",
    "build_directional_door",
    "build_directional_wall",
    "build_fireball_cannon",
    "build_oil_barrel",
    "build_storage_chest",
    "build_standing_torch",
    "build_trap_lever",
    "build_wall_torch",
]
