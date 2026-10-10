"""Lossless offline atlas repacking for registered paired native color banks."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from collections.abc import Iterable, Mapping

from PIL import Image

from devtools.repack_support_media import _repack_layer


def pack_coupled_frames(frames: Iterable[tuple[int, int, tuple[int, int], Mapping[str, tuple[bytes, int]]]],
                        output: Path, *, prefix: str, max_side: int = 2048) -> tuple[list[list[dict]], dict[str, dict]]:
    """Page consecutive raw frames, preserving exactly aligned numeric companions.

    Oversized frames become lossless pieces with their original canvas offsets.
    Only one decoded temporal page set is held while streaming the source bank.
    Returned dimensions belong to the release resource records, not a new codec.
    """
    records: list[list[dict]] = []
    resources: dict[str, dict] = {}
    pending: list[tuple[int, int, int, int, dict[str, bytes]]] = []
    addresses: list[dict] = []
    layout: dict[str, int] | None = None
    edge = x = y = row_height = used_width = used_height = 0
    page_index = 0

    def flush() -> None:
        nonlocal page_index, x, y, row_height, used_width, used_height
        if not pending:
            return
        assert layout is not None
        files = {}
        for name, bpp in layout.items():
            page = bytearray(used_width * used_height * bpp)
            for px, py, width, height, planes in pending:
                source = planes[name]
                for row in range(height):
                    offset = ((py + row) * used_width + px) * bpp
                    page[offset:offset + width * bpp] = source[row * width * bpp:(row + 1) * width * bpp]
            relative = f'{prefix}/{page_index:04d}.{name}.gz'
            path = output / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = gzip.compress(page, compresslevel=6, mtime=0)
            path.write_bytes(payload)
            resources[relative] = {'width': used_width, 'height': used_height,
                'channels': bpp, 'decodedBytes': len(page), 'bytes': len(payload),
                'sha256': hashlib.sha256(payload).hexdigest(),
                'decodedSha256': hashlib.sha256(page).hexdigest(), 'encoding': 'raw_gzip'}
            files[name] = relative
        for address in addresses:
            address['planes'] = files
        page_index += 1
        pending.clear(); addresses.clear()
        x = y = row_height = used_width = used_height = 0

    for width, height, offset, planes in frames:
        current_layout = {name: bpp for name, (_, bpp) in planes.items()}
        if not planes or min(width, height) <= 0 or any(bpp <= 0 for bpp in current_layout.values()):
            raise ValueError('Coupled frames need positive dimensions and plane channels')
        if layout is None:
            layout = current_layout
            edge = max_side
            if edge < 1:
                raise ValueError('Page side must be positive')
        elif current_layout != layout:
            raise ValueError('Companion layout changed within a frame bank')
        if any(len(data) != width * height * bpp for data, bpp in planes.values()):
            raise ValueError('Coupled plane length differs from registered dimensions')
        parts = []
        for top in range(0, height, edge):
            for left in range(0, width, edge):
                pw, ph = min(edge, width - left), min(edge, height - top)
                if x + pw > edge:
                    x, y, row_height = 0, y + row_height, 0
                if y + ph > edge:
                    flush()
                pixels = {name: b''.join(data[((top + row) * width + left) * bpp:
                                            ((top + row) * width + left + pw) * bpp]
                                        for row in range(ph))
                          for name, (data, bpp) in planes.items()}
                part = {'rect': [x, y, pw, ph], 'offset': [offset[0] + left, offset[1] + top]}
                parts.append(part); addresses.append(part)
                pending.append((x, y, pw, ph, pixels))
                used_width, used_height = max(used_width, x + pw), max(used_height, y + ph)
                x, row_height = x + pw, max(row_height, ph)
        records.append(parts)
    flush()
    return records, resources


def repack_bank(source: Path, name: str, output: Path, *, page_size: int = 2048) -> dict:
    """Keep every selected source frame, crop offset, pivot and clock unchanged."""
    source, output = source.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(source):
        raise ValueError("Atlas staging must be new and outside the preserved source")
    row = json.loads((source / "media.json").read_text())[name]
    if row["fps"] <= 0 or not row["cameras"]:
        raise ValueError("Repacking requires a positive authored rate and registered views")
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
