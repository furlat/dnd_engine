from dnd.monsters.srd_roster import SRD_CREATURE_RECIPES_BY_ID
from dnd.scenarios.evaluation.combatant_catalog import (
    HERO_CONFIGURATIONS,
    MONSTER_PARTY_CONFIGURATIONS,
    get_combatant_configuration,
)
from dnd.scenarios.evaluation.models import (
    BarbarianActorBlueprint,
    BestiaryActorBlueprint,
    FighterActorBlueprint,
    SideConfigurationSpec,
    SorcererActorBlueprint,
    SrdMonsterActorBlueprint,
    StartingCondition,
    StartingDamage,
)


def test_side_configuration_identity_is_mechanical_and_presentation_independent() -> None:
    fighter = FighterActorBlueprint(
        actor_id="frontline",
        level=5,
        fighting_style="dueling",
        equipment_preset="sword_shield",
        asi_4=(("strength", 2),),
    )
    first = SideConfigurationSpec(
        configuration_id="heroes.alpha",
        title="Alpha Heroes",
        side_kind="hero",
        members=(fighter,),
    )
    renamed = first.model_copy(update={
        "configuration_id": "heroes.renamed",
        "title": "A Different Label",
    })

    assert first.mechanical_hash == renamed.mechanical_hash


def test_configuration_identity_changes_with_loadout_or_spell_selection() -> None:
    archer = SideConfigurationSpec(
        configuration_id="heroes.archer",
        title="Archer",
        side_kind="hero",
        members=(FighterActorBlueprint(
            actor_id="hero",
            level=5,
            fighting_style="archery",
            equipment_preset="archery",
            asi_4=(("dexterity", 2),),
        ),),
    )
    shield = SideConfigurationSpec(
        configuration_id="heroes.shield",
        title="Shield Fighter",
        side_kind="hero",
        members=(FighterActorBlueprint(
            actor_id="hero",
            level=5,
            fighting_style="dueling",
            equipment_preset="sword_shield",
            asi_4=(("strength", 2),),
        ),),
    )
    caster = SideConfigurationSpec(
        configuration_id="monsters.caster",
        title="Caster",
        side_kind="monster_party",
        members=(SorcererActorBlueprint(
            actor_id="caster",
            level=5,
            spell_names=("Fire Bolt", "Magic Missile"),
            metamagic_choices=("quickened", "twinned"),
            asi_4=(("charisma", 2),),
        ),),
    )
    caster_changed = caster.model_copy(update={
        "members": (SorcererActorBlueprint(
            actor_id="caster",
            level=5,
            spell_names=("Fire Bolt", "Scorching Ray"),
            metamagic_choices=("quickened", "twinned"),
            asi_4=(("charisma", 2),),
        ),),
    })

    assert archer.mechanical_hash != shield.mechanical_hash
    assert caster.mechanical_hash != caster_changed.mechanical_hash


def test_member_order_does_not_change_party_identity() -> None:
    warrior = BestiaryActorBlueprint(actor_id="warrior", archetype="skeleton_warrior", darkvision=True)
    archer = BestiaryActorBlueprint(actor_id="archer", archetype="skeleton_archer", darkvision=True)
    first = SideConfigurationSpec(
        configuration_id="monsters.first",
        title="Skeleton Pair",
        side_kind="monster_party",
        members=(warrior, archer),
    )
    second = SideConfigurationSpec(
        configuration_id="monsters.second",
        title="Skeleton Pair Reordered",
        side_kind="monster_party",
        members=(archer, warrior),
    )

    assert first.mechanical_hash == second.mechanical_hash


def test_configuration_contract_fields_have_descriptions() -> None:
    for model in (BestiaryActorBlueprint, FighterActorBlueprint, SorcererActorBlueprint, SideConfigurationSpec):
        assert all(field.description for field in model.model_fields.values())


def test_catalog_has_exact_audited_canonical_counts_and_unique_identity() -> None:
    assert len(HERO_CONFIGURATIONS) == 20
    assert len(MONSTER_PARTY_CONFIGURATIONS) == 38
    assert len({row.configuration_id for row in HERO_CONFIGURATIONS}) == 20
    assert len({row.configuration_id for row in MONSTER_PARTY_CONFIGURATIONS}) == 38
    assert len({row.mechanical_hash for row in HERO_CONFIGURATIONS}) == 20
    assert len({row.mechanical_hash for row in MONSTER_PARTY_CONFIGURATIONS}) == 38


def test_every_srd_monster_factory_is_represented_in_a_configuration() -> None:
    configured_monster_ids = {
        member.monster_id
        for configuration in MONSTER_PARTY_CONFIGURATIONS
        for member in configuration.members
        if isinstance(member, SrdMonsterActorBlueprint)
    }

    assert len(SRD_CREATURE_RECIPES_BY_ID) == 27
    assert configured_monster_ids == set(SRD_CREATURE_RECIPES_BY_ID)


def test_new_srd_parties_have_exact_members_and_rating_metadata() -> None:
    expected_members = {
        "monsters.srd_border_raiders": ("orc", "thug", "scout", "tribal_warrior", "tribal_warrior"),
        "monsters.srd_spy_ring": ("spy", "scout", "commoner", "commoner"),
        "monsters.srd_dire_hunt": ("dire_wolf", "tribal_warrior", "tribal_warrior"),
        "monsters.srd_brute_pair": ("ogre", "berserker"),
    }

    for configuration_id, monster_ids in expected_members.items():
        configuration = get_combatant_configuration(configuration_id)
        assert tuple(member.monster_id for member in configuration.members if isinstance(member, SrdMonsterActorBlueprint)) == monster_ids
        assert configuration.portable
        assert configuration.rating_eligible
        assert len(configuration.tags) >= 7


def test_new_hero_loadout_presets_have_distinct_mechanical_hashes() -> None:
    expected_loadouts = {
        "hero.fighter_l5_great_weapon": (FighterActorBlueprint, "great_weapon", "greatsword"),
        "hero.fighter_l5_defense": (FighterActorBlueprint, "defense", "greatsword"),
        "hero.fighter_l5_two_weapon": (FighterActorBlueprint, "two_weapon", "dual_wield"),
        "hero.barbarian_l5_dual_axes": (BarbarianActorBlueprint, None, "dual_axes"),
        "hero.barbarian_l5_sword_shield": (BarbarianActorBlueprint, None, "sword_shield"),
    }
    configurations = [get_combatant_configuration(configuration_id) for configuration_id in expected_loadouts]

    for configuration in configurations:
        blueprint_type, fighting_style, equipment_preset = expected_loadouts[configuration.configuration_id]
        member = configuration.members[0]
        assert isinstance(member, blueprint_type)
        assert member.level == 5
        assert member.equipment_preset == equipment_preset
        if isinstance(member, FighterActorBlueprint):
            assert member.fighting_style == fighting_style
        assert configuration.portable
        assert configuration.rating_eligible
        assert len(configuration.tags) >= 5

    assert len({configuration.mechanical_hash for configuration in configurations}) == len(configurations)


def test_canonical_entries_cover_all_legacy_recipe_aliases_once_per_side() -> None:
    hero_sources = [arena_id for row in HERO_CONFIGURATIONS for arena_id in row.source_arena_ids]
    monster_sources = [arena_id for row in MONSTER_PARTY_CONFIGURATIONS for arena_id in row.source_arena_ids]

    assert len(hero_sources) == 38
    assert len(set(hero_sources)) == 38
    assert len(monster_sources) == 38
    assert set(monster_sources) == set(hero_sources)
    assert get_combatant_configuration("monsters.skeleton_trio").source_arena_ids == (
        "standard_skeleton_doors",
        "skeleton_anti_aoe_split",
        "double_door_dark_hunt",
        "skeleton_mark_focus_fire",
    )
    assert get_combatant_configuration("monsters.skeleton_caster_crossfire").source_arena_ids == (
        "caster_crossfire",
        "multi_object_control_room",
    )


def test_starting_hp_and_starting_conditions_are_mechanical_identity() -> None:
    pristine = SideConfigurationSpec(
        configuration_id="monsters.pristine",
        title="Pristine",
        side_kind="monster_party",
        members=(BestiaryActorBlueprint(
            actor_id="guard",
            deployment_role="monster_1",
            archetype="skeleton_warrior",
            darkvision=True,
        ),),
    )
    wounded = pristine.model_copy(update={
        "configuration_id": "monsters.wounded",
        "members": (BestiaryActorBlueprint(
            actor_id="guard",
            deployment_role="monster_1",
            archetype="skeleton_warrior",
            darkvision=True,
            augmentations=(StartingDamage(amount=10, damage_type="Slashing"),),
        ),),
    })
    wounded_more = wounded.model_copy(update={
        "members": (BestiaryActorBlueprint(
            actor_id="guard",
            deployment_role="monster_1",
            archetype="skeleton_warrior",
            darkvision=True,
            augmentations=(StartingDamage(amount=11, damage_type="Slashing"),),
        ),),
    })
    poisoned = wounded.model_copy(update={
        "configuration_id": "monsters.poisoned",
        "members": (BestiaryActorBlueprint(
            actor_id="guard",
            deployment_role="monster_1",
            archetype="skeleton_warrior",
            darkvision=True,
            augmentations=(
                StartingDamage(amount=10, damage_type="Slashing"),
                StartingCondition(condition_name="Poisoned"),
            ),
        ),),
    })

    assert len({pristine.mechanical_hash, wounded.mechanical_hash, wounded_more.mechanical_hash, poisoned.mechanical_hash}) == 4


def test_all_current_configurations_are_portable_and_rating_eligible() -> None:
    catalog = (*HERO_CONFIGURATIONS, *MONSTER_PARTY_CONFIGURATIONS)
    assert all(row.portable and row.rating_eligible for row in catalog)
    assert all(row.exclusion_reason is None for row in catalog)

    warning_ids = {
        row.configuration_id
        for row in MONSTER_PARTY_CONFIGURATIONS
        if row.diagnostic_warnings
    }
    assert warning_ids == {
        "monsters.support_attrition_cell",
        "monsters.guardian_shrine_cell",
        "monsters.cleanse_support_cell",
        "monsters.missile_allocation_cell",
        "monsters.projectile_no_aoe_cell",
    }
