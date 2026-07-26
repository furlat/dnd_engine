"""Deterministic startup loading for trusted external content packs."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID

import pytest

from dnd.content_system import pack_loader
from dnd.content_system.pack_loader import (
    discover_content_packs,
    load_content_system,
)
from dnd.core.base_object import BaseObject
from dnd.core.content.recipes import ContentRecipe
from dnd.core.events import EventQueue
from dnd.entity import Entity


_BUILT_IN_ARTIFACT_DIGEST = "a" * 64
_MUTATED_OBJECT_UUID = UUID("10000000-0000-0000-0000-000000000001")
_MUTATED_ENTITY_UUID = UUID("10000000-0000-0000-0000-000000000002")
_MUTATED_HANDLER_UUID = UUID("10000000-0000-0000-0000-000000000003")


def _write_fixture_pack(
    root: Path,
    *,
    directory_name: str,
    pack_id: str,
    python_package: str,
    content_id: str,
    import_failure: bool = False,
    dependencies: tuple[tuple[str, str], ...] = (),
    extra_imports: tuple[str, ...] = (),
) -> tuple[Path, Path]:
    pack_directory = root / directory_name
    package_directory = (
        pack_directory
        / "src"
        / Path(*python_package.split("."))
    )
    package_directory.mkdir(parents=True)
    marker_path = root / f"{directory_name}.imported.marker"
    manifest_lines = [
        "schema_version = 1",
        f'pack_id = "{pack_id}"',
        'pack_version = "1.0.0"',
        "engine_content_api = 1",
        'python_root = "src"',
        f'python_package = "{python_package}"',
        "",
    ]
    for dependency_pack_id, dependency_version in dependencies:
        manifest_lines.extend(
            (
                "[[dependencies]]",
                f'pack_id = "{dependency_pack_id}"',
                f'version = "{dependency_version}"',
                "",
            ),
        )
    manifest_lines.extend(
        (
            "[[sources]]",
            f'source_id = "{pack_id}.source"',
            'source_family = "fixture_internal"',
            'title = "Loader fixture source"',
            'source_version = "1"',
            'rules_baseline = "engine_neutral"',
            'license_id = "INTERNAL-TEST"',
            'canonical_uri = "https://example.invalid/loader-fixture"',
            f'document_digest = "{"f" * 64}"',
            'attribution_text = "Internal deterministic loader fixture."',
            "",
        ),
    )
    (pack_directory / "content-pack.toml").write_text(
        "\n".join(manifest_lines),
        encoding="utf-8",
    )
    (package_directory / "__init__.py").write_text(
        "from .items import create_fixture_item\n",
        encoding="utf-8",
    )
    failure_line = "raise RuntimeError('fixture import failed')\n" if import_failure else ""
    (package_directory / "items.py").write_text(
        "\n".join(
            (
                "from pathlib import Path",
                "from pydantic import BaseModel, ConfigDict",
                "from dnd.core.content.descriptors import ContentDescriptorSpec, ContentVisibility",
                "from dnd.core.content.item_definitions import ItemDefinition, ItemPersistencePolicy",
                "from dnd.core.content.provenance import ContentFidelity, ContentProvenance, ContentProvenanceRelation, ContentReviewStatus",
                "from dnd.core.content.registration import item_factory",
                *extra_imports,
                "",
                f"Path({str(marker_path)!r}).write_text('imported', encoding='utf-8')",
                failure_line.rstrip(),
                "",
                "class Parameters(BaseModel):",
                "    model_config = ConfigDict(extra='forbid', frozen=True)",
                "    charges: int",
                "",
                "@item_factory(",
                f"    pack_id={pack_id!r},",
                f"    content_id={content_id!r},",
                "    version=1,",
                "    parameters=Parameters,",
                "    descriptor=ContentDescriptorSpec(",
                "        display_name='Fixture Item',",
                "        description='Loaded from a trusted external pack.',",
                "        visibility=ContentVisibility.PUBLIC,",
                "        tags=('fixture',),",
                "    ),",
                "    provenance=ContentProvenance(",
                f"        primary_source_id={pack_id + '.source'!r},",
                "        source_anchor='Fixture / Item',",
                "        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,",
                "        fidelity=ContentFidelity.COMPLETE,",
                "        review_status=ContentReviewStatus.REVIEWED,",
                "    ),",
                "    item_definition=ItemDefinition(",
                "        persistence_policy=ItemPersistencePolicy.POSSESSION,",
                "    ),",
                ")",
                "def create_fixture_item(context: object, parameters: Parameters):",
                "    return context, parameters.charges",
                "",
            ),
        ),
        encoding="utf-8",
    )
    return pack_directory, marker_path


def _package_directory(pack_directory: Path, python_package: str) -> Path:
    """Return the fixture's concrete Python package directory."""
    return (
        pack_directory
        / "src"
        / Path(*python_package.split("."))
    )


def _replace_fixture_extra_import(
    pack_directory: Path,
    python_package: str,
    replacement: str,
) -> None:
    """Replace the fixture's import insertion point with arbitrary source."""
    items_path = _package_directory(pack_directory, python_package) / "items.py"
    source = items_path.read_text(encoding="utf-8")
    items_path.write_text(
        source.replace(
            "from dnd.core.content.registration import item_factory",
            "from dnd.core.content.registration import item_factory\n"
            + replacement,
        ),
        encoding="utf-8",
    )


def _runtime_registry_identity() -> tuple[object, ...]:
    """Capture identity-level facts for registries protected by cold loading."""
    return (
        tuple(
            sorted(
                (str(key), id(value))
                for key, value in BaseObject._registry.items()
            ),
        ),
        tuple(
            sorted(
                (str(key), id(value))
                for key, value in Entity._entity_registry.items()
            ),
        ),
        tuple(
            sorted(
                (
                    position,
                    tuple(id(entity) for entity in entities),
                )
                for position, entities in Entity._entity_by_position.items()
            ),
        ),
        tuple(
            sorted(
                (str(key), id(value))
                for key, value in EventQueue._event_handlers.items()
            ),
        ),
        tuple(
            sorted(
                (
                    str(source_uuid),
                    tuple(id(handler) for handler in handlers),
                )
                for source_uuid, handlers
                in EventQueue._event_handlers_by_source_entity_uuid.items()
            ),
        ),
    )


def test_discovery_is_cold_and_loading_publishes_one_frozen_registry(
    tmp_path: Path,
) -> None:
    """Manifest validation precedes imports and only a complete load is returned."""
    root = tmp_path / "packs"
    root.mkdir()
    _, marker = _write_fixture_pack(
        root,
        directory_name="alpha",
        pack_id="fixture.alpha",
        python_package="fixture_pack_alpha",
        content_id="item.alpha",
    )

    discovered = discover_content_packs((root,))
    assert tuple(row.manifest.pack_id for row in discovered) == ("fixture.alpha",)
    assert len(discovered[0].discovery_pack_digest) == 64
    assert not marker.exists()

    loaded = load_content_system(
        pack_roots=(root,),
        built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
    )
    assert marker.read_text(encoding="utf-8") == "imported"
    assert len(loaded.content_set_digest) == 64
    assert loaded.built_in_artifact_digest == _BUILT_IN_ARTIFACT_DIGEST
    assert tuple(loaded.registry.declarations) == (
        "fixture.alpha:item:item.alpha@1",
    )

    declaration = next(iter(loaded.registry.declarations.values()))
    recipe = ContentRecipe.create(
        ref=declaration.ref,
        parameters={"charges": 4},
    )
    context = object()
    assert loaded.registry.materialize(recipe, context) == (context, 4)


def test_pack_root_order_does_not_change_content_set_digest(tmp_path: Path) -> None:
    """Configured filesystem root order cannot affect protocol identity."""
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    _write_fixture_pack(
        first_root,
        directory_name="zeta",
        pack_id="fixture.zeta",
        python_package="fixture_pack_zeta",
        content_id="item.zeta",
    )
    _write_fixture_pack(
        second_root,
        directory_name="beta",
        pack_id="fixture.beta",
        python_package="fixture_pack_beta",
        content_id="item.beta",
    )

    forward = load_content_system(
        pack_roots=(first_root, second_root),
        built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
    )
    reverse = load_content_system(
        pack_roots=(second_root, first_root),
        built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
    )
    assert forward.content_set_digest == reverse.content_set_digest
    assert tuple(forward.registry.declarations) == tuple(reverse.registry.declarations)


def test_duplicate_pack_id_and_import_failure_abort_without_partial_result(
    tmp_path: Path,
) -> None:
    """Ambiguous or failing packs never produce a partly usable registry."""
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    _write_fixture_pack(
        first_root,
        directory_name="one",
        pack_id="fixture.duplicate",
        python_package="fixture_pack_duplicate_one",
        content_id="item.one",
    )
    _write_fixture_pack(
        second_root,
        directory_name="two",
        pack_id="fixture.duplicate",
        python_package="fixture_pack_duplicate_two",
        content_id="item.two",
    )
    with pytest.raises(ValueError, match="Duplicate content pack"):
        load_content_system(
            pack_roots=(first_root, second_root),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )

    failure_root = tmp_path / "failure"
    failure_root.mkdir()
    _write_fixture_pack(
        failure_root,
        directory_name="broken",
        pack_id="fixture.broken",
        python_package="fixture_pack_broken",
        content_id="item.broken",
        import_failure=True,
    )
    with pytest.raises(RuntimeError, match="fixture import failed"):
        load_content_system(
            pack_roots=(failure_root,),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )


def test_python_or_asset_symlink_cannot_escape_pack_directory(
    tmp_path: Path,
) -> None:
    """Resolved pack paths remain beneath their manifested pack directory."""
    root = tmp_path / "packs"
    root.mkdir()
    pack, _ = _write_fixture_pack(
        root,
        directory_name="escape",
        pack_id="fixture.escape",
        python_package="fixture_pack_escape",
        content_id="item.escape",
    )
    external = tmp_path / "external"
    external.mkdir()
    original_python_root = pack / "src"
    for path in sorted(original_python_root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        else:
            path.rmdir()
    original_python_root.rmdir()
    os.symlink(external, original_python_root, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes pack directory"):
        discover_content_packs((root,))


def test_length_prefixed_pack_hash_has_no_file_boundary_collision(
    tmp_path: Path,
) -> None:
    """A file payload cannot masquerade as additional path/content records."""
    embedded_records = tmp_path / "embedded"
    separate_records = tmp_path / "separate"
    embedded_records.mkdir()
    separate_records.mkdir()
    (embedded_records / "a").write_bytes(b"x\0b\0y")
    (separate_records / "a").write_bytes(b"x")
    (separate_records / "b").write_bytes(b"y")

    assert pack_loader._hash_pack_directory(
        embedded_records,
    ) != pack_loader._hash_pack_directory(separate_records)


def test_built_in_artifact_digest_is_validated_and_changes_content_identity(
    tmp_path: Path,
) -> None:
    """Built-in executable content participates in the frozen set identity."""
    root = tmp_path / "packs"
    root.mkdir()
    first = load_content_system(
        pack_roots=(root,),
        built_in_artifact_digest="a" * 64,
    )
    second = load_content_system(
        pack_roots=(root,),
        built_in_artifact_digest="b" * 64,
    )

    assert first.content_set_digest != second.content_set_digest
    with pytest.raises(ValueError, match="built_in_artifact_digest"):
        load_content_system(
            pack_roots=(root,),
            built_in_artifact_digest="not-a-sha256",
        )


def test_failed_import_restores_module_and_path_state_then_retry_is_fresh(
    tmp_path: Path,
) -> None:
    """A failed bootstrap leaves no cached pack code or installed import root."""
    root = tmp_path / "packs"
    root.mkdir()
    pack, _ = _write_fixture_pack(
        root,
        directory_name="retry",
        pack_id="fixture.retry",
        python_package="fixture_pack_retry",
        content_id="item.retry",
        import_failure=True,
    )
    python_root = str((pack / "src").resolve())
    assert python_root not in sys.path

    with pytest.raises(RuntimeError, match="fixture import failed"):
        load_content_system(
            pack_roots=(root,),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )
    assert python_root not in sys.path
    assert not any(
        name == "fixture_pack_retry"
        or name.startswith("fixture_pack_retry.")
        for name in sys.modules
    )

    items_path = pack / "src" / "fixture_pack_retry" / "items.py"
    items_path.write_text(
        items_path.read_text(encoding="utf-8").replace(
            "raise RuntimeError('fixture import failed')\n",
            "",
        ),
        encoding="utf-8",
    )
    loaded = load_content_system(
        pack_roots=(root,),
        built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
    )
    assert tuple(loaded.registry.declarations) == (
        "fixture.retry:item:item.retry@1",
    )


def test_cross_pack_import_requires_a_direct_manifest_dependency_before_import(
    tmp_path: Path,
) -> None:
    """Static imports cannot bypass the pack dependency contract."""
    root = tmp_path / "packs"
    root.mkdir()
    _, alpha_marker = _write_fixture_pack(
        root,
        directory_name="alpha",
        pack_id="fixture.alpha_importer",
        python_package="fixture_pack_alpha_importer",
        content_id="item.alpha_importer",
        dependencies=(("fixture.beta_dependency", "1"),),
        extra_imports=("import fixture_pack_gamma_transitive",),
    )
    _, beta_marker = _write_fixture_pack(
        root,
        directory_name="beta",
        pack_id="fixture.beta_dependency",
        python_package="fixture_pack_beta_dependency",
        content_id="item.beta_dependency",
        dependencies=(("fixture.gamma_transitive", "1"),),
    )
    _, gamma_marker = _write_fixture_pack(
        root,
        directory_name="gamma",
        pack_id="fixture.gamma_transitive",
        python_package="fixture_pack_gamma_transitive",
        content_id="item.gamma_transitive",
    )

    with pytest.raises(ValueError, match="direct manifest dependency"):
        load_content_system(
            pack_roots=(root,),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )
    assert not alpha_marker.exists()
    assert not beta_marker.exists()
    assert not gamma_marker.exists()

    alpha_items = (
        root
        / "alpha"
        / "src"
        / "fixture_pack_alpha_importer"
        / "items.py"
    )
    alpha_items.write_text(
        alpha_items.read_text(encoding="utf-8").replace(
            "import fixture_pack_gamma_transitive",
            "import fixture_pack_beta_dependency",
        ),
        encoding="utf-8",
    )
    loaded = load_content_system(
        pack_roots=(root,),
        built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
    )
    assert set(loaded.registry.declarations) == {
        "fixture.alpha_importer:item:item.alpha_importer@1",
        "fixture.beta_dependency:item:item.beta_dependency@1",
        "fixture.gamma_transitive:item:item.gamma_transitive@1",
    }


def test_pack_dependency_cycle_is_rejected_before_any_pack_executes(
    tmp_path: Path,
) -> None:
    """Dependency cycles fail during the cold bootstrap phase."""
    root = tmp_path / "packs"
    root.mkdir()
    _, alpha_marker = _write_fixture_pack(
        root,
        directory_name="alpha",
        pack_id="fixture.cycle_alpha",
        python_package="fixture_pack_cycle_alpha",
        content_id="item.cycle_alpha",
        dependencies=(("fixture.cycle_beta", "1"),),
    )
    _, beta_marker = _write_fixture_pack(
        root,
        directory_name="beta",
        pack_id="fixture.cycle_beta",
        python_package="fixture_pack_cycle_beta",
        content_id="item.cycle_beta",
        dependencies=(("fixture.cycle_alpha", "1"),),
    )

    with pytest.raises(ValueError, match="dependency cycle"):
        load_content_system(
            pack_roots=(root,),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )
    assert not alpha_marker.exists()
    assert not beta_marker.exists()


def test_mutation_after_discovery_is_rejected_before_pack_executes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovery identity is compared with a fresh pre-import pack hash."""
    root = tmp_path / "packs"
    root.mkdir()
    pack, marker = _write_fixture_pack(
        root,
        directory_name="mutating",
        pack_id="fixture.mutating",
        python_package="fixture_pack_mutating",
        content_id="item.mutating",
    )
    items_path = pack / "src" / "fixture_pack_mutating" / "items.py"
    real_hash = pack_loader._hash_pack_directory
    hash_calls = 0

    def mutate_after_discovery(pack_directory: Path) -> str:
        nonlocal hash_calls
        digest = real_hash(pack_directory)
        hash_calls += 1
        if hash_calls == 2:
            items_path.write_text(
                items_path.read_text(encoding="utf-8") + "\n# changed\n",
                encoding="utf-8",
            )
        return digest

    monkeypatch.setattr(
        pack_loader,
        "_hash_pack_directory",
        mutate_after_discovery,
    )
    with pytest.raises(RuntimeError, match="after discovery"):
        load_content_system(
            pack_roots=(root,),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )
    assert not marker.exists()


@pytest.mark.parametrize(
    ("forbidden_source", "message"),
    (
        (
            "def hidden_import() -> None:\n"
            "    import dnd.actions\n",
            "function-local import",
        ),
        (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    import dnd.actions\n",
            "TYPE_CHECKING",
        ),
        (
            "import typing as typing_alias\n"
            "if typing_alias.TYPE_CHECKING:\n"
            "    import dnd.actions\n",
            "TYPE_CHECKING",
        ),
        (
            "__import__('dnd.actions')\n",
            "dynamic import",
        ),
        (
            "import importlib as importlib_alias\n"
            "importlib_alias.import_module('dnd.actions')\n",
            "dynamic import",
        ),
        (
            "from importlib import import_module as load_module\n"
            "load_module('dnd.actions')\n",
            "dynamic import",
        ),
        (
            "from importlib.util import spec_from_file_location\n"
            "_DYNAMIC_SPEC = spec_from_file_location('hidden_pack', __file__)\n",
            "dynamic code",
        ),
        (
            "from importlib import util as loader_util\n"
            "_DYNAMIC_SPEC = loader_util.spec_from_file_location("
            "'hidden_pack', __file__)\n",
            "dynamic code",
        ),
        (
            "import importlib as loader_module\n"
            "_DYNAMIC_IMPORT = loader_module.import_module\n",
            "dynamic code",
        ),
        (
            "from importlib.machinery import SourceFileLoader\n"
            "_DYNAMIC_LOADER = SourceFileLoader\n",
            "dynamic code",
        ),
        (
            "import runpy as runner\n"
            "_DYNAMIC_RUNNER = runner.run_path\n",
            "dynamic code",
        ),
        (
            "exec('DYNAMIC_PACK_VALUE = 1')\n",
            "dynamic code",
        ),
        (
            "_DYNAMIC_PACK_VALUE = eval('1 + 1')\n",
            "dynamic code",
        ),
        (
            "_DYNAMIC_CODE = compile('value = 1', '<pack>', 'exec')\n",
            "dynamic code",
        ),
        (
            "from builtins import exec as execute\n"
            "execute('DYNAMIC_PACK_VALUE = 1')\n",
            "dynamic code",
        ),
    ),
)
def test_forbidden_pack_import_mechanisms_fail_before_any_pack_executes(
    tmp_path: Path,
    forbidden_source: str,
    message: str,
) -> None:
    """Packs cannot conceal dependencies behind runtime-only import mechanisms."""
    root = tmp_path / "packs"
    root.mkdir()
    pack, marker = _write_fixture_pack(
        root,
        directory_name="forbidden",
        pack_id="fixture.forbidden_import",
        python_package="fixture_pack_forbidden_import",
        content_id="item.forbidden_import",
    )
    _replace_fixture_extra_import(
        pack,
        "fixture_pack_forbidden_import",
        forbidden_source,
    )

    with pytest.raises(ValueError, match=message):
        load_content_system(
            pack_roots=(root,),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )
    assert not marker.exists()


def test_transitive_upward_dnd_import_fails_before_any_pack_executes(
    tmp_path: Path,
) -> None:
    """A locally imported engine module cannot conceal a composition edge."""
    root = tmp_path / "packs"
    root.mkdir()
    pack, marker = _write_fixture_pack(
        root,
        directory_name="transitive_upward",
        pack_id="fixture.transitive_upward",
        python_package="fixture_pack_transitive_upward",
        content_id="item.transitive_upward",
    )
    _replace_fixture_extra_import(
        pack,
        "fixture_pack_transitive_upward",
        "import dnd.maps.arena_layout",
    )

    with pytest.raises(ValueError, match="transitively reaches forbidden"):
        load_content_system(
            pack_roots=(root,),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )
    assert not marker.exists()


def test_dependency_leaf_and_entity_imports_remain_supported(
    tmp_path: Path,
) -> None:
    """Ordinary item and creature authoring surfaces remain legal imports."""
    root = tmp_path / "packs"
    root.mkdir()
    pack, marker = _write_fixture_pack(
        root,
        directory_name="authoring_surfaces",
        pack_id="fixture.authoring_surfaces",
        python_package="fixture_pack_authoring_surfaces",
        content_id="item.authoring_surfaces",
    )
    _replace_fixture_extra_import(
        pack,
        "fixture_pack_authoring_surfaces",
        "from dnd.blocks.base_item import BaseItem\n"
        "from dnd.entity import Entity",
    )

    loaded = load_content_system(
        pack_roots=(root,),
        built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
    )
    assert marker.read_text(encoding="utf-8") == "imported"
    assert tuple(loaded.registry.declarations) == (
        "fixture.authoring_surfaces:item:item.authoring_surfaces@1",
    )


@pytest.mark.parametrize(
    "forbidden_source",
    (
        "import ai.evaluation.arena_manifest",
        "import custom_ai.tactical",
        "import server.event_server",
        "import dnd.ai.runtime.controller",
        "from server import event_server",
        "import dnd.content_system.bootstrap",
        "from dnd.content_system import runtime",
        "from dnd.content_system.pack_loader import load_content_system",
        "import dnd.content_system.import_boundary",
        "from dnd import runtime_reset",
        "import dnd.scenarios",
    ),
)
def test_forbidden_upward_pack_imports_fail_before_any_pack_executes(
    tmp_path: Path,
    forbidden_source: str,
) -> None:
    """External definitions cannot reach server or startup composition roots."""
    root = tmp_path / "packs"
    root.mkdir()
    pack, marker = _write_fixture_pack(
        root,
        directory_name="upward",
        pack_id="fixture.upward_import",
        python_package="fixture_pack_upward_import",
        content_id="item.upward_import",
    )
    _replace_fixture_extra_import(
        pack,
        "fixture_pack_upward_import",
        forbidden_source,
    )

    with pytest.raises(ValueError, match="forbidden composition dependency"):
        load_content_system(
            pack_roots=(root,),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )
    assert not marker.exists()


def test_live_engine_object_rejects_pack_before_import_without_mutation(
    tmp_path: Path,
) -> None:
    """External pack loading is a cold-start operation, never a live reload."""
    root = tmp_path / "packs"
    root.mkdir()
    _, marker = _write_fixture_pack(
        root,
        directory_name="live_runtime",
        pack_id="fixture.live_runtime",
        python_package="fixture_pack_live_runtime",
        content_id="item.live_runtime",
    )
    object_uuid = UUID("20000000-0000-0000-0000-000000000001")
    nested_state = {"turn": {"actions": ["attack"]}}
    live_object = BaseObject(
        uuid=object_uuid,
        source_entity_uuid=object_uuid,
        context=nested_state,
    )
    registry_identity = id(BaseObject._registry)
    context_identity = id(live_object.context)
    inner_identity = id(nested_state["turn"])

    try:
        with pytest.raises(RuntimeError, match="cold engine runtime"):
            load_content_system(
                pack_roots=(root,),
                built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
            )
        assert not marker.exists()
        assert id(BaseObject._registry) == registry_identity
        assert BaseObject._registry[object_uuid] is live_object
        assert id(live_object.context) == context_identity
        assert live_object.context is not None
        assert id(live_object.context["turn"]) == inner_identity
        assert live_object.context == nested_state
    finally:
        BaseObject._registry.pop(object_uuid, None)


def test_equal_content_runtime_container_replacement_is_detected_and_restored(
    tmp_path: Path,
) -> None:
    """Replacing an empty protected registry is still a runtime mutation."""
    root = tmp_path / "packs"
    root.mkdir()
    pack, _ = _write_fixture_pack(
        root,
        directory_name="container_replacement",
        pack_id="fixture.container_replacement",
        python_package="fixture_pack_container_replacement",
        content_id="item.container_replacement",
    )
    _replace_fixture_extra_import(
        pack,
        "fixture_pack_container_replacement",
        "from dnd.core.base_object import BaseObject\n"
        "BaseObject._registry = dict(BaseObject._registry)",
    )
    original_registry = BaseObject._registry
    assert not original_registry

    try:
        with pytest.raises(RuntimeError, match="mutated engine runtime state"):
            load_content_system(
                pack_roots=(root,),
                built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
            )
        assert BaseObject._registry is original_registry
        assert not original_registry
    finally:
        BaseObject._registry = original_registry
        original_registry.clear()


@pytest.mark.parametrize(
    ("import_failure", "expected_error"),
    (
        (False, "mutated engine runtime state"),
        (True, "fixture import failed"),
    ),
)
def test_top_level_runtime_mutations_abort_and_restore_every_registry(
    tmp_path: Path,
    import_failure: bool,
    expected_error: str,
) -> None:
    """Pack imports are transactional with respect to live engine registries."""
    root = tmp_path / "packs"
    root.mkdir()
    pack, _ = _write_fixture_pack(
        root,
        directory_name="runtime_mutation",
        pack_id="fixture.runtime_mutation",
        python_package="fixture_pack_runtime_mutation",
        content_id="item.runtime_mutation",
        import_failure=import_failure,
    )
    _replace_fixture_extra_import(
        pack,
        "fixture_pack_runtime_mutation",
        "\n".join(
            (
                "from uuid import UUID",
                "from dnd.core.base_object import BaseObject",
                "from dnd.core.events import EventQueue",
                "from dnd.entity import Entity",
                "_RUNTIME_OBJECT = BaseObject(",
                f"    uuid=UUID({str(_MUTATED_OBJECT_UUID)!r}),",
                f"    source_entity_uuid=UUID({str(_MUTATED_OBJECT_UUID)!r}),",
                ")",
                f"Entity._entity_registry[UUID({str(_MUTATED_ENTITY_UUID)!r})] = _RUNTIME_OBJECT",
                "Entity._entity_by_position[(99, 99)].append(_RUNTIME_OBJECT)",
                f"EventQueue._event_handlers[UUID({str(_MUTATED_HANDLER_UUID)!r})] = _RUNTIME_OBJECT",
                f"EventQueue._event_handlers_by_source_entity_uuid[UUID({str(_MUTATED_OBJECT_UUID)!r})].append(_RUNTIME_OBJECT)",
            ),
        ),
    )
    before = _runtime_registry_identity()

    with pytest.raises((RuntimeError, ValueError), match=expected_error):
        load_content_system(
            pack_roots=(root,),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )

    assert _runtime_registry_identity() == before
    assert _MUTATED_OBJECT_UUID not in BaseObject._registry
    assert _MUTATED_ENTITY_UUID not in Entity._entity_registry
    assert (99, 99) not in Entity._entity_by_position
    assert _MUTATED_HANDLER_UUID not in EventQueue._event_handlers
    assert (
        _MUTATED_OBJECT_UUID
        not in EventQueue._event_handlers_by_source_entity_uuid
    )


def test_relative_package_imports_remain_supported(tmp_path: Path) -> None:
    """Ordinary static relative imports are resolved and execute normally."""
    root = tmp_path / "packs"
    root.mkdir()
    pack, marker = _write_fixture_pack(
        root,
        directory_name="relative",
        pack_id="fixture.relative_import",
        python_package="fixture_pack_relative_import",
        content_id="item.relative_import",
    )
    package = _package_directory(pack, "fixture_pack_relative_import")
    (package / "helpers.py").write_text(
        "FIXTURE_VALUE = 7\n",
        encoding="utf-8",
    )
    _replace_fixture_extra_import(
        pack,
        "fixture_pack_relative_import",
        "from .helpers import FIXTURE_VALUE",
    )

    loaded = load_content_system(
        pack_roots=(root,),
        built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
    )
    assert marker.read_text(encoding="utf-8") == "imported"
    assert tuple(loaded.registry.declarations) == (
        "fixture.relative_import:item:item.relative_import@1",
    )


def test_relative_internal_import_cycle_fails_before_pack_execution(
    tmp_path: Path,
) -> None:
    """Every pack module graph must be acyclic before any module executes."""
    root = tmp_path / "packs"
    root.mkdir()
    pack, marker = _write_fixture_pack(
        root,
        directory_name="module_cycle",
        pack_id="fixture.module_cycle",
        python_package="fixture_pack_module_cycle",
        content_id="item.module_cycle",
    )
    package = _package_directory(pack, "fixture_pack_module_cycle")
    (package / "left.py").write_text(
        "from . import right\n",
        encoding="utf-8",
    )
    (package / "right.py").write_text(
        "from . import left\n",
        encoding="utf-8",
    )
    _replace_fixture_extra_import(
        pack,
        "fixture_pack_module_cycle",
        "from . import left",
    )

    with pytest.raises(ValueError, match="Python import cycle"):
        load_content_system(
            pack_roots=(root,),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )
    assert not marker.exists()


def test_relative_import_cannot_escape_to_an_undeclared_pack(
    tmp_path: Path,
) -> None:
    """Resolved imports cannot reach another installed pack without a direct edge."""
    root = tmp_path / "packs"
    root.mkdir()
    importer, importer_marker = _write_fixture_pack(
        root,
        directory_name="importer",
        pack_id="fixture.relative_importer",
        python_package="fixture_namespace.relative_importer",
        content_id="item.relative_importer",
    )
    _, dependency_marker = _write_fixture_pack(
        root,
        directory_name="dependency",
        pack_id="fixture.relative_dependency",
        python_package="fixture_namespace.relative_dependency",
        content_id="item.relative_dependency",
    )
    _replace_fixture_extra_import(
        importer,
        "fixture_namespace.relative_importer",
        "from ..relative_dependency import create_fixture_item",
    )

    with pytest.raises(ValueError, match="direct manifest dependency"):
        load_content_system(
            pack_roots=(root,),
            built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
        )
    assert not importer_marker.exists()
    assert not dependency_marker.exists()


def test_successive_loads_reusing_a_python_package_do_not_share_import_roots(
    tmp_path: Path,
) -> None:
    """Successful bootstraps release temporary roots without breaking factories."""
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first_pack, first_marker = _write_fixture_pack(
        first_root,
        directory_name="first_pack",
        pack_id="fixture.sequential_first",
        python_package="fixture_pack_reused",
        content_id="item.sequential_first",
    )
    second_pack, second_marker = _write_fixture_pack(
        second_root,
        directory_name="second_pack",
        pack_id="fixture.sequential_second",
        python_package="fixture_pack_reused",
        content_id="item.sequential_second",
    )
    first_python_root = str((first_pack / "src").resolve())
    second_python_root = str((second_pack / "src").resolve())

    first = load_content_system(
        pack_roots=(first_root,),
        built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
    )
    assert first_marker.exists()
    assert first_python_root not in sys.path

    second = load_content_system(
        pack_roots=(second_root,),
        built_in_artifact_digest=_BUILT_IN_ARTIFACT_DIGEST,
    )
    assert second_marker.exists()
    assert second_python_root not in sys.path
    assert tuple(first.registry.declarations) == (
        "fixture.sequential_first:item:item.sequential_first@1",
    )
    assert tuple(second.registry.declarations) == (
        "fixture.sequential_second:item:item.sequential_second@1",
    )

    first_declaration = next(iter(first.registry.declarations.values()))
    first_recipe = ContentRecipe.create(
        ref=first_declaration.ref,
        parameters={"charges": 11},
    )
    first_context = object()
    assert first.registry.materialize(
        first_recipe,
        first_context,
    ) == (first_context, 11)
