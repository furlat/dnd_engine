"""Copy the selected spell deliveries into existing paged media storage.

Direction supplements publish complete components progressively. Only their
listed components are imported; authored recipes and gameplay remain separate.
"""

import argparse
import json
from pathlib import Path
import shutil

from devtools.media_delivery import owns_selected_media


ROOT = Path(__file__).resolve().parents[1]
MEDIA = Path("game/assets/pending_spells")


def _read(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def import_bundle(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    """Import finite spells and currently published buff/movement components."""
    folder = repo / "game/data/pending_spells"
    assets = {row["assetId"]: row for row in _read(folder / "projectile-assets.json", [])}
    bindings = _read(folder / "bindings.json", {"resources": {}, "projectileStorage": {}})
    storage = bindings.setdefault("projectileStorage", {})
    resources = bindings.setdefault("resources", {})
    imported: list[str] = []

    def copy(root: Path, group: str, relative: str) -> str:
        destination = MEDIA / group / relative
        (repo / destination).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, repo / destination)
        return destination.as_posix()

    def layer(root: Path, group: str, name: str, depth: str, *, cell, pivot,
              frames: int, fps: float, directions, palette, loop: bool, pages) -> None:
        identity = f"pending.{name}.{depth}"
        if not owns_selected_media(storage, identity, MEDIA.as_posix()):
            return
        anchor = {"x": pivot[0] / cell[0], "y": pivot[1] / cell[1]}
        assets[identity] = {
            "assetId": identity, "displayName": name.replace("_", " ").title() + " · " + depth,
            "kind": "projectile", "sheet": f"/pending-spells/{name}/{depth}.png",
            "frame": {"width": cell[0], "height": cell[1], "rows": 8, "cols": frames},
            "fps": fps, "rowOrder": directions,
            "phases": {"impact": {"start": 0, "frames": frames, "fps": fps, "loop": loop}},
            "anchor": anchor, "anchorsByFacing": {facing: anchor for facing in directions},
            "defaultScale": .5, "palettePreview": {"colors": [int(color, 16) for color in palette]},
        }
        packed = {facing: [{"file": copy(root, group, page["file"]),
                           "firstFrame": page["firstFrame"],
                           "frameCount": min(page["frameCount"], frames - page["firstFrame"]),
                           "columns": page["columns"]}
                          for page in pages[facing] if page["firstFrame"] < frames]
                  for facing in directions}
        storage[identity] = {"phases": {"impact": {
            "layers": [{"pages": packed, "blendMode": "normal"}]}}}

    finite = source / "delivery-next-spells-directions-v1"
    for spell in json.loads((finite / "manifest.json").read_text())["spells"]:
        name, count = spell["id"], spell["frames"]
        directions = list(spell["directions"])
        for depth in ("back", "front"):
            pages = {facing: [{"file": path, "firstFrame": index * spell["framesPerPage"],
                              "frameCount": min(spell["framesPerPage"], count - index * spell["framesPerPage"]),
                              "columns": spell["columns"]}
                             for index, path in enumerate(spell["directions"][facing]["layers"][depth])]
                     for facing in directions}
            layer(finite, "finite", name, depth, cell=spell["frameSize"], pivot=spell["pivot"],
                  frames=count, fps=spell["fps"], directions=directions, palette=spell["palette"],
                  loop=False, pages=pages)
        imported.append(name)

    for group in ("buffs", "movement"):
        supplement = source / f"delivery-{group}-directions-v1"
        manifest = _read(supplement / "manifest.json", None)
        if manifest is None:
            continue
        for name, component in manifest["components"].items():
            for depth in ("back", "front"):
                pages = {facing: component["directions"][facing]["layers"][depth]["pages"]
                         for facing in manifest["directions"]}
                layer(supplement, group, name, depth, cell=manifest["cell"], pivot=manifest["groundPivot"],
                      frames=component["playbackFrames"], fps=manifest["fps"],
                      directions=manifest["directions"], palette=component["spec"]["palette"],
                      loop=component["kind"] == "loop", pages=pages)
            imported.append(name)

    # Isolated caster magic comes from the original pack, not its review actor.
    buff_root = source / "buffs-review"
    buff_manifest = _read(buff_root / "delivery/manifest.json", {"spells": []})
    for spell in buff_manifest["spells"]:
        if spell["id"] in imported and spell["stage"] == "application":
            resources[f"/pending-spells/{spell['id']}/cast.png"] = copy(
                buff_root, "buffs", spell["cast"]["sourceLayer"])
    for name in ("jump", "retreat", "haste"):
        if name in imported:
            resources[f"/pending-spells/{name}/cast.png"] = copy(
                source / "movement-review", "movement", f"actors/{name}-hands.png")

    folder.mkdir(parents=True, exist_ok=True)
    for name, value in (("projectile-assets.json", list(assets.values())), ("bindings.json", bindings)):
        (folder / name).write_text(json.dumps(value, indent=2) + "\n")
    return tuple(imported)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vfx-root", required=True, type=Path)
    imported = import_bundle(parser.parse_args().vfx_root)
    print("Imported published spell media: " + ", ".join(imported))


if __name__ == "__main__":
    main()
