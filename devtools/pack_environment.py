"""Offline lossless paging for selected environment banks and loose mechanisms."""

import argparse
import copy
import json
from pathlib import Path
import sys

from PIL import Image

from devtools.art import contained, verify, write_json
from devtools.pack_art import art_name


def page_cells(cells: list[dict], cell: tuple[int, int], base: str,
               page_size: int) -> tuple[list[dict], list[dict]]:
    """Keep cell pixels unmodified; return pages and one address per logical cell."""
    width, height = cell
    if min(width, height) <= 0 or max(width, height) > page_size:
        raise ValueError(f"Cell does not fit selected page size: {base}: {cell}")
    columns = page_size // width
    capacity = columns * (page_size // height)
    jobs, addresses = [], []
    for start in range(0, len(cells), capacity):
        group = cells[start:start + capacity]
        local_columns = min(columns, len(group))
        path = f"{base}-{start // capacity:03}.png"
        entries = []
        for index, source in enumerate(group):
            rect = [(index % local_columns) * width, (index // local_columns) * height, width, height]
            entries.append({**source, "rect": rect})
            addresses.append({"path": path.removeprefix("game/assets/"), "rect": rect})
        jobs.append({"output": path,
                     "canvas": [local_columns * width,
                                ((len(group) + local_columns - 1) // local_columns) * height],
                     "cells": entries})
    return jobs, addresses


def plan_environment(selection: dict, archive: Path, data: Path,
                     *, page_size: int = 2048) -> dict:
    """Read authored metadata and loose PNG headers, without decoding images."""
    selected = {row["path"]: row for row in selection["files"]}
    banks = json.loads((data / "environment_art.json").read_text())["banks"]
    resources = json.loads((data / "assets.json").read_text())["resources"]
    jobs, updates = [], {"environment_art.json": [], "assets.json": []}
    counts = {"color_banks": 0, "depth_banks": 0, "static_frame_banks": 0,
              "static_frame_cells": 0, "loose_resources": 0}
    maximum_source = 0
    for identity, original in banks.items():
        bank = copy.deepcopy(original)
        count, rows = bank["frame_count"], bank["rows"]
        width, height = bank["cell"]
        if width * count > page_size:
            source = art_name("game/assets/" + bank.pop("path"))
            maximum_source = max(maximum_source, width * count * height * len(rows) * 4)
            cells = [{"source": source, "source_rect": [frame * width, row * height, width, height]}
                     for row in range(len(rows)) for frame in range(count)]
            pages, addresses = page_cells(cells, (width, height),
                f"game/assets/packed/environment/{identity}/color", page_size)
            jobs.extend(pages)
            bank["frames_by_pose"] = {pose: addresses[row * count:(row + 1) * count]
                                      for row, pose in enumerate(rows)}
            counts["color_banks"] += 1
            if "actor_depth" in bank:
                depth = bank["actor_depth"]
                source = art_name("game/assets/" + depth.pop("path"))
                dw, dh = depth["cell"]
                cells = [{"source": source, "source_rect": [frame * dw, row * dh, dw, dh]}
                         for row in range(len(rows)) for frame in range(count)]
                pages, addresses = page_cells(cells, (dw, dh),
                    f"game/assets/packed/environment/{identity}/depth", page_size)
                jobs.extend(pages)
                bank["depth_frames_by_pose"] = {pose: addresses[row * count:(row + 1) * count]
                                                for row, pose in enumerate(rows)}
                counts["depth_banks"] += 1
        if "frame_path" in bank:
            source = art_name("game/assets/" + bank.pop("frame_path"))
            cells = [{"source": source, "source_rect": [0, row * height, width, height]}
                     for row in range(len(rows))]
            pages, addresses = page_cells(cells, (width, height),
                f"game/assets/packed/environment/{identity}/frame", page_size)
            jobs.extend(pages)
            bank["frame_regions_by_pose"] = dict(zip(rows, addresses, strict=True))
            counts["static_frame_banks"] += 1
            counts["static_frame_cells"] += len(rows)
        if bank != original:
            updates["environment_art.json"].append(
                {"section": "banks", "key": identity, "before": original, "after": bank})

    # These selected image resources already have independent semantic IDs.
    # Packing changes only their physical address, never their animation lookup.
    groups, retained = {}, []
    families = ("/lever/", "/spikes/", "/spikes-blood/", "/spikes-coated/", "/trap-workshop/")
    for identity, resource in resources.items():
        source = art_name("game/assets/" + resource["path"])
        if source not in selected or not any(family in resource["path"] for family in families):
            continue
        if "rect" in resource:
            raise ValueError(f"Resource is already region-addressed: {identity}")
        with Image.open(contained(archive, source)) as image:
            width, height = image.size
        if max(width, height) > page_size:
            retained.append({"key": identity, "path": source,
                             "reason": "Existing strip exceeds whole-image page; retain its current frame sampler."})
            continue
        if resource["native_size"] != [width, height]:
            raise ValueError(f"Loose resource native size differs from source: {identity}")
        parent = str(Path(source).parent)
        groups.setdefault((parent, width, height), []).append((identity, resource, source))
    for (parent, width, height), group in sorted(groups.items()):
        cells = [{"source": source, "source_rect": [0, 0, width, height]}
                 for _, _, source in group]
        base = "game/assets/packed/" + parent.removeprefix("game/assets/") + f"/{width}x{height}"
        pages, addresses = page_cells(cells, (width, height), base, page_size)
        jobs.extend(pages)
        for (identity, resource, _), address in zip(group, addresses, strict=True):
            updates["assets.json"].append({"section": "resources", "key": identity,
                                          "before": resource, "after": {**resource, **address}})
        counts["loose_resources"] += len(group)
    used = {cell["source"] for job in jobs for cell in job["cells"]}
    missing = used - selected.keys()
    if missing:
        raise ValueError(f"Packing refers to unselected source: {min(missing)}")
    return {"version": 1, "jobs": jobs, "binding_updates": updates, "retained_resources": retained,
            "inputs": [selected[name] for name in sorted(used)],
            "summary": {**counts, "source_files": len(used),
                        "source_bytes": sum(selected[name]["bytes"] for name in used),
                        "pages": len(jobs), "retained_large_resources": len(retained),
                        "maximum_source_decoded_bytes": maximum_source,
                        "maximum_page_decoded_bytes": max((job["canvas"][0] * job["canvas"][1] * 4
                                                             for job in jobs), default=0)}}


def build_environment(plan: dict, archive: Path, data: Path, output: Path) -> dict:
    """Write separate pages and guarded binding records; never alter live data."""
    if output.exists() or output.is_symlink():
        raise ValueError("Environment output directory must be new")
    if (output.resolve().is_relative_to(archive.resolve())
            or output.resolve().is_relative_to(data.resolve())):
        raise ValueError("Output must be outside archive and public data")
    if plan["version"] != 1:
        raise ValueError("Unsupported environment plan")
    documents = {}
    for relative, changes in plan["binding_updates"].items():
        if relative not in ("environment_art.json", "assets.json"):
            raise ValueError(f"Unknown environment binding: {relative}")
        document = json.loads((data / relative).read_text())
        for change in changes:
            if document[change["section"]][change["key"]] != change["before"]:
                raise ValueError(f"Selected binding changed since planning: {change['key']}")
            document[change["section"]][change["key"]] = change["after"]
        documents[relative] = document
    for job in plan["jobs"]:
        art_name(job["output"])
    verify(archive, {"files": plan["inputs"]})
    output.mkdir(parents=True)
    files, source_path, source_image = [], None, None
    try:
        for job in plan["jobs"]:
            target = contained(output, job["output"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with Image.new("RGBA", tuple(job["canvas"])) as page:
                for cell in job["cells"]:
                    if cell["source"] != source_path:
                        if source_image is not None:
                            source_image.close()
                        source_path = cell["source"]
                        with Image.open(contained(archive, source_path)) as image:
                            source_image = image.convert("RGBA")
                    sx, sy, sw, sh = cell["source_rect"]
                    x, y, width, height = cell["rect"]
                    if (source_image is None or (sw, sh) != (width, height)
                            or sx < 0 or sy < 0 or sx + sw > source_image.width
                            or sy + sh > source_image.height):
                        raise ValueError(f"Invalid source cell: {cell}")
                    with source_image.crop((sx, sy, sx + sw, sy + sh)) as pixels:
                        page.paste(pixels, (x, y))
                page.save(target)
            files.append({"path": job["output"], "bytes": target.stat().st_size})
    finally:
        if source_image is not None:
            source_image.close()
    for relative, document in documents.items():
        write_json(output / "bindings" / relative, document)
    # A source strip can also serve an unchanged resource sampler, even when
    # another bank using that same strip has been paged. Keep that dependency.
    retained_paths = {row["path"] for row in plan["retained_resources"]}
    result = {"kind": "packed_environment", "version": 1,
              "files": files, "encoded_bytes": sum(row["bytes"] for row in files),
              "replaced_inputs": [row["path"] for row in plan["inputs"]
                                  if row["path"] not in retained_paths],
              "binding_updates": plan["binding_updates"], "source_summary": plan["summary"],
              "status": "Staged only; apply guarded records to current data, then validate and install."}
    write_json(output / "packed-environment.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planning = commands.add_parser("plan", help="Read binding metadata and loose PNG dimensions only")
    planning.add_argument("--selection", type=Path, required=True)
    planning.add_argument("--page-size", type=int, default=2048)
    building = commands.add_parser("build", help="Copy cells unchanged into a separate new output")
    building.add_argument("--plan", type=Path, required=True)
    for command in (planning, building):
        command.add_argument("--archive", type=Path, required=True)
        command.add_argument("--data", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            result = plan_environment(json.loads(args.selection.read_text()), args.archive,
                                      args.data, page_size=args.page_size)
            write_json(args.output, result)
            print(json.dumps(result["summary"], sort_keys=True))
        else:
            result = build_environment(json.loads(args.plan.read_text()), args.archive, args.data, args.output)
            print(json.dumps({"files": len(result["files"]), "encoded_bytes": result["encoded_bytes"]}))
    except (OSError, ValueError, KeyError) as error:
        print(f"Environment packing failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
