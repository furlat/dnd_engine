"""Canonical authored-encounter mechanics regressions."""

from dataclasses import dataclass
from uuid import UUID

from dnd.blocks.base_item import (
    BaseItem,
)
from dnd.content.scenarios.scenario_catalog import (
    AUTHORED_ENCOUNTERS,
    encounter_definition,
)
from dnd.content.scenarios.scenario_deployment import (
    AssembledScenario,
    assemble_scenario,
)
from dnd.core.base_block import BaseBlock
from dnd.types.world import CardinalDirection, LightLevel
from dnd.core.base_actions import (
    ActionAvailabilityStatus,
    TargetType,
)
from dnd.types.world import MovementMode
from dnd.types.equipment import WeaponSlot
from dnd.core.events.events_registry import (
    EventPhase,
)
from dnd.types.damage import DamageType
from dnd.core.gridmap import get_map
from dnd.core.base_conditions import BaseCondition
from dnd.types.encounter_state import EncounterState
from dnd.spatial.environmental_conditions import SpikeTrap
from dnd.entities.entity import Entity
from dnd.game import Game
from dnd.items.environment import DirectionalDoor
from dnd.items.environment_interactables import StorageChest, TrapLever
from dnd.actions.operations import execute_by_index
from dnd.maps.arena_layout import (
    DIFFICULT_TERRAIN_POSITIONS,
    DOOR_POSITION,
    SPIKE_ZONE_POSITIONS,
    TRAP_LEVER_POSITION,
    WATER_POSITIONS,
)
from dnd.monsters.skeleton_abilities import MarkTargetAction
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import SpatialCondition


@dataclass(frozen=True)
class CanonicalScenario:
    """Small test view over the product assembler result."""

    assembled: AssembledScenario

    @property
    def hero(self) -> Entity:
        return self.assembled.entities_by_roster_slot["roster_1"][0]

    @property
    def monsters(self) -> tuple[Entity, ...]:
        return self.assembled.entities_by_roster_slot["roster_2"]

    @property
    def encounter(self):
        return self.assembled.encounter

    @property
    def controllers(self) -> dict[UUID, object]:
        return dict(self.assembled.controllers)

    @property
    def notable_positions(self) -> dict[str, tuple[int, int]]:
        return dict(self.assembled.notable_positions)

    @property
    def environment(self):
        return self.assembled.battlefield.environment


def create_authored_encounter(encounter_id: str) -> CanonicalScenario:
    """Assemble one authored encounter through the sole product path."""
    reset_engine_runtime()
    return CanonicalScenario(
        assemble_scenario(
            Game(),
            encounter_definition(f"encounter.{encounter_id}"),
        ),
    )


def action_template_names(entity: Entity) -> set[str]:
    """Return action-template names registered on an entity."""
    return {action.name for action in entity.registered_actions if action.name}


def equipped_item_name(entity: Entity, slot: WeaponSlot) -> str:
    """Return the equipped item name for a weapon slot."""
    item = entity.equipment.get_item_by_slot(slot)
    assert item is not None
    assert item.name is not None
    return item.name


def inventory_item_names(entity: Entity) -> set[str]:
    """Return item names directly stored in an entity inventory."""
    return {item.name for item in entity.inventory.items.values() if item.name}


def available_action_display_names(entity: Entity) -> set[str]:
    """Return currently available display names across all action buckets."""
    return {action.display_name for action in entity.get_available_actions().all_actions}


def objects_at(position: tuple[int, int]) -> list[BaseItem]:
    """Return item-like objects placed at a grid position."""
    objects: list[BaseItem] = []
    for object_uuid in get_map().get_objects_at(position):
        obj = BaseBlock.get(object_uuid)
        if isinstance(obj, BaseItem):
            objects.append(obj)
    return objects


def door_at(position: tuple[int, int]) -> DirectionalDoor:
    """Return the directional door placed at a grid position."""
    doors = [obj for obj in objects_at(position) if isinstance(obj, DirectionalDoor)]
    assert len(doors) == 1
    return doors[0]


def test_authored_encounter_catalog_has_complete_stable_inventory() -> None:
    """All retained authored encounters have stable unique product ids."""
    ids = [
        recipe.encounter_id.removeprefix("encounter.")
        for recipe in AUTHORED_ENCOUNTERS
    ]

    assert ids == [
        "standard_skeleton_doors",
        "goblin_water_skirmish",
        "skeleton_anti_aoe_split",
        "caster_crossfire",
        "item_resource_gauntlet",
        "double_door_dark_hunt",
        "arcane_device_control",
        "skeleton_mark_focus_fire",
        "buff_consumable_ambush",
        "forced_movement_hazard_bridge",
        "line_aoe_corridor",
        "zone_control_web_gauntlet",
        "support_attrition_cache",
        "high_level_spell_resource_duel",
        "sorcerer_barbarian_duel",
        "class_party_mirror_scramble",
        "ranged_loadout_kiting_ring",
        "concentration_control_crossroads",
        "teleport_escape_skirmish",
        "darkness_reveal_labyrinth",
        "guardian_zone_shrine",
        "trap_lever_killzone",
        "condition_lock_sanctum",
        "necrotic_anti_healing_duel",
        "damage_affinity_weapon_lab",
        "resistance_weapon_counterplay",
        "field_cache_loot_race",
        "cleanse_support_triage",
        "multi_target_missile_allocation",
        "multi_projectile_no_aoe_lab",
        "reaction_counterspell_lab",
        "guardian_choke_body_block",
        "multi_object_control_room",
        "srd_low_cr_patrol",
        "srd_undead_crypt",
        "srd_goblinoid_warband",
        "srd_divine_cult_cell",
        "srd_elite_mercenary_contract",
        "elevation_proving_ground",
    ]
    assert len(ids) == len(set(ids))
    assert all(recipe.tags == ("authored",) for recipe in AUTHORED_ENCOUNTERS)


def test_each_authored_encounter_builds_started_with_unique_positions() -> None:
    """Every authored encounter assembles through the product runtime."""
    for recipe in AUTHORED_ENCOUNTERS:
        reset_engine_runtime()
        arena = CanonicalScenario(assemble_scenario(Game(), recipe))
        actors = (arena.hero, *arena.monsters)
        positions = [actor.position for actor in actors]

        assert arena.encounter.state == EncounterState.ACTIVE
        assert arena.hero.faction == "faction_1"
        assert {monster.faction for monster in arena.monsters} == {"faction_2"}
        assert len(arena.controllers) == len(actors)
        assert len(arena.encounter.combatants) == len(actors)
        assert len(positions) == len(set(positions))
        assert all(arena.encounter.get_controller_for(actor.uuid) for actor in actors)
        assert Entity.get(arena.hero.uuid) is arena.hero


def test_srd_undead_crypt_gives_shield_fighter_ranged_counterplay() -> None:
    """The undead crypt should not force melee-only chase loops against archers."""
    arena = create_authored_encounter("srd_undead_crypt")

    assert equipped_item_name(arena.hero, WeaponSlot.MELEE_MAIN) == "Longsword"
    assert equipped_item_name(arena.hero, WeaponSlot.MELEE_OFF) == "Shield"
    assert equipped_item_name(arena.hero, WeaponSlot.RANGED_MAIN) == "Longbow"
    assert "Attack_RANGED_MAIN" in action_template_names(arena.hero)


def test_standard_skeleton_door_arena_uses_current_baseline_content() -> None:
    """The baseline arena keeps the door, skeleton trio, and standard hazards."""
    arena = create_authored_encounter("standard_skeleton_doors")
    grid = get_map()
    water_tile = grid.get_tile(*WATER_POSITIONS[0])
    difficult_tile = grid.get_tile(*DIFFICULT_TERRAIN_POSITIONS[0])
    monster_names = {monster.name for monster in arena.monsters}

    assert arena.environment is not None
    assert arena.environment.barrier.door.is_open is False
    assert grid.get_object_position(arena.environment.barrier.door.uuid) == DOOR_POSITION
    assert water_tile is not None
    assert water_tile.name == "Water"
    assert water_tile.get_movement_cost(MovementMode.WALKING) == 0
    assert difficult_tile is not None
    assert difficult_tile.name == "Difficult Terrain"
    assert difficult_tile.get_movement_cost(MovementMode.WALKING) > 1
    assert monster_names == {
        "Validation Skeleton Warrior",
        "Validation Skeleton Archer",
        "Validation Skeleton Warlock",
    }


def test_standard_arena_water_uses_canonical_mechanics() -> None:
    """The product arena authors water through the canonical tile factory."""
    arena = create_authored_encounter("standard_skeleton_doors")
    grid = get_map()

    for position in WATER_POSITIONS:
        tile = grid.get_tile(*position)
        assert tile is not None
        assert tile.name == "Water"
        assert tile.get_movement_cost(MovementMode.WALKING) == 0
        assert tile.get_movement_cost(MovementMode.SWIMMING) == 1
        assert not grid.is_walkable(*position, mode=MovementMode.WALKING)
        assert grid.is_walkable(*position, mode=MovementMode.SWIMMING)
        arena.hero.senses.visible[position] = True

    assert not grid.can_transition(
        WATER_POSITIONS[0],
        WATER_POSITIONS[1],
        movement_mode=MovementMode.WALKING,
    )
    assert grid.can_transition(
        WATER_POSITIONS[0],
        WATER_POSITIONS[1],
        movement_mode=MovementMode.SWIMMING,
    )

def test_goblin_water_skirmish_samples_goblins_caster_and_route_blockers() -> None:
    """The goblin arena includes skirmish actions and water path pressure."""
    arena = create_authored_encounter("goblin_water_skirmish")
    grid = get_map()
    water_tile = grid.get_tile(*arena.notable_positions["water_choke"])
    monster_actions = {monster.name: action_template_names(monster) for monster in arena.monsters}
    caster = next(monster for monster in arena.monsters if monster.name == "Validation Goblin Caster")

    assert arena.environment is not None
    assert water_tile is not None
    assert water_tile.name == "Water"
    assert water_tile.get_movement_cost(MovementMode.WALKING) == 0
    assert equipped_item_name(arena.hero, WeaponSlot.RANGED_MAIN) == "Longbow"
    assert "Nimble Escape: Hide" in monster_actions["Validation Goblin Skirmisher"]
    assert "Nimble Escape: Disengage" in monster_actions["Validation Goblin Archer"]
    assert {"Fireball", "Magic Missile", "Thunderwave"} <= action_template_names(caster)
    assert caster.is_spellcaster


def test_skeleton_anti_aoe_split_starts_monsters_outside_fireball_cluster() -> None:
    """The split arena starts monsters far enough apart to test clustering regressions."""
    arena = create_authored_encounter("skeleton_anti_aoe_split")
    positions = [monster.position for monster in arena.monsters]
    pairwise_manhattan = [
        abs(a[0] - b[0]) + abs(a[1] - b[1])
        for index, a in enumerate(positions)
        for b in positions[index + 1:]
    ]
    archer = next(monster for monster in arena.monsters if "Archer" in monster.name)
    warlock = next(monster for monster in arena.monsters if "Warlock" in monster.name)

    assert min(pairwise_manhattan) >= 10
    assert "Fireball" in action_template_names(arena.hero)
    assert "Mark Target" in action_template_names(archer)
    assert any(isinstance(action, MarkTargetAction) for action in archer.registered_actions)
    assert {"Eldritch Blast", "Necrotic Bless"} <= action_template_names(warlock)


def test_caster_crossfire_opens_door_and_mixes_frontline_ranged_and_spell_pressure() -> None:
    """The crossfire arena keeps a melee hero under mixed pressure roles."""
    arena = create_authored_encounter("caster_crossfire")
    guard, archer, mage = arena.monsters
    hero_action_names = action_template_names(arena.hero)

    assert arena.environment is not None
    assert arena.environment.barrier.door.is_open is True
    assert get_map().get_object_position(arena.environment.barrier.door.uuid) == DOOR_POSITION
    assert "Frenzy" in hero_action_names
    assert "Rage" not in hero_action_names
    assert "Torch" in inventory_item_names(arena.hero)
    assert len(arena.hero.get_visible_enemies()) >= 1
    assert equipped_item_name(arena.hero, WeaponSlot.MELEE_MAIN) == "Greataxe"
    assert equipped_item_name(guard, WeaponSlot.MELEE_MAIN) == "Longsword"
    assert equipped_item_name(archer, WeaponSlot.RANGED_MAIN) == "Shortbow"
    assert mage.is_spellcaster
    assert {"Fireball", "Lightning Bolt", "Greater Invisibility"} & action_template_names(mage)


def test_item_resource_gauntlet_gives_hero_varied_item_backed_options() -> None:
    """The item gauntlet pressures inventory and charged-item action handling."""
    arena = create_authored_encounter("item_resource_gauntlet")
    item_names = inventory_item_names(arena.hero)
    caster = next(monster for monster in arena.monsters if monster.name == "Validation Cache Mage")
    goblin_archer = next(monster for monster in arena.monsters if "Goblin Archer" in monster.name)

    assert {
        "Wand of Magic Missiles",
        "Wand of Fire",
        "Scroll of Fireball",
        "Scroll of Magic Missile",
        "Scroll of Spike Growth",
        "Potion of Greater Invisibility",
        "Weapon Coat of Flame",
    } <= item_names
    assert equipped_item_name(arena.hero, WeaponSlot.RANGED_MAIN) == "Longbow"
    assert {"Nimble Escape: Hide", "Nimble Escape: Disengage"} <= action_template_names(goblin_archer)
    assert {"Fireball", "Greater Invisibility", "Magic Missile"} <= action_template_names(caster)


def test_double_door_dark_hunt_has_two_closed_doors_and_no_initial_enemy_sight() -> None:
    """The dark hunt pressures repeated door navigation before combat contact."""
    arena = create_authored_encounter("double_door_dark_hunt")
    first_door = door_at(arena.notable_positions["first_door"])
    second_door = door_at(arena.notable_positions["second_door"])
    tile = get_map().get_tile(*arena.hero.position)

    assert first_door.name == "First Door"
    assert second_door.name == "Second Door"
    assert first_door.is_open is False
    assert second_door.is_open is False
    assert tile is not None
    assert tile.default_light == LightLevel.DARKNESS
    assert "Torch" in inventory_item_names(arena.hero)
    assert not arena.hero.get_visible_enemies()
    assert all(monster.senses.sense_modes for monster in arena.monsters)


def test_arcane_device_control_places_usable_environment_object_and_floor_pickup() -> None:
    """The device arena pressures environment-object use and nearby pickups."""
    arena = create_authored_encounter("arcane_device_control")
    cannon_objects = objects_at(arena.notable_positions["fireball_cannon"])
    potion_objects = objects_at(arena.notable_positions["floor_potion"])
    cannon_names = {obj.name for obj in cannon_objects}
    potion_names = {obj.name for obj in potion_objects}
    device_mage = next(monster for monster in arena.monsters if monster.name == "Validation Device Mage")

    assert "Fireball Cannon" in cannon_names
    assert "Potion of Healing" in potion_names
    assert any(obj.is_usable for obj in cannon_objects)
    assert any(obj.is_pickable for obj in potion_objects)
    assert {"Fireball", "Thunderwave", "Magic Missile"} <= action_template_names(device_mage)
    assert len(arena.hero.get_visible_enemies()) >= 1


def test_skeleton_mark_focus_fire_has_support_marker_and_durable_target() -> None:
    """The focus-fire arena exposes Mark Target against a high-AC shield hero."""
    arena = create_authored_encounter("skeleton_mark_focus_fire")
    archer = next(monster for monster in arena.monsters if monster.name == "Validation Focus Archer")

    assert equipped_item_name(arena.hero, WeaponSlot.MELEE_MAIN) == "Longsword"
    assert equipped_item_name(arena.hero, WeaponSlot.MELEE_OFF) == "Shield"
    assert "Mark Target" in action_template_names(archer)
    assert any(isinstance(action, MarkTargetAction) for action in archer.registered_actions)
    assert len(arena.hero.get_visible_enemies()) == 3


def test_buff_consumable_ambush_surfaces_buff_items_and_scrolls() -> None:
    """The ambush arena exposes self-buff items and scroll pressure."""
    arena = create_authored_encounter("buff_consumable_ambush")
    mage = next(monster for monster in arena.monsters if monster.name == "Validation Ambush Mage")
    goblin_archer = next(monster for monster in arena.monsters if monster.name == "Validation Ambush Goblin Archer")
    guard = next(monster for monster in arena.monsters if monster.name == "Validation Ambush Guard")

    assert arena.environment is not None
    assert arena.environment.barrier.door.is_open is True
    assert "Scroll of Hold Person" in inventory_item_names(mage)
    assert {"Potion of Greater Invisibility", "Potion of Haste"} <= inventory_item_names(mage)
    assert "Potion of Haste" in inventory_item_names(goblin_archer)
    assert "Potion of Greater Invisibility" in inventory_item_names(guard)
    assert {"Nimble Escape: Hide", "Nimble Escape: Disengage"} <= action_template_names(goblin_archer)


def test_forced_movement_hazard_bridge_places_thunderwave_near_hazards() -> None:
    """The hazard bridge arena combines displacement spells with terrain cost."""
    arena = create_authored_encounter("forced_movement_hazard_bridge")
    grid = get_map()
    warlock = next(monster for monster in arena.monsters if monster.name == "Validation Hazard Warlock")
    mage = next(monster for monster in arena.monsters if monster.name == "Validation Hazard Mage")
    water_tile = grid.get_tile(*arena.notable_positions["water_choke"])
    spike_tile = grid.get_tile(*arena.notable_positions["spike_zone_sample"])

    assert arena.environment is not None
    assert arena.environment.barrier.door.is_open is True
    assert "Thunderwave" in action_template_names(warlock)
    assert "Thunderwave" in action_template_names(mage)
    assert water_tile is not None
    assert water_tile.get_movement_cost(MovementMode.WALKING) == 0
    assert spike_tile is not None
    assert spike_tile.active_conditions == {}
    spike_effect = BaseCondition.get(
        arena.environment.spike_condition_uuid,
    )
    assert isinstance(spike_effect, SpikeTrap)
    assert arena.notable_positions["spike_zone_sample"] in (
        spike_effect.affected_positions
    )


def test_line_aoe_corridor_aligns_multiple_targets_on_spell_lane() -> None:
    """The line corridor arena makes line spells and multi-target rows visible."""
    arena = create_authored_encounter("line_aoe_corridor")
    lane_y = arena.hero.position[1]
    lane_monsters = [monster for monster in arena.monsters if monster.position[1] == lane_y]
    off_lane = next(monster for monster in arena.monsters if monster.name == "Validation Off-Line Goblin")
    line_mage = next(monster for monster in arena.monsters if monster.name == "Validation Line Mage")

    assert "Lightning Bolt" in action_template_names(arena.hero)
    assert "Magic Missile" in action_template_names(arena.hero)
    assert "Lightning Bolt" in action_template_names(line_mage)
    assert len(lane_monsters) == 3
    assert off_lane.position[1] != lane_y


def test_zone_control_web_gauntlet_adds_control_spells_and_route_pressure() -> None:
    """The web gauntlet samples control spells in the standard terrain package."""
    arena = create_authored_encounter("zone_control_web_gauntlet")
    control_mage = next(monster for monster in arena.monsters if monster.name == "Validation Web Mage")
    goblin_archer = next(monster for monster in arena.monsters if monster.name == "Validation Web Goblin Archer")
    water_tile = get_map().get_tile(*arena.notable_positions["water_choke"])

    assert arena.environment is not None
    assert arena.environment.barrier.door.is_open is True
    assert {"Web", "Grease", "Spike Growth", "Fog Cloud"} <= action_template_names(control_mage)
    assert {"Nimble Escape: Hide", "Nimble Escape: Disengage"} <= action_template_names(goblin_archer)
    assert water_tile is not None
    assert water_tile.get_movement_cost(MovementMode.WALKING) == 0


def test_support_attrition_cache_includes_wounded_ally_and_support_actions() -> None:
    """The attrition arena makes support and healing rows immediately relevant."""
    arena = create_authored_encounter("support_attrition_cache")
    wounded_guard = next(monster for monster in arena.monsters if monster.name == "Validation Wounded Guard")
    support_caster = next(monster for monster in arena.monsters if monster.name == "Validation Support Acolyte")

    assert wounded_guard.health.damage_taken == 10
    assert {"Bless", "Bane", "Aid", "Healing Word", "Shield of Faith", "Sanctuary"} <= action_template_names(support_caster)
    assert {"Potion of Healing", "Weapon Coat of Lightning"} <= inventory_item_names(support_caster)
    assert equipped_item_name(arena.hero, WeaponSlot.MELEE_OFF) == "Shield"


def test_high_level_spell_resource_duel_samples_expensive_spells() -> None:
    """The high-level duel avoids overfitting validation to low-slot spell lists."""
    arena = create_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if monster.name == "Validation Duel Archmage")

    # The player-class factory enforces the legal Sorcerer known-spell cap;
    # the authored archmage owns the wider scenario-only spell surface.
    assert {
        "Cone of Cold",
        "Banishment",
        "Greater Invisibility",
    } <= action_template_names(arena.hero)
    assert {"Cone of Cold", "Cloudkill", "Hypnotic Pattern", "Slow", "Banishment", "Dimension Door"} <= action_template_names(archmage)
    assert archmage.action_economy.spell_slot_5.normalized_score >= 1


def test_sorcerer_barbarian_duel_uses_real_class_factories() -> None:
    """The duel fixture pressures control magic against melee recovery."""
    arena = create_authored_encounter("sorcerer_barbarian_duel")
    barbarian = arena.monsters[0]
    barbarian_action_names = action_template_names(barbarian)

    assert arena.hero.name == "Validation Duel Sorcerer"
    assert barbarian.name == "Validation Duel Barbarian"
    assert abs(arena.hero.position[0] - barbarian.position[0]) + abs(arena.hero.position[1] - barbarian.position[1]) == 8
    assert {"Hold Person", "Magic Missile", "Scorching Ray", "Fireball"} <= action_template_names(arena.hero)
    assert {"Frenzy", "Reckless Attack"} <= barbarian_action_names
    assert "Rage" not in barbarian_action_names
    assert equipped_item_name(barbarian, WeaponSlot.MELEE_MAIN) == "Greataxe"
    assert arena.hero.get_visible_enemies()
    assert barbarian.get_visible_enemies()


def test_class_party_mirror_scramble_uses_real_class_factories_and_features() -> None:
    """The mirror arena avoids testing only bespoke monster factories."""
    arena = create_authored_encounter("class_party_mirror_scramble")
    berserker = next(monster for monster in arena.monsters if monster.name == "Validation Mirror Berserker")
    archer = next(monster for monster in arena.monsters if monster.name == "Validation Mirror Archer")
    sorcerer = next(monster for monster in arena.monsters if monster.name == "Validation Mirror Sorcerer")
    berserker_action_names = action_template_names(berserker)
    archer_action_names = action_template_names(archer)
    sorcerer_action_names = action_template_names(sorcerer)

    assert "Frenzy" in berserker_action_names
    assert "Rage" not in berserker_action_names
    assert "Reckless Attack" in berserker_action_names
    assert equipped_item_name(berserker, WeaponSlot.MELEE_MAIN) == "Handaxe"
    assert equipped_item_name(berserker, WeaponSlot.MELEE_OFF) == "Handaxe"
    assert "Second Wind" in archer_action_names
    assert "Action Surge" in archer_action_names
    assert equipped_item_name(archer, WeaponSlot.RANGED_MAIN) == "Longbow"
    assert {"Fireball", "Lightning Bolt", "Slow", "Haste"} <= sorcerer_action_names
    assert "Quickened Spell" in sorcerer_action_names


def test_ranged_loadout_kiting_ring_keeps_ranged_gear_and_terrain_pressure() -> None:
    """The kiting arena pressures ranged-first decisions across blockers."""
    arena = create_authored_encounter("ranged_loadout_kiting_ring")
    grid = get_map()
    captain = next(monster for monster in arena.monsters if monster.name == "Validation Kiting Archer Captain")
    goblin_archer = next(monster for monster in arena.monsters if monster.name == "Validation Kiting Goblin Archer")
    warlock = next(monster for monster in arena.monsters if monster.name == "Validation Kiting Warlock")
    water_tile = grid.get_tile(*arena.notable_positions["water_choke"])
    difficult_tile = grid.get_tile(*arena.notable_positions["difficult_band"])

    assert arena.environment is not None
    assert arena.environment.barrier.door.is_open is True
    assert equipped_item_name(captain, WeaponSlot.RANGED_MAIN) == "Longbow"
    assert equipped_item_name(captain, WeaponSlot.MELEE_MAIN) == "Shortsword"
    assert {"Nimble Escape: Hide", "Nimble Escape: Disengage"} <= action_template_names(goblin_archer)
    assert {"Eldritch Blast", "Thunderwave", "Necrotic Bless"} <= action_template_names(warlock)
    assert water_tile is not None
    assert water_tile.get_movement_cost(MovementMode.WALKING) == 0
    assert difficult_tile is not None
    assert difficult_tile.get_movement_cost(MovementMode.WALKING) > 1


def test_concentration_control_crossroads_mixes_control_support_and_friendly_fire_pressure() -> None:
    """The crossroads arena exposes concentration control beside support rows."""
    arena = create_authored_encounter("concentration_control_crossroads")
    guard = next(monster for monster in arena.monsters if monster.name == "Validation Crossroads Guard")
    controller = next(monster for monster in arena.monsters if monster.name == "Validation Crossroads Controller")
    support = next(monster for monster in arena.monsters if monster.name == "Validation Crossroads Support")
    controller_action_names = action_template_names(controller)
    support_action_names = action_template_names(support)

    assert abs(guard.position[0] - arena.hero.position[0]) + abs(guard.position[1] - arena.hero.position[1]) == 3
    assert {"Web", "Hypnotic Pattern", "Slow", "Fireball"} <= controller_action_names
    assert {"Bless", "Bane", "Aid", "Healing Word", "Shield of Faith", "Sanctuary"} <= support_action_names
    assert support.is_spellcaster
    assert controller.is_spellcaster


def test_teleport_escape_skirmish_samples_mobility_and_ranged_pressure() -> None:
    """The escape arena keeps teleport and ranged options visible together."""
    arena = create_authored_encounter("teleport_escape_skirmish")
    escape_mage = next(monster for monster in arena.monsters if monster.name == "Validation Escape Mage")
    goblin_archer = next(monster for monster in arena.monsters if monster.name == "Validation Escape Goblin Archer")
    water_tile = get_map().get_tile(*arena.notable_positions["water_choke"])
    difficult_tile = get_map().get_tile(*arena.notable_positions["difficult_band"])

    assert arena.environment is not None
    assert arena.environment.barrier.door.is_open is True
    assert {"Misty Step", "Dimension Door", "Blur", "Mirror Image", "Ray of Frost"} <= action_template_names(escape_mage)
    assert {"Nimble Escape: Hide", "Nimble Escape: Disengage"} <= action_template_names(goblin_archer)
    assert water_tile is not None
    assert water_tile.get_movement_cost(MovementMode.WALKING) == 0
    assert difficult_tile is not None
    assert difficult_tile.get_movement_cost(MovementMode.WALKING) > 1


def test_darkness_reveal_labyrinth_uses_existing_vision_spell_surface() -> None:
    """The vision arena combines dark rooms, doors, concealment, and reveal spells."""
    arena = create_authored_encounter("darkness_reveal_labyrinth")
    shadow_mage = next(monster for monster in arena.monsters if monster.name == "Validation Shadow Mage")
    reveal_mage = next(monster for monster in arena.monsters if monster.name == "Validation Reveal Mage")
    first_door = door_at(arena.notable_positions["first_door"])
    second_door = door_at(arena.notable_positions["second_door"])
    hero_tile = get_map().get_tile(*arena.hero.position)

    assert first_door.is_open is False
    assert second_door.is_open is False
    assert hero_tile is not None
    assert hero_tile.default_light == LightLevel.DARKNESS
    assert {"Darkness", "Fog Cloud", "Invisibility", "Greater Invisibility", "Silence"} <= action_template_names(shadow_mage)
    assert {"See Invisibility", "Daylight", "Darkvision", "Light", "True Seeing"} <= action_template_names(reveal_mage)
    assert "Torch" in inventory_item_names(arena.hero)


def test_guardian_zone_shrine_samples_persistent_zone_and_healing_support() -> None:
    """The shrine arena exposes guardian, aura, healing, and support choices."""
    arena = create_authored_encounter("guardian_zone_shrine")
    wounded_guard = next(monster for monster in arena.monsters if monster.name == "Validation Shrine Wounded Guard")
    shrine_keeper = next(monster for monster in arena.monsters if monster.name == "Validation Shrine Keeper")

    assert wounded_guard.health.damage_taken == 24
    assert {
        "Spirit Guardians",
        "Guardian of Faith",
        "Beacon of Hope",
        "Mass Healing Word",
        "Flame Strike",
        "Sanctuary",
    } <= action_template_names(shrine_keeper)
    assert equipped_item_name(arena.hero, WeaponSlot.MELEE_OFF) == "Shield"
    assert shrine_keeper.is_spellcaster


def test_trap_lever_killzone_makes_hazard_object_use_available() -> None:
    """The killzone arena puts a real trap lever action next to monster actors."""
    arena = create_authored_encounter("trap_lever_killzone")
    lever_guard = next(monster for monster in arena.monsters if monster.name == "Validation Lever Guard")
    lever_objects = objects_at(arena.notable_positions["trap_lever"])
    spike_tile = get_map().get_tile(*arena.notable_positions["spike_zone_sample"])

    assert arena.environment is not None
    assert arena.environment.barrier.door.is_open is True
    assert arena.notable_positions["trap_lever"] == TRAP_LEVER_POSITION
    assert arena.notable_positions["spike_zone_sample"] in SPIKE_ZONE_POSITIONS
    assert any(isinstance(obj, TrapLever) for obj in lever_objects)
    assert any(name.startswith("Pull Lever") for name in available_action_display_names(lever_guard))
    assert spike_tile is not None
    assert spike_tile.active_conditions == {}
    spike_effect = BaseCondition.get(
        arena.environment.spike_condition_uuid,
    )
    assert isinstance(spike_effect, SpikeTrap)
    assert spike_effect.affected_positions == SPIKE_ZONE_POSITIONS
    assert (
        get_map().get_spatial_condition_uuids_at(
            arena.notable_positions["spike_zone_sample"],
        )
        == {spike_effect.uuid}
    )


def test_trap_lever_killzone_deactivates_handler_markers_and_hazard_routing() -> None:
    """Pulling the linked lever removes every objective part of the spike trap."""
    arena = create_authored_encounter("trap_lever_killzone")
    lever_guard = next(monster for monster in arena.monsters if monster.name == "Validation Lever Guard")
    lever = next(
        obj
        for obj in objects_at(arena.notable_positions["trap_lever"])
        if isinstance(obj, TrapLever)
    )
    available = lever_guard.get_available_actions()
    lever_row = next(
        row
        for row in available.all_actions
        if row.template_name.startswith("Pull Lever")
    )

    event = execute_by_index(
        lever_guard,
        lever_row.template_name,
        lever_row.valid_targets[0].index,
        available=available,
    )

    assert event is not None
    assert event.phase is EventPhase.COMPLETION
    assert lever.charges == 0
    assert arena.environment is not None
    assert (
        BaseCondition.get(arena.environment.spike_condition_uuid)
        is None
    )
    for position in SPIKE_ZONE_POSITIONS:
        tile = get_map().get_tile(*position)
        assert tile is not None
        assert "Spike Trap" not in tile.active_conditions
        assert tile.is_hazardous_for(lever_guard.uuid) is False
        assert get_map().get_spatial_condition_uuids_at(position) == set()


def test_condition_lock_sanctum_uses_disabling_and_support_spell_surface() -> None:
    """The lock arena gives enemy casters condition and support alternatives."""
    arena = create_authored_encounter("condition_lock_sanctum")
    controller = next(monster for monster in arena.monsters if monster.name == "Validation Lock Controller")
    support = next(monster for monster in arena.monsters if monster.name == "Validation Lock Support")
    hero_action_names = action_template_names(arena.hero)

    assert "Frenzy" in hero_action_names
    assert "Rage" not in hero_action_names
    assert {"Command", "Hold Person", "Fear", "Hypnotic Pattern", "Slow", "Banishment"} <= action_template_names(controller)
    assert {"Bless", "Bane", "Guiding Bolt", "Shield of Faith", "Sanctuary"} <= action_template_names(support)
    assert controller.is_spellcaster
    assert support.is_spellcaster


def test_necrotic_anti_healing_duel_surfaces_anti_heal_and_execution_spells() -> None:
    """The necrotic arena samples anti-healing status and high-slot burst."""
    arena = create_authored_encounter("necrotic_anti_healing_duel")
    necromancer = next(monster for monster in arena.monsters if monster.name == "Validation Necromancer")
    archer = next(monster for monster in arena.monsters if monster.name == "Validation Necrotic Archer")

    assert arena.hero.health.damage_taken == 8
    assert "Potion of Healing" in inventory_item_names(arena.hero)
    assert {"Chill Touch", "Blindness/Deafness", "Bestow Curse", "Blight", "Harm", "Finger of Death"} <= action_template_names(necromancer)
    assert necromancer.action_economy.spell_slot_7.normalized_score >= 1
    assert "Mark Target" in action_template_names(archer)


def test_damage_affinity_weapon_lab_surfaces_vulnerabilities_and_weapon_damage_types() -> None:
    """The affinity lab exposes target weaknesses and row damage labels."""
    arena = create_authored_encounter("damage_affinity_weapon_lab")
    crusher = next(monster for monster in arena.monsters if monster.name == "Validation Crusher Captain")
    actions = crusher.get_available_actions().entity_actions
    club = next(
        action
        for action in actions
        if action.weapon_name == "Club"
        and action.availability_status is ActionAvailabilityStatus.AVAILABLE
    )
    shortsword = next(
        action
        for action in actions
        if action.weapon_name == "Shortsword"
        and action.availability_status is ActionAvailabilityStatus.AVAILABLE
    )
    extra_attacks = tuple(
        action
        for action in actions
        if action.template_name.startswith("Extra Attack")
    )

    assert arena.hero.name == "Validation Vulnerable Skeleton Hero"
    assert arena.hero.health.damage_multiplier(DamageType.BLUDGEONING) == 2
    assert arena.hero.health.damage_multiplier(DamageType.PIERCING) == 1
    assert equipped_item_name(crusher, WeaponSlot.MELEE_MAIN) == "Shortsword"
    assert equipped_item_name(crusher, WeaponSlot.MELEE_OFF) == "Club"
    assert club.damage_types == ["Bludgeoning"]
    assert shortsword.damage_types == ["Piercing"]
    assert {target.target_uuid for target in club.valid_targets} == {arena.hero.uuid}
    assert {target.target_uuid for target in shortsword.valid_targets} == {arena.hero.uuid}
    assert {row.availability_status for row in extra_attacks} == {
        ActionAvailabilityStatus.REQUIREMENTS_UNMET
    }
    assert all(not row.valid_targets for row in extra_attacks)


def test_resistance_weapon_counterplay_uses_non_skeleton_damage_affinities() -> None:
    """The resistance lab exposes weapon counterplay without skeleton hardcoding."""
    arena = create_authored_encounter("resistance_weapon_counterplay")
    captain = next(monster for monster in arena.monsters if monster.name == "Validation Counterplay Captain")
    actions = captain.get_available_actions().entity_actions
    club = next(
        action
        for action in actions
        if action.weapon_name == "Club"
        and action.availability_status is ActionAvailabilityStatus.AVAILABLE
    )
    shortsword = next(
        action
        for action in actions
        if action.weapon_name == "Shortsword"
        and action.availability_status is ActionAvailabilityStatus.AVAILABLE
    )
    extra_attacks = tuple(
        action
        for action in actions
        if action.template_name.startswith("Extra Attack")
    )

    assert arena.hero.name == "Validation Resistant Duelist"
    assert arena.hero.health.damage_multiplier(DamageType.BLUDGEONING) == 2
    assert arena.hero.health.damage_multiplier(DamageType.PIERCING) == 0.5
    assert equipped_item_name(captain, WeaponSlot.MELEE_MAIN) == "Shortsword"
    assert equipped_item_name(captain, WeaponSlot.MELEE_OFF) == "Club"
    assert club.damage_types == ["Bludgeoning"]
    assert shortsword.damage_types == ["Piercing"]
    assert {target.target_uuid for target in club.valid_targets} == {arena.hero.uuid}
    assert {target.target_uuid for target in shortsword.valid_targets} == {arena.hero.uuid}
    assert {row.availability_status for row in extra_attacks} == {
        ActionAvailabilityStatus.REQUIREMENTS_UNMET
    }
    assert all(not row.valid_targets for row in extra_attacks)


def test_field_cache_loot_race_exposes_adjacent_chest_resource_choice() -> None:
    """The cache arena exposes map-loot interaction before items are carried."""
    arena = create_authored_encounter("field_cache_loot_race")
    cache_objects = objects_at(arena.notable_positions["field_cache"])
    chest = next(obj for obj in cache_objects if isinstance(obj, StorageChest))
    chest_item_names = {item.name for item in chest.chest_inventory.items.values()}

    assert arena.hero.name == "Validation Cache Runner"
    assert "Loot All (Validation Field Cache)" in available_action_display_names(arena.hero)
    assert {
        "Scroll of Fireball",
        "Scroll of Magic Missile",
        "Acid Flask",
        "Potion of Healing",
        "Weapon Coat of Flame",
    } <= chest_item_names


def test_cleanse_support_triage_starts_with_impaired_allies_and_restoration() -> None:
    """The triage arena makes support rows inspectable against real conditions."""
    arena = create_authored_encounter("cleanse_support_triage")
    poisoned_guard = next(monster for monster in arena.monsters if monster.name == "Validation Poisoned Guard")
    blinded_archer = next(monster for monster in arena.monsters if monster.name == "Validation Blinded Archer")
    support = next(monster for monster in arena.monsters if monster.name == "Validation Restoration Acolyte")

    assert "Poisoned" in poisoned_guard.active_conditions
    assert "Blinded" in blinded_archer.active_conditions
    assert poisoned_guard.health.damage_taken == 10
    assert {
        "Lesser Restoration",
        "Greater Restoration",
        "Cure Wounds",
        "Healing Word",
        "Mass Healing Word",
        "Bless",
        "Aid",
    } <= action_template_names(support)


def test_multi_target_missile_allocation_surfaces_projectiles_and_targets() -> None:
    """The missile arena makes multi-target metadata obvious for agents."""
    arena = create_authored_encounter("multi_target_missile_allocation")
    missile_rows = [
        action
        for action in arena.hero.get_available_actions().entity_actions
        if action.template_name == "Magic Missile" or action.base_template_name == "Magic Missile"
    ]
    missile = missile_rows[0]
    target_names = {target.target_name for target in missile.valid_targets}

    assert arena.hero.name == "Validation Missile Sorcerer"
    assert "Scorching Ray" in action_template_names(arena.hero)
    assert missile.target_type == TargetType.MULTI_ENTITY
    assert missile.num_projectiles is not None and missile.num_projectiles >= 3
    assert missile.allow_same_target is True
    assert {
        "Validation Missile Warrior",
        "Validation Missile Archer",
        "Validation Missile Goblin",
    } <= target_names
    assert all(monster.health.damage_taken > 0 for monster in arena.monsters)


def test_multi_target_area_log_summarizes_child_targets() -> None:
    """A multi-target parent log exposes child target facts for agents."""
    arena = create_authored_encounter("multi_target_missile_allocation")
    available = arena.hero.get_available_actions()
    fireball = next(
        action
        for action in available.position_actions
        if action.base_template_name == "Fireball"
    )
    expected_names = {
        "Validation Missile Archer",
        "Validation Missile Warrior",
        "Validation Missile Goblin",
    }
    target = next(
        row
        for row in fireball.valid_targets
        if set(row.affected_entity_names or []) == expected_names
    )

    event = execute_by_index(
        arena.hero,
        fireball.template_name,
        target.index,
        available=available,
    )

    assert event is not None
    assert event.combat_log is not None
    combat_log = event.combat_log
    assert set(combat_log.data["target_names"]) == expected_names
    assert len(combat_log.data["per_target_damage"]) == 3
    assert combat_log.data["saves_succeeded"] + combat_log.data["saves_failed"] == 3


def test_multi_projectile_no_aoe_lab_keeps_projectile_rows_without_area_escape() -> None:
    """The projectile lab forces missile/ray allocation instead of Fireball."""
    arena = create_authored_encounter("multi_projectile_no_aoe_lab")
    available = arena.hero.get_available_actions()
    missile_rows = [
        action
        for action in available.entity_actions
        if action.template_name == "Magic Missile" or action.base_template_name == "Magic Missile"
    ]
    ray_rows = [
        action
        for action in available.entity_actions
        if action.template_name == "Scorching Ray" or action.base_template_name == "Scorching Ray"
    ]
    missile = missile_rows[0]
    target_names = {target.target_name for target in missile.valid_targets}

    assert arena.hero.name == "Validation Projectile Sorcerer"
    assert "Fireball" not in action_template_names(arena.hero)
    assert "Lightning Bolt" not in action_template_names(arena.hero)
    assert "Hold Person" not in action_template_names(arena.hero)
    assert all(action.base_template_name != "Fireball" for action in available.position_actions)
    assert all(action.base_template_name != "Lightning Bolt" for action in available.position_actions)
    assert ray_rows
    assert missile.target_type == TargetType.MULTI_ENTITY
    assert missile.num_projectiles is not None and missile.num_projectiles >= 3
    assert missile.allow_same_target is True
    assert {
        "Validation Projectile Warrior",
        "Validation Projectile Archer",
        "Validation Projectile Goblin",
    } <= target_names
    assert {monster.name: monster.get_hp() for monster in arena.monsters} == {
        "Validation Projectile Warrior": 3,
        "Validation Projectile Archer": 2,
        "Validation Projectile Goblin": 3,
    }


def test_reaction_counterspell_lab_registers_reaction_defenses() -> None:
    """The reaction lab exposes Counterspell and Shield as real handlers."""
    arena = create_authored_encounter("reaction_counterspell_lab")
    abjurer = next(monster for monster in arena.monsters if monster.name == "Validation Counterspell Abjurer")
    shield_mage = next(monster for monster in arena.monsters if monster.name == "Validation Shield Mage")

    assert arena.hero.get_event_handler_by_name("Counterspell") is not None
    assert abjurer.get_event_handler_by_name("Counterspell") is not None
    assert shield_mage.get_event_handler_by_name("Shield") is not None
    assert {"Fireball", "Lightning Bolt", "Magic Missile"} <= action_template_names(abjurer)
    assert {"Magic Missile", "Scorching Ray", "Mirror Image", "Blur"} <= action_template_names(shield_mage)
    assert abjurer.action_economy.spell_slot_3.normalized_score >= 1


def test_guardian_choke_body_block_exposes_persistent_zone_and_body_lane() -> None:
    """The choke arena combines a blocking guard with guardian-style spells."""
    arena = create_authored_encounter("guardian_choke_body_block")
    guard = next(monster for monster in arena.monsters if monster.name == "Validation Choke Guard")
    guardian_caster = next(monster for monster in arena.monsters if monster.name == "Validation Guardian Caster")
    guardian_rows = [
        action
        for action in guardian_caster.get_available_actions().position_actions
        if action.template_name == "Guardian of Faith" or action.base_template_name == "Guardian of Faith"
    ]

    assert arena.environment is not None
    assert arena.environment.barrier.door.is_open is True
    assert guard.position == arena.notable_positions["guard_choke"]
    assert guard.position == DOOR_POSITION
    assert {"Guardian of Faith", "Spirit Guardians", "Sanctuary", "Healing Word", "Flame Strike"} <= action_template_names(guardian_caster)
    assert guardian_rows


def test_multi_object_control_room_exposes_several_nearby_object_actions() -> None:
    """The control room puts object choices into one immediate decision epoch."""
    arena = create_authored_encounter("multi_object_control_room")
    display_names = available_action_display_names(arena.hero)
    cache_objects = objects_at(arena.notable_positions["control_cache"])
    cannon_objects = objects_at(arena.notable_positions["fireball_cannon"])
    torch_objects = objects_at(arena.notable_positions["wall_torch"])

    assert arena.environment is not None
    assert arena.environment.barrier.door.is_open is True
    assert any(isinstance(obj, StorageChest) for obj in cache_objects)
    assert any(obj.name == "Fireball Cannon" for obj in cannon_objects)
    assert any(obj.name == "Wall Torch" for obj in torch_objects)
    torch = next(obj for obj in torch_objects if obj.name == "Wall Torch")
    torch_placement = get_map().get_object_placement(torch.uuid)
    assert torch_placement is not None
    assert (
        torch_placement.boundary_direction,
        torch_placement.base_height_steps,
        torch_placement.top_height_steps,
        torch_placement.orientation,
    ) == (
        CardinalDirection.WEST,
        1,
        2,
        CardinalDirection.EAST,
    )
    assert any(name.startswith("Pull Lever") for name in display_names)
    assert any(name.startswith("Loot All") for name in display_names)
    assert any(name.startswith("Extinguish Wall Torch") for name in display_names)
    assert any("Fireball" in name for name in display_names)


def test_unknown_authored_encounter_id_is_rejected() -> None:
    """Unknown catalog ids fail explicitly."""
    try:
        create_authored_encounter("not-a-real-arena")
    except ValueError as exc:
        assert "unknown authored encounter" in str(exc).casefold()
    else:
        raise AssertionError("Expected unknown arena id to raise ValueError")
