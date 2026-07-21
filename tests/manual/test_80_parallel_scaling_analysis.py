import pytest

from ai.evaluation.config_ladder.scaling import ScalingPilot, analyze_parallel_scaling


def test_parallel_scaling_reports_speedup_efficiency_and_selected_concurrency() -> None:
    analysis = analyze_parallel_scaling((
        _pilot(workers=1, wall_seconds=100.0, peak_rss_mb=900.0),
        _pilot(workers=4, wall_seconds=30.0, peak_rss_mb=2600.0),
        _pilot(workers=8, wall_seconds=18.0, peak_rss_mb=4700.0),
        _pilot(workers=12, wall_seconds=17.0, peak_rss_mb=6900.0),
        _pilot(workers=16, wall_seconds=20.0, peak_rss_mb=9000.0),
    ))

    rows = {row.worker_count: row for row in analysis.rows}

    assert rows[1].speedup == 1.0
    assert rows[4].speedup == pytest.approx(100.0 / 30.0)
    assert rows[4].parallel_efficiency == pytest.approx((100.0 / 30.0) / 4.0)
    assert rows[12].matches_per_second > rows[8].matches_per_second
    assert analysis.selected_worker_count == 12
    assert analysis.comparable_workload_hash == "same-workload"


def test_parallel_scaling_rejects_incomparable_or_invalid_pilots() -> None:
    with pytest.raises(ValueError, match="same workload"):
        analyze_parallel_scaling((
            _pilot(workers=1, wall_seconds=10.0, workload_hash="a"),
            _pilot(workers=4, wall_seconds=3.0, workload_hash="b"),
        ))

    with pytest.raises(ValueError, match="single-worker"):
        analyze_parallel_scaling((_pilot(workers=4, wall_seconds=3.0),))


def _pilot(
    *,
    workers: int,
    wall_seconds: float,
    peak_rss_mb: float = 1000.0,
    workload_hash: str = "same-workload",
) -> ScalingPilot:
    return ScalingPilot(
        worker_count=workers,
        workload_hash=workload_hash,
        scheduled_matches=100,
        completed_matches=100,
        eligible_matches=100,
        wall_seconds=wall_seconds,
        total_worker_cpu_seconds=80.0,
        peak_rss_mb=peak_rss_mb,
        failure_count=0,
        determinism_canaries_passed=True,
    )
