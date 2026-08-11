#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx


def config() -> tuple[str, dict[str, str]]:
    url = os.getenv("HSMT_ENGINE_URL", "http://127.0.0.1:8787").rstrip("/")
    token = os.getenv("HSMT_API_TOKEN", "")
    if not token:
        raise SystemExit("Missing HSMT_API_TOKEN")
    return url, {"Authorization": f"Bearer {token}"}


def request(method: str, path: str, **kwargs):
    url, headers = config()
    response = httpx.request(method, url + path, headers=headers, timeout=300, **kwargs)
    if response.is_error:
        raise SystemExit(f"HTTP {response.status_code}: {response.text}")
    return response


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("files", nargs="+")
    submit.add_argument("--project", default="")
    status = sub.add_parser("status")
    status.add_argument("job_id")
    events = sub.add_parser("events")
    events.add_argument("job_id")
    for name in ("approve", "reject"):
        review = sub.add_parser(name)
        review.add_argument("job_id")
        review.add_argument("--note", default="")
        review.add_argument("--results")
    download = sub.add_parser("download")
    download.add_argument("job_id")
    download.add_argument("artifact")
    download.add_argument("output")
    retry = sub.add_parser("retry")
    retry.add_argument("job_id")
    args = parser.parse_args()

    if args.command == "submit":
        opened = []
        try:
            for value in args.files:
                path = Path(value)
                stream = path.open("rb")
                opened.append(stream)
            files = [("files", (Path(value).name, stream)) for value, stream in zip(args.files, opened)]
            response = request("POST", "/v1/jobs", files=files, data={"project_name": args.project})
        finally:
            for stream in opened:
                stream.close()
    elif args.command == "status":
        response = request("GET", f"/v1/jobs/{args.job_id}")
    elif args.command == "events":
        response = request("GET", f"/v1/jobs/{args.job_id}/events")
    elif args.command in {"approve", "reject"}:
        body = {"decision": args.command, "note": args.note}
        if args.results:
            body["results"] = json.loads(Path(args.results).read_text(encoding="utf-8"))
        response = request("POST", f"/v1/jobs/{args.job_id}/review", json=body)
    elif args.command == "retry":
        response = request("POST", f"/v1/jobs/{args.job_id}/retry")
    else:
        response = request("GET", f"/v1/jobs/{args.job_id}/artifacts/{args.artifact}")
        Path(args.output).write_bytes(response.content)
        print(args.output)
        return
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
