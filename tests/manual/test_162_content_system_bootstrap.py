"""Shared standalone, gateway, and worker content-system bootstrap."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.artifact_digest import (
    LocalContentImportError,
    digest_artifact_paths,
    resolve_local_python_module_closure,
)
from dnd.content_system.builtin import (
    BUILT_IN_ARTIFACT_DIGEST,
    BUILT_IN_ARTIFACT_PATHS,
    BUILT_IN_DATA_ARTIFACT_PATHS,
    BUILT_IN_DECLARATIONS,
    BUILT_IN_IMPLEMENTATION_ROOT_MODULES,
    BUILT_IN_PACK_DEPENDENCIES,
    BUILT_IN_PACK_VERSIONS,
    BUILT_IN_PYTHON_ARTIFACT_PATHS,
    BUILT_IN_SOURCES,
)
from dnd.content_system.configuration import (
    DEFAULT_CONTENT_PACK_ROOT,
    configured_content_pack_roots,
)
from dnd.content_system.action_definitions import (
    ACTION_BEHAVIOR_DECLARATIONS,
)
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_DECLARATIONS,
)
from dnd.content_system.character_origin_definitions import (
    NEURODRAGON_CHARACTER_ORIGIN_DECLARATIONS,
    SRD_CHARACTER_ORIGIN_DECLARATIONS,
)
from dnd.content_system.starting_equipment_definitions import (
    STARTING_EQUIPMENT_PACKAGE_DECLARATIONS,
)
from dnd.content_system.reaction_definitions import (
    REACTION_BEHAVIOR_DECLARATIONS,
)
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.content.provenance import ContentSourceFamily, RulesBaseline
from dnd.actions import CORE_STANDARD_ACTION_DECLARATIONS
from dnd.classes.barbarian_progression_definitions import (
    BARBARIAN_PROGRESSION_DECLARATIONS,
)
from dnd.classes.content_factories import (
    PLAYER_CLASS_CREATURE_DECLARATIONS,
)
from dnd.classes.progression_definitions import (
    FIGHTER_PROGRESSION_DECLARATIONS,
)
from dnd.classes.sorcerer_progression_definitions import (
    SORCERER_PROGRESSION_DECLARATIONS,
)
from dnd.classes.sorcerer_structural_feature_definitions import (
    SORCERER_STRUCTURAL_FEATURE_DECLARATIONS,
)
from dnd.classes.structural_feature_definitions import (
    STRUCTURAL_CLASS_FEATURE_DECLARATIONS,
)
from dnd.conditions import CORE_STANDARD_CONDITION_DECLARATIONS
from dnd.extensions.field_focus import (
    NEURODRAGON_FIELD_FOCUS_ITEM_DECLARATIONS,
)
from dnd.items.armors import (
    NEURODRAGON_ARMOR_DECLARATIONS,
    SRD_ARMOR_DECLARATIONS,
)
from dnd.items.consumables import NEURODRAGON_CONSUMABLE_DECLARATIONS
from dnd.items.environment_content import (
    NEURODRAGON_ENVIRONMENT_OBJECT_DECLARATIONS,
)
from dnd.items.spell_items import (
    ACID_FLASK_SPELL_DECLARATION,
    NEURODRAGON_SPELL_ITEM_DECLARATIONS,
)
from dnd.items.torches import NEURODRAGON_TORCH_DECLARATIONS
from dnd.items.weapons import (
    NEURODRAGON_WEAPON_DECLARATIONS,
    SRD_WEAPON_DECLARATIONS,
)
from dnd.monsters.srd_roster import SRD_CREATURE_DECLARATIONS
from dnd.monsters.multiattack_definitions import (
    SRD_MULTIATTACK_CONFIGURATION_DECLARATIONS,
)
from dnd.monsters.srd_roster_items import (
    SRD_CREATURE_POSSESSION_ITEM_DECLARATIONS,
)
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_DECLARATIONS
from dnd.monsters.bestiary_items import (
    NEURODRAGON_BESTIARY_ITEM_DECLARATIONS,
)
from dnd.monsters.circus_fighter_items import (
    NEURODRAGON_CIRCUS_ITEM_DECLARATIONS,
)
from dnd.premade_characters import NEURODRAGON_PREMADE_CREATURE_DECLARATIONS
from dnd.player_character_body import PLAYER_CHARACTER_BODY_DECLARATION
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS
from dnd.spells.conjuration import (
    SRD_SPELL_ENVIRONMENT_OBJECT_DECLARATIONS,
)
from dnd.spells.abjuration import COUNTERSPELL_REACTION_DECLARATION
from dnd.spells.abjuration import SHIELD_REACTION_DECLARATION
from dnd.spells.reaction_spell_content import (
    LEARNED_REACTION_SPELL_DECLARATIONS,
)


def test_default_bootstrap_freezes_exact_builtin_identity() -> None:
    """The repository pack root and built-ins produce one immutable identity."""
    loaded = bootstrap_content_system(pack_roots=(DEFAULT_CONTENT_PACK_ROOT,))

    assert len(loaded.content_set_digest) == 64
    assert loaded.built_in_artifact_digest == BUILT_IN_ARTIFACT_DIGEST
    assert loaded.packs == ()
    expected_declarations = (
        *CORE_STANDARD_ACTION_DECLARATIONS,
        *CORE_STANDARD_CONDITION_DECLARATIONS,
        *ACTION_BEHAVIOR_DECLARATIONS,
        *CONDITION_BEHAVIOR_DECLARATIONS,
        *REACTION_BEHAVIOR_DECLARATIONS,
        *STRUCTURAL_CLASS_FEATURE_DECLARATIONS,
        *SORCERER_STRUCTURAL_FEATURE_DECLARATIONS,
        *SRD_CHARACTER_ORIGIN_DECLARATIONS,
        *NEURODRAGON_CHARACTER_ORIGIN_DECLARATIONS,
        *STARTING_EQUIPMENT_PACKAGE_DECLARATIONS,
        *BARBARIAN_PROGRESSION_DECLARATIONS,
        *FIGHTER_PROGRESSION_DECLARATIONS,
        *SORCERER_PROGRESSION_DECLARATIONS,
        COUNTERSPELL_REACTION_DECLARATION,
        SHIELD_REACTION_DECLARATION,
        *LEARNED_REACTION_SPELL_DECLARATIONS,
        *NEURODRAGON_ARMOR_DECLARATIONS,
        *NEURODRAGON_BESTIARY_ITEM_DECLARATIONS,
        *NEURODRAGON_CIRCUS_ITEM_DECLARATIONS,
        *BESTIARY_CREATURE_DECLARATIONS,
        *NEURODRAGON_CONSUMABLE_DECLARATIONS,
        *NEURODRAGON_ENVIRONMENT_OBJECT_DECLARATIONS,
        *NEURODRAGON_FIELD_FOCUS_ITEM_DECLARATIONS,
        *NEURODRAGON_PREMADE_CREATURE_DECLARATIONS,
        PLAYER_CHARACTER_BODY_DECLARATION,
        *NEURODRAGON_SPELL_ITEM_DECLARATIONS,
        *NEURODRAGON_TORCH_DECLARATIONS,
        *NEURODRAGON_WEAPON_DECLARATIONS,
        *PLAYER_CLASS_CREATURE_DECLARATIONS,
        ACID_FLASK_SPELL_DECLARATION,
        *SPELL_CONTENT_DECLARATIONS,
        *SRD_SPELL_ENVIRONMENT_OBJECT_DECLARATIONS,
        *SRD_ARMOR_DECLARATIONS,
        *SRD_CREATURE_POSSESSION_ITEM_DECLARATIONS,
        *SRD_MULTIATTACK_CONFIGURATION_DECLARATIONS,
        *SRD_CREATURE_DECLARATIONS,
        *SRD_WEAPON_DECLARATIONS,
    )
    assert loaded.registry.declarations == {
        declaration.ref.identity_key: declaration
        for declaration in BUILT_IN_DECLARATIONS
    }
    assert tuple(
        declaration.ref.identity_key
        for declaration in BUILT_IN_DECLARATIONS
    ) == tuple(
        declaration.ref.identity_key
        for declaration in expected_declarations
    )
    assert tuple(loaded.registry.sources) == (
        "wotc.srd_5_1_cc",
        "neurodragon.original_b2b3930",
    )
    assert BUILT_IN_PACK_VERSIONS == {
        "content.neurodragon": "1.0.0",
        "content.srd_5_1_cc": "1.0.0",
        "core.rules": "1.0.0",
    }
    assert BUILT_IN_PACK_DEPENDENCIES == {
        "content.neurodragon": frozenset({
            "content.srd_5_1_cc",
            "core.rules",
        }),
        "content.srd_5_1_cc": frozenset({"core.rules"}),
        "core.rules": frozenset(),
    }
    assert tuple(source.source_id for source in BUILT_IN_SOURCES) == (
        "wotc.srd_5_1_cc",
        "neurodragon.original_b2b3930",
    )
    neurodragon_source = BUILT_IN_SOURCES[1]
    assert neurodragon_source.source_family == (
        ContentSourceFamily.NEURODRAGON_ORIGINAL
    )
    assert neurodragon_source.rules_baseline == RulesBaseline.ENGINE_NEUTRAL
    assert neurodragon_source.license_id == "Neurodragon-Original"


def test_configured_roots_are_default_plus_sorted_absolute_additions(
    tmp_path: Path,
) -> None:
    """Deployment configuration cannot hide or ambiguously relativize roots."""
    first = tmp_path / "zeta"
    second = tmp_path / "alpha"
    first.mkdir()
    second.mkdir()
    configured = configured_content_pack_roots(
        {
            "DND_CONTENT_PACK_ROOTS": os.pathsep.join(
                (str(first), str(second), str(first)),
            ),
        },
    )

    assert configured == (
        DEFAULT_CONTENT_PACK_ROOT,
        second.resolve(),
        first.resolve(),
    )

    with pytest.raises(ValueError, match="absolute"):
        configured_content_pack_roots(
            {"DND_CONTENT_PACK_ROOTS": "relative/content-packs"},
        )


def test_builtin_artifact_digest_is_required_and_stable() -> None:
    """Built-in source and data close over one authenticated identity."""
    assert len(BUILT_IN_ARTIFACT_DIGEST) == 64
    assert BUILT_IN_ARTIFACT_DIGEST == bootstrap_content_system(
        pack_roots=(DEFAULT_CONTENT_PACK_ROOT,),
    ).built_in_artifact_digest
    relative_paths = {
        path.relative_to(Path(__file__).resolve().parents[2]).as_posix()
        for path in BUILT_IN_ARTIFACT_PATHS
    }
    assert {
        "dnd/actions_functional.py",
        "dnd/classes/barbarian.py",
        "dnd/classes/barbarian_progression_definitions.py",
        "dnd/items/armors.py",
        "dnd/items/consumables.py",
        "dnd/items/spell_items.py",
        "dnd/items/torches.py",
        "dnd/items/weapons.py",
        "dnd/classes/content_factories.py",
        "dnd/classes/fighter.py",
        "dnd/classes/progression_definitions.py",
        "dnd/classes/rage.py",
        "dnd/classes/sorcerer.py",
        "dnd/classes/sorcerer_progression_definitions.py",
        "dnd/content_system/artifact_digest.py",
        "dnd/content_system/builtin.py",
        "dnd/content_system/builtin_character_builds.py",
        "dnd/content_system/character_build_validation.py",
        "dnd/content_system/character_materialization.py",
        "dnd/content_system/installed_creature_materialization.py",
        "dnd/monsters/bestiary.py",
        "dnd/monsters/bestiary_content.py",
        "dnd/monsters/bestiary_items.py",
        "dnd/monsters/skeleton_abilities.py",
        "dnd/monsters/srd_roster.py",
        "dnd/monsters/traits.py",
        "dnd/player_character_body.py",
        "dnd/spells/conjuration.py",
        "dnd/spells/necromancy.py",
        "content_data/ledgers/neuroclient_authored_item_visuals.json",
        "content_data/sources/neurodragon_original_b2b3930.json",
        "content_data/sources/neurodragon_original_b2b3930.txt",
        "content_data/sources/srd_5_1_cc.json",
    } <= relative_paths
    assert set(BUILT_IN_PYTHON_ARTIFACT_PATHS).isdisjoint(
        BUILT_IN_DATA_ARTIFACT_PATHS,
    )
    assert set(BUILT_IN_ARTIFACT_PATHS) == {
        *BUILT_IN_PYTHON_ARTIFACT_PATHS,
        *BUILT_IN_DATA_ARTIFACT_PATHS,
    }
    assert BUILT_IN_IMPLEMENTATION_ROOT_MODULES == (
        "dnd.content_system.builtin",
    )


def test_transitive_helper_bytes_change_builtin_artifact_identity(
    tmp_path: Path,
) -> None:
    """A delegated helper changes identity without becoming a manual root."""
    package = tmp_path / "dnd"
    classes = package / "classes"
    content_system = package / "content_system"
    classes.mkdir(parents=True)
    content_system.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (classes / "__init__.py").write_text("", encoding="utf-8")
    (content_system / "__init__.py").write_text("", encoding="utf-8")
    composition_root = content_system / "builtin.py"
    declaration_owner = classes / "content_factories.py"
    helper_module = classes / "barbarian_factory.py"
    composition_root.write_text(
        "from dnd.classes.content_factories import DECLARATIONS\n",
        encoding="utf-8",
    )
    declaration_owner.write_text(
        "from dnd.classes.barbarian_factory import create_barbarian\n",
        encoding="utf-8",
    )
    helper_module.write_text(
        "def create_barbarian() -> str:\n    return 'first'\n",
        encoding="utf-8",
    )

    artifacts = resolve_local_python_module_closure(
        ("dnd.content_system.builtin",),
        repository_root=tmp_path,
    )
    assert {
        path.relative_to(tmp_path).as_posix()
        for path in artifacts
    } == {
        "dnd/__init__.py",
        "dnd/classes/__init__.py",
        "dnd/classes/barbarian_factory.py",
        "dnd/classes/content_factories.py",
        "dnd/content_system/__init__.py",
        "dnd/content_system/builtin.py",
    }
    before = digest_artifact_paths(
        artifacts,
        repository_root=tmp_path,
    )

    helper_module.write_text(
        "def create_barbarian() -> str:\n    return 'second'\n",
        encoding="utf-8",
    )
    after = digest_artifact_paths(
        resolve_local_python_module_closure(
            ("dnd.content_system.builtin",),
            repository_root=tmp_path,
        ),
        repository_root=tmp_path,
    )

    assert before != after


def test_transitive_local_import_closure_fails_closed(
    tmp_path: Path,
) -> None:
    """A missing local helper cannot produce a partial content identity."""
    package = tmp_path / "dnd"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "declaration.py").write_text(
        "from dnd.missing_helper import build\n",
        encoding="utf-8",
    )

    with pytest.raises(
        LocalContentImportError,
        match="unresolved local content module dnd.missing_helper",
    ):
        resolve_local_python_module_closure(
            ("dnd.declaration",),
            repository_root=tmp_path,
        )

    (package / "missing_helper.py").write_text(
        "build = object()\n",
        encoding="utf-8",
    )
    ambiguous_package = package / "missing_helper"
    ambiguous_package.mkdir()
    (ambiguous_package / "__init__.py").write_text(
        "build = object()\n",
        encoding="utf-8",
    )
    with pytest.raises(
        LocalContentImportError,
        match="ambiguous local content module dnd.missing_helper",
    ):
        resolve_local_python_module_closure(
            ("dnd.declaration",),
            repository_root=tmp_path,
        )


def test_runtime_installs_one_digest_and_never_rebinds() -> None:
    """A process has one frozen content identity until it is restarted."""
    runtime = ContentSystemRuntime()
    with pytest.raises(RuntimeError, match="not installed"):
        runtime.require()

    loaded = bootstrap_content_system(pack_roots=(DEFAULT_CONTENT_PACK_ROOT,))
    assert runtime.install(loaded) is loaded
    assert runtime.require() is loaded
    assert runtime.install(loaded) is loaded
    equivalent = bootstrap_content_system(
        pack_roots=(DEFAULT_CONTENT_PACK_ROOT,),
    )
    assert equivalent is not loaded
    assert runtime.install(equivalent) is loaded
    assert runtime.materialization_count == 0

    incompatible = loaded.__class__(
        registry=loaded.registry,
        packs=loaded.packs,
        built_in_artifact_digest="f" * 64,
        content_set_digest="e" * 64,
    )
    with pytest.raises(RuntimeError, match="already installed"):
        runtime.install(incompatible)
