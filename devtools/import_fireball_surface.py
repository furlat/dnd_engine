"""Install the accepted paired Fireball color/XYZ delivery without authoring behavior."""

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def import_bundle(source: Path, repo: Path = ROOT) -> None:
    destination = repo / "game/assets/fireball_surface"
    # Keep every native sample available. Playback selects the approved 48-frame
    # schedule; copying packets changes neither pixels nor their geometry.
    for direction in ("E", "SE", "S", "SW", "W", "NW", "N", "NE"):
        folder = destination / direction
        folder.mkdir(parents=True, exist_ok=True)
        for frame in range(288):
            shutil.copyfile(source / "delivery" / direction / f"{frame:03d}.bin.gz",
                            folder / f"{frame:03d}.bin.gz")
    path = repo / "game/data/spell_recovery/bindings.json"
    bindings = json.loads(path.read_text())
    bindings["projectileStorage"]["shared.fireball.20ft-ground.smoke.v3"] = {
        "phases": {"impact": {"surfaceFrames": {
            "pattern": "game/assets/fireball_surface/{direction}/{frame:03d}.bin.gz",
            "frameIndices": [*range(0, 277, 6), 287],
            "bounds": [-16, 16], "verticalScale": 1.224744871391589,
            "blendModes": ["normal", "add"],
        }}}
    }
    path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    import_bundle(args.source)
    print("Installed all eight paired Fireball banks; existing recipe and timing retained.")
