"""Static contracts for the gauntlet watcher HTML."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WATCHER_HTML = REPOSITORY_ROOT / "ai" / "AI_TOURNAMENT_MONITOR.html"


def test_gauntlet_watcher_renders_promoted_audit_fields_from_json() -> None:
    """The watcher should expose compact audit evidence without manual stats."""
    html = WATCHER_HTML.read_text(encoding="utf-8")

    assert 'id="tm-subjectivity"' in html
    assert 'id="tm-latency"' in html
    assert 'id="tm-nonaccepted"' in html
    assert 'id="tm-max-command"' in html
    assert 'id="tm-server-command"' in html
    assert 'id="tm-gate"' in html
    assert "gate_status" in html
    assert "gate_reasons" in html
    assert "latency_status" in html
    assert "latency_reasons" in html
    assert "latency_thresholds" in html
    assert "Latency Stage Breakdown" in html
    assert "Command Latency Time Series" in html
    assert "Command And Server Latency" in html
    assert "Local Decision Latency" in html
    assert "normal_stages" in html
    assert "diagnostic_stages" in html
    assert "command_total_samples_ms" in html
    assert "server_command_samples_ms" in html
    assert "local_decision_samples_ms" in html
    assert "renderCommandLatencySeries" in html
    assert "buildCommandLatencyRows" in html
    assert "renderCommandLatencyChart" in html
    assert "Missing samples are gaps, not zeros" in html
    assert "command_status_counts" in html
    assert "subjectivity_status" in html
    assert "subjectivity_violation_count" in html
    assert "max_command_total_ms" in html
    assert "max_server_command_ms" in html
    assert "max_local_decision_ms" in html
    assert "normal_command_total_p95_ms" in html
    assert "normal_command_total_p99_ms" in html
    assert "diagnostic_command_total_p99_ms" in html
    assert "Production command p95/p99/max" in html
    assert "Diagnostic command p95/p99/max" in html
    assert "Production local p95/p99/max" in html
    assert 'id="tm-api-base"' in html
    assert "/ai/gauntlets/live/latest" in html
    assert "/ai/gauntlets/latest" in html
    assert "loadBackendLatest" in html
    assert "Loaded latest gauntlet watcher state from" in html
    assert "Backend URL set to" in html
    assert "recent_events" in html
    assert "aggregateCommandStatusCounts" in html
    assert "aggregateSubjectivityStatus" in html
    assert "inferGateStatus" in html
    assert "inferGateReasons" in html
    assert "maxMatchField" in html
    assert "firstKnownNumber" in html
    assert "auditLatency" in html
    assert "formatLatencyTriple" in html
    assert "command_total_p95_over_5ms" in html
    assert "command_total_p99_over_10ms" in html
    assert "local_decision_p99_over_5ms" in html


def test_gauntlet_watcher_preserves_zero_values_in_audit_fields() -> None:
    """Zero-valued retained metrics should not be replaced by fallback values."""
    html = WATCHER_HTML.read_text(encoding="utf-8")

    assert "max_command_total_ms ||" not in html
    assert "max_server_command_ms ||" not in html
    assert "subjectivity_violation_count ||" not in html
    assert "command_status_counts ||" not in html
    assert "summary.failed_count ||" not in html
    assert "summary.pending_count ||" not in html
    assert "commandStatusCounts.stale ||" not in html
    assert "commandStatusCounts.rejected ||" not in html
    assert "latency_status ||" not in html
