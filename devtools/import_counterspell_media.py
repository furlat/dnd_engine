"""Copy Counterspell's declared camera media without authoring runtime behavior."""

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
MEDIA = Path("game/assets/counterspell_media")


def import_bundle(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    """Preserve source pixels, frame order and native-canvas registration."""
    manifest = json.loads((source / "manifest.json").read_text())
    media = json.loads((source / manifest["media"]).read_text())
    counter = manifest["recipes"]["counterspell"]
    selected = [
        (f"counterspell.{outcome}.q{quadrant}", key)
        for outcome in ("success", "failure")
        for quadrant, key in enumerate(counter[outcome])
    ]
    selected.append(("counterspell.dissipation", manifest["recipes"]["incoming_dissipation"]["media"]))
    folder = repo / "game/data/counterspell_media"
    binding_path, asset_path = folder / "bindings.json", folder / "projectile-assets.json"
    bindings = (json.loads(binding_path.read_text()) if binding_path.exists()
                else {"resources": {}, "projectileStorage": {}})
    assets = {row["assetId"]: row for row in json.loads(asset_path.read_text())} if asset_path.exists() else {}
    copied: set[Path] = set()

    def copy(relative: str) -> str:
        destination = MEDIA / relative
        if destination not in copied:
            (repo / destination).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, repo / destination)
            copied.add(destination)
        return destination.as_posix()

    for identity, key in selected:
        bank = media[key]
        width, height = bank["nativeSize"]
        pivot_x, pivot_y = bank["nativePivot"]
        parts = [[] if frame is None else [{
            "file": copy(bank["pages"][frame["page"]]),
            "rect": frame["source"],
            # Source atlas addresses are pivot-relative. Registered storage
            # subtracts the asset pivot while drawing, so restore it once here.
            "offset": [frame["offset"][0] + pivot_x, frame["offset"][1] + pivot_y],
        }] for frame in bank["frames"]]
        count, fps = len(parts), bank["fps"]
        assets[identity] = {
            "assetId": identity, "displayName": identity, "kind": "projectile",
            "sheet": f"/counterspell-media/{key}.png",
            "frame": {"width": width, "height": height, "rows": 8, "cols": count},
            "fps": fps, "rowOrder": list(DIRECTIONS),
            "phases": {"impact": {"start": 0, "frames": count, "fps": fps, "loop": False}},
            "anchor": {"x": pivot_x / width, "y": pivot_y / height},
            "defaultScale": 1,
            "palettePreview": {"colors": [0xFFFFFF] if key == "dissipation"
                               else [int(color, 16) for color in counter["palette"]]},
            "source": {"package": "abjuration-review", "asset": key,
                       "notes": "Lossless source atlas; offsets converted once from pivot-relative to native canvas."},
        }
        bindings["projectileStorage"][identity] = {"phases": {"impact": {
            "layers": [{"parts": parts, "blendMode": "normal"}],
        }}}

    bindings.setdefault("resources", {})["/counterspell-media/cast-hands.png"] = copy("actors/counterspell-hands.png")
    folder.mkdir(parents=True, exist_ok=True)
    binding_path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")
    asset_path.write_text(json.dumps(list(assets.values()), separators=(",", ":")) + "\n")
    return tuple(identity for identity, _key in selected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    imported = import_bundle(args.source)
    print(f"Imported {len(imported)} Counterspell media assets; no spell or interruption recipes changed.")


if __name__ == "__main__":
    main()
