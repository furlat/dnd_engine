"""Offline runtime-art selection and staging from the preserved inventory.

Plan reads metadata only. Stage copies selected payloads to a new directory;
neither command changes authoring, the installed game, or the source archive.
"""

import argparse
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

from devtools.art import MANIFEST, contained, copy_file, read_manifest, verify, write_json


def art_name(name: str) -> str:
    path = PurePosixPath(name)
    if (path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
            or path.parts[:2] != ("game", "assets")):
        raise ValueError(f"Invalid art path: {name}")
    return name


def build_plan(archive: Path, inventory: Path, applied_aliases: Path | None,
               code_release: str | None = None) -> dict:
    """Use published identities without opening payloads or computing checksums."""
    source = json.loads((archive / MANIFEST).read_text())
    files = {art_name(row["path"]): row for row in source["files"]}
    if source["version"] != 1 or not files or len(files) != len(source["files"]):
        raise ValueError("Unsupported, empty or duplicate source manifest")
    decisions = {}
    with inventory.open() as stream:
        for line in stream:
            row = json.loads(line)
            name = art_name(row["path"])
            original = files.get(name)
            if name in decisions or original is None:
                raise ValueError(f"Duplicate or unknown inventory path: {name}")
            if (row["bytes"] != original["bytes"]
                    or row["source_content_id"] != original["sha256"]):
                raise ValueError(f"Inventory differs from source manifest: {name}")
            if row["decision"] not in ("production", "archive_only"):
                raise ValueError(f"Unresolved inventory decision: {name}")
            decisions[name] = row["decision"]
    if decisions.keys() != files.keys():
        raise ValueError("Inventory must cover the complete source manifest")
    selected = {name: row for name, row in files.items() if decisions[name] == "production"}
    aliases = {}
    if applied_aliases is not None:
        with applied_aliases.open() as stream:
            for line in stream:
                row = json.loads(line)
                name, canonical = art_name(row["path"]), art_name(row["canonical"])
                if name in aliases or name == canonical or name not in selected or canonical not in selected:
                    raise ValueError(f"Invalid applied alias: {name} -> {canonical}")
                if any(selected[name][key] != selected[canonical][key] for key in ("bytes", "sha256")):
                    raise ValueError(f"Applied alias has a different published payload: {name}")
                aliases[name] = canonical
        if set(aliases) & set(aliases.values()):
            raise ValueError("Applied aliases must point directly to retained canonical payloads")
    retained = [row for name, row in sorted(selected.items()) if name not in aliases]
    if not retained:
        raise ValueError("Runtime selection is empty")
    return {
        "version": 1,
        "source_code_commit": source.get("source_code_commit"),
        "code_release": code_release,
        "files": retained,
        "applied_aliases": aliases,
        "counts": {
            "source_files": len(files), "source_bytes": sum(r["bytes"] for r in files.values()),
            "selected_references": len(selected), "selected_bytes": sum(r["bytes"] for r in selected.values()),
            "applied_aliases": len(aliases), "payload_files": len(retained),
            "payload_bytes": sum(r["bytes"] for r in retained),
        },
    }


def stage(archive: Path, destination: Path, plan: dict) -> None:
    """Copy the planned release only; no live binding edits or in-place pruning."""
    if destination.exists() or destination.is_symlink():
        raise ValueError("Production staging destination must be new")
    if destination.resolve().is_relative_to(archive.resolve()):
        raise ValueError("Production staging must be outside the preserved archive")
    source = json.loads((archive / MANIFEST).read_text())
    files = {row["path"]: row for row in source["files"]}
    if plan["version"] != 1 or not plan["files"]:
        raise ValueError("Unsupported or empty runtime plan")
    names = set()
    for row in plan["files"]:
        name = art_name(row["path"])
        if name in names or files.get(name) != row:
            raise ValueError(f"Planned payload differs from current source manifest: {name}")
        names.add(name)
        contained(destination, name)
    # Missing/unhydrated selected inputs fail before creating the destination.
    verify(archive, plan)
    destination.mkdir(parents=True)
    for row in plan["files"]:
        copy_file(contained(archive, row["path"]), contained(destination, row["path"]))
    manifest = {key: plan[key] for key in ("version", "source_code_commit", "code_release", "files")}
    write_json(destination / MANIFEST, manifest)
    write_json(destination / "production-selection.json", {
        "counts": plan["counts"], "applied_aliases": plan["applied_aliases"],
        "code_release": plan["code_release"],
    })


def propose_bindings(plan: dict, candidates: Path, bindings_root: Path, output: Path) -> dict:
    """Propose explicit VFX address edits; candidates are not yet applied aliases."""
    if output.exists() or output.resolve().is_relative_to(bindings_root.resolve()):
        raise ValueError("Binding proposal destination must be new and outside public bindings")
    selected = {row["path"]: row for row in plan["files"]}
    aliases = {}
    with candidates.open() as stream:
        for line in stream:
            row = json.loads(line)
            name, canonical = row["path"], row["canonical"]
            if name not in selected or canonical not in selected:
                continue
            if any(selected[name][key] != selected[canonical][key] for key in ("bytes", "sha256")):
                raise ValueError(f"Candidate alias differs from published payload: {name}")
            aliases[name] = canonical
    proposed = set()

    def storage_addresses(value):
        if isinstance(value, list):
            return [storage_addresses(child) for child in value]
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                if key == "file" and child in aliases:
                    proposed.add(child)
                    result[key] = aliases[child]
                else:
                    result[key] = storage_addresses(child)
            return result
        return value

    changes = []
    for path in sorted(bindings_root.glob("*/bindings.json")):
        before = path.read_text()
        document = json.loads(before)
        original = json.loads(before)
        if "projectileStorage" in document:
            document["projectileStorage"] = storage_addresses(document["projectileStorage"])
        for identity, name in document.get("resources", {}).items():
            if isinstance(name, str) and name in aliases:
                proposed.add(name)
                document["resources"][identity] = aliases[name]
        if document != original:
            after = (json.dumps(document, indent=2) if before.startswith("{\n") else
                     json.dumps(document, separators=(",", ":"))) + "\n"
            changes.append((path.relative_to(bindings_root), before, after))
    output.mkdir(parents=True)
    patch = []
    for relative, before, after in changes:
        target = output / "bindings" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(after)
        patch.extend(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                     fromfile=f"a/game/data/{relative.as_posix()}", tofile=f"b/game/data/{relative.as_posix()}"))
    (output / "public-bindings.patch").write_text("".join(patch))
    (output / "candidate-aliases.jsonl").write_text("".join(json.dumps({"path": name, "canonical": aliases[name]})
        + "\n" for name in sorted(proposed)))
    summary = {"changed_binding_documents": len(changes), "candidate_aliases": len(proposed),
               "candidate_bytes": sum(selected[name]["bytes"] for name in proposed),
               "status": "Proposal only. Confirm every remaining consumer before using as --applied-aliases."}
    write_json(output / "summary.json", summary)
    return summary


def finish_release(base: Path, packs: list[Path], bindings_root: Path,
                   destination: Path, *, code_release: str | None = None,
                   retain_sources: tuple[str, ...] = ()) -> dict:
    """Build a clean release after guarded public packing changes were applied.

    Existing payload identities are reused. New page/bundle identities are
    calculated once, during their copy; this is explicit release work only.
    """
    if destination.exists() or destination.is_symlink():
        raise ValueError("Final release destination must be new")
    roots = [base, bindings_root, *(path.parent for path in packs)]
    if any(destination.resolve().is_relative_to(root.resolve()) for root in roots):
        raise ValueError("Final release must be outside its source trees and public data")
    original = read_manifest(base)
    originals = {row["path"]: row for row in original["files"]}
    replaced, generated = set(), {}
    for pack_path in packs:
        pack = json.loads(pack_path.read_text())
        if pack["version"] != 1 or pack["kind"] not in ("packed_media", "packed_environment"):
            raise ValueError(f"Unsupported generated pack: {pack_path}")
        for relative, changes in pack["binding_updates"].items():
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise ValueError(f"Invalid public binding: {relative}")
            document = json.loads((bindings_root / relative).read_text())
            if pack["kind"] == "packed_media":
                for identity, phases in changes.items():
                    for phase, change in phases.items():
                        if document["projectileStorage"][identity]["phases"][phase] != change["after"]:
                            raise ValueError(f"Packing binding not applied: {identity}/{phase}")
            else:
                for change in changes:
                    if document[change["section"]][change["key"]] != change["after"]:
                        raise ValueError(f"Packing binding not applied: {change['key']}")
        replaced.update(art_name(name) for name in pack["replaced_inputs"])
        for row in pack["files"]:
            name = art_name(row["path"])
            if name in generated or name in originals:
                raise ValueError(f"Generated output collides with release payload: {name}")
            generated[name] = (pack_path.parent, row)
    if not replaced <= originals.keys():
        raise ValueError(f"Replaced input absent from base release: {min(replaced - originals.keys())}")
    retained_explicitly = {art_name(name) for name in retain_sources}
    if not retained_explicitly <= replaced:
        raise ValueError("--retain-source must name an input replaced by these packs")
    replaced -= retained_explicitly
    retained = [row for name, row in originals.items() if name not in replaced]
    # Read only selected new-output headers here. The existing staged base was
    # already preflighted; copying it does not rehash or re-audit its payloads.
    for root, row in generated.values():
        verify(root, {"files": [row]})
    destination.mkdir(parents=True)
    for row in retained:
        source = contained(base, row["path"])
        if source.stat().st_size != row["bytes"]:
            raise ValueError(f"Base payload size changed: {row['path']}")
        copy_file(source, contained(destination, row["path"]))
    files = list(retained)
    for name, (root, row) in generated.items():
        target = contained(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        checksum = hashlib.sha256()
        copied = 0
        with contained(root, name).open("rb") as source, target.open("wb") as sink:
            while chunk := source.read(1024 * 1024):
                sink.write(chunk)
                checksum.update(chunk)
                copied += len(chunk)
        if copied != row["bytes"]:
            raise ValueError(f"Generated payload size changed: {name}")
        files.append({"path": name, "bytes": copied, "sha256": checksum.hexdigest()})
    manifest = {key: value for key, value in original.items() if key != "files"}
    if code_release is not None:
        manifest["code_release"] = code_release
    manifest["files"] = sorted(files, key=lambda row: row["path"])
    write_json(destination / MANIFEST, manifest)
    summary = {"base_files": len(originals), "replaced_files": len(replaced),
               "retained_files": len(retained), "generated_files": len(generated),
               "files": len(files), "bytes": sum(row["bytes"] for row in files),
               "retained_replaced_sources": sorted(retained_explicitly)}
    write_json(destination / "production-finalization.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planning = commands.add_parser("plan", help="Read source/inventory metadata only")
    planning.add_argument("--archive", type=Path, required=True)
    planning.add_argument("--inventory", type=Path, required=True)
    planning.add_argument("--applied-aliases", type=Path,
                          help="JSONL path/canonical mappings already applied to the matching public bindings")
    planning.add_argument("--code-release", help="Matching public-code revision or release label")
    planning.add_argument("--output", type=Path, required=True)
    staging = commands.add_parser("stage", help="Copy selected payloads to a new production directory")
    staging.add_argument("--archive", type=Path, required=True)
    staging.add_argument("--plan", type=Path, required=True)
    staging.add_argument("--destination", type=Path, required=True)
    bindings = commands.add_parser("bindings", help="Propose public binding edits; never apply them")
    bindings.add_argument("--plan", type=Path, required=True)
    bindings.add_argument("--candidate-aliases", type=Path, required=True)
    bindings.add_argument("--bindings-root", type=Path, required=True)
    bindings.add_argument("--output", type=Path, required=True)
    finishing = commands.add_parser("finish", help="Build a clean release after reviewed packing bindings are applied")
    finishing.add_argument("--base", type=Path, required=True)
    finishing.add_argument("--pack", type=Path, action="append", required=True,
                           help="Generated packed-media.json or packed-environment.json; repeat for each pack")
    finishing.add_argument("--bindings-root", type=Path, required=True)
    finishing.add_argument("--destination", type=Path, required=True)
    finishing.add_argument("--code-release")
    finishing.add_argument("--retain-source", action="append", default=[],
                           help="Keep a replaced source still used by another reviewed consumer")
    args = parser.parse_args()
    try:
        if args.command == "plan":
            if args.output.resolve().is_relative_to(args.archive.resolve()):
                raise ValueError("Write packaging plans outside the preserved archive")
            plan = build_plan(args.archive, args.inventory, args.applied_aliases, args.code_release)
            write_json(args.output, plan)
        elif args.command == "stage":
            plan = json.loads(args.plan.read_text())
            stage(args.archive, args.destination, plan)
        elif args.command == "bindings":
            plan = json.loads(args.plan.read_text())
            print(json.dumps(propose_bindings(plan, args.candidate_aliases, args.bindings_root, args.output),
                             sort_keys=True))
            return 0
        else:
            print(json.dumps(finish_release(args.base, args.pack, args.bindings_root, args.destination,
                code_release=args.code_release, retain_sources=tuple(args.retain_source)), sort_keys=True))
            return 0
        print(json.dumps(plan["counts"], sort_keys=True))
    except (OSError, ValueError, KeyError) as error:
        print(f"Art packaging failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
