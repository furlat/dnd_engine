"""Preserve accepted weather/solar deliveries and register their unchanged crops."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image

from devtools.import_registered_media import DIRECTIONS, validate_billboard_bank
from devtools.media_delivery import contained_media_path, install_verified_payloads
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


ROOT = Path(__file__).resolve().parents[1]


def import_weather_solar(source: Path, program: str, *, preserved: Path,
                         production: Path, repo: Path = ROOT) -> dict:
    """Import one exact delivery; selected recipes are never rewritten."""
    if program not in ("ice", "sleet", "solar"):
        raise ValueError("Select ice, sleet or solar")
    metadata_name = "manifest.json" if program == "solar" else "media.json"
    manifest = json.loads((source / metadata_name).read_text())
    approval = json.loads((source / "approval.json").read_text())
    if approval["revision"] != {"ice": "textured-fracture-v3", "sleet": "soft-ground-contact-v5",
                                "solar": "solar-lifecycle-v1"}[program]:
        raise ValueError("Delivery does not match the accepted revision")
    if program == "ice":
        banks = manifest
        if set(banks) != {"ground0", "ground1", "ground2", "ground3", "contact0", "contact1"}:
            raise ValueError("Ice Storm requires its six original modules")
        if any(row["revision"] != "textured-fracture-v3" or row["frames"] != 96
               or row["fragmentCount"] != 8 for row in banks.values()):
            raise ValueError("Unexpected Ice Storm source revision")
    elif program == "sleet":
        banks = {"storm": manifest}
        if manifest["frames"] != 128 or manifest["phases"] != {
                "develop": [0, 32], "hold": [32, 96], "remove": [96, 128]}:
            raise ValueError("Unexpected Sleet Storm phase windows")
    else:
        banks = manifest["banks"]
        if manifest["revision"] != "solar-lifecycle-v1" or set(banks) != {
                *(f"beam-{index}" for index in range(8)), "burst-back", "burst-front"}:
            raise ValueError("Unexpected solar delivery")
    media_root = f"game/assets/weather_solar_media/{program}"
    assets, storage, payloads = {}, {}, {}
    dimensions = {}

    def parts(row, layer, first, count):
        result = []
        for frame in layer["frames"][first:first + count]:
            if frame is None:
                result.append([])
                continue
            relative = layer["pages"][frame["page"]]
            origin = contained_media_path(source, relative)
            if relative not in dimensions:
                with Image.open(origin) as picture:
                    if picture.mode != "RGBA":
                        raise ValueError("Accepted media must retain RGBA")
                    dimensions[relative] = picture.size
            x, y, width, height = frame["source"]
            if x + width > dimensions[relative][0] or y + height > dimensions[relative][1]:
                raise ValueError("Registered crop leaves original atlas")
            digest = row["sha256"][relative]
            if relative in payloads and payloads[relative][2] != digest:
                raise ValueError("One source page has conflicting checksums")
            payloads[relative] = (relative, f"{media_root}/{relative}", digest)
            result.append([{"file": f"{media_root}/{relative}", "rect": frame["source"],
                            "offset": frame["offset"]}])
        return result

    def register(identity, row, layers, first, count, *, loop=False, height=None):
        views = {facing: parts(row, layers[index], first, count) for index, facing in enumerate(DIRECTIONS)}
        cell, h = row["cell"], height or row["cell"]
        assets[identity] = {"assetId": identity, "displayName": identity, "kind": "projectile",
            "sheet": f"/{identity}.png", "frame": {"width": cell, "height": h, "rows": 8, "cols": count},
            "fps": 32, "rowOrder": list(DIRECTIONS), "phases": {"impact": {
                "start": 0, "frames": count, "fps": 32, "loop": loop}},
            "anchor": {"x": row["pivot"][0] / cell, "y": row["pivot"][1] / h},
            "defaultScale": 1, "palettePreview": {"colors": [0x56869f] if program != "solar" else [0xf7d366]}}
        storage[identity] = {"phases": {"impact": {"layers": [{"partsByFacing": views, "blendMode": "normal"}]}}}

    if program in ("ice", "sleet"):
        for name, row in banks.items():
            expected_layers = {"back", "front"} if program == "ice" else {"ground", "back", "front"}
            if set(row["layers"]) != expected_layers:
                raise ValueError("Delivery is missing an authored camera layer")
            for side, layer in row["layers"].items():
                validate_billboard_bank(dict(row, palette=["56869f"], layers={"front": layer}), paired=False)
                windows = (("fall", 0, 96, False), ("settled", 95, 1, True)) if program == "ice" else (
                    ("apply", 0, 32, False), ("hold", 32, 64, True), ("remove", 96, 32, False))
                for phase, first, count, loop in windows:
                    register(f"weather.{program}.{name}.{phase}.{side}", row, [layer] * 8, first, count, loop=loop)
    else:
        def solar_row(row):
            layer = {"pages": [row["file"]], "frames": [dict(frame, page=0) for frame in row["frames"]]}
            bank = dict(row, cell=512, frames=row["count"], sha256={row["file"]: row["sha256"]},
                        palette=["f7d366"], layers={"front": layer})
            validate_billboard_bank(bank, paired=False)
            return bank, layer
        directions = [solar_row(banks[f"beam-{index}"]) for index in range(8)]
        beam = dict(directions[0][0], sha256={row["file"]: row["sha256"] for row in banks.values()})
        # Native heading zero is world +X; the host calls that projected row SE.
        register("solar.sunbeam", beam, [directions[(index-1) % 8][1] for index in range(8)], 0, 48, height=384)
        for side in ("back", "front"):
            bank, layer = solar_row(banks[f"burst-{side}"])
            register(f"solar.sunburst.{side}", bank, [layer] * 8, 0, 64, height=384)
    for row in assets.values():
        AuthoredProjectileAsset.model_validate_json(json.dumps(row))
    for row in storage.values():
        ProjectileStorage.model_validate_json(json.dumps(row))
    bundle = repo / "game/data/weather_solar_media"
    binding_path, asset_path = bundle / "bindings.json", bundle / "projectile-assets.json"
    bindings = json.loads(binding_path.read_text()) if binding_path.exists() else {"resources": {}, "spells": {}}
    registered = {row["assetId"]: row for row in json.loads(asset_path.read_text())} if asset_path.exists() else {}
    # Preflight the full preserved delivery, including operators and validation;
    # a broken/missing metadata file must not leave a partial media installation.
    originals = []
    for origin in sorted(source.rglob("*")):
        if origin.is_dir():
            continue
        relative = origin.relative_to(source).as_posix()
        checked = contained_media_path(source, relative)
        target = contained_media_path(preserved, relative)
        digest = hashlib.sha256(checked.read_bytes()).hexdigest()
        if target.exists() and (not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest):
            raise ValueError(f"Preserved original differs: {relative}")
        originals.append((checked, target, {"path": relative, "sha256": digest}))
    files = install_verified_payloads(source, tuple(payloads.values()), preserved=preserved,
        production=production, repo=repo)
    for origin, target, _ in originals:
        target.parent.mkdir(parents=True, exist_ok=True)
        if origin != target:
            shutil.copyfile(origin, target)
    bindings.setdefault("projectileStorage", {}).update(storage)
    registered.update(assets)
    bundle.mkdir(parents=True, exist_ok=True)
    binding_path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    asset_path.write_text(json.dumps(list(registered.values()), separators=(",", ":")) + "\n")
    receipt = {"source": str(source), "preserved": str(preserved), "approval": approval,
        "metadata_sha256": hashlib.sha256((source / metadata_name).read_bytes()).hexdigest(),
        "identities": list(assets), "files": files, "originals": [row for _, _, row in originals],
        "camera_registration": "Source-authored camera-relative banks; no additional views or pixels generated."}
    (bundle / f"{program}-source.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--program", choices=("ice", "sleet", "solar"), required=True)
    parser.add_argument("--preserved", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    args = parser.parse_args()
    result = import_weather_solar(args.source, args.program, preserved=args.preserved, production=args.production)
    print(f"Registered {len(result['identities'])} media records and {len(result['files'])} unchanged pages")
