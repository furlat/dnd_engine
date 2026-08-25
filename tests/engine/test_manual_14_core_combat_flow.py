"""Focused checks for core combat flow."""
from dnd.types.materials import Material, TileSurface

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

from dnd.actions.standard import (
    Attack,
    AttackEvent,
)
from dnd.actions.operations import get_available_actions, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import (
    Weapon,
)
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core import dice as dice_module
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntryType
from dnd.types.rolls import AttackOutcome, RollType
from dnd.core.dice import Dice, DiceRoll
from dnd.types.equipment import WeaponSlot
from dnd.core.events.resolution_events import (
    DamageRollResultEvent,
    TakeDamageEvent,
)
from dnd.core.events.encounter_events import (
    DeathEvent,
)
from dnd.core.events.events_registry import (
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.gridmap import get_map
from dnd.types.life import LifeState
from dnd.types.damage import DamageType
from dnd.core.values import BaseValue
from dnd.entities.entity import Entity, EntityConfig
from dnd.items.weapons import SCIMITAR_RECIPE, SHORTBOW_RECIPE
from tests.engine.support import reset_combat_state


def reset_combat_tutorial_state(width: int = 8, height: int = 8) -> None:
    """Clear global state and create a small combat arena."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Dice._registry.clear()
    DiceRoll._registry.clear()
    get_map().create_rectangle(0, 0, width, height, surface=TileSurface(base_material=Material.STONE))


@contextmanager
def fixed_dice(*values: int) -> Iterator[None]:
    """Replace engine dice rolls with a deterministic sequence for one example."""
    if not values:
        raise ValueError("fixed_dice requires at least one value")

    original_randint = dice_module.random.randint
    remaining = list(values)

    def fake_randint(_: int, __: int) -> int:
        if len(remaining) > 1:
            return remaining.pop(0)
        return remaining[0]

    dice_module.random.randint = fake_randint
    try:
        yield
    finally:
        dice_module.random.randint = original_randint


def create_combatant(
    name: str,
    position: tuple[int, int],
    faction: str,
    dexterity: int = 14,
    hit_die_count: int = 2,
) -> Entity:
    """Create a combat-ready actor with a melee and ranged weapon."""
    actor_id = uuid4()
    actor = Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=dexterity),
                constitution=AbilityConfig(ability_score=12),
                intelligence=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=10),
                charisma=AbilityConfig(ability_score=10),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=8,
                        hit_dice_count=hit_die_count,
                        mode="maximums",
                    )
                ],
            ),
            action_economy=ActionEconomyConfig(movement=30),
            proficiency_bonus=2,
            position=position,
            faction=faction,
        ),
    )
    actor.equipment.equip(
        materialize_item(
            SCIMITAR_RECIPE,
            actor.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    actor.equipment.equip(
        materialize_item(
            SHORTBOW_RECIPE,
            actor.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.RANGED_MAIN,
    )
    setup_standard_actions(actor)
    return actor


def test_equipped_weapons_create_attack_templates_for_combat() -> None:
    """Weapon slots become concrete attack choices after standard setup."""
    reset_combat_tutorial_state()
    hero = create_combatant("Manual Fighter", (1, 1), "heroes")
    enemy = create_combatant("Training Skeleton", (2, 1), "monsters")
    Entity.materialize_all_navigation(max_distance=20)

    available = get_available_actions(hero)
    entity_actions = {action.template_name: action for action in available.entity_actions}

    assert "Attack_MELEE_MAIN" in entity_actions
    assert "Attack_RANGED_MAIN" in entity_actions
    assert "Attack_MELEE_OFF" not in entity_actions

    melee_attack = entity_actions["Attack_MELEE_MAIN"]
    assert melee_attack.cost_type == "actions"
    assert melee_attack.action_category.value == "attack"
    assert [target.target_uuid for target in melee_attack.valid_targets] == [enemy.uuid]


def test_invalid_attack_cancels_before_rolls_damage_or_costs() -> None:
    """A melee attack outside reach cancels during validation."""
    reset_combat_tutorial_state()
    hero = create_combatant("Manual Fighter", (1, 1), "heroes")
    enemy = create_combatant("Distant Skeleton", (5, 1), "monsters")
    Entity.materialize_all_navigation(max_distance=30)
    cursor = EventQueue.event_cursor()

    event = Attack(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=enemy.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()

    events = [event for _, event in EventQueue.iter_events_since(cursor)]

    assert isinstance(event, AttackEvent)
    assert event.canceled
    assert event.phase == EventPhase.CANCEL
    assert event.status_message is not None
    assert "not in reach" in event.status_message
    assert hero.action_economy.actions.normalized_score == 1
    assert enemy.get_hp() == enemy.get_max_hp()
    assert not any(isinstance(item, DamageRollResultEvent) for item in events)
    assert not any(isinstance(item, TakeDamageEvent) for item in events)


def test_successful_attack_rolls_damage_applies_hp_loss_and_spends_action() -> None:
    """A hit rolls attack, rolls damage, applies damage, logs it, then pays cost."""
    reset_combat_tutorial_state()
    hero = create_combatant("Manual Fighter", (1, 1), "heroes")
    enemy = create_combatant("Training Skeleton", (2, 1), "monsters")
    Entity.materialize_all_navigation(max_distance=20)
    cursor = EventQueue.event_cursor()
    hp_before = enemy.get_hp()

    with fixed_dice(12, 3):
        event = Attack(
            source_entity_uuid=hero.uuid,
            target_entity_uuid=enemy.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    damage_events = [
        event
        for event in events
        if isinstance(event, TakeDamageEvent) and event.phase == EventPhase.COMPLETION
    ]
    damage_roll_events = [
        event
        for event in events
        if isinstance(event, DamageRollResultEvent) and event.phase == EventPhase.COMPLETION
    ]

    assert isinstance(event, AttackEvent)
    assert not event.canceled
    assert event.attack_outcome == AttackOutcome.HIT
    assert event.dice_roll is not None
    assert event.dice_roll.roll_type == RollType.ATTACK
    assert event.dice_roll.results == [12]
    assert event.damage_rolls is not None
    assert event.damage_rolls[0].results == [3]
    assert event.damage_rolls[0].total == 5

    assert len(damage_roll_events) == 1
    assert len(damage_events) == 1
    assert damage_events[0].final_damage == 5
    assert enemy.get_hp() == hp_before - 5
    assert hero.action_economy.actions.normalized_score == 0

    assert event.combat_log is not None
    assert event.combat_log.entry_type == CombatLogEntryType.ATTACK
    assert event.combat_log.success is True
    assert event.combat_log.data["outcome"] == "hit"
    assert any(
        child.entry_type == CombatLogEntryType.DAMAGE_TAKEN
        for child in event.combat_log.sub_entries
    )


def test_natural_twenty_critical_doubles_weapon_damage_dice() -> None:
    """A natural 20 upgrades the hit to a crit and doubles base weapon dice."""
    reset_combat_tutorial_state()
    hero = create_combatant("Manual Fighter", (1, 1), "heroes")
    enemy = create_combatant("Training Skeleton", (2, 1), "monsters")
    Entity.materialize_all_navigation(max_distance=20)
    hp_before = enemy.get_hp()

    with fixed_dice(20, 3, 4):
        event = Attack(
            source_entity_uuid=hero.uuid,
            target_entity_uuid=enemy.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert isinstance(event, AttackEvent)
    assert event.attack_outcome == AttackOutcome.CRIT
    assert event.dice_roll is not None
    assert event.dice_roll.results == [20]
    assert event.damage_rolls is not None
    assert event.damage_rolls[0].results == [3, 4]
    assert event.damage_rolls[0].total == 9
    assert enemy.get_hp() == hp_before - 9


def test_miss_spends_the_action_without_damage_events() -> None:
    """A completed miss consumes the action and never creates damage children."""
    reset_combat_tutorial_state()
    hero = create_combatant("Manual Fighter", (1, 1), "heroes")
    enemy = create_combatant("Training Skeleton", (2, 1), "monsters")
    Entity.materialize_all_navigation(max_distance=20)
    cursor = EventQueue.event_cursor()
    hp_before = enemy.get_hp()

    with fixed_dice(2):
        event = Attack(
            source_entity_uuid=hero.uuid,
            target_entity_uuid=enemy.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    events = [event for _, event in EventQueue.iter_events_since(cursor)]

    assert isinstance(event, AttackEvent)
    assert event.attack_outcome == AttackOutcome.MISS
    assert event.damage_rolls is None
    assert enemy.get_hp() == hp_before
    assert hero.action_economy.actions.normalized_score == 0
    assert not any(isinstance(item, DamageRollResultEvent) for item in events)
    assert not any(isinstance(item, TakeDamageEvent) for item in events)
    assert event.combat_log is not None
    assert event.combat_log.success is False


def test_direct_damage_can_cause_death_as_a_child_event() -> None:
    """Lethal damage passes through TAKE_DAMAGE and then creates DEATH."""
    reset_combat_tutorial_state()
    hero = create_combatant("Manual Fighter", (1, 1), "heroes")
    enemy = create_combatant("Training Skeleton", (2, 1), "monsters", hit_die_count=1)
    cursor = EventQueue.event_cursor()

    actual_damage = enemy.receive_damage(
        amount=99,
        damage_type=DamageType.SLASHING,
        source_entity_uuid=hero.uuid,
    )

    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    damage_completions = [
        event
        for event in events
        if isinstance(event, TakeDamageEvent) and event.phase == EventPhase.COMPLETION
    ]
    death_completions = [
        event
        for event in events
        if isinstance(event, DeathEvent) and event.phase == EventPhase.COMPLETION
    ]

    assert actual_damage == 99
    assert enemy.get_hp() <= 0
    assert enemy.health.life_state is LifeState.DEAD
    assert len(damage_completions) == 1
    assert len(death_completions) == 1
    assert damage_completions[0].event_type == EventType.TAKE_DAMAGE
    assert death_completions[0].entity_uuid == enemy.uuid
    assert damage_completions[0].combat_log is not None
    assert any(
        child.entry_type == CombatLogEntryType.DEATH
        for child in damage_completions[0].combat_log.sub_entries
    )
