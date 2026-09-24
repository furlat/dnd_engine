"""Explicit private-art export/install/check. Never imported by the game.

Uses Git's existing SSH/HTTPS authentication; credentials never enter a manifest.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
from stat import S_ISREG
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/furlat/neurodragon_art.git"
MANIFEST = "art-manifest.json"
POINTER = b"version https://git-lfs.github.com/spec/v1"


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def art_path(name: str) -> PurePosixPath:
    """Validate manifest addresses without consulting an installation."""
    relative = PurePosixPath(name)
    if (relative.is_absolute() or ".." in relative.parts or "\\" in name
            or ":" in name or relative.parts[:2] != ("game", "assets")):
        raise ValueError(f"Invalid art path: {name}")
    return relative


def contained(root: Path, name: str, *, checked_directories: set[Path] | None = None) -> Path:
    """Reject filesystem redirects; directory reuse belongs to one caller pass."""
    relative = art_path(name)
    path = root.joinpath(*relative.parts)
    cursor = root
    for part in relative.parts[:-1]:
        cursor = cursor / part
        if checked_directories is not None and cursor in checked_directories:
            continue
        if cursor.is_symlink() or cursor.is_junction():
            raise ValueError(f"Art path must not traverse a symlink: {name}")
        if checked_directories is not None:
            checked_directories.add(cursor)
    if path.is_symlink() or path.is_junction():
        raise ValueError(f"Art path must not traverse a symlink: {name}")
    return path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False,
                                     encoding="utf-8") as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def copy_file(source: Path, destination: Path) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def export_art(source: Path, destination: Path) -> None:
    """Copy every installed companion, including untracked files; keep originals."""
    if destination.exists():
        raise ValueError("Export destination must be new; existing private work is preserved")
    if destination.resolve().is_relative_to(source.resolve()):
        raise ValueError("Export outside the engine checkout")
    files = sorted((source / "game/assets").rglob("*"))
    files = [path for path in files if path.is_file()]
    if not files:
        raise ValueError("No installed art found at source game/assets")
    destination.mkdir(parents=True)
    rows = []
    for path in files:
        name = path.relative_to(source).as_posix()
        original = contained(source, name)
        with original.open("rb") as stream:
            if stream.read(len(POINTER)) == POINTER:
                raise ValueError(f"Unhydrated Git LFS file: {name}")
        target = contained(destination, name)
        copy_file(original, target)
        checksum = digest(original)
        if digest(target) != checksum:
            raise ValueError(f"Export verification failed: {name}")
        rows.append({"path": name, "bytes": target.stat().st_size, "sha256": checksum})
    write_json(destination / MANIFEST, {"version": 1, "files": rows})
    (destination / ".gitattributes").write_text(
        "game/assets/** filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8")
    (destination / "README.md").write_text(
        "# Neurodragon private art\n\nPrivate licensed media and pixel-derived companions. "
        "No redistribution license is granted by the engine's code license.\n\n"
        "Keep all game/assets paths intact. Regenerate art-manifest.json with the engine's "
        "devtools/art.py export command when publishing a new complete installation. "
        "Use Git LFS before the first git add. Source archives and review media belong "
        "in private storage, not the engine repository.\n", encoding="utf-8")
    print(f"Exported and verified {len(rows)} files / {sum(r['bytes'] for r in rows):,} bytes to {destination}")


def read_manifest(root: Path) -> dict:
    data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if data["version"] != 1 or not data["files"]:
        raise ValueError("Unsupported or empty art manifest")
    names = set()
    for row in data["files"]:
        art_path(row["path"])
        if row["path"] in names or row["bytes"] < 0 or len(row["sha256"]) != 64:
            raise ValueError(f"Invalid manifest entry: {row['path']}")
        names.add(row["path"])
    return data


def verify(root: Path, manifest: dict, *, hashes: bool = False) -> None:
    failures = []
    checked_directories: set[Path] = set()
    for row in manifest["files"]:
        path = contained(root, row["path"], checked_directories=checked_directories)
        try:
            info = path.stat()
        except FileNotFoundError:
            failures.append(row["path"])
            continue
        if not S_ISREG(info.st_mode) or info.st_size != row["bytes"]:
            failures.append(row["path"])
            continue
        with path.open("rb") as stream:
            pointer = stream.read(len(POINTER)) == POINTER
        if pointer or (hashes and digest(path) != row["sha256"]):
            failures.append(row["path"])
    if failures:
        raise ValueError(f"Missing, incomplete or changed art ({len(failures)} files): "
                         + ", ".join(failures[:8])
                         + ". Run python devtools/art.py install (Git LFS must be installed).")


def install(args: argparse.Namespace) -> None:
    cache, target = args.cache.resolve(), args.root.resolve()
    if cache == target or cache.is_relative_to(target / "game/assets"):
        raise ValueError("Cache must be separate from installed game/assets")
    if args.source:
        source = args.source.resolve()
    else:
        git("lfs", "version")
        if not cache.exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            git("clone", "--depth", "1", "--", args.repo, str(cache))
        if git("remote", "get-url", "origin", cwd=cache) != args.repo:
            raise ValueError("Cache remote differs from --repo; choose a separate --cache")
        if git("status", "--porcelain", cwd=cache):
            raise ValueError("Private art cache has local edits; commit or preserve them before installing")
        if args.update or args.ref:
            git("fetch", "--depth", "1", "origin", args.ref or "HEAD", cwd=cache)
            git("checkout", "--detach", "FETCH_HEAD", cwd=cache)
        git("lfs", "pull", cwd=cache)
        source = cache
    if source == target:
        raise ValueError("Source and install destination must differ")
    manifest = read_manifest(source)
    receipt = target / ".runtime" / MANIFEST
    previous = ({row["path"]: row for row in read_manifest(receipt.parent)["files"]}
                if receipt.is_file() else {})
    pending = []
    checked_directories: set[Path] = set()
    for row in manifest["files"]:
        destination = contained(target, row["path"], checked_directories=checked_directories)
        # The previous manifest is a receipt, not a fresh integrity check. Its
        # published identity distinguishes same-size changes between releases.
        if not args.reinstall and previous.get(row["path"]) == row:
            try:
                info = destination.stat()
            except FileNotFoundError:
                pass
            else:
                if S_ISREG(info.st_mode) and info.st_size == row["bytes"]:
                    continue
        pending.append(row)
    # Preflight only payloads that will actually be copied. Deep verification
    # remains the explicit `check --hashes` command; gameplay never invokes it.
    verify(source, {"files": pending})
    source_directories: set[Path] = set()
    target_directories: set[Path] = set()
    copied = sum(copy_file(contained(source, row["path"], checked_directories=source_directories),
                           contained(target, row["path"], checked_directories=target_directories)) for row in pending)
    write_json(target / ".runtime" / MANIFEST, manifest)
    print(f"Installed {len(manifest['files'])} files ({copied} copied); existing caches/unlisted files preserved.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Copy installed art to a NEW private staging directory")
    export.add_argument("--root", type=Path, default=ROOT)
    export.add_argument("--destination", type=Path, required=True)
    installer = commands.add_parser("install", help="Fetch private art using existing Git authentication")
    installer.add_argument("--root", type=Path, default=ROOT)
    installer.add_argument("--repo", default=REPOSITORY)
    installer.add_argument("--cache", type=Path,
                           default=Path.home() / ".cache/neurodragon/art")
    installer.add_argument("--update", action="store_true", help="Explicitly fetch current remote HEAD")
    installer.add_argument("--ref", help="Fetch an exact private commit/tag for reproducible setup")
    installer.add_argument("--source", type=Path, help="Install a local exported bundle, without network")
    installer.add_argument("--reinstall", action="store_true",
                           help="Replace every listed installed file, ignoring the installation receipt")
    check = commands.add_parser("check", help="Explicit setup check; never runs on game startup")
    check.add_argument("--root", type=Path, default=ROOT)
    check.add_argument("--hashes", action="store_true", help="Also verify bytes against the installed manifest")
    args = parser.parse_args()
    try:
        if args.command == "export":
            export_art(args.root.resolve(), args.destination.resolve())
        elif args.command == "install":
            install(args)
        else:
            manifest = read_manifest(args.root / ".runtime")
            verify(args.root, manifest, hashes=args.hashes)
            print(f"Art setup complete: {len(manifest['files'])} files")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Art setup failed: {error}\nSee PRIVATE_ART.md for authenticated installation.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
