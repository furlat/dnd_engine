"""Static worker entry point for policy-promotion matches."""

from __future__ import annotations

from collections.abc import Sequence

from ai.evaluation.config_ladder.worker import main as worker_main
from ai.evaluation.promotion.match_runner import run_promotion_match


def main(argv: Sequence[str] | None = None) -> int:
    """Run one worker process with the promotion runner bound statically."""
    return worker_main(argv, real_match_runner=run_promotion_match)


if __name__ == "__main__":
    raise SystemExit(main())
