"""Render saved gameplay inputs; use --capture to generate them from native rules."""

import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import traceback
from uuid import uuid4

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from devtools.animation_review.cases import RecordedInput, ReviewSequence, load_cases, produce
from devtools.animation_review.record import record_case
from game.replay import decode_sequence, encode_sequence


REPO = Path(__file__).resolve().parents[2]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def source_identity() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    files = git("ls-files", "--cached", "--others", "--exclude-standard", "--", "game", "dnd", "content_data", "devtools", "tests/game")
    hashes = {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest()
              for name in sorted(set(files.splitlines())) if (REPO / name).is_file()}
    return {"branch": git("branch", "--show-current"), "commit": git("rev-parse", "HEAD"),
            "dirty": bool(git("status", "--porcelain")),
            "source_hash": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(), "files": hashes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=[], help="Case ID or glob; repeat to select several.")
    parser.add_argument("--tag", action="append", default=[], help="Include cases matching any selected tag.")
    parser.add_argument("--capture", action="store_true", help="Generate and replace selected saved inputs, then render their decoded bytes.")
    parser.add_argument("--review", type=Path, help="Render the recorded inputs embedded in an exported review JSON.")
    parser.add_argument("--list", action="store_true", help="List the catalog without running the engine.")
    parser.add_argument("--output", type=Path, default=Path(".runtime/animation-review"))
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=960, help="Width of each of the four camera views.")
    parser.add_argument("--height", type=int, default=640, help="Height of each camera view; video is a 2x2 mosaic.")
    args = parser.parse_args(argv)
    os.chdir(REPO)
    saved: dict[str, RecordedInput] = {}
    review_origins: dict[str, dict] = {}
    if args.review:
        if args.capture:
            parser.error("--review consumes recorded input; use --capture with catalog selection to generate new input")
        review = json.loads(args.review.read_text())
        if review.get("kind") != "dnd-animation-review":
            parser.error("--review must be an exported animation review")
        if not review.get("selections"):
            parser.error("exported review contains no selected cases")
        for row in review["selections"]:
            if not row.get("recorded_input"):
                parser.error("review contains a diagnostic trace without executable recorded input; "
                             "old traces cannot be faithfully replayed. Capture the scenario explicitly with --capture.")
            recorded = RecordedInput.model_validate(row["recorded_input"])
            if recorded.case.id != row["case"]["id"] or recorded.case.id in saved:
                parser.error("review contains a mismatched or duplicate recorded case")
            saved[recorded.case.id] = recorded
            review_origins[recorded.case.id] = {"run": review.get("run"), "review": row.get("review")}
        cases = tuple(recorded.case for recorded in saved.values())
    else:
        cases = load_cases()
    selected = tuple(case for case in cases if
                     (not args.case or any(fnmatch.fnmatchcase(case.id, pattern) for pattern in args.case)) and
                     (not args.tag or set(case.tags) & set(args.tag)))
    if not selected:
        parser.error("no catalog cases matched")
    if args.list:
        for case in selected:
            print(f"{case.id:28} {', '.join(case.tags)}")
        return 0
    output = args.output.resolve()
    if not args.capture and not args.review:
        missing = [case.id for case in selected if not (output / "inputs" / case.id / "input.json").is_file()]
        if missing:
            parser.error(f"no saved gameplay input for {', '.join(missing)}; use --capture to generate selected inputs once")
        for case in selected:
            path = output / "inputs" / case.id / "input.json"
            recorded = RecordedInput.model_validate_json(path.read_bytes())
            if recorded.case.id != case.id:
                parser.error(f"saved input {path} belongs to a different case")
            if recorded.case != case:
                print(f"{case.id}: using its recorded case definition; --capture explicitly replaces it.", flush=True)
            saved[case.id] = recorded
        selected = tuple(saved[case.id].case for case in selected)
    if not 1 <= args.fps <= 60 or min(args.width, args.height) < 240 or args.width % 2 or args.height % 2:
        parser.error("fps must be 1..60; even video dimensions must be at least 240")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None or shutil.which("ffprobe") is None:
        parser.error("ffmpeg and ffprobe are required to encode and validate videos")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]
    destination = output / "runs" / run_id
    destination.mkdir(parents=True)
    sources = source_identity()
    run = {"id": run_id, "created_at": now.isoformat(),
           **{key: value for key, value in sources.items() if key != "files"},
           "fps": args.fps, "width": args.width * 2, "height": args.height * 2,
           "view_width": args.width, "view_height": args.height, "layout": "four-corners-2x2",
           "input_mode": "capture" if args.capture else "review" if args.review else "saved",
           "command": shlex.join([sys.executable, "-m", "devtools.animation_review",
                                  *(["--capture"] if args.capture else []),
                                  *(["--review", str(args.review.resolve())] if args.review else []),
                                  "--fps", str(args.fps), "--width", str(args.width), "--height", str(args.height),
                                  "--output", str(output),
                                  *[arg for case in selected for arg in ("--case", case.id)]])}
    manifest = {"schema_version": 1, "run": run, "cases": []}
    write_json(destination / "sources.json", sources)
    for source, target in (("gallery.html", "index.html"), ("gallery.css", "styles.css"), ("gallery.js", "gallery.js")):
        shutil.copyfile(Path(__file__).with_name(source), destination / target)
    if args.capture:
        SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    for index, case in enumerate(selected):
        print(f"[{index + 1}/{len(selected)}] {case.id}", flush=True)
        relative = Path("cases") / case.id
        folder = destination / relative
        folder.mkdir(parents=True)
        trace = {"schema_version": 1, "run": run, "case": case.model_dump(mode="json"), "sources": sources}
        if case.id in review_origins:
            trace["review_origin"] = review_origins[case.id]
        item = {"id": case.id, "title": case.title, "tags": case.tags, "description": case.description,
                "video": None, "poster": None, "input": None, "trace": (relative / "trace.json").as_posix(),
                "duration_ms": 0, "frame_count": 0, "status": "failed", "checks": [], "gaps": []}
        try:
            if args.capture:
                generated = produce(case)
                recorded = RecordedInput(case=case, captured_at=now.isoformat(), sources=sources,
                                         sequence=json.loads(encode_sequence(generated.initialization, generated.lineages)))
                input_path = output / "inputs" / case.id / "input.json"
                input_path.parent.mkdir(parents=True, exist_ok=True)
                input_path.write_text(recorded.model_dump_json(), encoding="utf-8")
                # The first render crosses the same persisted boundary as every
                # later render. The producer's objects never enter record_case.
                recorded = RecordedInput.model_validate_json(input_path.read_bytes())
            else:
                recorded = saved[case.id]
            (folder / "input.json").write_text(recorded.model_dump_json(), encoding="utf-8")
            item["input"] = (relative / "input.json").as_posix()
            trace["input"] = {"captured_at": recorded.captured_at, "sources": recorded.sources}
            sequence = ReviewSequence(*decode_sequence(json.dumps(recorded.sequence, separators=(",", ":")).encode("utf-8")))
            item.update(record_case(case, folder, trace, sequence=sequence, fps=args.fps,
                                    size=(args.width, args.height), ffmpeg=ffmpeg))
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
