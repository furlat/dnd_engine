"""Real destruction leaves independently owned materials with ground contact."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import AttackObject, Jump, Move
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import BaseItem
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.condition_types import ConditionTag
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    DamageAppliedEvent, Event, EventPhase, EventQueue, ItemDestructionEvent,
    SavingThrowEvent, SpatialEffectChangeEvent, SpatialEffectInteractionEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.core.modifiers import ResistanceStatus
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_liquid_barrel
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.residues import BLOOD_RESIDUE, deposit_residue
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import FireSurface, SteamCloud, WetSurface
from dnd.spells.conjuration import GreaseZone
from dnd.types.residues import ResidueEllipse
from dnd.types.spatial_effects import SpatialEffectInteractionIntensity, SpatialEffectInteractionOperation
from dnd.types.world import OccupancyLayer


CONTENTS = ("oil", "water", "grease", "blood", "poison", "dread_blood")


@pytest.fixture
def world() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(6, 4))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def actor(world: Game, position: tuple[int, int], *, movement: int = 30,
          poison_immune: bool = False) -> Entity:
    result = Entity.create(uuid4(), "Barrel traveler", config=EntityConfig(
        position=position,
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18)),
        action_economy=ActionEconomyConfig(movement=movement),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")],
                            immunities=[DamageType.POISON] if poison_immune else []),
    ))
    setup_standard_actions(result)
    result.install_initial_items(((build_authored_item("weapon.longsword", result.uuid), WeaponSlot.MELEE_MAIN),))
    result.compose_entity()
    world.deploy_entity(result, position)
    return result


def placed_barrel(world: Game, contents: str, position: tuple[int, int] = (1, 1)) -> tuple[BaseItem, Entity]:
    attacker = actor(world, (position[0], position[1] - 1))
    # These isolate material-contact and lifetime rules. Surrounding-area behavior
    # is exercised through default authored barrels in test_liquid_barrel_areas.py.
    barrel = build_liquid_barrel(f"environment.blocker.{contents}_barrel", attacker.uuid, radius_cells=0)
    barrel.place_on_grid(position)
    return barrel, attacker


def break_with_attack(barrel: BaseItem, attacker: Entity) -> Event:
    attacker.action_economy.reset_all_costs()
    with fixed_dice_faces(8):
        result = AttackObject(source_entity_uuid=attacker.uuid, target_entity_uuid=barrel.uuid).apply()
    assert result is not None and not result.canceled
    assert barrel.integrity is ItemIntegrity.DESTROYED
    return result


def completed(cursor: int) -> list[Event]:
    return [event for _, event in EventQueue.iter_events_since(cursor) if event.phase is EventPhase.COMPLETION]


def walk(traveler: Entity, path: list[tuple[int, int]]) -> Event:
    traveler.materialize_navigation()
    result = Move(source_entity_uuid=traveler.uuid, end_position=path[-1], path=path, prefer_safe=False).apply()
    assert result is not None
    assert not result.canceled, result.status_message
    return result


def material_state(position: tuple[int, int]) -> tuple:
    tile = get_map().get_tile(*position)
    assert tile is not None
    return (tuple((condition.uuid, condition.name) for condition in get_map().get_spatial_conditions_at(position)),
            tile.to_world_tile_state().residues)


@pytest.mark.parametrize("contents", CONTENTS)
def test_attack_spills_once_under_destruction_and_material_survives_wreck_retirement(world: Game, contents: str) -> None:
    barrel, attacker = placed_barrel(world, contents)
    original = get_map().get_object_placement(barrel.uuid)
    assert original is not None and not get_map().is_walkable_for(1, 1)
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(1):
        hit = AttackObject(source_entity_uuid=attacker.uuid, target_entity_uuid=barrel.uuid).apply()
    assert hit is not None and not hit.canceled and barrel.get_hp() == 7
    assert material_state((1, 1)) == ((), ())
    break_with_attack(barrel, attacker)
    destruction, = [event for event in completed(cursor) if isinstance(event, ItemDestructionEvent)]
    assert destruction.previous_placement == original
    assert destruction.resulting_state is not None and destruction.resulting_state.item_uuid == barrel.uuid
    assert get_map().is_walkable_for(1, 1)
    effects = [event for event in completed(cursor)
               if isinstance(event, (SpatialEffectChangeEvent, ConditionApplicationEvent))]
    assert effects
    for effect in effects:
        ancestor = effect
        while ancestor.lineage_uuid != destruction.lineage_uuid:
            parent = ancestor.get_parent_event()
            assert parent is not None
            ancestor = parent
    state = material_state((1, 1))
    assert state != ((), ())
    cursor = EventQueue.event_cursor()
    barrel.destroy()
    assert barrel.receive_damage(10, DamageType.FIRE, attacker.uuid) == 0
    assert completed(cursor) == []
    barrel.retire()
    assert get_map().get_object_placement(barrel.uuid) is None
    assert material_state((1, 1)) == state
    assert not any(isinstance(event, ItemDestructionEvent) for event in completed(cursor))


@pytest.mark.parametrize("contents", CONTENTS)
def test_retiring_intact_or_destroying_unplaced_barrel_never_spills(world: Game, contents: str) -> None:
    barrel, _ = placed_barrel(world, contents)
    barrel.retire()
    assert material_state((1, 1)) == ((), ())
    unplaced = build_authored_item(f"environment.blocker.{contents}_barrel", uuid4())
    unplaced.destroy()
    assert not get_map().get_spatial_conditions()
    assert material_state((1, 1)) == ((), ())


@pytest.mark.parametrize("contents", CONTENTS)
@pytest.mark.parametrize("travel", ("walk", "jump_over", "jump_land"))
def test_liquid_effects_follow_actual_ground_contact(world: Game, contents: str, travel: str) -> None:
    position = (2, 1) if travel == "jump_land" else (1, 1)
    barrel, attacker = placed_barrel(world, contents, position)
    traveler = actor(world, (0, 1))
    break_with_attack(barrel, attacker)
    hp = traveler.get_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 10)):
        if travel == "walk":
            walk(traveler, [(0, 1), (1, 1), (2, 1)])
        else:
            jump = Jump(source_entity_uuid=traveler.uuid, end_position=(2, 1)).apply()
            assert jump is not None and not jump.canceled
    contact = travel != "jump_over"
    assert traveler.get_hp() == hp - (2 if contents == "poison" and contact else 0)
    assert traveler.occupancy_layer is OccupancyLayer.GROUND
    saves = [event for event in completed(cursor) if isinstance(event, SavingThrowEvent)]
    assert len(saves) == int(contact and contents in {"grease", "dread_blood"})
    if contents == "dread_blood" and contact:
        assert traveler.position == ((0, 1) if travel == "walk" else (1, 1))
        assert "Frightened" not in traveler.active_conditions
    else:
        assert traveler.position == (2, 1)
    assert ("Wet" in traveler.active_conditions) is (contents == "water" and travel == "jump_land")
    assert ("Prone" in traveler.active_conditions) is (contents == "grease" and contact)
    if contents == "grease" and contact:
        assert ConditionTag.MAGICAL not in traveler.active_conditions["Prone"].tags
    if contents == "blood":
        _, residues = material_state(position)
        assert len(residues) == 1 and residues[0].residue_id == "residue.blood" and residues[0].amount == 5


@pytest.mark.parametrize("immune", (False, True))
def test_poison_reentry_uses_poison_damage_and_native_immunity(world: Game, immune: bool) -> None:
    barrel, attacker = placed_barrel(world, "poison")
    traveler = actor(world, (0, 1), poison_immune=immune)
    break_with_attack(barrel, attacker)
    hp = traveler.get_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(2, 3):
        walk(traveler, [(0, 1), (1, 1), (2, 1)])
        walk(traveler, [(2, 1), (1, 1), (0, 1)])
    assert traveler.get_hp() == hp - (0 if immune else 5)
    injuries = [event for event in completed(cursor) if isinstance(event, DamageAppliedEvent)]
    assert len(injuries) == (0 if immune else 2)
    assert all(event.damage_type is DamageType.POISON for event in injuries)


def test_water_membership_survives_other_source_removal_and_ends_on_real_exit(world: Game) -> None:
    barrel, attacker = placed_barrel(world, "water")
    traveler = actor(world, (0, 1))
    cause = break_with_attack(barrel, attacker)
    walk(traveler, [(0, 1), (1, 1)])
    water, = get_map().get_spatial_conditions_at((1, 1))
    assert isinstance(water, WetSurface)
    assert traveler.health.get_resistance(DamageType.FIRE) is ResistanceStatus.RESISTANCE
    steam = SteamCloud(source_entity_uuid=attacker.uuid, position=(1, 1), affected_positions={(1, 1)})
    steam.activate(parent_event=cause)
    assert steam.deactivate(parent_event=cause)
    assert "Wet" in traveler.active_conditions
    walk(traveler, [(1, 1), (2, 1)])
    assert "Wet" not in traveler.active_conditions
    assert traveler.health.get_resistance(DamageType.FIRE) is ResistanceStatus.NONE


@pytest.mark.parametrize("save", (1, 20))
def test_grease_saves_preserve_mundane_tags_and_existing_turn_end_behavior(world: Game, save: int) -> None:
    barrel, attacker = placed_barrel(world, "grease")
    break_with_attack(barrel, attacker)
    with fixed_dice_faces(save):
        walk(attacker, [(1, 0), (1, 1)])
    assert ("Prone" in attacker.active_conditions) is (save == 1)
    assert "Concentrating" not in attacker.active_conditions
    if "Prone" in attacker.active_conditions:
        attacker.remove_condition("Prone")
    with fixed_dice_faces(1):
        attacker.on_turn_end(round_number=1, turn_index=0)
    assert "Prone" in attacker.active_conditions
    assert not attacker.active_conditions["Prone"].tags
    zone, = get_map().get_spatial_conditions_at((1, 1))
    assert isinstance(zone, GreaseZone) and zone.source_entity_uuid == barrel.uuid


@pytest.mark.parametrize("movement,save,expected_position,feared", (
    (30, 1, (0, 1), False), (5, 1, (1, 1), True), (30, 20, (1, 1), False),
))
def test_dread_uses_paid_reverse_step_or_retains_fear_when_exhausted(
    world: Game, movement: int, save: int, expected_position: tuple[int, int], feared: bool,
) -> None:
    barrel, attacker = placed_barrel(world, "dread_blood")
    traveler = actor(world, (0, 1), movement=movement)
    break_with_attack(barrel, attacker)
    with fixed_dice_faces(save):
        walk(traveler, [(0, 1), (1, 1)])
    assert traveler.position == expected_position
    assert ("Frightened" in traveler.active_conditions) is feared
    assert traveler.action_economy.movement.normalized_score == movement - (10 if save == 1 and movement > 5 else 5)


def interact(source: Entity, operation: SpatialEffectInteractionOperation) -> Event:
    event = SpatialEffectInteractionEvent(source_entity_uuid=source.uuid, positions=((1, 1),),
        operation=operation, intensity=SpatialEffectInteractionIntensity.STRONG)
    return event.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)


@pytest.mark.parametrize("contents,operation,expected_name", (
    ("oil", SpatialEffectInteractionOperation.IGNITE, "Fire Surface"),
    ("water", SpatialEffectInteractionOperation.FREEZE, "Ice Surface"),
    ("water", SpatialEffectInteractionOperation.ELECTRIFY, "Electrified Water"),
))
def test_ground_material_replacements_preserve_jump_admission(
    world: Game, contents: str, operation: SpatialEffectInteractionOperation, expected_name: str,
) -> None:
    barrel, attacker = placed_barrel(world, contents)
    traveler = actor(world, (0, 1))
    break_with_attack(barrel, attacker)
    interact(attacker, operation)
    material, = get_map().get_spatial_conditions_at((1, 1))
    assert material.name == expected_name
    hp = traveler.get_hp()
    cursor = EventQueue.event_cursor()
    jump = Jump(source_entity_uuid=traveler.uuid, end_position=(2, 1)).apply()
    assert jump is not None and not jump.canceled
    assert traveler.get_hp() == hp and not any(isinstance(event, SavingThrowEvent) for event in completed(cursor))
    assert "Wet" not in traveler.active_conditions and "Prone" not in traveler.active_conditions
    with fixed_dice_faces(1, 1):
        walk(traveler, [(2, 1), (1, 1)])
    assert traveler.get_hp() < hp or "Prone" in traveler.active_conditions


def test_fire_breaks_oil_into_fire_and_water_vapor_remains_a_cloud(world: Game) -> None:
    oil, attacker = placed_barrel(world, "oil")
    oil.receive_damage(12, DamageType.FIRE, attacker.uuid)
    fire, = get_map().get_spatial_conditions_at((1, 1))
    assert isinstance(fire, FireSurface)
    assert fire.affected_occupancy_layers == frozenset({OccupancyLayer.GROUND})
    oil.retire()
    fire.deactivate(parent_event=completed(0)[-1])
    water = build_liquid_barrel("environment.blocker.water_barrel", attacker.uuid, radius_cells=0)
    water.place_on_grid((1, 1))
    break_with_attack(water, attacker)
    interact(attacker, SpatialEffectInteractionOperation.VAPORIZE)
    cloud, = get_map().get_spatial_conditions_at((1, 1))
    assert isinstance(cloud, SteamCloud) and cloud.affects_occupancy_layer(OccupancyLayer.AIR)


def test_bulk_blood_deposit_preserves_existing_membership_and_caps_actual_amount(world: Game) -> None:
    tile = get_map().get_tile(1, 1)
    assert tile is not None
    ellipse = ResidueEllipse(center=(0.5, 0.5), radius_x=0.3, radius_y=0.3)
    initial = deposit_residue(tile, BLOOD_RESIDUE, amount=2, ellipses=(ellipse,))
    result = deposit_residue(tile, BLOOD_RESIDUE, amount=5, ellipses=(ellipse,))
    assert initial is not None and result is not None
    assert initial.condition_uuid == result.condition_uuid
    assert result.amount == result.contributions[0].amount == 5
    assert len(result.contributions) == 1


@pytest.mark.parametrize("contents,remaining", (("oil", 15), ("grease", 15), ("blood", 20), ("water", 20)))
def test_only_authored_slippery_material_adds_difficult_terrain(world: Game, contents: str, remaining: int) -> None:
    barrel, attacker = placed_barrel(world, contents)
    traveler = actor(world, (0, 1))
    break_with_attack(barrel, attacker)
    with fixed_dice_faces(20):
        walk(traveler, [(0, 1), (1, 1), (2, 1)])
    assert traveler.action_economy.movement.normalized_score == remaining


def test_grease_preserves_native_immediate_standing_policy_during_own_turn(world: Game) -> None:
    barrel, attacker = placed_barrel(world, "grease")
    traveler = actor(world, (0, 1))
    break_with_attack(barrel, attacker)
    traveler.on_turn_start(round_number=1, turn_index=0)
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(1):
        walk(traveler, [(0, 1), (1, 1)])
    save, = [event for event in completed(cursor) if isinstance(event, SavingThrowEvent)]
    assert save.result is False
    assert "Prone" not in traveler.active_conditions
    # Entering grease costs 10ft, then existing Prone pays 15ft to stand.
    assert traveler.action_economy.movement.normalized_score == 5


@pytest.mark.parametrize("contents", ("oil", "water", "grease"))
def test_visible_material_publishes_only_its_observed_cells(world: Game, contents: str) -> None:
    barrel, attacker = placed_barrel(world, contents)
    observer = actor(world, (0, 1))
    break_with_attack(barrel, attacker)
    material, = get_map().get_spatial_conditions_at((1, 1))
    observer.update_entity_senses(max_distance=1)
    observed = observer.senses.spatial_effects[material.uuid]
    assert observed.positions == ((1, 1),)
    assert observed.content_ref == material.content_ref
    assert observed.name == material.name
    assert observed.anchor_position == (1, 1)
    hidden = WetSurface(source_entity_uuid=attacker.uuid, position=(4, 1),
                        affected_positions={(4, 1)}, condition_stealth_dc=999)
    cause = completed(0)[-1]
    hidden.activate(parent_event=cause)
    observer.update_entity_senses()
    assert (4, 1) in observer.senses.visible
    assert hidden.uuid not in observer.senses.spatial_effects


def test_visible_multi_cell_material_does_not_disclose_unseen_cells_or_anchor(world: Game) -> None:
    barrel, attacker = placed_barrel(world, "water", (4, 1))
    observer = actor(world, (0, 1))
    cause = break_with_attack(barrel, attacker)
    spread = WetSurface(source_entity_uuid=attacker.uuid, position=(4, 2),
                       affected_positions={(1, 1), (4, 2)})
    observer.update_entity_senses(max_distance=1)
    spread.activate(parent_event=cause)
    observer.update_entity_senses(max_distance=1)
    observed = observer.senses.spatial_effects[spread.uuid]
    assert observed.positions == ((1, 1),) and observed.anchor_position is None
