"""Admit the accepted sensory delivery into the existing support media bundle.

Copies unchanged source pixels and media registrations only. Spell/condition
recipes are authored separately. Original 144 Hz banks remain in their archive.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from pydantic import TypeAdapter

from devtools.media_delivery import contained_media_path

from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


ROOT = Path(__file__).resolve().parents[1]


def import_sensory(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT) -> dict:
    manifest = json.loads((source / "delivery-manifest.json").read_text())
    source_bindings = json.loads((source / "bindings.json").read_text())
    source_assets = json.loads((source / "projectile-assets.json").read_text())
    TypeAdapter(list[AuthoredProjectileAsset]).validate_json(json.dumps(source_assets))
    TypeAdapter(dict[str, ProjectileStorage]).validate_json(json.dumps(source_bindings["projectileStorage"]))
    if source_bindings.get("spells") or set(source_bindings) != {"resources", "spells", "projectileStorage"}:
        raise ValueError("Sensory delivery must contain media only")
    if len(source_assets) != 12 or len(manifest) != 27:
        raise ValueError("Expected the accepted twelve-bank, twenty-seven-file delivery")
    payloads = {}
    for row in manifest:
        relative = row["file"]
        origin = contained_media_path(source / "payload", relative)
        if not origin.is_relative_to((source / "payload/game/assets/sensory_spells").resolve()):
            raise ValueError(f"Invalid sensory payload path: {relative}")
        data = origin.read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError(f"Sensory payload checksum mismatch: {relative}")
        payloads[relative] = origin
        for target in (contained_media_path(repo, relative), contained_media_path(production, relative),
                       contained_media_path(preserved / "payload", relative)):
            if target.exists() and (not target.is_file() or target.read_bytes() != data):
                raise ValueError(f"Refusing to overwrite different sensory bytes: {target}")
    metadata = [(origin, contained_media_path(preserved, origin.name)) for origin in source.iterdir()
                if origin.is_file() and origin.suffix in (".json", ".md")]
    for origin, target in metadata:
        if target.exists() and target.read_bytes() != origin.read_bytes():
            raise ValueError(f"Archived sensory metadata differs: {origin.name}")
    bundle = repo / "game/data/support_conditions"
    bindings = json.loads((bundle / "bindings.json").read_text())
    assets = {row["assetId"]: row for row in json.loads((bundle / "projectile-assets.json").read_text())}
    for field in ("resources", "projectileStorage"):
        for key, value in source_bindings[field].items():
            existing = bindings.setdefault(field, {}).get(key)
            if existing is not None and existing != value:
                raise ValueError(f"Conflicting sensory registration: {key}")
            bindings[field][key] = value
    for row in source_assets:
        existing = assets.get(row["assetId"])
        if existing is not None and existing != row:
            raise ValueError(f"Conflicting sensory asset: {row['assetId']}")
        assets[row["assetId"]] = row
    manifest_path = production / "art-manifest.json"
    previous = manifest_path.read_bytes()
    private = json.loads(previous)
    installed = {row["path"]: row for row in private["files"]}
    preserved.mkdir(parents=True, exist_ok=True)
    if not (preserved / "previous-art-manifest.json").exists():
        (preserved / "previous-art-manifest.json").write_bytes(previous)
    for origin, target in metadata:
        shutil.copyfile(origin, target)
    for row in manifest:
        relative = row["file"]
        for target in (contained_media_path(repo, relative), contained_media_path(production, relative),
                       contained_media_path(preserved / "payload", relative)):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(payloads[relative], target)
        installed[relative] = {"path": relative, "bytes": row["bytes"], "sha256": row["sha256"]}
    private["files"] = sorted(installed.values(), key=lambda row: row["path"])
    private["total_bytes"] = sum(row["bytes"] for row in private["files"])
    manifest_path.write_text(json.dumps(private, indent=2) + "\n")
    (bundle / "bindings.json").write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    (bundle / "projectile-assets.json").write_text(json.dumps(list(assets.values()), separators=(",", ":")) + "\n")
    receipt = {"source": str(source), "preserved": str(preserved),
        "source_manifest_sha256": hashlib.sha256((source / "delivery-manifest.json").read_bytes()).hexdigest(),
        "identities": [row["assetId"] for row in source_assets],
        "files": [installed[row["file"]] for row in manifest]}
    (bundle / "sensory-source.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (preserved / "install-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--preserved", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    args = parser.parse_args()
    receipt = import_sensory(args.source, preserved=args.preserved, production=args.production)
    print(f"Installed {len(receipt['identities'])} media records / {len(receipt['files'])} unchanged files")
