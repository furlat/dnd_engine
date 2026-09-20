"""Import the selected delivered spell frames, preserving Studio recipe data.

Offline only: no native execution, source audit, atlas decode or runtime export.
The two input directories are documented in game/data/spell_recovery/README.md.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

from dnd.content_system.spell_catalog_composition import SPELL_CATALOG_COMPOSITION_ROWS


REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "game/data/spell_recovery"
MEDIA = Path("game/assets/spell_recovery")
POINTS = ("acid_splash", "guiding_bolt", "eldritch_blast")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, value) -> None:
    (DATA / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def copy(source: Path, relative: Path) -> None:
    destination = REPO / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def copy_frames(source: Path, relative: Path, directions, count: int) -> None:
    for direction in directions:
        for frame in range(count):
            name = Path(direction) / f"{frame:02}.png"
            copy(source / name, relative / name)


def asset(identity: str, name: str, cell: int, directions, phases, colors):
    return {
        "assetId": identity, "displayName": name, "kind": "projectile",
        "sheet": f"/authored-vfx/spell-recovery/{identity}",
        "frame": {"width": cell, "height": cell, "rows": 8,
                  "cols": max(p["start"] + p["frames"] for p in phases.values())},
        "fps": 24, "rowOrder": directions, "phases": phases,
        "anchor": {"x": 0.5, "y": 0.5}, "defaultScale": 0.5,
        "palettePreview": {"colors": colors},
    }


def phase(raw):
    return {key: raw[key] for key in ("start", "frames", "fps", "loop")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vfx-root", type=Path, required=True)
    parser.add_argument("--neuroclient-app", type=Path, required=True)
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    release = args.vfx_root / "spell-recovery/release"
    caster = args.vfx_root / "spell-recovery/caster"
    manifests = {row["id"]: row for row in read(release / "manifest.json")}
    casts = read(caster / "manifest.json")["spells"]
    baseline = {row["definitionRef"]["content_id"]: row for row in read(
        REPO / "game/data/neuroclient/spell-studio-drafts.materialized.json")["spells"]}
    selected = {*POINTS, "fireball"}
    refs = {row.metadata.catalog_id: row.declaration.ref.model_dump(mode="json")
            for row in SPELL_CATALOG_COMPOSITION_ROWS if row.metadata.catalog_id in selected}
    bindings = {"resources": {}, "spells": {}, "projectileStorage": {}}
    assets, drafts = [], []
    for name in POINTS:
        source = manifests[name]
        identity = f"recovered.{name}.dense.v1"
        phases = {key: phase(value) for key, value in source["phases"].items()}
        recipe = deepcopy(baseline["spell.acid_splash" if name == "acid_splash" else "spell.fire_bolt"])
        recipe["definitionRef"] = refs[name]
        if name != "acid_splash":
            colors = ([0xFAE69A, 0xC5923F, 0xFFF5CF] if name == "guiding_bolt"
                      else [0x89C5FF, 0x377ABE, 0xD6F1FF])
            recipe["elementColors"] = dict(zip(("primary", "secondary", "tertiary"), colors))
            sheet = f"/spell-recovery/caster/{name}-weaponGlow.png"
            local = MEDIA / "caster" / f"{name}-weaponGlow.png"
            copy(caster / f"{name}-weaponGlow.png", local)
            bindings["resources"][sheet] = local.as_posix()
            recipe["cast"]["weaponGlow"]["sourceSheet"] = sheet
        for effect in recipe["cast"].get("effects", []):
            effect.update(enabled=False, hidden=True)
        p = recipe["projectile"]
        p["sprite"].update(assetId=identity, mediaFailurePolicy="fail_transaction")
        p.update(scale=source["defaultScale"], fps=phases["travel"]["fps"], missileStaggerMs=160 if name == "eldritch_blast" else 0)
        # Retain Studio's residual rotation after selecting an authored facing.
        p["targetAnchor"] = {"basis": "body", "liftY": 0, "forwardPx": 0}
        for field, key in (("prepare", "cast"), ("travel", "travel"), ("impact", "impact")):
            p[field] = {"enabled": key != "cast" or name == "eldritch_blast", "assetId": identity,
                        "assetPhase": key, "fps": phases.get(key, phases["travel"])["fps"]}
        p["sourceSockets"] = {"release": {direction: dict(zip(("x", "y"), value["sourceFramePixel"]))
                                           for direction, value in casts[name]["endpoints"].items()}}
        if name == "eldritch_blast":
            p["prepare"].update(startFrame=4, durationMs=500, overlapRelease=True)
            recipe["cast"]["holdReleaseForVolley"] = True
            p["sourceSockets"]["preparation"] = {
                direction: [None if xy is None else dict(zip(("x", "y"), xy)) for xy in rows]
                for direction, rows in casts[name]["handSocketSourcePixels"].items()}
        recipe["damage"]["impactDelayMs"] = 0
        recipe["damage"]["floatingNumber"]["label"] = {"acid_splash": "Acid", "guiding_bolt": "Radiant", "eldritch_blast": "Force"}[name]
        bindings["projectileStorage"][identity] = {"phases": {}}
        for key, value in phases.items():
            local = MEDIA / name / key
            copy_frames(release / name / key, local, source["rows"], value["frames"])
            bindings["projectileStorage"][identity]["phases"][key] = {"layers": [
                {"pattern": (local / "{direction}/{frame:02}.png").as_posix(), "blendMode": "add"}]}
        assets.append(asset(identity, name.replace("_", " ").title(), source["cell"], source["rows"],
                            phases, list(recipe["elementColors"].values())))
        drafts.append(recipe)
    magic = Path("spritesheets/Magic3/Special1.png")
    copy(args.neuroclient_app / "public" / magic, MEDIA / magic)
    bindings["resources"]["/" + magic.as_posix()] = (MEDIA / magic).as_posix()

    fire_root = args.vfx_root / "library-selection/release"
    fire = read(fire_root / "shared-fireball-20ft.json")
    identity = fire["assetId"]
    recipe = deepcopy(baseline["spell.fire_bolt"])
    recipe["definitionRef"] = refs["fireball"]
    recipe["area"] = deepcopy(read(REPO / "game/data/neuroclient/source/src/render/data/animation/generatedSpellPresentationProfile.json")["area"])
    recipe["area"]["geometry"]["enabled"] = False
    recipe["area"]["surfaceReveal"] = {"residueIds": ["residue.ashen"], "speedTilesPerSecond": 10}
    p = recipe["projectile"]
    p["sprite"].update(assetId=identity + ".travel", mediaFailurePolicy="fail_transaction")
    p.update(scale=fire["defaultScale"], missileStaggerMs=0, speedPxPerSecond=360)
    p["orientation"]["fineRotation"] = "none"
    p["prepare"] = {"enabled": False, "assetPhase": "cast"}
    p["sourceSockets"] = deepcopy(drafts[1]["projectile"]["sourceSockets"])
    recipe["damage"]["impactDelayMs"] = 0
    for key in ("travel", "impact"):
        raw = fire[key]
        asset_id = identity + ".travel" if key == "travel" else identity
        phase_data = {"start": 0, "frames": raw["frames"], "fps": raw["fps"], "loop": raw["loop"]}
        phases = {key: phase_data}
        assets.append(asset(asset_id, fire["displayName"] + f" · {key}", raw["cell"], fire["rowOrder"],
                            phases, list(recipe["elementColors"].values())))
        p[key] = {"enabled": True, "assetId": asset_id, "assetPhase": key, "fps": raw["fps"]}
        if key == "travel":
            p[key]["scale"] = fire["defaultScale"] * 1.2
        layers = []
        sources = [("fireball_b", "add")] if key == "travel" else [("fireball_smoke", "normal"), ("fireball_explosion", "add")]
        for source_name, blend in sources:
            local = MEDIA / source_name
            copy_frames(fire_root / source_name, local, fire["rowOrder"], raw["frames"])
            layers.append({"pattern": (local / "{direction}/{frame:02}.png").as_posix(), "blendMode": blend})
        bindings["projectileStorage"][asset_id] = {"phases": {phase_name: {"layers": layers} for phase_name in phases}}
    drafts.append(recipe)
    bindings["spells"] = {draft["definitionRef"]["content_id"]: draft["definitionRef"] for draft in drafts}
    write("bindings.json", bindings)
    write("projectile-assets.json", assets)
    write("spell-studio-drafts.json", {"schema": "neuroclient.spellStudioDrafts", "version": 6, "spells": drafts})
    print(f"Imported {len(drafts)} spell drafts and {len(assets)} finite frame assets.")


if __name__ == "__main__":
    main()
