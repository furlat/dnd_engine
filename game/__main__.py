"""Play an encounter with an isolated rules worker. Cast regressions: python -m game.reference."""

import argparse
import os
from pathlib import Path

from game.encounter_play import run as run_encounter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--encounter", choices=("encounter.lantern_crypt", "encounter.storehouse_demo", "encounter.residue_workshop"),
                        default="encounter.lantern_crypt", help="default: The Lantern Crypt, with Fighter and Sorcerer")
    parser.add_argument("--headless", action="store_true", help="use SDL dummy and a bounded frame run")
    parser.add_argument("--frames", type=int, help="stop after this many displayed frames")
    parser.add_argument("--capture-dir", type=Path, help="save actual displayed frames")
    parser.add_argument("--quadrant", type=int, choices=range(4), default=0)
    parser.add_argument("--fullscreen", action="store_true", help="use the current monitor's desktop resolution")
    parser.add_argument("--quick-start", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    while True:
        game = run_encounter(
            encounter_id=args.encounter,
            frame_deltas=(1 / 60,) if args.headless else None,
            max_frames=args.frames or (120 if args.headless else None),
            capture_dir=args.capture_dir, quadrant=args.quadrant, fullscreen=args.fullscreen,
        )
        print(f"commands={game.player_commands} lineages={len(game.lineages)} "
              f"historical_matches_latest={game.latest == game.historical}")
        if not game.restart_requested:
            break


if __name__ == "__main__":
    main()
