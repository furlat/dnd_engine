"""
Test Utilities for Combat Testing

Reusable functions for setting up combat scenarios, forcing attack outcomes,
and managing encounters for integration tests.
"""

from typing import Any, Dict, Optional, Tuple
from uuid import UUID, uuid4

from dnd.entity import Entity
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap
from dnd.core.modifiers import (
    NumericalModifier, CriticalModifier, CriticalStatus, DamageType,
    AutoHitModifier, AutoHitStatus
)


def reset_combat_state():
    """Clear all global state for a fresh combat test."""
    from dnd.core.base_conditions import SpellProtectionRegistry
    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()  # Reset spatial data
    SpellProtectionRegistry.reset()  # Reset globe-like protections


def setup_combat_arena(
    entity_a: Entity,
    entity_b: Entity,
    grid_size: int = 15
) -> Encounter:
    """
    Set up a combat encounter between two entities.

    Clears any existing state, updates senses, creates encounter with initiative.

    Args:
        entity_a: First combatant
        entity_b: Second combatant
        grid_size: Size of the combat grid (not currently used)

    Returns:
        Encounter object with both combatants, initiative rolled
    """
    _ = grid_size  # Reserved for future GridMap integration

    # Ensure senses are updated for line of sight
    Entity.update_all_entities_senses()

    # Create encounter with HumanControllers (for manual/test control)
    encounter = Encounter(name="Test Combat", source_entity_uuid=uuid4())
    ctrl_a = HumanController(source_entity_uuid=entity_a.uuid)
    ctrl_b = HumanController(source_entity_uuid=entity_b.uuid)
    encounter.add_combatant(entity_a, ctrl_a)
    encounter.add_combatant(entity_b, ctrl_b)
    encounter.roll_initiative()

    return encounter


def force_attack_hit(entity: Entity) -> UUID:
    """
    Add AUTOHIT modifier to guarantee hits (overrides natural 1).

    Args:
        entity: The attacker entity

    Returns:
        UUID of the modifier for later cleanup via remove_attack_modifier()
    """
    modifier = AutoHitModifier(
        name="Forced Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    )
    mod_uuid = entity.equipment.melee_attack_bonus.self_static.add_auto_hit_modifier(modifier)
    return mod_uuid


def force_attack_miss(entity: Entity) -> UUID:
    """
    Add -100 attack penalty to guarantee misses (barring auto-hit).

    Args:
        entity: The attacker entity

    Returns:
        UUID of the modifier for later cleanup via remove_attack_modifier()
    """
    modifier = NumericalModifier.create(
        source_entity_uuid=entity.uuid,
        name="Forced Miss",
        value=-100
    )
    mod_uuid = entity.equipment.melee_attack_bonus.self_static.add_value_modifier(modifier)
    return mod_uuid


def force_attack_crit(entity: Entity) -> UUID:
    """
    Add AUTOCRIT modifier to guarantee critical hits.

    Args:
        entity: The attacker entity

    Returns:
        UUID of the modifier for later cleanup via remove_attack_modifier()
    """
    modifier = CriticalModifier(
        name="Forced Crit",
        value=CriticalStatus.AUTOCRIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    )
    mod_uuid = entity.equipment.melee_attack_bonus.self_static.add_critical_modifier(modifier)
    return mod_uuid


def force_spell_attack_hit(entity: Entity) -> UUID:
    """
    Add AUTOHIT modifier to spell attacks to guarantee hits.

    Args:
        entity: The caster entity

    Returns:
        UUID of the modifier for later cleanup via remove_spell_attack_modifier()
    """
    modifier = AutoHitModifier(
        name="Forced Spell Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    )
    mod_uuid = entity.spellcasting.spell_attack_bonus.self_static.add_auto_hit_modifier(modifier)
    return mod_uuid


def force_spell_attack_crit(entity: Entity) -> UUID:
    """
    Add AUTOCRIT modifier to spell attacks to guarantee critical hits.
    NOTE: Also call force_spell_attack_hit() to prevent nat-1 misses.

    Args:
        entity: The caster entity

    Returns:
        UUID of the modifier for later cleanup via remove_spell_attack_modifier()
    """
    modifier = CriticalModifier(
        name="Forced Spell Crit",
        value=CriticalStatus.AUTOCRIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    )
    mod_uuid = entity.spellcasting.spell_attack_bonus.self_static.add_critical_modifier(modifier)
    return mod_uuid


def remove_spell_attack_modifier(entity: Entity, modifier_uuid: UUID):
    """
    Remove a previously added spell attack modifier.

    Args:
        entity: The entity with the modifier
        modifier_uuid: UUID returned from force_spell_attack_* function
    """
    entity.spellcasting.spell_attack_bonus.self_static.remove_modifier(modifier_uuid)


def remove_attack_modifier(entity: Entity, modifier_uuid: UUID):
    """
    Remove a previously added attack modifier.

    Args:
        entity: The entity with the modifier
        modifier_uuid: UUID returned from force_attack_* function
    """
    entity.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)


def run_turn_until_end(encounter: Encounter, entity: Entity):
    """
    Execute turn_start -> [allow actions in caller] -> turn_end for an entity.

    This is a helper for manual turn management in tests.

    Args:
        encounter: The active encounter
        entity: The entity whose turn to manage
    """
    # Start the entity's turn
    entity.on_turn_start()

    # Note: Caller should execute actions between start and end

    # End the entity's turn
    entity.on_turn_end()


def deal_damage_to(
    entity: Entity,
    amount: int,
    damage_type: DamageType = DamageType.SLASHING,
    source_uuid: Optional[UUID] = None
) -> int:
    """
    Apply damage to an entity with proper event firing.

    Uses entity.receive_damage() which fires TakeDamageEvent, allowing
    handlers (RelentlessRage, Retaliation, Sleep wake, Concentration, etc.)
    to respond to damage.

    Args:
        entity: Entity to damage
        amount: Amount of damage
        damage_type: Type of damage (default SLASHING)
        source_uuid: UUID of the damage source (optional)

    Returns:
        Actual damage taken after resistances
    """
    if source_uuid is None:
        source_uuid = entity.uuid  # Self-damage if no source

    # Apply damage through receive_damage which fires TakeDamageEvent
    actual = entity.receive_damage(amount, damage_type, source_uuid)
    return actual


def heal_entity(entity: Entity, amount: int):
    """
    Heal an entity by the specified amount.

    Args:
        entity: Entity to heal
        amount: Amount of HP to restore
    """
    entity.health.heal(amount)


def get_hp(entity: Entity) -> int:
    """Get the current HP of an entity."""
    return entity.get_hp()


def get_max_hp(entity: Entity) -> int:
    """Get the maximum HP of an entity."""
    # Max HP = hit dice HP + CON mod * hit dice count + bonuses
    con_mod = entity.ability_scores.get_ability("constitution").get_combined_values().normalized_score
    base_max = entity.health.get_max_hit_dices_points(constitution_modifier=con_mod)
    bonus = entity.health.max_hit_points_bonus.normalized_score
    return base_max + bonus


def set_hp(entity: Entity, hp: int):
    """
    Set entity's HP to a specific value.
    If hp exceeds current max HP, boosts max HP first via a modifier.

    Args:
        entity: Entity to modify
        hp: Target HP value
    """
    max_hp = get_max_hp(entity)
    if hp > max_hp:
        # Boost max HP so heal can reach the target value
        entity.health.max_hit_points_bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=entity.uuid,
                name="Test HP Boost",
                value=hp - max_hp
            )
        )

    current = entity.get_hp()
    if hp < current:
        # Need to deal damage
        diff = current - hp
        entity.health.take_damage(diff, DamageType.FORCE, entity.uuid)
    elif hp > current:
        # Need to heal
        diff = hp - current
        entity.health.heal(diff)


def get_position(entity: Entity) -> Tuple[int, int]:
    """Get the current position of an entity."""
    return entity.senses.position


def move_entity(entity: Entity, new_position: Tuple[int, int]):
    """
    Move an entity to a new position (bypassing movement costs).

    Args:
        entity: Entity to move
        new_position: Target (x, y) position
    """
    old_pos = entity.senses.position
    entity.position = new_position
    entity.senses.position = new_position

    # Update position registries
    if entity.uuid in Entity._entity_by_position.get(old_pos, []):
        Entity._entity_by_position[old_pos].remove(entity)
    if new_position not in Entity._entity_by_position:
        Entity._entity_by_position[new_position] = []
    Entity._entity_by_position[new_position].append(entity)

    # Update senses
    Entity.update_all_entities_senses()


def has_condition(entity: Entity, condition_name: str) -> bool:
    """Check if an entity has a specific condition."""
    return condition_name in entity.active_conditions


def count_conditions(entity: Entity, condition_name: str) -> int:
    """Count how many conditions with a given name are active."""
    count = 0
    for name in entity.active_conditions.keys():
        if name == condition_name:
            count += 1
    return count


def get_save_natural_roll(log_data: Dict[str, Any]) -> int:
    """Extract the natural d20 roll from spell save combat log data.

    Works with the serialized SpellSaveLogData dict stored in CombatLogEntry.data.
    Returns the d20 value that was actually used (handles advantage/disadvantage).
    """
    save_roll = log_data.get('save_roll', {})
    # d20_used is set when advantage/disadvantage applies
    d20_used = save_roll.get('d20_used')
    if d20_used is not None:
        return d20_used
    # Fall back to first result
    results = save_roll.get('results', [])
    if results:
        return results[0]
    return 0


def print_combat_state(entity_a: Entity, entity_b: Entity):
    """Print current HP and conditions for both combatants."""
    print(f"\n--- Combat State ---")
    print(f"  {entity_a.name}: HP {get_hp(entity_a)}/{get_max_hp(entity_a)}")
    if entity_a.active_conditions:
        cond_names = list(entity_a.active_conditions.keys())
        print(f"    Conditions: {cond_names}")

    print(f"  {entity_b.name}: HP {get_hp(entity_b)}/{get_max_hp(entity_b)}")
    if entity_b.active_conditions:
        cond_names = list(entity_b.active_conditions.keys())
        print(f"    Conditions: {cond_names}")
    print()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "reset_combat_state",
    "setup_combat_arena",
    "force_attack_hit",
    "force_attack_miss",
    "force_attack_crit",
    "remove_attack_modifier",
    "run_turn_until_end",
    "deal_damage_to",
    "heal_entity",
    "get_hp",
    "get_max_hp",
    "set_hp",
    "get_position",
    "move_entity",
    "has_condition",
    "count_conditions",
    "get_save_natural_roll",
    "print_combat_state",
]
