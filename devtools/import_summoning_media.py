"""Import accepted summoning pages into existing paged media storage.

This offline adapter writes a candidate media-only bundle and private manifest
entries. The caller merges those with the current release after concurrent media
imports finish. Native lifecycle rules, recipes and runtime schemas stay outside.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MEDIA = Path("game/assets/summoning_media")
FACINGS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
PHASES = {"cast": (24, ("back", "front")), "arrival": (56, ("ground", "back", "front")),
          "departure": (48, ("ground", "back", "front")), "bond": (24, ("ground", "back", "front"))}
FAMILIES = ("natural", "fey_spirit", "fiend")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def source_file(source: Path, relative: str) -> Path:
    path = (source / relative).resolve()
    if not path.is_relative_to(source.resolve()) or not path.is_file():
        raise ValueError(f"summoning source leaves delivery or is missing: {relative}")
    return path


def admit_copy(origin: Path, destination: Path) -> None:
    if destination.exists() and (not destination.is_file() or destination.read_bytes() != origin.read_bytes()):
        raise ValueError(f"refusing to overwrite different summoning source: {destination}")
    if any(parent.exists() and not parent.is_dir() for parent in destination.parents):
        raise ValueError(f"summoning destination parent is not a directory: {destination}")


def import_bundle(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT) -> dict:
    """Admit exact source bytes and registrations before writing any payload."""
    manifest_path = source_file(source, "manifest.json")
    manifest = json.loads(manifest_path.read_text())
    banks, palette = manifest["banks"], manifest["palette"]
    levels = palette["neutralLevels"]
    if (manifest["revision"] != "summoning-lifecycle-v1" or manifest["fps"] != 32
            or manifest["actorsOrFloorBaked"] or manifest["alphaEncoding"] != "straight_alpha_srgb"
            or palette["method"] != "exact_palette_replacement" or not palette["preserveAlpha"]
            or levels != [32, 62, 94, 128, 163, 196, 225, 244]
            or set(palette["families"]) != set(FAMILIES)):
        raise ValueError("summoning import requires the accepted neutral, actor-free 32 FPS source")
    expected = {f"{phase}-q{q}-{side}" for phase, (_, sides) in PHASES.items()
                for q in range(4) for side in sides}
    if set(banks) != expected:
        raise ValueError("summoning import requires all 44 camera/layer banks")
    payloads = {}
    for name, row in banks.items():
        phase, camera, side = name.split("-")
        count = PHASES[phase][0]
        if (row["kind"] != phase or row["layer"] != side or row["cameraQuadrant"] != int(camera[1:])
                or row["fps"] != 32 or row["count"] != count or len(row["frames"]) != count
                or row["canvas"] != [384, 384] or row["groundPivot"] != [192, 249.6]
                or row["worldPixelsPerCell"] != [128, 64]):
            raise ValueError(f"invalid summoning registration: {name}")
        relative = row["file"]
        origin = source_file(source, relative)
        digest = hashlib.sha256(origin.read_bytes()).hexdigest()
        if digest != row["sha256"] or origin.stat().st_size != row["bytes"]:
            raise ValueError(f"summoning source checksum mismatch: {relative}")
        with Image.open(origin) as image:
            if image.mode != "RGBA":
                raise ValueError(f"summoning source must retain straight RGBA: {relative}")
            if relative not in payloads:
                pixels = np.asarray(image)
                visible = pixels[:, :, 3] > 0
                rgb = pixels[:, :, :3]
                if (not np.array_equal(rgb[:, :, 0], rgb[:, :, 1])
                        or not np.array_equal(rgb[:, :, 0], rgb[:, :, 2])
                        or not np.isin(rgb[:, :, 0][visible], levels).all()
                        or rgb[~visible].any()):
                    raise ValueError(f"summoning source no longer has its exact neutral palette: {relative}")
            for index, frame in enumerate(row["frames"]):
                x, y, width, height = frame["source"]
                dx, dy = frame["offset"]
                if (min(x, y, dx, dy) < 0 or min(width, height) <= 0
                        or x + width > image.width or y + height > image.height
                        or dx + width > 384 or dy + height > 384
                        or frame["timeSeconds"] != index / 32):
                    raise ValueError(f"invalid summoning frame crop/clock: {name}/{index}")
                if index in (0, count - 1) and image.crop((x, y, x + width, y + height)).getchannel("A").getbbox():
                    raise ValueError(f"summoning finite endpoint must remain transparent: {name}/{index}")
        payloads[relative] = (origin, digest)
    if (len(payloads) != manifest["uniqueAtlasFiles"] or len(payloads) != 32
            or sum(path.stat().st_size for path, _ in payloads.values()) != manifest["assetBytes"]):
        raise ValueError("summoning unique payload totals disagree with manifest")

    # Keep original geometry, native captures and source documents privately.
    # Review actor/reference copies are deliberately not production payloads.
    documents = {name: source_file(source, name) for name in
                 ("HANDOFF.md", "manifest.json", "provenance.json", "inventory.json", "PLAN.md")}
    for directory in ("authoring", "originals", "native"):
        documents.update((path.relative_to(source).as_posix(), path)
                         for path in sorted((source / directory).rglob("*")) if path.is_file())
    for name in ("review/export-validation.json", "review/browser-validation.json", "review/validation.json"):
        documents[name] = source_file(source, name)
    for relative, origin in documents.items():
        admit_copy(origin, preserved / relative)
    for relative, (origin, _) in payloads.items():
        for destination in (preserved / relative, repo / MEDIA / relative, production / MEDIA / relative):
            admit_copy(origin, destination)

    assets, storage, phases = [], {}, {}
    for phase, (count, sides) in PHASES.items():
        phase_tracks = {}
        for family in FAMILIES:
            tracks = []
            colors = [int(color, 16) for color in palette["families"][family]]
            if len(colors) != len(levels):
                raise ValueError(f"summoning palette requires eight replacements: {family}")
            for side in sides:
                identity = f"summoning.{family}.{phase}.{side}"
                views = {}
                for q in range(4):
                    row = banks[f"{phase}-q{q}-{side}"]
                    parts = [[{"file": (MEDIA / row["file"]).as_posix(),
                               "rect": frame["source"], "offset": frame["offset"]}]
                             for frame in row["frames"]]
                    views[FACINGS[2 * q]] = views[FACINGS[2 * q + 1]] = parts
                assets.append({"assetId": identity, "displayName": identity, "kind": "projectile",
                    "sheet": f"/summoning/{family}/{phase}/{side}.png",
                    "frame": {"width": 384, "height": 384, "rows": 8, "cols": count},
                    "fps": 32, "rowOrder": list(FACINGS),
                    "phases": {"impact": {"start": 0, "frames": count, "fps": 32, "loop": False}},
                    "anchor": {"x": .5, "y": .65}, "defaultScale": 1,
                    "palettePreview": {"colors": colors},
                    "paletteSwap": {"originalColors": [level * 0x010101 for level in levels],
                                    "targetColors": colors, "tolerance": 0}})
                storage[identity] = {"phases": {"impact": {"layers": [
                    {"partsByFacing": views, "blendMode": "normal"}]}}}
                tracks.append({"id": f"{phase}.{side}", "assetId": identity, "assetPhase": "impact",
                    "attachment": "source_hand" if phase == "cast" else "target_ground",
                    "fps": 32, "durationMs": count * 1000 / 32, "loop": False,
                    "scale": 1, "scaleWithActor": False, "viewFacing": "E",
                    "depth": "ground" if side == "ground" else "behind_body" if side == "back" else "front_body"})
            phase_tracks[family] = tracks
        phases[phase] = {"durationMs": count * 1000 / 32, "tracksByManifestation": phase_tracks,
                         "sourceMarkers": manifest["phases"][phase]}
    original_colors = [level * 0x010101 for level in levels]
    palettes = {family: {"originalColors": original_colors,
                         "targetColors": [int(color, 16) for color in palette["families"][family]],
                         "tolerance": 0} for family in FAMILIES}
    receipt = {"revision": manifest["revision"], "source": str(source),
        "sourceManifestSha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "sourceStatusPreserved": manifest["status"], "cameraBanks": len(banks),
        "selectedFrameLayerSamples": sum(row["count"] for row in banks.values()),
        "assetIds": [asset["assetId"] for asset in assets], "files": [],
        "runtimePaletteStatus": "asset paletteSwap populated; shared runtime consumer owned by parent",
        "sharedManifestStatus": "candidate entries only; merge with current release after other imports",
        "registration": {"canvas": [384, 384], "pivot": [192, 249.6], "fps": 32,
                         "worldPixelsPerCell": [128, 64], "nativePixels": True},
        "sourceDocuments": []}
    for relative, origin in documents.items():
        destination = preserved / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
        digest = hashlib.sha256(origin.read_bytes()).hexdigest()
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise ValueError(f"summoning source preservation checksum mismatch: {relative}")
        receipt["sourceDocuments"].append({"path": relative, "sha256": digest})
    for relative, (origin, digest) in payloads.items():
        local = MEDIA / relative
        for destination in (preserved / relative, repo / local, production / local):
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, destination)
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise ValueError(f"summoning page copy checksum mismatch: {destination}")
        receipt["files"].append({"path": local.as_posix(), "bytes": origin.stat().st_size, "sha256": digest})
    receipt["files"].sort(key=lambda row: row["path"])
    folder = repo / "game/data/summoning_media"
    write_json(folder / "bindings.json", {"resources": {}, "spells": {}, "projectileStorage": storage})
    write_json(folder / "projectile-assets.json", assets)
    write_json(folder / "phase-candidates.json", {"phases": phases, "nativePixels": True,
        "supportedEffectScale": manifest["supportedEffectScale"]})
    write_json(folder / "palette-handoff.json", {"method": "exact_palette_replacement",
        "palettesByManifestation": palettes, "preserveAlpha": True, "bodyShadowExempt": True})
    write_json(folder / "source-receipt.json", {key: value for key, value in receipt.items() if key != "sourceDocuments"})
    write_json(preserved / "install-receipt.json", receipt)
    write_json(preserved / "art-manifest-entries.json", receipt["files"])
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--preserved", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args()
    receipt = import_bundle(args.source, preserved=args.preserved, production=args.production, repo=args.repo)
    print(f"Imported {len(receipt['files'])} original pages / {sum(row['bytes'] for row in receipt['files'])} bytes; "
          f"{len(receipt['assetIds'])} family layer records, shared manifests unchanged")
