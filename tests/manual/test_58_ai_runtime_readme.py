"""Documentation contracts for the AI runtime README."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
README = REPOSITORY_ROOT / "ai" / "readme.md"


def test_ai_readme_documents_gauntlet_release_and_watcher_contracts() -> None:
    """The runtime docs should preserve the gauntlet evidence contract."""
    text = README.read_text(encoding="utf-8")

    for mode in ("`smoke`", "`rotation`", "`content`", "`regression`", "`release`"):
        assert mode in text

    for required in (
        "stale, error, or missing command result",
        "MATCH_FAILED",
        "failure_rows",
        "failed_count",
        "subjectivity audit status",
        "`gate_status` and `gate_reasons`",
        "`latency_status`, `latency_reasons`, and `latency_thresholds`",
        "`gate_status: \"running\"`",
        "--require-gate-pass",
        "--require-latency-pass",
        "gauntlet_runner check <summary.json> --require-gate-pass",
        "`gate_status: \"passed\"` while",
        "`latency_status: \"failed\"`",
        "all-sample",
        "production-only",
        "diagnostic-only",
        "production command-total p95 at",
        "production command-total p99 at",
        "production local-decision",
        "diagnostic probes do not by themselves fail",
        "all-sample/production/diagnostic latency",
        "localized display text is never",
        "explicit retained `0`",
        "missing or `null` fields",
        "GET /ai/gauntlets/live/latest",
        "usable before a summary file exists",
        "GET /ai/gauntlets/latest",
        "GET /ai/gauntlets/{gauntlet_id}/watch",
        "GET /ai/gauntlets/{gauntlet_id}/events/subscribe?since=<cursor>",
        "Invalid retained summary JSON remains an error",
        "Watcher events are observability only",
    ):
        assert required in text
