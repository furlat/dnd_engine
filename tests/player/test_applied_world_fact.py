"""The world fold's record of what one fact wrote (`world_facts.apply_world_fact` -> `AppliedWorldFact`).

Each case fills the record from its own event's values: the seats' world publication reads which records an
occurrence wrote from it, and their values from the world as of the occurrence.
"""

from uuid import uuid4

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventPhase, EventType, SpatialChangeEvent, SpatialChangeType, WorldModifiedEvent
from dnd.types.event_facts import AppliedWorldFact
from dnd.types.materials import Material, TileSurface
from dnd.types.world import LightLevel
from dnd.world_facts import WorldFacts, apply_world_fact
from tests.player.test_projection_local_world import initial, item, placed


def folded(*objects) -> tuple[WorldFacts, object]:
    """A world folded from a nine-cell row's initialization, and its world event."""
    start = initial(objects, ((0, 0),), {})
    world_event = start.admitted[0][1]
    world = WorldFacts()
    applied = apply_world_fact(world, world_event)
    assert applied is not None and applied.replaced == frozenset((x, 0) for x in range(9))
    return world, world_event


def spatial(**fields) -> SpatialChangeEvent:
    return SpatialChangeEvent.model_validate(dict(source_entity_uuid=uuid4(), use_register=False,
        phase=EventPhase.COMPLETION, **fields), context=PASSIVE_EVENT_REPLAY)


def test_a_light_fact_records_every_after_value_it_carries_on_a_tile():
    world, _ = folded()
    light = spatial(change_type=SpatialChangeType.LIGHT_CHANGED, position=(99, 0),
        light_level_map={"1,0": LightLevel.DIM_LIGHT.value, "2,0": LightLevel.BRIGHT_LIGHT.value,
                         "99,0": LightLevel.DIM_LIGHT.value})
    applied = apply_world_fact(world, light)
    # (2, 0) already held bright light: the fact's own after-value is still recorded; (99, 0) is no tile.
    assert applied == AppliedWorldFact(light=(((1, 0), LightLevel.DIM_LIGHT), ((2, 0), LightLevel.BRIGHT_LIGHT)))
    assert apply_world_fact(world, light) == applied


def test_tile_scalars_replacements_and_their_static_part():
    world, _ = folded()
    cost = spatial(event_type=EventType.SPATIAL_TILE_CHANGED, change_type=SpatialChangeType.TILE_CHANGED,
        position=(1, 0), tile_walking_cost=3)
    assert apply_world_fact(world, cost) == AppliedWorldFact(tile_fields=(((1, 0), {"walking_cost": 3}),))
    replacement = world.tiles[(2, 0)].model_copy(update={"tile_uuid": uuid4(), "name": "Rubble",
        "surface": TileSurface(base_material=Material.WOOD)})
    whole = spatial(event_type=EventType.SPATIAL_TILE_CHANGED, change_type=SpatialChangeType.TILE_CHANGED,
        position=(2, 0), tile_state=replacement, tile_present=True)
    assert apply_world_fact(world, whole) == AppliedWorldFact(replaced=frozenset({(2, 0)}))
    renamed = spatial(event_type=EventType.SPATIAL_TILE_CHANGED, change_type=SpatialChangeType.TILE_CHANGED,
        position=(2, 0), tile_state=replacement.model_copy(update={"name": "Renamed"}), tile_present=True)
    with pytest.raises(ValueError, match="never change for its uuid"):
        apply_world_fact(world, renamed)


def test_objects_written_and_placed_and_connectors_with_their_own_values():
    box = placed(item("Box"), (1, 0))
    world, world_event = folded(box)
    identity = box.item.item_uuid
    moved = box.model_copy(update={"placement": box.placement.model_copy(update={"position": (3, 0),
        "covered_supports": ()})})
    write = WorldModifiedEvent.model_validate(dict(source_entity_uuid=uuid4(), use_register=False,
        phase=EventPhase.COMPLETION, object_uuid=identity, before=box, after=moved), context=PASSIVE_EVENT_REPLAY)
    assert apply_world_fact(world, write) == AppliedWorldFact(objects=frozenset({identity}),
        moved=frozenset({identity}))
    removed = WorldModifiedEvent.model_validate(dict(source_entity_uuid=uuid4(), use_register=False,
        phase=EventPhase.COMPLETION, object_uuid=identity, before=moved, after=None), context=PASSIVE_EVENT_REPLAY)
    assert apply_world_fact(world, removed) == AppliedWorldFact(objects=frozenset({identity}))
    assert identity not in world.objects


def test_canceled_and_foreign_facts_apply_nothing():
    world, _ = folded()
    light = spatial(change_type=SpatialChangeType.LIGHT_CHANGED, position=(1, 0),
        light_level_map={"1,0": LightLevel.DIM_LIGHT.value})
    assert apply_world_fact(world, light.model_copy(update={"canceled": True})) is None
    assert world.tiles[(1, 0)].resolved_light is LightLevel.BRIGHT_LIGHT
