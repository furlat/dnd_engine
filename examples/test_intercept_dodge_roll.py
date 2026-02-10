"""
Test script for homebrew Intercept and Dodge Roll reactions.

Validates:
1. Basic functionality of both reactions with proper Encounter turn flow
2. Movement cost accounting after interception
3. OA interaction (reaction consumed by intercept → no OA, or 2 reactions → both fire)
4. The _paths_dirty / per-cell walkability pattern via door open/close during turns
5. Condition removal cleans up reaction handlers

These are NOT SRD reactions — they're proof-of-concept for the incremental senses system.
"""

from uuid import uuid4
from dnd.utils import reset_combat_state, force_attack_hit, remove_attack_modifier
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.actions_functional import setup_standard_actions, execute_use_action
from dnd.actions import Move, Attack
from dnd.core.gridmap import get_map
from dnd.core.events import WeaponSlot
from dnd.core.base_conditions import DurationType
from dnd.core.modifiers import NumericalModifier
from dnd.items import create_shortsword
from dnd.items.test_reactions import (
    Intercepting, DodgeRollFeature, PrepareIntercept,
)
from dnd.items.test_items import TestDoorA
from dnd.reactions import add_opportunity_attack_handler
from dnd.encounter import Encounter
from dnd.controller import HumanController


passed = 0
failed = 0


def assert_test(condition: bool, message: str):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {message}")
    else:
        failed += 1
        print(f"  FAIL: {message}")


def create_melee_fighter(
    name: str = "Fighter",
    position: tuple = (0, 0),
    faction: str = "heroes",
) -> Entity:
    """Create a fighter with a melee weapon for reaction testing."""
    source_id = uuid4()
    entity_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=14),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=5, mode="average")]
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=3,
        position=position,
        faction=faction,
    )
    entity = Entity.create(name=name, source_entity_uuid=source_id, config=entity_config)
    setup_standard_actions(entity)

    # Equip a melee weapon (needed for intercept and attack reactions)
    sword = create_shortsword(entity.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)

    return entity


def setup_encounter(*entities):
    """Create encounter with entities in the given order. Starts first entity's turn."""
    encounter = Encounter(name="Reaction Test", source_entity_uuid=uuid4())
    for entity in entities:
        encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    encounter.roll_initiative()
    # Force initiative order to match argument order
    encounter.initiative_order = [e.uuid for e in entities]
    encounter.start_encounter()
    encounter.start_turn()  # First entity's turn
    return encounter


# =============================================================================
# INTERCEPT TESTS
# =============================================================================

def test_intercept_basic():
    """Prepare Intercept → enemy walks through charge_dest → interceptor charges + attacks."""
    print("\n=== Test: Intercept Basic ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 5)

    # Interceptor at (2,2), enemy at (8,2). Charge dest will be (5,2).
    # Enemy path to (3,2) goes through (5,2).
    interceptor = create_melee_fighter(name="Interceptor", position=(2, 2), faction="heroes")
    enemy = create_melee_fighter(name="Enemy", position=(8, 2), faction="monsters")
    Entity.update_all_entities_senses()

    encounter = setup_encounter(interceptor, enemy)

    # === Interceptor's turn: apply Intercepting condition ===
    charge_dest = (5, 2)
    intercepting = Intercepting(
        source_entity_uuid=interceptor.uuid,
        target_entity_uuid=interceptor.uuid,
        charge_destination=charge_dest,
    )
    intercepting.duration.duration_type = DurationType.ROUNDS
    intercepting.duration.duration = 1
    interceptor.add_condition(intercepting)
    assert_test("Intercepting" in interceptor.active_conditions, "Intercepting condition applied")

    # === Enemy's turn: move through charge destination ===
    encounter.next_turn()
    move = Move(source_entity_uuid=enemy.uuid, end_position=(3, 2))
    move.apply()

    # Interceptor charged to (5,2), blocking it
    assert_test(interceptor.position == charge_dest,
                f"Interceptor charged to {charge_dest} (at {interceptor.position})")

    # Enemy stopped at (6,2) — the cell before the interceptor
    assert_test(enemy.position == (6, 2),
                f"Enemy stopped at (6,2) (at {enemy.position})")

    # Interceptor used reaction for the attack
    assert_test(interceptor.action_economy.reactions.normalized_score == 0,
                f"Interceptor reaction consumed (remaining: {interceptor.action_economy.reactions.normalized_score})")

    encounter.end_encounter()


def test_intercept_costs():
    """PrepareIntercept costs 1 action + movement for the charge distance."""
    print("\n=== Test: Intercept Costs ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 5)

    fighter = create_melee_fighter(name="Fighter", position=(2, 2), faction="heroes")
    Entity.update_all_entities_senses()

    encounter = setup_encounter(fighter)

    # Record action economy before
    actions_before = fighter.action_economy.actions.normalized_score
    movement_before = fighter.action_economy.movement.normalized_score

    # PrepareIntercept at (5,2) — 3 cells = 15ft movement
    prepare = PrepareIntercept(source_entity_uuid=fighter.uuid)
    prepare.set_target_position((5, 2))
    result = prepare.apply()

    assert_test(result is not None and not result.canceled, "PrepareIntercept succeeded")
    assert_test("Intercepting" in fighter.active_conditions, "Intercepting condition applied")

    actions_after = fighter.action_economy.actions.normalized_score
    movement_after = fighter.action_economy.movement.normalized_score

    assert_test(actions_after == actions_before - 1,
                f"1 action consumed ({actions_before} → {actions_after})")
    assert_test(movement_after == movement_before - 15,
                f"15ft movement consumed ({movement_before} → {movement_after})")

    encounter.end_encounter()


def test_intercept_reaction_consumed():
    """After intercept triggers, reaction is consumed. Second enemy is NOT intercepted."""
    print("\n=== Test: Intercept Reaction Consumed ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 5)

    interceptor = create_melee_fighter(name="Interceptor", position=(2, 2), faction="heroes")
    enemy1 = create_melee_fighter(name="Enemy1", position=(8, 2), faction="monsters")
    enemy2 = create_melee_fighter(name="Enemy2", position=(10, 2), faction="monsters")
    Entity.update_all_entities_senses()

    encounter = setup_encounter(interceptor, enemy1, enemy2)

    # === Interceptor: prepare ===
    charge_dest = (5, 2)
    intercepting = Intercepting(
        source_entity_uuid=interceptor.uuid,
        target_entity_uuid=interceptor.uuid,
        charge_destination=charge_dest,
    )
    intercepting.duration.duration_type = DurationType.ROUNDS
    intercepting.duration.duration = 1
    interceptor.add_condition(intercepting)

    # === Enemy1: walks through charge_dest → intercepted ===
    encounter.next_turn()
    move1 = Move(source_entity_uuid=enemy1.uuid, end_position=(3, 2))
    move1.apply()

    assert_test(interceptor.action_economy.reactions.normalized_score == 0,
                "Reaction consumed after first intercept")
    assert_test(interceptor.position == charge_dest,
                f"Interceptor at charge dest (at {interceptor.position})")

    # === Enemy2: walks through same cell — but interceptor already there + no reaction ===
    encounter.next_turn()
    pos_before = interceptor.position
    # Enemy2 can't walk through (5,2) because interceptor blocks it.
    # They should stop before it or path around.
    move2 = Move(source_entity_uuid=enemy2.uuid, end_position=(3, 2))
    move2.apply()

    assert_test(interceptor.position == pos_before,
                f"Interceptor didn't move for second enemy (still at {interceptor.position})")

    encounter.end_encounter()


def test_intercept_ally_not_intercepted():
    """Allies moving through charge destination don't trigger intercept."""
    print("\n=== Test: Intercept Ally Not Intercepted ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 5)

    interceptor = create_melee_fighter(name="Interceptor", position=(2, 2), faction="heroes")
    ally = create_melee_fighter(name="Ally", position=(8, 2), faction="heroes")
    Entity.update_all_entities_senses()

    encounter = setup_encounter(interceptor, ally)

    # === Interceptor: prepare ===
    charge_dest = (5, 2)
    intercepting = Intercepting(
        source_entity_uuid=interceptor.uuid,
        target_entity_uuid=interceptor.uuid,
        charge_destination=charge_dest,
    )
    intercepting.duration.duration_type = DurationType.ROUNDS
    intercepting.duration.duration = 1
    interceptor.add_condition(intercepting)

    # === Ally moves through charge_dest ===
    encounter.next_turn()
    pos_before = interceptor.position
    move = Move(source_entity_uuid=ally.uuid, end_position=(3, 2))
    move.apply()

    assert_test(interceptor.position == pos_before,
                f"Interceptor didn't trigger on ally (still at {interceptor.position})")
    assert_test(interceptor.action_economy.reactions.normalized_score == 1,
                "Reaction not consumed for ally")

    encounter.end_encounter()


def test_intercept_blocks_enemy_movement_cost_and_no_oa():
    """Interceptor blocks enemy. Check: correct movement cost, remaining movement, no OA."""
    print("\n=== Test: Intercept Blocks + Movement Cost + No OA ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 5)

    interceptor = create_melee_fighter(name="Interceptor", position=(2, 2), faction="heroes")
    enemy = create_melee_fighter(name="Enemy", position=(8, 2), faction="monsters")
    # Give interceptor OA handler — should NOT fire after intercept (0 reactions)
    add_opportunity_attack_handler(interceptor)
    Entity.update_all_entities_senses()

    encounter = setup_encounter(interceptor, enemy)

    # === Interceptor: prepare ===
    intercepting = Intercepting(
        source_entity_uuid=interceptor.uuid,
        target_entity_uuid=interceptor.uuid,
        charge_destination=(5, 2),
    )
    intercepting.duration.duration_type = DurationType.ROUNDS
    intercepting.duration.duration = 1
    interceptor.add_condition(intercepting)

    # === Enemy's turn ===
    encounter.next_turn()
    move = Move(source_entity_uuid=enemy.uuid, end_position=(3, 2))
    move.apply()

    # Enemy stopped at (6,2): walked 2 steps (8→7→6), then step 6→5 was canceled
    assert_test(enemy.position == (6, 2),
                f"Enemy stopped at (6,2) (at {enemy.position})")

    # Movement consumed: 2 completed steps × 5ft = 10ft. Started with 30ft.
    remaining_movement = enemy.action_economy.movement.normalized_score
    assert_test(remaining_movement == 20,
                f"Enemy has 20ft remaining ({remaining_movement}ft)")

    # Interceptor consumed reaction for intercept attack
    assert_test(interceptor.action_economy.reactions.normalized_score == 0,
                "Interceptor reaction consumed by intercept")

    # Enemy moves AWAY from interceptor — no OA because interceptor has 0 reactions
    interceptor_hp_before = enemy.get_hp()  # track enemy HP to detect OA damage
    move2 = Move(source_entity_uuid=enemy.uuid, end_position=(7, 2))
    move2.apply()

    assert_test(enemy.position == (7, 2),
                f"Enemy moved away to (7,2) (at {enemy.position})")
    # No OA fired (interceptor has 0 reactions)
    assert_test(enemy.get_hp() == interceptor_hp_before,
                "No OA damage — interceptor had 0 reactions")

    encounter.end_encounter()


def test_intercept_with_2_reactions_also_oa():
    """Interceptor with 2 reactions: intercept consumes 1, then OA consumes the other.

    With single registration (no double-fire), the intercept handler cancels the step,
    which stops the handler loop — OA doesn't fire on the same step. When the enemy
    then moves away from the interceptor, OA fires on that separate movement.
    """
    print("\n=== Test: Intercept + OA (2 Reactions) ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 5)

    interceptor = create_melee_fighter(name="Interceptor", position=(2, 2), faction="heroes")
    enemy = create_melee_fighter(name="Enemy", position=(8, 2), faction="monsters")
    # Give interceptor OA handler
    add_opportunity_attack_handler(interceptor)
    # Give interceptor 2 reactions (homebrew OP setup)
    interceptor.action_economy.reactions.self_static.add_value_modifier(
        NumericalModifier(
            name="Extra Reaction", value=1,
            source_entity_uuid=interceptor.uuid,
            target_entity_uuid=interceptor.uuid
        )
    )
    Entity.update_all_entities_senses()

    encounter = setup_encounter(interceptor, enemy)

    assert_test(interceptor.action_economy.reactions.normalized_score == 2,
                "Interceptor starts with 2 reactions")

    # === Interceptor: prepare ===
    intercepting = Intercepting(
        source_entity_uuid=interceptor.uuid,
        target_entity_uuid=interceptor.uuid,
        charge_destination=(5, 2),
    )
    intercepting.duration.duration_type = DurationType.ROUNDS
    intercepting.duration.duration = 1
    interceptor.add_condition(intercepting)

    # === Enemy's turn ===
    encounter.next_turn()
    move = Move(source_entity_uuid=enemy.uuid, end_position=(3, 2))
    move.apply()

    # Intercept fired, canceled the step → OA didn't fire on same step
    assert_test(interceptor.position == (5, 2),
                f"Interceptor charged to (5,2) (at {interceptor.position})")
    assert_test(enemy.position == (6, 2),
                f"Enemy stopped at (6,2) (at {enemy.position})")

    # Intercept consumed 1 reaction, 1 remaining
    reactions_after_intercept = interceptor.action_economy.reactions.normalized_score
    assert_test(reactions_after_intercept == 1,
                f"1 reaction remaining after intercept ({reactions_after_intercept})")

    # Enemy moves away from interceptor → should trigger OA (1 reaction left)
    hit_mod = force_attack_hit(interceptor)
    enemy_hp_after_intercept = enemy.get_hp()
    move2 = Move(source_entity_uuid=enemy.uuid, end_position=(8, 2))
    move2.apply()
    remove_attack_modifier(interceptor, hit_mod)

    # OA should have fired and consumed the remaining reaction
    assert_test(interceptor.action_economy.reactions.normalized_score == 0,
                "OA consumed the remaining reaction")

    # Enemy took additional damage from OA
    assert_test(enemy.get_hp() < enemy_hp_after_intercept,
                f"Enemy took OA damage ({enemy_hp_after_intercept} → {enemy.get_hp()})")

    encounter.end_encounter()


# =============================================================================
# DODGE ROLL TESTS
# =============================================================================

def test_dodge_roll_basic():
    """Entity with DodgeRollFeature attacked → moves 2 cells away."""
    print("\n=== Test: Dodge Roll Basic ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 5)

    attacker = create_melee_fighter(name="Attacker", position=(3, 2), faction="monsters")
    defender = create_melee_fighter(name="Defender", position=(4, 2), faction="heroes")
    Entity.update_all_entities_senses()

    encounter = setup_encounter(defender, attacker)

    # === Defender's turn: apply DodgeRollFeature ===
    dodge_feat = DodgeRollFeature(
        source_entity_uuid=defender.uuid,
        target_entity_uuid=defender.uuid,
    )
    defender.add_condition(dodge_feat)
    assert_test("Dodge Roll" in defender.active_conditions, "Dodge Roll feature applied")

    # === Attacker's turn: attack defender ===
    encounter.next_turn()
    mod_uuid = force_attack_hit(attacker)
    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=defender.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    attack.apply()
    remove_attack_modifier(attacker, mod_uuid)

    # Defender dodged 2 cells away from attacker (flee direction: +x)
    assert_test(defender.position == (6, 2),
                f"Defender dodged to (6,2) (at {defender.position})")

    encounter.end_encounter()


def test_dodge_roll_costs_reaction():
    """After dodge roll, reaction is consumed."""
    print("\n=== Test: Dodge Roll Costs Reaction ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 5)

    attacker = create_melee_fighter(name="Attacker", position=(3, 2), faction="monsters")
    defender = create_melee_fighter(name="Defender", position=(4, 2), faction="heroes")
    Entity.update_all_entities_senses()

    encounter = setup_encounter(defender, attacker)

    dodge_feat = DodgeRollFeature(
        source_entity_uuid=defender.uuid,
        target_entity_uuid=defender.uuid,
    )
    defender.add_condition(dodge_feat)
    assert_test(defender.action_economy.reactions.normalized_score == 1,
                "Defender has 1 reaction before")

    encounter.next_turn()
    mod_uuid = force_attack_hit(attacker)
    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=defender.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    attack.apply()
    remove_attack_modifier(attacker, mod_uuid)

    assert_test(defender.action_economy.reactions.normalized_score == 0,
                "Reaction consumed after dodge roll")

    encounter.end_encounter()


def test_dodge_roll_blocked():
    """Entity backed against wall → can't dodge, no reaction consumed."""
    print("\n=== Test: Dodge Roll Blocked ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 5)

    # Defender at (0,2) backed against left edge. Flee direction = (-1,0) → off grid.
    attacker = create_melee_fighter(name="Attacker", position=(1, 2), faction="monsters")
    defender = create_melee_fighter(name="Defender", position=(0, 2), faction="heroes")
    Entity.update_all_entities_senses()

    encounter = setup_encounter(defender, attacker)

    dodge_feat = DodgeRollFeature(
        source_entity_uuid=defender.uuid,
        target_entity_uuid=defender.uuid,
    )
    defender.add_condition(dodge_feat)

    encounter.next_turn()
    pos_before = defender.position
    mod_uuid = force_attack_hit(attacker)
    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=defender.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    attack.apply()
    remove_attack_modifier(attacker, mod_uuid)

    assert_test(defender.position == pos_before,
                f"Defender didn't move (blocked, still at {defender.position})")
    assert_test(defender.action_economy.reactions.normalized_score == 1,
                "Reaction NOT consumed (dodge failed)")

    encounter.end_encounter()


def test_dodge_roll_partial():
    """1 cell free, 2nd blocked → moves 1 cell only, reaction consumed."""
    print("\n=== Test: Dodge Roll Partial ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 5)

    # Flee direction: +x. Cell (5,2) free, cell (6,2) is wall.
    attacker = create_melee_fighter(name="Attacker", position=(3, 2), faction="monsters")
    defender = create_melee_fighter(name="Defender", position=(4, 2), faction="heroes")
    Entity.update_all_entities_senses()

    grid.set_tile(6, 2, walkable=False, visible=False, name="Wall")

    encounter = setup_encounter(defender, attacker)

    dodge_feat = DodgeRollFeature(
        source_entity_uuid=defender.uuid,
        target_entity_uuid=defender.uuid,
    )
    defender.add_condition(dodge_feat)

    encounter.next_turn()
    mod_uuid = force_attack_hit(attacker)
    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=defender.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    attack.apply()
    remove_attack_modifier(attacker, mod_uuid)

    assert_test(defender.position == (5, 2),
                f"Defender moved 1 cell only (at {defender.position})")
    assert_test(defender.action_economy.reactions.normalized_score == 0,
                "Reaction consumed (partial dodge)")

    encounter.end_encounter()


# =============================================================================
# _paths_dirty VALIDATION TESTS (door open/close during encounter turns)
# =============================================================================

def test_intercept_path_blocked_by_door():
    """Door closes on charge path → intercept charge stops short → no block.

    Turn 1 (Interceptor): Prepare intercept at (6,2) — charge goes through open door at (4,2).
    Turn 2 (DoorCloser): Close door at (4,2) → SPATIAL_OBJECT_CHANGED.
    Turn 3 (Enemy): Move through (6,2) → intercept fires → charge blocked by closed door.
    """
    print("\n=== Test: Intercept Path Blocked By Door ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 5)

    interceptor = create_melee_fighter(name="Interceptor", position=(2, 2), faction="heroes")
    door_closer = create_melee_fighter(name="DoorCloser", position=(4, 3), faction="neutral")
    enemy = create_melee_fighter(name="Enemy", position=(9, 2), faction="monsters")

    # Create door at (4,2) — starts OPEN (interceptor opened it during setup)
    door = TestDoorA(source_entity_uuid=uuid4(), position=(4, 2))
    grid.place_object(door.uuid, (4, 2))
    # Open the door
    door.is_open = True
    door.blocks_movement = False
    door.blocks_vision_field = False

    Entity.update_all_entities_senses()

    encounter = setup_encounter(interceptor, door_closer, enemy)

    # === Turn 1 (Interceptor): prepare intercept at (6,2) through open door ===
    charge_dest = (6, 2)
    intercepting = Intercepting(
        source_entity_uuid=interceptor.uuid,
        target_entity_uuid=interceptor.uuid,
        charge_destination=charge_dest,
    )
    intercepting.duration.duration_type = DurationType.ROUNDS
    intercepting.duration.duration = 1
    interceptor.add_condition(intercepting)

    # === Turn 2 (DoorCloser): close the door → fires SPATIAL_OBJECT_CHANGED ===
    encounter.next_turn()
    execute_use_action(door_closer, door.uuid, "Close Door")
    assert_test(not door.is_open, "Door closed by DoorCloser")
    assert_test(door.blocks_movement, "Closed door blocks movement")

    # Verify _paths_dirty set on interceptor (door event propagated)
    assert_test(interceptor.senses._paths_dirty,
                "Interceptor's paths marked dirty after door closes")

    # === Turn 3 (Enemy): move through (6,2) — triggers intercept ===
    encounter.next_turn()
    move = Move(source_entity_uuid=enemy.uuid, end_position=(5, 2))
    move.apply()

    # Interceptor tried to charge but closed door at (4,2) blocked the path.
    # Charge stopped at (3,2) — NOT at charge_dest (6,2).
    assert_test(interceptor.position != charge_dest,
                f"Interceptor did NOT reach charge dest (at {interceptor.position}, dest was {charge_dest})")
    assert_test(interceptor.position[0] <= 3,
                f"Interceptor stopped before closed door (at {interceptor.position})")

    # Reaction consumed (charge attempt was made)
    assert_test(interceptor.action_economy.reactions.normalized_score == 0,
                "Reaction consumed (failed charge attempt)")

    # Enemy was NOT blocked (interceptor didn't reach charge_dest)
    # Enemy should have continued moving normally
    assert_test(enemy.position[0] <= 6,
                f"Enemy continued moving (at {enemy.position})")

    encounter.end_encounter()


def test_dodge_roll_enabled_by_door_open():
    """Entity backed against closed door. Ally opens door → dodge roll succeeds through it.

    Turn 1 (Defender): Apply DodgeRollFeature. Closed door at (5,2) blocks escape.
    Turn 2 (DoorOpener): Open door at (5,2) → SPATIAL_OBJECT_CHANGED.
    Turn 3 (Attacker): Attack defender → dodge roll fires → defender retreats through open door.
    """
    print("\n=== Test: Dodge Roll Enabled By Door Open ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 5)

    attacker = create_melee_fighter(name="Attacker", position=(3, 2), faction="monsters")
    defender = create_melee_fighter(name="Defender", position=(4, 2), faction="heroes")
    door_opener = create_melee_fighter(name="DoorOpener", position=(5, 3), faction="heroes")

    # Create closed door at (5,2)
    door = TestDoorA(source_entity_uuid=uuid4(), position=(5, 2))
    grid.place_object(door.uuid, (5, 2))
    assert_test(door.blocks_movement, "Door starts closed and blocks movement")

    Entity.update_all_entities_senses()

    encounter = setup_encounter(defender, door_opener, attacker)

    # === Turn 1 (Defender): apply DodgeRollFeature ===
    dodge_feat = DodgeRollFeature(
        source_entity_uuid=defender.uuid,
        target_entity_uuid=defender.uuid,
    )
    defender.add_condition(dodge_feat)

    # === Turn 2 (DoorOpener): open the door ===
    encounter.next_turn()
    execute_use_action(door_opener, door.uuid, "Open Door")
    assert_test(door.is_open, "Door opened by DoorOpener")
    assert_test(not door.blocks_movement, "Open door doesn't block movement")

    # === Turn 3 (Attacker): attack defender → dodge roll fires through open door ===
    encounter.next_turn()
    mod_uuid = force_attack_hit(attacker)
    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=defender.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    attack.apply()
    remove_attack_modifier(attacker, mod_uuid)

    # Defender dodged through the now-open door
    assert_test(defender.position[0] >= 5,
                f"Defender dodged through open door (at {defender.position})")
    assert_test(defender.action_economy.reactions.normalized_score == 0,
                "Reaction consumed (dodge succeeded through open door)")

    encounter.end_encounter()


# =============================================================================
# CONDITION REMOVAL TESTS
# =============================================================================

def test_intercept_condition_removed():
    """Remove Intercepting condition → enemy approaches → no intercept fires."""
    print("\n=== Test: Intercept Condition Removed ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 5)

    interceptor = create_melee_fighter(name="Interceptor", position=(2, 2), faction="heroes")
    enemy = create_melee_fighter(name="Enemy", position=(8, 2), faction="monsters")
    Entity.update_all_entities_senses()

    encounter = setup_encounter(interceptor, enemy)

    # === Interceptor: apply then remove ===
    intercepting = Intercepting(
        source_entity_uuid=interceptor.uuid,
        target_entity_uuid=interceptor.uuid,
        charge_destination=(5, 2),
    )
    intercepting.duration.duration_type = DurationType.ROUNDS
    intercepting.duration.duration = 1
    interceptor.add_condition(intercepting)
    assert_test("Intercepting" in interceptor.active_conditions, "Condition applied")

    interceptor.remove_condition("Intercepting")
    assert_test("Intercepting" not in interceptor.active_conditions, "Condition removed")

    # === Enemy moves through charge_dest — no intercept should fire ===
    encounter.next_turn()
    pos_before = interceptor.position
    move = Move(source_entity_uuid=enemy.uuid, end_position=(3, 2))
    move.apply()

    assert_test(interceptor.position == pos_before,
                f"Interceptor didn't move after removal (still at {interceptor.position})")
    assert_test(interceptor.action_economy.reactions.normalized_score == 1,
                "Reaction not consumed")

    encounter.end_encounter()


def test_dodge_roll_condition_removed():
    """Remove DodgeRollFeature → attacked → no dodge roll fires."""
    print("\n=== Test: Dodge Roll Condition Removed ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 5)

    attacker = create_melee_fighter(name="Attacker", position=(3, 2), faction="monsters")
    defender = create_melee_fighter(name="Defender", position=(4, 2), faction="heroes")
    Entity.update_all_entities_senses()

    encounter = setup_encounter(defender, attacker)

    dodge_feat = DodgeRollFeature(
        source_entity_uuid=defender.uuid,
        target_entity_uuid=defender.uuid,
    )
    defender.add_condition(dodge_feat)
    assert_test("Dodge Roll" in defender.active_conditions, "DodgeRoll applied")

    defender.remove_condition("Dodge Roll")
    assert_test("Dodge Roll" not in defender.active_conditions, "DodgeRoll removed")

    encounter.next_turn()
    pos_before = defender.position
    mod_uuid = force_attack_hit(attacker)
    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=defender.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    attack.apply()
    remove_attack_modifier(attacker, mod_uuid)

    assert_test(defender.position == pos_before,
                f"Defender didn't dodge after removal (still at {defender.position})")
    assert_test(defender.action_economy.reactions.normalized_score == 1,
                "Reaction not consumed")

    encounter.end_encounter()


# =============================================================================
# RUNNER
# =============================================================================

def run_all_tests():
    print("=" * 60)
    print("INTERCEPT & DODGE ROLL REACTION TESTS")
    print("(Homebrew — validates _paths_dirty pattern)")
    print("=" * 60)

    # Intercept tests
    test_intercept_basic()
    test_intercept_costs()
    test_intercept_reaction_consumed()
    test_intercept_ally_not_intercepted()
    test_intercept_blocks_enemy_movement_cost_and_no_oa()
    test_intercept_with_2_reactions_also_oa()

    # Dodge Roll tests
    test_dodge_roll_basic()
    test_dodge_roll_costs_reaction()
    test_dodge_roll_blocked()
    test_dodge_roll_partial()

    # _paths_dirty validation tests (door open/close during encounter turns)
    test_intercept_path_blocked_by_door()
    test_dodge_roll_enabled_by_door_open()

    # Condition removal tests
    test_intercept_condition_removed()
    test_dodge_roll_condition_removed()

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} assertions")
    if failed == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"FAILURES: {failed}")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
