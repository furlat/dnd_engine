#!/usr/bin/env python3
"""Verify detached reviews for the action-execution bridge plan."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA = "dnd.action_execution_bridge.plan_reviews"
SCHEMA_VERSION = 1
REQUIRED_ROLES = {
    "internal_backend_sdk",
    "internal_causal_vocabulary",
    "internal_neuroclient_studio",
    "independent_project_task",
}
REQUIRED_REVIEWERS = {
    "internal_backend_sdk": "/root/first_unit_contract_cut",
    "internal_causal_vocabulary": "/root/forced_move_unit_boundary",
    "internal_neuroclient_studio": "/root/first_unit_prioritization",
    "independent_project_task": "codex-thread:019ff6ba-7b0e-7003-81ff-b815d9a9df29",
}
HEX_256 = re.compile(r"^[0-9a-f]{64}$")
HEX_160 = re.compile(r"^[0-9a-f]{40}$")
RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
SIDECAR_KEYS = {
    "schema",
    "schema_version",
    "plan_path",
    "plan_sha256",
    "required_roles",
    "review_source_baseline",
    "review_source_baseline_sha256",
    "reviews",
}
BASELINE_KEYS = {"schema", "schema_version", "repositories"}
REPOSITORY_KEYS = {
    "repository_id",
    "root",
    "git_head",
    "tracked_diff_sha256",
    "reviewed_artifacts",
}
ARTIFACT_KEYS = {"path", "sha256"}
REVIEW_KEYS = {
    "review_id",
    "reviewer_role",
    "reviewer_identity",
    "reviewed_plan_sha256",
    "review_source_baseline_sha256",
    "verdict",
    "completed_at",
    "verbatim_verdict",
    "verdict_sha256",
    "blocking_findings",
}


class ReviewError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReviewError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewError(f"cannot read reviews: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewError("review sidecar root must be an object")
    return value


def _assert_no_floats(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        raise ReviewError(f"float is forbidden in canonical review JSON at {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_no_floats(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_floats(child, f"{path}[{index}]")


def _canonical_sha256(value: Any) -> str:
    _assert_no_floats(value)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or HEX_256.fullmatch(value) is None:
        raise ReviewError(f"{label} must be a lowercase SHA-256")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReviewError(f"{label} must be a nonempty string")
    return value


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ReviewError(
            f"{label} keys mismatch: missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReviewError(f"git command failed for {root}: {' '.join(args)}") from exc


def _same_file(left: Path, right: Path) -> bool:
    """Compare existing paths by filesystem identity, including DrvFs case aliases."""
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def _relative_to_samefile(path: Path, root: Path) -> str:
    """Return a relative path even when one DrvFs spelling differs only by case."""
    absolute = path.absolute()
    parts = [absolute.name]
    cursor = absolute.parent
    while True:
        if _same_file(cursor, root):
            return Path(*reversed(parts)).as_posix()
        if cursor == cursor.parent:
            return ""
        parts.append(cursor.name)
        cursor = cursor.parent


def _git_toplevel(path: Path) -> Path:
    root = Path(_git(path, "rev-parse", "--show-toplevel").decode("utf-8").strip()).absolute()
    if not root.is_dir():
        raise ReviewError(f"git top level does not exist: {root}")
    return root


def _git_dirty_paths(root: Path) -> set[str]:
    """Parse porcelain v1 -z without shell quoting or rename ambiguity."""
    payload = _git(root, "status", "--porcelain=v1", "-z", "-uall")
    fields = payload.split(b"\0")
    if fields[-1] != b"":
        raise ReviewError(f"unterminated git status payload for {root}")
    fields.pop()
    dirty: set[str] = set()
    index = 0
    while index < len(fields):
        record = fields[index]
        index += 1
        if len(record) < 4 or record[2:3] != b" ":
            raise ReviewError(f"unparseable git status record for {root}: {record!r}")
        status = record[:2]
        try:
            path = record[3:].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReviewError(f"non-UTF-8 git path in {root}") from exc
        dirty.add(Path(path).as_posix())
        if b"R" in status or b"C" in status:
            if index >= len(fields):
                raise ReviewError(f"rename/copy record lacks source path for {root}: {record!r}")
            try:
                source = fields[index].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ReviewError(f"non-UTF-8 git rename path in {root}") from exc
            index += 1
            dirty.add(Path(source).as_posix())
    return dirty


def _verify_review_source_baseline(
    baseline: dict[str, Any], *, reviews_path: Path, engine_root: Path, neuroclient_root: Path
) -> None:
    _require_exact_keys(baseline, BASELINE_KEYS, "review_source_baseline")
    if baseline.get("schema") != "dnd.action_execution_bridge.review_source_baseline":
        raise ReviewError("unsupported review source baseline schema")
    if baseline.get("schema_version") != 1:
        raise ReviewError("unsupported review source baseline version")
    repositories = baseline.get("repositories")
    if not isinstance(repositories, list) or len(repositories) != 2:
        raise ReviewError("review baseline must contain exactly two repositories")
    seen_repository_ids: set[str] = set()
    seen_roots: list[Path] = []
    for index, repository in enumerate(repositories):
        label = f"review_source_baseline.repositories[{index}]"
        if not isinstance(repository, dict):
            raise ReviewError(f"{label} must be an object")
        _require_exact_keys(repository, REPOSITORY_KEYS, label)
        repository_id = _require_string(repository.get("repository_id"), f"{label}.repository_id")
        if repository_id in seen_repository_ids:
            raise ReviewError(f"duplicate repository_id: {repository_id}")
        seen_repository_ids.add(repository_id)
        declared_root = Path(_require_string(repository.get("root"), f"{label}.root")).absolute()
        if not declared_root.is_dir():
            raise ReviewError(f"repository root does not exist: {declared_root}")
        root = _git_toplevel(declared_root)
        if not _same_file(root, declared_root):
            raise ReviewError(f"declared repository root is not its git top level: {declared_root}")
        expected_root = engine_root if repository_id == "engine" else neuroclient_root
        if repository_id not in {"engine", "neuroclient"} or not _same_file(root, expected_root):
            raise ReviewError(f"{label} is not the required {repository_id} repository: {root}")
        if any(_same_file(root, prior) for prior in seen_roots):
            raise ReviewError("engine and neuroclient review roots must be distinct")
        seen_roots.append(root)
        expected_head = _require_string(repository.get("git_head"), f"{label}.git_head")
        if HEX_160.fullmatch(expected_head) is None:
            raise ReviewError(f"{label}.git_head must be a lowercase 40-hex commit")
        actual_head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
        if actual_head != expected_head:
            raise ReviewError(f"{label} HEAD mismatch: {expected_head} != {actual_head}")
        expected_diff = _require_sha256(repository.get("tracked_diff_sha256"), f"{label}.tracked_diff_sha256")
        actual_diff = hashlib.sha256(_git(root, "diff", "--binary", "HEAD", "--")).hexdigest()
        if actual_diff != expected_diff:
            raise ReviewError(f"{label} tracked diff mismatch: {expected_diff} != {actual_diff}")

        artifacts = repository.get("reviewed_artifacts")
        if not isinstance(artifacts, list):
            raise ReviewError(f"{label}.reviewed_artifacts must be an array")
        artifact_paths: set[str] = set()
        for artifact_index, artifact in enumerate(artifacts):
            artifact_label = f"{label}.reviewed_artifacts[{artifact_index}]"
            if not isinstance(artifact, dict):
                raise ReviewError(f"{artifact_label} must be an object")
            _require_exact_keys(artifact, ARTIFACT_KEYS, artifact_label)
            relative = _require_string(artifact.get("path"), f"{artifact_label}.path")
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
                raise ReviewError(f"{artifact_label}.path must be a normalized relative POSIX path")
            if relative in artifact_paths:
                raise ReviewError(f"duplicate reviewed artifact: {repository_id}:{relative}")
            artifact_paths.add(relative)
            expected_sha = _require_sha256(artifact.get("sha256"), f"{artifact_label}.sha256")
            actual_sha = _file_sha256(root / path)
            if actual_sha != expected_sha:
                raise ReviewError(
                    f"reviewed artifact mismatch for {repository_id}:{relative}: {expected_sha} != {actual_sha}"
                )

        dirty_paths = _git_dirty_paths(root)
        sidecar_relative = _relative_to_samefile(reviews_path, root)
        if sidecar_relative:
            dirty_paths.discard(sidecar_relative)
        if dirty_paths != artifact_paths:
            raise ReviewError(
                f"{label} dirty artifact set mismatch: expected={sorted(artifact_paths)}, actual={sorted(dirty_paths)}"
            )
    if seen_repository_ids != {"engine", "neuroclient"}:
        raise ReviewError("review baseline repository IDs must be engine and neuroclient")


def verify(
    plan_path: Path,
    reviews_path: Path,
    neuroclient_root: Path,
    *,
    require_all_accept: bool,
) -> None:
    sidecar = _load_json(reviews_path)
    _require_exact_keys(sidecar, SIDECAR_KEYS, "review sidecar")
    if sidecar.get("schema") != SCHEMA or sidecar.get("schema_version") != SCHEMA_VERSION:
        raise ReviewError("unsupported review sidecar schema")

    supplied_plan = plan_path.absolute()
    engine_root = _git_toplevel(supplied_plan.parent)
    expected_neuroclient_root = _git_toplevel(neuroclient_root.absolute())
    if _same_file(engine_root, expected_neuroclient_root):
        raise ReviewError("engine and neuroclient roots must be distinct")
    declared_plan = Path(_require_string(sidecar.get("plan_path"), "plan_path"))
    if not declared_plan.is_absolute():
        declared_plan = (Path.cwd() / declared_plan).absolute()
    if not _same_file(declared_plan, supplied_plan):
        raise ReviewError(f"plan_path mismatch: {declared_plan} != {supplied_plan}")

    actual_plan_sha = _file_sha256(supplied_plan)
    declared_plan_sha = _require_sha256(sidecar.get("plan_sha256"), "plan_sha256")
    if declared_plan_sha != actual_plan_sha:
        raise ReviewError(f"plan SHA-256 mismatch: {declared_plan_sha} != {actual_plan_sha}")
    expected_name = f"{supplied_plan.name}.reviews.{actual_plan_sha}.json"
    if not _same_file(reviews_path.absolute().parent, supplied_plan.parent) or reviews_path.name != expected_name:
        raise ReviewError(f"review sidecar must be beside the plan with exact name {expected_name}")

    roles = sidecar.get("required_roles")
    if not isinstance(roles, list) or set(roles) != REQUIRED_ROLES or len(roles) != len(REQUIRED_ROLES):
        raise ReviewError("required_roles must contain the four exact roles once")

    baseline = sidecar.get("review_source_baseline")
    if not isinstance(baseline, dict) or not baseline:
        raise ReviewError("review_source_baseline must be a nonempty object")
    actual_baseline_sha = _canonical_sha256(baseline)
    declared_baseline_sha = _require_sha256(
        sidecar.get("review_source_baseline_sha256"), "review_source_baseline_sha256"
    )
    if actual_baseline_sha != declared_baseline_sha:
        raise ReviewError(
            f"review source baseline mismatch: {declared_baseline_sha} != {actual_baseline_sha}"
        )
    _verify_review_source_baseline(
        baseline,
        reviews_path=reviews_path,
        engine_root=engine_root,
        neuroclient_root=expected_neuroclient_root,
    )

    required_engine_artifacts = {
        _relative_to_samefile(supplied_plan, engine_root),
        _relative_to_samefile(Path(__file__).absolute(), engine_root),
        _relative_to_samefile(Path(__file__).with_name("test_verify_action_bridge_review_sidecar.py"), engine_root),
        "tools/RENDERER_NEUTRAL_GAMEPLAY_BRIDGE_STUDY.md",
        "tools/PRESENTATION_BRIDGE_AUDIT.md",
        "tools/PRESENTATION_BRIDGE_AUDIT.json",
        "tools/audit_presentation_bridge.py",
        "tools/presentation_bridge_action_sites.py",
    }
    engine_row = next(
        repository
        for repository in baseline["repositories"]
        if repository["repository_id"] == "engine"
    )
    reviewed_engine_paths = {artifact["path"] for artifact in engine_row["reviewed_artifacts"]}
    if not required_engine_artifacts <= reviewed_engine_paths:
        raise ReviewError(
            "review source baseline omits required plan/verifier/study/audit artifacts: "
            f"{sorted(required_engine_artifacts - reviewed_engine_paths)}"
        )

    reviews = sidecar.get("reviews")
    if not isinstance(reviews, list):
        raise ReviewError("reviews must be an array")
    review_ids: set[str] = set()
    last_by_role: dict[str, dict[str, Any]] = {}
    previous_completed_at: dt.datetime | None = None
    for index, review in enumerate(reviews):
        label = f"reviews[{index}]"
        if not isinstance(review, dict):
            raise ReviewError(f"{label} must be an object")
        _require_exact_keys(review, REVIEW_KEYS, label)
        review_id = _require_string(review.get("review_id"), f"{label}.review_id")
        if review_id in review_ids:
            raise ReviewError(f"duplicate review_id: {review_id}")
        review_ids.add(review_id)
        role = _require_string(review.get("reviewer_role"), f"{label}.reviewer_role")
        if role not in REQUIRED_ROLES:
            raise ReviewError(f"unknown reviewer role: {role}")
        reviewer_identity = _require_string(
            review.get("reviewer_identity"), f"{label}.reviewer_identity"
        )
        if reviewer_identity != REQUIRED_REVIEWERS[role]:
            raise ReviewError(
                f"{label}.reviewer_identity must be the assigned reviewer for {role}"
            )
        if _require_sha256(review.get("reviewed_plan_sha256"), f"{label}.reviewed_plan_sha256") != actual_plan_sha:
            raise ReviewError(f"{label} reviewed another plan")
        if _require_sha256(
            review.get("review_source_baseline_sha256"),
            f"{label}.review_source_baseline_sha256",
        ) != actual_baseline_sha:
            raise ReviewError(f"{label} reviewed another source baseline")
        verdict = review.get("verdict")
        if verdict not in {"ACCEPT", "REJECT"}:
            raise ReviewError(f"{label}.verdict must be ACCEPT or REJECT")
        completed_at = _require_string(review.get("completed_at"), f"{label}.completed_at")
        if RFC3339.fullmatch(completed_at) is None:
            raise ReviewError(f"{label}.completed_at must be strict RFC3339")
        try:
            parsed_completed_at = dt.datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ReviewError(f"{label}.completed_at must be RFC3339") from exc
        if parsed_completed_at.tzinfo is None:
            raise ReviewError(f"{label}.completed_at must include a timezone")
        parsed_completed_at = parsed_completed_at.astimezone(dt.timezone.utc)
        if previous_completed_at is not None and parsed_completed_at <= previous_completed_at:
            raise ReviewError(f"{label}.completed_at must increase strictly in array order")
        previous_completed_at = parsed_completed_at
        verbatim = _require_string(review.get("verbatim_verdict"), f"{label}.verbatim_verdict")
        if actual_plan_sha not in verbatim or verdict not in verbatim:
            raise ReviewError(f"{label} verbatim verdict must contain verdict and plan SHA-256")
        if _require_sha256(review.get("verdict_sha256"), f"{label}.verdict_sha256") != hashlib.sha256(
            verbatim.encode("utf-8")
        ).hexdigest():
            raise ReviewError(f"{label} verdict text hash mismatch")
        findings = review.get("blocking_findings")
        if not isinstance(findings, list):
            raise ReviewError(f"{label}.blocking_findings must be an array")
        if verdict == "ACCEPT" and findings:
            raise ReviewError(f"{label} accepts while retaining blockers")
        last_by_role[role] = review

    if require_all_accept:
        missing = sorted(REQUIRED_ROLES - last_by_role.keys())
        rejected = sorted(
            role for role, review in last_by_role.items() if review.get("verdict") != "ACCEPT"
        )
        if missing or rejected:
            raise ReviewError(f"review closure failed: missing={missing}, not_accepted={rejected}")
        terminal_identities = {
            review["reviewer_identity"] for review in last_by_role.values()
        }
        if len(terminal_identities) != len(REQUIRED_ROLES):
            raise ReviewError("four terminal roles require four distinct reviewer identities")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--neuroclient-root", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--require-all-accept", action="store_true")
    args = parser.parse_args()
    try:
        verify(
            args.plan,
            args.reviews,
            args.neuroclient_root,
            require_all_accept=args.require_all_accept,
        )
    except (OSError, ReviewError) as exc:
        print(f"review-sidecar verification failed: {exc}", file=sys.stderr)
        return 1
    print("review-sidecar verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
