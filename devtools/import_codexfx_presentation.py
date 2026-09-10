"""Bind an existing CodexFX export to an existing Studio spell recipe offline.

The source pipeline supplies its original compatibility converter. This tool
copies its PNG unchanged and emits the same asset/Studio JSON types consumed by
the game; it never renders artwork or modifies the pinned NeuroClient export.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
from devtools.import_neuroclient_presentation import REPO, contained_path, json_bytes, png_dimensions, sha256


DATA_ROOT = "game/data/codexfx"
ASSET_ROOT = "game/assets/codexfx"
BASE_DRAFTS = "game/data/neuroclient/spell-studio-drafts.materialized.json"

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
                      spell_id: str) -> dict[str, bytes]:
    """Produce a local authored selection without rewriting the original recipe."""
    source = {name: contained_path(package, name).read_bytes() for name in (
        "asset.json", "build.json", "readiness.json", "profiles/palette.json",
    )}
    asset = json.loads(source["asset.json"])
    sheet = contained_path(package, asset["sheet"]["uri"]).read_bytes()
    if sha256(sheet) != asset["sheet"]["sha256"]:
        raise ValueError("CodexFX sheet differs from its authored manifest")
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
    baseline = (REPO / BASE_DRAFTS).read_bytes()
    document = json.loads(baseline)
    selected = [row for row in document["spells"] if row["definitionRef"]["content_id"] == spell_id]
    if len(selected) != 1:
        raise ValueError(f"No unique existing Studio recipe for {spell_id}")
    draft = deepcopy(selected[0])
    projectile = draft["projectile"]
    projectile["geometry"]["enabled"] = False
    presentation = asset["presentation"]
    projectile["sprite"] = {
        "renderer": "sprite_projectile", "assetId": entry["assetId"],
        "alpha": 1, "tint": 0xFFFFFF, "blendMode": asset["sheet"]["blend"],
        "offsetX": presentation["offsetX"], "offsetY": presentation["offsetY"],
        "anchor": entry["anchor"], "geometryComposition": "replace_geometry",
        "mediaFailurePolicy": "fail_transaction",
    }
    projectile["scale"] = presentation["defaultScale"]
    # Body/release, trajectory, endpoints, staggering and feedback keep their
    # Studio values. Available export phases do not enable disabled tracks.
    for name in ("prepare", "travel", "impact"):
        phase = projectile[name]
        if phase["enabled"]:
            if phase["assetPhase"] not in entry["phases"]:
                raise ValueError(f"Export lacks selected Studio phase {phase['assetPhase']}")
            phase["assetId"] = entry["assetId"]

    local_sheet = f"{ASSET_ROOT}/{identity}/sheet.png"
    outputs = {
        **{f"{source_root}/{name}": payload for name, payload in source.items()},
        local_sheet: sheet,
        f"{DATA_ROOT}/projectile-assets.json": json_bytes([entry]),
        f"{DATA_ROOT}/spell-studio-drafts.json": json_bytes({**document, "spells": [draft]}),
        f"{DATA_ROOT}/bindings.json": json_bytes({"resources": {sheet_url: local_sheet}}),
    }
    provenance = {
        "package": str(package), "spell_id": spell_id,
        "selection": "Existing exported media replaces generated geometry; original Studio choreography is retained.",
        "inputs": {
            str(package / name): sha256(payload) for name, payload in source.items()
        } | {
            str(package / "validation.json"): sha256((package / "validation.json").read_bytes()),
            BASE_DRAFTS: sha256(baseline),
            **{str(pipeline / name): sha256((pipeline / name).read_bytes()) for name in (
                "src/codexfx_vfx/model.py", "src/codexfx_vfx/neuroclient.py",
            )},
        },
        "exporter_text_sha256": sha256(Path(__file__).read_text(encoding="utf-8").encode()),
        "outputs": {name: sha256(payload) for name, payload in outputs.items()},
    }
    outputs[f"{DATA_ROOT}/provenance.json"] = json_bytes(provenance)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-root", type=Path, required=True)
    parser.add_argument("--source-python", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--spell-id", required=True)
    parser.add_argument("--output-root", type=Path, default=REPO)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root, package = arguments.output_root.resolve(), arguments.package.resolve()
    if root.is_relative_to(package) or package.is_relative_to(root):
        parser.error("Output and source export must be separate")
    outputs = candidate_outputs(arguments.pipeline_root.resolve(), arguments.source_python,
                                package, arguments.spell_id)
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
