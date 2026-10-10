"""Pack unchanged original Unity wall debris, retaining its finite source clock."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image
from devtools.media_delivery import install_verified_payloads

ROOT = Path(__file__).resolve().parents[1]


def import_wall_debris(source: Path, output: Path = ROOT, *,
                       preserved: Path | None = None, production: Path | None = None) -> None:
    if (preserved is None) != (production is None):
        raise ValueError("Preservation and private production destinations must be supplied together")
    declarations = json.loads((ROOT / "game/data/solid_wall_media_sources.json").read_text())
    registration = output / "game/data/environment_art.json"
    document = json.loads(registration.read_text())
    media = output / "game/assets/environment/wall_debris"
    media.mkdir(parents=True, exist_ok=True)
    receipt = {}
    for identity, row in declarations["effects"].items():
        originals = [source / row["folder"] / f"{index:04}.png" for index in range(1, 32, 2)]
        sheet = Image.new("RGBA", (4 * 256, 4 * 256))
        for index, path in enumerate(originals):
            with Image.open(path) as image:
                if image.size != (256, 256):
                    raise ValueError(f"Unexpected original effect canvas: {path}")
                sheet.paste(image.convert("RGBA"), ((index % 4) * 256, (index // 4) * 256))
        relative = f"environment/wall_debris/{identity}.png"
        sheet.save(output / "game/assets" / relative, optimize=True)
        frames = [{"path": relative, "rect": [(i % 4) * 256, (i // 4) * 256, 256, 256]}
                  for i in range(16)]
        document["banks"][identity] = {
            "cell": [256, 256], "ground_pivot": row["pivot"],
            "pivots_by_pose": {pose: row["pivot"] for pose in "eswn"},
            "rows": list("eswn"), "scale": 128 / declarations["pixels_per_unit"],
            "frame_count": 16, "fps": declarations["fps"],
            "duration_ms": declarations["cleanup_ms"], "state_change_frame": 0,
            "clear_at_end": True,
            # Source uses the same unrotated effect for all four TileData poses.
            "frames_by_pose": {pose: frames for pose in "eswn"},
        }
        receipt[identity] = {"files": {str(path): sha256(path.read_bytes()).hexdigest() for path in originals},
            "packed_sha256": sha256((output / "game/assets" / relative).read_bytes()).hexdigest()}
    document["wall_destructions"] = declarations["wall_destructions"]
    for item_id, identity in declarations["props"].items():
        document["props"][item_id]["destructions"] = {"default": identity}
    registration.write_text(json.dumps(document, indent=2) + "\n")
    (media / "source-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if preserved is not None and production is not None:
        payloads = tuple((path.name, f"game/assets/environment/wall_debris/{path.name}",
                          sha256(path.read_bytes()).hexdigest()) for path in sorted(media.iterdir()) if path.is_file())
        install_verified_payloads(media, payloads, preserved=preserved, production=production, repo=output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT)
    parser.add_argument("--preserved", type=Path)
    parser.add_argument("--production", type=Path)
    args = parser.parse_args()
    import_wall_debris(args.source, args.output, preserved=args.preserved, production=args.production)
