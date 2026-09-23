"""Print initialized presentation coverage without creating an encounter or decoding art.

Run explicitly: python -m devtools.presentation_coverage > coverage.json
The full native/catalog imports belong to this developer command, not playback.
"""

import argparse
import json
import os
from pathlib import Path

# This command owns stdout as JSON, including imports that initialize Pygame.
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from dnd.content_system.spell_catalog_composition import SPELL_CATALOG_COMPOSITION_ROWS
from dnd.core.events import EventType
from game.animation_data import load_animation_data
from game.event_record import EVENT_MODELS
from game.presentation_coverage import presentation_inventory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rig", type=Path, action="append", default=[], help="Select an existing rig metadata file.")
    args = parser.parse_args()
    report = {
        "scope": "Initialized declarations; no encounter or media audit. This is not visual approval.",
        "event_categories": [category.value for category in EventType],
        "retained_models": sorted(EVENT_MODELS),
        "presentation": presentation_inventory(load_animation_data(rig_files=tuple(args.rig)), spell_ids=(
            row.declaration.ref.content_id for row in SPELL_CATALOG_COMPOSITION_ROWS)),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
