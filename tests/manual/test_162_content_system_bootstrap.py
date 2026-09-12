"""Shared standalone, gateway, and worker content-system bootstrap."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.artifact_digest import (
    LocalContentImportError,
    resolve_local_python_module_closure,
)
from dnd.content_system.builtin import (
    BUILT_IN_DECLARATIONS,
    BUILT_IN_PACK_DEPENDENCIES,
    BUILT_IN_PACK_VERSIONS,
    BUILT_IN_SOURCES,
)
from dnd.content_system.builtin_inventory import (
    BUILT_IN_DECLARATION_INVENTORY,
)
from dnd.content_system.configuration import (
    DEFAULT_CONTENT_PACK_ROOT,
    configured_content_pack_roots,
)
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.content.provenance import ContentSourceFamily, RulesBaseline


def test_default_bootstrap_freezes_exact_builtin_identity() -> None:
    """The repository pack root and built-ins produce one immutable identity."""
    loaded = bootstrap_content_system(pack_roots=(DEFAULT_CONTENT_PACK_ROOT,))

    assert len(loaded.content_set_digest) == 64
    assert loaded.packs == ()
    assert loaded.registry.declarations == {
        declaration.ref.identity_key: declaration
        for declaration in BUILT_IN_DECLARATIONS
    }
    assert tuple(
        declaration.ref.identity_key
        for declaration in BUILT_IN_DECLARATIONS
    ) == tuple(
        declaration.ref.identity_key
        for declaration in BUILT_IN_DECLARATION_INVENTORY
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


def test_installed_pack_dependency_closure_includes_transitive_helpers(
    tmp_path: Path,
) -> None:
    """External-pack dependency inspection follows delegated local helpers."""
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


def test_transitive_local_import_closure_fails_closed(
    tmp_path: Path,
) -> None:
    """External-pack dependency inspection rejects unresolved local imports."""
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
        content_set_digest="e" * 64,
    )
    with pytest.raises(RuntimeError, match="already installed"):
        runtime.install(incompatible)
