"""Authenticated built-in content-to-icon bindings."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path
from uuid import uuid4

import pytest

from dnd.actions import Move
from dnd.blocks.equipment import Weapon
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
from dnd.content_system.item_bindings import (
    ItemRuntimeBindingRegistry,
    ItemRuntimeOrigin,
)
from dnd.content_system.item_materialization import materialize_item
from dnd.content_system.runtime import ContentSystemRuntime
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
from dnd.items.weapons import CLUB_RECIPE
from dnd.reactions import create_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime


_ROOT = Path(__file__).resolve().parents[2]


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
    assert len(all_identities) == len(set(all_identities)) == 517
    assert len(public_declarations) == 509
    assert len(BUILT_IN_DECLARATIONS) - len(public_declarations) == 8
    assert Counter(
        row.decision.value
        for row in BUILT_IN_CONTENT_ICON_BINDING_LEDGER.definitions
    ) == {
        "bind": 444,
        "intentional_null": 42,
        "missing_asset": 23,
    }
    rows_by_identity = {
        row.content_ref.identity_key: row
        for row in BUILT_IN_CONTENT_ICON_BINDING_LEDGER.definitions
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
        assert row.content_ref == declaration.ref
        icon_key = declaration.descriptor.presentation.icon_key
        assert icon_key == row.icon_key
        if icon_key is None:
            assert row.asset_sha256 is None
        else:
            assert assets_by_key[icon_key].asset_sha256 == row.asset_sha256


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN_ISSUES: Public content catalog has 23 unauthored "
        "game-icon assets"
    ),
)
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


def test_recipe_preset_icon_rows_authenticate_bound_presets() -> None:
    """Preset inheritance is exact and its recomputed descriptor hash is pinned."""
    rows_by_identity = {
        row.preset_ref.identity_key: row
        for row in BUILT_IN_CONTENT_ICON_BINDING_LEDGER.recipe_presets
    }

    assert set(rows_by_identity) == {
        preset.ref.identity_key
        for preset in BUILT_IN_RECIPE_PRESETS
    }
    assert Counter(
        row.decision.value
        for row in BUILT_IN_CONTENT_ICON_BINDING_LEDGER.recipe_presets
    ) == {
        "bind": 165,
        "missing_asset": 40,
    }
    for preset in BUILT_IN_RECIPE_PRESETS:
        row = rows_by_identity[preset.ref.identity_key]
        assert preset.ref.preset_contract_hash == row.bound_preset_contract_hash
        assert preset.recipe.ref == row.inherit_definition_ref
        assert preset.descriptor.presentation.icon_key == row.icon_key


def test_provider_owned_actions_inherit_only_exact_dependency_assets() -> None:
    """Item-use icons follow authenticated GRANTS_ACTION edges, never names."""
    expected = {
        "action.item.potion_healing.drink": "item.potion-of-healing",
        "action.item.potion_haste.drink": "item.potion-of-haste",
        "action.item.potion_greater_invisibility.drink": (
            "item.potion-of-greater-invisibility"
        ),
        "action.item.torch.ignite": "item.torch",
        "action.item.torch.extinguish": "item.torch",
    }
    declarations_by_content_id = {
        declaration.ref.content_id: declaration
        for declaration in BUILT_IN_DECLARATIONS
    }
    rows_by_identity = {
        row.content_ref.identity_key: row
        for row in BUILT_IN_CONTENT_ICON_BINDING_LEDGER.definitions
    }

    for action_content_id, icon_key in expected.items():
        action = declarations_by_content_id[action_content_id]
        row = rows_by_identity[action.ref.identity_key]
        assert action.descriptor.presentation.icon_key == icon_key
        assert row.evidence_kind.value == "content_dependency"
        providers = tuple(
            declaration
            for declaration in BUILT_IN_DECLARATIONS
            if any(
                dependency.relation.value == "grants_action"
                and dependency.target_ref == action.ref
                for dependency in declaration.dependencies
            )
        )
        assert providers
        assert {
            provider.descriptor.presentation.icon_key
            for provider in providers
        } == {icon_key}
        assert all(
            provider.ref.identity_key in row.evidence_token
            for provider in providers
        )


def test_missing_or_unknown_public_binding_row_fails_closed() -> None:
    def remove_first(payload: dict[str, object]) -> None:
        definitions = payload["definitions"]
        assert isinstance(definitions, list)
        definitions.pop(0)

    with pytest.raises(ValueError, match="closure mismatch"):
        _validate_with(_validated_tampered_ledger(remove_first))

    def replace_with_unknown(payload: dict[str, object]) -> None:
        definitions = payload["definitions"]
        assert isinstance(definitions, list)
        row = definitions[0]
        assert isinstance(row, dict)
        ref = row["content_ref"]
        assert isinstance(ref, dict)
        ref["content_id"] = "action.fixture.unknown_icon_owner"

    with pytest.raises(ValueError, match="closure mismatch"):
        _validate_with(_validated_tampered_ledger(replace_with_unknown))


def test_stale_definition_contract_or_asset_fails_closed() -> None:
    def stale_contract(payload: dict[str, object]) -> None:
        definitions = payload["definitions"]
        assert isinstance(definitions, list)
        row = definitions[0]
        assert isinstance(row, dict)
        ref = row["content_ref"]
        assert isinstance(ref, dict)
        ref["definition_contract_hash"] = "0" * 64

    with pytest.raises(ValueError, match="content contract is stale"):
        _validate_with(_validated_tampered_ledger(stale_contract))

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


def test_preset_inheritance_or_bound_hash_tampering_fails_closed() -> None:
    def wrong_inheritance(payload: dict[str, object]) -> None:
        presets = payload["recipe_presets"]
        definitions = payload["definitions"]
        assert isinstance(presets, list)
        assert isinstance(definitions, list)
        row = presets[0]
        other = next(
            value
            for value in definitions
            if value["content_ref"] != row["inherit_definition_ref"]
        )
        row["inherit_definition_ref"] = other["content_ref"]
        ref = other["content_ref"]
        row["evidence_token"] = (
            f"{ref['pack_id']}:{ref['definition_kind']}:"
            f"{ref['content_id']}@{ref['content_version']}"
        )
        row["decision"] = other["decision"]
        row["icon_key"] = other["icon_key"]
        row["asset_sha256"] = other["asset_sha256"]

    with pytest.raises(ValueError, match="disagrees with recipe"):
        _validate_with(_validated_tampered_ledger(wrong_inheritance))

    def wrong_bound_hash(payload: dict[str, object]) -> None:
        presets = payload["recipe_presets"]
        assert isinstance(presets, list)
        presets[0]["bound_preset_contract_hash"] = "0" * 64

    with pytest.raises(ValueError, match="bound contract hash is stale"):
        _validate_with(_validated_tampered_ledger(wrong_bound_hash))


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


def test_original_declaration_identity_survives_runtime_binding_and_item_build() -> None:
    """Descriptor binding never replaces decorated declaration objects."""
    reset_engine_runtime(grid_size=(4, 4))
    loaded = bootstrap_content_system(pack_roots=())
    binder = BehaviorBinder(loaded.registry)
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
        assert behavior.behavior_binding.definition_ref == declaration.ref

    runtime = ContentSystemRuntime()
    runtime.install(loaded)
    bindings = ItemRuntimeBindingRegistry()
    club = materialize_item(
        CLUB_RECIPE,
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
        binding_registry=bindings,
        runtime=runtime,
    )
    club_declaration = loaded.registry.resolve_factory(CLUB_RECIPE.ref)
    assert club_declaration.construction is not None
    assert get_content_declaration(
        club_declaration.construction.factory,
    ) is club_declaration
    assert loaded.registry.resolve_definition(
        club_declaration.ref,
    ) is club_declaration
    assert club.content_ref == club_declaration.ref
    reset_engine_runtime()
