"""Pack the approved fixed-window pixels; authored physics and recipes stay separate."""

import argparse
import json
import hashlib
import shutil
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
POSES = "eswn"


def import_windows(source: Path, output: Path = ROOT, *, insert_source: Path) -> None:
    declarations = json.loads((ROOT / "game/data/window_media_sources.json").read_text())
    dense_root = source / "destruction-showcase/dense-production"
    dense = json.loads((dense_root / "manifest.json").read_text())
    inserts = json.loads((insert_source / "manifest.json").read_text())
    # The original dense "window" sheets are scene previews with a standing
    # parent wall baked behind the insert. They are not an independently usable layer.
    for row in declarations["banks"].values():
        if row["part"] != "insert" or row["mode"] != "break":
            continue
        key = f"{row['family']}/window"
        component = inserts[key]
        if component.get("component") != "insert" or component.get("parent_wall_beauty_included") is not False:
            raise ValueError(f"Insert destruction requires an insert-only export: {key}")
        for field in ("frame_count", "frame_times_seconds", "duration_seconds", "frame_size", "anchor"):
            if component[field] != dense[key][field]:
                raise ValueError(f"Insert-only export changed authored {field}: {key}")
    registration = output / "game/data/environment_art.json"
    document = json.loads(registration.read_text())
    media_root = output / "game/assets/environment/windows"
    media_root.mkdir(parents=True, exist_ok=True)
    for family in sorted(set(declarations["solid_siblings"].values())):
        bank_id = f"wall.fantasy.{family}.intact"
        relative = f"environment/windows/{bank_id}.png"
        sheet = Image.new("RGBA", (1280, 320))
        for index, pose in enumerate(POSES):
            original = source / "destruction-showcase/existing-solid-siblings" / f"fantasy-wall-{family}_{pose}.png"
            with Image.open(original) as image:
                if image.size != (256, 256):
                    raise ValueError(f"Unexpected solid-wall canvas: {original}")
                sheet.paste(image.convert("RGBA"), (index*320+32, 32))
        sheet.save(output / "game/assets" / relative, optimize=True)
        document["banks"][bank_id] = {
            "cell": [320, 320], "ground_pivot": [160, 240],
            "pivots_by_pose": {pose: [160, 240] for pose in POSES},
            "rows": list(POSES), "scale": 1, "frame_count": 1,
            "sample_times_ms": [0], "duration_ms": 0,
            "frames_by_pose": {pose: [{"path": relative,
                "rect": [index*320, 0, 320, 320]}] for index, pose in enumerate(POSES)},
        }
        document["props"][f"environment.wall.fantasy_{family}"] = {
            "intact": {"default": bank_id}, "destructions": {}, "occludes_actor_face": True,
        }
    for bank_id, row in declarations["banks"].items():
        family, part, mode = row["family"], row["part"], row["mode"]
        folder = source / "destruction-showcase" / family
        if mode != "intact":
            source_part = ("wall-after-insert" if mode == "after_insert" else
                           "window" if part == "insert" else "wall")
            delivery_root = insert_source if part == "insert" else dense_root
            delivered = (inserts if part == "insert" else dense)[f"{family}/{source_part}"]
            bank = document["banks"][bank_id]
            # Keep physical clearance at the already authored presentation time.
            clearance_ms = bank["sample_times_ms"][bank["state_change_frame"]]
            times = [value * 1000 for value in delivered["frame_times_seconds"]]
            bank.update(frame_count=delivered["frame_count"], sample_times_ms=times,
                duration_ms=delivered["duration_seconds"] * 1000,
                state_change_frame=next(i for i, value in enumerate(times) if value >= clearance_ms-1e-6))
            bank["frames_by_pose"] = {}
            for pose in POSES:
                view = delivered["views"][pose]
                original = delivery_root / view["atlas_url"]
                if hashlib.sha256(original.read_bytes()).hexdigest() != view["sha256"]:
                    raise ValueError(f"Dense delivery changed: {original}")
                relative = f"environment/windows/{bank_id}.{pose}.png"
                shutil.copy2(original, output / "game/assets" / relative)
                bank["frames_by_pose"][pose] = [{"path": relative,
                    "rect": [region["x"], region["y"], region["width"], region["height"]]}
                    for region in delivered["frame_regions"]]
            continue
        cells = []
        for pose in POSES:
            entry = Image.new("RGBA", (320, 320))
            entry.paste(Image.open(folder / f"{part}-{pose}.png").convert("RGBA"), (32, 32))
            cells.append(entry)
        columns = min(6, len(cells))
        sheet = Image.new("RGBA", (columns*320, ((len(cells)+columns-1)//columns)*320))
        for index, image in enumerate(cells):
            if image.size != (320, 320):
                raise ValueError(f"Unexpected approved cell: {bank_id}: {image.size}")
            sheet.paste(image, ((index % columns)*320, (index // columns)*320))
        relative = f"environment/windows/{bank_id}.png"
        sheet.save(output / "game/assets" / relative, optimize=True)
        count = document["banks"][bank_id]["frame_count"]
        document["banks"][bank_id]["frames_by_pose"] = {
            pose: [{"path": relative, "rect": [((row_index*count+i)%columns)*320,
                       ((row_index*count+i)//columns)*320, 320, 320]} for i in range(count)]
            for row_index, pose in enumerate(POSES)}
        if mode == "intact":
            mask = Image.new("RGBA", (1280, 320))
            for i, pose in enumerate(POSES):
                region = Image.open(folder / f"{'window' if part == 'insert' else 'wall'}-mask-{pose}.png").convert("L")
                pixels = Image.new("RGBA", region.size, "white")
                pixels.putalpha(region)
                mask.paste(pixels, (i*320+32, 32))
            mask.save(media_root / f"window.{family}.{part}.selection.png", optimize=True)
            if part == "wall":
                document["props"][f"environment.window.fantasy_{family}.wall"]["occludes_actor_face"] = True
                aperture = Image.new("RGBA", (1280, 320))
                for index, pose in enumerate(POSES):
                    with Image.open(folder / f"window-mask-{pose}.png") as original:
                        region = original.convert("L")
                    pixels = Image.new("RGBA", region.size, "white")
                    pixels.putalpha(region)
                    aperture.paste(pixels,(index*320+32,32))
                relative = f"environment/windows/window.{family}.aperture.png"
                aperture.save(output / "game/assets" / relative,optimize=True)
                document["props"][f"environment.window.fantasy_{family}.wall"]["aperture_masks_by_pose"] = {
                    pose: {"path":relative,"rect":[index*320,0,320,320]}
                    for index,pose in enumerate(POSES)}
    registration.write_text(json.dumps(document, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--insert-source", type=Path, required=True,
                        help="Component-only insert delivery; combined wall previews are not usable layers.")
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args()
    import_windows(args.source, args.output, insert_source=args.insert_source)
