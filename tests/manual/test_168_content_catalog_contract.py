"""Safe installed-content manifest and descriptor catalog contracts."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.content.registration import ContentDeclarationMode
from server.content_catalog import (
    ContentCatalogResponse,
    build_content_manifest,
    build_public_content_catalog,
    content_response_etag,
)
from server.event_server import app


_EXPECTED_FRONTEND_ICON_KEYS = {
    "action.class.sorcerer.convert_slot_to_sorcery_points": (
        "action.convert-slot-to-sorcery-points"
    ),
    "action.class.sorcerer.convert_sorcery_points_to_slot": (
        "action.convert-sorcery-points-to-slot"
    ),
    "action.class.sorcerer.quickened_spell": "action.quickened-spell",
    "action.class.sorcerer.twinned_spell": "action.twinned-spell",
    "consumable.healing_potion": "item.potion-of-healing",
    "consumable.potion_haste": "item.potion-of-haste",
    "equipment.portable_torch": "item.torch",
    "reaction.opportunity_attack": "reaction.opportunity-attack-handler",
    "reaction.spell.shield": "reaction.shield",
    "spell.burning_hands": "spell.burning-hands",
    "spell.lightning_bolt": "spell.lightning-bolt",
}


def test_content_manifest_exposes_sources_and_deployment_digest() -> None:
    """Standalone, gateway, and workers publish one built-in identity."""
    loaded = bootstrap_content_system()
    manifest = build_content_manifest(loaded)

    assert manifest.content_set_digest == loaded.content_set_digest
    assert manifest.built_in_artifact_digest == loaded.built_in_artifact_digest
    assert tuple(source.source_id for source in manifest.sources) == (
        "neurodragon.original_b2b3930",
        "wotc.srd_5_1_cc",
    )
    assert content_response_etag(manifest.content_set_digest) == (
        f'"{loaded.content_set_digest}"'
    )


def test_public_catalog_is_complete_code_free_and_self_authenticating() -> None:
    """The authoring surface contains descriptors/schemas, never Python factories."""
    loaded = bootstrap_content_system()
    catalog = build_public_content_catalog(loaded)
    expected_public_refs = {
        declaration.ref.identity_key
        for declaration in loaded.registry.declarations.values()
        if declaration.descriptor.visibility == ContentVisibility.PUBLIC
    }

    assert catalog.content_set_digest == loaded.content_set_digest
    assert len(catalog.catalog_digest) == 64
    assert {entry.ref.identity_key for entry in catalog.entries} == (
        expected_public_refs
    )
    assert catalog.entries
    for entry in catalog.entries:
        assert entry.visibility == ContentVisibility.PUBLIC
        if entry.definition_mode == ContentDeclarationMode.FACTORY:
            assert entry.parameter_schema is not None
            assert entry.parameter_schema["additionalProperties"] is False
            if entry.ref.definition_kind == ContentDefinitionKind.ITEM:
                assert entry.item_definition is not None
                assert entry.item_definition.persistence_policy in {
                    ItemPersistencePolicy.POSSESSION,
                    ItemPersistencePolicy.INTRINSIC,
                }
            elif (
                entry.ref.definition_kind
                == ContentDefinitionKind.ENVIRONMENT_OBJECT
            ):
                assert entry.item_definition is not None
                assert entry.item_definition.persistence_policy in {
                    ItemPersistencePolicy.ENVIRONMENT,
                    ItemPersistencePolicy.ENCOUNTER_ONLY,
                }
            else:
                assert entry.item_definition is None
        elif (
            entry.definition_mode
            == ContentDeclarationMode.BEHAVIOR_IDENTITY
        ):
            assert (
                entry.definition_mode
                == ContentDeclarationMode.BEHAVIOR_IDENTITY
            )
            assert entry.runtime_behavior_kind is not None
            assert entry.item_definition is None
            assert entry.parameter_schema is None
        else:
            assert (
                entry.definition_mode
                == ContentDeclarationMode.TYPED_DEFINITION
            )
            assert entry.ref.definition_kind in {
                ContentDefinitionKind.ACTION,
                ContentDefinitionKind.CLASS,
                ContentDefinitionKind.SUBCLASS,
                ContentDefinitionKind.SPECIES,
                ContentDefinitionKind.SPECIES_VARIANT,
                ContentDefinitionKind.BACKGROUND,
                ContentDefinitionKind.STARTING_EQUIPMENT_PACKAGE,
                ContentDefinitionKind.TRAIT,
            }
            assert entry.runtime_behavior_kind is None
            assert entry.item_definition is None
            assert entry.parameter_schema is None

    encoded = catalog.model_dump_json()
    assert "__module__" not in encoded
    assert '"factory":' not in encoded
    assert '"python_path":' not in encoded
    assert '"source_module":' not in encoded
    assert "dnd.items." not in encoded
    assert ContentCatalogResponse.model_validate_json(encoded) == catalog


def test_reported_player_content_uses_exact_frontend_manifest_icon_keys() -> None:
    """Authored icon keys are exact assets, never content-ID fallbacks."""
    catalog = build_public_content_catalog(bootstrap_content_system())
    entries_by_content_id = {
        entry.ref.content_id: entry
        for entry in catalog.entries
    }

    assert {
        content_id: entries_by_content_id[content_id].presentation.icon_key
        for content_id in _EXPECTED_FRONTEND_ICON_KEYS
    } == _EXPECTED_FRONTEND_ICON_KEYS


def test_catalog_digest_rejects_descriptor_or_schema_tampering() -> None:
    """A client cannot silently merge descriptors from another code/content set."""
    catalog = build_public_content_catalog(bootstrap_content_system())
    payload = json.loads(catalog.model_dump_json())
    payload["entries"][0]["display_name"] = "Tampered"

    with pytest.raises(ValidationError, match="catalog_digest"):
        ContentCatalogResponse.model_validate(payload)


def test_standalone_content_routes_share_identity_and_honor_etags() -> None:
    """The public HTTP surface has one unversioned manifest/catalog path."""
    loaded = SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())

    async def request(
        path: str,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://content.test",
        ) as client:
            return await client.get(path, headers=headers)

    manifest_response = asyncio.run(request("/content/manifest"))
    catalog_response = asyncio.run(request("/content/catalog"))

    assert manifest_response.status_code == 200
    assert catalog_response.status_code == 200
    assert manifest_response.json()["content_set_digest"] == (
        loaded.content_set_digest
    )
    assert catalog_response.json()["content_set_digest"] == (
        loaded.content_set_digest
    )
    manifest_etag = manifest_response.headers["etag"]
    catalog_etag = catalog_response.headers["etag"]
    assert manifest_etag == content_response_etag(loaded.content_set_digest)
    assert catalog_etag == content_response_etag(
        catalog_response.json()["catalog_digest"],
    )

    not_modified_manifest = asyncio.run(request(
        "/content/manifest",
        {"If-None-Match": manifest_etag},
    ))
    not_modified_catalog = asyncio.run(request(
        "/content/catalog",
        {"If-None-Match": catalog_etag},
    ))
    assert not_modified_manifest.status_code == 304
    assert not_modified_catalog.status_code == 304
    assert not_modified_manifest.content == b""
    assert not_modified_catalog.content == b""

    route_paths = {
        path
        for route in app.routes
        if isinstance((path := getattr(route, "path", None)), str)
    }
    assert "/content/manifest" in route_paths
    assert "/content/catalog" in route_paths
    assert not any(path.startswith("/content/v") for path in route_paths)
