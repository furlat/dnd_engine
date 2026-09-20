"""Offline adaptation of approved v8 pages into the existing Studio bundle.

Copy selected media once; retain all source samples and fixed registration.
No source scan, hash validation, authoring tool or exporter runs in the game.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

from dnd.content_system.spell_catalog_composition import SPELL_CATALOG_COMPOSITION_ROWS
from devtools.import_spell_recovery import asset


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "game/data/ice_spells"
MEDIA = Path("game/assets/ice_spells")


def read(path: Path):
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    manifest = read(args.source / "manifest.json")
    baseline = next(row for row in read(ROOT / "game/data/spell_recovery/spell-studio-drafts.json")["spells"]
                    if row["definitionRef"]["content_id"] == "spell.guiding_bolt")
    refs = {row.metadata.catalog_id: row.declaration.ref.model_dump(mode="json")
            for row in SPELL_CATALOG_COMPOSITION_ROWS}
    bindings = {"resources": {}, "spells": {}, "projectileStorage": {}, "effectDrafts": {}}
    assets, drafts = [], []
    for spell in manifest["spells"]:
        name = spell["id"]
        recipe = deepcopy(baseline)
        recipe["definitionRef"] = refs[name]
        colors = sorted(spell["palette"]["colors"], key=lambda rgb: sum(a*b for a,b in zip(rgb, (.2126,.7152,.0722))))
        encoded = [r*65536+g*256+b for r,g,b in colors]
        recipe["elementColors"] = dict(zip(("primary", "secondary", "tertiary"), (encoded[-5],encoded[len(encoded)//2],encoded[-1])))
        cast = recipe["cast"]
        cast["weaponGlow"].pop("sourceSheet", None)
        cast["weaponGlow"]["colors"].update(primary=encoded[-5])
        cast["holdReleaseForVolley"] = False
        p = recipe["projectile"]
        p.update(missileStaggerMs=0, scale=.5, fps=144, minimumTravelDurationMs=150,
                 speedPxPerSecond=spell["playback"].get("referenceTravelPixelsPerSecond", 420))
        p["prepare"] = {"enabled": False, "assetPhase": "cast"}
        p["sprite"].update(blendMode="normal", offsetX=0, offsetY=0)
        p["sprite"].pop("anchor", None)
        p["orientation"]["fineRotation"] = "isometricHybrid"
        p["travel"] = {"enabled": name != "chill_touch", "assetPhase": "travel", "fps": 144,
                       "overlapContactMs": spell["playback"].get("postContactTravelFadeSeconds", 0)*1000}
        p["impact"] = {"enabled": name != "ice_knife", "assetPhase": "impact", "fps": 144}
        palette = {"colors": encoded, "gamma": .65}
        if name == "chill_touch":
            p["targetLocal"] = {"contactAfterReleaseMs": 1000/24,
                                "approachOffsetTiles": .12, "approachUntilFrame": 240}
            p["orientation"]["fineRotation"] = "none"
            p["targetAnchor"].update(liftY=-5, forwardPx=-6)
            p["impact"]["timeMap"] = [{"elapsedMs":0,"sourceFrame":0},
                {"elapsedMs":1000*5/12,"sourceFrame":206},
                {"elapsedMs":1000*5/12+(720-206)*1000/144,"sourceFrame":720}]
            palette = {"colors": [rgb for rgb, values in zip(encoded, colors)
                                   if sum(a*b for a,b in zip(values,(.2126,.7152,.0722))) < 180],
                       "gamma":1.1, "noiseSheet":"/spell-palettes/source-hand-noise.png", "untinted":True}
        recipe["damage"]["hitFlash"].update(frame=0, durationMs=150, palette=palette)
        recipe["damage"]["floatingNumber"]["label"] = "Necrotic" if name=="chill_touch" else "Cold" if name=="ray_of_frost" else "Piercing"
        recipe["damage"]["impactDelayMs"] = 0
        recipe["condition"] = {"anchor":"effect", "delayMs":0, "feedbackEnabled":True}
        for phase_name in ("travel", "impact"):
            if phase_name not in spell["phases"]:
                continue
            phase = spell["phases"][phase_name]
            size = phase.get("cell", spell["cell"])
            identity = f"ice.v8.{name}.{phase_name}"
            layers = [phase_name]
            if name=="ray_of_frost" and phase_name=="travel":
                layers.append("travelIce")
            if name=="ice_knife" and phase_name=="impact":
                layers.append("impactLight")
            record = asset(identity, name.replace("_", " ").title()+" · "+phase_name, size,
                spell["directions"], {phase_name:{"start":0,"frames":phase["frames"],"fps":144,"loop":phase_name=="travel"}}, encoded)
            record["anchorsByFacing"] = {f:{"x":xy[0]/size,"y":xy[1]/size}
                                          for f,xy in spell["registration"][phase_name].items()}
            assets.append(record)
            storage = []
            for layer_name in layers:
                raw = spell["phases"][layer_name]
                pages = {}
                for direction, entries in raw["directions"].items():
                    pages[direction] = []
                    for page in entries:
                        path = MEDIA / page["file"]
                        destination = ROOT / path
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(args.source / page["file"], destination)
                        pages[direction].append({"file":path.as_posix(), **{key:page[key] for key in ("firstFrame","frameCount","columns")}})
                storage.append({"pages":pages,"blendMode":"add" if raw["blend"]=="add" else "normal", "gain":raw.get("gain",1)})
            bindings["projectileStorage"][identity] = {"phases":{phase_name:{"layers":storage}}}
            p[phase_name]["assetId"] = identity
        p["sprite"]["assetId"] = p["impact" if name=="chill_touch" else "travel"]["assetId"]
        if name=="ice_knife":
            burst = deepcopy(recipe)
            burst["cast"].update(enabled=False, weaponGlow=None, aura=None, effects=[], slash=None)
            bp = burst["projectile"]
            bp["targetLocal"] = {"contactAfterReleaseMs":0}
            bp["travel"]["enabled"] = False
            bp["impact"]["enabled"] = True
            bp["sprite"]["assetId"] = bp["impact"]["assetId"]
            bp["orientation"]["fineRotation"] = "none"
            burst["damage"]["floatingNumber"]["label"] = "Cold"
            burst["area"] = deepcopy(read(ROOT / "game/data/neuroclient/source/src/render/data/animation/generatedSpellPresentationProfile.json")["area"])
            burst["area"]["geometry"]["enabled"] = False
            bindings["effectDrafts"]["spell.ice_knife.burst"] = burst
        if name in ("ray_of_frost", "ice_knife"):
            # Incoming body contact is upper torso; the copied burst stays on its ground support.
            p["targetAnchor"]["liftY"] = -12
        drafts.append(recipe)
        bindings["spells"]["spell."+name] = recipe["definitionRef"]
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for name,value in (("bindings.json",bindings),("projectile-assets.json",assets),
                       ("spell-studio-drafts.json",{"schema":"neuroclient.spellStudioDrafts","version":6,"spells":drafts})):
        (DESTINATION/name).write_text(json.dumps(value,indent=2)+"\n")
    print(f"Imported {len(drafts)} spells, {len(assets)} phase assets, all source frames retained.")


if __name__ == "__main__":
    main()
