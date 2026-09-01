"""Authenticated built-in content-to-icon bindings."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from dnd.actions import Move
from dnd.conditions import Blinded
from dnd.content_system.behavior_bindings import BehaviorBinder
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin import (
    BUILT_IN_ARTIFACT_PATHS,
    BUILT_IN_DECLARATIONS,
    BUILT_IN_RECIPE_PRESETS,
)
from dnd.content_system.icon_bindings import (
    BUILT_IN_CONTENT_ICON_BINDING_LEDGER,
    CONTENT_ICON_BINDING_LEDGER_PATH,
    GAME_ICON_ASSET_INDEX_PATH,
    NEUROCLIENT_GAME_ICON_ASSET_INDEX,
    BuiltInContentIconBindingLedger,
    validate_builtin_content_icons,
)
from dnd.core.content.descriptors import (
    ContentDescriptor,
    ContentDescriptorSpec,
    ContentPresentation,
    ContentVisibility,
    resolve_content_icon_key,
)
from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
)
from dnd.core.content.registration import get_content_declaration
from dnd.reactions import create_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
_ROOT = Path(__file__).resolve().parents[2]
_RETIRED_ITEM_KINDS = {
    ContentDefinitionKind.ITEM,
    ContentDefinitionKind.ENVIRONMENT_OBJECT,
}


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
    ).hexdigest()


def test_icon_binding_importer_runs_directly_from_the_repository_root() -> None:
    """The documented offline CLI must own its repository import boundary."""
    completed = subprocess.run(
        [
            sys.executable,
            "devtools/import_neuroclient_content_icon_bindings.py",
            "--help",
        ],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=15.0,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "manifest" in completed.stdout


def _validated_tampered_ledger(
    mutate: object,
) -> BuiltInContentIconBindingLedger:
    payload = BUILT_IN_CONTENT_ICON_BINDING_LEDGER.model_dump(mode="json")
    assert callable(mutate)
    mutate(payload)
    payload["binding_digest"] = _canonical_digest({
        "definitions": payload["definitions"],
        "recipe_presets": payload["recipe_presets"],
    })
    return BuiltInContentIconBindingLedger.model_validate(payload)


def _validate_with(ledger: BuiltInContentIconBindingLedger) -> None:
    validate_builtin_content_icons(
        declarations=BUILT_IN_DECLARATIONS,
        recipe_presets=BUILT_IN_RECIPE_PRESETS,
        ledger=ledger,
        asset_index=NEUROCLIENT_GAME_ICON_ASSET_INDEX,
    )


def test_every_public_builtin_has_one_authenticated_icon_disposition() -> None:
    """Public rows bind an exact asset or explicitly disclose no icon."""
    all_identities = [
        declaration.ref.identity_key
        for declaration in BUILT_IN_DECLARATIONS
    ]
    public_declarations = tuple(
        declaration
        for declaration in BUILT_IN_DECLARATIONS
        if declaration.descriptor.visibility == ContentVisibility.PUBLIC
    )
    assert len(all_identities) == len(set(all_identities))
    assert {
        declaration.ref.identity_key for declaration in public_declarations
    } <= set(all_identities)
    rows_by_identity = {
        row.content_ref.identity_key: row
        for row in BUILT_IN_CONTENT_ICON_BINDING_LEDGER.definitions
        if row.content_ref.definition_kind not in _RETIRED_ITEM_KINDS
    }
    assets_by_key = {
        row.icon_key: row
        for row in NEUROCLIENT_GAME_ICON_ASSET_INDEX.assets
    }

    assert set(rows_by_identity) == {
        declaration.ref.identity_key
        for declaration in public_declarations
    }
    for declaration in public_declarations:
        row = rows_by_identity[declaration.ref.identity_key]
        icon_key = declaration.descriptor.presentation.icon_key
        assert icon_key == row.icon_key
        if icon_key is None:
            assert row.asset_sha256 is None
        else:
            assert assets_by_key[icon_key].asset_sha256 == row.asset_sha256


def test_every_public_builtin_has_no_unresolved_icon_assets() -> None:
    """Public catalog rows require an asset or a closed intentional omission."""
    public_identities = {
        declaration.ref.identity_key
        for declaration in BUILT_IN_DECLARATIONS
        if declaration.descriptor.visibility == ContentVisibility.PUBLIC
    }
    unresolved = tuple(
        row.content_ref.identity_key
        for row in BUILT_IN_CONTENT_ICON_BINDING_LEDGER.definitions
        if (
            row.content_ref.identity_key in public_identities
            and row.decision.value in {"missing_asset", "ambiguous"}
        )
    )

    assert unresolved == ()


def test_retired_item_preset_rows_are_evidence_only() -> None:
    """The active generic catalog owns no item recipe-preset authority."""
    assert BUILT_IN_RECIPE_PRESETS == ()
    assert all(
        row.inherit_definition_ref.definition_kind in _RETIRED_ITEM_KINDS
        for row in BUILT_IN_CONTENT_ICON_BINDING_LEDGER.recipe_presets
    )


def test_missing_or_unknown_public_binding_row_fails_closed() -> None:
    def remove_first(payload: dict[str, object]) -> None:
        definitions = payload["definitions"]
        assert isinstance(definitions, list)
        row_index = next(
            index
            for index, row in enumerate(definitions)
            if row["content_ref"]["definition_kind"]
            not in {"item", "environment_object"}
        )
        definitions.pop(row_index)

    with pytest.raises(ValueError, match="closure mismatch"):
        _validate_with(_validated_tampered_ledger(remove_first))

    def replace_with_unknown(payload: dict[str, object]) -> None:
        definitions = payload["definitions"]
        assert isinstance(definitions, list)
        row = next(
            value
            for value in definitions
            if value["content_ref"]["definition_kind"]
            not in {"item", "environment_object"}
        )
        assert isinstance(row, dict)
        ref = row["content_ref"]
        assert isinstance(ref, dict)
        ref["content_id"] = "action.fixture.unknown_icon_owner"

    with pytest.raises(ValueError, match="closure mismatch"):
        _validate_with(_validated_tampered_ledger(replace_with_unknown))


def test_missing_or_mismatched_icon_asset_fails_closed() -> None:
    def missing_asset(payload: dict[str, object]) -> None:
        definitions = payload["definitions"]
        assert isinstance(definitions, list)
        row = next(
            value
            for value in definitions
            if value["decision"] == "bind"
        )
        row["icon_key"] = "fixture.missing-asset"
        row["asset_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="missing or mismatched asset"):
        _validate_with(_validated_tampered_ledger(missing_asset))

    def mismatched_digest(payload: dict[str, object]) -> None:
        definitions = payload["definitions"]
        assert isinstance(definitions, list)
        row = next(
            value
            for value in definitions
            if value["decision"] == "bind"
        )
        row["asset_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="missing or mismatched asset"):
        _validate_with(_validated_tampered_ledger(mismatched_digest))


def test_external_pack_descriptor_keeps_its_authored_icon() -> None:
    """An unlisted external ContentRef never enters the built-in atlas ledger."""
    external_ref = ContentRef(
        pack_id="example.external_pack",
        definition_kind=ContentDefinitionKind.ACTION,
        content_id="action.clockwork_chime",
        content_version=1,
        definition_contract_hash="a" * 64,
    )
    authored = ContentDescriptorSpec(
        display_name="Clockwork Chime",
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(icon_key="external.clockwork-chime"),
    )

    assert resolve_content_icon_key(
        external_ref,
        authored.presentation.icon_key,
    ) == ("external.clockwork-chime", False)
    assert ContentDescriptor.from_spec(
        external_ref,
        authored,
    ).presentation.icon_key == "external.clockwork-chime"


def test_runtime_selection_uses_only_exact_generated_identity_rows() -> None:
    """Gameplay code cannot inspect legacy manifest evidence to select icons."""
    selector_source = inspect.getsource(resolve_content_icon_key)
    for forbidden in (
        "evidence",
        "manifest",
        "__module__",
        "display_name",
        "alias",
        "normalize",
    ):
        assert forbidden not in selector_source

    generated_source = (
        _ROOT
        / "dnd"
        / "core"
        / "content"
        / "icon_bindings_generated.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "/home/",
        "manifest_",
        "evidence",
        "class_name",
        "display_name",
        "aliases",
    ):
        assert forbidden not in generated_source

    assert GAME_ICON_ASSET_INDEX_PATH in BUILT_IN_ARTIFACT_PATHS
    assert CONTENT_ICON_BINDING_LEDGER_PATH in BUILT_IN_ARTIFACT_PATHS


def test_original_declaration_identity_survives_runtime_behavior_binding() -> None:
    """Descriptor binding never replaces decorated behavior declarations."""
    reset_engine_runtime(grid_size=(4, 4))
    loaded = bootstrap_content_system(pack_roots=())
    binder = BehaviorBinder(
        loaded.behavior_declarations_by_class,
        provider_only_behavior_ids=loaded.provider_only_behavior_ids,
    )
    owner_uuid = uuid4()

    move = Move(
        source_entity_uuid=owner_uuid,
        template=True,
        use_register=False,
    )
    blinded = Blinded(
        source_entity_uuid=owner_uuid,
        target_entity_uuid=owner_uuid,
        use_register=False,
    )
    opportunity = create_opportunity_attack_handler(owner_uuid)
    for behavior in (move, blinded, opportunity):
        declaration = get_content_declaration(type(behavior))
        assert loaded.registry.resolve_definition(
            declaration.ref,
        ) is declaration
        binder.bind_independent(
            behavior,
            runtime_owner_uuid=owner_uuid,
        )
        assert behavior.behavior_binding is not None
        assert behavior.behavior_binding.behavior_id == declaration.ref.content_id

    reset_engine_runtime()
