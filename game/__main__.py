"""Play an in-process encounter. Cast regressions: python -m game.reference."""

import argparse
import os
from pathlib import Path

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from game.encounter_play import run as run_encounter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--encounter", choices=("encounter.residue_workshop",),
                        help="play the authored Blood and Bone Workshop; default is the Goblin skirmish")
    parser.add_argument("--headless", action="store_true", help="use SDL dummy and a bounded frame run")
    parser.add_argument("--frames", type=int, help="stop after this many displayed frames")
    parser.add_argument("--capture-dir", type=Path, help="save actual displayed frames")
    parser.add_argument("--quadrant", type=int, choices=range(4), default=0)
    args = parser.parse_args()
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    game = run_encounter(
        encounter_id=args.encounter,
        frame_deltas=(1 / 60,) if args.headless else None,
        max_frames=args.frames or (120 if args.headless else None),
        capture_dir=args.capture_dir, quadrant=args.quadrant,
    )
    print(f"commands={game.player_commands} lineages={len(game.lineages)} "
          f"historical_matches_latest={game.latest == game.historical}")


if __name__ == "__main__":
    main()
