"""Exact post-hard-cut gates for direct item recovery."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from collections import defaultdict
from uuid import uuid4

import pytest

from dnd.content.items.authored_item_builders import (
    DIRECT_ITEM_BUILDERS,
    build_authored_item,
)
from dnd.spells.conjuration import build_guardian_of_faith_object
from tests.architecture import test_content_recovery_cr0_evidence as cr0


_PUBLIC_ITEM_ID_HASH = (
    "04966a28ddf9fae4b413f0d101b61a262e26f76395475d54a4029874b583436d"
)
_ITEM_OVERLAY_ID_HASH = (
    "b28bdc07d4683d1ccd9dce416234daa241c989c8ba59551e8235cb290b6bfb3d"
)
_PRIVATE_GUARDIAN_ID = "environment.spell_object.guardian_of_faith"
_DIRECT_SPECIAL_IDS = frozenset({
    "weapon.arcane_staff",
    "weapon.assassin_dagger",
    "apparel.spellblade_crown",
    "armor.padded",
    "armor.scale_mail",
    "armor.half_plate",
    "armor.ring_mail",
    "armor.chain_mail",
    "armor.splint",
    "armor.plate",
    "consumable.healing_potion",
    "consumable.potion_haste",
    "consumable.potion_greater_invisibility",
    "consumable.weapon_coat.fire",
    "consumable.weapon_coat.lightning",
    "consumable.weapon_coat.concentration_fire",
    "consumable.weapon_coat.timed_fire",
    "consumable.acid_flask",
    "spell_item.scroll_fireball",
    "spell_item.scroll_magic_missile",
    "spell_item.scroll_hold_person",
    "spell_item.scroll_mage_armor",
    "spell_item.scroll_spike_growth",
    "spell_item.scroll_invisibility",
    "spell_item.scroll_fire_bolt",
    "spell_item.wand_magic_missiles",
    "spell_item.wand_fire",
    "equipment.portable_torch",
    "environment.directional_door",
    "environment.campfire",
    "environment.arcane_device",
    "environment.arcane_machine_gun",
    "environment.wall_torch",
    "environment.trap_lever",
    "environment.storage_chest",
    "environment.fireball_cannon",
    "environment.spell_object.heroes_feast",
    "gear.field_kit",
    "environment.blocker.oil_barrel",
})
_ITEM_EXCLUSIVE_OVERLAY_PATHS = frozenset({
    "dnd/extensions/field_focus.py",
    "dnd/items/acolyte_gear.py",
    "dnd/items/armors.py",
    "dnd/items/consumables.py",
    "dnd/items/environment.py",
    "dnd/items/environment_content.py",
    "dnd/items/environment_interactables.py",
    "dnd/items/spell_items.py",
    "dnd/items/torches.py",
    "dnd/items/weapons.py",
    "dnd/monsters/bestiary_items.py",
    "dnd/monsters/circus_fighter_items.py",
    "dnd/monsters/srd_roster_items.py",
})
_GUARDIAN_OVERLAY_IDS = frozenset({
    (
        "definition_presentation::content.srd_5_1_cc:"
        "environment_object:environment.spell_object.guardian_of_faith@1"
    ),
    (
        "definition_presentation::content.srd_5_1_cc:"
        "environment_object:environment.spell_object.heroes_feast@1"
    ),
    (
        "definition_presentation::content.srd_5_1_cc:"
        "spell:spell.guardian_of_faith@1"
    ),
    "spatial_effect.spell.guardian_of_faith",
})
_REMOVED_IMPORTERS = frozenset({
    ("dnd/blocks/base_item.py", "uses_ContentRef"),
    ("dnd/blocks/creature_proficiencies.py", "uses_ContentRef"),
    ("dnd/content_system/creature_possessions.py", "imports_dnd_content_system"),
    ("dnd/content_system/item_bindings.py", "imports_dnd_core_content"),
    ("dnd/content_system/item_materialization.py", "imports_dnd_content_system"),
    ("dnd/content_system/item_materialization.py", "imports_dnd_core_content"),
    (
        "dnd/content_system/item_runtime_materialization.py",
        "imports_dnd_content_system",
    ),
    (
        "dnd/content_system/item_runtime_materialization.py",
        "imports_dnd_core_content",
    ),
    ("dnd/items/acolyte_gear.py", "imports_dnd_core_content"),
    ("dnd/items/apparel_presets.py", "imports_dnd_core_content"),
    ("dnd/items/armors.py", "imports_dnd_core_content"),
    ("dnd/items/authored_presentations.py", "imports_dnd_core_content"),
    ("dnd/items/authored_variant_presets.py", "imports_dnd_core_content"),
    ("dnd/items/environment_content.py", "imports_dnd_content_system"),
    ("dnd/items/environment_content.py", "imports_dnd_core_content"),
    ("dnd/items/environment_content.py", "uses_ContentRef"),
    ("dnd/items/weapons.py", "imports_dnd_core_content"),
    ("dnd/maps/arena_layout.py", "imports_dnd_content_system"),
    ("dnd/monsters/bestiary.py", "imports_dnd_content_system"),
    ("dnd/monsters/bestiary_items.py", "imports_dnd_core_content"),
    ("dnd/monsters/circus_fighter.py", "imports_dnd_content_system"),
    ("dnd/monsters/circus_fighter_items.py", "imports_dnd_core_content"),
    ("dnd/monsters/srd_roster_items.py", "imports_dnd_core_content"),
    ("dnd/scenarios/battlefield_catalog.py", "imports_dnd_content_system"),
    ("dnd/spells/conjuration.py", "imports_dnd_content_system"),
})
_FIXED_ACTIVE_VISUALS = {
    "apparel.spellblade_crown": ("Crown", None),
    "apparel.armored_boots": ("Armored Boots", None),
    "apparel.bracers": ("Bracers", None),
    "apparel.chain_coif": ("Chain Coif", None),
    "apparel.cloth_hood": ("Cloth Hood", None),
    "apparel.cloth_shoes": ("Cloth Shoes", None),
    "apparel.common_clothes": ("Common Clothes", None),
    "apparel.costume": ("Costume", None),
    "apparel.fine_clothes": ("Fine Clothes", None),
    "apparel.gauntlets": ("Gauntlets", None),
    "apparel.great_helm": ("Great Helm", None),
    "apparel.horned_helmet": ("Horned Helmet", None),
    "apparel.leather_boots": ("Leather Boots", None),
    "apparel.leather_gloves": ("Leather Gloves", None),
    "apparel.leather_hood": ("Leather Hood", None),
    "apparel.leather_shoes": ("Leather Shoes", None),
    "apparel.monster_hands": ("Monster Hands", None),
    "apparel.monster_helm": ("Monster Helm", None),
    "apparel.robes": ("Robes", None),
    "apparel.sandals": ("Sandals", None),
    "apparel.travelers_clothes": ("Traveler's Clothes", None),
    "consumable.acid_flask": ("Acid Flask", "acid_flask"),
    "spell_item.scroll_fire_bolt": ("Scroll of Fire Bolt", "scroll_fire_bolt_cl5"),
    "spell_item.scroll_fireball": ("Scroll of Fireball", "scroll_fireball_l3"),
    "spell_item.scroll_hold_person": (
        "Scroll of Hold Person",
        "scroll_hold_person_l2",
    ),
    "spell_item.scroll_invisibility": (
        "Scroll of Invisibility",
        "scroll_invisibility_l2",
    ),
    "spell_item.scroll_mage_armor": (
        "Scroll of Mage Armor",
        "scroll_mage_armor_l1",
    ),
    "spell_item.scroll_magic_missile": (
        "Scroll of Magic Missile",
        "scroll_magic_missile_l1",
    ),
    "spell_item.scroll_spike_growth": (
        "Scroll of Spike Growth",
        "scroll_spike_growth_l2",
    ),
    "spell_item.wand_fire": ("Wand of Fire", "fire"),
    "spell_item.wand_magic_missiles": (
        "Wand of Magic Missiles",
        "magic_missiles",
    ),
    "weapon.circus.flaming_scimitar": ("Scimitar", "30000017"),
    "weapon.arcane_staff": ("Quarterstaff", "1000000f"),
    "weapon.assassin_dagger": ("Dagger", "10000004"),
    "weapon.creature.bandit_captain_thrown_dagger": ("Dagger", None),
    "weapon.creature.bugbear_morningstar": ("Morningstar", None),
    "weapon.creature.kobold_sling": ("Sling", None),
    "weapon.creature.ogre_greatclub": ("Club", None),
    "weapon.creature.ogre_thrown_javelin": ("Javelin", None),
    "weapon.creature.ogre_zombie_morningstar": ("Morningstar", None),
    "weapon.creature.spy_hand_crossbow": ("Light Crossbow", None),
    "weapon.creature.thrown_javelin": ("Javelin", None),
}

_AFFECTED_MODULES = (
    "tests/architecture/test_action_discovery_requirements.py",
    "tests/architecture/test_content_recovery_cr0_evidence.py",
    "tests/architecture/test_no_legacy_character_factory_dependencies.py",
    "tests/architecture/test_spell_catalog_composition.py",
    "tests/engine/test_action_cost_atomicity.py",
    "tests/engine/test_action_discovery.py",
    "tests/engine/test_cold_presentation_facts.py",
    "tests/engine/test_combat_actions.py",
    "tests/engine/test_condition_lifecycle.py",
    "tests/engine/test_condition_transform_ownership.py",
    "tests/engine/test_content_recovery_behavior_semantics.py",
    "tests/engine/test_content_recovery_item_semantics.py",
    "tests/engine/test_dice_event_semantics.py",
    "tests/engine/test_entity_composition.py",
    "tests/engine/test_equipment_domain_ownership.py",
    "tests/engine/test_equipment_replication_facts.py",
    "tests/engine/test_event_lifecycle.py",
    "tests/engine/test_items_inventory_equipment.py",
    "tests/engine/test_manual_14_core_combat_flow.py",
    "tests/engine/test_monster_presets.py",
    "tests/engine/test_runtime_identity_registries.py",
    "tests/engine/test_runtime_reset.py",
    "tests/engine/test_spatial_conditions.py",
    "tests/engine/test_spell_families.py",
    "tests/engine/test_world_entity_initialization.py",
    "tests/engine/test_world_geometry_contract.py",
    "tests/manual/test_09_action_discovery_and_costs.py",
    "tests/manual/test_11_equipment_inventory_and_items.py",
    "tests/manual/test_125_haste_restricted_action.py",
    "tests/manual/test_126_slow_legacy_contract.py",
    "tests/manual/test_131_advanced_item_world_legacy_contract.py",
    "tests/manual/test_131_inventory_use_actions_legacy_contract.py",
    "tests/manual/test_132_barbarian_unarmored_defense.py",
    "tests/manual/test_133_new_spells_batch4_legacy_contract.py",
    "tests/manual/test_134_cleric_batch1_legacy_contract.py",
    "tests/manual/test_134_stackable_usable_item_legacy_contract.py",
    "tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py",
    "tests/manual/test_135_stealth_lighting_legacy_contract.py",
    "tests/manual/test_142_item_equip_hooks_legacy_contract.py",
    "tests/manual/test_144_handler_toggle_legacy_contract.py",
    "tests/manual/test_145_haste_legacy_manifest.py",
    "tests/manual/test_151_native_ai_execution.py",
    "tests/manual/test_154_content_system_contracts.py",
    "tests/manual/test_169_neurodragon_weapon_content_factories.py",
    "tests/manual/test_170_neurodragon_consumable_content_factories.py",
    "tests/manual/test_172_behavior_runtime_binding.py",
    "tests/manual/test_178_remaining_possession_item_roots.py",
    "tests/manual/test_180_srd_creature_possession_bindings.py",
    "tests/manual/test_183_content_icon_bindings.py",
    "tests/manual/test_20_content_extension_basics.py",
    "tests/manual/test_42_action_semantics.py",
    "tests/manual/test_45_policy_routines.py",
    "tests/manual/test_71_authored_roster_catalog.py",
    "tests/manual/test_84_generic_roster_duels.py",
    "tests/manual/test_legacy_reactive_reaction_coverage.py",
    "tests/manual/test_neurodragon_spell_item_content_factories.py",
    "tests/manual/test_premade_character_content.py",
    "tests/manual/test_protection_reaction_legacy_contract.py",
    "tests/manual/test_remaining_creature_content_factories.py",
    "tests/manual/test_remaining_spell_legacy_contract.py",
    "tests/manual/test_srd_creature_content_factories.py",
    "tests/progression/test_barbarian_berserker_materialization.py",
    "tests/progression/test_barbarian_character_grant_appliers.py",
    "tests/progression/test_content_recovery_character_semantics.py",
    "tests/progression/test_dwarf_acolyte_authored_content.py",
    "tests/progression/test_fighter_champion_materialization.py",
    "tests/progression/test_fighter_character_grant_appliers.py",
    "tests/progression/test_half_orc_origin_runtime.py",
    "tests/progression/test_halfling_origin_runtime.py",
    "tests/progression/test_origin_feature_definitions.py",
    "tests/progression/test_origin_innate_spellcasting.py",
    "tests/progression/test_origin_integration_matrix.py",
    "tests/progression/test_origin_structural_feature_applier.py",
    "tests/progression/test_saving_throw_context.py",
    "tests/progression/test_schema2_character_materialization.py",
    "tests/progression/test_sorcerer_character_grant_appliers.py",
    "tests/progression/test_sorcerer_class_materialization.py",
    "tests/progression/test_sorcerer_progression_definitions.py",
    "tests/progression/test_sorcerer_spell_source_materialization.py",
    "tests/progression/test_spell_damage_affinity_contributions.py",
)
_ADDITIONAL_ANCHORS = frozenset({
    (
        "tests/manual/test_134_cleric_batch1_legacy_contract.py::"
        "test_guardian_placement_ward_and_damage_budget"
    ),
    (
        "tests/manual/test_134_stackable_usable_item_legacy_contract.py::"
        "test_nonusable_and_out_of_range_objects_do_not_surface_use_rows"
    ),
    (
        "tests/manual/test_134_stackable_usable_item_legacy_contract.py::"
        "test_override_and_default_door_actions_toggle_spatial_state"
    ),
    (
        "tests/manual/test_42_action_semantics.py::"
        "test_guardian_of_faith_declares_hostile_only_persistent_effect_scope"
    ),
    (
        "tests/manual/test_legacy_reactive_reaction_coverage.py::"
        "test_closed_door_invalidates_prepared_intercept_path_at_trigger_time"
    ),
    (
        "tests/manual/test_legacy_reactive_reaction_coverage.py::"
        "test_open_door_is_authoritative_when_dodge_roll_triggers"
    ),
})
_EXCLUDED_CURRENT_NODES = frozenset({
    (
        "tests/architecture/test_spell_catalog_composition.py::"
        "test_content_bootstrap_and_composed_spell_catalog_cold_start"
    ),
    (
        "tests/engine/test_runtime_reset.py::"
        "test_reset_engine_runtime_clears_active_behavior_provider_fact"
    ),
    (
        "tests/engine/test_runtime_reset.py::"
        "test_reset_engine_runtime_invalidates_nested_behavior_provider_scopes"
    ),
})
_RETIRED_CR0_NODES = frozenset({
    (
        "tests/architecture/test_content_recovery_cr0_evidence.py::"
        "test_binding_reconciliation_covers_every_authored_row"
    ),
    (
        "tests/architecture/test_content_recovery_cr0_evidence.py::"
        "test_direct_item_inventory_is_mechanically_reconciled"
    ),
    (
        "tests/architecture/test_content_recovery_cr0_evidence.py::"
        "test_every_behavior_identity_has_one_exact_concrete_owner"
    ),
    (
        "tests/architecture/test_content_recovery_cr0_evidence.py::"
        "test_every_current_proof_node_is_collectible"
    ),
    (
        "tests/architecture/test_content_recovery_cr0_evidence.py::"
        "test_every_materializable_root_has_one_exact_factory_owner"
    ),
    (
        "tests/architecture/test_content_recovery_cr0_evidence.py::"
        "test_legacy_authority_and_importer_inventories_match_current_python"
    ),
})
_NEW_NODES = frozenset({
    (
        "tests/architecture/test_content_recovery_cri_direct_items.py::"
        "test_cr0_binding_artifacts_remain_hash_and_row_exact"
    ),
    (
        "tests/architecture/test_content_recovery_cri_direct_items.py::"
        "test_cri_direct_item_visual_values_match_frozen_cr0_rows"
    ),
    (
        "tests/architecture/test_content_recovery_cri_direct_items.py::"
        "test_cri_live_authority_and_importer_delta_is_exact"
    ),
    (
        "tests/architecture/test_content_recovery_cri_direct_items.py::"
        "test_cri_maintained_proof_union_is_collectible_and_hash_exact"
    ),
    (
        "tests/architecture/test_content_recovery_cri_direct_items.py::"
        "test_cri_non_item_visual_overlay_still_matches_current_owners"
    ),
    (
        "tests/architecture/test_content_recovery_cri_direct_items.py::"
        "test_cri_public_item_inventory_is_exact_and_direct"
    ),
    (
        "tests/architecture/test_content_recovery_cri_direct_items.py::"
        "test_cri_remaining_legacy_and_direct_item_construction_owners_are_exact"
    ),
    (
        "tests/architecture/test_content_recovery_cri_direct_items.py::"
        "test_cri_remaining_legacy_and_migrated_direct_behavior_owners_are_exact"
    ),
    *{
        "tests/engine/test_direct_item_runtime.py::" + name
        for name in (
            "test_all_maintained_holders_materialize_exact_direct_item_plans",
            "test_all_public_item_ids_construct_directly_with_independent_state",
            "test_behavior_bearing_items_preserve_exact_equip_consume_and_use_mechanics",
            "test_entity_birth_installs_direct_loadout_silently_and_publishes_complete_state",
            "test_guardian_spell_constructs_private_direct_object_and_preserves_zone_lifecycle",
            "test_initial_loadout_validation_and_failure_cleanup_leave_no_residue",
            "test_item_required_behavior_sources_cleanup_symmetrically_and_publish_direct_ids",
            "test_item_required_behaviors_execute_without_content_runtime_admission",
            "test_item_state_location_and_charge_events_publish_direct_item_id",
            "test_legacy_door_collision_migrates_to_explicit_directional_boundary_behavior",
            "test_oil_barrel_destruction_preserves_direct_material_transition",
            "test_private_guardian_item_is_direct_but_not_publicly_buildable",
            "test_runtime_inventory_equipment_and_world_mutations_remain_eventful",
            "test_stacks_charges_durability_containers_intrinsics_and_world_blockers_are_exact",
        )
    },
    *{
        "tests/progression/test_direct_item_durable_and_proficiency.py::" + name
        for name in (
            "test_character_item_v2_rejects_tampering_legacy_recipe_and_augmentations_without_partial_state",
            "test_character_item_v2_round_trip_authenticates_direct_state",
            "test_specific_weapon_proficiency_uses_direct_item_ids_in_attacks_sources_and_birth_facts",
        )
    },
})


def _normalized_hash(values: set[str] | frozenset[str]) -> str:
    return hashlib.sha256(
        ("\n".join(sorted(values)) + "\n").encode("utf-8"),
    ).hexdigest()


def _item_relevant_overlay_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        row
        for row in cr0._manifest()["python_binding_overlay"]
        if (
            row["source_path"] in _ITEM_EXCLUSIVE_OVERLAY_PATHS
            or row["semantic_id"].startswith("bestiary_wardrobe::")
            or row["semantic_id"].startswith("configured_srd_wardrobe::")
            or row["semantic_id"] in _GUARDIAN_OVERLAY_IDS
        )
    )


def _collect_nodes(arguments: tuple[str, ...] | list[str]) -> set[str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *arguments],
        cwd=cr0.REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return {
        line
        for line in result.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    }


def test_cr0_binding_artifacts_remain_hash_and_row_exact() -> None:
    """Immutable CR-0 bytes and all eight historical pairs remain exact."""
    assert cr0._sha256(cr0.MANIFEST_PATH.read_bytes()) == (
        "8693fbbeb949cf18bc9f4b7a1ba81845fac2db4bc5adc131729c5dc0d70bf5c7"
    )
    for row in cr0._manifest()["source_artifacts"]:
        payload = cr0._artifact_bytes(row)
        assert cr0._sha256(payload) == row["sha256"]
        assert cr0._artifact_row_count(row["artifact_id"], payload) == (
            row["row_count"]
        )

    reconciliation = cr0._manifest()["binding_reconciliation"]
    assert len(reconciliation["artifact_pairs"]) == 8
    assert len(reconciliation["rows"]) == 121
    overrides_by_pair: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    for row in reconciliation["rows"]:
        overrides_by_pair[row["artifact_pair"]][row["stable_row_identity"]] = row
    for pair in reconciliation["artifact_pairs"]:
        pair_id = pair["pair_id"]
        current = cr0._artifact_pair_rows(pair_id, pair["current_artifact_id"])
        accepted = cr0._artifact_pair_rows(pair_id, pair["accepted_artifact_id"])
        overrides = overrides_by_pair[pair_id]
        assert len(current) == pair["current_row_count"]
        assert len(accepted) == pair["accepted_row_count"]
        assert len(overrides) == pair["changed_or_collision_row_count"]
        for identity in set(current) | set(accepted):
            if identity in overrides:
                assert overrides[identity]["current_value"] == current.get(identity)
                assert overrides[identity]["accepted_value"] == accepted.get(identity)
                continue
            row = current.get(identity, accepted.get(identity))
            matches = [
                rule
                for rule in pair["default_rules"][:-1]
                if cr0._default_rule_matches(rule, identity, row)
            ]
            assert len(matches) <= 1
            assert cr0._default_rule_matches(pair["default_rules"][-1], identity, row)


def test_cri_direct_item_visual_values_match_frozen_cr0_rows() -> None:
    """The frozen item subset maps to exact direct instance visual values."""
    item_rows = _item_relevant_overlay_rows()
    item_ids = {row["semantic_id"] for row in item_rows}
    assert len(item_rows) == len(item_ids) == 182
    assert _normalized_hash(item_ids) == _ITEM_OVERLAY_ID_HASH

    variant_rows = {}
    artifact = cr0._artifact_json("current.authored_item_visuals")
    for category in artifact["inventory"]["categories"]:
        for row in category["variants"]:
            preset_id = row["preset_id"]
            if preset_id in DIRECT_ITEM_BUILDERS:
                variant_rows[preset_id] = (
                    row["display_name"],
                    category["base_category"],
                    row["visual_variant_id"],
                )
    assert len(variant_rows) == 20

    expected = dict(_FIXED_ACTIVE_VISUALS)
    for item_id, visual in variant_rows.items():
        assert build_authored_item(item_id, uuid4()).name == visual[0]
        expected[item_id] = visual[1:]

    actual = {}
    for item_id in DIRECT_ITEM_BUILDERS:
        item = build_authored_item(item_id, uuid4())
        if item.visual_item_name is not None or item.visual_variant_id is not None:
            actual[item_id] = (
                item.visual_item_name,
                item.visual_variant_id,
            )
    assert actual == expected

    overlay_item_ids = {
        row["semantic_id"]
        .removeprefix("definition_presentation::")
        .split(":", 2)[-1]
        .rsplit("@", 1)[0]
        for row in item_rows
        if row["semantic_id"].startswith("definition_presentation::")
        and (
            ":item:" in row["semantic_id"]
            or ":environment_object:" in row["semantic_id"]
        )
    }
    overlay_item_ids.remove("environment.door")
    overlay_item_ids.remove(_PRIVATE_GUARDIAN_ID)
    assert overlay_item_ids <= set(DIRECT_ITEM_BUILDERS)


def test_cri_live_authority_and_importer_delta_is_exact() -> None:
    """Direct-item authority remains exact after the later character cut."""
    manifest = cr0._manifest()
    authorities: dict[str, set[str]] = defaultdict(set)
    for row in manifest["legacy_authorities"]:
        authorities[row["authority_kind"]].add(row["legacy_identity"])
    removed_declarations = {
        identity
        for identity in authorities["declaration"]
        if ":item:" in identity or ":environment_object:" in identity
    }
    assert len(removed_declarations) == 128
    post_item_declarations = authorities["declaration"] - removed_declarations
    current_declarations = set(cr0._declarations())
    assert current_declarations <= post_item_declarations
    later_character_declarations = post_item_declarations - current_declarations
    assert len(later_character_declarations) == 168
    assert _normalized_hash(later_character_declarations) == (
        "3c961600b0cdac5211b6f3e4d391d0f366b74ee52f9f58feaf846f49ee27e6b2"
    )
    assert cr0._presets() == {}
    assert len(authorities["recipe_preset"]) == 205

    factory_identities = {
        identity
        for identity, declaration in cr0._declarations().items()
        if declaration.mode.value == "factory"
    }
    assert factory_identities == (
        authorities["materializable_root"]
        - removed_declarations
        - later_character_declarations
    )
    assert {
        identity
        for identity, declaration in cr0._declarations().items()
        if declaration.mode.value == "behavior_identity"
    } == authorities["behavior_identity"] - later_character_declarations
    assert {
        identity
        for identity, declaration in cr0._declarations().items()
        if declaration.mode.value == "typed_definition"
    } == authorities["structural_definition"] - later_character_declarations

    old_importers = {
        (row["path"], row["import_category"])
        for row in manifest["production_importers"]
    }
    assert _REMOVED_IMPORTERS <= old_importers
    post_item_importers = old_importers - _REMOVED_IMPORTERS
    current_importers = cr0._current_importer_keys()
    later_removed_importers = post_item_importers - current_importers
    assert len(later_removed_importers) == 86
    assert _normalized_hash(
        f"{path}|{category}" for path, category in later_removed_importers
    ) == "bcfb520b89f0a7b938c8be190be64aadc79379702bdf0375eaf6b3a7919759fd"
    assert current_importers - post_item_importers == {
        ("dnd/actions_functional.py", "imports_dnd_core_content"),
        ("dnd/content/items/authored_item_builders.py", "imports_dnd_core_content"),
    }


def test_cri_maintained_proof_union_is_collectible_and_hash_exact() -> None:
    """Every direct-item successor proof survives later recovery cuts."""
    existing_modules = [
        module
        for module in _AFFECTED_MODULES
        if (cr0.REPOSITORY_ROOT / module).is_file()
    ]
    collected = _collect_nodes(existing_modules)
    assert len(_NEW_NODES) == 25
    assert _normalized_hash(_NEW_NODES) == (
        "f5ea8b49e99135bd432bf3bb586324c444637afdc05ae99244f18c6d996993cd"
    )
    assert collected
    assert _collect_nodes(sorted(_NEW_NODES)) == _NEW_NODES


def test_cri_non_item_visual_overlay_still_matches_current_owners() -> None:
    """Every non-item CR-0 visual row still matches its active owner."""
    item_ids = {row["semantic_id"] for row in _item_relevant_overlay_rows()}
    current_declarations = set(cr0._declarations())
    later_character_ids = {
        f"definition_presentation::{identity}"
        for identity in cr0._definition_manifest_rows()
        if identity not in current_declarations
    } - item_ids
    assert len(later_character_ids) == 168
    assert _normalized_hash(later_character_ids) == (
        "c5805354eb533c3ff898abbec62935aaf9ab0d7d5760f9c7461d6031c2916556"
    )
    cr0.validate_historical_bindings_and_current_non_item_overlay(
        item_ids | later_character_ids,
    )


def test_cri_public_item_inventory_is_exact_and_direct() -> None:
    """The direct public surface is exactly 147 independent item species."""
    public_ids = set(DIRECT_ITEM_BUILDERS)
    assert len(public_ids) == 147
    assert _normalized_hash(public_ids) == _PUBLIC_ITEM_ID_HASH
    assert "environment.door" not in public_ids
    assert "environment.directional_door" in public_ids
    assert _PRIVATE_GUARDIAN_ID not in public_ids

    first = {item_id: build_authored_item(item_id, uuid4()) for item_id in public_ids}
    second = {item_id: build_authored_item(item_id, uuid4()) for item_id in public_ids}
    assert {item.item_id for item in first.values()} == public_ids
    assert all(first[item_id].uuid != second[item_id].uuid for item_id in public_ids)
    guardian = build_guardian_of_faith_object(uuid4())
    assert {item.item_id for item in first.values()} | {guardian.item_id} == (
        public_ids | {_PRIVATE_GUARDIAN_ID}
    )
    with pytest.raises(KeyError):
        build_authored_item(_PRIVATE_GUARDIAN_ID, uuid4())


def test_cri_remaining_legacy_and_direct_item_construction_owners_are_exact() -> None:
    """Creature factories remain unique; item construction is direct only."""
    declarations = cr0._declarations()
    factory_ids = {
        declaration.ref.content_id
        for declaration in declarations.values()
        if declaration.mode.value == "factory"
    }
    assert len(factory_ids) == 56
    assert all(item_id.startswith("creature.") for item_id in factory_ids)
    assert set(cr0._static_factory_owners()) == factory_ids
    assert not any(
        declaration.ref.definition_kind.value in {"item", "environment_object"}
        for declaration in declarations.values()
    )
    assert cr0._presets() == {}
    assert len(DIRECT_ITEM_BUILDERS) == 147


def test_cri_remaining_legacy_and_migrated_direct_behavior_owners_are_exact() -> None:
    """Legacy behaviors keep one owner and migrated item roots keep none."""
    declarations = cr0._declarations()
    behavior_ids = {
        declaration.ref.content_id
        for declaration in declarations.values()
        if declaration.mode.value == "behavior_identity"
    }
    assert len(behavior_ids) == 311
    assert set(cr0._static_behavior_owners()) == behavior_ids

    assert len(_DIRECT_SPECIAL_IDS) == 39
    assert len(set(DIRECT_ITEM_BUILDERS) - _DIRECT_SPECIAL_IDS) == 108
    legacy_content_ids = {
        declaration.ref.content_id for declaration in declarations.values()
    }
    assert not (_DIRECT_SPECIAL_IDS & legacy_content_ids)
    assert {
        build_authored_item(item_id, uuid4()).item_id
        for item_id in _DIRECT_SPECIAL_IDS
    } == _DIRECT_SPECIAL_IDS
