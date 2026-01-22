"""
Test script for the session-based authority system.

Run this BEFORE interactive testing to verify:
1. Session creation and management
2. Game creation and entity assignment
3. Turn validation logic
4. Action validation

Usage:
    python examples/test_session_system.py
"""

from uuid import uuid4
import sys

# Add project root to path
sys.path.insert(0, '.')

from server.session import (
    SessionManager, PlayerSession, GameSession,
    PlayerType, ConnectionStatus, get_session_manager
)
from dnd.entity import Entity
from dnd.encounter import Encounter, TurnState
from dnd.controller import HumanController, Controller
from dnd.monsters.bestiary import create_skeleton
from dnd.core.gridmap import get_map, reset_map


def test_player_session():
    """Test PlayerSession creation and methods."""
    print("\n=== Test: PlayerSession ===")

    session = PlayerSession(
        session_id=uuid4(),
        player_type=PlayerType.HUMAN,
        name="TestPlayer"
    )

    assert session.connection_status == ConnectionStatus.CONNECTED
    print(f"  Created session: {session.session_id}")
    print(f"  Player type: {session.player_type.value}")
    print(f"  Status: {session.connection_status.value}")

    # Test entity ownership
    entity_uuid = uuid4()
    session.controlled_entities.add(entity_uuid)
    assert session.owns_entity(entity_uuid)
    assert not session.owns_entity(uuid4())
    print(f"  Entity ownership: OK")

    # Test ping
    import time
    old_activity = session.last_activity
    time.sleep(0.1)
    session.ping()
    assert session.last_activity > old_activity
    print(f"  Ping updates activity: OK")

    # Test disconnect
    session.disconnect()
    assert session.connection_status == ConnectionStatus.DISCONNECTED
    print(f"  Disconnect: OK")

    # Test reconnect via ping
    session.ping()
    assert session.connection_status == ConnectionStatus.CONNECTED
    print(f"  Reconnect via ping: OK")

    print("  PASSED")


def test_game_session():
    """Test GameSession with entity ownership."""
    print("\n=== Test: GameSession ===")

    game = GameSession(game_id=uuid4())

    # Create two sessions
    human_session = PlayerSession(
        session_id=uuid4(),
        player_type=PlayerType.HUMAN,
        name="Human"
    )
    claude_session = PlayerSession(
        session_id=uuid4(),
        player_type=PlayerType.CLAUDE,
        name="Claude"
    )

    game.add_player(human_session)
    game.add_player(claude_session)
    print(f"  Added 2 players: {len(game.players)} players in game")

    # Create fake entity UUIDs
    hero_uuid = uuid4()
    skeleton_uuid = uuid4()

    # Assign entities
    game.assign_entity(hero_uuid, human_session.session_id)
    game.assign_entity(skeleton_uuid, claude_session.session_id)

    assert game.get_entity_owner(hero_uuid) == human_session
    assert game.get_entity_owner(skeleton_uuid) == claude_session
    print(f"  Entity assignment: OK")

    # Verify ownership is in player sessions too
    assert human_session.owns_entity(hero_uuid)
    assert claude_session.owns_entity(skeleton_uuid)
    print(f"  Bidirectional ownership: OK")

    # Test player type lookup
    humans = game.get_players_by_type(PlayerType.HUMAN)
    claudes = game.get_players_by_type(PlayerType.CLAUDE)
    assert len(humans) == 1
    assert len(claudes) == 1
    print(f"  Player type lookup: OK")

    print("  PASSED")


def test_session_manager():
    """Test SessionManager singleton."""
    print("\n=== Test: SessionManager ===")

    # Reset singleton for clean test
    SessionManager.reset()

    mgr = get_session_manager()
    assert mgr is get_session_manager()  # Same instance
    print(f"  Singleton: OK")

    # Create sessions
    human = mgr.create_session(PlayerType.HUMAN, "Player1")
    claude = mgr.create_session(PlayerType.CLAUDE, "Claude")

    assert mgr.get_session(human.session_id) == human
    assert mgr.get_session(claude.session_id) == claude
    print(f"  Session creation: OK")

    # Create game
    game = mgr.create_game()
    assert mgr.get_active_game() == game
    print(f"  Game creation: OK")

    # Add players to game
    game.add_player(human)
    game.add_player(claude)

    # Cleanup
    SessionManager.reset()
    print("  PASSED")


def test_turn_validation():
    """Test turn-based validation with real entities."""
    print("\n=== Test: Turn Validation ===")

    # Reset everything
    SessionManager.reset()
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    # Create map
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Create entities
    hero = create_skeleton(name="Hero", position=(2, 7))
    skeleton = create_skeleton(name="Skeleton", position=(12, 7))

    print(f"  Created Hero: {hero.uuid}")
    print(f"  Created Skeleton: {skeleton.uuid}")

    # Create encounter
    encounter = Encounter(
        name="Test Encounter",
        source_entity_uuid=uuid4()
    )
    # Create controllers properly with source_entity_uuid
    hero_ctrl = HumanController(source_entity_uuid=hero.uuid)
    skeleton_ctrl = HumanController(source_entity_uuid=skeleton.uuid)
    encounter.add_combatant(hero, hero_ctrl)
    encounter.add_combatant(skeleton, skeleton_ctrl)
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    current = encounter.get_current_entity()
    print(f"  Current turn: {current.name if current else 'None'}")
    print(f"  Turn state: {encounter.turn_state.value}")

    # Setup session manager
    mgr = get_session_manager()

    # Create sessions
    human_session = mgr.create_session(PlayerType.HUMAN, "Human")
    claude_session = mgr.create_session(PlayerType.CLAUDE, "Claude")

    # Create game with encounter
    game = mgr.create_game(encounter)
    game.add_player(human_session)
    game.add_player(claude_session)

    # Assign entities
    game.assign_entity(hero.uuid, human_session.session_id)
    game.assign_entity(skeleton.uuid, claude_session.session_id)

    print(f"  Game setup complete")
    print(f"  Active entity: {game.active_entity_uuid}")
    print(f"  Active player: {game.active_player.name if game.active_player else 'None'}")

    # Test validation
    active_entity = game.active_entity_uuid
    active_player = game.active_player
    other_entity = skeleton.uuid if active_entity == hero.uuid else hero.uuid
    other_player = claude_session if active_player == human_session else human_session

    print(f"\n  Testing validation...")

    # Should succeed: active player acting with their entity
    try:
        session, g = mgr.validate_action(active_player.session_id, active_entity)
        print(f"  Valid action (correct player, correct entity): OK")
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

    # Should fail: other player trying to act
    try:
        mgr.validate_action(other_player.session_id, other_entity)
        print(f"  FAILED: Should have rejected wrong player's turn")
        return False
    except Exception as e:
        print(f"  Rejected wrong player: OK ({e.detail})")

    # Should fail: active player trying to use other's entity
    try:
        mgr.validate_action(active_player.session_id, other_entity)
        print(f"  FAILED: Should have rejected wrong entity")
        return False
    except Exception as e:
        print(f"  Rejected wrong entity: OK ({e.detail})")

    # Should fail: invalid session
    try:
        mgr.validate_action(uuid4(), active_entity)
        print(f"  FAILED: Should have rejected invalid session")
        return False
    except Exception as e:
        print(f"  Rejected invalid session: OK ({e.detail})")

    print("  PASSED")
    return True


def test_turn_switching():
    """Test that turn switching updates active player correctly."""
    print("\n=== Test: Turn Switching ===")

    # Reset everything
    SessionManager.reset()
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    # Create map
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Create entities
    hero = create_skeleton(name="Hero", position=(2, 7))
    skeleton = create_skeleton(name="Skeleton", position=(12, 7))

    # Create encounter
    encounter = Encounter(
        name="Test Encounter",
        source_entity_uuid=uuid4()
    )
    # Create controllers properly with source_entity_uuid
    hero_ctrl = HumanController(source_entity_uuid=hero.uuid)
    skeleton_ctrl = HumanController(source_entity_uuid=skeleton.uuid)
    encounter.add_combatant(hero, hero_ctrl)
    encounter.add_combatant(skeleton, skeleton_ctrl)
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    first_entity = encounter.get_current_entity()
    print(f"  First turn: {first_entity.name}")

    # Setup session manager
    mgr = get_session_manager()
    human_session = mgr.create_session(PlayerType.HUMAN, "Human")
    claude_session = mgr.create_session(PlayerType.CLAUDE, "Claude")

    game = mgr.create_game(encounter)
    game.add_player(human_session)
    game.add_player(claude_session)
    game.assign_entity(hero.uuid, human_session.session_id)
    game.assign_entity(skeleton.uuid, claude_session.session_id)

    first_player = game.active_player
    print(f"  First player: {first_player.name}")

    # End turn and advance to next turn
    encounter.next_turn()  # This ends current turn and starts next one

    second_entity = encounter.get_current_entity()
    second_player = game.active_player
    print(f"  Second turn: {second_entity.name}")
    print(f"  Second player: {second_player.name}")

    # Verify different entity/player
    assert first_entity.uuid != second_entity.uuid
    assert first_player.session_id != second_player.session_id
    print(f"  Turn switched correctly: OK")

    # Verify validation reflects new turn
    try:
        mgr.validate_action(second_player.session_id, second_entity.uuid)
        print(f"  New player can act: OK")
    except Exception as e:
        print(f"  FAILED: New player should be able to act: {e}")
        return False

    try:
        mgr.validate_action(first_player.session_id, first_entity.uuid)
        print(f"  FAILED: Old player should not be able to act")
        return False
    except Exception as e:
        print(f"  Old player rejected: OK ({e.detail})")

    print("  PASSED")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("SESSION SYSTEM TESTS")
    print("=" * 60)

    try:
        test_player_session()
        test_game_session()
        test_session_manager()

        if not test_turn_validation():
            print("\n!!! Turn validation test FAILED !!!")
            return 1

        if not test_turn_switching():
            print("\n!!! Turn switching test FAILED !!!")
            return 1

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n!!! EXCEPTION: {e} !!!")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
