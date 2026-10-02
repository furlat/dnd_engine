"""Lossless offline atlas repacking for registered paired native color banks."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from devtools.repack_support_media import _repack_layer


def repack_bank(source: Path, name: str, output: Path, *, page_size: int = 2048) -> dict:
    """Keep every selected source frame, crop offset, pivot and clock unchanged."""
    source, output = source.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(source):
        raise ValueError("Atlas staging must be new and outside the preserved source")
    row = json.loads((source / "media.json").read_text())[name]
    if row["fps"] != 32 or set(row["cameras"]) != {"0", "1", "2", "3"}:
        raise ValueError("Repacking requires a complete registered 32-FPS bank")
    checksums = {relative.strip().removeprefix("./"): digest
        for digest, relative in (line.split(maxsplit=1)
            for line in (source / "SHA256SUMS").read_text().splitlines())}
    pages = {page for camera in row["cameras"].values()
        for layer in camera["layers"].values() for page in layer["pages"]}
    for relative in pages:
        path = (source / relative).resolve()
        if not path.is_relative_to(source) or hashlib.sha256(path.read_bytes()).hexdigest() != checksums.get(relative):
            raise ValueError(f"Unverified source atlas: {relative}")
    for camera in row["cameras"].values():
        if set(camera["layers"]) != {"back", "front"}:
            raise ValueError("Native rear/front pair is required")
        for layer in camera["layers"].values():
            if len(layer["frames"]) != row["frames"]:
                raise ValueError("Incomplete native frame addresses")
    result = json.loads(json.dumps(row))
    output.mkdir(parents=True)
    verified = 0
    for q, camera in row["cameras"].items():
        for side, layer in camera["layers"].items():
            packed = _repack_layer(source, output, layer, list(range(row["frames"])),
                f"packed/{name}/q{q}/{side}", page_size)
            # Verify exact RGBA per addressed crop, not whole-page identities.
            original_path = packed_path = None
            original_image = packed_image = None
            try:
                for before, after in zip(layer["frames"], packed["frames"], strict=True):
                    if before is None:
                        assert after is None
                        continue
                    assert after is not None and before["offset"] == after["offset"]
                    for current, root, original in ((before, source, True), (after, output, False)):
                        relative = (layer if original else packed)["pages"][current["page"]]
                        if original and relative != original_path:
                            if original_image is not None:
                                original_image.close()
                            original_image = Image.open(root / relative).convert("RGBA")
                            original_path = relative
                        elif not original and relative != packed_path:
                            if packed_image is not None:
                                packed_image.close()
                            packed_image = Image.open(root / relative).convert("RGBA")
                            packed_path = relative
                    x, y, w, h = before["source"]
                    px, py, pw, ph = after["source"]
                    assert (w, h) == (pw, ph) and original_image is not None and packed_image is not None
                    with original_image.crop((x, y, x+w, y+h)) as a, packed_image.crop((px, py, px+w, py+ph)) as b:
                        if a.tobytes() != b.tobytes():
                            raise ValueError("Repacked source pixels changed")
                    verified += 1
            finally:
                if original_image is not None:
                    original_image.close()
                if packed_image is not None:
                    packed_image.close()
            result["cameras"][q]["layers"][side] = packed
    selected = sorted({page for camera in result["cameras"].values()
        for layer in camera["layers"].values() for page in layer["pages"]})
    (output / "media.json").write_text(json.dumps({name: result}, indent=2) + "\n")
    (output / "SHA256SUMS").write_text("".join(
        hashlib.sha256((output / page).read_bytes()).hexdigest() + "  " + page + "\n" for page in selected))
    receipt = {"source": str(source), "name": name, "source_pages": len(pages),
        "source_bytes": sum((source / p).stat().st_size for p in pages),
        "selected_pages": len(selected), "selected_bytes": sum((output / p).stat().st_size for p in selected),
        "exact_rgba_crops_verified": verified, "fps": row["fps"], "frames": row["frames"], "page_size": page_size}
    (output / "packing-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-size", type=int, default=2048)
    args = parser.parse_args()
    print(json.dumps(repack_bank(args.source, args.name, args.output, page_size=args.page_size)))
