"""Cold manifest contracts for trusted installed content packs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dnd.core.content.pack_contracts import (
    ContentPackDependency,
    ContentPackManifest,
)
from dnd.core.content.provenance import (
    ContentSource,
    ContentSourceFamily,
    RulesBaseline,
)


_FIXTURE_SOURCE = ContentSource(
    source_id="fixture.pack_source",
    source_family=ContentSourceFamily.FIXTURE_INTERNAL,
    title="Fixture pack source",
    source_version="1",
    rules_baseline=RulesBaseline.ENGINE_NEUTRAL,
    license_id="INTERNAL-TEST",
    canonical_uri="https://example.invalid/fixture-pack",
    document_digest="f" * 64,
    attribution_text="Internal deterministic test fixture.",
)


def _manifest(**updates) -> ContentPackManifest:
    payload = {
        "schema_version": 1,
        "pack_id": "fixture.example_pack",
        "pack_version": "1.0.0",
        "engine_content_api": 1,
        "python_root": "src",
        "python_package": "example_pack",
        "assets_root": "assets",
        "dependencies": (
            ContentPackDependency(
                pack_id="engine.rules",
                version="1",
            ),
        ),
        "sources": (_FIXTURE_SOURCE,),
    }
    payload.update(updates)
    return ContentPackManifest(**payload)


def test_manifest_is_cold_normalized_and_dependency_order_independent() -> None:
    """Manifest identity is data-only and canonicalized before code import."""
    manifest = _manifest()
    assert manifest.pack_id == "fixture.example_pack"
    assert manifest.python_package == "example_pack"
    assert manifest.dependency_pack_ids == ("engine.rules",)
    assert len(manifest.contract_digest) == 64

    reordered = _manifest(
        dependencies=tuple(reversed(manifest.dependencies)),
        sources=tuple(reversed(manifest.sources)),
    )
    assert reordered.contract_digest == manifest.contract_digest


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("python_root", "../escape"),
        ("python_root", "/absolute"),
        ("python_root", "./src"),
        ("python_root", "src/"),
        ("python_root", "src//nested"),
        ("assets_root", "assets/../../escape"),
        ("assets_root", "./assets"),
        ("assets_root", "assets/"),
        ("python_package", "example-pack"),
        ("python_package", "ExamplePack"),
    ),
)
def test_manifest_rejects_escaping_paths_and_invalid_python_package(
    field_name: str,
    value: str,
) -> None:
    """Installed packs cannot escape their validated directory or import namespace."""
    with pytest.raises(ValidationError):
        _manifest(**{field_name: value})


def test_manifest_rejects_self_duplicate_dependency_and_source_contracts() -> None:
    """Dependency/source ambiguity fails before importing pack code."""
    with pytest.raises(ValidationError, match="depend on itself"):
        _manifest(
            dependencies=(
                ContentPackDependency(
                    pack_id="fixture.example_pack",
                    version="1",
                ),
            ),
        )
    duplicate_dependency = ContentPackDependency(
        pack_id="engine.rules",
        version="1",
    )
    with pytest.raises(ValidationError, match="Duplicate pack dependency"):
        _manifest(dependencies=(duplicate_dependency, duplicate_dependency))
    with pytest.raises(ValidationError, match="Duplicate content source"):
        _manifest(sources=(_FIXTURE_SOURCE, _FIXTURE_SOURCE))
