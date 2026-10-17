"""Perception settled by deltas equals a cold recompute after real operations (plan §7 oracle).

Each case performs public operations; after each step every observer's
visible cells, contacts, hazards, light levels and light descriptors must be
what a complete recompute from the world produces.
"""

from dataclasses import dataclass
from typing import Callable, Sequence
from unittest.mock import patch
from uuid import uuid4

from dnd.blocks.base_item import BaseItem
from dnd.core.base_block import LightLevel
from dnd.core.events import Event, EventPhase, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spells.conjuration import FogCloudZone, SpiritGuardians
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state
from tests.engine.test_simultaneous_groups import assert_matches_cold_recompute
from tests.engine.test_spell_families import (
    create_family_caster, create_family_target, fixed_zone_randint, reset_spell_family_state,
)


@dataclass(frozen=True)
class SettlementCase:
    name: str
    # Builds the world; returns its observers and the steps to perform in order.
    build: Callable[[], tuple[Sequence[Entity], Sequence[Callable[[], object]]]]


def check_settlement(case: SettlementCase) -> None:
    observers, steps = case.build()
    for index, step in enumerate(steps):
        step()
        try:
            assert_matches_cold_recompute(*observers)
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


def test_settled_perception_equals_a_cold_recompute() -> None:
    for case in (
        SettlementCase("spirit guardians over an unexcluded ally", _spirit_guardians_over_an_ally),
        SettlementCase("fog cloud installed and removed", _fog_installed_and_removed),
        SettlementCase("walking torch", _walking_torch),
        SettlementCase("center object placed and removed", _center_object_placed_and_removed),
    ):
        check_settlement(case)
