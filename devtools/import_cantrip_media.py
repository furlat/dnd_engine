"""Copy explicitly selected cantrip media, leaving authored recipes unchanged.

Ordinary current intake selects the bundle and its delivered projectile updates
together: --source BUNDLE --selected-projectile PROJECTILE_DELIVERY.
--bundle-only deliberately selects the older bundle without those updates.
"""

import argparse
import json
from pathlib import Path
import shutil

from devtools.import_spell_recovery import asset


ROOT = Path(__file__).resolve().parents[1]


def import_bundle(source: Path, *, projectile_sources: tuple[Path, ...], repo: Path = ROOT) -> None:
    """Import a selected bundle plus explicit replacement phase-page deliveries.

    An empty tuple deliberately selects the bundle alone. Requiring this choice
    prevents an old bare invocation from silently restoring its impact-only media.
    """
    manifest = json.loads((source / "review-sheets/manifest.json").read_text())
    selected = {json.loads((path / "manifest.json").read_text())["assetId"]: path
                for path in projectile_sources}
    folder = repo / "game/data/cantrips"
    bindings = json.loads((folder / "bindings.json").read_text())
    assets = {row["assetId"]: row for row in json.loads((folder / "projectile-assets.json").read_text())}
    for spell in manifest["spells"]:
        name = spell["id"]
        colors = [r * 65536 + g * 256 + b for r, g, b in spell["palette"]["colors"]]
        for name_phase, phase in spell["phases"].items():
            identity = f"cantrip.{name}.{name_phase}"
            if identity in selected:
                continue
            size = phase["cell"]
            delivered = asset(identity, f"{name} {name_phase}", size, spell["directions"],
                {"impact": {"start": 0, "frames": phase["frames"], "fps": phase["fps"], "loop": False}}, colors)
            record = assets.setdefault(identity, delivered)
            record.update({key: delivered[key] for key in ("frame", "fps", "rowOrder", "phases", "palettePreview")})
            record["anchor"] = {"x": phase["pivot"][0] / size, "y": phase["pivot"][1] / size}
            record["anchorsByFacing"] = {direction: record["anchor"] for direction in spell["directions"]}
            pages = {}
            for direction, entries in phase["pages"].items():
                pages[direction] = []
                for page in entries:
                    path = Path("game/assets/cantrips") / page["file"]
                    (repo / path).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source / "review-sheets" / page["file"], repo / path)
                    pages[direction].append({"file": path.as_posix(), **{key: page[key]
                        for key in ("firstFrame", "frameCount", "columns")}})
            bindings["projectileStorage"][identity] = {"phases": {"impact": {"layers": [
                {"pages": pages, "blendMode": "normal"}]}}}
        glow = "Special1-glow.png" if name == "sacred_flame" else "hand-glow.png"
        relative = Path("game/assets/cantrips") / name / glow
        (repo / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / "actors" / name / glow, repo / relative)
        bindings["resources"][f"/cantrips/{name}/cast.png"] = relative.as_posix()
    (folder / "bindings.json").write_text(json.dumps(bindings, indent=2) + "\n")
    (folder / "projectile-assets.json").write_text(json.dumps(list(assets.values()), indent=2) + "\n")
    for path in selected.values():
        import_projectile_media(path, repo=repo)


def import_projectile_media(source: Path, *, repo: Path = ROOT) -> None:
    """Replace one delivered phase-page asset, preserving authored behavior."""
    manifest = json.loads((source / "manifest.json").read_text())
    identity = manifest["assetId"]
    folder = repo / "game/data/cantrips"
    bindings = json.loads((folder / "bindings.json").read_text())
    assets = json.loads((folder / "projectile-assets.json").read_text())
    record = next(row for row in assets if row["assetId"] == identity)
    cell = manifest["cell"]
    anchor = {"x": manifest["pivot"][0] / cell, "y": manifest["pivot"][1] / cell}
    phases = {name: {"start": 0, **{key: phase[key] for key in ("frames", "fps", "loop")}}
              for name, phase in manifest["phases"].items()}
    record.update(frame={"width": cell, "height": cell, "rows": len(manifest["directions"]),
                         "cols": max(phase["frames"] for phase in phases.values())},
                  fps=phases["travel"]["fps"], rowOrder=manifest["directions"],
                  anchor=anchor, anchorsByFacing={facing: anchor for facing in manifest["directions"]},
                  phases=phases,
                  palettePreview={"colors": [r*65536 + g*256 + b for r,g,b in manifest["palette"]["colors"]]})
    destination = Path("game/assets/cantrips/projectiles") / identity
    storage = {}
    for name, phase in manifest["phases"].items():
        pages = {}
        for facing, entries in phase["pages"].items():
            pages[facing] = []
            for page in entries:
                relative = destination / page["file"]
                (repo / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / page["file"], repo / relative)
                pages[facing].append({"file": relative.as_posix(), **{key: page[key]
                    for key in ("firstFrame", "frameCount", "columns")}})
        storage[name] = {"layers": [{"pages": pages, "blendMode": "normal"}]}
    bindings["projectileStorage"][identity] = {"phases": storage}
    (folder / "bindings.json").write_text(json.dumps(bindings, indent=2) + "\n")
    (folder / "projectile-assets.json").write_text(json.dumps(assets, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT, help="Checkout or temporary output containing existing authoring.")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--projectile-media", action="store_true", help="Import --source as one selected phase-page asset.")
    selection.add_argument("--bundle-only", action="store_true", help="Explicitly select the bundle without projectile replacements.")
    selection.add_argument("--selected-projectile", type=Path, action="append", default=[],
                           help="Selected phase-page delivery replacing the same bundle asset; repeat for separate assets.")
    args = parser.parse_args()
    if args.projectile_media:
        import_projectile_media(args.source, repo=args.output_root)
    else:
        import_bundle(args.source, projectile_sources=tuple(args.selected_projectile), repo=args.output_root)


if __name__ == "__main__":
    main()
