"""
Debug test for Ray of Frost duration fix.

Tests that the speed reduction expires at the start of CASTER's turn,
not the target's turn (per SRD: "until the start of your next turn").
"""
from uuid import uuid4

from dnd.utils import reset_combat_state, has_condition
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.actions_functional import setup_standard_actions
from dnd.monsters.bestiary import create_caster
from dnd.core.modifiers import NumericalModifier
from dnd.spells.evocation import RayOfFrost


def create_test_target(name: str, position: tuple, dex: int = 10, faction: str = "monsters"):
    """Helper to create test targets."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(dexterity=AbilityConfig(ability_score=dex)),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]),
        position=position,
        faction=faction,
        proficiency_bonus=2,
    )
    entity = Entity.create(name=name, source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(entity)
    return entity


def test_ray_of_frost_duration_debug():
    """Debug version of Ray of Frost duration test."""
    print("=" * 60)
    print("RAY OF FROST DURATION DEBUG TEST")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    target = create_test_target("Target", (2, 0), dex=1)
    base_speed = target.action_economy.movement.normalized_score  # Should be 30

    Entity.update_all_entities_senses()

    # Force hit
    hit_mod = NumericalModifier(name="Force Hit", value=100, source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    mod_uuid = caster.spellcasting.spell_attack_bonus.self_static.add_value_modifier(hit_mod)

    ray = RayOfFrost(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, caster_level=1)
    ray.apply()

    caster.spellcasting.spell_attack_bonus.self_static.remove_modifier(mod_uuid)

    print("\n=== After spell cast ===")
    print(f"Caster conditions: {list(caster.active_conditions.keys())}")
    print(f"Target speed: {target.action_economy.movement.normalized_score} (base: {base_speed})")

    # Check the effect condition on caster
    effect = caster.active_conditions.get("Ray of Frost Effect")
    assert effect is not None, "Ray of Frost Effect should be on caster"
    assert effect.applied, "Ray of Frost Effect should be applied"
    print(f"Effect duration: {effect.duration.duration} (type: {effect.duration.duration_type})")

    # Target should be slowed (speed reduced by 10)
    assert target.action_economy.movement.normalized_score == base_speed - 10, \
        f"Target should be slowed to {base_speed - 10}, got {target.action_economy.movement.normalized_score}"

    print("\n=== After target's turn start ===")
    target.on_turn_start()
    print(f"Caster conditions: {list(caster.active_conditions.keys())}")
    print(f"Target speed: {target.action_economy.movement.normalized_score}")

    # Target should STILL be slowed - effect expires at CASTER's turn, not target's
    assert target.action_economy.movement.normalized_score == base_speed - 10, \
        "Target should STILL be slowed after their turn start!"

    print("\n=== After target's turn end ===")
    target.on_turn_end()
    print(f"Caster conditions: {list(caster.active_conditions.keys())}")
    print(f"Target speed: {target.action_economy.movement.normalized_score}")

    # Target should STILL be slowed
    assert target.action_economy.movement.normalized_score == base_speed - 10, \
        "Target should STILL be slowed after their turn end!"

    print("\n=== After caster's turn start ===")
    caster.on_turn_start()
    print(f"Caster conditions: {list(caster.active_conditions.keys())}")
    print(f"Target speed: {target.action_economy.movement.normalized_score}")

    # NOW the effect should expire - condition removed from caster, speed restored on target
    assert not has_condition(caster, "Ray of Frost Effect"), "Caster's effect should expire at their turn start!"
    assert target.action_economy.movement.normalized_score == base_speed, \
        f"Target speed should be restored to {base_speed}, got {target.action_economy.movement.normalized_score}"

    print("\n" + "=" * 60)
    print("PASS: Ray of Frost expires at caster's turn start")
    print("=" * 60)


if __name__ == "__main__":
    test_ray_of_frost_duration_debug()
