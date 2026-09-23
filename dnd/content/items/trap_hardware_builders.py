"""Physical trap hardware composed with the existing independent pulse owner."""

from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID, uuid4

from dnd.blocks.base_item import BaseItem
from dnd.core.creature_types import DamageType
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.item_types import ItemDestructionProfile
from dnd.spatial.mechanisms import (
    AreaGeometry, CRUSHER_CONTENT_REF, FiniteTrap, SWINGING_BLADE_CONTENT_REF, TrapSave,
)
from dnd.types.materials import Material
from dnd.types.spatial_effects import SpatialEffectAnchorKind
from dnd.types.traps import TrapDamage, TrapPayload, TrapState
from dnd.types.world import CardinalDirection


@dataclass(frozen=True, slots=True)
class TrapHardwareProfile:
    mechanism: str
    material: Material
    style: str
    hit_points: int = 18


TRAP_HARDWARE_PROFILES = MappingProxyType({
    f"environment.trap.{mechanism}.{material.value}.{style}": TrapHardwareProfile(
        mechanism, material, style, 27 if material is Material.STONE else 18)
    for mechanism in ("swinging_blade", "crusher")
    for material in (Material.STONE, Material.WOOD)
    for style in ("workshop", "brassbound", "fortress")
})


def build_trap_hardware(item_id: str, *, hit_points: int | None = None,
                        source_entity_uuid: UUID | None = None) -> BaseItem:
    """Create an ordinary breakable, nonblocking fixture before attachment."""
    profile = TRAP_HARDWARE_PROFILES[item_id]
    hp = profile.hit_points if hit_points is None else hit_points
    if hp < 1:
        raise ValueError("Trap hardware hit points must be positive")
    name = f"{profile.style.title()} {profile.mechanism.replace('_', ' ')}"
    item = BaseItem(source_entity_uuid=source_entity_uuid or uuid4(), item_id=item_id,
        name=name, is_targetable=True, is_pickable=False,
        destruction_profile=ItemDestructionProfile(name=f"Broken {name}"))
    item.health = item.create_item_health(item.uuid, hp)
    return item


def materialize_trap_hardware(position: tuple[int, int], *,
        item_id: str = "environment.trap.swinging_blade.stone.workshop",
        direction: tuple[int, int] = (1, 0), trap_state: TrapState = TrapState.READY,
        rearm_after_activation: bool = False, stealth_dc: int | None = None,
        hit_points: int | None = None, payload: TrapPayload | None = None,
        avoidance: TrapSave | None = None, parent_event: Event | None = None,
        base_height_steps: int | None = None) -> tuple[BaseItem, FiniteTrap]:
    """Place one hardware object and its exact WORLD_OBJECT-anchored mechanism."""
    item = build_trap_hardware(item_id, hit_points=hit_points)
    profile = TRAP_HARDWARE_PROFILES[item_id]
    blade = profile.mechanism == "swinging_blade"
    mechanism = FiniteTrap(source_entity_uuid=item.uuid, position=position,
        affected_positions={position}, anchor_kind=SpatialEffectAnchorKind.WORLD_OBJECT,
        anchor_uuid=item.uuid, content_ref=SWINGING_BLADE_CONTENT_REF if blade else CRUSHER_CONTENT_REF,
        name=item.name, geometry=AreaGeometry(), direction=direction, trap_state=trap_state,
        rearm_after_activation=rearm_after_activation, condition_stealth_dc=stealth_dc,
        avoidance=avoidance or TrapSave(retreat_on_success=True),
        payload=payload or TrapPayload(damages=(TrapDamage(dice_count=1, dice_sides=6,
            damage_type=DamageType.SLASHING if blade else DamageType.BLUDGEONING),)))
    item.perception_condition_uuid = mechanism.uuid
    cause = parent_event
    if cause is None:
        cause = EventQueue.publish_declaration(Event(name="Install trap hardware",
            event_type=EventType.BASE_ACTION, source_entity_uuid=item.uuid, use_register=False))
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            cause = cause.phase_to(phase)
            if cause.canceled:
                raise RuntimeError("Trap hardware installation was canceled")
    orientation = {(1, 0): CardinalDirection.EAST, (-1, 0): CardinalDirection.WEST,
                   (0, 1): CardinalDirection.NORTH, (0, -1): CardinalDirection.SOUTH}[direction]
    item.place_on_grid(position, orientation=orientation, base_height_steps=base_height_steps,
                       parent_event=cause.uuid)
    result = mechanism.activate(parent_event=cause)
    if result is None or result.canceled or not mechanism.applied:
        item.retire(parent_event=cause)
        raise RuntimeError("Trap hardware mechanism installation failed")
    if parent_event is None:
        cause.phase_to(EventPhase.COMPLETION)
    return item, mechanism
