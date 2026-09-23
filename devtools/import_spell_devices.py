"""Copy the artist's device sheets and measured attachment data for playback.

This offline adapter owns media packaging only. Spell grants, target rules and
projectile recipes remain outside the device artwork document.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
PITCHES = (0, 15, 30, 45)
AUTHORED_DATA = ROOT / "game" / "data" / "spell_devices.json"


def import_spell_devices(source: Path, output_root: Path,
                         authored_data: Path = AUTHORED_DATA) -> Path:
    """Package two body banks without importing any engine or renderer code."""
    document = json.loads(authored_data.read_text(encoding="utf-8"))
    for body in ("cannon", "arcane"):
        banks = []
        for pitch in PITCHES:
            source_bank = source / f"{body}-pitch{pitch}"
            metadata = json.loads((source_bank / "metadata.json").read_text())
            frames = {
                (frame["camera_quadrant"], frame["row"], frame["column"]): frame
                for frame in metadata["frames"]
            }
            relative_bank = Path("environment") / "spell_devices" / source_bank.name
            destination = output_root / "game" / "assets" / relative_bank
            destination.mkdir(parents=True, exist_ok=True)
            sheets = []
            for quadrant in range(4):
                filename = f"sheet-q{quadrant}.png"
                shutil.copyfile(source_bank / metadata["sheets"][str(quadrant)], destination / filename)
                sheets.append((relative_bank / filename).as_posix())
            row_count = len(metadata["rows"])
            frame_count = metadata["columns"]
            release_frame = metadata["release_column"]
            banks.append({
                "pitchDegrees": metadata["elevation_degrees"],
                "sheets": sheets,
                "muzzlePixels": [
                    [[frames[quadrant, row, frame]["muzzle_pixels"]
                      for frame in range(frame_count)] for row in range(row_count)]
                    for quadrant in range(4)
                ],
                "forwardScreen": [
                    [frames[quadrant, row, release_frame]["screen_forward"]
                     for row in range(row_count)]
                    for quadrant in range(4)
                ],
                "muzzleHeightStepsByRow": [
                    # Four camera views cancel planar displacement; the map
                    # projects one elevation step as 64 unscaled pixels.
                    (metadata["anchor"][1] - sum(
                        frames[quadrant, row, release_frame]["muzzle_pixels"][1]
                        for quadrant in range(4)
                    ) / 4) / 64
                    for row in range(row_count)
                ],
            })
            if pitch == 0:
                document["devices"][body].update({
                    "cell": metadata["cell"],
                    "anchor": metadata["anchor"],
                    "rows": [row.upper() for row in metadata["rows"]],
                    "fps": round(1000 / metadata["frame_ms"]),
                    "releaseFrame": release_frame,
                    "frameCount": frame_count,
                    "pitchBanks": banks,
                })
    output = output_root / "game" / "data" / "spell_devices.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return output


def import_device_destruction(source: Path, output_root: Path,
                              authored_data: Path = AUTHORED_DATA) -> Path:
    """Register approved breakdown sheets without choosing gameplay remnant IDs."""
    document = json.loads(authored_data.read_text(encoding="utf-8"))
    for body in ("cannon", "arcane"):
        authored = document["devices"][body]["destruction"]
        banks = []
        for suffix in (*[f"pitch{pitch}" for pitch in PITCHES], "wreck"):
            source_bank = source / f"{body}-{suffix}"
            metadata = json.loads((source_bank / "metadata.json").read_text())
            relative = Path("environment/spell_devices/destruction") / source_bank.name
            destination = output_root / "game/assets" / relative
            destination.mkdir(parents=True, exist_ok=True)
            sheets = []
            for quadrant in range(4):
                filename = f"sheet-q{quadrant}.png"
                shutil.copyfile(source_bank / metadata["sheets"][str(quadrant)], destination / filename)
                sheets.append((relative / filename).as_posix())
            if suffix == "wreck":
                authored["wreckSheets"] = sheets
            else:
                banks.append({"pitchDegrees": metadata["elevation_degrees"], "sheets": sheets})
                authored["fps"] = metadata["fps"]
                authored["frameCount"] = metadata["columns"]
        authored["pitchBanks"] = banks
    output = output_root / "game/data/spell_devices.json"
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="Artist weapon-workshop directory containing both pitch banks.")
    parser.add_argument("--output-root", type=Path, default=ROOT,
                        help="Repository root receiving the packaged media and data.")
    parser.add_argument("--authored-data", type=Path, default=AUTHORED_DATA,
                        help="Canonical device settings preserved while media is reimported.")
    parser.add_argument("--destruction", action="store_true", help="Import breakdown/wreck media into existing authored destruction bindings.")
    args = parser.parse_args()
    importer = import_device_destruction if args.destruction else import_spell_devices
    output = importer(args.source, args.output_root, args.authored_data)
    print(f"Imported device media registration to {output}")


if __name__ == "__main__":
    main()
