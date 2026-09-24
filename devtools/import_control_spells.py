"""Package reviewed control-spell pixels and phase views, never spell recipes.

Application/removal windows are views into original atlas pages. Shared glyph
media retains one frame-address sequence; Color Spray retains all eight views.
"""

import argparse
import json
from pathlib import Path
import shutil

from devtools.media_delivery import owns_selected_media


ROOT = Path(__file__).resolve().parents[1]
MEDIA = Path("game/assets/control_spells")
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
CASTS = ("charmed", "blinded", "deafened", "command", "silence", "color_spray")


def _read(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def import_bundle(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    """Import the explicit final control selection and self-contained Sleep loop."""
    catalog = json.loads((source / "media.json").read_text())
    lifecycle = json.loads((source / "lifecycle-contract.json").read_text())
    actors = json.loads((source / "actors.json").read_text())
    directions = json.loads((source / "color-directions.json").read_text())
    hands = json.loads((source / "color-hand-anchors.json").read_text())
    sleep_root = source / "sleep-sustain-v1"
    sleep = json.loads((sleep_root / "manifest.json").read_text())
    folder = repo / "game/data/control_spells"
    bindings = _read(folder / "bindings.json", {"resources": {}, "projectileStorage": {}})
    assets = {row["assetId"]: row for row in _read(folder / "projectile-assets.json", [])}
    storage = bindings.setdefault("projectileStorage", {})
    resources = bindings.setdefault("resources", {})
    copied: set[Path] = set()
    imported: list[str] = []

    def copy(root: Path, group: str, relative: str) -> str:
        destination = MEDIA / group / relative
        if destination not in copied:
            (repo / destination).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative, repo / destination)
            copied.add(destination)
        return destination.as_posix()

    def pack(name: str, row: dict, palette: list[str], *, first: int = 0,
             frames: int | None = None, loop: bool = False,
             views: dict | None = None, root: Path = source, group: str = "catalog") -> None:
        count = row["frames"] - first if frames is None else frames
        pivot, cell, fps = row["pivot"], row["cell"], row["fps"]
        anchor = {"x": pivot[0] / cell, "y": pivot[1] / cell}

        def parts(view: dict, depth: str) -> list[list[dict]]:
            layer = view["layers"][depth]
            result = []
            for frame in range(first, first + count):
                bound = layer["bounds"][frame]
                if bound is None:
                    result.append([])
                    continue
                left, top, right, bottom = bound
                local = frame % layer["perPage"]
                file = copy(root, group, layer["pages"][frame // layer["perPage"]])
                result.append([{"file": file, "rect": [
                    local % layer["columns"] * cell + left,
                    local // layer["columns"] * cell + top, right - left, bottom - top],
                    "offset": [left, top]}])
            return result

        for depth in ("back", "front"):
            identity = f"control.{name}.{depth}"
            if not owns_selected_media(storage, identity, MEDIA.as_posix()):
                continue
            assets[identity] = {
                "assetId": identity, "displayName": identity, "kind": "projectile",
                "sheet": f"/control-spells/{name}/{depth}.png",
                "frame": {"width": cell, "height": cell, "rows": 8, "cols": count},
                "fps": fps, "rowOrder": list(DIRECTIONS),
                "phases": {"impact": {"start": 0, "frames": count, "fps": fps, "loop": loop}},
                "anchor": anchor, "defaultScale": row["scale"] / 2,
                "palettePreview": {"colors": [int(color, 16) for color in palette]},
                "source": {"package": "control-spells-review", "asset": name,
                    "notes": f"Original atlas samples {first} through {first + count - 1}; unchanged RGBA and full-cell pivot."},
            }
            if views is None:
                layer = {"parts": parts(row, depth), "blendMode": "normal"}
            else:
                layer = {"partsByFacing": {facing: parts(views[facing], depth)
                                          for facing in DIRECTIONS}, "blendMode": "normal"}
                assets[identity]["anchorsByFacing"] = {
                    facing: {"x": view["pivot"][0] / cell, "y": view["pivot"][1] / cell}
                    for facing, view in views.items()}
            storage[identity] = {"phases": {"impact": {"layers": [layer]}}}
            imported.append(identity)

    for name in ("charm_flower", "charm_hearts"):
        pack(name, catalog[name], actors["charmed"]["palette"])
    for name in ("charmed", "blinded", "deafened", "command"):
        phases = lifecycle["conditions"][name]
        palette = actors[name]["palette"]
        pack(f"{name}.sustain", catalog[phases["sustain"]["asset"]], palette, loop=True)
        if name == "charmed":
            continue  # Flower/hearts are the separately retained application media.
        for phase in ("application", "clear", *(["execute"] if "execute" in phases else [])):
            spec = phases[phase]
            first, last = spec["frames"]
            label = "removal" if phase == "clear" else phase
            pack(f"{name}.{label}", catalog[spec["asset"]], palette,
                 first=first, frames=last - first + 1)
    for phase in ("application", "sustain"):
        spec = lifecycle["silence"][phase]
        first, last = spec["frames"]
        pack(f"silence.{phase}", catalog[spec["asset"]], actors["silence"]["palette"],
             first=first, frames=last - first + 1, loop=phase == "sustain")
    pack("sleep.sustain", sleep, sleep["palette"], loop=True, root=sleep_root, group="sleep")
    # The original cone contains the preview actor's ground-to-hand offset.
    # Register that exact emitted point so the recipe can attach it to a hand
    # at any actor scale without applying that baked displacement twice.
    color_views = {facing: {**view, "pivot": [view["pivot"][axis] + hands[facing][axis] / view["scale"]
                                           for axis in (0, 1)]}
                   for facing, view in directions.items()}
    pack("color_spray", color_views["SE"], actors["color_spray"]["palette"], views=color_views)
    for name in CASTS:
        resources[f"/control-spells/{name}/cast.png"] = copy(source, "catalog", f"actors/{name}-hands.png")

    folder.mkdir(parents=True, exist_ok=True)
    # Frame-address metadata is generated storage, kept compact. Authored
    # spell/condition recipes and existing resource owners remain untouched.
    for name, document in (("bindings.json", bindings), ("projectile-assets.json", list(assets.values()))):
        (folder / name).write_text(json.dumps(document, separators=(",", ":")) + "\n")
    return tuple(imported)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    imported = import_bundle(args.source)
    print(f"Imported {len(imported)} control media views; authored recipes retained.")


if __name__ == "__main__":
    main()
