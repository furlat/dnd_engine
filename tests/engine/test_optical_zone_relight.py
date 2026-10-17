"""An opaque zone's removal re-lights the cells it shadowed (plan §6b light grid writer).

The end state of "cast an opaque zone, then end it" must equal a world built
directly into that end state: every cell's objective light and every observer's
view (visible cells, effective light, hazards, contacts by name).
"""

from dataclasses import dataclass
from typing import Callable

import pytest

from dnd.actions import DropConcentration
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.dice import fixed_dice_faces
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition
from dnd.spells.walls import WallOfFire
from dnd.types.spatial_effects import SpatialEffectAnchorKind, SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.types.world import LightLevel
from tests.engine.support import reset_combat_state
from tests.manual.spell_regression_support import create_spell_regression_actor


@dataclass(frozen=True)
class RelightCase:
    name: str
    # Acts on the built world (caster first); the end state must equal the untouched world.
    act: Callable[[Entity], None]


def _world() -> list[Entity]:
    """A dark hall lit by one torch west of the wall line, watched from both sides."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 16, 11, default_light=LightLevel.DARKNESS)
    caster = create_spell_regression_actor("Caster", (1, 1), "heroes", spell_slots={4: 2})
    watchers = [create_spell_regression_actor("West watcher", (2, 5), "heroes"),
                create_spell_regression_actor("East watcher", (12, 5), "heroes")]
    grid.add_light_source((4, 5), bright_radius_feet=20, dim_radius_feet=20)
    Entity.update_all_entities_senses(max_distance=20)
    return [caster, *watchers]


def _state(observers: list[Entity]) -> dict:
    names = {observer.uuid: observer.name for observer in observers}
    views = {}
    for observer in observers:
        snapshot = capture_senses_snapshot(observer.senses)
        views[observer.name] = (snapshot.visible, snapshot.effective_light_levels, snapshot.hazardous_cells,
                                {names.get(identity, "?"): contact for identity, contact in snapshot.entities.items()})
    lights = {position: tile.resolved_light_level for position, tile in get_map().get_all_tiles().items()}
    return {"cell light": lights, "views": views}


def _wall_of_fire_then_dropped(caster: Entity) -> None:
    with fixed_dice_faces(*([4] * 200)):
        cast = WallOfFire(source_entity_uuid=caster.uuid, end_position=(7, 1), extra_target_positions=[(7, 9)]).apply()
    assert cast is not None and not cast.canceled
    dropped = DropConcentration(source_entity_uuid=caster.uuid, use_register=False).apply()
    assert dropped is not None and not dropped.canceled


def check_relight(case: RelightCase) -> None:
    expected = _state(_world())
    observers = _world()
    case.act(observers[0])
    actual = _state(observers)
    for key in expected:
        differing = sorted(str(item) for item in set(expected[key]) | set(actual[key])
                           if expected[key].get(item) != actual[key].get(item))
        assert not differing, f"{case.name}: {key} differs at {differing[:8]}"


def test_an_ended_opaque_zone_leaves_the_world_it_found() -> None:
    check_relight(RelightCase("wall of fire cast, then concentration dropped", _wall_of_fire_then_dropped))


def test_a_creature_cannot_carry_an_opaque_zone() -> None:
    """A presence change of the anchor never re-lights, so an opaque zone anchored to a creature is rejected."""
    caster = _world()[0]
    with pytest.raises(ValueError, match="cannot block physical optics"):
        AreaCondition(name="Carried wall", source_entity_uuid=caster.uuid, content_ref=_ref("carried_wall"),
                      position=caster.position, affected_positions={caster.position},
                      anchor_kind=SpatialEffectAnchorKind.ENTITY, anchor_uuid=caster.uuid,
                      layer=SpatialEffectLayer.FIELD, occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
                      blocks_physical_optics=True)


def _ref(name: str) -> ContentRef:
    return ContentRef(pack_id="test.relight", definition_kind=ContentDefinitionKind.CONDITION,
                      content_id=f"condition.relight.{name}", content_version=1, definition_contract_hash="0" * 64)
