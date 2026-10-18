"""A recorded world folded from keyed tile changes holds every Tile's complete row (plan Q4 (W), oracle (C)).

Each step is one residue or terrain write. Its committed facts carry only the keys the writer changed; folded
onto the rows recorded before the step, they must reproduce each live Tile's complete after-value: what a
whole-row fact used to carry.
"""

from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.residues import (ASHEN_RESIDUE, BLOOD_RESIDUE, CORROSIVE_RESIDUE, ResidueProfile, deposit_residues,
    remove_residues)
from dnd.spatial.area_conditions import AreaCondition
from dnd.types.event_facts import WorldTileState
from dnd.types.residues import ResidueEllipse
from dnd.types.spatial_effects import SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.world_facts import WorldFacts, apply_world_fact
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state

SPLASH = (ResidueEllipse(center=(3.5, 1.5), radius_x=0.8, radius_y=0.5),)
SPRAY = (ResidueEllipse(center=(4.2, 1.1), radius_x=0.4, radius_y=0.4, angle=0.5),)
SOURCE = uuid4()


def deposit(profile: ResidueProfile, cells: dict[tuple[int, int], tuple[ResidueEllipse, ...]], amount: int = 1
            ) -> Callable[[], object]:
    return lambda: deposit_residues(profile, cells, source_entity_uuid=SOURCE, amount=amount)


def remove(profile: ResidueProfile, *cells: tuple[int, int]) -> Callable[[], object]:
    return lambda: remove_residues(profile.residue_id, cells, source_entity_uuid=SOURCE)


@dataclass(frozen=True)
class Step:
    name: str
    write: Callable[[], object]
    # How many keyed tile facts the write commits.
    facts: int


def live_rows() -> dict[tuple[int, int], WorldTileState]:
    return {position: tile.to_world_tile_state() for position, tile in get_map().get_all_tiles().items()}


def check(steps: tuple[Step, ...]) -> None:
    recorded = WorldFacts(tiles=live_rows())
    for step in steps:
        cursor = EventQueue.event_cursor()
        step.write()
        facts = [event for _, event in EventQueue.iter_events_since(cursor)
                 if event.event_type is EventType.SPATIAL_TILE_CHANGED and event.phase is EventPhase.COMPLETION
                 and not event.canceled]
        assert len(facts) == step.facts, step.name
        for fact in facts:
            assert apply_world_fact(recorded, fact), step.name
        assert recorded.tiles == live_rows(), step.name


def test_residue_writes_fold_to_the_complete_tile_rows() -> None:
    reset_senses_state(width=9, height=3)
    check((
        Step("a material appears, with and without a contribution", deposit(BLOOD_RESIDUE, {
            (3, 1): SPLASH, (4, 1): SPLASH, (5, 1): ()}), 1),
        Step("its contribution grows", deposit(BLOOD_RESIDUE, {(3, 1): SPLASH, (4, 1): SPLASH}, amount=2), 1),
        Step("a second contribution joins", deposit(BLOOD_RESIDUE, {(4, 1): SPRAY}), 1),
        Step("pools fill to their maximum", deposit(BLOOD_RESIDUE, {(3, 1): SPLASH, (6, 1): ()}, amount=5), 1),
        Step("a full pool keeps its after-value", deposit(BLOOD_RESIDUE, {(3, 1): SPLASH, (6, 1): ()}), 0),
        Step("a second material shares a tile", deposit(ASHEN_RESIDUE, {(4, 1): (), (7, 1): ()}), 1),
        Step("a hazardous material appears", deposit(CORROSIVE_RESIDUE, {(5, 1): (), (6, 1): ()}), 1),
        Step("a material leaves, absent cells ignored", remove(BLOOD_RESIDUE, (3, 1), (4, 1), (8, 1)), 1),
        Step("the hazardous material leaves", remove(CORROSIVE_RESIDUE, (5, 1), (6, 1)), 1),
        Step("nothing left to remove", remove(BLOOD_RESIDUE, (3, 1)), 0),
    ))


def test_terrain_install_and_removal_fold_to_the_complete_tile_rows() -> None:
    reset_senses_state(width=8, height=3)
    observer = create_skeleton(name="Observer", position=(0, 1), darkvision=False)
    zone = AreaCondition(name="Test mud", source_entity_uuid=observer.uuid, content_ref=ContentRef(
            pack_id="test.keyed_tiles", definition_kind=ContentDefinitionKind.CONDITION,
            content_id="condition.keyed_tiles.mud", content_version=1, definition_contract_hash="0" * 64),
        position=(3, 1), affected_positions={(x, 1) for x in range(3, 7)},
        layer=SpatialEffectLayer.GROUND_SURFACE, occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        adds_difficult_terrain=True)
    cause = Event(name="Keyed tile test cause", event_type=EventType.BASE_ACTION, phase=EventPhase.EFFECT,
                  source_entity_uuid=observer.uuid)
    check((
        Step("terrain installs", lambda: zone.activate(parent_event=cause), 1),
        Step("terrain leaves", lambda: zone.deactivate(parent_event=cause), 1),
    ))
