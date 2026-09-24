"""Install paired AoE delivery packets; retain authored clocks and contact rules."""

import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
FACINGS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
# Existing cardinal cube banks: diagonal aim uses the same native cube as before.
CUBE_BANKS = dict(zip(FACINGS, ("SE", "SE", "SE", "SW", "NW", "NW", "NW", "NE")))
BUNDLES = (
    ("burning", "area_spells", "area.burning_hands.v9", None),
    ("gust", "area_spells", "area.gust_of_wind.v4", None),
    ("thunderwave", "area_spells", "area.thunderwave.surface", None),
    ("shatter", "pending_spells", "pending.shatter.back", "back"),
    ("shatter", "pending_spells", "pending.shatter.front", "front"),
    ("color_spray", "control_spells", "control.color_spray.back", "back"),
    ("color_spray", "control_spells", "control.color_spray.front", "front"),
    ("sleep", "spell_recovery", "sleep.area.v1", None),
    ("ice_knife", "ice_spells", "ice.v8.ice_knife.impact", None),
)


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n")


def import_bundle(source: Path, repo: Path = ROOT) -> None:
    manifests = {name: json.loads((source / f"{name}-manifest.json").read_text())
                 for name, _, _, _ in BUNDLES}
    destination = repo / "game/assets/aoe_surface"
    for name, manifest in manifests.items():
        shutil.copytree(source / "delivery" / manifest["spell"], destination / manifest["spell"],
                        dirs_exist_ok=True)
        shutil.copyfile(source / f"{name}-manifest.json", destination / f"{name}-manifest.json")
    for name, bundle, asset_id, component in BUNDLES:
        manifest = manifests[name]
        path = repo / "game/data" / bundle / "bindings.json"
        bindings = json.loads(path.read_text())
        banks = {}
        for facing in FACINGS:
            bank = facing if facing in manifest["directions"] else CUBE_BANKS[facing]
            parts = (manifest["components"][bank] if "components" in manifest else
                     [{"path": component or "", "pivot": manifest["directions"][bank],
                       "blend": "source-over"}])
            banks[facing] = [{
                "pattern": str(Path("game/assets/aoe_surface") / manifest["spell"] / bank /
                               part["path"] / "{frame:03d}.bin.gz"),
                "pivot": part["pivot"],
                "blendMode": "add" if part["blend"] == "lighter" else "normal",
            } for part in parts]
        bindings["projectileStorage"][asset_id] = {"phases": {"impact": {"surfaceFrames": {
            "componentsByFacing": banks, "frameIndices": list(range(manifest["frames"])),
            "bounds": [-16, 16], "verticalScale": 1.224744871391589,
            "positionScale": manifest.get("displayScale", 1),
        }}}}
        write(path, bindings)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    import_bundle(args.source)
    print("Installed seven paired AoE deliveries; spell clocks and contact rules retained.")
