"""Static worker entry point for connected configuration matches."""

from __future__ import annotations

from collections.abc import Sequence

from ai.evaluation.config_ladder.match_runner import run_connected_match
from ai.evaluation.config_ladder.worker import main as worker_main


def main(argv: Sequence[str] | None = None) -> int:
    """Run one worker process with the connected-match runner bound statically."""
    return worker_main(argv, real_match_runner=run_connected_match)


if __name__ == "__main__":
    raise SystemExit(main())
