"""Selected intake preserves pixels, registration and unrelated authored behavior."""

import hashlib
import json
from pathlib import Path

from PIL import Image
import pytest

from devtools.import_production_gap_media import BUNDLES, COLD_TEXTURES, REVISION, WIND_TEXTURE, import_production_gaps


def delivery_fixture(root: Path):
    source = root / "delivery"
    source.mkdir()
    rows = []
    media = {"revision": REVISION, "contracts": {group: {} for group in BUNDLES}}
    for group in BUNDLES:
        names = ([*(f"h{i}/{band}" for i in range(8) for band in ("near", "middle", "far", "ground")),
                  "contact-back", "contact-front"] if group == "cone" else
                 [f"q{i}" for i in range(4)] if group == "call" else [f"h{i}" for i in range(8)])
        media[group] = {}
        for index, name in enumerate(names):
            address = f"../reused/{name}.png" if group == "cone" and name.startswith("h0/") else f"media/{group}/{name}.png"
            page = (source / address).resolve()
            page.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGBA", (2, 2), (73, 149, 19, 83)).save(page)
            rows.append({"path": page.relative_to(root).as_posix(), "bytes": page.stat().st_size,
                "sha256": hashlib.sha256(page.read_bytes()).hexdigest(), "roles": ["runtime RGBA"], "groups": [group]})
            count = 96 if group == "cone" and not name.startswith("contact") else 32 if group == "wind" else 48
            media[group][name] = {"cell": 64, "captureZoom": .67 if group == "cone" else .75 if group == "call" else 1,
                "pivot": [index + 1, index + 2], "fps": 32, "frameCount": count, "pages": [address],
                "revision": {"cone": "straight-alpha-volume-v4", "call": "blue-local-v4",
                             "wind": "native-isolated-block-v1"}[group],
                "frames": [{"page": 0, "source": [0, 0, 2, 2], "offset": [3, 4]}] * (count - 1) + [None],
                "sortDepthCanonical": index - 15}
    texture = root / WIND_TEXTURE
    texture.parent.mkdir(parents=True)
    Image.new("RGBA", (5, 2), (0, 0, 0, 61)).save(texture)
    rows.append({"path": WIND_TEXTURE, "bytes": texture.stat().st_size,
        "sha256": hashlib.sha256(texture.read_bytes()).hexdigest(),
        "roles": ["private native donor dependency"], "groups": ["wind"]})
    for relative in COLD_TEXTURES.values():
        texture = root / relative
        texture.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (2, 2), (9, 18, 36, 63)).save(texture, format="PNG")
        rows.append({"path": relative, "bytes": texture.stat().st_size,
            "sha256": hashlib.sha256(texture.read_bytes()).hexdigest(),
            "roles": ["shared runtime/source dependency"], "groups": ["cone"]})
    cold = root / "cold-weather-batch/cone-of-cold-v1"
    cold.mkdir(parents=True)
    (cold / "NOTES.md").write_text("Selected original notes")
    (cold / "review.js").write_text("Selected original timing")
    path = source / "media.json"
    path.write_text(json.dumps(media))
    rows.append({"path": "delivery/media.json", "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "roles": ["runtime registration"], "groups": ["all"]})
    (source / "delivery-receipt.json").write_text(json.dumps({"revision": REVISION, "files": rows}))
    Image.new("RGBA", (1, 1), (255, 0, 0, 255)).save(source / "unselected.png")
    export = root / "export"
    export.mkdir()
    mesh = export / "wind-mesh.json"
    mesh.write_text(json.dumps({"vertices": [[0, 0, 0]] * 8, "uv": [[0, 0]] * 8, "indices": [0, 1, 2] * 4}))
    for name in ("export-wind-mesh.gd", "export-command.json", "export.log"):
        (export / name).write_text("Recorded extraction")
    repo, production, preserved = root / "repo", root / "production", root / "preserved"
    production.mkdir()
    (production / "art-manifest.json").write_text(json.dumps({"files": [], "total_bytes": 0}))
    for bundle_name in BUNDLES.values():
        bundle = repo / "game/data" / bundle_name
        bundle.mkdir(parents=True)
        (bundle / "bindings.json").write_text(json.dumps({"spells": {"untouched": {"native": True}},
            "resources": {"/old": "old.png"}, "projectileStorage": {"old": {"retained": True}}}))
        (bundle / "projectile-assets.json").write_text(json.dumps([{"assetId": "old"}]))
        (bundle / "drafts.json").write_text("Existing selected recipes\n")
    return source, mesh, repo, production, preserved


def test_intake_keeps_pixels_crops_facings_cameras_and_existing_recipes(tmp_path):
    source, mesh, repo, production, preserved = delivery_fixture(tmp_path)
    result = import_production_gaps(source, mesh, repo=repo, production=production, preserved=preserved)
    assert [len(result[group]["identities"]) for group in BUNDLES] == [6, 4, 8]
    manifest = json.loads((production / "art-manifest.json").read_text())
    assert len(manifest["files"]) == 50  # Forty-six banks, three donor textures and mesh record.
    assert not tuple(preserved.rglob("unselected.png"))
    for group, bundle_name in BUNDLES.items():
        bundle = repo / "game/data" / bundle_name
        bindings = json.loads((bundle / "bindings.json").read_text())
        assert bindings["spells"] == {"untouched": {"native": True}}
        assert bindings["projectileStorage"]["old"] == {"retained": True}
        assert bindings["resources"]["/old"] == "old.png"
        assert (bundle / "drafts.json").read_text() == "Existing selected recipes\n"
        for identity in result[group]["identities"]:
            views = bindings["projectileStorage"][identity]["phases"]["impact"]["layers"][0]["partsByFacing"]
            for parts in views.values():
                assert parts[-1] == []
                assert parts[0][0]["rect"] == [0, 0, 2, 2] and parts[0][0]["offset"] == [3, 4]
                with Image.open(repo / parts[0][0]["file"]) as image:
                    assert image.getpixel((0, 0)) == (73, 149, 19, 83)
    cone = json.loads((repo / "game/data/weather_solar_media/projectile-assets.json").read_text())
    near = next(row for row in cone if row["assetId"] == "weather.cone.near")
    assert near["anchorsByFacing"]["SE"] == {"x": 1 / 64, "y": 2 / 64}
    assert near["anchorsByFacing"]["E"] == {"x": 29 / 64, "y": 30 / 64}
    assert result["cone"]["registrations"]["weather.cone.near"]["banksByFacing"]["SE"] == "h0/near"
    assert [result["call"]["registrations"][f"lightning.call_lightning.v5.q{q}"]["banksByFacing"]["E"]
            for q in range(4)] == [f"q{q}" for q in range(4)]
    component = json.loads((repo / "game/assets/wall_media/production-gaps/wind/block-components.json").read_text())
    assert component["mesh"] == json.loads(mesh.read_text())
    assert component["count"] == 5 and component["sheet"] == [5, 2]
    assert component["texture"] == "/wind/block-texture.png"
    first_manifest = (production / "art-manifest.json").read_bytes()
    import_production_gaps(source, mesh, repo=repo, production=production, preserved=preserved)
    assert (production / "art-manifest.json").read_bytes() == first_manifest


@pytest.mark.parametrize("fault", ["checksum", "crop", "missing_bank", "escape", "missing_extraction"])
def test_invalid_delivery_fails_before_any_installed_or_authored_change(tmp_path, fault):
    source, mesh, repo, production, preserved = delivery_fixture(tmp_path)
    media = json.loads((source / "media.json").read_text())
    if fault == "checksum":
        (source / "media/wind/h0.png").write_bytes(b"changed original")
    elif fault == "crop":
        media["wind"]["h0"]["frames"][0]["source"] = [1, 1, 2, 2]
    elif fault == "missing_bank":
        del media["call"]["q3"]
    elif fault == "escape":
        media["call"]["q3"]["pages"] = ["../../outside.png"]
    else:
        (mesh.parent / "export.log").unlink()
    path = source / "media.json"
    path.write_text(json.dumps(media))
    receipt = json.loads((source / "delivery-receipt.json").read_text())
    row = next(row for row in receipt["files"] if row["path"] == "delivery/media.json")
    row.update(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (source / "delivery-receipt.json").write_text(json.dumps(receipt))
    before = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    manifest = (production / "art-manifest.json").read_bytes()
    with pytest.raises((ValueError, FileNotFoundError)):
        import_production_gaps(source, mesh, repo=repo, production=production, preserved=preserved)
    assert {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()} == before
    assert (production / "art-manifest.json").read_bytes() == manifest
    assert not preserved.exists()
