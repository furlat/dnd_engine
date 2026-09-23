"""Damageable ground fixtures composed with existing authored spatial owners."""

from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID, uuid4

from dnd.blocks.base_item import BaseItem
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.item_types import ItemDestructionProfile
from dnd.spatial.area_conditions import SpatialCondition
from dnd.types.spatial_effects import SpatialEffectAnchorKind
from dnd.types.world import CardinalDirection


@dataclass(frozen=True, slots=True)
class GroundHardwareProfile:
    name: str
    description: str
    hit_points: int


GROUND_HARDWARE_PROFILES = MappingProxyType({
    "environment.trap.spikes": GroundHardwareProfile(
        "Spike housing", "A floor-mounted housing for retractable spikes.", 18),
    "environment.trap.dart_emitter": GroundHardwareProfile(
        "Dart emitter", "A fixed mechanism that launches its loaded darts.", 18),
    "environment.trap.jaw": GroundHardwareProfile(
        "Jaw trap", "A spring-loaded jaw fastened to the ground.", 18),
    "environment.trap.gas_vent": GroundHardwareProfile(
        "Gas vent", "A stone-mounted outlet for a controlled gas release.", 27),
    "environment.trap.pressure_plate": GroundHardwareProfile(
        "Pressure plate", "A floor plate connected to an authored control.", 12),
    "environment.trap.tripwire": GroundHardwareProfile(
        "Tripwire", "A tensioned wire connected to an authored trigger.", 2),
    "environment.trap.portal_hatch": GroundHardwareProfile(
        "Portal hatch", "A fitted hatch containing a magical passage.", 18),
})


def build_ground_hardware(item_id: str, *, source_entity_uuid: UUID | None = None,
                          hit_points: int | None = None) -> BaseItem:
    """Construct one passive body; its payload and control links are separate."""
    profile = GROUND_HARDWARE_PROFILES[item_id]
    hp = profile.hit_points if hit_points is None else hit_points
    if hp < 1:
        raise ValueError("Ground hardware hit points must be positive")
    item = BaseItem(
        source_entity_uuid=source_entity_uuid or uuid4(), item_id=item_id,
        name=profile.name, description=profile.description,
        is_targetable=True, is_pickable=False,
        destruction_profile=ItemDestructionProfile(
            name=f"Broken {profile.name.lower()}",
            description=f"Broken {profile.name.lower()}; its mechanism no longer functions.",
        ),
    )
    item.health = item.create_item_health(item.uuid, hp)
    return item


def materialize_ground_hardware(
    mechanism: SpatialCondition, *, item_id: str,
    hit_points: int | None = None, orientation: CardinalDirection | None = None,
    base_height_steps: int | None = None, parent_event: Event | None = None,
) -> BaseItem:
    """Install an unactivated authored mechanism on one physical body.

    The caller owns the mechanism's payload, footprint, visibility and links.
    Its existing WORLD_OBJECT binding owns movement and destruction cleanup.
    """
    if mechanism.applied or mechanism.is_active_spatial_condition():
        raise ValueError("Ground hardware requires an unactivated mechanism")
    if mechanism.anchor_kind is not SpatialEffectAnchorKind.FIXED_POSITION:
        raise ValueError("Ground mechanism already has an attachment owner")
    cause = parent_event
    if cause is None:
        cause = EventQueue.publish_declaration(Event(
            name="Install ground hardware", event_type=EventType.BASE_ACTION,
            source_entity_uuid=mechanism.source_entity_uuid, use_register=False,
        ))
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            if cause.canceled:
                raise RuntimeError("Ground hardware installation was canceled")
            cause = cause.phase_to(phase)
    if cause.canceled:
        raise RuntimeError("Ground hardware installation was canceled")

    item = build_ground_hardware(item_id, hit_points=hit_points,
                                 source_entity_uuid=mechanism.source_entity_uuid)
    mechanism.source_entity_uuid = item.uuid
    mechanism.anchor_kind = SpatialEffectAnchorKind.WORLD_OBJECT
    mechanism.anchor_uuid = item.uuid
    item.perception_condition_uuid = mechanism.uuid
    try:
        item.place_on_grid(mechanism.position, orientation=orientation,
                           base_height_steps=base_height_steps, parent_event=cause.uuid)
        result = mechanism.activate(parent_event=cause)
        if result is None or result.canceled or not mechanism.applied:
            raise RuntimeError("Ground hardware mechanism installation failed")
    except Exception:
        item.retire(parent_event=cause)
        raise
    if parent_event is None:
        cause.phase_to(EventPhase.COMPLETION)
    return item
