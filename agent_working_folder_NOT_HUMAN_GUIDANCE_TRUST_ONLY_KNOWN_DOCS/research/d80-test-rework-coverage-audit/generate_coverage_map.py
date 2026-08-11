"""Generate a static coverage map for the July 1 test rework.

This script is an audit aid, not a claim that lexical similarity proves runtime
equivalence.  It inventories every test-surface record changed by d80dab27,
every Python example/test surface moved out of the active tree, every test case
and assertion in the pre-rework source, and the closest current active test
candidates.  Exact normalized assertion matches are called out separately from
heuristic semantic candidates.
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
import csv
import math
from pathlib import Path
import re
import subprocess
from typing import Iterable, Iterator, Sequence


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path(__file__).resolve().parent
REWORK_COMMIT = "d80dab27adda8fdd1949048b5a9fd1e37cedd10d"

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")
CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
GENERIC_TOKENS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "case",
    "check",
    "does",
    "for",
    "from",
    "get",
    "has",
    "in",
    "is",
    "it",
    "not",
    "of",
    "on",
    "one",
    "or",
    "return",
    "set",
    "should",
    "test",
    "tests",
    "that",
    "the",
    "then",
    "to",
    "true",
    "false",
    "when",
    "with",
}


@dataclass(frozen=True)
class AssertionRecord:
    selector: str
    path: str
    case_name: str
    line: int
    ordinal: int
    source: str
    tokens: Counter[str]
    normalized_ast: str


@dataclass(frozen=True)
class CaseRecord:
    selector: str
    path: str
    name: str
    kind: str
    line: int
    source: str
    tokens: Counter[str]
    assertion_count: int


@dataclass(frozen=True)
class FileInventoryRecord:
    old_path: str
    archived_path: str
    similarity: str
    surface_kind: str
    test_case_count: int
    assertion_count: int


class FunctionCollector(ast.NodeVisitor):
    """Collect named functions with stable class-qualified names."""

    def __init__(self) -> None:
        self.class_names: list[str] = []
        self.functions: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_names.append(node.name)
        self.generic_visit(node)
        self.class_names.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        name = ".".join((*self.class_names, node.name))
        self.functions.append((name, node))
        # Nested helpers are part of the outer case rather than independent cases.

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        name = ".".join((*self.class_names, node.name))
        self.functions.append((name, node))


def run_git(*args: str) -> str:
    """Run one read-only git query from the repository root."""
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
        errors="replace",
    )


def split_words(value: str) -> Iterator[str]:
    """Yield normalized snake/camel/text tokens."""
    for raw in WORD_RE.findall(value.replace("_", " ")):
        for part in CAMEL_BOUNDARY_RE.split(raw):
            token = part.lower()
            if len(token) > 1 and token not in GENERIC_TOKENS:
                yield token


def add_words(counter: Counter[str], value: str, weight: int = 1) -> None:
    """Add weighted normalized words to a counter."""
    for token in split_words(value):
        counter[token] += weight


def node_tokens(
    node: ast.AST,
    *,
    name: str = "",
    path: str = "",
    include_docstring: bool = True,
) -> Counter[str]:
    """Build a weighted semantic token vector for one AST node."""
    result: Counter[str] = Counter()
    add_words(result, name, weight=6)
    add_words(result, Path(path).stem, weight=3)
    if include_docstring and isinstance(
        node,
        (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
    ):
        docstring = ast.get_docstring(node)
        if docstring:
            add_words(result, docstring, weight=3)
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            add_words(result, child.id)
        elif isinstance(child, ast.Attribute):
            add_words(result, child.attr, weight=2)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if child is not node:
                add_words(result, child.name)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            add_words(result, child.value)
        elif isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                add_words(result, child.func.id, weight=2)
            elif isinstance(child.func, ast.Attribute):
                add_words(result, child.func.attr, weight=2)
        elif isinstance(child, ast.Compare):
            for operator in child.ops:
                result[type(operator).__name__.lower()] += 1
    return result


def source_segment(source: str, node: ast.AST) -> str:
    """Return one compact, single-line source segment."""
    segment = ast.get_source_segment(source, node) or ast.dump(
        node,
        include_attributes=False,
    )
    return " ".join(segment.split())


def normalized_assert_ast(node: ast.Assert) -> str:
    """Return an exact structural assertion fingerprint."""
    return ast.dump(node.test, annotate_fields=True, include_attributes=False)


def manual_case_label(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str | None:
    """Return the label used by legacy ``@test("...")`` script cases."""
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if not isinstance(decorator.func, ast.Name) or decorator.func.id != "test":
            continue
        if not decorator.args:
            continue
        label = decorator.args[0]
        if isinstance(label, ast.Constant) and isinstance(label.value, str):
            return label.value
    return None


def parse_cases(path: str, source: str) -> tuple[list[CaseRecord], list[AssertionRecord]]:
    """Parse test cases and every assertion from one source file."""
    tree = ast.parse(source, filename=path)
    collector = FunctionCollector()
    collector.visit(tree)

    cases: list[CaseRecord] = []
    assertions: list[AssertionRecord] = []
    owned_assert_ids: set[int] = set()

    for qualified_name, node in collector.functions:
        manual_label = manual_case_label(node)
        if node.name.startswith("test_"):
            case_name = qualified_name
            case_kind = "named_test"
        elif manual_label is not None:
            case_name = f"manual::{manual_label}"
            case_kind = "decorated_manual_case"
        else:
            continue
        case_selector = f"{path}::{case_name}"
        case_assertions = [
            child for child in ast.walk(node) if isinstance(child, ast.Assert)
        ]
        owned_assert_ids.update(id(child) for child in case_assertions)
        cases.append(
            CaseRecord(
                selector=case_selector,
                path=path,
                name=case_name,
                kind=case_kind,
                line=node.lineno,
                source=source_segment(source, node),
                tokens=node_tokens(node, name=case_name, path=path),
                assertion_count=len(case_assertions),
            )
        )
        for ordinal, assertion in enumerate(case_assertions, start=1):
            assertions.append(
                AssertionRecord(
                    selector=f"{case_selector}::assert-{ordinal}",
                    path=path,
                    case_name=case_name,
                    line=assertion.lineno,
                    ordinal=ordinal,
                    source=source_segment(source, assertion),
                    tokens=node_tokens(
                        assertion,
                        name=case_name,
                        path=path,
                        include_docstring=False,
                    ),
                    normalized_ast=normalized_assert_ast(assertion),
                )
            )

    # Assertions in setup helpers and script-style test files matter too.  Keep
    # them in the assertion ledger even though pytest would not collect them as
    # independent cases.
    function_by_assertion: dict[int, str] = {}
    for qualified_name, node in collector.functions:
        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                function_by_assertion[id(child)] = qualified_name
    unowned_ordinal = 0
    for assertion in (child for child in ast.walk(tree) if isinstance(child, ast.Assert)):
        if id(assertion) in owned_assert_ids:
            continue
        unowned_ordinal += 1
        owner = function_by_assertion.get(id(assertion), "<module>")
        selector = f"{path}::helper::{owner}::assert-{unowned_ordinal}"
        assertions.append(
            AssertionRecord(
                selector=selector,
                path=path,
                case_name=f"helper::{owner}",
                line=assertion.lineno,
                ordinal=unowned_ordinal,
                source=source_segment(source, assertion),
                tokens=node_tokens(
                    assertion,
                    name=owner,
                    path=path,
                    include_docstring=False,
                ),
                normalized_ast=normalized_assert_ast(assertion),
            )
        )
    return cases, assertions


def moved_test_files() -> list[tuple[str, str, str]]:
    """Return every Python example/test surface moved to ``to_archive`` by d80."""
    output = run_git(
        "diff-tree",
        "-r",
        "-M",
        "-C",
        "--name-status",
        "--no-commit-id",
        f"{REWORK_COMMIT}^",
        REWORK_COMMIT,
    )
    rows: list[tuple[str, str, str]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not parts[0].startswith("R"):
            continue
        status, old_path, new_path = parts
        if not old_path.endswith(".py"):
            continue
        if not new_path.startswith("to_archive/"):
            continue
        if not (
            old_path.startswith("examples/")
            or old_path.startswith("interactive_ruleset/tests/")
        ):
            continue
        rows.append((old_path, new_path, status.removeprefix("R")))
    return sorted(rows)


def surface_kind(path: str) -> str:
    """Classify one displaced Python surface without calling all of it pytest."""
    filename = Path(path).name
    if filename == "__init__.py":
        return "package_marker"
    if filename.startswith("test_") or filename.endswith("_test.py"):
        return "test_script"
    return "manual_or_live_script"


def test_surface_changes() -> list[dict[str, str]]:
    """Return all added, modified, deleted, or renamed d80 test-surface records."""
    output = run_git(
        "diff-tree",
        "-r",
        "-M",
        "-C",
        "--name-status",
        "--no-commit-id",
        f"{REWORK_COMMIT}^",
        REWORK_COMMIT,
    )
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) == 3:
            old_path, new_path = parts[1:]
        elif len(parts) == 2:
            old_path = "" if status == "A" else parts[1]
            new_path = "" if status == "D" else parts[1]
        else:
            continue
        paths = [path for path in (old_path, new_path) if path]
        in_test_surface = any(
            path.startswith(("examples/", "tests/", "interactive_ruleset/tests/"))
            or Path(path).name.startswith("test_")
            or Path(path).name.endswith(("_test.py", "test_utils.py"))
            for path in paths
        )
        if not in_test_surface:
            continue
        if status.startswith("R"):
            change_kind = "renamed"
        elif status.startswith("C"):
            change_kind = "copied"
        elif status == "A":
            change_kind = "added"
        elif status == "D":
            change_kind = "deleted"
        else:
            change_kind = "modified"
        rows.append(
            {
                "status": status,
                "change_kind": change_kind,
                "old_path": old_path,
                "new_path": new_path,
            }
        )
    return rows


def current_active_test_files() -> list[Path]:
    """Return every active Python test file in the current working tree."""
    return sorted((ROOT / "tests").rglob("test_*.py"))


def idf_for(records: Sequence[CaseRecord] | Sequence[AssertionRecord]) -> dict[str, float]:
    """Compute inverse-document frequency for sparse semantic vectors."""
    document_frequency: Counter[str] = Counter()
    for record in records:
        document_frequency.update(record.tokens)
    count = len(records)
    return {
        token: math.log((count + 1) / (frequency + 1)) + 1.0
        for token, frequency in document_frequency.items()
    }


def weighted_norm(tokens: Counter[str], idf: dict[str, float]) -> float:
    """Return the TF-IDF vector norm."""
    return math.sqrt(
        sum((weight * idf.get(token, 1.0)) ** 2 for token, weight in tokens.items())
    )


def closest_records(
    source_tokens: Counter[str],
    candidates: Sequence[CaseRecord] | Sequence[AssertionRecord],
    inverted_index: dict[str, set[int]],
    idf: dict[str, float],
    candidate_norms: Sequence[float],
    *,
    limit: int = 3,
) -> list[tuple[int, float]]:
    """Return sparse cosine-similarity candidates."""
    candidate_ids: set[int] = set()
    for token in source_tokens:
        candidate_ids.update(inverted_index.get(token, ()))
    source_norm = weighted_norm(source_tokens, idf)
    if not source_norm:
        return []
    scores: list[tuple[int, float]] = []
    for candidate_id in candidate_ids:
        candidate = candidates[candidate_id]
        dot = 0.0
        for token, source_weight in source_tokens.items():
            candidate_weight = candidate.tokens.get(token)
            if candidate_weight:
                token_idf = idf.get(token, 1.0)
                dot += source_weight * candidate_weight * token_idf * token_idf
        denominator = source_norm * candidate_norms[candidate_id]
        if denominator:
            scores.append((candidate_id, dot / denominator))
    scores.sort(key=lambda row: row[1], reverse=True)
    return scores[:limit]


def build_index(
    records: Sequence[CaseRecord] | Sequence[AssertionRecord],
) -> tuple[dict[str, set[int]], dict[str, float], list[float]]:
    """Build a sparse lookup index for semantic matching."""
    idf = idf_for(records)
    inverted: dict[str, set[int]] = defaultdict(set)
    for index, record in enumerate(records):
        for token in record.tokens:
            inverted[token].add(index)
    norms = [weighted_norm(record.tokens, idf) for record in records]
    return inverted, idf, norms


def candidate_status(score: float) -> str:
    """Classify a semantic candidate without overstating equivalence."""
    if score >= 0.62:
        return "strong_semantic_candidate"
    if score >= 0.43:
        return "partial_semantic_candidate"
    if score >= 0.28:
        return "weak_semantic_candidate"
    return "unmapped_requires_review"


def write_tsv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, object]]) -> None:
    """Write one deterministic tab-separated audit artifact."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Generate file, case, and assertion coverage ledgers."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    moved = moved_test_files()
    surface_changes = test_surface_changes()

    old_cases: list[CaseRecord] = []
    old_assertions: list[AssertionRecord] = []
    inventories: list[FileInventoryRecord] = []
    for old_path, archived_path, similarity in moved:
        source = run_git("show", f"{REWORK_COMMIT}^:{old_path}")
        cases, assertions = parse_cases(old_path, source)
        old_cases.extend(cases)
        old_assertions.extend(assertions)
        inventories.append(
            FileInventoryRecord(
                old_path=old_path,
                archived_path=archived_path,
                similarity=similarity,
                surface_kind=surface_kind(old_path),
                test_case_count=len(cases),
                assertion_count=len(assertions),
            )
        )

    active_cases: list[CaseRecord] = []
    active_assertions: list[AssertionRecord] = []
    for active_path in current_active_test_files():
        relative = str(active_path.relative_to(ROOT))
        cases, assertions = parse_cases(relative, active_path.read_text(encoding="utf-8"))
        active_cases.extend(cases)
        active_assertions.extend(assertions)

    case_inverted, case_idf, case_norms = build_index(active_cases)
    assertion_inverted, assertion_idf, assertion_norms = build_index(active_assertions)
    exact_assertions: dict[str, list[AssertionRecord]] = defaultdict(list)
    for assertion in active_assertions:
        exact_assertions[assertion.normalized_ast].append(assertion)

    case_matches: dict[str, list[tuple[CaseRecord, float]]] = {}
    case_rows: list[dict[str, object]] = []
    for old_case in old_cases:
        matches = closest_records(
            old_case.tokens,
            active_cases,
            case_inverted,
            case_idf,
            case_norms,
        )
        resolved = [(active_cases[index], score) for index, score in matches]
        case_matches[old_case.selector] = resolved
        top_score = resolved[0][1] if resolved else 0.0
        row: dict[str, object] = {
            "old_selector": old_case.selector,
            "old_case_kind": old_case.kind,
            "old_line": old_case.line,
            "old_assertion_count": old_case.assertion_count,
            "status": candidate_status(top_score),
        }
        for ordinal in range(3):
            candidate = resolved[ordinal] if ordinal < len(resolved) else None
            row[f"candidate_{ordinal + 1}"] = candidate[0].selector if candidate else ""
            row[f"score_{ordinal + 1}"] = f"{candidate[1]:.4f}" if candidate else ""
        case_rows.append(row)

    assertion_rows: list[dict[str, object]] = []
    for old_assertion in old_assertions:
        exact = exact_assertions.get(old_assertion.normalized_ast, [])
        if exact:
            status = "exact_normalized_ast"
            top_candidate = exact[0]
            top_score = 1.0
        else:
            matches = closest_records(
                old_assertion.tokens,
                active_assertions,
                assertion_inverted,
                assertion_idf,
                assertion_norms,
                limit=1,
            )
            if matches:
                top_candidate = active_assertions[matches[0][0]]
                top_score = matches[0][1]
                status = candidate_status(top_score)
            else:
                top_candidate = None
                top_score = 0.0
                status = "unmapped_requires_review"
        assertion_rows.append(
            {
                "old_selector": old_assertion.selector,
                "old_line": old_assertion.line,
                "old_assertion": old_assertion.source,
                "status": status,
                "active_candidate": top_candidate.selector if top_candidate else "",
                "candidate_line": top_candidate.line if top_candidate else "",
                "candidate_assertion": top_candidate.source if top_candidate else "",
                "score": f"{top_score:.4f}",
                "exact_match_count": len(exact),
            }
        )

    file_rows: list[dict[str, object]] = []
    for inventory in inventories:
        candidate_counts: Counter[str] = Counter()
        status_counts: Counter[str] = Counter()
        for old_case in (case for case in old_cases if case.path == inventory.old_path):
            matches = case_matches.get(old_case.selector, [])
            score = matches[0][1] if matches else 0.0
            status_counts[candidate_status(score)] += 1
            if matches:
                candidate_counts[matches[0][0].path] += 1
        top_files = candidate_counts.most_common(3)
        file_rows.append(
            {
                "old_path": inventory.old_path,
                "archived_path": inventory.archived_path,
                "rename_similarity_percent": inventory.similarity,
                "surface_kind": inventory.surface_kind,
                "test_case_count": inventory.test_case_count,
                "assertion_count": inventory.assertion_count,
                "top_active_candidate_1": top_files[0][0] if top_files else "",
                "candidate_case_count_1": top_files[0][1] if top_files else "",
                "top_active_candidate_2": top_files[1][0] if len(top_files) > 1 else "",
                "candidate_case_count_2": top_files[1][1] if len(top_files) > 1 else "",
                "top_active_candidate_3": top_files[2][0] if len(top_files) > 2 else "",
                "candidate_case_count_3": top_files[2][1] if len(top_files) > 2 else "",
                "strong_case_candidates": status_counts["strong_semantic_candidate"],
                "partial_case_candidates": status_counts["partial_semantic_candidate"],
                "weak_case_candidates": status_counts["weak_semantic_candidate"],
                "unmapped_cases": status_counts["unmapped_requires_review"],
            }
        )

    write_tsv(
        OUTPUT_DIR / "d80_file_inventory.tsv",
        (
            "old_path",
            "archived_path",
            "rename_similarity_percent",
            "surface_kind",
            "test_case_count",
            "assertion_count",
            "top_active_candidate_1",
            "candidate_case_count_1",
            "top_active_candidate_2",
            "candidate_case_count_2",
            "top_active_candidate_3",
            "candidate_case_count_3",
            "strong_case_candidates",
            "partial_case_candidates",
            "weak_case_candidates",
            "unmapped_cases",
        ),
        file_rows,
    )
    write_tsv(
        OUTPUT_DIR / "d80_test_surface_changes.tsv",
        ("status", "change_kind", "old_path", "new_path"),
        surface_changes,
    )
    write_tsv(
        OUTPUT_DIR / "d80_case_coverage_map.tsv",
        (
            "old_selector",
            "old_case_kind",
            "old_line",
            "old_assertion_count",
            "status",
            "candidate_1",
            "score_1",
            "candidate_2",
            "score_2",
            "candidate_3",
            "score_3",
        ),
        case_rows,
    )
    write_tsv(
        OUTPUT_DIR / "d80_assertion_coverage_map.tsv",
        (
            "old_selector",
            "old_line",
            "old_assertion",
            "status",
            "active_candidate",
            "candidate_line",
            "candidate_assertion",
            "score",
            "exact_match_count",
        ),
        assertion_rows,
    )

    summary = {
        "changed_test_surface_records": len(surface_changes),
        "moved_python_example_test_surfaces": len(moved),
        "moved_conventional_test_scripts": sum(
            inventory.surface_kind == "test_script" for inventory in inventories
        ),
        "moved_manual_or_live_scripts": sum(
            inventory.surface_kind == "manual_or_live_script"
            for inventory in inventories
        ),
        "moved_package_markers": sum(
            inventory.surface_kind == "package_marker" for inventory in inventories
        ),
        "old_test_cases": len(old_cases),
        "old_named_test_cases": sum(case.kind == "named_test" for case in old_cases),
        "old_decorated_manual_cases": sum(
            case.kind == "decorated_manual_case" for case in old_cases
        ),
        "old_assertions_all_functions": len(old_assertions),
        "current_active_test_files": len(current_active_test_files()),
        "current_active_test_cases": len(active_cases),
        "current_active_assertions_all_functions": len(active_assertions),
        "exact_normalized_assertions": sum(
            row["status"] == "exact_normalized_ast" for row in assertion_rows
        ),
        "strong_case_candidates": sum(
            row["status"] == "strong_semantic_candidate" for row in case_rows
        ),
        "partial_case_candidates": sum(
            row["status"] == "partial_semantic_candidate" for row in case_rows
        ),
        "weak_case_candidates": sum(
            row["status"] == "weak_semantic_candidate" for row in case_rows
        ),
        "unmapped_cases": sum(
            row["status"] == "unmapped_requires_review" for row in case_rows
        ),
    }
    (OUTPUT_DIR / "d80_mapping_summary.txt").write_text(
        "\n".join(f"{key}\t{value}" for key, value in summary.items()) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
