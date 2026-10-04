"""Install the October 4 selected banks and unchanged Wind K1 components.

This offline adapter updates storage/registration only. It does not select or
write spell recipes. External bank references are admitted by the delivery's
explicit receipt and resolved inside its common source parent.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

from devtools.import_registered_media import DIRECTIONS
from devtools.media_delivery import contained_media_path, install_verified_payloads
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


ROOT = Path(__file__).resolve().parents[1]
REVISION = "production-gaps-20261004-v1"
BUNDLES = {"cone": "weather_solar_media", "call": "lightning_media", "wind": "wall_media"}
PALETTES = {
    "cone": [0x1d394c, 0x2d536e, 0x3f7895, 0x609eb8, 0x91c1d1, 0xc0dce2, 0xe0ecea],
    "wind": [0x445765, 0x718c9c, 0xa5c0cd, 0xd6e2e5, 0xf1efda],
}
WIND_PROJECT = "godot-library/projects/lelu-godot-wind-premium-1"
WIND_TEXTURE = f"{WIND_PROJECT}/VFX/textures/T_WindWave_Single_A1.png"
COLD_TEXTURES = {f"/cold/{name}": f"wall-spells-study/cold-conditions-demo/assets/{name}"
                 for name in ("freeze-noise.png", "freeze-normal.webp")}
SOURCE_ROLES = {
    "source registration", "existing runtime registration", "runtime registration",
    "editable capture adapter", "reproduction command", "timing evidence",
    "private native donor dependency", "editable authoring/reproduction source",
    "shared runtime/source dependency", "native donor provenance",
    "approved native baseline source", "camera/vector adapter",
    "continuous native geometry recipe", "delivery documentation", "validation/resource evidence",
}

MESH_EXPORT_SCRIPT = '''extends SceneTree
func _initialize()->void:
 var scene=load("res://VFX/Scenes/VFX_WindHit_K1.tscn").instantiate()
 var mesh=scene.get_node("VFX_Smoke_A8").draw_pass_1
 assert(mesh.get_surface_count()==1)
 var a=mesh.surface_get_arrays(0)
 var vertices=[];var uv=[];var indices=[]
 for p in a[Mesh.ARRAY_VERTEX]:vertices.append([p.x,p.y,p.z])
 for p in a[Mesh.ARRAY_TEX_UV]:uv.append([p.x,p.y])
 for p in a[Mesh.ARRAY_INDEX]:indices.append(p)
 FileAccess.open(OUTPUT_PATH,FileAccess.WRITE).store_string(JSON.stringify({"vertices":vertices,"uv":uv,"indices":indices}))
 scene.free()
 print("WIND_K1_ORIGINAL_MESH_EXPORTED")
 quit()
'''


def export_wind_mesh(source: Path, output: Path, godot: Path) -> Path:
    """Read imported donor arrays through Godot; no capture or source-project edit."""
    output.mkdir(parents=True, exist_ok=True)
    mesh = output / "wind-mesh.json"
    def windows(path: Path) -> str:
        return subprocess.check_output(["wslpath", "-w", str(path.resolve())], text=True).strip()
    script = output / "export-wind-mesh.gd"
    script.write_text(MESH_EXPORT_SCRIPT.replace("OUTPUT_PATH", json.dumps(windows(mesh))))
    command = [str(godot), "--headless", "--path", windows(source.parent / WIND_PROJECT),
               "--script", windows(script)]
    (output / "export-command.json").write_text(json.dumps(command, indent=2) + "\n")
    with (output / "export.log").open("w") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=45)
    if not mesh.is_file():
        raise ValueError("Godot did not export the original Wind mesh")
    return mesh


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_production_gaps(source: Path, mesh_export: Path, *, preserved: Path,
                           production: Path, repo: Path = ROOT) -> dict:
    source = source.resolve()
    common = source.parent
    media_path, receipt_path = source / "media.json", source / "delivery-receipt.json"
    media, delivery = json.loads(media_path.read_text()), json.loads(receipt_path.read_text())
    if media["revision"] != REVISION or delivery["revision"] != REVISION:
        raise ValueError("Unexpected production-gap delivery revision")
    declared = {row["path"]: row for row in delivery["files"]}
    if len(declared) != len(delivery["files"]):
        raise ValueError("Delivery receipt repeats a source address")
    originals: dict[str, Path] = {}

    def verify(relative: str) -> Path:
        path = contained_media_path(common, relative)
        row = declared[relative]
        if path.stat().st_size != row["bytes"] or _digest(path) != row["sha256"]:
            raise ValueError(f"Delivery checksum mismatch: {relative}")
        originals[relative] = path
        return path

    verify(media_path.relative_to(common).as_posix())
    for relative, row in declared.items():
        if set(row["groups"]) & {"cone", "call", "wind", "all"} and set(row["roles"]) & SOURCE_ROLES:
            verify(relative)
    # The receipt cannot hash itself. Preserve its exact bytes and the original
    # Cone operator/notes alongside the selected receipt-indexed dependencies.
    for path in (receipt_path, common / "cold-weather-batch/cone-of-cold-v1/NOTES.md",
                 common / "cold-weather-batch/cone-of-cold-v1/review.js"):
        originals[path.relative_to(common).as_posix()] = path
    expected = {
        "cone": {*(f"h{i}/{band}" for i in range(8) for band in ("near", "middle", "far", "ground")),
                 "contact-back", "contact-front"},
        "call": {f"q{i}" for i in range(4)}, "wind": {f"h{i}" for i in range(8)},
    }
    payloads: dict[str, tuple[str, str, str]] = {}
    dimensions: dict[str, tuple[int, int]] = {}
    palettes = dict(PALETTES)
    parts_by_bank: dict[str, dict] = {group: {} for group in BUNDLES}
    for group, names in expected.items():
        if set(media[group]) != names:
            raise ValueError(f"Incomplete {group} bank selection")
        for name, bank in media[group].items():
            count = 96 if group == "cone" and not name.startswith("contact") else 32 if group == "wind" else 48
            revision = bank.get("sourceRevision", bank.get("revision"))
            if (bank["fps"] != 32 or bank["frameCount"] != count or len(bank["frames"]) != count
                    or revision != {"cone": "straight-alpha-volume-v4", "call": "blue-local-v4",
                                    "wind": "native-isolated-block-v1"}[group]):
                raise ValueError(f"Unexpected {group}/{name} source timing or revision")
            page_paths = []
            for index, address in enumerate(bank["pages"]):
                path = (source / address).resolve()
                if not path.is_relative_to(common):
                    raise ValueError("Bank reference leaves common source root")
                relative = path.relative_to(common).as_posix()
                verify(relative)
                if not set(declared[relative]["roles"]) & {"runtime RGBA", "existing runtime RGBA"}:
                    raise ValueError("Selected page is not declared runtime RGBA")
                if relative not in dimensions:
                    with Image.open(path) as picture:
                        if picture.mode != "RGBA":
                            raise ValueError("Selected source pages must retain RGBA")
                        dimensions[relative] = picture.size
                        if group == "call" and "call" not in palettes:
                            # Call retains continuous native blue, not a palette
                            # remap. These UI swatches are existing visible pixels.
                            pixels = np.asarray(picture).reshape(-1, 4)
                            colors, counts = np.unique(pixels[pixels[:, 3] > 0, :3], axis=0, return_counts=True)
                            palettes["call"] = [int(r) * 65536 + int(g) * 256 + int(b)
                                for r, g, b in colors[np.argsort(counts)[-6:][::-1]]]
                runtime = f"game/assets/{BUNDLES[group]}/production-gaps/{group}/{name}/{index}.png"
                payloads[relative] = (relative, runtime, declared[relative]["sha256"])
                page_paths.append((relative, runtime))
            parts = []
            for frame in bank["frames"]:
                if frame is None:
                    parts.append([])
                    continue
                relative, runtime = page_paths[frame["page"]]
                x, y, width, height = frame["source"]
                left, top = frame["offset"]
                if (min(x, y, left, top) < 0 or min(width, height) <= 0
                        or x + width > dimensions[relative][0] or y + height > dimensions[relative][1]
                        or left + width > bank["cell"] or top + height > bank["cell"]):
                    raise ValueError(f"Crop leaves source atlas or logical cell: {group}/{name}")
                parts.append([{"file": runtime, "rect": frame["source"], "offset": frame["offset"]}])
            parts_by_bank[group][name] = parts

    assets: dict[str, dict] = {group: {} for group in BUNDLES}
    storage: dict[str, dict] = {group: {} for group in BUNDLES}
    registrations: dict[str, dict] = {group: {} for group in BUNDLES}

    def register(group: str, identity: str, facing_names: dict[str, str]) -> None:
        banks = {facing: media[group][name] for facing, name in facing_names.items()}
        first = next(iter(banks.values()))
        cell, count = first["cell"], first["frameCount"]
        if any((row["cell"], row["frameCount"], row["captureZoom"]) != (cell, count, first["captureZoom"])
               for row in banks.values()):
            raise ValueError("Facing banks disagree on frame or capture registration")
        anchors = {facing: {"x": row["pivot"][0] / cell, "y": row["pivot"][1] / cell}
                   for facing, row in banks.items()}
        assets[group][identity] = {
            "assetId": identity, "displayName": identity, "kind": "projectile", "sheet": f"/{identity}.png",
            "frame": {"width": cell, "height": cell, "rows": 8, "cols": count}, "fps": 32,
            "rowOrder": list(DIRECTIONS), "phases": {"impact": {"start": 0, "frames": count, "fps": 32, "loop": False}},
            "anchor": anchors["SE"], "anchorsByFacing": anchors, "defaultScale": 1,
            "palettePreview": {"colors": palettes[group]},
        }
        storage[group][identity] = {"phases": {"impact": {"layers": [{"partsByFacing": {
            facing: parts_by_bank[group][name] for facing, name in facing_names.items()}, "blendMode": "normal"}]}}}
        registrations[group][identity] = {"banksByFacing": facing_names, "captureZoom": first["captureZoom"],
            "referencePixelScale": 1 / first["captureZoom"], "frameCount": count, "fps": 32,
            "pivotByFacing": {facing: row["pivot"] for facing, row in banks.items()},
            "sortDepthByFacing": {facing: row.get("sortDepthCanonical") for facing, row in banks.items()}}

    for band in ("near", "middle", "far", "ground"):
        register("cone", f"weather.cone.{band}", {facing: f"h{(index - 1) % 8}/{band}"
                 for index, facing in enumerate(DIRECTIONS)})
    for side in ("back", "front"):
        register("cone", f"weather.cone.contact.{side}", {f: f"contact-{side}" for f in DIRECTIONS})
    for camera in range(4):
        register("call", f"lightning.call_lightning.v5.q{camera}", {f: f"q{camera}" for f in DIRECTIONS})
    for heading in range(8):
        register("wind", f"wall.wind.block.h{heading}", {f: f"h{heading}" for f in DIRECTIONS})
    for group in BUNDLES:
        for row in assets[group].values():
            AuthoredProjectileAsset.model_validate_json(json.dumps(row))
        for row in storage[group].values():
            ProjectileStorage.model_validate_json(json.dumps(row))

    mesh = json.loads(mesh_export.read_text())
    if (set(mesh) != {"vertices", "uv", "indices"} or len(mesh["vertices"]) != 8
            or len(mesh["uv"]) != 8 or len(mesh["indices"]) != 12):
        raise ValueError("Expected the exact imported K1 cross-plane mesh")
    component = {"mesh": mesh, "texture": "/wind/block-texture.png", "palette": PALETTES["wind"],
        "nativeUnitsPerCell": 2.121320344, "verticalUnitsPerCell": 3 ** .5, "count": 5,
        "staggerSeconds": .022, "durationSeconds": .70, "scale": [.33, .48, .33],
        "yawStepRadians": 1.1, "baseColor": [.78, .87, .91], "opacity": .66, "sheet": [5, 2]}
    verify(WIND_TEXTURE)
    texture_runtime = "game/assets/wall_media/production-gaps/wind/block-texture.png"
    payloads[WIND_TEXTURE] = (WIND_TEXTURE, texture_runtime, declared[WIND_TEXTURE]["sha256"])
    cold_resources = {}
    for identity, relative in COLD_TEXTURES.items():
        verify(relative)
        runtime = f"game/assets/weather_solar_media/production-gaps/cold/{Path(relative).name}"
        payloads[relative] = (relative, runtime, declared[relative]["sha256"])
        cold_resources[identity] = runtime
    component_relative = "extracted/wind/block-components.json"
    component_runtime = "game/assets/wall_media/production-gaps/wind/block-components.json"
    component_bytes = (json.dumps(component, separators=(",", ":")) + "\n").encode()
    payloads[component_relative] = (component_relative, component_runtime, hashlib.sha256(component_bytes).hexdigest())
    for name in ("wind-mesh.json", "export-wind-mesh.gd", "export-command.json", "export.log"):
        originals[f"extracted/wind/{name}"] = mesh_export.parent / name

    # Complete source/preservation preflight precedes every installed mutation.
    original_digests = {relative: _digest(origin) for relative, origin in originals.items()}
    for relative, origin in originals.items():
        target = contained_media_path(preserved, relative)
        if target.exists() and (not target.is_file() or target.read_bytes() != origin.read_bytes()):
            raise ValueError(f"Preserved original differs: {relative}")
    with TemporaryDirectory(prefix="dnd-production-gap-") as temporary:
        stage = Path(temporary)
        for relative, _, _ in payloads.values():
            target = contained_media_path(stage, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative == component_relative:
                target.write_bytes(component_bytes)
            else:
                shutil.copyfile(originals[relative], target)
        installed = install_verified_payloads(stage, tuple(payloads.values()), preserved=preserved,
            production=production, repo=repo)
    for relative, origin in originals.items():
        target = contained_media_path(preserved, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
    result = {}
    for group, bundle_name in BUNDLES.items():
        bundle = repo / "game/data" / bundle_name
        binding_path, asset_path = bundle / "bindings.json", bundle / "projectile-assets.json"
        bindings = json.loads(binding_path.read_text()) if binding_path.exists() else {"resources": {}, "spells": {}}
        registered = {row["assetId"]: row for row in json.loads(asset_path.read_text())} if asset_path.exists() else {}
        bindings.setdefault("projectileStorage", {}).update(storage[group])
        registered.update(assets[group])
        if group == "wind":
            bindings.setdefault("resources", {}).update({"/wind/block-components.json": component_runtime,
                                                        "/wind/block-texture.png": texture_runtime})
        elif group == "cone":
            bindings.setdefault("resources", {}).update(cold_resources)
        bundle.mkdir(parents=True, exist_ok=True)
        binding_path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
        asset_path.write_text(json.dumps(list(registered.values()), separators=(",", ":")) + "\n")
        receipt = {"revision": REVISION, "source": str(source), "preserved": str(preserved),
            "mediaSha256": _digest(media_path), "deliveryReceiptSha256": _digest(receipt_path),
            "identities": list(assets[group]), "registrations": registrations[group],
            "contracts": media["contracts"][group],
            "files": [row for row in installed if row["path"].startswith(f"game/assets/{bundle_name}/")],
            "originals": [{"path": relative, "sha256": original_digests[relative]} for relative in originals
                          if relative not in declared or set(declared[relative]["groups"]) & {group, "all"}],
            "scope": "Original selected RGBA/crops and source components; no recipes, rescaling, recoloring or render capture."}
        if group == "wind":
            receipt["componentOperator"] = {
                "resource": "/wind/block-components.json", "texture": "/wind/block-texture.png",
                "phase": "u=clamp((age-i*.022)/.70,0,1)",
                "position": "[(i-2)*.20*smoothstep(0,.5,u), -.22+u*.9, .10+sin(i)*.04]",
                "scale": "[.33,.48,.33]*(1+u*.35)", "rotationY": "i*1.1",
                "opacity": "smoothstep(0,.10,u)*(1-smoothstep(.55,1,u))*.66",
                "frame": "floor(u*9)", "uv": "UV/[5,2]+[frame%5/5,floor(frame/5)/2]",
                "alpha": "texture.a*opacity", "albedo": [.78, .87, .91],
                "paletteSampling": "Original lower-right RGB in each 2x2 capture pixel block; nearest sRGB palette color, keep original alpha, alpha<3 becomes zero.",
                "orientation": "Normalize tangent w and incoming v; reverse when v.dot([-w.y,w.x])>1e-8 or when abs(side)<=1e-8 and v.dot(w)>0; heading=atan2(w.y,w.x)+PI if reversed; root.rotation.y=-heading.",
                "geometry": "Exact Godot imported arrays, including mesh compression coordinates; no raster capture."}
        (bundle / "production-gap-source.json").write_text(json.dumps(receipt, indent=2) + "\n")
        result[group] = receipt
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "preserved", "production", "mesh-export"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = import_production_gaps(args.source, args.mesh_export, preserved=args.preserved, production=args.production)
    print(json.dumps({group: {"assets": len(row["identities"]), "files": len(row["files"])}
                      for group, row in result.items()}))
