"""Install explicitly selected original equipment sheets, without editing recipes."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def import_item_media(archive: Path, preserved: Path, production: Path,
                      output_root: Path = ROOT, *,
                      selected_paths: frozenset[str] | None = None) -> tuple[int, int]:
    document = json.loads((ROOT / "game/data/item_media_sources.json").read_text())
    if archive.name != document["archive"]:
        raise ValueError("incorrect item source archive")
    if selected_paths is not None and not selected_paths <= {row["path"] for row in document["files"]}:
        raise ValueError("selected item media must be in the authored source manifest")
    preserved.mkdir(parents=True, exist_ok=True)
    original = preserved / archive.name
    if not original.exists():
        shutil.copyfile(archive, original)
    elif original.stat().st_size != archive.stat().st_size:
        raise ValueError("preserved original differs; never overwrite it")
    receipts = []
    with zipfile.ZipFile(original) as source:
        for row in document["files"]:
            if selected_paths is not None and row["path"] not in selected_paths:
                continue
            relative = PurePosixPath(row["path"])
            if relative.is_absolute() or ".." in relative.parts or relative.parts[:3] != ("game", "assets", "neuroclient"):
                raise ValueError("item media destination escapes private art")
            payload = source.read(row["member"])
            for root in (output_root, production):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            receipts.append(dict(path=str(relative), bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest()))
    manifest_path = production / "art-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    files = {row["path"]: row for row in manifest["files"]}
    files.update({row["path"]: row for row in receipts})
    manifest["files"] = sorted(files.values(), key=lambda row: row["path"])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    (preserved / "installation-receipt.json").write_text(json.dumps(dict(files=receipts), indent=2)+"\n")
    return len(receipts), sum(row["bytes"] for row in receipts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--preserved", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--path", action="append", help="Install only these authored paths; leave other sheets untouched")
    arguments = parser.parse_args()
    print(import_item_media(arguments.archive, arguments.preserved, arguments.production,
                            selected_paths=None if arguments.path is None else frozenset(arguments.path)))
