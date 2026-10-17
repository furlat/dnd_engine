"""Window-box settlement equals recomputing every observer (plan §7 correctness oracle).

Each case performs public operations. After each step, the observers a fact
selected (their window box meets its change box) have settled; recomputing
every registered observer from the world must change nothing they publish:
visible cells, effective light, hazards, contacts and light descriptors.
Memory (seen cells, remembered fixtures) is excluded, as the plan states.
The world grids their writers keep (combined obscurement, hazard owners) must
equal a scan of the live world at every step.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Callable, Sequence
from unittest.mock import patch
from uuid import uuid4

import numpy as np

from dnd.action_timing import reset_action_count_recorder, set_action_count_recorder
from dnd.blocks.base_item import BaseItem
from dnd.blocks.sensory import capture_senses_snapshot, spatial_senses_system
from dnd.core.base_block import BaseBlock, LightLevel
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionCategory, HazardFilter
from dnd.core.events import Event, EventPhase, EventType
from dnd.core.gridmap import get_map
from dnd.core.view import layer_positions
from dnd.entity import Entity
from dnd.spells.conjuration import FogCloudZone, SpiritGuardians
from dnd.types.senses import OBSCUREMENT_BITS
from dnd.types.world import OccupancyLayer
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state
from tests.engine.test_spell_families import (
    create_family_caster, create_family_target, fixed_zone_randint, reset_spell_family_state,
)


def _published(observer_uuid) -> dict:
    snapshot = capture_senses_snapshot(spatial_senses_system.senses_by_observer[observer_uuid])
    return {"visible": snapshot.visible, "light": snapshot.effective_light_levels,
            "hazards": snapshot.hazardous_cells, "entities": snapshot.entities, "objects": snapshot.objects,
            "light_sources": snapshot.light_sources}


def assert_selection_matches_every_observer_recomputed() -> None:
    """The oracle: no registered observer's published perception moves under a full recompute."""
    observers = sorted(spatial_senses_system.senses_by_observer, key=str)
    settled = {identity: _published(identity) for identity in observers}
    # Cold: no observer keeps routes, contact rows or light inputs from the settled pass, so a
    # missed revision or touched set cannot hide behind a reused value.
    spatial_senses_system.fields.clear()
    for identity in observers:
        spatial_senses_system.recompute_observer(identity)
    for identity in observers:
        recomputed = _published(identity)
        differing = [key for key in settled[identity] if settled[identity][key] != recomputed[key]]
        assert not differing, f"{BaseBlock.get(identity).name}: {differing}"


def _holds_ground_hazard(block: BaseBlock) -> bool:
    return any(condition.hazard_filter is not None and condition.affects_occupancy_layer(OccupancyLayer.GROUND)
               for condition in block.active_conditions.values())


def assert_world_grids_match_a_scan() -> None:
    """The writer-kept obscurement bits and hazard owners equal a scan of the live world."""
    grid = get_map()
    exists = grid.cell_exists
    expected = np.zeros(exists.values.shape, dtype=np.uint8)
    footprints = {condition.uuid: set(layer_positions(grid.condition_footprint(condition.uuid)))
                  for condition in grid.get_spatial_conditions()}
    for condition in grid.get_spatial_conditions():
        value = condition.optical_obscurement_value()
        if value is None or not condition.contributions_active():
            continue
        suppressed = {cell for suppression in condition.spatial_suppressions for cell in suppression.positions}
        for x, y in footprints[condition.uuid] - suppressed:
            expected[x - exists.x0, y - exists.y0] |= OBSCUREMENT_BITS[value]
    grid.settle_obscurement_activity()
    assert np.array_equal(grid.cell_obscurement.values, expected)

    owners, xs, ys, owner_of = grid.hazard_owners()
    reported = {owner.uuid: set(zip(xs[owner_of == index].tolist(), ys[owner_of == index].tolist()))
                for index, owner in enumerate(owners)}
    scanned = dict(footprints)
    tiles = grid.get_all_tiles()
    for position, tile in tiles.items():
        if _holds_ground_hazard(tile):
            scanned[tile.uuid] = {position}
    for placement in grid.iter_object_placements():
        block = BaseBlock.get(placement.object_uuid)
        if block is not None and _holds_ground_hazard(block):
            scanned[block.uuid] = set(placement.positions if placement.boundary_direction is None
                                      else (placement.position,))
    assert {identity: reported.get(identity) for identity in scanned} == scanned
    residue_tiles = {tile.uuid for tile in tiles.values() if tile.is_hazardous_for()}
    assert reported.keys() - scanned.keys() <= residue_tiles


@dataclass(frozen=True)
class SettlementCase:
    name: str
    # Builds the world; returns its observers and the steps to perform in order.
    build: Callable[[], tuple[Sequence[Entity], Sequence[Callable[[], object]]]]


def check_settlement(case: SettlementCase) -> None:
    _, steps = case.build()
    for index, step in enumerate(steps):
        step()
        try:
            assert_world_grids_match_a_scan()
            assert_selection_matches_every_observer_recomputed()
        except AssertionError as error:
            raise AssertionError(f"{case.name}, step {index}: {error}") from error


def _cause(source) -> Event:
    return Event(event_type=EventType.BASE_ACTION, source_entity_uuid=source, phase=EventPhase.EFFECT)


def _spirit_guardians_over_an_ally():
    # The ally is not excluded: the zone installed in its own group is
    # hazardous to it, and its membership conditions settle in that group.
    reset_spell_family_state(width=18, height=18)
    caster = create_family_caster(position=(5, 5), spell_slots={3: 1}, faction="heroes")
    enemy = create_family_target(name="Spirit Enemy", position=(7, 5), faction="monsters", hp_dice=10)
    ally = create_family_target(name="Spirit Ally", position=(6, 6), faction="heroes", hp_dice=10)
    Entity.update_all_entities_senses(max_distance=30)

    def cast():
        with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
            event = SpiritGuardians(source_entity_uuid=caster.uuid, template=False).apply()
        assert event is not None and not event.canceled
    return (caster, enemy, ally), (cast,)


def _fog_installed_and_removed():
    reset_senses_state(width=9, height=3)
    observers = (create_skeleton(name="Near", position=(0, 1), darkvision=False),
                 create_skeleton(name="Darkvision", position=(2, 0), darkvision=True),
                 create_skeleton(name="Far", position=(8, 1), darkvision=False))
    for observer in observers:
        observer.update_entity_senses(max_distance=8)
    source = uuid4()
    fog = FogCloudZone(source_entity_uuid=source, position=(4, 1), affected_positions={(4, 0), (4, 1), (4, 2)})
    return observers, (lambda: fog.activate(parent_event=_cause(source)),
                       lambda: fog.deactivate(parent_event=_cause(source)))


def _walking_torch():
    reset_senses_state(width=10, height=3, default_light=LightLevel.DARKNESS)
    mover = create_skeleton(name="Torchbearer", position=(2, 1), darkvision=False)
    observers = (mover, create_skeleton(name="Watcher", position=(8, 1), darkvision=False),
                 create_skeleton(name="Darkvision", position=(0, 0), darkvision=True))
    get_map().add_light_source(mover.position, bright_radius_feet=10, dim_radius_feet=5, anchor_uuid=mover.uuid)
    for observer in observers:
        observer.update_entity_senses(max_distance=9)
    return observers, tuple((lambda destination=destination: Entity.update_entity_position(mover, destination))
                            for destination in ((3, 1), (4, 1), (4, 2), (3, 2)))


def _center_object_placed_and_removed():
    reset_senses_state(width=8, height=3)
    observers = (create_skeleton(name="West", position=(0, 1), darkvision=False),
                 create_skeleton(name="East", position=(7, 1), darkvision=False))
    for observer in observers:
        observer.update_entity_senses(max_distance=8)
    crate = BaseItem(item_id="test.scoped.crate", source_entity_uuid=uuid4(), name="Crate", is_pickable=False)
    grid = get_map()
    return observers, (lambda: grid.place_object(crate.uuid, (3, 1)), lambda: grid.remove_object(crate.uuid))


def _ground_hazard_on_a_tile_and_an_object():
    reset_senses_state(width=8, height=3)
    observers = (create_skeleton(name="West", position=(0, 1), darkvision=False),
                 create_skeleton(name="East", position=(7, 1), darkvision=False))
    for observer in observers:
        observer.update_entity_senses(max_distance=8)
    grid = get_map()
    tile = grid.get_tile(3, 0)
    crate = BaseItem(item_id="test.oracle.hazard_crate", source_entity_uuid=uuid4(), name="Crate", is_pickable=False)

    def hazard(target) -> BaseCondition:
        return BaseCondition(name=f"Burning {target.name}", source_entity_uuid=uuid4(), target_entity_uuid=target.uuid,
                             condition_category=ConditionCategory.CONDITION, hazard_filter=HazardFilter.ALL)
    burning = hazard(tile)
    return observers, (lambda: tile.add_condition(burning), lambda: grid.place_object(crate.uuid, (4, 1)),
                       lambda: crate.add_condition(hazard(crate)), lambda: grid.remove_object(crate.uuid),
                       lambda: tile.remove_condition(burning.name))


def _distant_observer_outside_every_window(with_far: bool = True):
    # The far watcher's window (its 3-cell reach) never meets these changes, so no
    # fact selects it; its published view must still be what a recompute gives.
    reset_senses_state(width=40, height=3, default_light=LightLevel.DARKNESS)
    mover = create_skeleton(name="Torchbearer", position=(1, 1), darkvision=False)
    near = create_skeleton(name="Near", position=(4, 1), darkvision=True)
    watchers = [(mover, 6), (near, 6)]
    if with_far:
        watchers.append((create_skeleton(name="Far", position=(37, 1), darkvision=True), 3))
    get_map().add_light_source(mover.position, bright_radius_feet=10, dim_radius_feet=5, anchor_uuid=mover.uuid)
    for observer, reach in watchers:
        observer.update_entity_senses(max_distance=reach)
    crate = BaseItem(item_id="test.oracle.crate", source_entity_uuid=uuid4(), name="Crate", is_pickable=False)
    grid = get_map()
    return tuple(observer for observer, _ in watchers), (lambda: Entity.update_entity_position(mover, (2, 1)),
                                lambda: grid.place_object(crate.uuid, (3, 1)),
                                lambda: Entity.update_entity_position(mover, (2, 2)),
                                lambda: grid.remove_object(crate.uuid))


def test_window_selected_settlement_equals_every_observer_recomputed() -> None:
    for case in (
        SettlementCase("spirit guardians over an unexcluded ally", _spirit_guardians_over_an_ally),
        SettlementCase("fog cloud installed and removed", _fog_installed_and_removed),
        SettlementCase("walking torch", _walking_torch),
        SettlementCase("center object placed and removed", _center_object_placed_and_removed),
        SettlementCase("ground hazard on a tile and an object", _ground_hazard_on_a_tile_and_an_object),
        SettlementCase("distant observer outside every window", _distant_observer_outside_every_window),
    ):
        check_settlement(case)


def _recomputes_of_first_step(with_far: bool) -> int:
    _, steps = _distant_observer_outside_every_window(with_far)
    counts: Counter[str] = Counter()
    token = set_action_count_recorder(lambda name, value: counts.update({name: value}))
    try:
        steps[0]()  # the torchbearer's step: the far watcher's window is 30 cells away
    finally:
        reset_action_count_recorder(token)
    return counts["sensory.observer_settled"]


def test_a_change_recomputes_only_the_observers_whose_window_it_reaches() -> None:
    assert _recomputes_of_first_step(with_far=True) == _recomputes_of_first_step(with_far=False) > 0
