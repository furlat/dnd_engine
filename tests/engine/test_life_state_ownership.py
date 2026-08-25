"""Regressions for authoritative, entity-owned life-state derivation."""

from uuid import uuid4

from dnd.actions.operations import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import (
    EquipmentConfig,
)
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.types.life import LifeState
from dnd.types.damage import DamageType
from dnd.types.world import LightLevel
from dnd.entities.entity import Entity, EntityConfig
from dnd.entities.entity_creation import compose_entity, create_entity
from dnd.core.gridmap import get_map
from dnd.game import Game
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
    entity = create_entity(
        uuid4(),
        entity_kind_id="test.life_state_entity",
        name=name,
        config=config,
    )
    compose_entity(entity)
    return entity


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
    assert dead.appears_in_entity_contacts() is False


def test_dead_rejects_ordinary_healing_and_revive_restores_normal_hp_only() -> None:
    """Only explicit revival crosses DEAD to ALIVE, independent of temp HP."""
    reset_core_action_state()
    target = strong_entity("Revival Target", (4, 4), "heroes", setup_actions=False)
    target.receive_instant_death(target.uuid, source_description="test")
    target.grant_temporary_hit_points(7, target.uuid)

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


def test_world_presence_and_death_light_suppressions_compose_through_restore() -> None:
    """World absence and death each own a light token through relocation."""
    reset_core_action_state()
    target = strong_entity("World-presence light bearer", (4, 4), "heroes", setup_actions=False)
    grid = get_map()
    old_position = target.position
    new_position = (12, 12)
    grid.set_tile_base_light(old_position, LightLevel.DARKNESS)
    grid.set_tile_base_light(new_position, LightLevel.DARKNESS)
    light_uuid = grid.add_light_source(
        old_position,
        bright_radius_feet=5,
        dim_radius_feet=0,
        anchor_uuid=target.uuid,
    )
    assert light_uuid in target.get_attached_light_sources()
    assert grid.get_tile(*old_position).resolved_light_level is LightLevel.BRIGHT_LIGHT

    target.suspend_spatial_presence()
    assert grid.get_tile(*old_position).resolved_light_level is LightLevel.DARKNESS

    target.receive_instant_death(target.uuid, source_description="test")
    target.restore_spatial_presence(new_position)
    assert grid.get_tile(*old_position).resolved_light_level is LightLevel.DARKNESS
    assert grid.get_tile(*new_position).resolved_light_level is LightLevel.DARKNESS

    assert target.revive()
    assert grid.get_tile(*old_position).resolved_light_level is LightLevel.DARKNESS
    assert grid.get_tile(*new_position).resolved_light_level is LightLevel.BRIGHT_LIGHT


def test_undeployed_attached_light_stays_absent_until_public_deploy() -> None:
    """An attached source created before deployment honors world absence."""
    reset_core_action_state()
    entity = _raw_configured_entity("Undeployed light bearer", LifeState.ALIVE)
    grid = get_map()
    position = entity.position
    grid.set_tile_base_light(position, LightLevel.DARKNESS)
    light_uuid = grid.add_light_source(
        position,
        bright_radius_feet=5,
        dim_radius_feet=0,
        anchor_uuid=entity.uuid,
    )
    assert light_uuid in entity.get_attached_light_sources()
    assert grid.get_tile(*position).resolved_light_level is LightLevel.DARKNESS

    game = Game()
    game.deploy_entity(entity, position)
    assert grid.get_tile(*position).resolved_light_level is LightLevel.BRIGHT_LIGHT

    game.remove_entity(entity.uuid)
    assert grid.get_tile(*position).resolved_light_level is LightLevel.DARKNESS


def test_revival_reintroduces_entity_to_incremental_senses() -> None:
    """Dead removal and revival re-addition both use perceivability events."""
    reset_core_action_state()
    observer = strong_entity("Observer", (3, 4), "heroes", setup_actions=False)
    target = strong_entity("Observed", (4, 4), "monsters", setup_actions=False)
    assert target.uuid in observer.senses.entities

    target.receive_instant_death(target.uuid, source_description="test")
    assert target.uuid not in observer.senses.entities

    assert target.revive()
    assert target.uuid in observer.senses.entities
