"""Deterministic runtime coverage for displaced persistent-zone spell matrices."""

from typing import cast

from dnd.actions import SpellEvent
from dnd.actions_functional import setup_standard_actions
from dnd.conditions import Prone
from dnd.core.base_block import LightLevel, MovementMode
from dnd.core.base_conditions import (
    BaseCondition,
    ConditionCategory,
    HazardFilter,
)
from dnd.core.base_tiles import (
    difficult_terrain_factory,
    wall_factory,
    water_factory,
)
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spells.conjuration import (
    Cloudkill,
    CloudkillZone,
    Grease,
    GreaseZone,
    IncendiaryCloud,
    IncendiaryCloudZone,
    InsectPlague,
    InsectPlagueZone,
    SpiritGuardians,
    SpiritGuardiansZone,
)
from dnd.spells.evocation import GustOfWind, GustOfWindZone
from dnd.spells.transmutation import SpikeGrowth, SpikeGrowthZone
from tests.engine.support import get_hp, has_condition
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def test_movement_mode_pathfinding_preserves_terrain_specific_routes() -> None:
    """Walking, flying, and swimming consume only their own terrain channel."""
    reset_spell_regression_arena(5, 1)
    grid = get_map()
    grid.set_tile(
        2,
        0,
        tile=difficult_terrain_factory((2, 0)),
    )

    walking_distances, walking_paths = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.WALKING,
    )
    flying_distances, flying_paths = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.FLYING,
    )

    assert walking_distances[(4, 0)] == 5
    assert flying_distances[(4, 0)] == 4
    assert walking_paths[(4, 0)] == [
        (0, 0),
        (1, 0),
        (2, 0),
        (3, 0),
        (4, 0),
    ]
    assert flying_paths[(4, 0)] == walking_paths[(4, 0)]

    reset_spell_regression_arena(3, 1)
    grid = get_map()
    grid.set_tile(1, 0, tile=wall_factory((1, 0)))

    wall_flying_distances, _ = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.FLYING,
    )

    assert (2, 0) not in wall_flying_distances

    reset_spell_regression_arena(4, 1)
    grid = get_map()
    for x in range(3):
        grid.set_tile(x, 0, tile=water_factory((x, 0)))

    swimming_distances, swimming_paths = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.SWIMMING,
    )

    assert swimming_distances[(2, 0)] == 2
    assert swimming_paths[(2, 0)] == [(0, 0), (1, 0), (2, 0)]
    assert (3, 0) not in swimming_distances

    land_swimming_distances, _ = grid.compute_paths(
        (3, 0),
        movement_mode=MovementMode.SWIMMING,
    )
    assert land_swimming_distances == {(3, 0): 0}

    reset_spell_regression_arena(3, 1)
    grid = get_map()
    grid.set_tile(1, 0, tile=water_factory((1, 0)))

    water_walking_distances, _ = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.WALKING,
    )

    assert (2, 0) not in water_walking_distances


def test_hazard_filters_and_factions_preserve_exact_requester_semantics() -> None:
    """Hazard ownership and faction filters classify every requester exactly."""
    reset_spell_regression_arena(8, 4)
    grid = get_map()
    caster = create_spell_regression_actor(
        "Hazard Caster",
        (0, 0),
        "heroes",
    )
    ally = create_spell_regression_actor(
        "Hazard Ally",
        (1, 0),
        "heroes",
    )
    enemy = create_spell_regression_actor(
        "Hazard Enemy",
        (2, 0),
        "monsters",
    )
    neutral = create_spell_regression_actor(
        "Hazard Neutral",
        (3, 0),
        "neutral-placeholder",
    )
    neutral.faction = None
    Entity.update_all_entities_senses(max_distance=40)
    assert caster.senses.safe_paths == {}
    tile = grid.get_tile(5, 2)
    assert tile is not None

    ordinary = BaseCondition(
        name="Ordinary Tile Fact",
        source_entity_uuid=caster.uuid,
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
    )
    tile.add_condition(ordinary)
    assert not tile.is_hazardous_for(caster.uuid)
    assert not grid.is_position_hazardous_for(5, 2, caster.uuid)
    tile.remove_condition("Ordinary Tile Fact")

    all_hazard = BaseCondition(
        name="Everyone Hazard",
        source_entity_uuid=caster.uuid,
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ALL,
    )
    tile.add_condition(all_hazard)
    assert tile.is_hazardous_for(caster.uuid)
    assert tile.is_hazardous_for(ally.uuid)
    assert tile.is_hazardous_for(enemy.uuid)
    assert tile.is_hazardous_for(None)
    tile.remove_condition("Everyone Hazard")

    non_source_hazard = BaseCondition(
        name="Non-Source Hazard",
        source_entity_uuid=caster.uuid,
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.NON_SOURCE,
    )
    tile.add_condition(non_source_hazard)
    assert not tile.is_hazardous_for(caster.uuid)
    assert tile.is_hazardous_for(ally.uuid)
    assert tile.is_hazardous_for(enemy.uuid)
    tile.remove_condition("Non-Source Hazard")

    enemy_hazard = BaseCondition(
        name="Enemy Hazard",
        source_entity_uuid=caster.uuid,
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ENEMIES,
    )
    tile.add_condition(enemy_hazard)
    assert not tile.is_hazardous_for(caster.uuid)
    assert not tile.is_hazardous_for(ally.uuid)
    assert tile.is_hazardous_for(enemy.uuid)
    assert tile.is_hazardous_for(neutral.uuid)
    assert grid.is_position_hazardous_for(5, 2, enemy.uuid)
    assert not grid.is_position_hazardous_for(5, 2, ally.uuid)

    assert tile.is_enemy_of(caster.uuid)
    assert not caster.is_enemy_of(ally.uuid)
    assert caster.is_enemy_of(enemy.uuid)
    assert caster.is_enemy_of(neutral.uuid)
    assert neutral.is_enemy_of(caster.uuid)
    assert not caster.is_enemy_of(caster.uuid)


def test_grease_preserves_initial_entry_turn_stand_and_cleanup_rules() -> None:
    """Grease owns its zone while Prone owns turn-scoped auto-standing."""
    reset_spell_regression_arena(14, 10)
    caster = create_spell_regression_actor(
        "Grease Caster",
        (1, 1),
        "heroes",
        spell_slots={1: 1},
    )
    initial = create_spell_regression_actor(
        "Initial Grease Target",
        (5, 5),
        "monsters",
    )
    entrant = create_spell_regression_actor(
        "Grease Entrant",
        (11, 5),
        "monsters",
    )
    setup_standard_actions(initial)
    setup_standard_actions(entrant)
    force_save_result(initial, "dexterity", succeeds=False)
    force_save_result(entrant, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=70)

    with fixed_dice_faces(*([10] * 8)):
        result = Grease(
            source_entity_uuid=caster.uuid,
            end_position=(5, 5),
            cast_at_level=1,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert has_condition(caster, "Grease Zone")
    assert has_condition(caster, "Concentrating")
    zone = cast(GreaseZone, caster.active_conditions["Grease Zone"])
    center_tile = get_map().get_tile(5, 5)
    assert center_tile is not None
    assert center_tile.walking_cost.normalized_score == 2
    assert has_condition(initial, "Prone")

    initial.remove_condition("Prone")
    with fixed_dice_faces(*([10] * 4)):
        initial.on_turn_start()
    assert not has_condition(initial, "Prone")
    assert initial.action_economy.movement.normalized_score == 15

    initial.action_economy.consume(
        "movement",
        initial.action_economy.movement.normalized_score,
    )
    zero_movement_prone = Prone(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=initial.uuid,
    )
    zero_movement_result = initial.add_condition(zero_movement_prone)
    assert zero_movement_result is not None
    assert not zero_movement_result.canceled
    assert has_condition(initial, "Prone")
    assert initial.action_economy.movement.normalized_score == 0

    assert entrant.is_my_turn is False
    with fixed_dice_faces(*([10] * 4)):
        Entity.update_entity_position(entrant, (5, 6))
    assert has_condition(entrant, "Prone")
    assert entrant.action_economy.movement.normalized_score == 30

    caster.remove_condition("Concentrating")
    assert not has_condition(caster, "Concentrating")
    assert not has_condition(caster, "Grease Zone")
    assert center_tile.walking_cost.normalized_score == 1
    assert zone.spatial_handler_uuids == []
    assert zone.event_handlers_uuids == []


def test_cloudkill_preserves_initial_entry_turn_move_and_cleanup_rules() -> None:
    """Cloudkill applies every damage trigger and retires its moving zone."""
    reset_spell_regression_arena(30, 16)
    caster = create_spell_regression_actor(
        "Cloudkill Caster",
        (2, 7),
        "heroes",
        spell_slots={5: 1},
    )
    initial = create_spell_regression_actor(
        "Initial Cloudkill Target",
        (10, 7),
        "monsters",
    )
    entrant = create_spell_regression_actor(
        "Cloudkill Entrant",
        (22, 7),
        "monsters",
    )
    force_save_result(initial, "constitution", succeeds=False)
    force_save_result(entrant, "constitution", succeeds=False)
    Entity.update_all_entities_senses(max_distance=150)
    initial_hp = get_hp(initial)

    with fixed_dice_faces(10, *([4] * 5)):
        result = Cloudkill(
            source_entity_uuid=caster.uuid,
            end_position=(10, 7),
            cast_at_level=5,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert initial_hp - get_hp(initial) == 20
    assert has_condition(caster, "Cloudkill Zone")
    assert has_condition(caster, "Concentrating")
    zone = cast(CloudkillZone, caster.active_conditions["Cloudkill Zone"])
    assert zone.zone_center == (10, 7)
    center_tile = get_map().get_tile(10, 7)
    assert center_tile is not None
    assert center_tile.walking_cost.normalized_score == 1

    entrant_hp = get_hp(entrant)
    with fixed_dice_faces(10, *([4] * 5)):
        Entity.update_entity_position(entrant, (10, 8))
    assert entrant_hp - get_hp(entrant) == 20

    hp_before_turn = get_hp(entrant)
    with fixed_dice_faces(10, *([4] * 5)):
        entrant.on_turn_start()
    assert hp_before_turn - get_hp(entrant) == 20

    caster.on_turn_start()
    assert zone.zone_center == (12, 7)

    caster.remove_condition("Concentrating")
    assert not has_condition(caster, "Concentrating")
    assert not has_condition(caster, "Cloudkill Zone")
    assert zone.spatial_handler_uuids == []
    assert zone.event_handlers_uuids == []

    Entity.update_entity_position(entrant, (22, 7))
    hp_after_cleanup = get_hp(entrant)
    Entity.update_entity_position(entrant, zone.zone_center)
    assert get_hp(entrant) == hp_after_cleanup


def test_spirit_guardians_preserves_faction_damage_slow_follow_and_cleanup() -> None:
    """Spirit Guardians applies its closed enemy-only moving-zone lifecycle."""
    reset_spell_regression_arena(32, 24)
    caster = create_spell_regression_actor(
        "Guardian Caster",
        (10, 10),
        "heroes",
        spell_slots={3: 1},
    )
    initial_enemy = create_spell_regression_actor(
        "Initial Guardian Enemy",
        (11, 10),
        "monsters",
    )
    initial_ally = create_spell_regression_actor(
        "Initial Guardian Ally",
        (11, 11),
        "heroes",
    )
    entrant = create_spell_regression_actor(
        "Guardian Entrant",
        (20, 10),
        "monsters",
    )
    force_save_result(initial_enemy, "wisdom", succeeds=False)
    force_save_result(entrant, "wisdom", succeeds=False)
    Entity.update_all_entities_senses(max_distance=160)
    enemy_hp = get_hp(initial_enemy)
    ally_hp = get_hp(initial_ally)

    with fixed_dice_faces(10, *([4] * 3)):
        result = SpiritGuardians(
            source_entity_uuid=caster.uuid,
            cast_at_level=3,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert enemy_hp - get_hp(initial_enemy) == 12
    assert get_hp(initial_ally) == ally_hp
    assert has_condition(caster, "Spirit Guardians Zone")
    assert has_condition(caster, "Concentrating")
    zone = cast(
        SpiritGuardiansZone,
        caster.active_conditions["Spirit Guardians Zone"],
    )
    assert zone.zone_center == (10, 10)
    assert has_condition(initial_enemy, "Spirit Guardians Triggered")
    assert has_condition(initial_enemy, "Spirit Guardians Slowed")
    assert not has_condition(initial_ally, "Spirit Guardians Triggered")
    assert not has_condition(initial_ally, "Spirit Guardians Slowed")
    assert initial_enemy.action_economy.movement.normalized_score == 15

    hp_after_initial = get_hp(initial_enemy)
    Entity.update_entity_position(initial_enemy, (12, 10))
    assert get_hp(initial_enemy) == hp_after_initial

    entrant_hp = get_hp(entrant)
    with fixed_dice_faces(10, *([4] * 3)):
        Entity.update_entity_position(entrant, (11, 10))
    assert entrant_hp - get_hp(entrant) == 12
    assert has_condition(entrant, "Spirit Guardians Slowed")
    assert entrant.action_economy.movement.normalized_score == 15

    Entity.update_entity_position(entrant, (20, 10))
    assert not has_condition(entrant, "Spirit Guardians Slowed")
    assert entrant.action_economy.movement.normalized_score == 30

    Entity.update_entity_position(caster, (15, 15))
    assert zone.zone_center == (15, 15)

    caster.remove_condition("Concentrating")
    assert not has_condition(caster, "Concentrating")
    assert not has_condition(caster, "Spirit Guardians Zone")
    assert zone.spatial_handler_uuids == []
    assert zone.event_handlers_uuids == []


def test_spike_growth_preserves_hidden_hazard_damage_and_source_immunity() -> None:
    """Spike Growth joins its marker, damage, source immunity, and cleanup."""
    reset_spell_regression_arena(24, 14)
    caster = create_spell_regression_actor(
        "Spike Growth Caster",
        (2, 6),
        "heroes",
        spell_slots={2: 1},
    )
    target = create_spell_regression_actor(
        "Spike Growth Target",
        (17, 6),
        "monsters",
    )
    high_perception = create_spell_regression_actor(
        "High Perception Observer",
        (17, 7),
        "monsters",
        wisdom=30,
    )
    low_perception = create_spell_regression_actor(
        "Low Perception Observer",
        (17, 8),
        "monsters",
        wisdom=8,
    )
    Entity.update_all_entities_senses(max_distance=140)
    target_hp = get_hp(target)

    result = SpikeGrowth(
        source_entity_uuid=caster.uuid,
        end_position=(10, 6),
        cast_at_level=2,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert has_condition(caster, "Spike Growth Zone")
    assert has_condition(caster, "Concentrating")
    zone = cast(
        SpikeGrowthZone,
        caster.active_conditions["Spike Growth Zone"],
    )
    center_tile = get_map().get_tile(10, 6)
    assert center_tile is not None
    assert center_tile.walking_cost.normalized_score == 2
    marker = center_tile.active_conditions["Spike Growth"]
    assert marker.hazard_filter is HazardFilter.NON_SOURCE
    assert marker.condition_stealth_dc == caster.spell_save_dc()
    assert not get_map().is_position_hazardous_for(10, 6, caster.uuid)
    assert get_map().is_position_hazardous_for(
        10,
        6,
        high_perception.uuid,
    )
    assert not get_map().is_position_hazardous_for(
        10,
        6,
        low_perception.uuid,
    )

    with fixed_dice_faces(3, 4):
        Entity.update_entity_position(target, (10, 6))
    assert target_hp - get_hp(target) == 7

    caster_hp = get_hp(caster)
    Entity.update_entity_position(caster, (10, 7))
    assert get_hp(caster) == caster_hp

    caster.remove_condition("Concentrating")
    assert not has_condition(caster, "Concentrating")
    assert not has_condition(caster, "Spike Growth Zone")
    assert "Spike Growth" not in center_tile.active_conditions
    assert center_tile.walking_cost.normalized_score == 1
    assert zone.spatial_handler_uuids == []
    assert not get_map().is_position_hazardous_for(
        10,
        6,
        high_perception.uuid,
    )


def test_gust_of_wind_executes_cast_entry_turn_wall_and_cleanup_edges() -> None:
    """Every zone trigger uses the same save/push rule and retires atomically."""
    reset_spell_regression_arena(30, 14)
    grid = get_map()
    caster = create_spell_regression_actor(
        "Gust Caster",
        (3, 6),
        "heroes",
        spell_slots={2: 1},
    )
    initial = create_spell_regression_actor(
        "Initial Gust Target",
        (7, 6),
        "monsters",
    )
    force_save_result(initial, "strength", succeeds=False)
    Entity.update_all_entities_senses(max_distance=140)

    with fixed_dice_faces(10):
        result = GustOfWind(
            source_entity_uuid=caster.uuid,
            end_position=(20, 6),
            cast_at_level=2,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert initial.position == (10, 6)
    assert has_condition(caster, "Gust of Wind Zone")
    assert has_condition(caster, "Concentrating")
    zone = cast(
        GustOfWindZone,
        caster.active_conditions["Gust of Wind Zone"],
    )
    assert (6, 6) in zone.affected_positions
    zone_tile = grid.get_tile(6, 6)
    assert zone_tile is not None
    assert zone_tile.walking_cost.normalized_score == 2

    entrant = create_spell_regression_actor(
        "Gust Entrant",
        (2, 2),
        "monsters",
    )
    force_save_result(entrant, "strength", succeeds=False)
    saves_before = len(EventQueue.get_events_by_type(EventType.SAVING_THROW))
    pushes_before = len(EventQueue.get_events_by_type(EventType.FORCED_MOVEMENT))
    with fixed_dice_faces(10):
        Entity.update_entity_position(entrant, (6, 6))
    assert entrant.position == (9, 6)
    saves_after = EventQueue.get_events_by_type(EventType.SAVING_THROW)
    pushes_after = EventQueue.get_events_by_type(EventType.FORCED_MOVEMENT)
    assert len(saves_after) - saves_before == 4
    assert [
        event.phase
        for event in pushes_after[pushes_before:]
    ] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert sum(
        event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == entrant.uuid
        for event in saves_after
    ) == 1
    assert sum(
        event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == entrant.uuid
        for event in pushes_after
    ) == 1

    Entity.update_entity_position(entrant, (2, 2))
    assert entrant.position == (2, 2)
    with fixed_dice_faces(10):
        Entity.update_entity_position(entrant, (6, 6))
    assert entrant.position == (9, 6)
    assert sum(
        event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == entrant.uuid
        for event in EventQueue.get_events_by_type(EventType.SAVING_THROW)
    ) == 2
    assert sum(
        event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == entrant.uuid
        for event in EventQueue.get_events_by_type(EventType.FORCED_MOVEMENT)
    ) == 2

    with fixed_dice_faces(10):
        initial.on_turn_start()
    assert initial.position == (13, 6)

    former_entry = (6, 6)
    caster.remove_condition("Concentrating")

    assert not has_condition(caster, "Gust of Wind Zone")
    assert zone_tile.walking_cost.normalized_score == 1
    after_cleanup = create_spell_regression_actor(
        "Post Gust Entrant",
        (2, 3),
        "monsters",
    )
    force_save_result(after_cleanup, "strength", succeeds=False)
    Entity.update_entity_position(after_cleanup, former_entry)
    assert after_cleanup.position == former_entry

    reset_spell_regression_arena(18, 10)
    grid = get_map()
    caster = create_spell_regression_actor(
        "Blocked Gust Caster",
        (5, 5),
        "heroes",
        spell_slots={2: 1},
    )
    blocked = create_spell_regression_actor(
        "Blocked Gust Target",
        (7, 5),
        "monsters",
    )
    grid.set_tile(9, 5, walkable=False, visible=False, name="Wall")
    force_save_result(blocked, "strength", succeeds=False)
    Entity.update_all_entities_senses(max_distance=90)

    with fixed_dice_faces(10):
        blocked_result = GustOfWind(
            source_entity_uuid=caster.uuid,
            end_position=(16, 5),
            cast_at_level=2,
        ).apply()

    assert isinstance(blocked_result, SpellEvent)
    assert not blocked_result.canceled
    assert blocked.position == (8, 5)


def test_insect_plague_executes_initial_entry_turn_reentry_and_cleanup() -> None:
    """Upcast damage and every persistent trigger remain live until cleanup."""
    reset_spell_regression_arena(24, 14)
    caster = create_spell_regression_actor(
        "Plague Caster",
        (2, 6),
        "heroes",
        spell_slots={6: 1},
    )
    failed = create_spell_regression_actor(
        "Initial Plague Failure",
        (10, 6),
        "monsters",
    )
    passed = create_spell_regression_actor(
        "Initial Plague Success",
        (11, 6),
        "monsters",
    )
    force_save_result(failed, "constitution", succeeds=False)
    force_save_result(passed, "constitution", succeeds=True)
    Entity.update_all_entities_senses(max_distance=120)
    failed_hp = get_hp(failed)
    passed_hp = get_hp(passed)

    with fixed_dice_faces(*([4] * 30)):
        result = InsectPlague(
            source_entity_uuid=caster.uuid,
            end_position=(10, 6),
            cast_at_level=6,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert failed_hp - get_hp(failed) == 20
    assert passed_hp - get_hp(passed) == 10
    assert has_condition(caster, "Insect Plague Zone")
    assert has_condition(caster, "Concentrating")
    zone = cast(
        InsectPlagueZone,
        caster.active_conditions["Insect Plague Zone"],
    )
    center_tile = get_map().get_tile(10, 6)
    assert center_tile is not None
    assert center_tile.walking_cost.normalized_score == 2

    entrant = create_spell_regression_actor(
        "Plague Entrant",
        (2, 2),
        "monsters",
    )
    force_save_result(entrant, "constitution", succeeds=False)
    entrant_hp = get_hp(entrant)
    with fixed_dice_faces(*([4] * 10)):
        Entity.update_entity_position(entrant, (10, 7))
    assert entrant_hp - get_hp(entrant) == 20

    hp_before_turn = get_hp(entrant)
    with fixed_dice_faces(*([4] * 10)):
        entrant.on_turn_start()
    assert hp_before_turn - get_hp(entrant) == 20

    hp_before_exit = get_hp(entrant)
    Entity.update_entity_position(entrant, (2, 2))
    assert get_hp(entrant) == hp_before_exit

    with fixed_dice_faces(*([4] * 10)):
        Entity.update_entity_position(entrant, (10, 7))
    assert hp_before_exit - get_hp(entrant) == 20

    caster.remove_condition("Concentrating")

    assert not has_condition(caster, "Insect Plague Zone")
    assert center_tile.walking_cost.normalized_score == 1
    Entity.update_entity_position(entrant, (2, 2))
    hp_after_cleanup = get_hp(entrant)
    Entity.update_entity_position(entrant, (10, 7))
    assert get_hp(entrant) == hp_after_cleanup
    assert zone.spatial_handler_uuids == []
    assert zone.event_handlers_uuids == []


def test_incendiary_cloud_executes_initial_entry_turn_move_and_cleanup() -> None:
    """Fire damage triggers persist across entry/turn and stop with concentration."""
    reset_spell_regression_arena(30, 16)
    caster = create_spell_regression_actor(
        "Incendiary Caster",
        (3, 7),
        "heroes",
        spell_slots={8: 1},
    )
    initial = create_spell_regression_actor(
        "Initial Incendiary Target",
        (11, 7),
        "monsters",
    )
    force_save_result(initial, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=150)
    initial_hp = get_hp(initial)

    with fixed_dice_faces(*([4] * 20)):
        result = IncendiaryCloud(
            source_entity_uuid=caster.uuid,
            end_position=(11, 7),
            cast_at_level=8,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert initial_hp - get_hp(initial) == 40
    assert has_condition(caster, "Incendiary Cloud Zone")
    assert has_condition(caster, "Concentrating")
    zone = cast(
        IncendiaryCloudZone,
        caster.active_conditions["Incendiary Cloud Zone"],
    )
    old_center = zone.zone_center
    old_only_position = (old_center[0] - 4, old_center[1])
    added_position = (old_center[0] + 6, old_center[1])
    old_only_tile = get_map().get_tile(*old_only_position)
    added_tile = get_map().get_tile(*added_position)
    assert old_only_tile is not None
    assert added_tile is not None
    assert old_only_tile.resolved_light_level == LightLevel.DARKNESS
    assert "Incendiary Cloud" in old_only_tile.active_conditions
    assert added_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert "Incendiary Cloud" not in added_tile.active_conditions

    entrant = create_spell_regression_actor(
        "Incendiary Entrant",
        (2, 2),
        "monsters",
    )
    force_save_result(entrant, "dexterity", succeeds=False)
    entrant_hp = get_hp(entrant)
    with fixed_dice_faces(*([4] * 20)):
        Entity.update_entity_position(entrant, (11, 8))
    assert entrant_hp - get_hp(entrant) == 40

    hp_before_turn = get_hp(entrant)
    with fixed_dice_faces(*([4] * 20)):
        entrant.on_turn_start()
    assert hp_before_turn - get_hp(entrant) == 40

    caster.on_turn_start()
    assert zone.zone_center != old_center
    assert old_only_position not in zone.affected_positions
    assert added_position in zone.affected_positions
    assert old_only_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert "Incendiary Cloud" not in old_only_tile.active_conditions
    assert added_tile.resolved_light_level == LightLevel.DARKNESS
    assert "Incendiary Cloud" in added_tile.active_conditions

    caster.remove_condition("Concentrating")

    assert not has_condition(caster, "Incendiary Cloud Zone")
    assert added_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert "Incendiary Cloud" not in added_tile.active_conditions
    Entity.update_entity_position(entrant, (2, 2))
    hp_after_cleanup = get_hp(entrant)
    Entity.update_entity_position(entrant, zone.zone_center)
    assert get_hp(entrant) == hp_after_cleanup
    assert zone.spatial_handler_uuids == []
    assert zone.event_handlers_uuids == []
