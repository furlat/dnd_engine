"""Register released fire atlas windows; gameplay and recipes remain separate."""

import argparse
import json
from pathlib import Path


from devtools.import_registered_media import import_registered_bank


ROOT = Path(__file__).resolve().parents[1]


def import_continual_flame(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    """Install the accepted fixed-origin bank, preserving both layer registrations."""
    row = json.loads((source / "media.json").read_text())["continual_anchor_v41_0"]
    if (row["frames"], row["fps"], row["hold"]) != (112, 32, [48, 112]):
        raise ValueError("Continual Flame requires the released 48-frame onset and 64-frame hold")
    if not row["fixedFlameBase"]:
        raise ValueError("Continual Flame requires a fixed flame origin")
    return import_registered_bank(source, row, "continual_flame", (("apply", 0, 48), ("hold", 48, 64)), repo, bundle="fire_media")


def import_flame_strike(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    """Install the finite native pillar without changing its mechanical footprint."""
    row = json.loads((source / "media.json").read_text())["flame_strike"]
    if (row["frames"], row["fps"], row["radiusFeet"], row["heightFeet"]) != (96, 32, 10, 40):
        raise ValueError("Flame Strike requires the released 96-frame ten-foot pillar")
    return import_registered_bank(source, row, "flame_strike", (("finite", 0, 96),), repo, bundle="fire_media")




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--program", choices=("continual_flame", "flame_strike"), default="continual_flame")
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args()
    importer = import_continual_flame if args.program == "continual_flame" else import_flame_strike
    print(f"Registered {len(importer(args.source, repo=args.repo))} {args.program} phase layers")
