"""Physical contact remains distinct from sight, navigation and resource costs."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import Attack, Move
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.base_item import WorldItem
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, ItemDestructionEvent, Trigger
from dnd.core.base_tiles import Tile
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemDestructionProfile
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment import OpenDirectionalDoorAction, CloseDirectionalDoorAction
from dnd.monsters.traits import MultiattackAction, NaturalAttack
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import TrueStrike
from dnd.spells.divination import Guidance
from dnd.types.materials import Material
from dnd.types.physical_access import ContactPassage
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.types.world_placement import BoundaryStructure, BoundaryStructureKind, WorldPlacementKind, WorldPlacementSpec
from dnd.world_facts import WorldFacts, apply_world_fact


@pytest.fixture
def arena() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(8, 8))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


@pytest.mark.parametrize("position,allowed", [((2, 2), False), ((3, 2), True)])
def test_hand_operated_door_requires_nearby_contact(arena: Game, position, allowed):
    actor = Entity.create(uuid4(), "Operator", config=EntityConfig(position=position))
    actor.compose_entity()
    arena.deploy_entity(actor, position)
    door = build_authored_item("environment.door.fantasy_c1", actor.uuid)
    door.place_on_grid((4, 2), boundary_direction=CardinalDirection.EAST)
    result = OpenDirectionalDoorAction(source_entity_uuid=actor.uuid, source_item_uuid=door.uuid).apply()
    assert result is not None and result.canceled is not allowed
    assert door.get_spatial_open_state() is allowed
    if allowed:
        closed = CloseDirectionalDoorAction(source_entity_uuid=actor.uuid, source_item_uuid=door.uuid).apply()
        assert closed is not None and not closed.canceled
        assert door.get_spatial_open_state() is False


def combatants(game: Game, weapon: str, target_position: tuple[int, int] = (3, 2)) -> tuple[Entity, Entity, WeaponSlot]:
    slot = WeaponSlot.RANGED_MAIN if weapon == "longbow" else WeaponSlot.MELEE_MAIN
    attacker = Entity.create(uuid4(), "Attacker", config=EntityConfig(position=(2, 2), faction="heroes", health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=2, mode="maximums")])))
    setup_standard_actions(attacker)
    attacker.install_initial_items(((build_authored_item(f"weapon.{weapon}", attacker.uuid), slot),))
    attacker.compose_entity()
    game.deploy_entity(attacker, (2, 2))
    target = Entity.create(uuid4(), "Target", config=EntityConfig(position=target_position, faction="monsters", health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=4, hit_dice_count=1, mode="maximums")])))
    setup_standard_actions(target)
    target.compose_entity()
    game.deploy_entity(target, target_position)
    return attacker, target, slot


def barrier(policy: ContactPassage, *, insert: bool = False) -> WorldItem:
    item = WorldItem(item_id="test.window_insert" if insert else "test.window_frame",
        name="Grille" if insert else "Frame", source_entity_uuid=uuid4(),
        is_targetable=True, is_pickable=False,
        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=not insert, vertical_extent_steps=2),
        boundary_structure=BoundaryStructure(structure=BoundaryStructureKind.WALL,
            material=Material.STONE, blocked_channels=(WorldEdgeChannel.MOVEMENT,), contact_passage=policy),
        destruction_profile=ItemDestructionProfile(name="Broken", placement_spec=WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY, occupies_bands=False, vertical_extent_steps=1),
            boundary_structure=BoundaryStructure(structure=BoundaryStructureKind.WALL,
                material=Material.STONE, blocked_channels=())),
    )
    item.health = item.create_item_health(item.uuid, 3)
    item.place_on_grid((2, 2), boundary_direction=CardinalDirection.EAST)
    Entity.update_all_entities_senses()
    return item


@pytest.mark.parametrize("weapon,allowed", [
    ("dagger", True), ("handaxe", True), ("greataxe", False),
    ("spear", False), ("rapier", False), ("longbow", True),
])
def test_visible_window_uses_actual_weapon_and_rejects_before_cost(arena: Game, weapon: str, allowed: bool) -> None:
    source, target, slot = combatants(arena, weapon)
    barrier(ContactPassage.HAND_AND_LIGHT_WEAPONS)
    assert target.uuid in source.senses.entities
    attack = Attack(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid, weapon_slot=slot)
    assert attack.validate_requirements_for_discovery() is allowed
    hp, actions = target.get_hp(), source.action_economy.actions.normalized_score
    with fixed_dice_faces(20, 4, 4, 4, 4):
        result = attack.apply()
    assert result is not None and result.canceled is not allowed
    assert (target.get_hp() < hp) is allowed
    assert source.action_economy.actions.normalized_score == actions - int(allowed)


def test_insert_break_exposes_frame_policy_and_same_uuid_facts(arena: Game) -> None:
    source, target, slot = combatants(arena, "dagger")
    frame = barrier(ContactPassage.HAND_AND_LIGHT_WEAPONS)
    insert = barrier(ContactPassage.BLOCKED, insert=True)
    attack = Attack(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid, weapon_slot=slot)
    assert not attack.validate_requirements_for_discovery()
    insert.receive_damage(5, DamageType.BLUDGEONING, source.uuid)
    assert attack.validate_requirements_for_discovery()
    assert not get_map().can_transition((2, 2), (3, 2), source.uuid)
    assert frame.get_hp() == 3
    facts = WorldFacts()
    for _, event in EventQueue.iter_events_since(0):
        apply_world_fact(facts, event)
    assert facts.objects[frame.uuid].item.contact_passage is ContactPassage.HAND_AND_LIGHT_WEAPONS
    assert facts.objects[insert.uuid].item.contact_passage is ContactPassage.STRUCTURAL
    breaks = [event for _, event in EventQueue.iter_events_since(0)
              if isinstance(event, ItemDestructionEvent) and event.phase is EventPhase.COMPLETION]
    assert len(breaks) == 1


def test_weapon_wrapper_and_natural_attack_cannot_bypass_frame(arena: Game) -> None:
    source, target, _ = combatants(arena, "greataxe")
    barrier(ContactPassage.HAND_AND_LIGHT_WEAPONS)
    actions = source.action_economy.actions.normalized_score
    for action in (TrueStrike(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid),
                   NaturalAttack(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid)):
        result = action.apply()
        assert result is not None and result.canceled
        assert source.action_economy.actions.normalized_score == actions


@pytest.mark.parametrize("weapon,allowed", [("dagger", True), ("greataxe", False)])
def test_opportunity_attack_and_close_pressure_agree_at_window(arena: Game, weapon: str, allowed: bool) -> None:
    source, mover, _ = combatants(arena, weapon)
    barrier(ContactPassage.HAND_AND_LIGHT_WEAPONS)
    add_opportunity_attack_handler(source)
    assert mover.is_threatened() is allowed
    assert ((3, 2) in source.senses.get_threathened_positions()) is allowed
    hp, reactions = mover.get_hp(), source.action_economy.reactions.normalized_score
    with fixed_dice_faces(20, 4, 4, 4, 4, 4, 4):
        result = Move(source_entity_uuid=mover.uuid, end_position=(4, 2)).apply()
    assert result is not None
    assert (mover.get_hp() < hp) is allowed
    assert source.action_economy.reactions.normalized_score == reactions - int(allowed)
    if allowed:
        assert mover.position == (3, 2)  # lethal reaction before departure
    else:
        assert mover.position == (4, 2)


def test_heavy_weapon_can_hit_the_obstruction_it_cannot_cross(arena: Game) -> None:
    source, _, _ = combatants(arena, "greataxe")
    frame = barrier(ContactPassage.HAND_AND_LIGHT_WEAPONS)
    with fixed_dice_faces(19, 4):
        source.update_entity_senses()
        result = Attack(weapon_slot=WeaponSlot.MELEE_MAIN, source_entity_uuid=source.uuid, target_entity_uuid=frame.uuid).apply()
    assert result is not None and not result.canceled
    assert frame.get_hp() <= 0


def test_hidden_barrier_is_not_disclosed_but_execution_does_not_pay(arena: Game) -> None:
    source, target, _ = combatants(arena, "dagger")
    insert = barrier(ContactPassage.BLOCKED)
    insert.set_stealth_dc(100)
    Entity.update_all_entities_senses()
    assert insert.uuid not in source.senses.objects
    action = MultiattackAction(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
                              attack_sequence=((WeaponSlot.MELEE_MAIN, 1),))
    assert action.validate_requirements_for_discovery()
    hp, actions = target.get_hp(), source.action_economy.actions.normalized_score
    result = action.apply()
    assert result is not None and result.canceled
    assert target.get_hp() == hp
    assert source.action_economy.actions.normalized_score == actions
    assert (3, 2) not in source.senses.get_threathened_positions()
    assert (3, 2) in source.senses.get_threathened_positions(knowledge_observer_uuid=target.uuid)


@pytest.mark.parametrize("stage", ["execution", "before_roll", "after_roll"])
def test_execution_barrier_interrupts_without_refund(arena: Game, stage: str) -> None:
    source, target, slot = combatants(arena, "dagger")
    changed = False
    def interrupt(event: Event, _source) -> Event:
        nonlocal changed
        if (not changed and event.target_entity_uuid == target.uuid
                and (stage == "execution" or stage == "before_roll" and event.status_message == "Rolling attack"
                     or stage == "after_roll" and event.status_message is not None and event.status_message.startswith("Attack rolled"))):
            changed = True
            barrier(ContactPassage.BLOCKED)
        return event
    handler = EventHandler(name="Intervening barrier", source_entity_uuid=source.uuid,
        trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EXECUTION)],
        event_processor=interrupt)
    EventQueue.add_event_handler(handler)
    hp, actions = target.get_hp(), source.action_economy.actions.normalized_score
    result = Attack(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid, weapon_slot=slot).apply()
    assert changed and result is not None and result.canceled
    assert target.get_hp() == hp
    assert source.action_economy.actions.normalized_score == actions - 1


def test_touch_spell_does_not_depend_on_held_weapon(arena: Game) -> None:
    source, target, _ = combatants(arena, "greataxe")
    barrier(ContactPassage.HAND_AND_LIGHT_WEAPONS)
    result = Guidance(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None and not result.canceled
    source.action_economy.reset_all_costs()
    barrier(ContactPassage.BLOCKED, insert=True)
    before = source.action_economy.actions.normalized_score
    blocked = Guidance(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid).apply()
    assert blocked is not None and blocked.canceled
    assert source.action_economy.actions.normalized_score == before


def test_spent_reaction_preserves_close_pressure(arena: Game) -> None:
    source, target, _ = combatants(arena, "dagger")
    barrier(ContactPassage.HAND_AND_LIGHT_WEAPONS)
    add_opportunity_attack_handler(source)
    source.action_economy.consume("reactions", 1)
    assert target.is_threatened()
    hp = target.get_hp()
    result = Move(source_entity_uuid=target.uuid, end_position=(4, 2)).apply()
    assert result is not None and not result.canceled
    assert target.position == (4, 2) and target.get_hp() == hp


def test_solid_terrain_stops_projectiles_without_requiring_walkable_floor(arena: Game) -> None:
    source, target, slot = combatants(arena, "longbow", (5, 2))
    grid = get_map()
    grid.set_tile(3, 2, tile=Tile.create((3, 2), name="Water", walking_cost=0))
    Entity.update_all_entities_senses()
    attack = Attack(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid, weapon_slot=slot)
    assert attack.validate_requirements_for_discovery()
    grid.set_tile(3, 2, tile=Tile.create((3, 2), name="Physical barrier", blocks_propagation=True))
    Entity.update_all_entities_senses()
    result = attack.apply()
    assert result is not None and result.canceled
