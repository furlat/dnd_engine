"""Package declared prop media; native behavior and media bindings stay authored.

Read the accepted metadata paths, preserving pivots, timing and actual pixels.
No source hashes, discovery scan, gameplay inference, or runtime validation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import pygame


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DECLARATIONS = ROOT / "game/data/environment_prop_sources.json"


def import_environment_props(source: Path, output_root: Path,
                             declarations: Path = SOURCE_DECLARATIONS) -> Path:
    authored = json.loads(declarations.read_text())
    approved = {row["metadata"] for row in json.loads((source / "reviewed-manifest.json").read_text())["banks"]}
    output = output_root / "game/data/environment_art.json"
    document = json.loads(output.read_text())
    for identity, row in authored["banks"].items():
        metadata_path = row["metadata"]
        if metadata_path not in approved:
            raise ValueError(f"Prop bank is absent from accepted manifest: {metadata_path}")
        metadata_file = source / metadata_path
        metadata = json.loads(metadata_file.read_text())
        relative = Path("environment/props") / identity
        destination = output_root / "game/assets" / relative
        destination.mkdir(parents=True, exist_ok=True)
        sheet = metadata_file.parent / metadata.get("sheet", "sheet.png")
        shutil.copyfile(sheet, destination / "break.png")
        intact = metadata_file.parent / "intact.png"
        if intact.is_file():
            shutil.copyfile(intact, destination / "intact.png")
        else:
            # Exact frame-zero camera column, not a substitute static sprite.
            image = pygame.image.load(sheet)
            column = image.subsurface((0, 0, metadata["cell"][0], metadata["cell"][1] * len(metadata["rows"])))
            pygame.image.save(column, destination / "intact.png")
        common = {
            "cell": metadata["cell"], "ground_pivot": metadata["pivot"],
            "pivots_by_pose": {pose: metadata["pivot"] for pose in metadata["rows"]},
            "rows": metadata["rows"], "scale": row["scale"], "fps": metadata["fps"],
        }
        document["banks"][f"prop.{identity}.intact"] = {
            **common, "path": (relative / "intact.png").as_posix(),
            "frame_count": 1, "duration_ms": 0,
        }
        document["banks"][f"prop.{identity}.break"] = {
            **common, "path": (relative / "break.png").as_posix(),
            "frame_count": metadata["columns"], "duration_ms": metadata["columns"] * 1000 / metadata["fps"],
            **({"release_frame": row["release_frame"]} if "release_frame" in row else {}),
            **({"state_change_frame": row["state_change_frame"]} if "state_change_frame" in row else {}),
        }
    output.write_text(json.dumps(document, indent=2) + "\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(import_environment_props(args.source, args.output_root))


if __name__ == "__main__":
    main()
