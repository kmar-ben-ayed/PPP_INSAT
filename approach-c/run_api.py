"""CLI entrypoint for the shared API server."""

from __future__ import annotations

import argparse

from src.api_server import run


def main() -> None:
    """Parse args and run the HTTP API server."""
    parser = argparse.ArgumentParser(description="Run the FAQ API server.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8081, help="Port to listen on.")
    args = parser.parse_args()
    run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
