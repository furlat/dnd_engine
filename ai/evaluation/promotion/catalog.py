"""Structured roster edges and symmetric contexts for policy promotion."""

from __future__ import annotations

from ai.evaluation.promotion.contracts import MatchupFamily, PromotionMatchupSpec, PromotionPanel
from dnd.scenarios.evaluation.models import BattlefieldSpec, DeploymentSpec, SideConfigurationSpec


FROZEN_CORE_HERO_IDS = frozenset({
    "hero.sorcerer_l5_standard_torch",
    "hero.fighter_l5_archer_torch",
    "hero.barbarian_l5_berserker_torch",
    "hero.fighter_l5_item_gauntlet",
    "hero.fighter_l5_shield_torch",
    "hero.sorcerer_l9_standard_torch",
    "hero.fighter_l5_wounded_necrotic",
    "hero.skeleton_warrior_darkvision",
    "hero.fighter_l5_affinity_lab",
    "hero.sorcerer_l5_projectile_only",
    "hero.sorcerer_l5_counterspell",
    "hero.fighter_l5_archer_magic_missile_scroll",
    "hero.fighter_l5_shield_healing_potion",
    "hero.sorcerer_l5_hold_person_scroll",
    "hero.sorcerer_l9_greater_invisibility_potion",
})

FROZEN_CORE_MONSTER_IDS = frozenset({
    "monsters.skeleton_trio",
    "monsters.goblin_water_cell",
    "monsters.skeleton_caster_crossfire",
    "monsters.item_gauntlet_cell",
    "monsters.arcane_device_cell",
    "monsters.buff_consumable_cell",
    "monsters.forced_movement_cell",
    "monsters.line_aoe_column",
    "monsters.web_control_cell",
    "monsters.support_attrition_cell",
    "monsters.high_level_spell_cell",
    "monsters.berserker_duelist",
    "monsters.class_mirror_party",
    "monsters.ranged_kiting_cell",
    "monsters.concentration_crossroads_cell",
    "monsters.teleport_escape_cell",
    "monsters.darkness_reveal_cell",
    "monsters.guardian_shrine_cell",
    "monsters.trap_lever_cell",
    "monsters.condition_lock_cell",
    "monsters.necrotic_cell",
    "monsters.damage_affinity_weapon_cell",
    "monsters.resistance_weapon_cell",
    "monsters.field_cache_cell",
    "monsters.cleanse_support_cell",
    "monsters.missile_allocation_cell",
    "monsters.projectile_no_aoe_cell",
    "monsters.counterspell_reaction_cell",
    "monsters.guardian_choke_cell",
    "monsters.srd_low_cr_patrol",
    "monsters.srd_undead_crypt",
    "monsters.srd_goblinoid_warband",
    "monsters.srd_divine_cult_cell",
    "monsters.srd_elite_mercenaries",
})

_SIDE_A_SLOTS = ((2, 7), (2, 5), (2, 9), (2, 3), (2, 11))
_SIDE_B_SLOTS = ((12, 7), (12, 5), (12, 9), (12, 3), (12, 11))


TARGETED_POLICY_PROMOTION_MATCHUP_IDS: tuple[tuple[str, str], ...] = (
    ("hero.sorcerer_l5_standard_torch", "monsters.skeleton_trio"),
    ("hero.barbarian_l5_berserker_torch", "monsters.skeleton_trio"),
    ("hero.sorcerer_l9_standard_torch", "monsters.skeleton_trio"),
    ("hero.sorcerer_l9_standard_torch", "monsters.concentration_crossroads_cell"),
    ("hero.fighter_l5_shield_healing_potion", "monsters.skeleton_trio"),
    ("hero.fighter_l5_shield_healing_potion", "monsters.guardian_choke_cell"),
    ("hero.fighter_l5_archer_magic_missile_scroll", "monsters.skeleton_trio"),
    ("hero.fighter_l5_archer_magic_missile_scroll", "monsters.missile_allocation_cell"),
    ("hero.barbarian_l5_dual_axes", "monsters.skeleton_trio"),
    ("hero.barbarian_l5_dual_axes", "monsters.srd_brute_pair"),
    ("monsters.srd_brute_pair", "monsters.srd_dire_hunt"),
    ("monsters.srd_dire_hunt", "monsters.skeleton_trio"),
)

TARGETED_POLICY_PROMOTION_BATTLEFIELD_IDS: tuple[str, ...] = (
    "battlefield.standard_hazards_closed",
    "battlefield.open_floor_bright",
)


def build_symmetric_promotion_deployments(
    battlefields: tuple[BattlefieldSpec, ...],
) -> tuple[DeploymentSpec, ...]:
    """Create five-versus-five symmetric deployments without changing game catalogs."""
    return tuple(
        DeploymentSpec(
            deployment_id=f"promotion.symmetric.{battlefield.battlefield_id}",
            title=f"Promotion Symmetric: {battlefield.title}",
            battlefield_id=battlefield.battlefield_id,
            hero_slots=_SIDE_A_SLOTS,
            monster_slots=_SIDE_B_SLOTS,
            tags=("promotion", "symmetric", "five-versus-five"),
            portable=True,
            max_hero_members=5,
            max_monster_members=5,
            rating_eligible=True,
        )
        for battlefield in battlefields
        if battlefield.portable
    )


def build_default_promotion_matchups(
    configurations: tuple[SideConfigurationSpec, ...],
) -> tuple[PromotionMatchupSpec, ...]:
    """Build a sparse connected field covering every hero and monster roster."""
    heroes = tuple(sorted(
        (row for row in configurations if row.side_kind == "hero" and row.rating_eligible),
        key=lambda row: row.configuration_id,
    ))
    monsters = tuple(sorted(
        (row for row in configurations if row.side_kind == "monster_party" and row.rating_eligible),
        key=lambda row: row.configuration_id,
    ))
    if not heroes or not monsters:
        raise ValueError("Default promotion matchups require hero and monster configurations.")
    edges: dict[tuple[str, str], PromotionMatchupSpec] = {}
    for hero_index, hero in enumerate(heroes):
        for offset in range(3):
            opponent = monsters[(hero_index * 3 + offset) % len(monsters)]
            _add_edge(edges, hero, opponent, MatchupFamily.HERO_VS_MONSTER)
    for index, monster in enumerate(monsters):
        for offset in {1, max(1, len(monsters) // 2)}:
            opponent = monsters[(index + offset) % len(monsters)]
            _add_edge(edges, monster, opponent, MatchupFamily.MONSTER_VS_MONSTER)
    if len(heroes) > 1:
        for index, hero in enumerate(heroes):
            _add_edge(edges, hero, heroes[(index + 1) % len(heroes)], MatchupFamily.HERO_VS_HERO)
    return tuple(edges[key] for key in sorted(edges))


def _add_edge(
    edges: dict[tuple[str, str], PromotionMatchupSpec],
    side_a: SideConfigurationSpec,
    side_b: SideConfigurationSpec,
    family: MatchupFamily,
) -> None:
    """Add one canonical undirected roster edge with protected strata."""
    if side_a.configuration_id == side_b.configuration_id:
        return
    left, right = sorted((side_a.configuration_id, side_b.configuration_id))
    key = (left, right)
    if key in edges:
        return
    by_id = {side_a.configuration_id: side_a, side_b.configuration_id: side_b}
    first = by_id[left]
    second = by_id[right]
    core_ids = FROZEN_CORE_HERO_IDS | FROZEN_CORE_MONSTER_IDS
    panel = (
        PromotionPanel.FROZEN_CORE
        if first.configuration_id in core_ids and second.configuration_id in core_ids
        else PromotionPanel.EXPANDED
    )
    edges[key] = PromotionMatchupSpec(
        matchup_id=f"matchup:{left}:vs:{right}",
        side_a_configuration_id=left,
        side_b_configuration_id=right,
        family=family,
        panel=panel,
        tags=tuple(sorted({family.value, *first.tags, *second.tags})),
    )


def build_targeted_promotion_matchups(
    configurations: tuple[SideConfigurationSpec, ...],
) -> tuple[PromotionMatchupSpec, ...]:
    """Build a compact pathology-focused panel for candidate-vs-baseline Elo."""
    by_id = {row.configuration_id: row for row in configurations}
    edges: dict[tuple[str, str], PromotionMatchupSpec] = {}
    for left_id, right_id in TARGETED_POLICY_PROMOTION_MATCHUP_IDS:
        left = by_id.get(left_id)
        right = by_id.get(right_id)
        if left is None or right is None:
            raise ValueError(f"Unknown targeted promotion configuration: {left_id} vs {right_id}")
        if not left.rating_eligible or not right.rating_eligible:
            raise ValueError(f"Targeted promotion configuration is not rating eligible: {left_id} vs {right_id}")
        if left.side_kind == "hero" and right.side_kind == "hero":
            family = MatchupFamily.HERO_VS_HERO
        elif left.side_kind == "monster_party" and right.side_kind == "monster_party":
            family = MatchupFamily.MONSTER_VS_MONSTER
        elif left.configuration_id == right.configuration_id:
            family = MatchupFamily.MIRROR
        else:
            family = MatchupFamily.HERO_VS_MONSTER
        _add_edge(edges, left, right, family)
    return tuple(edges[key] for key in sorted(edges))
