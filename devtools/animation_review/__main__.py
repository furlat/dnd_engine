"""Generate a fresh review run: python -m devtools.animation_review."""

import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from uuid import uuid4

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from devtools.animation_review.cases import load_cases
from devtools.animation_review.record import record_case


REPO = Path(__file__).resolve().parents[2]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def source_identity() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    files = git("ls-files", "--cached", "--others", "--exclude-standard", "--", "game", "dnd", "content_data", "devtools", "tests/game/scenarios.py")
    hashes = {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest()
              for name in sorted(set(files.splitlines())) if (REPO / name).is_file()}
    return {"branch": git("branch", "--show-current"), "commit": git("rev-parse", "HEAD"),
            "dirty": bool(git("status", "--porcelain")),
            "source_hash": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(), "files": hashes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=[], help="Case ID or glob; repeat to select several.")
    parser.add_argument("--tag", action="append", default=[], help="Include cases matching any selected tag.")
    parser.add_argument("--review", type=Path, help="Rerun the case IDs in an exported review JSON.")
    parser.add_argument("--list", action="store_true", help="List the catalog without running the engine.")
    parser.add_argument("--output", type=Path, default=Path(".runtime/animation-review"))
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=960, help="Width of each of the four camera views.")
    parser.add_argument("--height", type=int, default=640, help="Height of each camera view; video is a 2x2 mosaic.")
    args = parser.parse_args(argv)
    os.chdir(REPO)
    cases = load_cases()
    if args.review:
        review = json.loads(args.review.read_text())
        if review.get("kind") != "dnd-animation-review":
            parser.error("--review must be an exported animation review")
        if not review.get("selections"):
            parser.error("exported review contains no selected cases")
        args.case.extend(row["case"]["id"] for row in review["selections"])
        unknown = set(args.case) - {case.id for case in cases}
        if unknown:
            parser.error(f"review contains unavailable case IDs: {sorted(unknown)}")
    selected = tuple(case for case in cases if
                     (not args.case or any(fnmatch.fnmatchcase(case.id, pattern) for pattern in args.case)) and
                     (not args.tag or set(case.tags) & set(args.tag)))
    if not selected:
        parser.error("no catalog cases matched")
    if args.list:
        for case in selected:
            print(f"{case.id:28} {', '.join(case.tags)}")
        return 0
    if not 1 <= args.fps <= 60 or min(args.width, args.height) < 240 or args.width % 2 or args.height % 2:
        parser.error("fps must be 1..60; even video dimensions must be at least 240")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None or shutil.which("ffprobe") is None:
        parser.error("ffmpeg and ffprobe are required to encode and validate videos")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]
    output = args.output.resolve()
    destination = output / "runs" / run_id
    destination.mkdir(parents=True)
    sources = source_identity()
    run = {"id": run_id, "created_at": now.isoformat(),
           **{key: value for key, value in sources.items() if key != "files"},
           "fps": args.fps, "width": args.width * 2, "height": args.height * 2,
           "view_width": args.width, "view_height": args.height, "layout": "four-corners-2x2",
           "command": f"python -m devtools.animation_review --fps {args.fps} --width {args.width} --height {args.height} "
                      + " ".join(f"--case {case.id}" for case in selected)}
    manifest = {"schema_version": 1, "run": run, "cases": []}
    write_json(destination / "sources.json", sources)
    for source, target in (("gallery.html", "index.html"), ("gallery.css", "styles.css"), ("gallery.js", "gallery.js")):
        shutil.copyfile(Path(__file__).with_name(source), destination / target)
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    for index, case in enumerate(selected):
        print(f"[{index + 1}/{len(selected)}] {case.id}", flush=True)
        relative = Path("cases") / case.id
        folder = destination / relative
        folder.mkdir(parents=True)
        trace = {"schema_version": 1, "run": run, "case": case.model_dump(mode="json"), "sources": sources}
        item = {"id": case.id, "title": case.title, "tags": case.tags, "description": case.description,
                "video": None, "poster": None, "trace": (relative / "trace.json").as_posix(),
                "duration_ms": 0, "frame_count": 0, "status": "failed", "checks": [], "gaps": []}
        try:
            item.update(record_case(case, folder, trace, fps=args.fps, size=(args.width, args.height), ffmpeg=ffmpeg))
            item.update(video=(relative / "clip.mp4").as_posix(), poster=(relative / "poster.png").as_posix())
        except Exception as error:
            trace["error"] = traceback.format_exc()
            item.update(error=f"{type(error).__name__}: {error}", checks=trace.get("checks", []), gaps=trace.get("gaps", []))
            print(item["error"], flush=True)
        write_json(folder / "trace.json", trace)
        manifest["cases"].append(item)
        write_json(destination / "manifest.json", manifest)
    write_json(output / "latest.json", {"run": run_id, "path": f"runs/{run_id}/index.html"})
    (output / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=runs/{run_id}/index.html">'
        f'<a href="runs/{run_id}/index.html">Open latest animation review</a>', encoding="utf-8")
    failures = sum(case["status"] == "failed" for case in manifest["cases"])
    print(f"{len(selected) - failures}/{len(selected)} cases passed; gallery: {destination / 'index.html'}", flush=True)
    print(f"Serve: {sys.executable} -m devtools.animation_review.serve --directory {output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
