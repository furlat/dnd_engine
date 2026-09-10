"""Play an in-process encounter, or open an explicit cast regression reference."""

import argparse
import os
from pathlib import Path

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from game.play import run
from game.encounter_play import run as run_encounter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true", help="use SDL dummy and a bounded frame run")
    parser.add_argument("--reference", action="store_true", help="open the finite cast regression scene")
    parser.add_argument("--frames", type=int, help="stop after this many displayed frames")
    parser.add_argument("--capture-dir", type=Path, help="save actual displayed frames")
    parser.add_argument("--quadrant", type=int, choices=range(4), default=0)
    outcome = parser.add_mutually_exclusive_group()
    outcome.add_argument("--miss-second", action="store_true", help="use a legal missed second attack")
    outcome.add_argument("--lethal", action="store_true", help="use a real Goblin recipient killed by the second hit")
    parser.add_argument("--goblin", action="store_true", help="use a real Goblin recipient for one hit followed by one miss")
    parser.add_argument("--replace-weapon", action="store_true", help="replace a dagger with a shortsword between the casts")
    parser.add_argument("--magic-missile", action="store_true", help="cast three ordered darts at A/B/A in each turn")
    args = parser.parse_args()
    if args.magic_missile and (args.miss_second or args.lethal or args.goblin):
        parser.error("--magic-missile uses two living modular targets; omit the Fire Bolt outcome options")
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    if not (args.reference or args.magic_missile or args.miss_second or args.lethal or args.goblin or args.replace_weapon):
        game = run_encounter(
            frame_deltas=(1 / 60,) if args.headless else None,
            max_frames=args.frames or (120 if args.headless else None),
            capture_dir=args.capture_dir, quadrant=args.quadrant,
        )
        print(f"commands={game.player_commands} lineages={len(game.lineages)} "
              f"historical_matches_latest={game.latest == game.historical}")
        return
    summary = run(
        frame_deltas=(1 / 60,) if args.headless else None,
        max_frames=args.frames or (1200 if args.headless else None),
        exit_when_complete=args.headless,
        capture_dir=args.capture_dir,
        quadrant=args.quadrant,
        miss_second=args.miss_second,
        goblin_recipient=args.goblin,
        lethal_second=args.lethal,
        replace_weapon=args.replace_weapon,
        magic_missile=args.magic_missile,
    )
    print(f"casts={summary.completed_casts}/2 historical_matches_latest={summary.latest == summary.historical}")


if __name__ == "__main__":
    main()
