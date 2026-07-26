"""Canonical combatant configurations for composed evaluation scenarios."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from dnd.core.equipment_types import WeaponSlot
from dnd.items.consumables import (
    FIRE_WEAPON_COAT_RECIPE,
    GREATER_INVISIBILITY_POTION_RECIPE,
    HASTE_POTION_RECIPE,
    LIGHTNING_WEAPON_COAT_RECIPE,
    healing_potion_recipe,
)
from dnd.items.spell_items import (
    ACID_FLASK_RECIPE,
    FIREBALL_SCROLL_RECIPE,
    HOLD_PERSON_SCROLL_RECIPE,
    MAGIC_MISSILE_SCROLL_RECIPE,
    SPIKE_GROWTH_SCROLL_RECIPE,
    wand_of_fire_recipe,
    wand_of_magic_missiles_recipe,
)
from dnd.items.torches import TORCH_RECIPE
from dnd.items.weapons import CLUB_RECIPE, LONGBOW_RECIPE, SHORTSWORD_RECIPE
from dnd.scenarios.evaluation.models import (
    ActorAugmentation,
    AbilityName,
    BarbarianEquipmentPreset,
    BarbarianActorBlueprint,
    BestiaryActorBlueprint,
    DamageAffinity,
    EquipmentGrant,
    FighterActorBlueprint,
    FighterEquipmentPreset,
    FighterStyleName,
    ItemGrant,
    ReactionGrant,
    SideConfigurationSpec,
    SorcererActorBlueprint,
    SpellGrant,
    SrdMonsterActorBlueprint,
    StartingCondition,
    StartingDamage,
    BestiaryArchetype,
)
from dnd.scenarios.evaluation.wardrobes import (
    BERSERKER_WARDROBE,
    BESTIARY_WARDROBES,
    CASTER_WARDROBES,
    SRD_WARDROBES,
)


LEVEL_5_SORCERER_SPELLS = (
    "Fire Bolt",
    "Ray of Frost",
    "Magic Missile",
    "Burning Hands",
    "Thunderwave",
    "Scorching Ray",
    "Hold Person",
    "Shatter",
    "Invisibility",
    "Fireball",
    "Lightning Bolt",
)

LEVEL_9_SORCERER_SPELLS = (
    "Fire Bolt",
    "Ray of Frost",
    "Magic Missile",
    "Thunderwave",
    "Scorching Ray",
    "Hold Person",
    "Shatter",
    "Invisibility",
    "Fireball",
    "Lightning Bolt",
    "Hypnotic Pattern",
    "Slow",
    "Haste",
    "Banishment",
    "Greater Invisibility",
    "Cone of Cold",
    "Cloudkill",
)


def _hero(
    configuration_id: str,
    title: str,
    member: BarbarianActorBlueprint | BestiaryActorBlueprint | FighterActorBlueprint | SorcererActorBlueprint,
    source_arena_ids: tuple[str, ...],
    tags: tuple[str, ...] = (),
) -> SideConfigurationSpec:
    """Create one immutable hero-side catalog entry."""
    return SideConfigurationSpec(
        configuration_id=configuration_id,
        title=title,
        side_kind="hero",
        members=(member,),
        source_arena_ids=source_arena_ids,
        tags=tags,
    )


def _party(
    configuration_id: str,
    title: str,
    members: tuple[
        BarbarianActorBlueprint
        | BestiaryActorBlueprint
        | FighterActorBlueprint
        | SorcererActorBlueprint
        | SrdMonsterActorBlueprint,
        ...,
    ],
    source_arena_ids: tuple[str, ...],
    tags: tuple[str, ...] = (),
    rating_eligible: bool = True,
    exclusion_reason: str | None = None,
    diagnostic_warnings: tuple[str, ...] = (),
) -> SideConfigurationSpec:
    """Create one immutable monster-party catalog entry."""
    return SideConfigurationSpec(
        configuration_id=configuration_id,
        title=title,
        side_kind="monster_party",
        members=members,
        source_arena_ids=source_arena_ids,
        tags=tags,
        rating_eligible=rating_eligible,
        exclusion_reason=exclusion_reason,
        diagnostic_warnings=diagnostic_warnings,
    )


def _sorcerer(
    role: str,
    level: int,
    spell_names: tuple[str, ...],
    augmentations: tuple[ActorAugmentation, ...] = (),
) -> SorcererActorBlueprint:
    """Return the class-factory Sorcerer blueprint used by the legacy fixtures."""
    return SorcererActorBlueprint(
        actor_id=role,
        deployment_role=role,
        level=level,
        metamagic_choices=("quickened", "twinned"),
        spell_names=spell_names,
        asi_4=(("charisma", 2),),
        asi_8=(("dexterity", 2),) if level >= 8 else (),
        augmentations=augmentations,
    )


def _fighter(
    role: str,
    fighting_style: FighterStyleName,
    equipment_preset: FighterEquipmentPreset,
    ability: AbilityName,
    augmentations: tuple[ActorAugmentation, ...] = (),
) -> FighterActorBlueprint:
    """Return a level-five class-factory Fighter blueprint."""
    return FighterActorBlueprint(
        actor_id=role,
        deployment_role=role,
        level=5,
        fighting_style=fighting_style,
        equipment_preset=equipment_preset,
        asi_4=((ability, 2),),
        augmentations=augmentations,
    )


def _barbarian(
    role: str,
    equipment_preset: BarbarianEquipmentPreset = "greataxe",
    augmentations: tuple[ActorAugmentation, ...] = (),
) -> BarbarianActorBlueprint:
    """Return a level-five Berserker blueprint."""
    return BarbarianActorBlueprint(
        actor_id=role,
        deployment_role=role,
        level=5,
        primal_path="berserker",
        equipment_preset=equipment_preset,
        asi_4=(("strength", 2),),
        augmentations=(*BERSERKER_WARDROBE, *augmentations),
    )


def _bestiary(
    role: str,
    archetype: BestiaryArchetype,
    *,
    level: int = 5,
    darkvision: bool | None = None,
    augmentations: tuple[ActorAugmentation, ...] = (),
) -> BestiaryActorBlueprint:
    """Return one existing bestiary-factory blueprint."""
    return BestiaryActorBlueprint(
        actor_id=role,
        deployment_role=role,
        archetype=archetype,
        level=level,
        darkvision=darkvision,
        augmentations=(*BESTIARY_WARDROBES.get(archetype, ()), *augmentations),
    )


def _skeleton(
    role: str,
    archetype: BestiaryArchetype,
    augmentations: tuple[ActorAugmentation, ...] = (),
) -> BestiaryActorBlueprint:
    """Return a darkvision-enabled skeleton blueprint."""
    return _bestiary(role, archetype, darkvision=True, augmentations=augmentations)


def _caster(
    role: str,
    level: int = 5,
    spells: tuple[str, ...] = (),
    augmentations: tuple[ActorAugmentation, ...] = (),
    wardrobe: Literal["arcane", "dark", "divine", "necromancer"] = "arcane",
) -> BestiaryActorBlueprint:
    """Return a generic-caster blueprint with optional additive spell grants."""
    grants: tuple[ActorAugmentation, ...] = (*CASTER_WARDROBES[wardrobe], *augmentations)
    if spells:
        grants = (SpellGrant(spell_names=spells, caster_level=level), *grants)
    return _bestiary(role, "caster", level=level, augmentations=grants)


def _goblin_archer(role: str, *, nimble: bool) -> BestiaryActorBlueprint:
    """Return a goblin archer, preserving the fixture-specific Nimble Escape grant."""
    augmentations: tuple[ActorAugmentation, ...] = ()
    if nimble:
        augmentations = (ReactionGrant(reaction_id="goblin_nimble_escape"),)
    return _bestiary(role, "goblin_archer", augmentations=augmentations)


def _srd(
    role: str,
    monster_id: str,
    augmentations: tuple[ActorAugmentation, ...] = (),
) -> SrdMonsterActorBlueprint:
    """Return one typed SRD roster blueprint."""
    return SrdMonsterActorBlueprint(
        actor_id=role,
        deployment_role=role,
        monster_id=monster_id,
        augmentations=(*SRD_WARDROBES.get(monster_id, ()), *augmentations),
    )


_TORCH = ItemGrant(recipe=TORCH_RECIPE, on_grant="ignite")
_SHIELD_LOADOUT = (
    EquipmentGrant(recipe=LONGBOW_RECIPE, slot=WeaponSlot.RANGED_MAIN),
    _TORCH,
)


HERO_CONFIGURATIONS: tuple[SideConfigurationSpec, ...] = (
    _hero(
        "hero.sorcerer_l5_standard_torch",
        "Level 5 Sorcerer With Torch",
        _sorcerer("hero", 5, LEVEL_5_SORCERER_SPELLS, (_TORCH,)),
        (
            "standard_skeleton_doors",
            "skeleton_anti_aoe_split",
            "arcane_device_control",
            "line_aoe_corridor",
            "sorcerer_barbarian_duel",
            "concentration_control_crossroads",
            "darkness_reveal_labyrinth",
            "multi_target_missile_allocation",
        ),
        ("sorcerer", "level-5", "torch"),
    ),
    _hero(
        "hero.fighter_l5_archer_torch",
        "Level 5 Archer Fighter With Torch",
        _fighter("hero", "archery", "archery", "dexterity", (_TORCH,)),
        ("goblin_water_skirmish", "field_cache_loot_race", "multi_object_control_room"),
        ("fighter", "level-5", "ranged", "torch"),
    ),
    _hero(
        "hero.barbarian_l5_berserker_torch",
        "Level 5 Berserker With Torch",
        _barbarian("hero", augmentations=(_TORCH,)),
        (
            "caster_crossfire",
            "double_door_dark_hunt",
            "buff_consumable_ambush",
            "forced_movement_hazard_bridge",
            "zone_control_web_gauntlet",
            "ranged_loadout_kiting_ring",
            "teleport_escape_skirmish",
            "trap_lever_killzone",
            "condition_lock_sanctum",
            "guardian_choke_body_block",
            "srd_goblinoid_warband",
        ),
        ("barbarian", "level-5", "melee", "torch"),
    ),
    _hero(
        "hero.fighter_l5_item_gauntlet",
        "Archer Fighter Item Gauntlet",
        _fighter(
            "hero",
            "archery",
            "archery",
            "dexterity",
            (
                _TORCH,
                ItemGrant(recipe=wand_of_magic_missiles_recipe(charges=3)),
                ItemGrant(recipe=wand_of_fire_recipe(charges=4)),
                ItemGrant(recipe=FIREBALL_SCROLL_RECIPE),
                ItemGrant(recipe=MAGIC_MISSILE_SCROLL_RECIPE),
                ItemGrant(recipe=SPIKE_GROWTH_SCROLL_RECIPE),
                ItemGrant(recipe=GREATER_INVISIBILITY_POTION_RECIPE),
                ItemGrant(recipe=FIRE_WEAPON_COAT_RECIPE),
            ),
        ),
        ("item_resource_gauntlet",),
        ("fighter", "items", "diagnostic"),
    ),
    _hero(
        "hero.fighter_l5_shield_torch",
        "Level 5 Shield Fighter With Longbow And Torch",
        _fighter("hero", "dueling", "sword_shield", "strength", _SHIELD_LOADOUT),
        (
            "skeleton_mark_focus_fire",
            "support_attrition_cache",
            "class_party_mirror_scramble",
            "guardian_zone_shrine",
            "cleanse_support_triage",
        ),
        ("fighter", "level-5", "shield", "torch"),
    ),
    _hero(
        "hero.sorcerer_l9_standard_torch",
        "Level 9 Sorcerer With Torch",
        _sorcerer("hero", 9, LEVEL_9_SORCERER_SPELLS, (_TORCH,)),
        ("high_level_spell_resource_duel",),
        ("sorcerer", "level-9", "torch"),
    ),
    _hero(
        "hero.fighter_l5_wounded_necrotic",
        "Necrotically Wounded Shield Fighter",
        _fighter(
            "hero",
            "dueling",
            "sword_shield",
            "strength",
            (
                *_SHIELD_LOADOUT,
                StartingDamage(amount=8, damage_type="Necrotic"),
                ItemGrant(recipe=healing_potion_recipe(heal_amount=14)),
            ),
        ),
        ("necrotic_anti_healing_duel",),
        ("fighter", "wounded", "diagnostic"),
    ),
    _hero(
        "hero.skeleton_warrior_darkvision",
        "Skeleton Warrior Hero",
        _skeleton("hero", "skeleton_warrior"),
        ("damage_affinity_weapon_lab",),
        ("bestiary", "undead", "diagnostic"),
    ),
    _hero(
        "hero.fighter_l5_affinity_lab",
        "Resistant Shield Fighter",
        _fighter(
            "hero",
            "dueling",
            "sword_shield",
            "strength",
            (
                *_SHIELD_LOADOUT,
                DamageAffinity(status="resistance", damage_type="Piercing", label="Validation Piercing Resistance"),
                DamageAffinity(status="vulnerability", damage_type="Bludgeoning", label="Validation Bludgeoning Vulnerability"),
            ),
        ),
        ("resistance_weapon_counterplay",),
        ("fighter", "damage-affinity", "diagnostic"),
    ),
    _hero(
        "hero.sorcerer_l5_projectile_only",
        "Level 5 Projectile Sorcerer",
        _sorcerer(
            "hero",
            5,
            ("Fire Bolt", "Ray of Frost", "Magic Missile", "Scorching Ray"),
            (_TORCH,),
        ),
        ("multi_projectile_no_aoe_lab",),
        ("sorcerer", "projectile", "diagnostic"),
    ),
    _hero(
        "hero.sorcerer_l5_counterspell",
        "Level 5 Counterspell Sorcerer",
        _sorcerer(
            "hero",
            5,
            LEVEL_5_SORCERER_SPELLS,
            (_TORCH, ReactionGrant(reaction_id="counterspell")),
        ),
        ("reaction_counterspell_lab",),
        ("sorcerer", "counterspell"),
    ),
    _hero(
        "hero.fighter_l5_archer_magic_missile_scroll",
        "Archer Fighter With Magic Missile Scroll",
        _fighter(
            "hero",
            "archery",
            "archery",
            "dexterity",
            (_TORCH, ItemGrant(recipe=MAGIC_MISSILE_SCROLL_RECIPE)),
        ),
        ("srd_low_cr_patrol",),
        ("fighter", "ranged", "scroll"),
    ),
    _hero(
        "hero.fighter_l5_shield_healing_potion",
        "Shield Fighter With Healing Potion",
        _fighter(
            "hero",
            "dueling",
            "sword_shield",
            "strength",
            (
                *_SHIELD_LOADOUT,
                ItemGrant(recipe=healing_potion_recipe(heal_amount=16)),
            ),
        ),
        ("srd_undead_crypt",),
        ("fighter", "shield", "potion"),
    ),
    _hero(
        "hero.sorcerer_l5_hold_person_scroll",
        "Level 5 Sorcerer With Hold Person Scroll",
        _sorcerer(
            "hero",
            5,
            LEVEL_5_SORCERER_SPELLS,
            (_TORCH, ItemGrant(recipe=HOLD_PERSON_SCROLL_RECIPE)),
        ),
        ("srd_divine_cult_cell",),
        ("sorcerer", "scroll"),
    ),
    _hero(
        "hero.sorcerer_l9_greater_invisibility_potion",
        "Level 9 Sorcerer With Greater Invisibility Potion",
        _sorcerer(
            "hero",
            9,
            LEVEL_9_SORCERER_SPELLS,
            (_TORCH, ItemGrant(recipe=GREATER_INVISIBILITY_POTION_RECIPE)),
        ),
        ("srd_elite_mercenary_contract",),
        ("sorcerer", "level-9", "potion"),
    ),
    _hero(
        "hero.fighter_l5_great_weapon",
        "Level 5 Great Weapon Fighter",
        _fighter("hero", "great_weapon", "greatsword", "strength"),
        (),
        ("fighter", "level-5", "melee", "greatsword", "two-handed", "great-weapon-fighting"),
    ),
    _hero(
        "hero.fighter_l5_defense",
        "Level 5 Defense Fighter With Greatsword",
        _fighter("hero", "defense", "greatsword", "strength"),
        (),
        ("fighter", "level-5", "melee", "greatsword", "two-handed", "defense"),
    ),
    _hero(
        "hero.fighter_l5_two_weapon",
        "Level 5 Two-Weapon Fighter",
        _fighter("hero", "two_weapon", "dual_wield", "strength"),
        (),
        ("fighter", "level-5", "melee", "dual-wield", "two-weapon-fighting"),
    ),
    _hero(
        "hero.barbarian_l5_dual_axes",
        "Level 5 Berserker With Dual Axes",
        _barbarian("hero", equipment_preset="dual_axes"),
        (),
        ("barbarian", "berserker", "level-5", "melee", "dual-wield", "axes"),
    ),
    _hero(
        "hero.barbarian_l5_sword_shield",
        "Level 5 Berserker With Sword And Shield",
        _barbarian("hero", equipment_preset="sword_shield"),
        (),
        ("barbarian", "berserker", "level-5", "melee", "sword", "shield", "defense"),
    ),
)


_CRUSHER_AUGMENTATIONS: tuple[ActorAugmentation, ...] = (
    EquipmentGrant(
        recipe=SHORTSWORD_RECIPE,
        slot=WeaponSlot.MELEE_MAIN,
        replace=True,
    ),
    EquipmentGrant(
        recipe=CLUB_RECIPE,
        slot=WeaponSlot.MELEE_OFF,
        replace=True,
    ),
)


MONSTER_PARTY_CONFIGURATIONS: tuple[SideConfigurationSpec, ...] = (
    _party(
        "monsters.skeleton_trio",
        "Skeleton Warrior, Archer, And Warlock",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _skeleton("monster_2", "skeleton_archer"),
            _skeleton("monster_3", "skeleton_warlock"),
        ),
        ("standard_skeleton_doors", "skeleton_anti_aoe_split", "double_door_dark_hunt", "skeleton_mark_focus_fire"),
        ("skeletons", "frontline", "ranged", "caster"),
    ),
    _party(
        "monsters.goblin_water_cell",
        "Goblin Water Skirmish Cell",
        (
            _bestiary("monster_1", "goblin"),
            _goblin_archer("monster_2", nimble=True),
            _caster("monster_3"),
        ),
        ("goblin_water_skirmish",),
    ),
    _party(
        "monsters.skeleton_caster_crossfire",
        "Skeleton Crossfire With Generic Caster",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _skeleton("monster_2", "skeleton_archer"),
            _caster("monster_3"),
        ),
        ("caster_crossfire", "multi_object_control_room"),
    ),
    _party(
        "monsters.item_gauntlet_cell",
        "Item Gauntlet Opposition",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _goblin_archer("monster_2", nimble=True),
            _caster("monster_3"),
        ),
        ("item_resource_gauntlet",),
    ),
    _party(
        "monsters.arcane_device_cell",
        "Arcane Device Opposition",
        (
            _bestiary("monster_1", "goblin"),
            _skeleton("monster_2", "skeleton_archer"),
            _caster("monster_3"),
        ),
        ("arcane_device_control",),
    ),
    _party(
        "monsters.buff_consumable_cell",
        "Buff Consumable Ambush Cell",
        (
            _skeleton(
                "monster_1",
                "skeleton_warrior",
                (ItemGrant(recipe=GREATER_INVISIBILITY_POTION_RECIPE),),
            ),
            _bestiary(
                "monster_2",
                "goblin_archer",
                augmentations=(
                    ReactionGrant(reaction_id="goblin_nimble_escape"),
                    ItemGrant(recipe=HASTE_POTION_RECIPE),
                ),
            ),
            _caster(
                "monster_3",
                augmentations=(ItemGrant(recipe=HOLD_PERSON_SCROLL_RECIPE),),
            ),
        ),
        ("buff_consumable_ambush",),
    ),
    _party(
        "monsters.forced_movement_cell",
        "Forced Movement Bridge Cell",
        (
            _skeleton("monster_1", "skeleton_warlock"),
            _caster("monster_2"),
            _skeleton("monster_3", "skeleton_archer"),
        ),
        ("forced_movement_hazard_bridge",),
    ),
    _party(
        "monsters.line_aoe_column",
        "Line AoE Corridor Column",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _skeleton("monster_2", "skeleton_archer"),
            _caster("monster_3"),
            _bestiary("monster_4", "goblin"),
        ),
        ("line_aoe_corridor",),
    ),
    _party(
        "monsters.web_control_cell",
        "Web Control Cell",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _goblin_archer("monster_2", nimble=True),
            _caster("monster_3", spells=("Web", "Grease", "Spike Growth", "Fog Cloud")),
        ),
        ("zone_control_web_gauntlet",),
    ),
    _party(
        "monsters.support_attrition_cell",
        "Support Attrition Cell",
        (
            _skeleton("monster_1", "skeleton_warrior", (StartingDamage(amount=10, damage_type="Slashing", source_role="hero"),)),
            _skeleton("monster_2", "skeleton_archer"),
            _caster(
                "monster_3",
                spells=("Bless", "Bane", "Aid", "Healing Word", "Shield of Faith", "Sanctuary"),
                augmentations=(
                    ItemGrant(recipe=healing_potion_recipe(heal_amount=14)),
                    ItemGrant(recipe=LIGHTNING_WEAPON_COAT_RECIPE),
                ),
                wardrobe="divine",
            ),
        ),
        ("support_attrition_cache",),
        ("support", "starting-damage", "diagnostic"),
        diagnostic_warnings=("Includes a deliberately wounded frontline member in rated identity.",),
    ),
    _party(
        "monsters.high_level_spell_cell",
        "High-Level Spell Cell",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _goblin_archer("monster_2", nimble=False),
            _caster("monster_3", level=9, spells=("Cone of Cold", "Cloudkill", "Hypnotic Pattern", "Slow", "Banishment", "Dimension Door")),
        ),
        ("high_level_spell_resource_duel",),
    ),
    _party(
        "monsters.berserker_duelist",
        "Berserker Duelist",
        (_barbarian("monster_1"),),
        ("sorcerer_barbarian_duel",),
    ),
    _party(
        "monsters.class_mirror_party",
        "Berserker, Archer, And Sorcerer Party",
        (
            _barbarian("monster_1", equipment_preset="dual_axes"),
            _fighter("monster_2", "archery", "archery", "dexterity"),
            _sorcerer(
                "monster_3",
                5,
                ("Fire Bolt", "Ray of Frost", "Magic Missile", "Scorching Ray", "Hold Person", "Haste", "Slow", "Fireball", "Lightning Bolt"),
            ),
        ),
        ("class_party_mirror_scramble",),
    ),
    _party(
        "monsters.ranged_kiting_cell",
        "Ranged Kiting Cell",
        (
            _fighter("monster_1", "archery", "archery", "dexterity"),
            _goblin_archer("monster_2", nimble=True),
            _skeleton("monster_3", "skeleton_warlock"),
        ),
        ("ranged_loadout_kiting_ring",),
    ),
    _party(
        "monsters.concentration_crossroads_cell",
        "Concentration Crossroads Cell",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _sorcerer("monster_2", 5, ("Fire Bolt", "Ray of Frost", "Magic Missile", "Hold Person", "Web", "Hypnotic Pattern", "Slow", "Fireball")),
            _caster(
                "monster_3",
                spells=("Bless", "Bane", "Aid", "Healing Word", "Shield of Faith", "Sanctuary"),
                wardrobe="divine",
            ),
        ),
        ("concentration_control_crossroads",),
    ),
    _party(
        "monsters.teleport_escape_cell",
        "Teleport Escape Cell",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _goblin_archer("monster_2", nimble=True),
            _caster("monster_3", level=7, spells=("Misty Step", "Dimension Door", "Blur", "Mirror Image", "Ray of Frost")),
        ),
        ("teleport_escape_skirmish",),
    ),
    _party(
        "monsters.darkness_reveal_cell",
        "Darkness And Reveal Cell",
        (
            _caster(
                "monster_1",
                level=7,
                spells=("Darkness", "Fog Cloud", "Invisibility", "Greater Invisibility", "Silence"),
                wardrobe="dark",
            ),
            _caster(
                "monster_2",
                level=11,
                spells=("See Invisibility", "Daylight", "Darkvision", "Light", "True Seeing"),
                wardrobe="divine",
            ),
            _goblin_archer("monster_3", nimble=True),
        ),
        ("darkness_reveal_labyrinth",),
    ),
    _party(
        "monsters.guardian_shrine_cell",
        "Guardian Shrine Cell",
        (
            _skeleton("monster_1", "skeleton_warrior", (StartingDamage(amount=12, damage_type="Bludgeoning", source_role="hero"),)),
            _skeleton("monster_2", "skeleton_archer"),
            _caster(
                "monster_3",
                level=9,
                spells=("Spirit Guardians", "Guardian of Faith", "Beacon of Hope", "Mass Healing Word", "Flame Strike", "Sanctuary"),
                wardrobe="divine",
            ),
        ),
        ("guardian_zone_shrine",),
        ("guardian", "starting-damage", "diagnostic"),
        diagnostic_warnings=("Includes a deliberately wounded frontline member in rated identity.",),
    ),
    _party(
        "monsters.trap_lever_cell",
        "Trap Lever Cell",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _skeleton("monster_2", "skeleton_warlock"),
            _goblin_archer("monster_3", nimble=True),
        ),
        ("trap_lever_killzone",),
    ),
    _party(
        "monsters.condition_lock_cell",
        "Condition Lock Cell",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _sorcerer("monster_2", 7, ("Fire Bolt", "Ray of Frost", "Command", "Hold Person", "Fear", "Hypnotic Pattern", "Slow", "Banishment")),
            _caster(
                "monster_3",
                spells=("Bless", "Bane", "Guiding Bolt", "Shield of Faith", "Sanctuary"),
                wardrobe="divine",
            ),
        ),
        ("condition_lock_sanctum",),
    ),
    _party(
        "monsters.necrotic_cell",
        "Necrotic Anti-Healing Cell",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _skeleton("monster_2", "skeleton_archer"),
            _caster(
                "monster_3",
                level=13,
                spells=("Chill Touch", "Blindness/Deafness", "Bestow Curse", "Blight", "Harm", "Finger of Death"),
                wardrobe="necromancer",
            ),
        ),
        ("necrotic_anti_healing_duel",),
    ),
    _party(
        "monsters.damage_affinity_weapon_cell",
        "Damage Affinity Weapon Cell",
        (
            _fighter("monster_1", "two_weapon", "dual_wield", "strength", _CRUSHER_AUGMENTATIONS),
            _skeleton("monster_2", "skeleton_archer"),
            _caster("monster_3"),
        ),
        ("damage_affinity_weapon_lab",),
    ),
    _party(
        "monsters.resistance_weapon_cell",
        "Resistance Weapon Counterplay Cell",
        (
            _fighter("monster_1", "two_weapon", "dual_wield", "strength", _CRUSHER_AUGMENTATIONS),
            _goblin_archer("monster_2", nimble=False),
            _caster("monster_3"),
        ),
        ("resistance_weapon_counterplay",),
    ),
    _party(
        "monsters.field_cache_cell",
        "Field Cache Opposition",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _goblin_archer("monster_2", nimble=False),
            _caster("monster_3"),
        ),
        ("field_cache_loot_race",),
    ),
    _party(
        "monsters.cleanse_support_cell",
        "Cleanse Support Triage Cell",
        (
            _skeleton(
                "monster_1",
                "skeleton_warrior",
                (
                    StartingDamage(amount=10, damage_type="Slashing", source_role="hero"),
                    StartingCondition(condition_name="Poisoned", source_role="hero"),
                ),
            ),
            _skeleton("monster_2", "skeleton_archer", (StartingCondition(condition_name="Blinded", source_role="hero"),)),
            _caster(
                "monster_3",
                level=9,
                spells=("Lesser Restoration", "Greater Restoration", "Cure Wounds", "Healing Word", "Mass Healing Word", "Bless", "Aid"),
                wardrobe="divine",
            ),
        ),
        ("cleanse_support_triage",),
        ("support", "starting-damage", "starting-conditions", "diagnostic"),
        diagnostic_warnings=("Includes deliberate wounds and conditions in rated identity.",),
    ),
    _party(
        "monsters.missile_allocation_cell",
        "Multi-Target Missile Allocation Cell",
        (
            _skeleton("monster_1", "skeleton_warrior", (StartingDamage(amount=15, damage_type="Force", source_role="hero"),)),
            _skeleton("monster_2", "skeleton_archer", (StartingDamage(amount=10, damage_type="Force", source_role="hero"),)),
            _bestiary("monster_3", "goblin", augmentations=(StartingDamage(amount=4, damage_type="Force", source_role="hero"),)),
        ),
        ("multi_target_missile_allocation",),
        ("projectile-allocation", "starting-damage", "diagnostic"),
        diagnostic_warnings=("Includes projectile-allocation wounds in rated identity.",),
    ),
    _party(
        "monsters.projectile_no_aoe_cell",
        "Projectile-Only Allocation Cell",
        (
            _skeleton("monster_1", "skeleton_warrior", (StartingDamage(amount=28, damage_type="Force", source_role="hero"),)),
            _skeleton("monster_2", "skeleton_archer", (StartingDamage(amount=22, damage_type="Force", source_role="hero"),)),
            _bestiary("monster_3", "goblin", augmentations=(StartingDamage(amount=7, damage_type="Force", source_role="hero"),)),
        ),
        ("multi_projectile_no_aoe_lab",),
        ("projectile-allocation", "starting-damage", "diagnostic"),
        diagnostic_warnings=("Includes projectile-allocation wounds in rated identity.",),
    ),
    _party(
        "monsters.counterspell_reaction_cell",
        "Counterspell And Shield Reaction Cell",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _caster(
                "monster_2",
                level=7,
                spells=("Magic Missile", "Fireball", "Lightning Bolt", "Greater Invisibility"),
                augmentations=(ReactionGrant(reaction_id="counterspell"),),
            ),
            _caster(
                "monster_3",
                spells=("Magic Missile", "Scorching Ray", "Mirror Image", "Blur"),
                augmentations=(ReactionGrant(reaction_id="shield"),),
            ),
        ),
        ("reaction_counterspell_lab",),
    ),
    _party(
        "monsters.guardian_choke_cell",
        "Guardian Choke Cell",
        (
            _skeleton("monster_1", "skeleton_warrior"),
            _caster(
                "monster_2",
                level=9,
                spells=("Guardian of Faith", "Spirit Guardians", "Sanctuary", "Healing Word", "Flame Strike"),
                wardrobe="divine",
            ),
            _skeleton("monster_3", "skeleton_archer"),
        ),
        ("guardian_choke_body_block",),
    ),
    _party(
        "monsters.srd_low_cr_patrol",
        "SRD Low-CR Patrol",
        (
            _srd("monster_1", "bandit"),
            _srd("monster_2", "guard"),
            _srd("monster_3", "kobold"),
            _srd("monster_4", "wolf"),
            _srd("monster_5", "acolyte"),
        ),
        ("srd_low_cr_patrol",),
    ),
    _party(
        "monsters.srd_undead_crypt",
        "SRD Undead Crypt",
        (
            _srd("monster_1", "zombie"),
            _srd("monster_2", "ghoul"),
            _skeleton("monster_3", "skeleton_archer"),
            _srd("monster_4", "ogre_zombie"),
        ),
        ("srd_undead_crypt",),
    ),
    _party(
        "monsters.srd_goblinoid_warband",
        "SRD Goblinoid Warband",
        (
            _srd(
                "monster_1",
                "kobold",
                (ItemGrant(recipe=ACID_FLASK_RECIPE),),
            ),
            _srd("monster_2", "hobgoblin"),
            _srd("monster_3", "bugbear"),
            _srd("monster_4", "gnoll"),
        ),
        ("srd_goblinoid_warband",),
    ),
    _party(
        "monsters.srd_divine_cult_cell",
        "SRD Divine Cult Cell",
        (
            _srd("monster_1", "cultist"),
            _srd("monster_2", "guard"),
            _srd(
                "monster_3",
                "cult_fanatic",
                (ItemGrant(recipe=HASTE_POTION_RECIPE),),
            ),
            _srd(
                "monster_4",
                "priest",
                (ItemGrant(recipe=healing_potion_recipe(heal_amount=18)),),
            ),
        ),
        ("srd_divine_cult_cell",),
    ),
    _party(
        "monsters.srd_elite_mercenaries",
        "SRD Elite Mercenaries",
        (
            _srd("monster_1", "knight"),
            _srd(
                "monster_2",
                "veteran",
                (ItemGrant(recipe=FIRE_WEAPON_COAT_RECIPE),),
            ),
            _srd("monster_3", "mage"),
            _srd("monster_4", "bandit_captain"),
        ),
        ("srd_elite_mercenary_contract",),
    ),
    _party(
        "monsters.srd_border_raiders",
        "SRD Border Raiders",
        (
            _srd("monster_1", "orc"),
            _srd("monster_2", "thug"),
            _srd("monster_3", "scout"),
            _srd("monster_4", "tribal_warrior"),
            _srd("monster_5", "tribal_warrior"),
        ),
        (),
        ("srd", "humanoid", "mixed-party", "melee", "ranged", "aggressive", "pack-tactics", "multiattack"),
    ),
    _party(
        "monsters.srd_spy_ring",
        "SRD Spy Ring",
        (
            _srd("monster_1", "spy"),
            _srd("monster_2", "scout"),
            _srd("monster_3", "commoner"),
            _srd("monster_4", "commoner"),
        ),
        (),
        ("srd", "humanoid", "mixed-party", "skirmisher", "ranged", "sneak-attack", "cunning-action", "multiattack"),
    ),
    _party(
        "monsters.srd_dire_hunt",
        "SRD Dire Hunt",
        (
            _srd("monster_1", "dire_wolf"),
            _srd("monster_2", "tribal_warrior"),
            _srd("monster_3", "tribal_warrior"),
        ),
        (),
        ("srd", "beast", "humanoid", "mixed-party", "melee", "fast", "pack-tactics", "prone-rider"),
    ),
    _party(
        "monsters.srd_brute_pair",
        "SRD Brute Pair",
        (
            _srd("monster_1", "ogre"),
            _srd("monster_2", "berserker"),
        ),
        (),
        ("srd", "giant", "humanoid", "brute", "melee", "large", "reckless", "high-hit-points"),
    ),
)


HERO_CONFIGURATIONS_BY_ID = {spec.configuration_id: spec for spec in HERO_CONFIGURATIONS}
MONSTER_PARTY_CONFIGURATIONS_BY_ID = {
    spec.configuration_id: spec for spec in MONSTER_PARTY_CONFIGURATIONS
}
COMBATANT_CONFIGURATIONS_BY_ID = {
    **HERO_CONFIGURATIONS_BY_ID,
    **MONSTER_PARTY_CONFIGURATIONS_BY_ID,
}


def get_combatant_configuration(configuration_id: str) -> SideConfigurationSpec:
    """Return one canonical side configuration by stable identifier."""
    try:
        return COMBATANT_CONFIGURATIONS_BY_ID[configuration_id]
    except KeyError as exc:
        raise ValueError(f"Unknown combatant configuration: {configuration_id}") from exc


def list_combatant_configurations() -> tuple[SideConfigurationSpec, ...]:
    """Return all hero then monster-party catalog entries in deterministic order."""
    return (*HERO_CONFIGURATIONS, *MONSTER_PARTY_CONFIGURATIONS)


def configuration_aliases() -> dict[str, tuple[str, ...]]:
    """Group configuration IDs that share complete mechanical content."""
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for spec in list_combatant_configurations():
        grouped[spec.mechanical_hash].append(spec.configuration_id)
    return {
        content_hash: tuple(configuration_ids)
        for content_hash, configuration_ids in sorted(grouped.items())
        if len(configuration_ids) > 1
    }
