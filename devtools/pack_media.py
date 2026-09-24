"""Offline lossless page/packet packing; source registration remains authored."""

import argparse
import copy
import difflib
import json
from pathlib import Path
import sys
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

from devtools.art import contained, verify, write_json
from devtools.pack_art import art_name


def plan_media(selection: dict, phases: list[dict], bindings_root: Path,
               *, page_size: int = 2048) -> dict:
    selected = {row["path"]: row for row in selection["files"]}
    assets = {}
    documents = {}
    owners = {}
    for path in sorted(bindings_root.glob("*/projectile-assets.json")):
        assets.update({row["assetId"]: row for row in json.loads(path.read_text())})
    for path in sorted(bindings_root.glob("*/bindings.json")):
        document = json.loads(path.read_text())
        relative = path.relative_to(bindings_root).as_posix()
        documents[relative] = document
        for identity in document.get("projectileStorage", {}):
            owners[identity] = relative
    jobs, updates = [], {}
    used = set()
    member_bytes = 0
    for row in phases:
        identity, phase, kind = row["asset"], row["phase"], row["storage"]
        if kind not in ("loose_color_frames", "loose_component_packets", "loose_combined_packets"):
            continue
        owner = owners[identity]
        original = documents[owner]["projectileStorage"][identity]["phases"][phase]
        storage = copy.deepcopy(original)
        asset = assets[identity]
        base = f"game/assets/packed/{identity}/{phase}"
        packet = storage.get("surfaceFrames")
        if packet is not None:
            indices = sorted(set(packet["frameIndices"]))
            components = packet.get("componentsByFacing")
            if components is None:
                members = []
                for facing in asset["rowOrder"]:
                    for frame in indices:
                        source = packet["pattern"].format(direction=facing, frame=frame)
                        if source in selected:
                            members.append({"source": source, "member": f"{facing}/{frame:04}.bin.gz"})
                archive = base + ".zip"
                packet.pop("pattern")
                packet["archive"] = {"file": archive, "memberPattern": "{direction}/{frame:04}.bin.gz"}
                jobs.append({"kind": "xyz_archive", "output": archive, "members": members})
            else:
                for facing, parts in components.items():
                    archive = base + f"-{facing}.zip"
                    members = []
                    for index, part in enumerate(parts):
                        for frame in indices:
                            source = part["pattern"].format(direction=facing, frame=frame)
                            if source in selected:
                                members.append({"source": source,
                                                "member": f"component-{index:02}/{frame:04}.bin.gz"})
                        part.pop("pattern")
                        part["archive"] = {"file": archive,
                                           "memberPattern": f"component-{index:02}/{{frame:04}}.bin.gz"}
                    if members:
                        jobs.append({"kind": "xyz_archive", "output": archive, "members": members})
        else:
            width, height = asset["frame"]["width"], asset["frame"]["height"]
            if max(width, height) > page_size:
                raise ValueError(f"Native frame exceeds selected page size: {identity}")
            capacity = (page_size // width) * (page_size // height)
            for index, layer in enumerate(storage["layers"]):
                pattern = layer.pop("pattern")
                pages = {}
                for facing in asset["rowOrder"]:
                    frames = [frame for frame in range(asset["phases"][phase]["frames"])
                              if pattern.format(direction=facing, frame=frame) in selected]
                    groups = []
                    for frame in frames:
                        if not groups or frame != groups[-1][-1] + 1 or len(groups[-1]) == capacity:
                            groups.append([])
                        groups[-1].append(frame)
                    if not groups:
                        continue
                    pages[facing] = []
                    for group in groups:
                        columns = min(page_size // width, len(group))
                        output = base + f"-{index}-{facing}-{group[0]:04}.png"
                        pages[facing].append({"file": output, "firstFrame": group[0],
                                              "frameCount": len(group), "columns": columns})
                        jobs.append({"kind": "color_page", "output": output,
                            "canvas": [columns * width, ((len(group) + columns - 1) // columns) * height],
                            "frames": [{"source": pattern.format(direction=facing, frame=frame),
                                        "rect": [(local % columns) * width, (local // columns) * height, width, height]}
                                       for local, frame in enumerate(group)]})
                layer["pages"] = pages
        updates.setdefault(owner, {}).setdefault(identity, {})[phase] = {
            "before": original, "after": storage}
    # Several authored facings intentionally share complete source banks. Keep
    # their different registrations, but do not copy those packets into two ZIPs.
    archive_signatures, shared_archives, retained_jobs = {}, {}, []
    for job in jobs:
        if job["kind"] == "xyz_archive":
            signature = tuple((entry["member"], selected[entry["source"]]["sha256"],
                               selected[entry["source"]]["bytes"]) for entry in job["members"])
            if signature in archive_signatures:
                shared_archives[job["output"]] = archive_signatures[signature]
                continue
            archive_signatures[signature] = job["output"]
        retained_jobs.append(job)
    jobs = retained_jobs
    for phase_updates in updates.values():
        for asset_updates in phase_updates.values():
            for change in asset_updates.values():
                packet = change["after"].get("surfaceFrames")
                if packet is None:
                    continue
                sources = ([packet] if "archive" in packet else
                           [part for parts in packet["componentsByFacing"].values() for part in parts])
                for source in sources:
                    descriptor = source["archive"]
                    descriptor["file"] = shared_archives.get(descriptor["file"], descriptor["file"])
    for job in jobs:
        entries = job["members"] if job["kind"] == "xyz_archive" else job["frames"]
        if not entries:
            raise ValueError(f"Selected phase has no production samples: {job['output']}")
        for entry in entries:
            used.add(entry["source"])
            if job["kind"] == "xyz_archive":
                member_bytes += selected[entry["source"]]["bytes"]
    return {"version": 1, "jobs": jobs, "binding_updates": updates,
            "inputs": [selected[name] for name in sorted(used)],
            "summary": {"source_files": len(used), "source_bytes": sum(selected[name]["bytes"] for name in used),
                "xyz_archives": sum(job["kind"] == "xyz_archive" for job in jobs),
                "shared_archive_references": len(shared_archives),
                "unchanged_gzip_member_bytes": member_bytes,
                "color_pages": sum(job["kind"] == "color_page" for job in jobs),
                "max_color_page_decoded_bytes": max((job["canvas"][0] * job["canvas"][1] * 4
                    for job in jobs if job["kind"] == "color_page"), default=0),
                "note": "ZIP indexes add bytes; color PNG output sizes are measured only after building."}}


def build_media(plan: dict, archive: Path, bindings_root: Path, output: Path) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError("Media output directory must be new")
    if (output.resolve().is_relative_to(archive.resolve())
            or output.resolve().is_relative_to(bindings_root.resolve())):
        raise ValueError("Media output must be outside source archive and public bindings")
    if plan["version"] != 1:
        raise ValueError("Unsupported media plan")
    changes = []
    for relative, assets in plan["binding_updates"].items():
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Invalid binding output: {relative}")
        before = (bindings_root / relative).read_text()
        document = json.loads(before)
        for identity, phases in assets.items():
            for phase, change in phases.items():
                if document["projectileStorage"][identity]["phases"][phase] != change["before"]:
                    raise ValueError(f"Selected binding changed since planning: {identity}/{phase}")
                document["projectileStorage"][identity]["phases"][phase] = change["after"]
        after = (json.dumps(document, indent=2) if before.startswith("{\n") else
                 json.dumps(document, separators=(",", ":"))) + "\n"
        changes.append((relative, before, after))
    for job in plan["jobs"]:
        art_name(job["output"])
    verify(archive, {"files": plan["inputs"]})
    output.mkdir(parents=True)
    packed = []
    for job in plan["jobs"]:
        target = contained(output, job["output"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if job["kind"] == "xyz_archive":
            with ZipFile(target, "w", compression=ZIP_STORED, allowZip64=True) as bundle:
                for member in job["members"]:
                    bundle.write(contained(archive, member["source"]), member["member"])
        else:
            image = Image.new("RGBA", tuple(job["canvas"]))
            for frame in job["frames"]:
                with Image.open(contained(archive, frame["source"])) as source:
                    x, y, width, height = frame["rect"]
                    if source.size != (width, height):
                        raise ValueError(f"Native frame size differs from metadata: {frame['source']}")
                    image.paste(source.convert("RGBA"), (x, y))
            image.save(target)
            image.close()
        packed.append({"path": job["output"], "bytes": target.stat().st_size})
    patch = []
    for relative, before, after in changes:
        target = output / "bindings" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(after)
        patch.extend(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                     fromfile=f"a/game/data/{relative}", tofile=f"b/game/data/{relative}"))
    (output / "public-bindings.patch").write_text("".join(patch))
    result = {"kind": "packed_media", "version": 1,
              "files": packed, "encoded_bytes": sum(row["bytes"] for row in packed),
              "replaced_inputs": [row["path"] for row in plan["inputs"]],
              "binding_updates": plan["binding_updates"],
              "source_summary": plan["summary"],
              "status": "Staged output only; apply reviewed bindings and validate before installation."}
    write_json(output / "packed-media.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planning = commands.add_parser("plan", help="Metadata-only packing plan; no media reads")
    planning.add_argument("--selection", type=Path, required=True)
    planning.add_argument("--phases", type=Path, required=True)
    planning.add_argument("--bindings-root", type=Path, required=True)
    planning.add_argument("--page-size", type=int, default=2048)
    planning.add_argument("--output", type=Path, required=True)
    building = commands.add_parser("build", help="Pack selected inputs into a fresh output directory")
    building.add_argument("--plan", type=Path, required=True)
    building.add_argument("--archive", type=Path, required=True)
    building.add_argument("--bindings-root", type=Path, required=True)
    building.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            plan = plan_media(json.loads(args.selection.read_text()), json.loads(args.phases.read_text()),
                              args.bindings_root, page_size=args.page_size)
            write_json(args.output, plan)
            print(json.dumps(plan["summary"], sort_keys=True))
        else:
            result = build_media(json.loads(args.plan.read_text()), args.archive, args.bindings_root, args.output)
            print(json.dumps({"files": len(result["files"]), "encoded_bytes": result["encoded_bytes"]}))
    except (OSError, ValueError, KeyError) as error:
        print(f"Media packing failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
