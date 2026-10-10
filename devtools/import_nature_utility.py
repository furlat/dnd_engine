"""Install compact-palm-v7 media and material sources; never copy fixture trajectories."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image
from pydantic import TypeAdapter

from devtools.import_registered_media import DIRECTIONS, register_billboard_bank, validate_billboard_bank
from devtools.media_delivery import contained_media_path, install_verified_payloads
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage

ROOT = Path(__file__).resolve().parents[1]


def import_flame_travel(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT) -> dict:
    """Pack original emitter-local frames, retaining all eight native headings."""
    bundle = repo / "game/data/support_conditions"
    bindings = json.loads((bundle / "bindings.json").read_text())
    assets = {row["assetId"]: row for row in json.loads((bundle / "projectile-assets.json").read_text())}
    banks = []
    originals = {}
    for heading in range(8):
        for side in ("back", "front"):
            folder = source / f"d{heading}" / side
            metadata = json.loads((folder / "source.json").read_text())
            capture = json.loads((folder / "capture.json").read_text())
            if (metadata["frames"] != 64 or metadata["fps"] != 32 or metadata["cell"] != [192, 192]
                    or metadata["pivot"] != [96, 96] or metadata["trail_seconds"] != .035
                    or metadata["spark_count"] != 9 or metadata["spark_lifetime"] != .1
                    or len(capture["captured"]) != 64
                    or hashlib.sha256((folder / "adapter.gd").read_bytes()).hexdigest() != metadata["adapter_sha256"]):
                raise ValueError(f"Incompatible source travel capture: {folder}")
            frames = []
            for index, tick in enumerate(capture["captured"]):
                if tick["actual_tick"] != tick["target_tick"]:
                    raise ValueError(f"Source capture has the wrong simulation tick: {folder}/{index}")
                path = folder / "frames" / f"frame_{index:03}.png"
                with Image.open(path) as image:
                    if image.mode != "RGBA" or image.size != (192, 192):
                        raise ValueError(f"Invalid original travel frame: {path}")
                    box = image.getchannel("A").getbbox()
                    if box and (min(box[:2]) <= 0 or max(box[2:]) >= 192):
                        raise ValueError(f"Source travel touches the capture edge: {path}")
                    frames.append((image.copy(), box))
            banks.append((heading, side, frames))
            for path in (*folder.glob("*.gd"), *folder.glob("*.json"), *sorted((folder / "frames").glob("*.png"))):
                relative = path.relative_to(source)
                payload = path.read_bytes()
                target = contained_media_path(preserved, str(relative))
                if target.exists() and target.read_bytes() != payload:
                    raise ValueError(f"Preserved original differs: {relative}")
                originals[relative] = payload
    packed = preserved / "packed"
    packed.mkdir(parents=True, exist_ok=True)
    for relative, payload in originals.items():
        target = preserved / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    payloads = []
    layers = {side: {} for side in ("back", "front")}
    for heading, side, frames in banks:
        width = max((box[2]-box[0] for _, box in frames if box), default=1)
        height = max((box[3]-box[1] for _, box in frames if box), default=1)
        sheet = Image.new("RGBA", (width*8, height*8))
        name = f"produce-travel-{heading}-{side}.png"
        installed = "game/assets/nature_utility/" + name
        parts = []
        for index, (image, box) in enumerate(frames):
            if box is None:
                parts.append([])
                continue
            x, y = index % 8 * width, index // 8 * height
            sheet.paste(image.crop(box), (x, y))
            parts.append([{"file": installed, "rect": [x, y, box[2]-box[0], box[3]-box[1]],
                           "offset": list(box[:2])}])
        sheet.save(packed / name)
        payloads.append((name, installed, hashlib.sha256((packed / name).read_bytes()).hexdigest()))
        # Godot positive yaw turns +X toward -Z; engine facing rows turn +X
        # toward +Y. Camera rotation then uses the existing facing transform.
        layers[side][DIRECTIONS[-heading % 8]] = parts
    identity = "nature.produce.travel.directional"
    asset = {"assetId": identity, "displayName": "Produce Flame original moving head and short trail",
        "sheet": "/nature/produce-travel.png",
        "frame": {"width": 192, "height": 192, "rows": 8, "cols": 64}, "fps": 32,
        "rowOrder": list(DIRECTIONS), "phases": {"travel": {"start": 0, "frames": 64, "fps": 32, "loop": True}},
        "anchor": {"x": .5, "y": .5}, "defaultScale": .5,
        "palettePreview": {"colors": [0x662718, 0xa73d1c, 0xdb6722, 0xef9834, 0xf1bd59, 0xf9dd91]}}
    storage = {"phases": {"travel": {"layers": [
        {"partsByFacing": layers[side], "blendMode": "normal"} for side in ("back", "front")]}}}
    TypeAdapter(AuthoredProjectileAsset).validate_json(json.dumps(asset))
    TypeAdapter(ProjectileStorage).validate_json(json.dumps(storage))
    files = install_verified_payloads(packed, tuple(payloads), preserved=packed, production=production, repo=repo)
    assets[identity] = asset
    bindings["projectileStorage"][identity] = storage
    (bundle / "projectile-assets.json").write_text(json.dumps(list(assets.values()), separators=(",", ":")) + "\n")
    (bundle / "bindings.json").write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    receipt = {"source": str(source), "preserved": str(preserved), "asset_id": identity, "files": files,
        "originals": {str(path): hashlib.sha256(payload).hexdigest() for path, payload in originals.items()},
        "registration": "Eight native headings; original RGBA only cropped/packed around emitter center. Runtime actual launch/contact owns translation. Fixed source-velocity trail; no fixture trajectory or screen-space rotation."}
    (bundle / "produce-travel-source.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def register_flame_delivery(bundle: Path) -> None:
    """Reuse the retained head at runtime endpoints, never the +X fixture path."""
    path = bundle / "projectile-assets.json"
    assets = json.loads(path.read_text())
    by_id = {row["assetId"]: row for row in assets}
    asset_id = "nature.produce.delivery"
    row = deepcopy(by_id["nature.produce.hold.front"])
    row.update(assetId=asset_id, displayName="Produce Flame retained head delivery",
        sheet="/nature.produce.delivery.png",
        phases={"cast": {"start": 0, "frames": 64, "fps": 32, "loop": True},
                "travel": {"start": 0, "frames": 64, "fps": 32, "loop": True},
                "impact": {"start": 0, "frames": 32, "fps": 32, "loop": False}})
    by_id[asset_id] = row
    path.write_text(json.dumps(list(by_id.values()), separators=(",", ":")) + "\n")
    path = bundle / "bindings.json"
    bindings = json.loads(path.read_text())
    storage = bindings["projectileStorage"]
    head = {"layers": [deepcopy(layer) for side in ("back", "front")
        for layer in storage[f"nature.produce.hold.{side}"]["phases"]["impact"]["layers"]]}
    storage[asset_id] = {"phases": {"cast": head, "travel": head,
        "impact": deepcopy(storage["nature.produce-hit.contact.front"]["phases"]["impact"])}}
    path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")


def import_nature(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT) -> dict:
    receipt = json.loads((source / "delivery-receipt.json").read_text())
    if receipt["revision"] != "compact-palm-v7" or receipt["fps"] != 32:
        raise ValueError("Expected accepted compact-palm-v7 at32FPS")
    manifest = json.loads((source / "media.json").read_text())
    banks = []
    payloads = {}
    for program, sides in (("produce", ("back", "front")), ("produce-hit", ("front",)),
            ("warm", ("back", "front")), ("chill", ("back", "front")),
            ("warm-contact", ("back", "front")), ("chill-contact", ("back", "front")),
            ("warm-reaction", ("front",)), ("chill-reaction", ("front",))):
        rows = {side: manifest[f"{program}-{side}"] for side in sides}
        first = rows[sides[0]]
        for row in rows.values():
            if (row["fps"] != 32 or row["cell"] != first["cell"] or row["pivot"] != first["pivot"]
                    or len(row["frames"]) != len(first["frames"])):
                raise ValueError("Incompatible paired nature layers")
            for path in row["pages"]:
                expected = receipt["files"][path]
                if row["sha256"][path] != expected["sha256"]:
                    raise ValueError("Nature receipt and bank checksums disagree")
                payloads[path] = (path, f"game/assets/nature_utility/{path}", expected["sha256"])
        windows = (("apply", 0, 31), ("hold", 31, 64), ("clear", 95, 33)) if first["hold"] else (("contact", 0, len(first["frames"])),)
        for phase, start, count in windows:
            bank = {"fps": 32, "cell": first["cell"], "pivot": first["pivot"], "frames": count,
                "palette": ["ffffff"], "layers": {side: {"frames": row["frames"][start:start+count],
                    "pages": row["pages"]} for side, row in rows.items()}}
            validate_billboard_bank(bank, paired=len(sides) == 2)
            banks.append((program, phase, bank, len(sides) == 2))
    texture = "assets/bark.png"
    payloads[texture] = (texture, "game/assets/nature_utility/bark.png", receipt["operators"][texture]["sha256"])
    metadata = [(source / name, contained_media_path(preserved, name)) for name in
        ("HANDOFF.md", "media.json", "spec.json", "delivery-receipt.json", "source-lineage.json",
         "weapon-material.js", "body-material.js")]
    for origin, target in metadata:
        content = origin.read_bytes()
        expected = receipt["operators"].get(origin.name)
        if expected and hashlib.sha256(content).hexdigest() != expected["sha256"]:
            raise ValueError(f"Nature material checksum mismatch: {origin.name}")
        if target.exists() and target.read_bytes() != content:
            raise ValueError(f"Archived nature metadata differs: {origin.name}")
    files = install_verified_payloads(source, tuple(payloads.values()), preserved=preserved,
        production=production, repo=repo)
    for origin, target in metadata:
        shutil.copyfile(origin, target)
    bundle = repo / "game/data/support_conditions"
    identities = []
    for program, phase, bank, paired in banks:
        identities.extend(register_billboard_bank(bank, f"nature.{program}.{phase}",
            media_root="game/assets/nature_utility", bundle=bundle, loop=phase == "hold", paired=paired))
    path = bundle / "bindings.json"
    bindings = json.loads(path.read_text())
    bindings["resources"]["/nature/bark.png"] = "game/assets/nature_utility/bark.png"
    path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    register_flame_delivery(bundle)
    installed = {"source": str(source), "preserved": str(preserved), "revision": receipt["revision"],
        "files": files, "identities": identities,
        "manifest_sha256": hashlib.sha256((source / "media.json").read_bytes()).hexdigest()}
    (bundle / "nature-source.json").write_text(json.dumps(installed, indent=2) + "\n")
    return installed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "preserved", "production"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--travel", action="store_true")
    args = parser.parse_args()
    install = import_flame_travel if args.travel else import_nature
    installed = install(args.source, preserved=args.preserved, production=args.production)
    print(f"Installed {len(installed['files'])} original payloads")
