"""Canonical SRD creature declarations and materialization behavior."""

from __future__ import annotations

import subprocess
import sys
from types import MappingProxyType
from uuid import uuid4

import pytest

from dnd.content_system.creature_bindings import CREATURE_RUNTIME_BINDINGS
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentReviewStatus,
)
from dnd.types.equipment import WeaponSlot
from dnd.monsters import srd_roster
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS,
    SRD_CREATURE_DECLARATIONS_BY_ID,
    SRD_CREATURE_RECIPES_BY_ID,
)
from dnd.items.weapons import CLUB_RECIPE
from dnd.runtime_reset import reset_engine_runtime


EXPECTED_SRD_CREATURE_IDS = (
    "commoner",
    "bandit",
    "cultist",
    "guard",
    "tribal_warrior",
    "kobold",
    "acolyte",
    "scout",
    "thug",
    "spy",
    "berserker",
    "bandit_captain",
    "priest",
    "cult_fanatic",
    "knight",
    "veteran",
    "mage",
    "orc",
    "hobgoblin",
    "bugbear",
    "gnoll",
    "ogre",
    "wolf",
    "dire_wolf",
    "zombie",
    "ogre_zombie",
    "ghoul",
)


def _materialize(
    creature_id: str,
    possession_mode: CreaturePossessionMode,
):
    declaration = SRD_CREATURE_DECLARATIONS_BY_ID[creature_id]
    return materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID[creature_id],
        runtime_entity_uuid=uuid4(),
        display_name=declaration.descriptor.display_name,
        faction="monsters",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.srd_roster.{creature_id}",
        ),
        possession_mode=possession_mode,
    )


def test_srd_creature_registry_is_exact_immutable_and_has_no_legacy_lookup() -> None:
    """The 27 authenticated recipes are the sole public roster identity."""
    assert tuple(SRD_CREATURE_DECLARATIONS_BY_ID) == EXPECTED_SRD_CREATURE_IDS
    assert tuple(SRD_CREATURE_RECIPES_BY_ID) == EXPECTED_SRD_CREATURE_IDS
    assert isinstance(SRD_CREATURE_DECLARATIONS_BY_ID, MappingProxyType)
    assert isinstance(SRD_CREATURE_RECIPES_BY_ID, MappingProxyType)
    assert tuple(SRD_CREATURE_DECLARATIONS_BY_ID.values()) == (
        SRD_CREATURE_DECLARATIONS
    )
    assert not hasattr(srd_roster, "SRD_MONSTER_FACTORIES")
    assert not hasattr(srd_roster, "SRD_MONSTER_SPECS")
    assert not hasattr(srd_roster, "create_srd_monster")
    assert not hasattr(srd_roster, "list_srd_monster_specs")


def test_builtin_and_roster_import_cold_without_bootstrap_cycle() -> None:
    """Definition composition never imports either lazy runtime adapter."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import dnd.content_system.builtin; "
                "import dnd.monsters.srd_roster; "
                "import dnd.content_system.bootstrap"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_installed_runtime_item_leaf_fails_clearly_without_startup() -> None:
    """Canonical materializers never invent or lazily install a registry."""
    runtime = ContentSystemRuntime()
    with pytest.raises(RuntimeError, match="Content system is not installed"):
        materialize_item(
            CLUB_RECIPE,
            uuid4(),
            origin=ItemRuntimeOrigin.STARTER,
            runtime=runtime,
        )
    with pytest.raises(RuntimeError, match="Content system is not installed"):
        materialize_creature(
            SRD_CREATURE_RECIPES_BY_ID["commoner"],
            runtime_entity_uuid=uuid4(),
            display_name="Uninstalled Commoner",
            faction="monsters",
            position=(2, 2),
            deployment_role=CreatureDeploymentRole(
                role_id="encounter.uninstalled.commoner",
            ),
            possession_mode=(
                CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
            ),
            runtime=runtime,
        )
    assert runtime.is_installed is False


def test_every_srd_creature_recipe_has_public_reviewed_5_1_provenance() -> None:
    """Catalog metadata is carried by the authenticated declaration itself."""
    identity_keys: set[str] = set()
    contract_hashes: set[str] = set()
    for creature_id, declaration in SRD_CREATURE_DECLARATIONS_BY_ID.items():
        recipe = SRD_CREATURE_RECIPES_BY_ID[creature_id]
        assert declaration.ref == recipe.ref
        assert recipe.parameters == {}
        assert declaration.ref.pack_id == "content.srd_5_1_cc"
        assert declaration.ref.definition_kind == ContentDefinitionKind.CREATURE
        assert declaration.ref.content_id == f"creature.{creature_id}"
        assert declaration.descriptor.visibility.value == "public"
        assert "creature" in declaration.descriptor.tags
        assert "srd" in declaration.descriptor.tags
        assert declaration.provenance.primary_source_id == "wotc.srd_5_1_cc"
        assert declaration.provenance.fidelity == ContentFidelity.PARTIAL
        assert (
            declaration.provenance.review_status
            == ContentReviewStatus.REVIEWED
        )
        identity_keys.add(declaration.ref.identity_key)
        contract_hashes.add(declaration.ref.definition_contract_hash)
    assert identity_keys == {
        recipe.ref.identity_key
        for recipe in SRD_CREATURE_RECIPES_BY_ID.values()
    }
    assert len(contract_hashes) == 1


def test_every_srd_creature_materializes_with_exact_identity_and_actions() -> None:
    """The full default-loadout mode preserves every currently playable root."""
    for creature_id in EXPECTED_SRD_CREATURE_IDS:
        reset_engine_runtime(grid_size=(12, 12))
        entity = _materialize(
            creature_id,
            CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
        )
        recipe = SRD_CREATURE_RECIPES_BY_ID[creature_id]
        actions = entity.get_available_actions()
        action_rows = (
            len(actions.entity_actions)
            + len(actions.position_actions)
            + len(actions.self_actions)
            + len(actions.object_actions)
        )
        assert entity.content_ref == recipe.ref
        assert entity.uuid == entity.source_entity_uuid
        assert entity.get_hp() > 0
        assert entity.ac_bonus().normalized_score >= 8
        assert action_rows > 0
        binding = CREATURE_RUNTIME_BINDINGS.require(entity.uuid)
        assert binding.recipe == recipe
        assert (
            binding.possession_mode
            == CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
        )


def test_structure_only_drops_default_loadouts_but_keeps_body_intrinsics() -> None:
    """Persistence reconstruction can omit loot without deleting anatomy."""
    for creature_id in EXPECTED_SRD_CREATURE_IDS:
        reset_engine_runtime(grid_size=(12, 12))
        entity = _materialize(
            creature_id,
            CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY,
        )
        assert entity.content_ref == SRD_CREATURE_RECIPES_BY_ID[creature_id].ref

        body_armor = entity.equipment.body_armor
        melee = entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
        offhand = entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_OFF)
        ranged = entity.equipment._get_weapon_by_slot(WeaponSlot.RANGED_MAIN)
        if creature_id in {"wolf", "dire_wolf"}:
            assert body_armor is not None
            assert body_armor.name == "Natural Armor"
            assert melee is not None and melee.name == "Bite"
        elif creature_id == "zombie":
            assert body_armor is None
            assert melee is not None and melee.name == "Slam"
        elif creature_id == "ghoul":
            assert body_armor is None
            assert melee is not None and melee.name == "Claws"
            assert offhand is not None and offhand.name == "Bite"
        else:
            assert body_armor is None
            assert melee is None
            assert offhand is None
        assert ranged is None
