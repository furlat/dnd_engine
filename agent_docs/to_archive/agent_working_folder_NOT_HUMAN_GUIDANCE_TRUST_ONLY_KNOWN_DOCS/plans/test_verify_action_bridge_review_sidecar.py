from __future__ import annotations

import copy
import fcntl
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("verify_action_bridge_review_sidecar.py")
SPEC = importlib.util.spec_from_file_location("action_bridge_review_verifier", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)

ENGINE_ROOT = Path(
    subprocess.run(
        ["git", "-C", str(Path(__file__).parent), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
)
CLIENT_ROOT = Path("/home/tommaso/Dev/NeuroClient")


@pytest.fixture(scope="session", autouse=True)
def _serialize_verifier_suites():
    """Keep repository-dirty-set fixtures isolated across concurrent review runs."""
    lock_path = Path(tempfile.gettempdir()) / "dnd-action-bridge-review-verifier.lock"
    with lock_path.open("w", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
    ).stdout


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_row(repository_id: str, root: Path, excluded: Path) -> dict[str, object]:
    dirty = verifier._git_dirty_paths(root)
    excluded_relative = verifier._relative_to_samefile(excluded, root)
    if excluded_relative:
        dirty.discard(excluded_relative)
    artifacts = [
        {"path": relative, "sha256": _sha(root / relative)}
        for relative in sorted(dirty)
    ]
    return {
        "repository_id": repository_id,
        "root": str(root),
        "git_head": _git(root, "rev-parse", "HEAD").decode().strip(),
        "tracked_diff_sha256": hashlib.sha256(
            _git(root, "diff", "--binary", "HEAD", "--")
        ).hexdigest(),
        "reviewed_artifacts": artifacts,
    }


def _valid_sidecar(plan: Path, reviews: Path) -> dict[str, object]:
    plan_sha = _sha(plan)
    baseline = {
        "schema": "dnd.action_execution_bridge.review_source_baseline",
        "schema_version": 1,
        "repositories": [
            _repository_row("engine", ENGINE_ROOT, reviews),
            _repository_row("neuroclient", CLIENT_ROOT, reviews),
        ],
    }
    baseline_sha = verifier._canonical_sha256(baseline)
    roles = [
        "internal_backend_sdk",
        "internal_causal_vocabulary",
        "internal_neuroclient_studio",
        "independent_project_task",
    ]
    reviews_rows: list[dict[str, object]] = []
    for index, role in enumerate(roles):
        verdict = f"ACCEPT {plan_sha} reviewer {index}"
        reviews_rows.append(
            {
                "review_id": f"review-{index}",
                "reviewer_role": role,
                "reviewer_identity": verifier.REQUIRED_REVIEWERS[role],
                "reviewed_plan_sha256": plan_sha,
                "review_source_baseline_sha256": baseline_sha,
                "verdict": "ACCEPT",
                "completed_at": f"2026-08-12T10:00:0{index}+00:00",
                "verbatim_verdict": verdict,
                "verdict_sha256": hashlib.sha256(verdict.encode()).hexdigest(),
                "blocking_findings": [],
            }
        )
    return {
        "schema": "dnd.action_execution_bridge.plan_reviews",
        "schema_version": 1,
        "plan_path": str(plan),
        "plan_sha256": plan_sha,
        "required_roles": roles,
        "review_source_baseline": baseline,
        "review_source_baseline_sha256": baseline_sha,
        "reviews": reviews_rows,
    }


def _write(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")


@pytest.fixture()
def valid_record():
    plans_dir = Path(__file__).parent
    with tempfile.TemporaryDirectory(prefix="review-verifier-", dir=plans_dir) as directory:
        root = Path(directory)
        plan = root / "plan.md"
        plan.write_text("frozen plan\n", encoding="utf-8")
        plan_sha = _sha(plan)
        reviews = root / f"{plan.name}.reviews.{plan_sha}.json"
        value = _valid_sidecar(plan, reviews)
        _write(reviews, value)
        yield plan, reviews, value


def _verify(plan: Path, reviews: Path) -> None:
    verifier.verify(plan, reviews, CLIENT_ROOT, require_all_accept=True)


def test_valid_record_passes(valid_record) -> None:
    plan, reviews, _ = valid_record
    _verify(plan, reviews)


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_root",
        "unknown_key",
        "non_rfc3339",
        "reordered_timestamp",
        "equal_timestamp",
        "same_reviewer",
        "accept_with_blocker",
        "other_baseline",
        "wrong_plan_hash",
        "wrong_artifact_hash",
    ],
)
def test_record_mutations_fail(valid_record, mutation: str) -> None:
    plan, reviews, original = valid_record
    value = copy.deepcopy(original)
    if mutation == "wrong_root":
        value["review_source_baseline"]["repositories"][1]["root"] = str(ENGINE_ROOT)
    elif mutation == "unknown_key":
        value["unexpected"] = True
    elif mutation == "non_rfc3339":
        value["reviews"][0]["completed_at"] = "2026-08-12 10:00:00+00:00"
    elif mutation == "reordered_timestamp":
        value["reviews"][2]["completed_at"] = "2026-08-12T09:00:00Z"
    elif mutation == "equal_timestamp":
        value["reviews"][1]["completed_at"] = value["reviews"][0]["completed_at"]
    elif mutation == "same_reviewer":
        for review in value["reviews"]:
            review["reviewer_identity"] = "one-reviewer"
    elif mutation == "accept_with_blocker":
        value["reviews"][0]["blocking_findings"] = ["still blocked"]
    elif mutation == "other_baseline":
        value["reviews"][0]["review_source_baseline_sha256"] = "0" * 64
    elif mutation == "wrong_plan_hash":
        value["plan_sha256"] = "0" * 64
    elif mutation == "wrong_artifact_hash":
        engine_row = next(
            repository
            for repository in value["review_source_baseline"]["repositories"]
            if repository["repository_id"] == "engine"
        )
        assert engine_row["reviewed_artifacts"]
        engine_row["reviewed_artifacts"][0]["sha256"] = "0" * 64
        replacement_baseline_sha = verifier._canonical_sha256(
            value["review_source_baseline"]
        )
        value["review_source_baseline_sha256"] = replacement_baseline_sha
        for review in value["reviews"]:
            review["review_source_baseline_sha256"] = replacement_baseline_sha
    _write(reviews, value)
    with pytest.raises(verifier.ReviewError):
        _verify(plan, reviews)


def test_nonadjacent_and_misprefixed_sidecars_fail(valid_record, tmp_path: Path) -> None:
    plan, reviews, value = valid_record
    nonadjacent = tmp_path / reviews.name
    _write(nonadjacent, value)
    with pytest.raises(verifier.ReviewError):
        _verify(plan, nonadjacent)

    misprefixed = reviews.with_name(f"wrong-{reviews.name}")
    _write(misprefixed, value)
    with pytest.raises(verifier.ReviewError):
        _verify(plan, misprefixed)
    misprefixed.unlink()


def test_git_status_z_handles_odd_rename_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    old = repo / "old name -> marker.txt"
    old.write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "--", old.name], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "seed"], check=True, capture_output=True)
    new = repo / "new name with spaces.txt"
    old.rename(new)
    dirty = verifier._git_dirty_paths(repo)
    assert old.name in dirty
    assert new.name in dirty
