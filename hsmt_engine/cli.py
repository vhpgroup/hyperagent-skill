from __future__ import annotations

import argparse

import uvicorn

from .config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the HSMT Product Matcher API")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    settings = Settings.load()
    uvicorn.run(
        "hsmt_engine.api:app", host=args.host or settings.api_host,
        port=args.port or settings.api_port, reload=args.reload,
    )


if __name__ == "__main__":
    main()
