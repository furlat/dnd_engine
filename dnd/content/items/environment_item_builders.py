"""Direct constructors for authored world objects used by battlefields."""

from dataclasses import dataclass, replace
from types import MappingProxyType
from uuid import UUID, uuid4
from typing import Literal, Sequence

from dnd.actions import SpellAction
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.core.creature_types import DamageType
from dnd.core.gridmap import get_map
from dnd.core.item_types import DoorSwing, ItemDestructionProfile
from dnd.content.items.door_profiles import DOOR_PROFILES
from dnd.core.events import (
    Event,
    EventPhase,
    SpatialEffectInteractionEvent,
    ItemDestructionEvent,
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
    ControlLever,
    LeverLink,
    LootAllAction,
    PullLeverAction,
    RestAction,
    StorageChest,
    TrapLever,
)
from dnd.items.spell_items import SpellGrantingItem
from dnd.items.torches import StandingTorch, WallTorch
from dnd.residues import BLOOD_RESIDUE, DREAD_RESIDUE, POISON_RESIDUE, ResidueProfile, deposit_residue
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spatial.environmental_conditions import OilSurface, WetSurface
from dnd.core.ground import ground_footprint
from dnd.spells.conjuration import GreaseZone
from dnd.spells.evocation import Fireball
from dnd.spells.enchantment import Sleep
from dnd.types.materials import Material
from dnd.types.material_deposits import MaterialDepositSource
from dnd.types.world import OccupancyLayer, WorldEdgeChannel
from dnd.types.world_placement import BoundaryStructure, BoundaryStructureKind, WorldPlacementKind, WorldPlacementSpec
from dnd.types.spatial_effects import (
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
)


@dataclass(frozen=True, slots=True)
class LiquidSpillProfile:
    """Authored contents; the existing surface or residue owns all mechanics."""

    name: str
    material: Literal["oil", "water", "grease"] | ResidueProfile
    amount: int = 1
    radius_cells: int = 1


LIQUID_BARREL_PROFILES = MappingProxyType({
    "environment.blocker.oil_barrel": LiquidSpillProfile("Oil", "oil"),
    "environment.blocker.water_barrel": LiquidSpillProfile("Water", "water"),
    "environment.blocker.grease_barrel": LiquidSpillProfile("Grease", "grease"),
    "environment.blocker.blood_barrel": LiquidSpillProfile("Blood", BLOOD_RESIDUE, amount=5),
    "environment.blocker.poison_barrel": LiquidSpillProfile("Poison", POISON_RESIDUE),
    "environment.blocker.dread_blood_barrel": LiquidSpillProfile("Dread Blood", DREAD_RESIDUE),
})

_LIQUID_SURFACES: dict[
    Literal["oil", "water", "grease"], type[OilSurface] | type[WetSurface] | type[GreaseZone]
] = {
    "oil": OilSurface, "water": WetSurface, "grease": GreaseZone,
}


class LiquidBarrel(BaseItem):
    """One physical container composes its authored material on destruction."""

    spill_profile: LiquidSpillProfile = LIQUID_BARREL_PROFILES["environment.blocker.oil_barrel"]

    def _on_destroy(self, parent_event: Event | None) -> None:
        if not isinstance(parent_event, ItemDestructionEvent):
            raise ValueError("A liquid spill requires its item destruction event")
        placement = parent_event.previous_placement
        if placement is None:
            return
        spill_position = placement.position
        positions = ground_footprint(spill_position, self.spill_profile.radius_cells)
        if not positions:
            return
        deposit_source = MaterialDepositSource(
            deposit_uuid=parent_event.lineage_uuid, origin=spill_position,
            radius_cells=self.spill_profile.radius_cells,
        )
        material = self.spill_profile.material
        if isinstance(material, ResidueProfile):
            for position in sorted(positions):
                tile = get_map().get_tile(*position)
                if tile is not None:
                    deposit_residue(tile, material, parent_event=parent_event,
                        amount=self.spill_profile.amount, deposit_source=deposit_source)
            return

        surface = _LIQUID_SURFACES[material](
            # Mundane grease has no caster. The destroyed item owns attribution,
            # so Grease's existing caster exemption cannot exempt the attacker.
            source_entity_uuid=self.uuid if material == "grease" else parent_event.source_entity_uuid,
            position=spill_position,
            affected_positions=positions,
            deposit_source=deposit_source,
            affected_occupancy_layers=frozenset({OccupancyLayer.GROUND}),
            duration=Duration(duration=None, duration_type=DurationType.PERMANENT),
            tags=set(),
        )
        # Spilling is not a new mixing rule. Leave incompatible ground owners
        # untouched; the existing material owner still arbitrates same-kind overlap.
        surface.affected_positions = {
            position for position in positions
            if all(isinstance(incumbent, SpatialCondition) and incumbent.content_ref == surface.content_ref
                   for incumbent in get_map().get_spatial_conditions_at(position, layer=surface.layer))
        }
        if not surface.affected_positions:
            surface.discard_from_runtime_owner()
            return
        activation = surface.activate(parent_event=parent_event)
        if activation is None or activation.canceled or not surface.applied:
            return
        if material != "oil" or DamageType.FIRE not in parent_event.damage_types:
            return

        interaction = SpatialEffectInteractionEvent(
            source_entity_uuid=parent_event.source_entity_uuid,
            source_entity_name=parent_event.source_entity_name,
            target_entity_uuid=surface.uuid,
            operation=SpatialEffectInteractionOperation.IGNITE,
            positions=tuple(sorted(surface.affected_positions)),
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


# Preserve the old public constructor name without a second behavior class.
OilBarrel = LiquidBarrel


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
    item = WallTorch(
        source_entity_uuid=uuid4(),
        item_id="environment.wall_torch",
        is_targetable=True,
        destruction_profile=ItemDestructionProfile(name="Broken Wall Torch"),
    )
    item.health = item.create_item_health(item.uuid, 5)
    return item


def build_standing_torch() -> StandingTorch:
    """Construct one fixed freestanding light source."""
    item = StandingTorch(
        source_entity_uuid=uuid4(),
        item_id="environment.standing_torch",
        is_targetable=True,
        destruction_profile=ItemDestructionProfile(name="Broken Standing Torch"),
    )
    item.health = item.create_item_health(item.uuid, 5)
    return item


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


def build_spell_device(
    *,
    item_id: str,
    name: str,
    spell_templates: Sequence[SpellAction],
    charges: int = -1,
    source_entity_uuid: UUID | None = None,
    scroll_cast_level: int = 1,
    hit_points: int = 32,
    concentration_capacity: int = 2,
) -> SpellGrantingItem:
    """Compose a fixed body identity with independently authored spell grants."""
    device = SpellGrantingItem(
        source_entity_uuid=source_entity_uuid or uuid4(),
        item_id=item_id,
        name=name,
        scroll_cast_level=scroll_cast_level,
        charges=charges,
        max_charges=charges,
        is_pickable=False,
        is_consumable=False,
        is_targetable=True,
        concentration_capacity=concentration_capacity,
        destruction_profile=ItemDestructionProfile(name=f"Broken {name}"),
        use_action_templates=list(spell_templates),
    )
    device.health = device.create_item_health(device.uuid, hit_points)
    return device


def build_authored_door(item_id: str, *, swing: DoorSwing = DoorSwing.OUTWARD,
                        is_open: bool = False, destruction_outcome: Literal["clear", "jammed"] = "clear",
                        hit_points: int | None = None, source_entity_uuid: UUID | None = None) -> DirectionalDoor:
    """Compose a family through the existing boundary, use and damage contracts."""
    profile = DOOR_PROFILES[item_id]
    if destruction_outcome not in ("clear", "jammed"):
        raise ValueError("Door destruction outcome must be clear or jammed")
    if destruction_outcome == "jammed" and not profile.supports_jammed_remnant:
        raise ValueError("This door family has no authored jammed outcome")
    hp = profile.hit_points if hit_points is None else hit_points
    if hp < 1:
        raise ValueError("Door hit points must be positive")
    owner = source_entity_uuid or uuid4()
    door = DirectionalDoor(source_entity_uuid=owner, item_id=item_id,
        health=BaseItem.create_item_health(owner, hp),
        name=profile.name, material=profile.material, mechanism=profile.mechanism,
        swing=swing, is_open=is_open, vertical_extent_steps=profile.vertical_extent_steps,
        blocked_channels=profile.closed_channels, is_targetable=True,
        destruction_profile=ItemDestructionProfile(
            name=f"Broken {profile.name}", outcome=destruction_outcome, placement_spec=WorldPlacementSpec(
                kind=WorldPlacementKind.BOUNDARY, occupies_bands=True,
                vertical_extent_steps=profile.vertical_extent_steps),
            boundary_structure=BoundaryStructure(structure=BoundaryStructureKind.DOOR,
                material=profile.material,
                blocked_channels=(WorldEdgeChannel.MOVEMENT,) if destruction_outcome == "jammed" else ())))
    return door


def build_arcane_machine_gun(
    source_entity_uuid: UUID,
    *,
    spell_templates: Sequence[SpellAction] | None = None,
    charges: int = -1,
) -> SpellGrantingItem:
    """Construct the arcane body with an aimed Sleep grant by default."""
    if spell_templates is None:
        spell_templates = [Sleep(
            source_entity_uuid=source_entity_uuid,
            caster_level=1,
            cast_at_level=1,
            cast_origin="source_item",
            target_sector_degrees=45,
            template=True,
            semantic_key="spell.sleep",
        )]
    return build_spell_device(
        source_entity_uuid=source_entity_uuid,
        item_id="environment.arcane_machine_gun",
        name="Arcane Machine Gun",
        spell_templates=spell_templates,
        charges=charges,
    )


def build_trap_lever(
    trap_condition_uuid: UUID | None = None,
    *,
    charges: int = 1,
    allow_activation: bool = False,
) -> TrapLever:
    """Build a finite pull-only or explicitly reversible trap control."""
    item_id = "environment.trap_lever"
    lever = TrapLever(
        source_entity_uuid=uuid4(),
        item_id=item_id,
        is_targetable=True,
        destruction_profile=ItemDestructionProfile(name="Broken Trap Lever"),
        charges=charges,
        allow_activation=allow_activation,
        use_action_templates=[],
    )
    if trap_condition_uuid is not None:
        lever.use_action_templates.append(PullLeverAction(
            source_entity_uuid=lever.uuid,
            trap_condition_uuid=trap_condition_uuid,
            template=True,
            semantic_key="action.environment.trap_lever.pull",
        ))
    lever.health = lever.create_item_health(lever.uuid, 10)
    return lever


def build_control_lever(link: LeverLink, *, is_engaged: bool = False) -> ControlLever:
    """Construct a reusable handle connected to one placed light or door."""
    item = ControlLever(
        source_entity_uuid=uuid4(),
        item_id="environment.control_lever",
        is_targetable=True,
        destruction_profile=ItemDestructionProfile(name="Broken Control Lever"),
        link=link,
        is_engaged=is_engaged,
    )
    item.health = item.create_item_health(item.uuid, 10)
    return item


def build_storage_chest(
    display_name: str,
    *,
    include_loot_all_action: bool,
    is_open: bool = False,
    item_id: str = "environment.storage_chest",
    source_entity_uuid: UUID | None = None,
) -> StorageChest:
    """Construct one fixed container; callers own its exact contents."""
    chest = StorageChest(
        source_entity_uuid=source_entity_uuid or uuid4(),
        item_id=item_id,
        name=display_name,
        is_targetable=True,
        destruction_profile=ItemDestructionProfile(name=f"Broken {display_name}"),
        is_open=is_open,
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
    chest.health = chest.create_item_health(chest.uuid, 18)
    return chest


def build_fireball_cannon(
    *,
    charges: int = 3,
    spell_templates: Sequence[SpellAction] | None = None,
    range_feet: int = 225,
    target_sector_degrees: float | None = 45,
) -> SpellGrantingItem:
    """Construct the cannon body; custom grants retain their own targeting data."""
    minimum_cast_level = 3 if spell_templates is None else 1
    if spell_templates is None:
        spell_templates = [Fireball(
            source_entity_uuid=uuid4(),
            caster_level=5,
            cast_at_level=3,
            cast_origin="source_item",
            alt_range=range_feet,
            target_sector_degrees=target_sector_degrees,
            template=True,
            semantic_key="spell.fireball",
        )]
    return build_spell_device(
        item_id="environment.fireball_cannon",
        name="Fireball Cannon",
        scroll_cast_level=minimum_cast_level,
        charges=charges,
        spell_templates=spell_templates,
    )


def build_liquid_barrel(item_id: str, source_entity_uuid: UUID, *, radius_cells: int | None = None) -> LiquidBarrel:
    """Compose an authored barrel body and its independent ground aftermath."""
    profile = LIQUID_BARREL_PROFILES[item_id]
    if radius_cells is not None:
        if radius_cells < 0:
            raise ValueError("Liquid spill radius cannot be negative")
        profile = replace(profile, radius_cells=radius_cells)
    return LiquidBarrel(
        source_entity_uuid=source_entity_uuid,
        item_id=item_id,
        name=f"{profile.name} Barrel",
        description=f"A barrel filled with {profile.name.lower()}.",
        spill_profile=profile,
        is_pickable=False,
        is_targetable=True,
        health=BaseItem.create_item_health(source_entity_uuid, 12),
        destruction_profile=ItemDestructionProfile(
            name=f"Broken {profile.name} Barrel",
            description=f"A shattered barrel that has spilled its {profile.name.lower()}."),
        map_char="O",
        blocks_movement=True,
        blocks_optics_field=False,
        blocks_propagation_field=False,
    )


def build_oil_barrel(source_entity_uuid: UUID, *, radius_cells: int | None = None) -> LiquidBarrel:
    """Keep the existing authored oil constructor and content identity."""
    return build_liquid_barrel("environment.blocker.oil_barrel", source_entity_uuid, radius_cells=radius_cells)


__all__ = [
    "build_arcane_device",
    "build_arcane_machine_gun",
    "build_campfire",
    "build_cliff_face",
    "build_control_lever",
    "build_directional_door",
    "build_directional_wall",
    "build_fireball_cannon",
    "build_liquid_barrel",
    "build_oil_barrel",
    "build_spell_device",
    "build_storage_chest",
    "build_standing_torch",
    "build_trap_lever",
    "build_wall_torch",
]
