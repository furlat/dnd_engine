"""Run the reference external policy provider with Uvicorn."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn

from services.ai_policy_server.app import create_ai_policy_service
from services.ai_policy_server.composition import (
    DEFAULT_PROVIDER_CAPACITY,
    DEFAULT_PROVIDER_ID,
    DEFAULT_RESPONSE_CACHE_SIZE,
)


def main(argv: Sequence[str] | None = None) -> None:
    """Serve one explicitly configured reference-provider process."""
    parser = argparse.ArgumentParser(
        description="D&D external AI policy provider",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8010,
        help="Port to bind to",
    )
    parser.add_argument(
        "--provider-id",
        default=DEFAULT_PROVIDER_ID,
        help="Globally unique provider identity",
    )
    parser.add_argument(
        "--capacity",
        type=int,
        default=DEFAULT_PROVIDER_CAPACITY,
        help="Maximum concurrent character assignments",
    )
    parser.add_argument(
        "--response-cache-size",
        type=int,
        default=DEFAULT_RESPONSE_CACHE_SIZE,
        help="Idempotent decision responses retained per assignment",
    )
    args = parser.parse_args(argv)
    service = create_ai_policy_service(
        provider_id=args.provider_id,
        capacity=args.capacity,
        response_cache_size=args.response_cache_size,
    )
    uvicorn.run(
        service,
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
