"""Import the bounded P1 NeuroStudio source set using its original materializer.

This offline tool uses NeuroClient and Bun only while importing/checking data.
It never launches the old server or changes the source checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import struct
import subprocess
import sys
import tempfile
from typing import Any


REPO = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "d274f2d62ca9c1c5ed62a77841cacf6cc0347491"
DATA_ROOT = "game/data/neuroclient"
ASSET_ROOT = "game/assets/neuroclient"
SPELL_IDS = ("fire_bolt", "acid_splash", "magic_missile")
SOURCE_JSON = (
    "public/studio/spell-studio-drafts.json",
    "public/studio/spell-projectile-assets.json",
    *(f"src/render/data/animation/{name}.json" for name in (
        "generatedSpellPresentationProfile", "contentActionPresentationRecipes",
        "actionContextPresentation", "actionPresentationDispositions",
        "conditionPresentation", "actionMediaAssets", "paletteMap", "vfxSourceHues",
    )),
    *(f"src/render/data/{name}.json" for name in (
        "actorVisualProfiles", "actorVisualProfileBindings",
        "ancestryVisualProfiles", "ancestryVisualProfileBindings",
    )),
)
SOURCE_TS = (
    *(f"src/render/spellAuthoring/{name}.ts" for name in (
        "validation", "generatedBaseline", "generatedProfile", "catalogIdentity",
        "types", "phaseGraph",
    )),
    *(f"src/render/{name}.ts" for name in (
        "contentPresentationCatalog", "objectFieldValidation", "deepFreeze", "types",
        "visualAnchors",
    )),
    "src/iso.ts",
)
ENGINE_OWNERS = (
    "dnd/content_system/spell_catalog_composition.py",
    "dnd/spells/catalog_content.py", "dnd/spells/content_metadata.py",
    "dnd/spells/evocation.py", "dnd/spells/conjuration.py",
    "dnd/core/content/registration.py", "dnd/core/content/identities.py",
)
RIG_CATEGORIES = (
    "NakedBody", "Head22", "Head15", "Chest14", "Legs1", "Belt2",
    "Shoes1", "Shadow", "Melee1", "Melee3",
    "Legs7", "Shoes2", "Chest7", "Belt1", "Shield5", "Melee2", "Head2", "Head10", "Head13",
    "Ranged1",
)
MELEE_CLIPS = ("Attack1", "Attack2", "Attack4", "Attack5", "Attack6")
RIG_CLIPS = ("Idle", *MELEE_CLIPS, "Attack3", "TakeDamage", "Die", "Taunt", "Special1", "Run", "Rolling")
FIRE_ASSET_ID = "lelu_fire_strike_128_pixel_lab_fire24_px8"
FIRE_SHEET = f"/authored-vfx/projectiles/neuroclient_128/{FIRE_ASSET_ID}/{FIRE_ASSET_ID}.png"
RESOURCE_URLS = (
    *(f"/spritesheets/{category}/{clip}.png" for category in RIG_CATEGORIES for clip in RIG_CLIPS),
    *(f"/spritesheets/{category}/{clip}.png" for category in ("Slash1", "Slash2") for clip in MELEE_CLIPS),
    "/spritesheets/Slash1/Attack3.png",
    "/spritesheets/Magic2/Attack5.png", FIRE_SHEET,
)

# Execute the current immutable composition owner in an isolated process. This
# captures authored metadata; it neither instantiates a spell nor boots a game.
CAPTURE_OWNER = """
import json
from dnd.content_system.spell_catalog_composition import SPELL_CATALOG_COMPOSITION_ROWS
selected = {'fire_bolt', 'acid_splash', 'magic_missile'}
print(json.dumps([
    {'name': row.display_name, 'school': row.school, 'level': row.level,
     'source': row.declaration.provenance.primary_source_id,
     'contentRef': row.declaration.ref.model_dump(mode='json'),
     'metadata': row.metadata.model_dump(mode='json')}
    for row in SPELL_CATALOG_COMPOSITION_ROWS if row.metadata.catalog_id in selected
]))
"""


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(command: list[str], *, cwd: Path, stdin: str | None = None) -> str:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(command, cwd=cwd, input=stdin, text=True,
                            capture_output=True, env=env, check=False)
    if result.returncode:
        raise ValueError(f"{command[0]} failed:\n{result.stderr or result.stdout}")
    return result.stdout.strip()


def contained_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if parts.is_absolute() or ".." in parts.parts or "\\" in relative:
        raise ValueError(f"Invalid relative resource path: {relative}")
    path = root.joinpath(*parts.parts)
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"Resource escapes its root: {relative}")
    return path


def require_source_pin(app: Path) -> None:
    if run(["git", "rev-parse", "HEAD"], cwd=app) != SOURCE_REVISION:
        raise ValueError(f"NeuroClient must be at {SOURCE_REVISION}")
    if run(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=app):
        raise ValueError("NeuroClient source checkout must be clean")


def backend_catalog_entry(row: dict[str, Any]) -> dict[str, Any]:
    """The existing server projector's field names, without its model imports."""
    meta, area = row["metadata"], row["metadata"]["aoe"]
    return {
        "id": meta["catalog_id"], "content_ref": row["contentRef"],
        "name": row["name"], "description": meta["description"],
        "action_category": "spell", "level": row["level"], "school": row["school"],
        "target_type": meta["target_type"], "range_type": meta["range_type"],
        "range_ft": meta["range_ft"], "projectile_type": meta["projectile_type"],
        "aoe_shape_type": area["shape"] if area else None,
        "aoe_radius_ft": area["radius_ft"] if area else None,
        "aoe_length_ft": area["length_ft"] if area else None,
        "aoe_width_ft": area["width_ft"] if area else None,
        "aoe_height_ft": area["height_ft"] if area else None,
        "damage_types": meta["damage_types"], "healing": meta["healing"],
        "attack_roll": meta["attack_roll"], "saving_throws": meta["saving_throws"],
        "concentration": meta["concentration"], "ritual": meta["ritual"],
        "verbal": meta["verbal"], "somatic": meta["somatic"], "material": meta["material"],
        "classes": meta["classes"], "subclasses": meta["subclasses"],
        "source": row["source"], "multi_target": meta["multi_target"],
        "vfx": {"projectile_type": meta["projectile_type"],
                "aoe_shape_type": area["shape"] if area else None,
                "route_hint": meta["delivery"],
                "recommended_asset_tags": meta["recommended_asset_tags"]},
    }


def materialize(app: Path, bun: Path, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    # All imports are explicit original source owners. Bun erases their type-only
    # SDK/Pixi imports; no source rewriting, vendored closure or custom loader.
    entry = f"""
import {{ readFileSync }} from 'node:fs';
import {{ backendSpellToCatalogEntry, buildLoadedSpellAuthoringData,
  validateStudioDraftFileStrict, validateProjectileAssetFileStrict }}
  from {json.dumps(str(app / 'src/render/spellAuthoring/validation.ts'))};
import {{ FACING_ROW, FACING_CYCLE, SHEET_COLS, CELL_W, CELL_H, ANIM_FPS,
  SLOT_RENDER_ORDER, SLOT_CATEGORIES, HAIR_CATEGORIES }}
  from {json.dumps(str(app / 'src/render/types.ts'))};
import {{ AUTHORED_PROJECTILE_ROW_ORDER }}
  from {json.dumps(str(app / 'src/render/spellAuthoring/types.ts'))};
import {{ RIG_ORIGIN_Y_FROM_GROUND }} from {json.dumps(str(app / 'src/render/visualAnchors.ts'))};
import {{ TILE_W, TILE_H }} from {json.dumps(str(app / 'src/iso.ts'))};
const catalog = JSON.parse(readFileSync(0, 'utf8')).map(backendSpellToCatalogEntry);
const studioDrafts = JSON.parse(readFileSync({json.dumps(str(app / SOURCE_JSON[0]))}, 'utf8'));
const projectileAssets = JSON.parse(readFileSync({json.dumps(str(app / SOURCE_JSON[1]))}, 'utf8'));
validateStudioDraftFileStrict(studioDrafts);
validateProjectileAssetFileStrict(projectileAssets);
const loaded = buildLoadedSpellAuthoringData({{ catalog, studioDrafts, projectileAssets }});
if (loaded.warnings.length) throw new Error(loaded.warnings.join(' | '));
for (const draft of loaded.studioDrafts.spells) {{
  const projectile = draft.projectile;
  const refs = [projectile?.sprite,
    ...['prepare', 'travel', 'impact'].map(phase => projectile?.[phase])
      .filter(phase => phase?.enabled)];
  for (const ref of refs) {{
    if (ref?.assetId && !loaded.projectileAssetById.has(ref.assetId))
      throw new Error(`Unknown projectile asset ${{ref.assetId}}`);
  }}
}}
process.stdout.write(JSON.stringify({{ drafts: loaded.studioDrafts, rigs: {{
  FACING_ROW, FACING_CYCLE, SHEET_COLS, CELL_W, CELL_H, ANIM_FPS,
  SLOT_RENDER_ORDER, SLOT_CATEGORIES, HAIR_CATEGORIES,
  AUTHORED_PROJECTILE_ROW_ORDER, RIG_ORIGIN_Y_FROM_GROUND, TILE_W, TILE_H
}} }}));
"""
    with tempfile.TemporaryDirectory(prefix="neurostudio-p1-") as directory:
        script = Path(directory) / "export.ts"
        script.write_text(entry)
        return json.loads(run([str(bun), str(script)], cwd=app,
                              stdin=json.dumps([backend_catalog_entry(row) for row in catalog])))


def png_dimensions(data: bytes, name: str) -> tuple[int, int]:
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"Invalid PNG: {name}")
    return struct.unpack(">II", data[16:24])


def validate_selected_media(drafts: dict[str, Any], rigs: dict[str, Any],
                            assets: list[dict[str, Any]], media: dict[str, bytes]) -> None:
    fire = next(row for row in drafts["spells"] if row["definitionRef"]["content_id"] == "spell.fire_bolt")
    catalog = {asset["assetId"]: asset for asset in assets}
    cast, projectile = fire["cast"], fire["projectile"]
    for url, data in media.items():
        if url.startswith("/spritesheets/"):
            expected = (rigs["CELL_W"] * rigs["SHEET_COLS"], rigs["CELL_H"] * len(rigs["FACING_ROW"]))
            if png_dimensions(data, url) != expected:
                raise ValueError(f"Rig sheet dimensions disagree with source tables: {url}")
    layers = [cast.get("weaponGlow"), cast.get("aura"), cast.get("slash"), *cast["effects"]]
    for layer in layers:
        if layer and layer["enabled"] and not layer["hidden"]:
            if layer["category"] not in rigs["SLOT_CATEGORIES"][layer["slot"]]:
                raise ValueError(f"Invalid selected layer category: {layer['category']}")
            url = f"/spritesheets/{layer['category']}/{cast['actionClip']}.png"
            if url not in media:
                raise ValueError(f"Missing selected layer sheet: {url}")
    sprite = projectile["sprite"]
    if sprite["assetId"] != FIRE_ASSET_ID:
        raise ValueError("Selected Fire Bolt sprite does not match the P1 source set")
    for phase in ("prepare", "travel", "impact"):
        spec = projectile[phase]
        if not spec["enabled"]:
            continue
        asset_id = spec.get("assetId", sprite["assetId"])
        if asset_id not in catalog:
            raise ValueError(f"Unknown selected phase asset: {asset_id}")
        asset = catalog[asset_id]
        if asset["sheet"] not in media:
            raise ValueError(f"Missing selected phase media: {asset['sheet']}")
        sheet_phase = asset["phases"][spec["assetPhase"]]
        frame = asset["frame"]
        if sheet_phase["start"] < 0 or sheet_phase["start"] + sheet_phase["frames"] > frame["cols"]:
            raise ValueError(f"Selected phase exceeds its sheet: {phase}")
        expected = (frame["width"] * frame["cols"], frame["height"] * frame["rows"])
        if png_dimensions(media[asset["sheet"]], asset["sheet"]) != expected:
            raise ValueError(f"Projectile sheet dimensions disagree with metadata: {asset_id}")


def candidate_outputs(app: Path, bun: Path) -> dict[str, bytes]:
    require_source_pin(app)
    source = {name: contained_path(app, name).read_bytes() for name in (*SOURCE_JSON, *SOURCE_TS)}
    for name in SOURCE_JSON:
        json.loads(source[name])
    media = {url: contained_path(app, "public" + url).read_bytes() for url in RESOURCE_URLS}
    catalog = json.loads(run([sys.executable, "-c", CAPTURE_OWNER], cwd=REPO))
    if sorted(row["metadata"]["catalog_id"] for row in catalog) != sorted(SPELL_IDS):
        raise ValueError("Composition owner did not produce exactly the selected three spells")
    refs = {row["contentRef"]["content_id"]: row["contentRef"] for row in catalog}
    for saved in json.loads(source[SOURCE_JSON[0]])["spells"]:
        ref = saved["definitionRef"]
        if refs.get(ref["content_id"]) != ref:
            raise ValueError(f"Unknown or mismatched saved spell reference: {ref['content_id']}")
    resolved = materialize(app, bun, catalog)
    validate_selected_media(resolved["drafts"], resolved["rigs"], json.loads(source[SOURCE_JSON[1]]), media)
    require_source_pin(app)
    for name, original in source.items():
        if contained_path(app, name).read_bytes() != original:
            raise ValueError(f"Source changed during import: {name}")
    resources = {url: ASSET_ROOT + url for url in RESOURCE_URLS}
    outputs = {f"{DATA_ROOT}/source/{name}": source[name] for name in SOURCE_JSON}
    outputs.update({resources[url]: data for url, data in media.items()})
    outputs.update({
        f"{DATA_ROOT}/catalog-input.json": json_bytes(catalog),
        f"{DATA_ROOT}/spell-studio-drafts.materialized.json": json_bytes(resolved["drafts"]),
        f"{DATA_ROOT}/rig-tables.json": json_bytes(resolved["rigs"]),
        f"{DATA_ROOT}/bindings.json": json_bytes({"spells": refs, "root_rig": "neuroclient.modular", "resources": resources}),
    })
    provenance = {
        "neuroclient": {"revision": SOURCE_REVISION, "source_sha256": {
            **{name: sha256(data) for name, data in source.items()},
            **{"public" + url: sha256(data) for url, data in media.items()},
        }},
        # Code hashes normalize text to LF; existing engine files may be CRLF
        # on Windows. Imported authored JSON/media above remain byte-exact.
        "engine": {"revision": run(["git", "log", "-1", "--format=%H", "--", *ENGINE_OWNERS], cwd=REPO),
                   "owner_text_sha256": {
                       name: sha256((REPO / name).read_text(encoding="utf-8").encode("utf-8"))
                       for name in ENGINE_OWNERS
                   }},
        "exporter_text_sha256": sha256(Path(__file__).read_text(encoding="utf-8").encode("utf-8")),
        "bun_version": run([str(bun), "--version"], cwd=app),
        "outputs": {name: sha256(data) for name, data in sorted(outputs.items())},
    }
    # A manifest cannot include its own digest. Every other owned output is covered.
    outputs[f"{DATA_ROOT}/provenance.json"] = json_bytes(provenance)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-app", type=Path, required=True)
    parser.add_argument("--bun", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=REPO)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    app, bun, root = args.source_app.resolve(), args.bun.resolve(), args.output_root.resolve()
    try:
        if root.is_relative_to(app.parent) or app.is_relative_to(root):
            raise ValueError("Output root and NeuroClient source checkout must be separate")
        outputs = candidate_outputs(app, bun)
        paths = {name: contained_path(root, name) for name in outputs}
        for name, path in paths.items():
            if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root):
                raise ValueError(f"Output path must not traverse a symlink: {name}")
            if path.exists() and not path.is_file():
                raise ValueError(f"Expected an output file: {name}")
            for parent in path.parents:
                if parent.exists() and not parent.is_dir():
                    raise ValueError(f"Expected an output directory: {parent}")
                if parent == root:
                    break
        changed = [name for name, data in outputs.items() if not paths[name].is_file() or paths[name].read_bytes() != data]
        if args.check:
            if changed:
                raise ValueError("P1 outputs differ or are missing:\n" + "\n".join(changed))
            print(f"Checked {len(outputs)} P1 outputs; all match.")
            return
        for name in changed:
            paths[name].parent.mkdir(parents=True, exist_ok=True)
            paths[name].write_bytes(outputs[name])
        print(f"Validated {len(outputs)} P1 outputs; wrote {len(changed)} changed files.")
    except (OSError, ValueError, KeyError, StopIteration) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
