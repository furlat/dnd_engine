"""Build a static directory of saved reviews after recording/replay finishes."""

from html import escape
import json
from pathlib import Path
import shutil
from urllib.parse import quote


def write_run_index(output: Path) -> None:
    rows: list[str] = []
    total_clips = 0
    for path in sorted((output / "runs").glob("*/manifest.json"), reverse=True):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        run, cases = manifest["run"], manifest["cases"]
        videos = sum(bool(case.get("video")) for case in cases)
        failures = sum(case["status"] == "failed" for case in cases)
        total_clips += videos
        tags = sorted({tag for case in cases for tag in case["tags"]})
        titles = " · ".join(dict.fromkeys(case["title"] for case in cases))
        target = f"runs/{quote(path.parent.name)}/index.html"
        rows.append(
            f'<article class="saved-run"><h2><a href="{target}">{escape(run["created_at"])}</a></h2>'
            f'<p>{videos} clips · {len(cases)} cases · {failures} failed checks'
            f' · {escape(run.get("input_mode", "capture"))}</p>'
            f'<p class="run-tags">{escape(", ".join(tags))}</p>'
            f'<details><summary>Cases · {escape(path.parent.name)}</summary><p>{escape(titles)}</p></details></article>'
        )
    latest_path = output / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8")) if latest_path.exists() else None
    latest_link = f'<p><a href="{escape(latest["path"], quote=True)}">Open latest run →</a></p>' if latest else ""
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>All animation reviews</title><link rel="stylesheet" href="styles.css"></head>'
        '<body><main><p class="eyebrow">D&D ENGINE · LOCAL REVIEW</p><h1>All animation reviews</h1>'
        f'<p>{len(rows)} saved runs · {total_clips} clips across these runs (including repeat renders).</p>'
        '<p class="subtitle">Each run contains the cases recorded for that session. Open a run to watch its clips '
        'and export traces. Use Clear filters inside a run to show every case.</p>'
        f'{latest_link}<label>Find a run<input id="find-run" type="search" placeholder="Case, tag or date…"></label>'
        '<p id="run-count" role="status"></p><section class="saved-runs">'
        + "".join(rows)
        + '</section></main><script>'
        'const rows = [...document.querySelectorAll(".saved-run")];'
        'const search = document.getElementById("find-run");'
        'function filter() { const query = search.value.trim().toLowerCase();'
        'for (const row of rows) row.hidden = !row.textContent.toLowerCase().includes(query);'
        'document.getElementById("run-count").textContent = '
        '`${rows.filter(row => !row.hidden).length} / ${rows.length} runs shown`; }'
        'search.addEventListener("input", filter); filter();'
        '</script></body></html>', encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("gallery.css"), output / "styles.css")
