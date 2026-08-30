"""Regressions for authoritative, entity-owned life-state derivation."""

from uuid import uuid4

from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.life_types import LifeState
from dnd.core.creature_types import DamageType
from dnd.entity import Entity, EntityConfig
from dnd.core.gridmap import get_map
from tests.engine.test_combat_actions import (
    reset_core_action_state,
    strong_entity,
)


def _raw_configured_entity(name: str, state: LifeState) -> Entity:
    """Create an entity with no action/rules bootstrap calls."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=12),
            dexterity=AbilityConfig(ability_score=12),
            constitution=AbilityConfig(ability_score=12),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            life_state=state,
            hit_dices=[
                HitDiceConfig(
                    hit_dice_value=8,
                    hit_dice_count=2,
                    mode="maximums",
                )
            ],
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        position=(4, 4),
        faction="heroes",
        uses_death_saves=True,
    )
    return Entity.create(source_entity_uuid=uuid4(), name=name, config=config)


def test_raw_entity_lifecycle_never_depends_on_standard_action_setup() -> None:
    """A directly-created entity receives derived dying capabilities."""
    reset_core_action_state()
    source = strong_entity("Source", (3, 4), "monsters", setup_actions=False)
    target = strong_entity(
        "Raw Target",
        (4, 4),
        "heroes",
        uses_death_saves=True,
        setup_actions=False,
    )

    target.receive_damage(
        target.get_normal_hp(),
        DamageType.SLASHING,
        source.uuid,
    )

    assert target.health.life_state is LifeState.DYING
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert target.senses.visual_access.normalized_score == 0
    assert not target.can_take_actions()
    assert "Dying" not in target.active_conditions

    before = (
        target.action_economy.action_permission.normalized_score,
        target.action_economy.movement.normalized_score,
        target.senses.visual_access.normalized_score,
    )
    setup_standard_actions(target)
    assert before == (
        target.action_economy.action_permission.normalized_score,
        target.action_economy.movement.normalized_score,
        target.senses.visual_access.normalized_score,
    )


def test_initial_stable_and_dead_states_are_reconciled_during_creation() -> None:
    """Configured non-alive states start at zero HP with correct capabilities."""
    reset_core_action_state()
    stable = _raw_configured_entity("Initially Stable", LifeState.STABLE)
    dead = _raw_configured_entity("Initially Dead", LifeState.DEAD)

    assert stable.get_normal_hp() == 0
    assert stable.action_economy.action_permission.normalized_score == 0
    assert stable.senses.visual_access.normalized_score == 0
    assert stable.blocks_walking() is True

    assert dead.get_normal_hp() == 0
    assert dead.action_economy.action_permission.normalized_score == 0
    assert dead.senses.visual_access.normalized_score == 0
    assert dead.blocks_walking() is False
    stable.update_entity_senses()
    assert dead.uuid not in stable.senses.entities


def test_dead_rejects_ordinary_healing_and_revive_restores_normal_hp_only() -> None:
    """Only explicit revival crosses DEAD to ALIVE, independent of temp HP."""
    reset_core_action_state()
    target = strong_entity("Revival Target", (4, 4), "heroes", setup_actions=False)
    target.receive_instant_death(target.uuid, source_description="test")
    target.health.add_temporary_hit_points(7, target.uuid)

    healed = target.receive_healing(5, target.uuid)

    assert healed == 0
    assert target.health.life_state is LifeState.DEAD
    assert target.get_normal_hp() == 0
    assert target.senses.visual_access.normalized_score == 0

    assert target.revive(hit_points=2)
    assert target.health.life_state is LifeState.ALIVE
    assert target.get_normal_hp() == 2
    assert target.health.temporary_hit_points.normalized_score == 7
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.senses.visual_access.normalized_score == 1


def test_death_suppresses_lights_reversibly_and_preserves_other_owners() -> None:
    """Death owns one composable light-suppression token, not the light source."""
    reset_core_action_state()
    target = strong_entity("Light Bearer", (4, 4), "heroes", setup_actions=False)
    grid = get_map()
    light_uuid = grid.add_light_source(
        target.position,
        bright_radius_feet=10,
        dim_radius_feet=10,
        anchor_uuid=target.uuid,
    )
    assert grid._light_sources[light_uuid].affected_tiles

    grid.set_block_light_suppressed(target.uuid, "other.effect", True)
    target.receive_instant_death(target.uuid, source_description="test")

    source = grid._light_sources[light_uuid]
    assert source.is_active
    assert source.affected_tiles == {}
    assert light_uuid in target.get_attached_light_sources()

    assert target.revive()
    assert source.affected_tiles == {}

    grid.set_block_light_suppressed(target.uuid, "other.effect", False)
    assert source.affected_tiles


def test_light_desired_state_and_nonblocking_survive_death_and_revival() -> None:
    """Revival does not overwrite independent light or collision state."""
    reset_core_action_state()
    target = strong_entity("Independent State", (4, 4), "heroes", setup_actions=False)
    target.non_blocking = True
    grid = get_map()
    inactive_uuid = grid.add_light_source(
        target.position,
        bright_radius_feet=5,
        dim_radius_feet=5,
        anchor_uuid=target.uuid,
    )
    grid.toggle_light_source(inactive_uuid, False)

    target.receive_instant_death(target.uuid, source_description="test")
    added_while_dead = grid.add_light_source(
        target.position,
        bright_radius_feet=5,
        dim_radius_feet=5,
        anchor_uuid=target.uuid,
    )
    assert grid._light_sources[added_while_dead].affected_tiles == {}

    assert target.revive()
    assert target.non_blocking is True
    assert grid._light_sources[inactive_uuid].is_active is False
    assert grid._light_sources[inactive_uuid].affected_tiles == {}
    assert grid._light_sources[added_while_dead].affected_tiles


def test_revival_reintroduces_entity_to_incremental_senses() -> None:
    """Dead removal and revival re-addition both use perceivability events."""
    reset_core_action_state()
    observer = strong_entity("Observer", (3, 4), "heroes", setup_actions=False)
    target = strong_entity("Observed", (4, 4), "monsters", setup_actions=False)
    Entity.update_all_entities_senses(max_distance=20)
    assert target.uuid in observer.senses.entities

    target.receive_instant_death(target.uuid, source_description="test")
    assert target.uuid not in observer.senses.entities

    assert target.revive()
    assert target.uuid in observer.senses.entities
