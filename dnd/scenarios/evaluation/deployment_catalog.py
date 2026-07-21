"""Neutral portable and exact legacy deployment formations."""

from __future__ import annotations

from dnd.scenarios.evaluation.battlefield_catalog import BATTLEFIELDS
from dnd.scenarios.evaluation.models import DeploymentRoleSlot, DeploymentSpec


_NEUTRAL_HERO_SLOTS = ((2, 7),)
_NEUTRAL_MONSTER_SLOTS = ((12, 3), (12, 5), (12, 7), (12, 9), (12, 11))


def _role_slots(prefix: str, positions: tuple[tuple[int, int], ...]) -> tuple[DeploymentRoleSlot, ...]:
    """Assign sequential semantic roles to deployment coordinates."""
    if prefix == "hero":
        return (DeploymentRoleSlot(role="hero", position=positions[0]),)
    return tuple(
        DeploymentRoleSlot(role=f"monster_{index}", position=position)
        for index, position in enumerate(positions, start=1)
    )


def _neutral(battlefield_id: str, title: str) -> DeploymentSpec:
    """Create one portable formation with capacity for every canonical party."""
    return DeploymentSpec(
        deployment_id=f"neutral.{battlefield_id}",
        title=title,
        battlefield_id=battlefield_id,
        hero_slots=_NEUTRAL_HERO_SLOTS,
        monster_slots=_NEUTRAL_MONSTER_SLOTS,
        hero_role_slots=_role_slots("hero", _NEUTRAL_HERO_SLOTS),
        monster_role_slots=_role_slots("monster", _NEUTRAL_MONSTER_SLOTS),
        tags=("neutral", "portable", "opposed-zones"),
        portable=True,
        max_hero_members=1,
        max_monster_members=5,
        rating_eligible=True,
    )


NEUTRAL_DEPLOYMENTS: tuple[DeploymentSpec, ...] = tuple(
    _neutral(spec.battlefield_id, f"Neutral Deployment: {spec.title}")
    for spec in BATTLEFIELDS
)


def _legacy(
    arena_id: str,
    battlefield_id: str,
    hero_position: tuple[int, int],
    monster_positions: tuple[tuple[int, int], ...],
) -> DeploymentSpec:
    """Create one exact legacy formation outside the general ladder."""
    return DeploymentSpec(
        deployment_id=f"legacy.{arena_id}",
        title=f"Legacy Deployment: {arena_id}",
        battlefield_id=battlefield_id,
        hero_slots=(hero_position,),
        monster_slots=monster_positions,
        hero_role_slots=(DeploymentRoleSlot(role="hero", position=hero_position),),
        monster_role_slots=_role_slots("monster", monster_positions),
        tags=("legacy", "diagnostic"),
        portable=False,
        max_hero_members=1,
        max_monster_members=len(monster_positions),
        rating_eligible=False,
        source_arena_id=arena_id,
    )


LEGACY_DEPLOYMENTS: tuple[DeploymentSpec, ...] = (
    _legacy("standard_skeleton_doors", "battlefield.standard_hazards_closed", (2, 7), ((12, 5), (12, 7), (12, 9))),
    _legacy("goblin_water_skirmish", "battlefield.standard_hazards_closed", (4, 1), ((0, 1), (1, 2), (0, 4))),
    _legacy("skeleton_anti_aoe_split", "battlefield.open_floor_bright", (7, 7), ((2, 2), (12, 2), (12, 12))),
    _legacy("caster_crossfire", "battlefield.standard_hazards_open", (2, 7), ((8, 7), (12, 6), (12, 8))),
    _legacy("item_resource_gauntlet", "battlefield.open_floor_bright", (2, 7), ((10, 7), (11, 4), (12, 10))),
    _legacy("double_door_dark_hunt", "battlefield.double_door_dark", (2, 7), ((12, 6), (12, 8), (11, 7))),
    _legacy("arcane_device_control", "battlefield.arcane_device_bright", (3, 7), ((10, 6), (11, 8), (12, 7))),
    _legacy("skeleton_mark_focus_fire", "battlefield.open_floor_bright", (6, 7), ((9, 7), (11, 6), (11, 8))),
    _legacy("buff_consumable_ambush", "battlefield.standard_hazards_open", (2, 7), ((10, 9), (10, 5), (12, 7))),
    _legacy("forced_movement_hazard_bridge", "battlefield.standard_hazards_open", (4, 10), ((6, 10), (10, 7), (11, 9))),
    _legacy("line_aoe_corridor", "battlefield.open_floor_bright", (2, 7), ((8, 7), (10, 7), (12, 7), (10, 9))),
    _legacy("zone_control_web_gauntlet", "battlefield.standard_hazards_open", (3, 7), ((8, 7), (10, 5), (11, 7))),
    _legacy("support_attrition_cache", "battlefield.open_floor_bright", (5, 7), ((8, 7), (10, 5), (11, 7))),
    _legacy("high_level_spell_resource_duel", "battlefield.open_floor_bright", (3, 7), ((8, 7), (10, 5), (11, 7))),
    _legacy("sorcerer_barbarian_duel", "battlefield.open_floor_bright", (3, 7), ((11, 7),)),
    _legacy("class_party_mirror_scramble", "battlefield.open_floor_bright", (5, 7), ((8, 7), (11, 5), (11, 9))),
    _legacy("ranged_loadout_kiting_ring", "battlefield.standard_hazards_open", (3, 7), ((11, 7), (12, 5), (12, 9))),
    _legacy("concentration_control_crossroads", "battlefield.open_floor_bright", (4, 7), ((7, 7), (11, 7), (10, 5))),
    _legacy("teleport_escape_skirmish", "battlefield.standard_hazards_open", (3, 7), ((9, 8), (12, 5), (11, 7))),
    _legacy("darkness_reveal_labyrinth", "battlefield.reveal_labyrinth_dark", (2, 7), ((11, 6), (12, 9), (10, 4))),
    _legacy("guardian_zone_shrine", "battlefield.open_floor_bright", (5, 7), ((8, 7), (10, 5), (11, 7))),
    _legacy("trap_lever_killzone", "battlefield.standard_hazards_open", (3, 10), ((5, 11), (8, 11), (10, 9))),
    _legacy("condition_lock_sanctum", "battlefield.open_floor_bright", (4, 7), ((8, 7), (11, 7), (10, 5))),
    _legacy("necrotic_anti_healing_duel", "battlefield.open_floor_bright", (5, 7), ((8, 7), (10, 5), (11, 7))),
    _legacy("damage_affinity_weapon_lab", "battlefield.open_floor_bright", (6, 7), ((7, 7), (10, 5), (11, 8))),
    _legacy("resistance_weapon_counterplay", "battlefield.open_floor_bright", (6, 7), ((7, 7), (10, 5), (11, 8))),
    _legacy("field_cache_loot_race", "battlefield.field_cache_bright", (4, 7), ((9, 7), (11, 5), (12, 8))),
    _legacy("cleanse_support_triage", "battlefield.open_floor_bright", (5, 7), ((8, 7), (10, 5), (11, 7))),
    _legacy("multi_target_missile_allocation", "battlefield.open_floor_bright", (4, 7), ((8, 7), (10, 6), (10, 8))),
    _legacy("multi_projectile_no_aoe_lab", "battlefield.open_floor_bright", (4, 7), ((8, 3), (10, 7), (8, 11))),
    _legacy("reaction_counterspell_lab", "battlefield.open_floor_bright", (4, 7), ((8, 7), (10, 7), (11, 5))),
    _legacy("guardian_choke_body_block", "battlefield.standard_hazards_open", (3, 7), ((7, 7), (10, 7), (10, 5))),
    _legacy("multi_object_control_room", "battlefield.multi_object_dark", (5, 11), ((9, 11), (10, 9), (11, 12))),
    _legacy("srd_low_cr_patrol", "battlefield.open_floor_bright", (3, 7), ((10, 4), (9, 7), (11, 9), (8, 10), (12, 6))),
    _legacy("srd_undead_crypt", "battlefield.open_floor_dark", (3, 7), ((10, 5), (9, 7), (11, 9), (12, 7))),
    _legacy("srd_goblinoid_warband", "battlefield.standard_hazards_open", (2, 7), ((9, 4), (9, 7), (11, 6), (12, 9))),
    _legacy("srd_divine_cult_cell", "battlefield.open_floor_bright", (3, 7), ((8, 7), (9, 6), (11, 7), (12, 9))),
    _legacy("srd_elite_mercenary_contract", "battlefield.open_floor_bright", (3, 7), ((8, 7), (10, 5), (12, 7), (10, 9))),
)


DEPLOYMENTS: tuple[DeploymentSpec, ...] = (*NEUTRAL_DEPLOYMENTS, *LEGACY_DEPLOYMENTS)
DEPLOYMENTS_BY_ID = {spec.deployment_id: spec for spec in DEPLOYMENTS}


def get_deployment(deployment_id: str) -> DeploymentSpec:
    """Return one deployment by stable identifier."""
    try:
        return DEPLOYMENTS_BY_ID[deployment_id]
    except KeyError as exc:
        raise ValueError(f"Unknown deployment: {deployment_id}") from exc
