"""Tutorial tests for perception, light, stealth, and invisibility."""

from uuid import uuid4

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.conditions import Hidden, Invisible
from dnd.actions_functional import execute_by_index
from dnd.core.base_block import BaseBlock, LightLevel, SenseMode, SensesType
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.core.events import (
    EventPhase,
    EventQueue,
    EventType,
    SensoryUpdateEvent,
    SensoryUpdateReason,
)
from dnd.core.gridmap import GridMap, get_map
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from tests.manual.authored_encounter_support import (
    assemble_authored_encounter,
)


def reset_perception_tutorial_state(
    width: int = 8,
    height: int = 3,
    default_light: LightLevel = LightLevel.BRIGHT_LIGHT,
) -> None:
    """Clear global state and create a tutorial grid with one light level."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    for tile in grid.get_all_tiles().values():
        tile.default_light = default_light


def create_perception_actor(
    name: str,
    position: tuple[int, int],
    *,
    wisdom: int = 10,
    faction: str | None = None,
) -> Entity:
    """Create a plain actor for perception examples."""
    actor_id = uuid4()
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=12),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=wisdom),
            charisma=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(hit_dice_value=8, hit_dice_count=2, mode="maximums")
            ]
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    return Entity.create(source_entity_uuid=actor_id, name=name, config=config)


def completed_sensory_updates(observer) -> list[SensoryUpdateEvent]:
    """Return completed sensory update events for one observer."""
    return [
        event
        for event in EventQueue.get_events_by_type(EventType.SENSORY_UPDATE)
        if isinstance(event, SensoryUpdateEvent)
        and event.phase == EventPhase.COMPLETION
        and event.observer_uuid == observer.uuid
    ]


def test_sensory_delta_is_one_completed_observational_event() -> None:
    """A sensory delta retains causality without empty mutable phases."""
    reset_perception_tutorial_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_perception_actor("Observer", position=(0, 0), faction="heroes")
    create_perception_actor("Target", position=(3, 0), faction="monsters")
    observer.update_entity_senses(max_distance=5)
    source_cursor = EventQueue.event_cursor()

    get_map().add_light_source((3, 0), bright_radius_feet=5, dim_radius_feet=0)
    sensory_events = [
        event
        for _, event in EventQueue.iter_events_since(source_cursor)
        if isinstance(event, SensoryUpdateEvent)
    ]

    assert sensory_events
    assert {event.phase for event in sensory_events} == {EventPhase.COMPLETION}
    assert len(sensory_events) == len({event.lineage_uuid for event in sensory_events})
    assert all(event.parent_lineage is not None for event in sensory_events)
    observer_update = next(
        event for event in sensory_events if event.observer_uuid == observer.uuid
    )
    assert observer_update.observer_position == observer.position
    assert observer_update.effective_light_levels == (
        observer.senses.get_effective_light_levels(observer.uuid)
    )


def test_light_change_emits_subjective_levels_without_visibility_membership_delta() -> None:
    """A brighter visible tile still reaches clients when FOV membership is stable."""
    reset_perception_tutorial_state(width=5, height=1, default_light=LightLevel.DIM_LIGHT)
    observer = create_perception_actor("Observer", position=(0, 0), faction="heroes")
    observer.update_entity_senses(max_distance=5)
    visible_before = set(observer.senses.visible)
    source_cursor = EventQueue.event_cursor()

    get_map().add_light_source((2, 0), bright_radius_feet=5, dim_radius_feet=0)

    updates = [
        event
        for _, event in EventQueue.iter_events_since(source_cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
    ]
    assert set(observer.senses.visible) == visible_before
    assert updates
    assert updates[-1].visible_cells_added == []
    assert updates[-1].visible_cells_removed == []
    assert updates[-1].effective_light_levels == (
        observer.senses.get_effective_light_levels(observer.uuid)
    )


def test_movement_end_preserves_contacts_revealed_by_carried_light() -> None:
    """A movement-end refresh does not reuse visibility from before light moved."""
    arena = assemble_authored_encounter("standard_skeleton_doors")
    observer = arena.hero
    updates_before = len(completed_sensory_updates(observer))
    actions = observer.get_available_actions()
    movement = next(
        action
        for action in actions.position_actions
        if action.template_name == "Move"
    )
    destination = next(
        target
        for target in movement.valid_targets
        if target.position == (7, 12)
    )

    result = execute_by_index(
        observer,
        movement.template_name,
        destination.index,
        available=actions,
    )
    movement_updates = completed_sensory_updates(observer)[updates_before:]
    added_contacts = {
        entity_uuid
        for update in movement_updates
        for entity_uuid in update.visible_entities_added
    }
    removed_contacts = {
        entity_uuid
        for update in movement_updates
        for entity_uuid in update.visible_entities_removed
    }
    expected_visible = {entity.uuid for entity in arena.monsters[1:]}
    warm_entities = dict(observer.senses.entities)
    observer.update_entity_senses(max_distance=20)
    cold_entities = dict(observer.senses.entities)

    assert result is not None
    assert not result.canceled
    assert expected_visible <= added_contacts
    assert expected_visible <= set(warm_entities)
    assert not expected_visible & removed_contacts
    assert warm_entities == cold_entities


def test_first_perception_example_prints_visible_observer_knowledge(capsys) -> None:
    """One observer prints visibility before and after a light change."""
    reset_perception_tutorial_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_perception_actor("Observer", position=(0, 0), faction="heroes")
    target = create_perception_actor("Target", position=(3, 0), faction="monsters")
    observer.update_entity_senses(max_distance=5)

    subscriptions = get_map().get_entity_subscriptions(observer.uuid)
    before = {
        "subscribed": (3, 0) in subscriptions,
        "adjacent_visible": (1, 0) in observer.senses.visible,
        "target_cell_visible": (3, 0) in observer.senses.visible,
        "target_visible": target.uuid in observer.senses.entities,
        "target_cell_seen": (3, 0) in observer.senses.seen,
    }

    get_map().add_light_source((3, 0), bright_radius_feet=5, dim_radius_feet=0)
    light_updates = [
        event
        for event in EventQueue.get_events_by_type(EventType.SENSORY_UPDATE)
        if isinstance(event, SensoryUpdateEvent)
        and event.phase == EventPhase.COMPLETION
        and event.observer_uuid == observer.uuid
        and event.update_reason == SensoryUpdateReason.LIGHT
    ]
    after = {
        "target_cell_visible": (3, 0) in observer.senses.visible,
        "target_visible": target.uuid in observer.senses.entities,
        "target_cell_seen": (3, 0) in observer.senses.seen,
        "update_cell": any(
            (3, 0) in event.visible_cells_added for event in light_updates
        ),
        "update_target": any(
            target.uuid in event.visible_entities_added for event in light_updates
        ),
    }
    readout_lines = [
        f"observer: {observer.name}",
        f"target cell subscribed: {before['subscribed']}",
        f"adjacent visible in darkness: {before['adjacent_visible']}",
        f"target cell visible before light: {before['target_cell_visible']}",
        f"target visible before light: {before['target_visible']}",
        f"target cell seen before light: {before['target_cell_seen']}",
        f"target cell visible after light: {after['target_cell_visible']}",
        f"target visible after light: {after['target_visible']}",
        f"target cell seen after light: {after['target_cell_seen']}",
        f"light update added cell: {after['update_cell']}",
        f"light update added target: {after['update_target']}",
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "observer: Observer",
        "target cell subscribed: True",
        "adjacent visible in darkness: True",
        "target cell visible before light: False",
        "target visible before light: False",
        "target cell seen before light: False",
        "target cell visible after light: True",
        "target visible after light: True",
        "target cell seen after light: True",
        "light update added cell: True",
        "light update added target: True",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_senses_subscribe_to_geometric_fov_before_light_filtering(capsys) -> None:
    """Geometric FOV subscriptions are broader than visible lit cells."""
    reset_perception_tutorial_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_perception_actor("Observer", position=(0, 0), faction="heroes")
    target = create_perception_actor("Target", position=(3, 0), faction="monsters")

    observer.update_entity_senses(max_distance=5)

    subscriptions = get_map().get_entity_subscriptions(observer.uuid)

    assert (3, 0) in subscriptions
    assert (3, 0) not in observer.senses.visible
    assert (1, 0) in observer.senses.visible
    assert target.uuid not in observer.senses.entities
    assert (3, 0) not in observer.senses.seen

    geometry_lines = [
        f"subscribed target cell: {(3, 0) in subscriptions}",
        f"visible adjacent cell: {(1, 0) in observer.senses.visible}",
        f"visible target cell: {(3, 0) in observer.senses.visible}",
        f"target in visible entities: {target.uuid in observer.senses.entities}",
        f"target cell remembered: {(3, 0) in observer.senses.seen}",
    ]

    print("\n".join(geometry_lines))

    expected_geometry_lines = [
        "subscribed target cell: True",
        "visible adjacent cell: True",
        "visible target cell: False",
        "target in visible entities: False",
        "target cell remembered: False",
    ]
    assert geometry_lines == expected_geometry_lines
    assert capsys.readouterr().out.splitlines() == expected_geometry_lines


def test_shadowcast_memoizes_blocking_checks_within_one_fov_query(monkeypatch) -> None:
    """One FOV query resolves each observer-specific blocking cell once."""
    reset_perception_tutorial_state(width=20, height=20)
    grid = get_map()
    original_is_blocking = grid.is_blocking
    checked_positions: list[tuple[int, int]] = []

    def record_is_blocking(x: int, y: int, requesting_entity_uuid=None) -> bool:
        checked_positions.append((x, y))
        return original_is_blocking(x, y, requesting_entity_uuid)

    monkeypatch.setattr(grid, "is_blocking", record_is_blocking)

    visible = grid.compute_fov((10, 10), max_distance=8)

    assert visible
    assert len(checked_positions) == len(set(checked_positions))
    assert all(
        max(abs(x - 10), abs(y - 10)) <= 8
        for x, y in checked_positions
    )


def test_special_senses_change_subjective_light(capsys) -> None:
    """Darkvision, Devil's Sight, and truesight alter effective light differently."""
    reset_perception_tutorial_state(width=16, height=1)
    observer = create_perception_actor("Observer", position=(0, 0))
    grid = get_map()
    far_dark = grid.get_tile(15, 0)
    near_dark = grid.get_tile(10, 0)
    dim = grid.get_tile(5, 0)
    magical = grid.get_tile(2, 0)
    assert far_dark is not None
    assert near_dark is not None
    assert dim is not None
    assert magical is not None
    far_dark.default_light = LightLevel.DARKNESS
    near_dark.default_light = LightLevel.DARKNESS
    dim.default_light = LightLevel.DIM_LIGHT
    magical.add_obscurement(uuid4(), LightLevel.MAGICAL_DARKNESS, fire_event=False)

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
    ]

    assert far_dark.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.DARKNESS
    assert near_dark.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.DIM_LIGHT
    assert dim.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.BRIGHT_LIGHT
    assert magical.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.MAGICAL_DARKNESS
    darkvision_state = (
        far_dark.get_effective_light_for(observer.uuid, (0, 0)),
        near_dark.get_effective_light_for(observer.uuid, (0, 0)),
        dim.get_effective_light_for(observer.uuid, (0, 0)),
        magical.get_effective_light_for(observer.uuid, (0, 0)),
    )

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.DEVILS_SIGHT, range_feet=120)
    ]

    assert magical.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.BRIGHT_LIGHT
    devils_sight_state = magical.get_effective_light_for(observer.uuid, (0, 0))

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]

    assert magical.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.BRIGHT_LIGHT
    truesight_state = magical.get_effective_light_for(observer.uuid, (0, 0))

    special_lines = [
        f"darkvision far darkness: {darkvision_state[0].name}",
        f"darkvision near darkness: {darkvision_state[1].name}",
        f"darkvision dim light: {darkvision_state[2].name}",
        f"darkvision magical darkness: {darkvision_state[3].name}",
        f"devil's sight magical darkness: {devils_sight_state.name}",
        f"truesight magical darkness: {truesight_state.name}",
    ]

    print("\n".join(special_lines))

    expected_special_lines = [
        "darkvision far darkness: DARKNESS",
        "darkvision near darkness: DIM_LIGHT",
        "darkvision dim light: BRIGHT_LIGHT",
        "darkvision magical darkness: MAGICAL_DARKNESS",
        "devil's sight magical darkness: BRIGHT_LIGHT",
        "truesight magical darkness: BRIGHT_LIGHT",
    ]
    assert special_lines == expected_special_lines
    assert capsys.readouterr().out.splitlines() == expected_special_lines


def test_light_changes_reveal_subscribed_cells_reactively(capsys) -> None:
    """A light event can update subscribed observer senses without a bulk refresh."""
    reset_perception_tutorial_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_perception_actor("Observer", position=(0, 0), faction="heroes")
    target = create_perception_actor("Target", position=(3, 0), faction="monsters")
    observer.update_entity_senses(max_distance=5)

    assert target.uuid not in observer.senses.entities
    before = {
        "target_visible": target.uuid in observer.senses.entities,
        "cell_visible": (3, 0) in observer.senses.visible,
        "cell_seen": (3, 0) in observer.senses.seen,
    }

    get_map().add_light_source((3, 0), bright_radius_feet=5, dim_radius_feet=0)

    assert (3, 0) in observer.senses.visible
    assert (3, 0) in observer.senses.seen
    assert target.uuid in observer.senses.entities

    light_updates = [
        event
        for event in completed_sensory_updates(observer)
        if event.update_reason == SensoryUpdateReason.LIGHT
    ]
    assert light_updates
    assert any((3, 0) in event.visible_cells_added for event in light_updates)
    assert any(target.uuid in event.visible_entities_added for event in light_updates)
    after = {
        "target_visible": target.uuid in observer.senses.entities,
        "cell_visible": (3, 0) in observer.senses.visible,
        "cell_seen": (3, 0) in observer.senses.seen,
        "added_cell": any(
            (3, 0) in event.visible_cells_added for event in light_updates
        ),
        "added_target": any(
            target.uuid in event.visible_entities_added for event in light_updates
        ),
        "update_count": len(light_updates),
    }

    reactive_lines = [
        (
            "before light: "
            f"target_visible={before['target_visible']}, "
            f"cell_visible={before['cell_visible']}, "
            f"cell_seen={before['cell_seen']}"
        ),
        (
            "after light: "
            f"target_visible={after['target_visible']}, "
            f"cell_visible={after['cell_visible']}, "
            f"cell_seen={after['cell_seen']}"
        ),
        (
            "light updates: "
            f"count={after['update_count']}, "
            f"added_cell={after['added_cell']}, "
            f"added_target={after['added_target']}"
        ),
    ]

    print("\n".join(reactive_lines))

    expected_reactive_lines = [
        "before light: target_visible=False, cell_visible=False, cell_seen=False",
        "after light: target_visible=True, cell_visible=True, cell_seen=True",
        "light updates: count=1, added_cell=True, added_target=True",
    ]
    assert reactive_lines == expected_reactive_lines
    assert capsys.readouterr().out.splitlines() == expected_reactive_lines


def test_stealth_and_invisibility_filter_perceivable_entities(capsys) -> None:
    """Stealth DC and invisibility are observer-relative perceivability filters."""
    reset_perception_tutorial_state(width=5, height=1)
    observer = create_perception_actor("Observer", position=(0, 0), faction="heroes")
    target = create_perception_actor("Target", position=(2, 0), faction="monsters")
    truesight = create_perception_actor("Truesight", position=(4, 0), faction="heroes")
    truesight.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]
    Entity.update_all_entities_senses(max_distance=5)

    assert target.uuid in observer.senses.entities
    initial_state = (
        target.uuid in observer.senses.entities,
        observer.get_passive_perception(),
    )

    target.set_stealth_dc(observer.get_passive_perception() + 1)

    assert not target.is_perceivable_by(observer.uuid)
    assert target.uuid not in observer.senses.entities
    assert any(
        target.uuid in event.visible_entities_removed
        for event in completed_sensory_updates(observer)
    )
    hidden_state = (
        target.stealth_dc,
        target.is_perceivable_by(observer.uuid),
        target.uuid in observer.senses.entities,
        any(
            target.uuid in event.visible_entities_removed
            for event in completed_sensory_updates(observer)
        ),
    )

    target.set_stealth_dc(1)

    assert target.is_perceivable_by(observer.uuid)
    assert target.uuid in observer.senses.entities
    revealed_state = (
        target.stealth_dc,
        target.is_perceivable_by(observer.uuid),
        target.uuid in observer.senses.entities,
    )

    target.set_invisible(True)

    assert not target.is_perceivable_by(observer.uuid)
    assert target.is_perceivable_by(truesight.uuid)
    assert target.uuid not in observer.senses.entities
    assert target.uuid in truesight.senses.entities
    invisible_state = (
        target.is_perceivable_by(observer.uuid),
        target.is_perceivable_by(truesight.uuid),
        target.uuid in observer.senses.entities,
        target.uuid in truesight.senses.entities,
    )

    stealth_lines = [
        f"initial ordinary sight: visible={initial_state[0]}, passive={initial_state[1]}",
        (
            "high stealth dc: "
            f"dc={hidden_state[0]}, "
            f"perceivable={hidden_state[1]}, "
            f"visible={hidden_state[2]}, "
            f"removal_event={hidden_state[3]}"
        ),
        (
            "low stealth dc: "
            f"dc={revealed_state[0]}, "
            f"perceivable={revealed_state[1]}, "
            f"visible={revealed_state[2]}"
        ),
        (
            "invisible target: "
            f"ordinary={invisible_state[0]}, "
            f"truesight={invisible_state[1]}, "
            f"ordinary_list={invisible_state[2]}, "
            f"truesight_list={invisible_state[3]}"
        ),
    ]

    print("\n".join(stealth_lines))

    expected_stealth_lines = [
        "initial ordinary sight: visible=True, passive=10",
        "high stealth dc: dc=11, perceivable=False, visible=False, removal_event=True",
        "low stealth dc: dc=1, perceivable=True, visible=True",
        "invisible target: ordinary=False, truesight=True, ordinary_list=False, truesight_list=True",
    ]
    assert stealth_lines == expected_stealth_lines
    assert capsys.readouterr().out.splitlines() == expected_stealth_lines


def test_subjective_paths_do_not_leak_imperceivable_blockers(capsys) -> None:
    """Subjective pathfinding ignores blockers the observer cannot perceive."""
    reset_perception_tutorial_state(width=5, height=1)
    observer = create_perception_actor("Observer", position=(0, 0), faction="heroes")
    invisible = create_perception_actor("Invisible", position=(2, 0), faction="monsters")
    invisible.add_condition(
        Invisible(source_entity_uuid=invisible.uuid, target_entity_uuid=invisible.uuid)
    )

    Entity.update_all_entities_senses(max_distance=5)

    assert invisible.uuid not in observer.senses.entities
    assert (2, 0) in observer.senses.paths
    assert (4, 0) in observer.senses.paths
    unknown_state = (
        invisible.uuid in observer.senses.entities,
        (2, 0) in observer.senses.paths,
        (4, 0) in observer.senses.paths,
    )

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]
    Entity.update_all_entities_senses(max_distance=5)

    assert invisible.uuid in observer.senses.entities
    assert (2, 0) not in observer.senses.paths
    assert (4, 0) not in observer.senses.paths
    known_state = (
        invisible.uuid in observer.senses.entities,
        (2, 0) in observer.senses.paths,
        (4, 0) in observer.senses.paths,
    )

    path_lines = [
        (
            "before truesight: "
            f"blocker_visible={unknown_state[0]}, "
            f"blocker_cell_path={unknown_state[1]}, "
            f"beyond_blocker_path={unknown_state[2]}"
        ),
        (
            "after truesight: "
            f"blocker_visible={known_state[0]}, "
            f"blocker_cell_path={known_state[1]}, "
            f"beyond_blocker_path={known_state[2]}"
        ),
    ]

    print("\n".join(path_lines))

    expected_path_lines = [
        "before truesight: blocker_visible=False, blocker_cell_path=True, beyond_blocker_path=True",
        "after truesight: blocker_visible=True, blocker_cell_path=False, beyond_blocker_path=False",
    ]
    assert path_lines == expected_path_lines
    assert capsys.readouterr().out.splitlines() == expected_path_lines


def test_hidden_and_invisible_flags_stack_independently(capsys) -> None:
    """Removing Hidden does not reveal a still-invisible entity to ordinary sight."""
    reset_perception_tutorial_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_perception_actor("Observer", position=(0, 0), faction="heroes")
    truesight = create_perception_actor("Truesight", position=(5, 0), faction="heroes")
    target = create_perception_actor("Stacked Target", position=(3, 0), faction="monsters")
    truesight.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]

    target.add_condition(Invisible(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    target.add_condition(
        Hidden(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            stealth_result=max(
                observer.get_passive_perception(),
                truesight.get_passive_perception(),
            )
            + 10,
        )
    )
    Entity.update_all_entities_senses(max_distance=5)

    assert target.is_invisible is True
    assert target.stealth_dc is not None
    assert "Hidden" in target.active_conditions
    assert "Invisible" in target.active_conditions
    assert target.uuid not in observer.senses.entities
    assert target.uuid not in truesight.senses.entities
    before = (
        target.is_invisible,
        target.stealth_dc is not None,
        "Hidden" in target.active_conditions,
        "Invisible" in target.active_conditions,
        target.uuid in observer.senses.entities,
        target.uuid in truesight.senses.entities,
    )

    get_map().add_light_source(
        (3, 0),
        bright_radius_feet=0,
        dim_radius_feet=0,
        very_bright_radius_feet=5,
    )

    assert "Hidden" not in target.active_conditions
    assert "Invisible" in target.active_conditions
    assert target.stealth_dc is None
    assert target.is_invisible is True
    assert target.uuid not in observer.senses.entities
    assert target.uuid in truesight.senses.entities
    after = (
        "Hidden" in target.active_conditions,
        "Invisible" in target.active_conditions,
        target.stealth_dc,
        target.is_invisible,
        target.uuid in observer.senses.entities,
        target.uuid in truesight.senses.entities,
    )

    stacked_lines = [
        (
            "before reveal: "
            f"invisible={before[0]}, "
            f"hidden={before[2]}, "
            f"stealth_dc_set={before[1]}, "
            f"observer_visible={before[4]}, "
            f"truesight_visible={before[5]}"
        ),
        (
            "after bright reveal: "
            f"hidden={after[0]}, "
            f"invisible={after[1]}, "
            f"stealth_dc={after[2]}, "
            f"still_invisible={after[3]}"
        ),
        (
            "after reveal visibility: "
            f"observer_visible={after[4]}, "
            f"truesight_visible={after[5]}"
        ),
    ]

    print("\n".join(stacked_lines))

    expected_stacked_lines = [
        "before reveal: invisible=True, hidden=True, stealth_dc_set=True, observer_visible=False, truesight_visible=False",
        "after bright reveal: hidden=False, invisible=True, stealth_dc=None, still_invisible=True",
        "after reveal visibility: observer_visible=False, truesight_visible=True",
    ]
    assert stacked_lines == expected_stacked_lines
    assert capsys.readouterr().out.splitlines() == expected_stacked_lines
