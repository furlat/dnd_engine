"""Spell rules that deviated from the SRD, fixed with the simultaneous pass (plan §8.1 PB3; human Q4-Q7)."""

from collections.abc import Iterator

import pytest

from dnd.actions import SpellEvent
from dnd.conditions import Blinded
from dnd.core.base_block import LightLevel, MovementMode
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventPhase, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import AreaCondition
from dnd.spells.conjuration import Darkness, Daylight, StinkingCloud, Web
from dnd.spells.evocation import MassCureWounds, Shatter
from dnd.spells.illusion import HypnoticPattern, Silence
from dnd.spells.transmutation import Slow
from dnd.types.senses import OpticalObscurement
from dnd.types.spatial_effects import SpatialEffectLayer, SpatialEffectOccupancyPolicy
from tests.engine.support import set_hp
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena

CENTER = (8, 8)
# Seven cells around the centre; (7, 7) sorts first in the fixed resolution order.
CROWD_CELLS = ((7, 7), (8, 7), (9, 7), (7, 8), (8, 8), (9, 8), (7, 9))


@pytest.fixture
def caster() -> Iterator[Entity]:
    reset_spell_regression_arena(16, 16)
    actor = create_spell_regression_actor("Caster", (0, 0), "heroes", spell_slots={2: 4, 3: 3, 4: 1, 5: 2})
    yield actor
    reset_engine_runtime()


def cast(spell) -> SpellEvent:
    """Cast with fixed low dice faces and a fresh action, as on a new turn."""
    Entity.get(spell.source_entity_uuid).action_economy.reset_all_costs()
    Entity.update_all_entities_senses(max_distance=120)
    with fixed_dice_faces(*([2] * 80)):
        result = spell.apply()
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.phase is EventPhase.COMPLETION
    return result


def crowd(faction: str) -> list[Entity]:
    """Seven creatures whose HP falls with the fixed order: the first one has the most HP."""
    creatures = [create_spell_regression_actor(f"Creature {index}", cell, faction, wisdom=1)
                 for index, cell in enumerate(CROWD_CELLS)]
    for index, creature in enumerate(creatures):
        set_hp(creature, 70 - 10 * index)
    return creatures


def test_slow_affects_the_six_lowest_hp_creatures(caster: Entity) -> None:
    creatures = crowd("monsters")
    cast(Slow(source_entity_uuid=caster.uuid, end_position=CENTER, cast_at_level=3))
    slowed = ["Slowed" in creature.active_conditions for creature in creatures]
    assert slowed == [False, True, True, True, True, True, True]


def test_mass_cure_wounds_heals_the_six_lowest_hp_allies(caster: Entity) -> None:
    creatures = crowd("heroes")
    before = [creature.get_hp() for creature in creatures]
    cast(MassCureWounds(source_entity_uuid=caster.uuid, end_position=CENTER, cast_at_level=5))
    healed = [creature.get_hp() > hp for creature, hp in zip(creatures, before)]
    assert healed == [False, True, True, True, True, True, True]


def test_hypnotic_pattern_spares_a_creature_that_cannot_see_it(caster: Entity) -> None:
    sighted = create_spell_regression_actor("Sighted", (8, 8), "monsters", wisdom=1)
    blind = create_spell_regression_actor("Blind", (9, 8), "monsters", wisdom=1)
    blind.add_condition(Blinded(source_entity_uuid=blind.uuid, target_entity_uuid=blind.uuid))
    cast(HypnoticPattern(source_entity_uuid=caster.uuid, end_position=CENTER, cast_at_level=3))
    assert "Hypnotic Pattern" in sighted.active_conditions
    assert "Hypnotic Pattern" not in blind.active_conditions


def test_silence_makes_creatures_inside_immune_to_thunder_while_it_lasts(caster: Entity) -> None:
    target = create_spell_regression_actor("Target", CENTER, "monsters")

    def shatter_damage() -> int:
        before = target.get_hp()
        cast(Shatter(source_entity_uuid=caster.uuid, end_position=CENTER, cast_at_level=2))
        return before - target.get_hp()

    assert shatter_damage() > 0
    cast(Silence(source_entity_uuid=caster.uuid, end_position=CENTER, cast_at_level=2))
    assert shatter_damage() == 0
    assert caster.remove_condition("Concentrating")
    assert shatter_damage() > 0


@pytest.mark.parametrize(("darkness_level", "dispelled"), ((2, True), (3, True), (4, False)))
def test_daylight_dispels_only_darkness_of_third_level_or_lower(caster: Entity, darkness_level: int,
                                                                dispelled: bool) -> None:
    other = create_spell_regression_actor("Daylight caster", (15, 15), "heroes", spell_slots={3: 1})
    cast(Darkness(source_entity_uuid=caster.uuid, end_position=CENTER, cast_at_level=darkness_level))
    assert OpticalObscurement.MAGICAL_DARKNESS in get_map().get_optical_obscurements_at(CENTER)
    cast(Daylight(source_entity_uuid=other.uuid, end_position=(12, 12), cast_at_level=3))
    darkness_remains = OpticalObscurement.MAGICAL_DARKNESS in get_map().get_optical_obscurements_at(CENTER)
    assert darkness_remains is not dispelled


def test_stinking_cloud_costs_the_action_of_each_turn_started_inside(caster: Entity) -> None:
    """Zone turn triggers run at EXECUTION (Q7): the retching lasts the rest of that turn."""
    target = create_spell_regression_actor("Target", CENTER, "monsters", constitution=1)
    cast(StinkingCloud(source_entity_uuid=caster.uuid, end_position=CENTER, cast_at_level=3))
    for round_number in (1, 2):
        with fixed_dice_faces(*([2] * 20)):
            target.on_turn_start(round_number=round_number)
        assert "Nauseated" in target.active_conditions
        assert target.action_economy.actions.normalized_score == 0
        assert target.action_economy.bonus_actions.normalized_score == 1
        target.on_turn_end(round_number=round_number)
        assert "Nauseated" not in target.active_conditions


def _mud(source: Entity, name: str, cells: set[tuple[int, int]]) -> AreaCondition:
    zone = AreaCondition(name=name, source_entity_uuid=source.uuid, content_ref=ContentRef(
            pack_id="test.rules", definition_kind=ContentDefinitionKind.CONDITION,
            content_id=f"condition.rules.{name.lower().replace(' ', '_')}", content_version=1,
            definition_contract_hash="0" * 64),
        position=min(cells), affected_positions=set(cells), layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING, adds_difficult_terrain=True)
    zone.activate(parent_event=Event(name="Mud cause", event_type=EventType.BASE_ACTION, phase=EventPhase.EFFECT,
        source_entity_uuid=source.uuid))
    return zone


def test_difficult_terrain_never_stacks(caster: Entity) -> None:
    grid = get_map()
    grid.set_tile(4, 4, walking_cost=2)  # naturally difficult ground

    def cost(cell: tuple[int, int]) -> int:
        tile = grid.get_tile(*cell)
        assert tile is not None
        return tile.get_movement_cost(MovementMode.WALKING)

    first = _mud(caster, "Mud A", {(3, 3), (4, 4)})
    second = _mud(caster, "Mud B", {(3, 3), (4, 4)})
    assert (cost((3, 3)), cost((4, 4))) == (2, 2)
    first.deactivate()
    assert (cost((3, 3)), cost((4, 4))) == (2, 2)
    second.deactivate()
    assert (cost((3, 3)), cost((4, 4))) == (1, 2)


def test_web_lowers_light_one_level_while_it_stands(caster: Entity) -> None:
    grid = get_map()
    dark_cell = (CENTER[0] + 1, CENTER[1])
    grid.set_tile_base_light(dark_cell, LightLevel.DARKNESS)

    def light(cell: tuple[int, int]) -> LightLevel:
        tile = grid.get_tile(*cell)
        assert tile is not None
        return tile.resolved_light_level

    cast(Web(source_entity_uuid=caster.uuid, end_position=CENTER, cast_at_level=2))
    assert (light(CENTER), light(dark_cell)) == (LightLevel.DIM_LIGHT, LightLevel.DARKNESS)
    assert caster.remove_condition("Concentrating")
    assert (light(CENTER), light(dark_cell)) == (LightLevel.BRIGHT_LIGHT, LightLevel.DARKNESS)
