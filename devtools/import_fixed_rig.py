"""Import exact original sheets and explicitly paired visible shadow layers.

    python devtools/import_fixed_rig.py --archive /path/to/pack.zip \
        --binding game/data/rigs/goblin01.json

Add --check to compare source bytes with the imported files without writing.
The binding owns clip selection and adaptation; this tool never infers either.
For a RAR, pass --source-root containing its extracted archive-relative paths;
the original archive and every selected extracted member are still hash checked.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import struct
import zipfile

import numpy as np
from PIL import Image

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def recover_visible_shadow(body_png: bytes, combined_png: bytes) -> bytes:
    """Keep original visible shadow pixels; never invent pixels hidden by body.

    These selected pixel-art bodies have binary alpha. Opaque body pixels must
    match exactly in the composite. Thus body-over-recovered-shadow reconstructs
    every visible RGBA source pixel without an inverse or guessed hidden area.
    The recovered image already owns its original alpha; bind it at opacity 1.
    """
    body = np.array(Image.open(io.BytesIO(body_png)).convert("RGBA"))
    combined = np.array(Image.open(io.BytesIO(combined_png)).convert("RGBA"))
    if body.shape != combined.shape:
        raise ValueError("paired body/shadow sheet dimensions differ")
    alpha = body[:, :, 3]
    if np.any((alpha != 0) & (alpha != 255)):
        raise ValueError("paired shadow extraction requires the selected binary-alpha body")
    opaque = alpha == 255
    if not np.array_equal(body[opaque], combined[opaque]):
        raise ValueError("paired composite changes opaque body pixels")
    shadow = combined.copy()
    shadow[opaque] = 0
    # Transparent RGB has no visual meaning and is canonicalized for storage.
    shadow[shadow[:, :, 3] == 0] = 0
    result = io.BytesIO()
    Image.fromarray(shadow).save(result, format="PNG")
    return result.getvalue()


def _source_payload(record: dict, package: zipfile.ZipFile | None, source_root: Path | None) -> bytes:
    member = PurePosixPath(record["archive_member"])
    if member.is_absolute() or ".." in member.parts or "\\" in str(member):
        raise ValueError(f"invalid source member: {member}")
    if package is not None:
        payload = package.read(str(member))
    else:
        if source_root is None:
            raise ValueError("non-ZIP archives require --source-root")
        payload = (source_root / str(member)).read_bytes()
    if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
        raise ValueError(f"source member bytes differ from binding: {member}")
    return payload


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate binding key: {key}")
        result[key] = value
    return result


def import_fixed_rig(archive: Path, binding: Path, *, check: bool = False,
                     output_root: Path = REPOSITORY_ROOT,
                     source_root: Path | None = None) -> tuple[int, int]:
    """Validate all selected source bytes before copying or comparing any file."""
    document = json.loads(binding.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    provenance, rig, resources = document["provenance"], document["rig"], document["resources"]
    original = provenance["archive"]
    if archive.stat().st_size != original["bytes"]:
        raise ValueError("source archive byte count differs from binding")
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != original["sha256"]:
            raise ValueError("source archive SHA256 differs from binding")
    source_files = provenance["files"]
    expected: dict[str, tuple[int, int]] = {}
    for clip in rig["clips"].values():
        for url in clip["sheets"].values():
            if url not in resources:
                continue  # Shared media is owned and imported by its source binding.
            dimensions = (rig["cell_width"] * clip["frames"], rig["cell_height"] * len(rig["facing_rows"]))
            if url in expected and expected[url] != dimensions:
                raise ValueError(f"inconsistent sheet dimensions: {url}")
            expected[url] = dimensions
    if set(expected) != set(resources) or set(resources) != set(source_files):
        raise ValueError("clip sheets, resources and provenance files must match exactly")
    output_root = output_root.resolve()
    asset_root = (output_root / "game/assets/rigs").resolve()
    selected: dict[Path, bytes] = {}
    with (zipfile.ZipFile(archive) if source_root is None and zipfile.is_zipfile(archive)
          else nullcontext(None)) as package:
        for url, relative in resources.items():
            authored = PurePosixPath(relative)
            if authored.is_absolute() or ".." in authored.parts or "\\" in relative:
                raise ValueError(f"invalid local rig resource path: {relative}")
            destination = (output_root / relative).resolve()
            if not destination.is_relative_to(asset_root):
                raise ValueError(f"rig resource escapes local asset directory: {relative}")
            if destination in selected:
                raise ValueError(f"duplicate local rig destination: {relative}")
            source = source_files[url]
            if source.get("derivation") == "paired-visible-shadow-v1":
                payload = recover_visible_shadow(
                    _source_payload(source["body"], package, source_root),
                    _source_payload(source["combined"], package, source_root))
            elif "derivation" in source:
                raise ValueError(f"unknown rig sheet derivation: {source['derivation']}")
            else:
                payload = _source_payload(source, package, source_root)
            if (len(payload) != source["bytes"]
                    or hashlib.sha256(payload).hexdigest() != source["sha256"]):
                raise ValueError(f"derived sheet bytes differ from binding: {url}")
            if (len(payload) < 24 or payload[:8] != b"\x89PNG\r\n\x1a\n"
                    or payload[12:16] != b"IHDR"
                    or struct.unpack(">II", payload[16:24]) != expected[url]):
                raise ValueError(f"source sheet dimensions differ from binding: {url}")
            selected[destination] = payload
    for destination in selected:
        if destination.exists() and not destination.is_file():
            raise ValueError(f"rig destination is not a regular file: {destination}")
        for parent in destination.parents:
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"rig destination parent is not a directory: {parent}")
    for destination, payload in selected.items():
        if check:
            if not destination.is_file() or destination.read_bytes() != payload:
                raise ValueError(f"imported rig file differs from original source: {destination}")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
    return len(selected), sum(len(payload) for payload in selected.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    count, size = import_fixed_rig(args.archive, args.binding, check=args.check,
        output_root=args.output_root, source_root=args.source_root)
    print(f"{'Verified' if args.check else 'Imported'} {count} selected PNGs ({size:,} bytes)")


if __name__ == "__main__":
    main()
