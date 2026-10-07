"""Index effective selected presentation identities; never decode media pixels.

Run as a module from the repository root using runpy.run_path(...).
"""

import json
from pathlib import Path

from pydantic import TypeAdapter

from game.assets import load_catalog
from game.animation_data import load_animation_data
from game.animation_types import AnimationData


OUT = Path(__file__).resolve().parent
FIELDS = (
    "devices", "device_wrecks", "drafts", "attack_recipes", "shove_recipes",
    "body_action_recipes", "body_action_bindings", "condition_recipes", "condition_media",
    "projectile_assets", "projectile_storage", "resources", "rigs", "creature_rigs",
    "shove_feedback", "vfx_source_hues", "world_animations", "spatial_media",
    "action_media_assets", "body_release_media", "portals", "blood_responses",
    "action_playback_rates", "action_deliveries", "deposit_media", "concentration_media",
    "construction_media", "body_materials", "entity_lifecycle_media", "item_attachments",
    "action_materials", "action_intakes",
)


def main():
    catalog = load_catalog()
    data = load_animation_data(rig_files=tuple(sorted(Path("game/data/rigs").glob("*.json"))),
                               world_source=catalog.world_source)
    exported = json.loads(TypeAdapter(AnimationData).dump_json(data, warnings="error"))
    selected = {key: sorted(exported[key]) for key in FIELDS}
    (OUT / "selected-content-index.json").write_text(json.dumps({
        "status": "effective identity inventory; aliases/shared selections are not unique spells or proof of runtime correctness",
        "families": selected,
        "counts": {key: len(value) for key, value in selected.items()},
    }, indent=2) + "\n")
    print(json.dumps({key: len(value) for key, value in selected.items()}))


if __name__ == "__main__":
    main()
