"""Package authored Sleep/Web media; spell recipes remain independently authored."""

import argparse
import json
from pathlib import Path
import shutil

from PIL import Image

from devtools.media_delivery import owns_selected_media


ROOT = Path(__file__).resolve().parents[1]
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")


def import_bundle(source: Path, *, repo: Path = ROOT, field_asset: str | None = None) -> None:
    manifest = json.loads((source / "manifest.json").read_text())
    spell = manifest["id"]
    palette = json.loads((source / manifest["palette"]).read_text())["colors"]
    colors = [r * 65536 + g * 256 + b for r, g, b in palette]
    data = repo / "game/data/spell_recovery"
    bindings = json.loads((data / "bindings.json").read_text())
    assets = {asset["assetId"]: asset for asset in json.loads((data / "projectile-assets.json").read_text())}
    media = Path("game/assets/spell_recovery") / spell
    (repo / media).mkdir(parents=True, exist_ok=True)

    projectile = manifest["projectile"]
    if "sheet" in projectile:
        row = manifest["projectile"]
        identity = f"{spell}.projectile.v1"
        url = f"/authored-vfx/{spell}-projectile.png"
        relative = media / f"{spell}-projectile.png"
        shutil.copyfile(source / row["sheet"], repo / relative)
        bindings["resources"][url] = relative.as_posix()
        assets[identity] = {
            "assetId": identity, "displayName": row["displayName"], "kind": "projectile", "sheet": url,
            "frame": {"width": row["cell"], "height": row["cell"], "rows": len(row["rows"]), "cols": row["frames"]},
            "fps": row["fps"], "rowOrder": row["rows"],
            "phases": {"travel": {"start": 0, "frames": row["frames"], "fps": row["fps"], "loop": row["loop"]}},
            "anchor": {"x": row["originPixels"][0] / row["cell"], "y": row["originPixels"][1] / row["cell"]},
            "defaultScale": row["recommendedScale"], "palettePreview": {"colors": colors},
        }
    world_assets_path = repo / "game/data/assets.json"
    world_assets = json.loads(world_assets_path.read_text())
    for name, asset in manifest["assets"].items():
        if name == field_asset:
            # Existing prop resources own finite floor animation. Reuse adjacent
            # identical holds offline; runtime performs ordinary frame lookup.
            retained = set()
            for direction in ("E", "S", "W", "N"):
                row = asset["directions"][direction]
                pages = [Image.open(source / page["file"]).convert("RGBA") for page in row["pages"]]
                previous = None
                previous_id = None
                frame_ids = []
                for index, frame in enumerate(row["frames"]):
                    if frame is None:
                        image = Image.new("RGBA", (1, 1))
                        pivot = (0, 0)
                    else:
                        x, y, width, height = frame["rect"]
                        image = pages[frame["page"]].crop((x, y, x + width, y + height))
                        pivot = tuple(row["pivot"][axis] - frame["offset"][axis] for axis in (0, 1))
                    current = (image.size, pivot, image.tobytes())
                    if current != previous:
                        previous_id = f"{name}.field.{direction}.{index}"
                        relative = media / "field" / direction / f"{index:03}.png"
                        (repo / relative).parent.mkdir(parents=True, exist_ok=True)
                        image.save(repo / relative)
                        world_assets["resources"][previous_id] = {
                            "path": relative.relative_to("game/assets").as_posix(),
                            "native_size": list(image.size), "pivot": list(pivot),
                            "scale": world_assets["resources"].get(previous_id, {}).get("scale", 1),
                        }
                        previous = current
                    frame_ids.append(previous_id)
                    retained.add(previous_id)
                for page in pages:
                    page.close()
                # This is a media frame list, not a behavior/world binding.
                (repo / media / "field" / f"{direction}.json").write_text(json.dumps(frame_ids) + "\n")
            for identity in tuple(world_assets["resources"]):
                if identity.startswith(f"{name}.field.") and identity not in retained:
                    old = world_assets["resources"].pop(identity)
                    (repo / "game/assets" / old["path"]).unlink(missing_ok=True)
            continue
        if name not in (spell, projectile.get("asset")):
            # Persistent field/tether sprites keep their source registration.
            # The separate world binding owns placement and lifetime semantics.
            for direction, row in asset["directions"].items():
                frame = row["frames"][0]
                x, y, width, height = frame["rect"]
                with Image.open(source / row["pages"][frame["page"]]["file"]) as sheet:
                    image = sheet.crop((x, y, x + width, y + height))
                    relative = media / name / f"{direction}.png"
                    (repo / relative).parent.mkdir(parents=True, exist_ok=True)
                    image.save(repo / relative)
                world_assets["resources"][f"{name}.{direction}"] = {
                    "path": relative.relative_to("game/assets").as_posix(),
                    "native_size": [width, height],
                    "pivot": [row["pivot"][axis] - frame["offset"][axis] for axis in (0, 1)],
                    "scale": world_assets["resources"].get(f"{name}.{direction}", {}).get("scale", 1),
                }
            continue
        phase = "travel" if name == projectile.get("asset") else "impact"
        identity = f"{spell}.projectile.v1" if phase == "travel" else f"{spell}.area.v1"
        if not owns_selected_media(bindings.get("projectileStorage", {}), identity, media.as_posix()):
            continue
        # Repack the source's cropped rectangles into the existing fixed-cell
        # page format. All views keep one common canvas crop and their measured
        # pivot; frames and native timing are unchanged, including empty tails.
        frames = [frame for direction in asset["directions"].values() for frame in direction["frames"] if frame]
        left = min(frame["offset"][0] for frame in frames)
        top = min(frame["offset"][1] for frame in frames)
        width = max(frame["offset"][0] + frame["rect"][2] for frame in frames) - left
        height = max(frame["offset"][1] + frame["rect"][3] for frame in frames) - top
        columns, per_page = 4, 32
        pages = {}
        anchors = {}
        for direction, row in asset["directions"].items():
            anchors[direction] = {"x": (row["pivot"][0] - left) / width, "y": (row["pivot"][1] - top) / height}
            source_pages = [Image.open(source / page["file"]).convert("RGBA") for page in row["pages"]]
            pages[direction] = []
            for first in range(0, asset["frames"], per_page):
                count = min(per_page, asset["frames"] - first)
                sheet = Image.new("RGBA", (width * columns, height * ((count + columns - 1) // columns)))
                for index, frame in enumerate(row["frames"][first:first + count]):
                    if frame is None:
                        continue
                    x, y, w, h = frame["rect"]
                    crop = source_pages[frame["page"]].crop((x, y, x + w, y + h))
                    sheet.paste(crop, ((index % columns) * width + frame["offset"][0] - left,
                                       (index // columns) * height + frame["offset"][1] - top))
                relative = media / phase / direction / f"{first // per_page:02}.png"
                (repo / relative).parent.mkdir(parents=True, exist_ok=True)
                sheet.save(repo / relative, compress_level=3)
                pages[direction].append({"file": relative.as_posix(), "firstFrame": first, "frameCount": count, "columns": columns})
            for page in source_pages:
                page.close()
        assets[identity] = {
            "assetId": identity, "displayName": projectile["displayName"] if phase == "travel" else f"{spell.title()} Area", "kind": "projectile",
            "sheet": f"/authored-vfx/{spell}-{'projectile' if phase == 'travel' else 'area'}.png", "frame": {"width": width, "height": height, "rows": 8, "cols": asset["frames"]},
            "fps": asset["fps"], "rowOrder": list(DIRECTIONS),
            "phases": {phase: {"start": 0, "frames": asset["frames"], "fps": asset["fps"], "loop": asset["loop"]}},
            "anchor": anchors["S"], "anchorsByFacing": anchors, "defaultScale": 0.5,
            "palettePreview": {"colors": colors},
        }
        bindings.setdefault("projectileStorage", {})[identity] = {"phases": {phase: {"layers": [
            {"pages": pages, "blendMode": "normal" if asset["blendMode"] == "alpha" else "add"}]}}}
    for name, value in (("bindings.json", bindings), ("projectile-assets.json", list(assets.values()))):
        (data / name).write_text(json.dumps(value, indent=2) + "\n")
    if any(name != spell for name in manifest["assets"]):
        world_assets_path.write_text(json.dumps(world_assets, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--field-asset", help="Package this declared media sequence as existing prop frame resources.")
    args = parser.parse_args()
    import_bundle(args.source, field_asset=args.field_asset)
    print("Packaged authored media and registration; spell recipes retained.")


if __name__ == "__main__":
    main()
