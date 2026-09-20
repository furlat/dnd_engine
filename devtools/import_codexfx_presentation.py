"""Import media for an already-authored CodexFX Studio selection offline.

The source pipeline supplies its original compatibility converter. This tool
copies its PNG unchanged and updates asset/resource packaging. Canonical spell
recipes are read-only inputs; it never renders artwork or rewrites choreography.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from devtools.import_neuroclient_presentation import REPO, contained_path, json_bytes, png_dimensions


DATA_ROOT = "game/data/codexfx"
ASSET_ROOT = "game/assets/codexfx"

# Use the export package's existing adapter, with its own offline dependencies.
CONVERT = """
import json, sys
from pathlib import Path
from codexfx_vfx.model import AssetManifest
from codexfx_vfx.neuroclient import compatibility_entry
package = Path(sys.argv[1])
asset = AssetManifest.from_dict(json.loads((package / 'asset.json').read_text()))
palette = json.loads((package / 'profiles/palette.json').read_text())
print(json.dumps(compatibility_entry(
    asset, report=json.loads((package / 'validation.json').read_text()),
    sheet_uri=sys.argv[2], manifest_uri=sys.argv[3],
    palette_preview={'palette': palette['paletteId'], 'colors': [
        (r << 16) | (g << 8) | b for r, g, b in palette['colors']
    ]},
)))
"""


def candidate_outputs(pipeline: Path, source_python: Path, package: Path,
                      spell_id: str, *, authored_root: Path = REPO) -> dict[str, bytes]:
    """Update selected media without changing its authored presentation."""
    source = {name: contained_path(package, name).read_bytes() for name in (
        "asset.json", "build.json", "readiness.json", "profiles/palette.json",
    )}
    asset = json.loads(source["asset.json"])
    sheet = contained_path(package, asset["sheet"]["uri"]).read_bytes()
    if png_dimensions(sheet, asset["sheet"]["uri"]) != (asset["sheet"]["width"], asset["sheet"]["height"]):
        raise ValueError("CodexFX sheet dimensions differ from its authored manifest")
    if (asset["sheet"]["sampling"], asset["sheet"]["alphaMode"], asset["sheet"]["colorSpace"]) != ("nearest", "straight", "srgb"):
        raise ValueError("This local sprite adapter consumes nearest, straight-alpha sRGB exports")

    identity = f"{asset['assetId']}.{asset['variantId']}"
    sheet_url = f"/authored-vfx/projectiles/codexfx/{identity}/sheet.png"
    source_root = f"{DATA_ROOT}/source/{identity}"
    environment = {**os.environ, "PYTHONPATH": str(pipeline / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        [str(source_python), "-c", CONVERT, str(package), sheet_url, f"{source_root}/asset.json"],
        capture_output=True, text=True, check=True, env=environment,
    )
    entry = json.loads(result.stdout)
    document = json.loads((authored_root / DATA_ROOT / "spell-studio-drafts.json").read_text())
    selected = [row for row in document["spells"] if row["definitionRef"]["content_id"] == spell_id]
    if len(selected) != 1:
        raise ValueError(f"No unique existing Studio recipe for {spell_id}")
    projectile = selected[0]["projectile"]
    if projectile["sprite"]["assetId"] != entry["assetId"]:
        raise ValueError(f"Export is not the authored media selection for {spell_id}")
    # Import availability cannot enable disabled tracks or retune their timing.
    for name in ("prepare", "travel", "impact"):
        phase = projectile[name]
        if phase["enabled"] and (phase.get("assetId") or entry["assetId"]) == entry["assetId"]:
            if phase["assetPhase"] not in entry["phases"]:
                raise ValueError(f"Export lacks selected Studio phase {phase['assetPhase']}")

    local_sheet = f"{ASSET_ROOT}/{identity}/sheet.png"
    bindings = json.loads((authored_root / DATA_ROOT / "bindings.json").read_text())
    bindings["resources"][sheet_url] = local_sheet
    assets = {row["assetId"]: row for row in json.loads(
        (authored_root / DATA_ROOT / "projectile-assets.json").read_text())}
    assets[identity] = entry
    outputs = {
        **{f"{source_root}/{name}": payload for name, payload in source.items()},
        local_sheet: sheet,
        f"{DATA_ROOT}/projectile-assets.json": json_bytes(list(assets.values())),
        f"{DATA_ROOT}/bindings.json": json_bytes(bindings),
    }
    provenance = {
        "package": str(package), "spell_id": spell_id,
        "selection": "Selected media packaging only; canonical Studio choreography and palette treatment are retained.",
    }
    outputs[f"{DATA_ROOT}/provenance.json"] = json_bytes(provenance)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-root", type=Path, required=True)
    parser.add_argument("--source-python", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--spell-id", required=True)
    parser.add_argument("--output-root", type=Path, default=REPO,
                        help="Checkout containing the selected canonical recipes and media bindings")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root, package = arguments.output_root.resolve(), arguments.package.resolve()
    if root.is_relative_to(package) or package.is_relative_to(root):
        parser.error("Output and source export must be separate")
    outputs = candidate_outputs(arguments.pipeline_root.resolve(), arguments.source_python,
                                package, arguments.spell_id, authored_root=root)
    paths = {name: contained_path(root, name) for name in outputs}
    changed = [name for name, payload in outputs.items()
               if not paths[name].is_file() or paths[name].read_bytes() != payload]
    if arguments.check:
        if changed:
            parser.error("Authored CodexFX outputs differ: " + ", ".join(changed))
        print(f"Checked {len(outputs)} authored CodexFX outputs.")
        return
    for name in changed:
        paths[name].parent.mkdir(parents=True, exist_ok=True)
        paths[name].write_bytes(outputs[name])
    print(f"Validated {len(outputs)} authored CodexFX outputs; wrote {len(changed)} changed files.")


if __name__ == "__main__":
    main()
