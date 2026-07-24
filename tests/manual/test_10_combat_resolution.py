"""Tutorial tests for attack resolution, damage, healing, reactions, and shove."""

from uuid import UUID, uuid4

from dnd.actions import Attack, Move, Shove
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import (
    AutoHitModifier,
    AutoHitStatus,
    CriticalModifier,
    CriticalStatus,
    DamageType,
    Size,
)
from dnd.core.values import BaseValue
from dnd.conditions import Incapacitated, Prone
from dnd.entity import Entity, EntityConfig
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.reactions import add_opportunity_attack_handler


def reset_combat_tutorial_state() -> None:
    """Clear global state and create the tutorial combat arena."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, 20, 20)


def make_melee_attack_auto_hit(entity: Entity) -> UUID:
    """Add an explicit auto-hit modifier to the entity's melee attack bonus."""
    modifier = AutoHitModifier(
        name="Tutorial Auto Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    return entity.equipment.melee_attack_bonus.self_static.add_auto_hit_modifier(modifier)


def make_melee_attack_auto_crit(entity: Entity) -> UUID:
    """Add an explicit auto-critical modifier to the entity's melee attack bonus."""
    modifier = CriticalModifier(
        name="Tutorial Auto Crit",
        value=CriticalStatus.AUTOCRIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    return entity.equipment.melee_attack_bonus.self_static.add_critical_modifier(modifier)


def clear_melee_attack_modifier(entity: Entity, modifier_uuid: UUID) -> None:
    """Remove a tutorial modifier from the entity's melee attack bonus."""
    entity.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)


def create_strong_actor(
    name: str,
    position: tuple[int, int],
    faction: str | None,
    strength: int = 20,
    weight: int = 120,
    size: Size = Size.MEDIUM,
) -> Entity:
    """Create a deterministic strong actor for shove examples."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=strength),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=14),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(hit_dice_value=10, hit_dice_count=3, mode="maximums")
            ]
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
        weight=weight,
        size=size,
    )
    actor = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(actor)
    return actor


def test_first_combat_example_prints_visible_hit_damage_and_heal(capsys) -> None:
    """One attack prints outcome, HP changes, cost spending, and heal events."""
    reset_combat_tutorial_state()
    attacker = create_goblin(name="Blade", position=(5, 5), faction="heroes")
    target = create_skeleton(name="Bone Guard", position=(6, 5), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    target_hp_before = target.get_hp()
    actions_before = attacker.action_economy.actions.normalized_score
    hit_modifier = make_melee_attack_auto_hit(attacker)

    with fixed_dice_faces(10, 4):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    clear_melee_attack_modifier(attacker, hit_modifier)
    assert event is not None
    damage_roll = event.damage_rolls[0]
    target_hp_after_hit = target.get_hp()
    healing = target.receive_healing(
        3,
        source_entity_uuid=attacker.uuid,
        source_description="Tutorial healing",
    )
    completion_counts = {
        event_type.value: sum(
            stored_event.phase == EventPhase.COMPLETION
            for stored_event in EventQueue.get_events_by_type(event_type)
        )
        for event_type in [
            EventType.ATTACK,
            EventType.DAMAGE_ROLL_RESULT,
            EventType.TAKE_DAMAGE,
            EventType.HEAL,
        ]
    }
    readout_lines = [
        f"attack: {attacker.name} -> {target.name} with {event.weapon_name}",
        f"outcome: {event.attack_outcome.value}",
        f"damage roll: {damage_roll.results} + {damage_roll.bonus} = {damage_roll.total}",
        f"target hp after hit: {target_hp_before} -> {target_hp_after_hit}",
        (
            "actions after attack: "
            f"{actions_before} -> {attacker.action_economy.actions.normalized_score}"
        ),
        f"healing applied: {healing}",
        f"target hp after healing: {target.get_hp()}",
        "completion events: "
        + ", ".join(f"{name}={count}" for name, count in completion_counts.items()),
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "attack: Blade -> Bone Guard with Scimitar",
        "outcome: Hit",
        "damage roll: [4] + 2 = 6",
        "target hp after hit: 17 -> 11",
        "actions after attack: 1 -> 0",
        "healing applied: 3",
        "target hp after healing: 14",
        "completion events: attack=1, damage_roll_result=1, take_damage=1, heal=1",
    ]
    assert readout_lines == expected_lines
    assert event.phase == EventPhase.COMPLETION
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_prone_auto_stand_waits_when_movement_is_unavailable() -> None:
    """Turn-start auto-stand should not crash when constraints remove movement."""
    reset_combat_tutorial_state()
    actor = create_strong_actor("Pinned Hero", (5, 5), faction="heroes")
    actor.add_condition(Prone(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid))
    actor.add_condition(Incapacitated(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid))

    actor.on_turn_start(round_number=1, turn_index=0)

    assert "Prone" in actor.active_conditions
    assert actor.action_economy.movement.normalized_score == 0


def test_invalid_melee_attack_cancels_before_costs(capsys) -> None:
    """Invalid attack validation cancels without spending the action."""
    reset_combat_tutorial_state()
    attacker = create_goblin(name="Attacker", position=(2, 2), faction="heroes")
    target = create_skeleton(name="Too Far", position=(12, 2), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    actions_before = attacker.action_economy.actions.normalized_score
    event = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()

    assert event is not None
    assert event.canceled is True
    assert "reach" in (event.status_message or "").lower()
    assert attacker.action_economy.actions.normalized_score == actions_before

    invalid_lines = [
        f"event phase: {event.phase.value}",
        f"canceled: {event.canceled}",
        f"reason: {event.status_message}",
        (
            "actions after invalid attack: "
            f"{actions_before} -> {attacker.action_economy.actions.normalized_score}"
        ),
    ]

    print("\n".join(invalid_lines))

    expected_invalid_lines = [
        "event phase: cancel",
        "canceled: True",
        "reason: Target entity not in reach for Attack",
        "actions after invalid attack: 1 -> 1",
    ]
    assert invalid_lines == expected_invalid_lines
    assert capsys.readouterr().out.splitlines() == expected_invalid_lines


def test_successful_attack_rolls_damage_spends_action_and_can_be_healed(capsys) -> None:
    """A hit rolls damage, applies HP loss, emits events, and can be healed."""
    reset_combat_tutorial_state()
    attacker = create_goblin(name="Attacker", position=(5, 5), faction="heroes")
    target = create_skeleton(name="Target", position=(6, 5), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    target_hp_before = target.get_hp()
    hit_modifier = make_melee_attack_auto_hit(attacker)

    with fixed_dice_faces(10, 4):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    clear_melee_attack_modifier(attacker, hit_modifier)

    assert event is not None
    assert event.phase == EventPhase.COMPLETION
    assert event.damage_rolls
    assert target.get_hp() < target_hp_before
    assert attacker.action_economy.actions.normalized_score == 0
    assert EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
    assert EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)

    damaged_hp = target.get_hp()
    actual_healing = target.receive_healing(
        3,
        source_entity_uuid=attacker.uuid,
        source_description="Tutorial healing",
    )

    assert actual_healing == min(3, target_hp_before - damaged_hp)
    assert target.get_hp() == damaged_hp + actual_healing
    assert EventQueue.get_events_by_type(EventType.HEAL)

    completion_counts = {
        event_type.value: sum(
            stored_event.phase == EventPhase.COMPLETION
            for stored_event in EventQueue.get_events_by_type(event_type)
        )
        for event_type in [
            EventType.ATTACK,
            EventType.DAMAGE_ROLL_RESULT,
            EventType.TAKE_DAMAGE,
            EventType.HEAL,
        ]
    }
    damage_roll = event.damage_rolls[0]
    hit_lines = [
        f"outcome: {event.attack_outcome.value}",
        f"damage roll: {damage_roll.results} + {damage_roll.bonus} = {damage_roll.total}",
        f"hp after damage: {target_hp_before} -> {damaged_hp}",
        f"healing applied: {actual_healing}",
        f"hp after healing: {target.get_hp()}",
        f"actions after attack: {attacker.action_economy.actions.normalized_score}",
        "completion events: "
        + ", ".join(f"{name}={count}" for name, count in completion_counts.items()),
    ]

    print("\n".join(hit_lines))

    expected_hit_lines = [
        "outcome: Hit",
        "damage roll: [4] + 2 = 6",
        "hp after damage: 17 -> 11",
        "healing applied: 3",
        "hp after healing: 14",
        "actions after attack: 0",
        "completion events: attack=1, damage_roll_result=1, take_damage=1, heal=1",
    ]
    assert hit_lines == expected_hit_lines
    assert capsys.readouterr().out.splitlines() == expected_hit_lines


def test_critical_hit_doubles_weapon_damage_dice(capsys) -> None:
    """A critical weapon hit rolls the weapon damage dice twice."""
    reset_combat_tutorial_state()
    attacker = create_goblin(name="Attacker", position=(5, 5), faction="heroes")
    target = create_skeleton(name="Target", position=(6, 5), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    hit_modifier = make_melee_attack_auto_hit(attacker)
    crit_modifier = make_melee_attack_auto_crit(attacker)

    with fixed_dice_faces(10, 3, 4):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    clear_melee_attack_modifier(attacker, hit_modifier)
    clear_melee_attack_modifier(attacker, crit_modifier)

    assert event is not None
    assert event.attack_outcome is not None
    assert event.attack_outcome.value == "Crit"
    assert event.damage_rolls
    assert event.damage_rolls[0].results == [3, 4]

    damage_roll = event.damage_rolls[0]
    crit_lines = [
        f"outcome: {event.attack_outcome.value}",
        f"damage dice: {damage_roll.results}",
        f"damage bonus: {damage_roll.bonus}",
        f"total damage: {damage_roll.total}",
        f"target hp after crit: {target.get_hp()}",
    ]

    print("\n".join(crit_lines))

    expected_crit_lines = [
        "outcome: Crit",
        "damage dice: [3, 4]",
        "damage bonus: 2",
        "total damage: 9",
        "target hp after crit: 8",
    ]
    assert crit_lines == expected_crit_lines
    assert capsys.readouterr().out.splitlines() == expected_crit_lines


def test_step_movement_can_trigger_opportunity_attack(capsys) -> None:
    """Voluntary step movement can trigger a hostile opportunity attack."""
    reset_combat_tutorial_state()
    watcher = create_skeleton(name="Watcher", position=(5, 5), faction="monsters")
    mover = create_goblin(name="Mover", position=(5, 6), faction="heroes")
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses(max_distance=20)
    setup_standard_actions(mover)
    available = mover.get_available_actions()
    move = next(
        action
        for action in available.position_actions
        if action.template_name == "Move"
    )
    target = next(
        candidate
        for candidate in move.valid_targets
        if candidate.position == (5, 10)
    )
    exposure = target.opportunity_attack_exposures[0]

    assert exposure.reactor_uuid == watcher.uuid
    assert exposure.reactor_name == watcher.name
    assert exposure.from_position == (5, 6)
    assert exposure.to_position == (5, 7)

    mover_hp_before = mover.get_hp()
    hit_modifier = make_melee_attack_auto_hit(watcher)

    with fixed_dice_faces(10, 4):
        move_event = Move(source_entity_uuid=mover.uuid, end_position=(5, 10)).apply()

    clear_melee_attack_modifier(watcher, hit_modifier)

    assert move_event is not None
    assert mover.position == (5, 10)
    assert mover.get_hp() < mover_hp_before
    assert watcher.action_economy.reactions.normalized_score == 0
    assert any(
        event.name == "Opportunity Attack"
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
    )

    opportunity_attack_completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
        if event.name == "Opportunity Attack" and event.phase == EventPhase.COMPLETION
    ]
    opportunity_lines = [
        f"move phase: {move_event.phase.value}",
        f"mover position: {mover.position}",
        f"mover hp after reaction: {mover_hp_before} -> {mover.get_hp()}",
        f"watcher reactions after attack: {watcher.action_economy.reactions.normalized_score}",
        f"opportunity attack completions: {len(opportunity_attack_completions)}",
    ]

    print("\n".join(opportunity_lines))

    expected_opportunity_lines = [
        "move phase: completion",
        "mover position: (5, 10)",
        "mover hp after reaction: 10 -> 4",
        "watcher reactions after attack: 0",
        "opportunity attack completions: 1",
    ]
    assert opportunity_lines == expected_opportunity_lines
    assert capsys.readouterr().out.splitlines() == expected_opportunity_lines


def test_bg3_shove_uses_bonus_action_and_forced_movement_not_opportunity_attack(capsys) -> None:
    """BG3-style Shove pushes through forced movement and does not trigger OA."""
    reset_combat_tutorial_state()
    shover = create_strong_actor("Shove Hero", position=(5, 5), faction="heroes")
    target = create_strong_actor(
        "Light Target",
        position=(6, 5),
        faction="monsters",
        strength=8,
        weight=40,
    )
    watcher = create_skeleton(name="Watcher", position=(6, 6), faction="monsters")
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses(max_distance=20)

    with fixed_dice_faces(20):
        shove_event = Shove(
            source_entity_uuid=shover.uuid,
            target_entity_uuid=target.uuid,
        ).apply()

    assert shove_event is not None
    assert shove_event.phase == EventPhase.COMPLETION
    assert shove_event.contest_success is True
    assert shove_event.push_distance == 10
    assert target.position == (8, 5)
    assert shover.action_economy.bonus_actions.normalized_score == 0

    forced_events = EventQueue.get_events_by_type(EventType.FORCED_MOVEMENT)
    assert any(event.phase == EventPhase.COMPLETION for event in forced_events)
    assert watcher.action_economy.reactions.normalized_score == 1
    assert not any(
        event.name == "Opportunity Attack"
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
    )

    forced_movement_completions = [
        event
        for event in forced_events
        if event.phase == EventPhase.COMPLETION
    ]
    opportunity_attacks = [
        event
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
        if event.name == "Opportunity Attack"
    ]
    shove_lines = [
        f"shove phase: {shove_event.phase.value}",
        f"contest success: {shove_event.contest_success}",
        f"push distance: {shove_event.push_distance}",
        f"target position after shove: {target.position}",
        f"bonus actions after shove: {shover.action_economy.bonus_actions.normalized_score}",
        f"forced movement completions: {len(forced_movement_completions)}",
        f"watcher reactions after forced movement: {watcher.action_economy.reactions.normalized_score}",
        f"opportunity attacks created: {len(opportunity_attacks)}",
    ]

    print("\n".join(shove_lines))

    expected_shove_lines = [
        "shove phase: completion",
        "contest success: True",
        "push distance: 10",
        "target position after shove: (8, 5)",
        "bonus actions after shove: 0",
        "forced movement completions: 1",
        "watcher reactions after forced movement: 1",
        "opportunity attacks created: 0",
    ]
    assert shove_lines == expected_shove_lines
    assert capsys.readouterr().out.splitlines() == expected_shove_lines
