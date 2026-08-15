"""Deterministic spatial-effect spike-trap movement regressions."""

from dnd.actions.operations import execute_action, get_available_actions
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events.events_registry import (
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.events.world_events import (
    SpatialEffectChangeEvent,
)
from dnd.types.life import LifeState
from dnd.core.gridmap import get_map
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.content.spike_trap_materialization import materialize_spike_trap_effect
from dnd.spatial.environmental_effects import SpikeTrapController, SpikeTrapGroundEffect
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.spatial.effect_base import SpatialEffect
from tests.engine.support import get_hp, reset_combat_state, set_hp


def _move_target(entity: Entity, position: tuple[int, int]):
    actions = get_available_actions(entity)
    move = next(
        action
        for action in actions.position_actions
        if action.template_name == "Move"
    )
    return next(target for target in move.valid_targets if target.position == position)


def _walk_log_tree(entry: CombatLogEntry):
    yield entry
    for child in entry.sub_entries:
        yield from _walk_log_tree(child)


def test_spike_zone_activation_uses_one_independent_spatial_effect() -> None:
    """One exact effect owns the complete hazard without tile marker identity."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 8)
    positions = {(2, 4), (3, 4), (4, 4)}
    effect = materialize_spike_trap_effect(positions)
    observer = create_skeleton(
        name="Spike Hazard Observer",
        position=(0, 4),
    )

    assert isinstance(effect, SpikeTrapGroundEffect)
    assert SpatialEffect.get_effect(effect.uuid) is effect
    assert effect.affected_positions == positions
    controller = effect.active_conditions["Spike Trap"]
    assert isinstance(controller, SpikeTrapController)
    for position in positions:
        tile = grid.get_tile(*position)
        assert tile is not None
        assert not tile.active_conditions
    assert all(
        grid.is_position_hazardous_for(*position, observer.uuid)
        for position in positions
    )
    assert all(
        grid.get_spatial_effect_uuids_at(position) == {effect.uuid}
        for position in positions
    )
    assert all(
        len(EventQueue.get_spatial_handlers_at(
            position,
            EventType.SPATIAL_ENTITY_ENTERED,
            EventPhase.EFFECT,
        )) == 1
        for position in positions
    )
    assert all(
        len(EventQueue.get_spatial_handlers_at(
            position,
            EventType.SPATIAL_EFFECT_INTERACTION,
            EventPhase.EFFECT,
        )) == 1
        for position in positions
    )

def test_spike_zone_applies_damage_for_each_committed_step() -> None:
    """A multi-cell traversal resolves the shared spatial handler per entry."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 8)
    materialize_spike_trap_effect({(2, 4), (3, 4), (4, 4)})
    walker = create_skeleton(
        name="Spike Step Walker",
        position=(0, 4),
    )
    Entity.update_all_entities_senses()
    hp_before = get_hp(walker)

    with fixed_dice_faces(2, 2, 2, 2, 2, 2):
        result = execute_action(
            walker,
            "Move",
            _move_target(walker, (5, 4)),
            prefer_safe=False,
        )

    assert result is not None
    assert not result.canceled
    assert walker.position == (5, 4)
    damage_taken = hp_before - get_hp(walker)
    if damage_taken != 12:
        raise AssertionError(
            f"expected three deterministic 4-point spike hits, got {damage_taken}",
        )
    assert not walker.senses._paths_dirty
    assert result.combat_log is not None
    assert sum(
        entry.entry_type is CombatLogEntryType.DAMAGE_TAKEN
        for entry in _walk_log_tree(result.combat_log)
    ) == 3


def test_lethal_spike_step_stops_remaining_movement_with_life_state() -> None:
    """Lethal entry stops the path and commits canonical death, not a Dead condition."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 8)
    materialize_spike_trap_effect({(2, 4), (3, 4), (4, 4)})
    walker = create_skeleton(
        name="Lethal Spike Walker",
        position=(0, 4),
    )
    set_hp(walker, 2)
    Entity.update_all_entities_senses()

    with fixed_dice_faces(4, 4):
        result = execute_action(
            walker,
            "Move",
            _move_target(walker, (5, 4)),
            prefer_safe=False,
        )

    assert result is not None
    assert not result.canceled
    assert walker.position == (2, 4)
    assert walker.health.life_state is LifeState.DEAD
    assert "Dead" not in walker.active_conditions
    assert not walker.senses._paths_dirty


def test_hidden_spike_trap_reveals_its_exact_effect_once_when_triggered() -> None:
    """Triggering a hidden network publishes one typed reveal and updates hazard knowledge."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 6, 3)
    effect = materialize_spike_trap_effect({(2, 1), (3, 1)}, stealth_dc=30)
    walker = create_skeleton(name="Trap Trigger", position=(1, 1))
    Entity.update_all_entities_senses()
    cursor = EventQueue.event_cursor()

    assert not grid.is_position_hazardous_for(2, 1, walker.uuid)

    with fixed_dice_faces(1, 1):
        result = execute_action(walker, "Move", _move_target(walker, (2, 1)))

    assert result is not None and not result.canceled
    assert grid.is_position_hazardous_for(2, 1, walker.uuid)
    assert grid.is_position_hazardous_for(3, 1, walker.uuid)
    controller = effect.active_conditions["Spike Trap"]
    assert isinstance(controller, SpikeTrapController)
    assert controller.condition_stealth_dc is None
    assert effect.stealth_dc is None
    reveal_events = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialEffectChangeEvent)
        and event.phase.value == "completion"
        and event.spatial_effect_uuid == effect.uuid
        and event.operation is SpatialEffectChangeOperation.REVEALED
    ]
    assert len(reveal_events) == 1
    assert reveal_events[0].combat_log is not None
    assert reveal_events[0].combat_log.data["operation"] == "revealed"
