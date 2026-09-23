"""Package the frozen area media without writing spell recipes or contacts."""

import argparse
import json
from pathlib import Path
import shutil

import pygame


ROOT = Path(__file__).resolve().parents[1]
DIRECTIONS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
CUBE_BANKS = {"E": "SE", "SE": "SE", "S": "SE", "SW": "SW",
              "W": "NW", "NW": "NW", "N": "NW", "NE": "NE"}


def cube_cell(bank: str, distance: int, lateral: int) -> tuple[int, int]:
    """Address the delivered cube's longitudinal/transverse storage cell."""
    return {"SE": (distance, lateral), "SW": (-lateral, distance),
            "NW": (-distance, -lateral), "NE": (lateral, -distance)}[bank]


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Dense frame-address metadata is generated media data, not recipe prose.
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n")


def _asset(identity: str, *, size: tuple[int, int], frames: int, fps: float,
           pivots: dict[str, list[float]], palette: list[list[int]]) -> dict:
    anchors = {direction: {"x": pivot[0] / size[0], "y": pivot[1] / size[1]}
               for direction, pivot in pivots.items()}
    return {
        "assetId": identity, "displayName": identity, "kind": "projectile",
        "sheet": f"/area-media/{identity}.png",
        "frame": {"width": size[0], "height": size[1], "rows": 8, "cols": frames},
        "fps": fps, "rowOrder": list(DIRECTIONS),
        "phases": {"impact": {"start": 0, "frames": frames, "fps": fps, "loop": False}},
        "anchor": anchors["S"], "anchorsByFacing": anchors,
        "defaultScale": .5,
        "palettePreview": {"colors": [r * 65536 + g * 256 + b for r, g, b in palette]},
    }


def _pack_slices(source: Path, pages: list[dict], bounds: dict, destination: Path,
                 repo: Path, frames: int) -> list[list[dict]]:
    """Remove transparent storage margins, retaining logical offsets/alpha."""
    result: list[list[dict]] = [[] for _ in range(frames)]
    page_size = 1024
    atlas = pygame.Surface((page_size, page_size), pygame.SRCALPHA)
    x = y = row_height = page_index = 0

    def save() -> None:
        destination.mkdir(parents=True, exist_ok=True)
        used_height = max(1, y + row_height)
        pygame.image.save(atlas.subsurface((0, 0, page_size, used_height)),
                          destination / f"{page_index:02}.png")

    for page in pages:
        sheet = pygame.image.load(source / "sheets" / page["file"])
        for local in range(page["frameCount"]):
            box = bounds[page["file"]][local]
            if box is None:
                continue
            left, top, right, bottom = box
            width, height = right - left, bottom - top
            if x + width > page_size:
                x, y, row_height = 0, y + row_height, 0
            if y + height > page_size:
                save()
                page_index += 1
                atlas = pygame.Surface((page_size, page_size), pygame.SRCALPHA)
                x = y = row_height = 0
            source_rect = (local % page["columns"] * 256 + left,
                           local // page["columns"] * 256 + top, width, height)
            # Copy pixels, rather than alpha-compositing them onto transparency.
            crop = sheet.subsurface(source_rect)
            pygame.surfarray.pixels3d(atlas)[x:x + width, y:y + height] = pygame.surfarray.array3d(crop)
            pygame.surfarray.pixels_alpha(atlas)[x:x + width, y:y + height] = pygame.surfarray.array_alpha(crop)
            result[page["firstFrame"] + local] = [{
                "file": (destination / f"{page_index:02}.png").relative_to(repo).as_posix(),
                "rect": [x, y, width, height], "offset": [left, top],
            }]
            x += width
            row_height = max(row_height, height)
    save()
    return result


def import_bundle(source: Path, *, repo: Path = ROOT) -> None:
    """Import selected media/registration; existing authored JSON is untouched."""
    data = repo / "game/data/area_spells"
    bindings_path = data / "bindings.json"
    bindings = json.loads(bindings_path.read_text()) if bindings_path.exists() else {"resources": {}, "spells": {}}
    assets_path = data / "projectile-assets.json"
    assets = {row["assetId"]: row for row in json.loads(assets_path.read_text())} if assets_path.exists() else {}
    storage = bindings.setdefault("projectileStorage", {})
    media = repo / "game/assets/area_spells"

    burning_root = source / "burning-hands-review"
    burning = json.loads((burning_root / "manifest.json").read_text())
    identity = "area.burning_hands.v9"
    pages = {}
    for direction in DIRECTIONS:
        pages[direction] = []
        for page in burning["directions"][direction]["pages"]:
            relative = Path("game/assets/area_spells/burning_hands") / page["file"]
            (repo / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(burning_root / page["file"], repo / relative)
            pages[direction].append({key: page[key] for key in ("firstFrame", "frameCount", "columns")} | {"file": relative.as_posix()})
    assets[identity] = _asset(identity, size=(burning["cell"], burning["cell"]),
        frames=burning["frames"], fps=burning["fps"], palette=burning["palette"],
        pivots={direction: burning["directions"][direction]["pivot"] for direction in DIRECTIONS})
    storage[identity] = {"phases": {"impact": {"layers": [{"pages": pages, "blendMode": "normal"}]}}}

    thunder_root = source / "aoe-crest-review"
    thunder = json.loads((thunder_root / "manifest.json").read_text())
    crest = thunder["spells"]["thunderwave"]
    bounds = json.loads((thunder_root / "frame-bounds.json").read_text())
    for distance in range(3):
        for lateral in range(-1, 2):
            for depth in ("back", "front"):
                identity = f"area.thunderwave.v10.{distance}.{lateral}.{depth}"
                parts = {}
                for bank in ("SE", "SW", "NW", "NE"):
                    cell = "_".join(map(str, cube_cell(bank, distance, lateral)))
                    row = crest["directions"][bank]
                    parts[bank] = _pack_slices(thunder_root, row["cells"][cell]["phases"][depth], bounds,
                        media / "thunderwave" / bank / cell / depth, repo, row["frames"])
                assets[identity] = _asset(identity, size=(thunder["cell"], thunder["cell"]),
                    frames=crest["directions"]["SE"]["frames"], fps=thunder["captureFps"],
                    pivots={direction: thunder["pivot"] for direction in DIRECTIONS}, palette=crest["palette"])
                storage[identity] = {"phases": {"impact": {"layers": [{
                    "partsByFacing": {direction: parts[CUBE_BANKS[direction]] for direction in DIRECTIONS},
                    "blendMode": "normal"}]}}}

    gust_root = source / "gust-wave-review"
    gust = json.loads((gust_root / "whole-manifest.json").read_text())
    identity = "area.gust_of_wind.v4"
    parts = {}
    for direction in DIRECTIONS:
        row = gust["directions"][direction]
        files = []
        for page in row["pages"]:
            relative = Path("game/assets/area_spells/gust_of_wind") / page
            (repo / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(gust_root / "whole-sheets" / page, repo / relative)
            files.append(relative.as_posix())
        parts[direction] = [[{"file": files[p], "rect": [x, y, w, h], "offset": [cx, cy]}
            for p, x, y, w, h, cx, cy in frame] for frame in row["frames"]]
    assets[identity] = _asset(identity, size=(1536, 1024), frames=gust["frames"], fps=gust["fps"],
        pivots={direction: gust["directions"][direction]["pivot"] for direction in DIRECTIONS}, palette=gust["palette"])
    storage[identity] = {"phases": {"impact": {"layers": [{"partsByFacing": parts, "blendMode": "normal"}]}}}

    for spell, original in (
        ("burning_hands", thunder_root / "actors/burning_hands/hand-glow.png"),
        ("thunderwave", thunder_root / "actors/thunderwave/Special1-glow.png"),
        ("gust_of_wind", gust_root / "actors/gust_of_wind/hand-glow.png"),
    ):
        destination = media / "caster" / f"{spell}-weaponGlow.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
        bindings["resources"][f"/area-media/{spell}-weaponGlow.png"] = destination.relative_to(repo).as_posix()
    _write(bindings_path, bindings)
    _write(assets_path, list(assets.values()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    import_bundle(args.source)
    print("Packaged area media and registration; spell recipes retained.")


if __name__ == "__main__":
    main()
