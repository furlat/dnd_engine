from ai.evaluation.arena_manifest import capture_arena_manifest_for_id, roster_identity_hash
from ai.evaluation.elo_contract import EntityRosterRow


def test_manifest_hashes_are_stable_across_volatile_uuids() -> None:
    first = capture_arena_manifest_for_id("standard_skeleton_doors", random_seed=1)
    second = capture_arena_manifest_for_id("standard_skeleton_doors", random_seed=1)

    assert first.manifest_hash == second.manifest_hash
    assert first.roster_hash_by_side == second.roster_hash_by_side
    assert set(first.entity_rosters) == {"heroes", "monsters"}


def test_manifest_captures_representative_arena_shapes() -> None:
    arena_ids = [
        "standard_skeleton_doors",
        "item_resource_gauntlet",
        "srd_low_cr_patrol",
        "high_level_spell_resource_duel",
    ]

    manifests = [
        capture_arena_manifest_for_id(arena_id, random_seed=1)
        for arena_id in arena_ids
    ]

    for manifest in manifests:
        assert manifest.map_size[0] > 0
        assert manifest.map_size[1] > 0
        assert "heroes" in manifest.roster_hash_by_side
        assert "monsters" in manifest.roster_hash_by_side
        assert manifest.manifest_hash
        assert any(row.action_template_summary for rows in manifest.entity_rosters.values() for row in rows)


def test_manifest_surfaces_items_spells_and_srd_rosters() -> None:
    item_manifest = capture_arena_manifest_for_id("item_resource_gauntlet", random_seed=1)
    srd_manifest = capture_arena_manifest_for_id("srd_low_cr_patrol", random_seed=1)
    spell_manifest = capture_arena_manifest_for_id("high_level_spell_resource_duel", random_seed=1)

    assert any(row.inventory_summary for rows in item_manifest.entity_rosters.values() for row in rows)
    item_rows = [
        item
        for rows in item_manifest.entity_rosters.values()
        for row in rows
        for item in [*row.inventory_summary, *row.equipment_summary]
    ]
    assert all(item.get("semantic_key") for item in item_rows)
    assert all("provided_action_semantic_keys" in item for item in item_rows)
    assert len(srd_manifest.entity_rosters["monsters"]) >= 5
    assert any(row.condition_summary for row in srd_manifest.entity_rosters["monsters"])
    assert any(row.handler_summary for row in srd_manifest.entity_rosters["monsters"])
    assert any(row.spell_summary for rows in spell_manifest.entity_rosters.values() for row in rows)
    assert all(row.get("semantic_key") for row in item_manifest.object_summary)


def test_manifest_distinguishes_bright_and_dark_open_battlefields() -> None:
    bright = capture_arena_manifest_for_id("skeleton_anti_aoe_split", random_seed=1)
    dark = capture_arena_manifest_for_id("srd_undead_crypt", random_seed=1)

    assert bright.terrain_summary["by_default_light"] != dark.terrain_summary["by_default_light"]
    assert bright.manifest_hash != dark.manifest_hash


def test_roster_identity_ignores_names_runtime_ownership_and_member_order() -> None:
    first = EntityRosterRow(
        stable_name="Alpha",
        faction="heroes",
        controller_type="pass",
        position=(1, 2),
        class_or_monster="Fighter",
        max_hp=20,
        current_hp=20,
        ac=16,
    )
    second = EntityRosterRow(
        stable_name="Beta",
        faction="heroes",
        controller_type="pass",
        position=(1, 3),
        class_or_monster="Sorcerer",
        max_hp=14,
        current_hp=14,
        ac=13,
    )
    renamed = first.model_copy(update={
        "stable_name": "Entirely Different",
        "faction": "monsters",
        "controller_type": "external_ai",
        "position": (12, 12),
    })

    assert roster_identity_hash([first, second]) == roster_identity_hash([second, renamed])
