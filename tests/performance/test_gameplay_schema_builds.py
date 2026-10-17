"""No gameplay operation builds a validation schema (human: "move it to character creation as cost").

Conditions and actions defer their pydantic schema to first use. Creating a
character, creature, item or placed object builds what its content can create,
so a cast or a discovery builds nothing. Builds are process-wide, so
each case runs in a fresh Gallery Crowd worker; its report counts the schema
builds inside every measured operation (`schema_builds`).

Performance lane, run explicitly: `python -m pytest tests/performance` (one
fresh worker start per case, ~15-25 s each under load). The cases cast only
content their creatures own (no spell the harness builds itself).
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[2]
GALLERY = ROOT / "devtools" / "performance" / "gallery_crowd.py"
REPORTS = ROOT / ".runtime" / "single-pass" / "gallery_crowd"
# Destruction, spill and ignition products of a known spell; discovery of placed objects and a weapon attack;
# a godmode caster's Command (every area spell is its creation content).
CASES = ("fireball", "choices_fighter", "choices_caster")


@pytest.mark.parametrize("case", CASES)
def test_gallery_operations_build_no_schema(case):
    name = f"schema_builds_{case}_{uuid4().hex}"
    completed = subprocess.run([sys.executable, str(GALLERY), "--case", case, "--mode", "ordinary", "--name", name],
        cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True, timeout=600)
    report_path = REPORTS / f"{name}.json"
    try:
        report = json.loads(report_path.read_text())
    finally:
        report_path.unlink(missing_ok=True)
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert report["status"] == "passed", report.get("error")
    rows = report["operations"]
    assert [row.get("harness_built", []) for row in rows] == [[] for _ in rows]
    builds = {f"{index}:{row['kind']}": row["schema_builds"] for index, row in enumerate(rows)}
    assert builds == {key: [] for key in builds}
