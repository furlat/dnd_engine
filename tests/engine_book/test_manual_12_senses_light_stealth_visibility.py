"""Manual Chapter 12 checks for senses, light, stealth, and visibility."""

from uuid import uuid4

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.conditions import Hidden, Invisible
from dnd.core.base_block import BaseBlock, LightLevel, SenseMode, SensesType
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.utils import reset_combat_state


def reset_senses_state(
    width: int = 8,
    height: int = 1,
    default_light: LightLevel = LightLevel.BRIGHT_LIGHT,
) -> None:
    """Clear global state and create a floor arena with one light level."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    for tile in grid._tiles.values():
        tile.default_light = default_light


def create_senses_actor(
    name: str,
    position: tuple[int, int],
    faction: str | None,
    wisdom: int = 12,
) -> Entity:
    """Create an actor with stable perception, senses, and movement."""
    actor_id = uuid4()
    return Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=12),
                intelligence=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=wisdom),
                charisma=AbilityConfig(ability_score=10),
            ),
            action_economy=ActionEconomyConfig(movement=30),
            proficiency_bonus=2,
            position=position,
            faction=faction,
        ),
    )


def test_darkness_filters_geometric_fov_into_visible_senses() -> None:
    """Senses subscribe to geometric FOV but expose only effectively lit cells."""
    reset_senses_state(width=6, default_light=LightLevel.DARKNESS)
    observer = create_senses_actor("Observer", (0, 0), "heroes")
    target = create_senses_actor("Target", (3, 0), "monsters")

    observer.update_entity_senses(max_distance=5)

    subscriptions = get_map().get_entity_subscriptions(observer.uuid)
    assert (3, 0) in subscriptions
    assert (3, 0) not in observer.senses.visible
    assert (1, 0) in observer.senses.visible
    assert target.uuid not in observer.senses.entities
    assert (3, 0) not in observer.senses.seen


def test_sense_modes_resolve_light_from_the_observers_point_of_view() -> None:
    """Darkvision, Devil's Sight, and truesight change effective light."""
    reset_senses_state(width=16)
    observer = create_senses_actor("Observer", (0, 0), "heroes")
    grid = get_map()
    near_dark = grid.get_tile(10, 0)
    far_dark = grid.get_tile(15, 0)
    dim = grid.get_tile(5, 0)
    magical = grid.get_tile(2, 0)
    assert near_dark is not None
    assert far_dark is not None
    assert dim is not None
    assert magical is not None

    near_dark.default_light = LightLevel.DARKNESS
    far_dark.default_light = LightLevel.DARKNESS
    dim.default_light = LightLevel.DIM_LIGHT
    magical.default_light = LightLevel.BRIGHT_LIGHT
    magical.add_obscurement(uuid4(), LightLevel.MAGICAL_DARKNESS, fire_event=False)

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
    ]

    assert near_dark.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.DIM_LIGHT
    assert far_dark.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.DARKNESS
    assert dim.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.BRIGHT_LIGHT
    assert magical.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.MAGICAL_DARKNESS

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.DEVILS_SIGHT, range_feet=120)
    ]
    assert magical.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.BRIGHT_LIGHT

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]
    assert magical.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.BRIGHT_LIGHT


def test_bright_senses_cache_visible_entities_seen_cells_and_paths() -> None:
    """A full senses update fills visible cells, entities, memory, and paths."""
    reset_senses_state(width=6)
    observer = create_senses_actor("Observer", (0, 0), "heroes")
    target = create_senses_actor("Target", (3, 0), "monsters")

    observer.update_entity_senses(max_distance=5)

    assert (3, 0) in observer.senses.visible
    assert (3, 0) in observer.senses.seen
    assert target.uuid in observer.senses.entities
    assert observer.senses.entities[target.uuid] == (3, 0)
    assert observer.senses.paths[(2, 0)] == [(0, 0), (1, 0), (2, 0)]
    assert (3, 0) not in observer.senses.paths


def test_stealth_dc_and_invisibility_filter_visible_entities() -> None:
    """Perceivability removes hidden or invisible targets from observer senses."""
    reset_senses_state(width=6)
    observer = create_senses_actor("Observer", (0, 0), "heroes")
    target = create_senses_actor("Target", (3, 0), "monsters")

    observer.update_entity_senses(max_distance=5)
    assert target.uuid in observer.senses.entities

    target.set_stealth_dc(observer.get_passive_perception() + 1)
    observer.update_entity_senses(max_distance=5)
    assert target.uuid not in observer.senses.entities

    target.set_stealth_dc(1)
    observer.update_entity_senses(max_distance=5)
    assert target.uuid in observer.senses.entities

    target.set_invisible(True)
    observer.update_entity_senses(max_distance=5)
    assert target.uuid not in observer.senses.entities

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]
    observer.update_entity_senses(max_distance=5)
    assert target.uuid in observer.senses.entities


def test_light_source_reveals_a_subscribed_dark_cell() -> None:
    """Reactive light changes can reveal a target in a subscribed dark cell."""
    reset_senses_state(width=6, default_light=LightLevel.DARKNESS)
    observer = create_senses_actor("Observer", (0, 0), "heroes")
    target = create_senses_actor("Target", (3, 0), "monsters")
    observer.update_entity_senses(max_distance=5)

    assert target.uuid not in observer.senses.entities

    get_map().add_light_source((3, 0), bright_radius_feet=5, dim_radius_feet=0)

    assert (3, 0) in observer.senses.visible
    assert (3, 0) in observer.senses.seen
    assert target.uuid in observer.senses.entities


def test_subjective_paths_hide_imperceivable_blockers_until_they_are_seen() -> None:
    """Subjective pathing avoids leaking blockers the observer cannot perceive."""
    reset_senses_state(width=6)
    observer = create_senses_actor("Observer", (0, 0), "heroes")
    blocker = create_senses_actor("Invisible Blocker", (2, 0), "monsters")
    blocker.add_condition(
        Invisible(source_entity_uuid=blocker.uuid, target_entity_uuid=blocker.uuid)
    )

    observer.update_entity_senses(max_distance=5)

    assert blocker.uuid not in observer.senses.entities
    assert (2, 0) in observer.senses.paths
    assert (5, 0) in observer.senses.paths

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]
    observer.update_entity_senses(max_distance=5)

    assert blocker.uuid in observer.senses.entities
    assert (2, 0) not in observer.senses.paths
    assert (5, 0) not in observer.senses.paths


def test_very_bright_light_breaks_hidden() -> None:
    """Hidden owns a stealth DC and very bright light removes the condition."""
    reset_senses_state(width=6, default_light=LightLevel.DARKNESS)
    observer = create_senses_actor("Observer", (0, 0), "heroes")
    hidden = create_senses_actor("Hidden Target", (3, 0), "monsters")
    hidden.add_condition(
        Hidden(
            source_entity_uuid=hidden.uuid,
            target_entity_uuid=hidden.uuid,
            stealth_result=30,
        )
    )
    Entity.update_all_entities_senses(max_distance=5)

    assert "Hidden" in hidden.active_conditions
    assert hidden.stealth_dc == 30
    assert hidden.uuid not in observer.senses.entities

    get_map().add_light_source(
        (3, 0),
        bright_radius_feet=0,
        dim_radius_feet=0,
        very_bright_radius_feet=5,
    )

    assert "Hidden" not in hidden.active_conditions
    assert hidden.stealth_dc is None
    assert hidden.uuid in observer.senses.entities
