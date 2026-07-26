"""Import reviewed NeuroClient icon evidence into exact ContentRef ledgers.

Runtime content composition never reads NeuroClient.  This offline importer
pins one manifest, reduces its legacy evidence to reviewed exact identities,
and writes the only data consumed by the engine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from dnd.content_system import builtin_inventory
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.recipe_presets import ContentRecipePreset


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET_INDEX_PATH = (
    REPOSITORY_ROOT
    / "content_data"
    / "ledgers"
    / "neuroclient_game_icon_asset_index.json"
)
DEFAULT_BINDING_LEDGER_PATH = (
    REPOSITORY_ROOT
    / "content_data"
    / "ledgers"
    / "content_icon_bindings.json"
)
DEFAULT_GENERATED_BINDINGS_PATH = (
    REPOSITORY_ROOT
    / "dnd"
    / "core"
    / "content"
    / "icon_bindings_generated.py"
)
EXPECTED_MANIFEST_SHA256 = (
    "c154feeea3803fe3c023c7a89d4bf71cdc13624e2f6adf2be3429d4315815bea"
)
EXPECTED_MANIFEST_ASSET_COUNT = 455
EXPECTED_MANIFEST_SCHEMA_VERSION = 3
EXPECTED_STYLE_ID = "fantasy-classic-v1"


_HUMAN_REVIEWED_BINDINGS = {
    # Definition identity owns the selected authored inventory asset.
    (
        "content.neurodragon:item:"
        "apparel.travelers_clothes@1"
    ): "item.traveler-s-clothes",
    (
        "content.neurodragon:item:"
        "apparel.wizard_hat@1"
    ): "item.wizard-s-hat",
    "content.srd_5_1_cc:item:armor.splint@1": "item.splint-armor",
    "content.srd_5_1_cc:item:armor.plate@1": "item.plate-armor",
    "content.srd_5_1_cc:item:armor.leather@1": "item.leather-armor",
    "content.srd_5_1_cc:item:armor.hide@1": "item.hide-armor",
    (
        "content.srd_5_1_cc:action:"
        "action.class.barbarian.reckless_attack@1"
    ): "action.reckless-attack",
    (
        "content.srd_5_1_cc:reaction:"
        "reaction.spell.counterspell@1"
    ): "reaction.counterspell",
    # Exact environment definitions/actions with dedicated authored assets.
    (
        "content.neurodragon:environment_object:"
        "environment.directional_door@1"
    ): "object.directional-door",
    (
        "content.neurodragon:environment_object:"
        "environment.directional_wall@1"
    ): "object.directional-wall",
    (
        "content.neurodragon:action:"
        "action.environment.directional_door.open@1"
    ): "action.open-door",
    (
        "content.neurodragon:action:"
        "action.environment.directional_door.close@1"
    ): "action.close-door",
    (
        "content.neurodragon:action:"
        "action.environment.door.open@1"
    ): "action.open-door",
    (
        "content.neurodragon:action:"
        "action.environment.door.close@1"
    ): "action.close-door",
    (
        "content.neurodragon:action:"
        "action.environment.wall_torch.ignite@1"
    ): "action.light-wall-torch",
    (
        "content.neurodragon:action:"
        "action.environment.wall_torch.extinguish@1"
    ): "action.extinguish-wall-torch",
    (
        "content.neurodragon:action:"
        "action.environment.trap_lever.pull@1"
    ): "action.pull-lever",
    (
        "content.neurodragon:action:"
        "action.environment.storage_chest.loot_all@1"
    ): "action.loot-all",
    (
        "content.neurodragon:action:"
        "action.environment.campfire.cook@1"
    ): "action.cook",
    (
        "content.neurodragon:action:"
        "action.environment.campfire.rest@1"
    ): "action.rest",
    (
        "content.neurodragon:action:"
        "action.environment.arcane_device.activate@1"
    ): "action.activate-device",
    # Exact intrinsic creature equipment assets.
    (
        "content.srd_5_1_cc:item:"
        "armor.creature.wolf_natural@1"
    ): "item.natural-armor",
    (
        "content.srd_5_1_cc:item:"
        "armor.creature.dire_wolf_natural@1"
    ): "item.natural-armor",
    (
        "content.srd_5_1_cc:item:"
        "weapon.creature.wolf_bite@1"
    ): "item.bite",
    (
        "content.srd_5_1_cc:item:"
        "weapon.creature.dire_wolf_bite@1"
    ): "item.bite",
    (
        "content.srd_5_1_cc:item:"
        "weapon.creature.ghoul_bite@1"
    ): "item.bite",
    (
        "content.srd_5_1_cc:item:"
        "weapon.creature.ghoul_claws@1"
    ): "item.claws",
    (
        "content.srd_5_1_cc:item:"
        "weapon.creature.zombie_slam@1"
    ): "item.slam",
    # Four authored coat definitions and their exact elemental states.
    (
        "content.neurodragon:item:"
        "consumable.weapon_coat.fire@1"
    ): "item.weapon-coat-of-flame",
    (
        "content.neurodragon:item:"
        "consumable.weapon_coat.concentration_fire@1"
    ): "item.weapon-coat-of-flame",
    (
        "content.neurodragon:item:"
        "consumable.weapon_coat.timed_fire@1"
    ): "item.weapon-coat-of-flame",
    (
        "content.neurodragon:item:"
        "consumable.weapon_coat.lightning@1"
    ): "item.weapon-coat-of-lightning",
    (
        "content.neurodragon:condition:"
        "condition.consumable.weapon_coat.fire@1"
    ): "item.weapon-coat-of-flame",
    (
        "content.neurodragon:condition:"
        "condition.consumable.weapon_coat.concentration_fire@1"
    ): "item.weapon-coat-of-flame",
    (
        "content.neurodragon:condition:"
        "condition.consumable.weapon_coat.timed_fire@1"
    ): "item.weapon-coat-of-flame",
    (
        "content.neurodragon:condition:"
        "condition.consumable.weapon_coat.lightning@1"
    ): "item.weapon-coat-of-lightning",
    (
        "content.neurodragon:action:"
        "action.item.weapon_coat.apply@1"
    ): "item.weapon-coat",
    (
        "content.neurodragon:item:"
        "weapon.assassin_dagger@1"
    ): "item.dagger",
    (
        "content.neurodragon:item:"
        "weapon.circus.rusty_dagger@1"
    ): "item.dagger",
    (
        "content.neurodragon:item:"
        "weapon.circus.flaming_scimitar@1"
    ): "item.scimitar",
    (
        "content.neurodragon:item:"
        "weapon.circus.longsword_plus_one@1"
    ): "item.longsword",
    (
        "content.neurodragon:item:"
        "weapon.circus.soul_draining_morningstar@1"
    ): "item.morningstar",
}


_HUMAN_REVIEWED_TRAIT_REUSES = {
    "trait.brave": (
        "condition.dnd-monsters-traits-conditionalsaveadvantagefeature"
    ),
    "trait.dark_devotion": (
        "condition.dnd-monsters-traits-conditionalsaveadvantagefeature"
    ),
    "trait.brute": "condition.dnd-monsters-traits-bonusdamagefeature",
    "trait.martial_advantage": (
        "condition.dnd-monsters-traits-bonusdamagefeature"
    ),
    "trait.sneak_attack": (
        "condition.dnd-monsters-traits-bonusdamagefeature"
    ),
    "trait.surprise_attack": (
        "condition.dnd-monsters-traits-bonusdamagefeature"
    ),
    "trait.keen_hearing_and_sight": (
        "condition.dnd-monsters-traits-keenperceptionfeature"
    ),
    "trait.keen_hearing_and_smell": (
        "condition.dnd-monsters-traits-keenperceptionfeature"
    ),
    "trait.dire_wolf_bite_prone": (
        "condition.dnd-monsters-traits-hitsaveriderfeature"
    ),
    "trait.wolf_bite_prone": (
        "condition.dnd-monsters-traits-hitsaveriderfeature"
    ),
}


_EVIDENCE_KIND_MAP = {
    "currently_authored_valid": "authored_presentation",
    "manifest_backend_spell_catalog_id": "backend_spell_catalog",
    "manifest_condition_declaration_type": "backend_condition_class",
    "manifest_runtime_declaration_type": "runtime_action_class",
    "manifest_contextual_source_and_display": "contextual_action",
    "manifest_backend_item_catalog_id": "backend_item_catalog",
    "authored_item_category_exact_runtime_row": "runtime_item_class",
    "manifest_backend_environment_catalog_id": (
        "backend_environment_catalog"
    ),
}
_INTENTIONAL_DYNAMIC_PROVIDER_IDENTITIES = frozenset({
    "core.rules:action:action.attack@1",
    "content.srd_5_1_cc:action:action.monster.multiattack@1",
})


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _write_or_check(path: Path, payload: dict[str, Any], *, check: bool) -> None:
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"generated artifact is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def _write_or_check_text(path: Path, rendered: str, *, check: bool) -> None:
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"generated artifact is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def _manifest_identity(
    manifest_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    icons = manifest.get("icons")
    if not isinstance(icons, list):
        raise ValueError("NeuroClient icon manifest lacks an icons list")
    style = manifest.get("style")
    if not isinstance(style, dict):
        raise ValueError("NeuroClient icon manifest lacks style identity")
    identity = {
        "sha256": digest,
        "schema_version": manifest.get("schema_version"),
        "style_id": style.get("style_id"),
        "asset_count": len(icons),
    }
    expected = {
        "sha256": EXPECTED_MANIFEST_SHA256,
        "schema_version": EXPECTED_MANIFEST_SCHEMA_VERSION,
        "style_id": EXPECTED_STYLE_ID,
        "asset_count": EXPECTED_MANIFEST_ASSET_COUNT,
    }
    if identity != expected:
        raise ValueError(
            f"NeuroClient icon manifest identity mismatch: {identity!r}",
        )
    return identity


def _asset_rows(manifest: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in manifest["icons"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("asset"), dict):
            raise ValueError("malformed icon manifest asset row")
        digest = raw["asset"].get("digest")
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise ValueError("icon manifest asset lacks a SHA-256 digest")
        rows.append({
            "icon_key": raw["icon_key"],
            "asset_sha256": digest.removeprefix("sha256:"),
            "asset_path": raw["asset"]["path"],
        })
    rows.sort(key=lambda row: row["icon_key"])
    if len({row["icon_key"] for row in rows}) != len(rows):
        raise ValueError("NeuroClient icon manifest has duplicate keys")
    return rows


def _unbound_content() -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    return (
        tuple(builtin_inventory.BUILT_IN_DECLARATION_INVENTORY),
        tuple(builtin_inventory.BUILT_IN_RECIPE_PRESET_INVENTORY),
    )


def _audit_rows_by_identity(
    audit_path: Path,
    manifest_identity: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    audit = _read_json(audit_path)
    source = audit.get("source")
    if not isinstance(source, dict):
        raise ValueError("icon audit lacks source identity")
    expected = {
        "manifest_sha256": manifest_identity["sha256"],
        "manifest_schema_version": manifest_identity["schema_version"],
        "style_id": manifest_identity["style_id"],
        "asset_count": manifest_identity["asset_count"],
    }
    actual = {
        key: source.get(key)
        for key in expected
    }
    if actual != expected:
        raise ValueError("icon audit targets another source manifest")
    rows = audit.get("definitions")
    if not isinstance(rows, list):
        raise ValueError("icon audit lacks definition rows")
    return {row["identity"]: row for row in rows}


def _first_selected_evidence(
    audit_row: dict[str, Any],
) -> tuple[str, str]:
    selected_key = audit_row["selected_icon_key"]
    candidates = tuple(
        candidate
        for candidate in audit_row["candidates"]
        if candidate["icon_key"] == selected_key
    )
    if len(candidates) != 1 or not candidates[0]["evidence"]:
        raise ValueError(
            f"selected audit row lacks unique evidence: {audit_row['identity']}",
        )
    evidence = candidates[0]["evidence"][0]
    return _EVIDENCE_KIND_MAP[evidence["kind"]], evidence["token"]


def _definition_rows_from_audit(
    *,
    audit_path: Path,
    manifest_identity: dict[str, Any],
    assets_by_key: dict[str, dict[str, str]],
    declarations: tuple[Any, ...],
) -> list[dict[str, Any]]:
    audit_rows = _audit_rows_by_identity(audit_path, manifest_identity)
    public_declarations = tuple(
        declaration
        for declaration in declarations
        if declaration.descriptor.visibility == ContentVisibility.PUBLIC
    )
    if set(audit_rows) != {
        declaration.ref.identity_key
        for declaration in public_declarations
    }:
        raise ValueError("icon audit does not match public built-in closure")

    rows: list[dict[str, Any]] = []
    for declaration in sorted(
        public_declarations,
        key=lambda value: value.ref.identity_key,
    ):
        identity = declaration.ref.identity_key
        audit_row = audit_rows[identity]
        manual_key = _HUMAN_REVIEWED_BINDINGS.get(identity)
        if (
            manual_key is None
            and declaration.ref.content_id in _HUMAN_REVIEWED_TRAIT_REUSES
        ):
            manual_key = _HUMAN_REVIEWED_TRAIT_REUSES[
                declaration.ref.content_id
            ]
        selected_key = manual_key or audit_row["selected_icon_key"]
        if selected_key is not None:
            asset = assets_by_key.get(selected_key)
            if asset is None:
                raise ValueError(
                    f"reviewed binding names unknown asset {selected_key!r}",
                )
            if manual_key is not None:
                evidence_kind = "human_reviewed"
                evidence_token = (
                    "reviewed_content_ref_to_manifest_asset:"
                    f"{identity}->{selected_key}"
                )
            else:
                evidence_kind, evidence_token = _first_selected_evidence(
                    audit_row,
                )
            rows.append({
                "content_ref": declaration.ref.model_dump(mode="json"),
                "decision": "bind",
                "icon_key": selected_key,
                "asset_sha256": asset["asset_sha256"],
                "evidence_kind": evidence_kind,
                "evidence_token": evidence_token,
            })
            continue
        if identity in _INTENTIONAL_DYNAMIC_PROVIDER_IDENTITIES:
            decision = "intentional_null"
            evidence_kind = "intentional_dynamic_provider"
            evidence_token = f"provider_attributed_runtime_icon:{identity}"
        elif declaration.ref.definition_kind.value == "creature":
            decision = "intentional_null"
            evidence_kind = "intentional_non_icon_presentation"
            evidence_token = f"portrait_sprite_owned_presentation:{identity}"
        elif audit_row["status"] == "ambiguous":
            decision = "ambiguous"
            evidence_kind = "unresolved_ambiguous"
            evidence_token = f"review_required:{identity}:ambiguous"
        else:
            decision = "missing_asset"
            evidence_kind = "unresolved_uncovered"
            evidence_token = f"new_asset_required:{identity}"
        rows.append({
            "content_ref": declaration.ref.model_dump(mode="json"),
            "decision": decision,
            "icon_key": None,
            "asset_sha256": None,
            "evidence_kind": evidence_kind,
            "evidence_token": evidence_token,
        })
    _apply_exact_provider_icon_inheritance(
        rows=rows,
        declarations=public_declarations,
    )
    return rows


def _apply_exact_provider_icon_inheritance(
    *,
    rows: list[dict[str, Any]],
    declarations: tuple[Any, ...],
) -> None:
    """Bind provider-owned targets only through exact dependency edges."""
    rows_by_identity = {
        (
            f"{row['content_ref']['pack_id']}:"
            f"{row['content_ref']['definition_kind']}:"
            f"{row['content_ref']['content_id']}@"
            f"{row['content_ref']['content_version']}"
        ): row
        for row in rows
    }
    providers_by_target: dict[
        str,
        list[tuple[str, Any, dict[str, Any]]],
    ] = {}
    for declaration in declarations:
        provider_row = rows_by_identity[declaration.ref.identity_key]
        for dependency in declaration.dependencies:
            if dependency.relation.value not in {
                "grants_action",
                "creates_object",
            }:
                continue
            target_row = rows_by_identity.get(dependency.target_ref.identity_key)
            if (
                target_row is None
                or target_row["content_ref"]
                != dependency.target_ref.model_dump(mode="json")
            ):
                raise ValueError(
                    "grants_action dependency targets an unbound declaration: "
                    f"{dependency.target_ref.identity_key}",
                )
            providers_by_target.setdefault(
                dependency.target_ref.identity_key,
                [],
            ).append((
                dependency.relation.value,
                declaration,
                provider_row,
            ))

    for target_identity, providers in providers_by_target.items():
        target = rows_by_identity[target_identity]
        if target["decision"] == "bind":
            continue
        if any(row["decision"] != "bind" for _, _, row in providers):
            continue
        presentations = {
            (row["icon_key"], row["asset_sha256"])
            for _, _, row in providers
        }
        if len(presentations) != 1:
            continue
        icon_key, asset_sha256 = presentations.pop()
        if icon_key is None or asset_sha256 is None:
            raise ValueError("bound provider lacks its authenticated asset")
        provider_identities = tuple(sorted(
            declaration.ref.identity_key
            for _, declaration, _ in providers
        ))
        relations = tuple(sorted({
            relation
            for relation, _, _ in providers
        }))
        target.update({
            "decision": "bind",
            "icon_key": icon_key,
            "asset_sha256": asset_sha256,
            "evidence_kind": "content_dependency",
            "evidence_token": (
                "+".join(relations)
                + ":"
                + ",".join(provider_identities)
                + f"->{target_identity}"
            ),
        })


def _definition_rows_from_existing(
    *,
    existing: dict[str, Any],
    declarations: tuple[Any, ...],
) -> list[dict[str, Any]]:
    rows = existing.get("definitions")
    if not isinstance(rows, list):
        raise ValueError("existing icon ledger lacks definition rows")
    public = tuple(
        declaration
        for declaration in declarations
        if declaration.descriptor.visibility == ContentVisibility.PUBLIC
    )
    refs_by_identity = {
        declaration.ref.identity_key: declaration.ref.model_dump(mode="json")
        for declaration in public
    }
    rows_by_identity = {
        (
            f"{row['content_ref']['pack_id']}:"
            f"{row['content_ref']['definition_kind']}:"
            f"{row['content_ref']['content_id']}@"
            f"{row['content_ref']['content_version']}"
        ): row
        for row in rows
    }
    if rows_by_identity.keys() != refs_by_identity.keys():
        raise ValueError("existing icon ledger public closure is stale")
    normalized: list[dict[str, Any]] = []
    for identity in sorted(refs_by_identity):
        row = dict(rows_by_identity[identity])
        if row["content_ref"] != refs_by_identity[identity]:
            raise ValueError(
                f"existing icon ledger ContentRef is stale: {identity}",
            )
        normalized.append(row)
    return normalized


def _bound_preset_hash(
    preset: Any,
    icon_key: str | None,
) -> str:
    presentation = ContentPresentation.model_validate({
        **preset.descriptor.presentation.model_dump(mode="python"),
        "icon_key": icon_key,
    })
    descriptor = ContentDescriptorSpec.model_validate({
        **preset.descriptor.model_dump(mode="python"),
        "presentation": presentation,
    })
    bound = ContentRecipePreset.create(
        pack_id=preset.ref.pack_id,
        preset_id=preset.ref.preset_id,
        preset_version=preset.ref.preset_version,
        recipe=preset.recipe,
        descriptor=descriptor,
        provenance=preset.provenance,
    )
    return bound.ref.preset_contract_hash


def _preset_rows(
    *,
    presets: tuple[Any, ...],
    definition_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    definitions_by_identity = {
        (
            f"{row['content_ref']['pack_id']}:"
            f"{row['content_ref']['definition_kind']}:"
            f"{row['content_ref']['content_id']}@"
            f"{row['content_ref']['content_version']}"
        ): row
        for row in definition_rows
    }
    rows: list[dict[str, Any]] = []
    for preset in sorted(
        presets,
        key=lambda value: value.ref.identity_key,
    ):
        inherited = definitions_by_identity.get(
            preset.recipe.ref.identity_key,
        )
        if inherited is None or inherited["content_ref"] != (
            preset.recipe.ref.model_dump(mode="json")
        ):
            raise ValueError(
                "preset recipe target lacks an exact public icon disposition: "
                f"{preset.ref.identity_key}",
            )
        icon_key = inherited["icon_key"]
        bound_contract_hash = _bound_preset_hash(
            preset,
            icon_key,
        )
        bound_ref = preset.ref.model_dump(mode="json")
        bound_ref["preset_contract_hash"] = bound_contract_hash
        rows.append({
            "preset_ref": bound_ref,
            "inherit_definition_ref": preset.recipe.ref.model_dump(mode="json"),
            "bound_preset_contract_hash": bound_contract_hash,
            "decision": inherited["decision"],
            "icon_key": icon_key,
            "asset_sha256": inherited["asset_sha256"],
            "evidence_kind": "inherit_definition",
            "evidence_token": preset.recipe.ref.identity_key,
        })
    return rows


def _build_outputs(
    *,
    manifest_path: Path,
    audit_path: Path | None,
    existing_ledger_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _read_json(manifest_path)
    manifest_identity = _manifest_identity(manifest_path, manifest)
    asset_rows = _asset_rows(manifest)
    assets_by_key = {
        row["icon_key"]: row
        for row in asset_rows
    }
    asset_index_digest = _canonical_digest(asset_rows)
    declarations, presets = _unbound_content()
    if audit_path is not None:
        definition_rows = _definition_rows_from_audit(
            audit_path=audit_path,
            manifest_identity=manifest_identity,
            assets_by_key=assets_by_key,
            declarations=declarations,
        )
    else:
        definition_rows = _definition_rows_from_existing(
            existing=_read_json(existing_ledger_path),
            declarations=declarations,
        )
    for row in definition_rows:
        icon_key = row["icon_key"]
        if icon_key is None:
            if row["asset_sha256"] is not None:
                raise ValueError("unresolved binding retains an asset digest")
            continue
        asset = assets_by_key.get(icon_key)
        if asset is None or asset["asset_sha256"] != row["asset_sha256"]:
            raise ValueError(
                f"icon binding asset is stale: {row['content_ref']!r}",
            )
    preset_rows = _preset_rows(
        presets=presets,
        definition_rows=definition_rows,
    )
    asset_index = {
        "schema_version": 1,
        "source_manifest": manifest_identity,
        "asset_index_digest": asset_index_digest,
        "assets": asset_rows,
    }
    binding_digest = _canonical_digest({
        "definitions": definition_rows,
        "recipe_presets": preset_rows,
    })
    ledger = {
        "schema_version": 1,
        "source_manifest": manifest_identity,
        "asset_index_digest": asset_index_digest,
        "binding_digest": binding_digest,
        "definitions": definition_rows,
        "recipe_presets": preset_rows,
    }
    return asset_index, ledger


def _render_generated_bindings(ledger: dict[str, Any]) -> str:
    lines = [
        '"""Generated exact built-in ContentRef-to-icon bindings.',
        "",
        "Regenerate with "
        "``devtools/import_neuroclient_content_icon_bindings.py``.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "",
        "# exact identity_key#definition_contract_hash ->",
        "# (definition_contract_hash, disposition, icon_key, asset_sha256)",
        "BUILT_IN_CONTENT_ICON_BINDINGS: dict[",
        "    str,",
        "    tuple[str, str, str | None, str | None],",
        "] = {",
    ]
    for row in ledger["definitions"]:
        ref = row["content_ref"]
        identity = (
            f"{ref['pack_id']}:{ref['definition_kind']}:"
            f"{ref['content_id']}@{ref['content_version']}"
        )
        contract_hash = ref["definition_contract_hash"]
        lines.extend([
            f"    {identity + '#' + contract_hash!r}: (",
            f"        {contract_hash!r},",
            f"        {row['decision']!r},",
            f"        {row['icon_key']!r},",
            f"        {row['asset_sha256']!r},",
            "    ),",
        ])
    lines.extend(["}", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--audit-source",
        type=Path,
        help="One reviewed machine audit used only to seed a migration.",
    )
    parser.add_argument(
        "--asset-index-output",
        type=Path,
        default=DEFAULT_ASSET_INDEX_PATH,
    )
    parser.add_argument(
        "--binding-ledger-output",
        type=Path,
        default=DEFAULT_BINDING_LEDGER_PATH,
    )
    parser.add_argument(
        "--generated-bindings-output",
        type=Path,
        default=DEFAULT_GENERATED_BINDINGS_PATH,
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    asset_index, ledger = _build_outputs(
        manifest_path=args.manifest.resolve(strict=True),
        audit_path=(
            args.audit_source.resolve(strict=True)
            if args.audit_source is not None
            else None
        ),
        existing_ledger_path=args.binding_ledger_output,
    )
    _write_or_check(
        args.asset_index_output,
        asset_index,
        check=args.check,
    )
    _write_or_check(
        args.binding_ledger_output,
        ledger,
        check=args.check,
    )
    _write_or_check_text(
        args.generated_bindings_output,
        _render_generated_bindings(ledger),
        check=args.check,
    )


if __name__ == "__main__":
    main()
