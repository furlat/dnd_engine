#!/usr/bin/env python
"""Live uvicorn SSE test for directional spatial event payloads.

Run with:
    python examples/server_tests/test_directional_event_stream_live.py
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests


ROOT = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"
PORT = int(os.environ.get("DIRECTIONAL_EVENT_STREAM_PORT", "8127"))
BASE_URL = f"http://{HOST}:{PORT}"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  PASSED: {message}")


def start_server() -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server.event_server:app",
            "--host",
            HOST,
            "--port",
            str(PORT),
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.monotonic() + 20
    last_error: Optional[Exception] = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"uvicorn exited early with code {process.returncode}\n{output}")
        try:
            response = requests.get(f"{BASE_URL}/", timeout=0.5)
            if response.status_code == 200:
                return process
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(0.2)

    raise RuntimeError(f"uvicorn did not become ready: {last_error}")


def stop_server(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def iter_sse_frames(response: requests.Response):
    frame: list[str] = []
    for line in response.iter_lines(decode_unicode=True):
        if line == "":
            if frame:
                yield frame
                frame = []
            continue
        frame.append(line)


def parse_sse_frame(frame: list[str]) -> tuple[Optional[str], dict]:
    event_name: Optional[str] = None
    data_lines: list[str] = []
    for line in frame:
        if line.startswith("event: "):
            event_name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            data_lines.append(line.removeprefix("data: "))
    return event_name, json.loads("\n".join(data_lines))


def read_directional_game_event(session: requests.Session, since_event: int) -> dict:
    with session.get(
        f"{BASE_URL}/events/subscribe",
        params={"since_event": since_event},
        stream=True,
        timeout=(3, 8),
    ) as response:
        check(response.status_code == 200, "SSE subscribe returns 200")
        check(response.headers["content-type"].startswith("text/event-stream"), "SSE content type is text/event-stream")

        deadline = time.monotonic() + 8
        for frame in iter_sse_frames(response):
            event_name, data = parse_sse_frame(frame)
            if event_name == "game_event":
                event = data["event"]
                if event.get("event_type") == "spatial_tile_changed" and event.get("directional_channels") == ["vision"]:
                    return event
            if time.monotonic() > deadline:
                break

    raise AssertionError("Timed out waiting for directional spatial game_event over SSE")


def main() -> None:
    print("=" * 72)
    print("LIVE UVICORN DIRECTIONAL EVENT STREAM TEST")
    print("=" * 72)
    server = start_server()
    try:
        with requests.Session() as session:
            response = session.post(
                f"{BASE_URL}/mapeditor/maps",
                json={"source": "scratch", "width": 3, "height": 3, "origin": [0, 0], "default_tile": "Floor"},
                timeout=5,
            )
            check(response.status_code == 200, "scratch map created through live server")

            response = session.get(f"{BASE_URL}/events", params={"limit": 0}, timeout=5)
            check(response.status_code == 200, "event history endpoint returns cursor")
            cursor = response.json()["total"]

            response = session.post(
                f"{BASE_URL}/mapeditor/map/tiles",
                json={
                    "tiles": [
                        {
                            "x": 1,
                            "y": 1,
                            "directional_channel": "vision",
                            "direction": "east",
                            "passable": False,
                        }
                    ]
                },
                timeout=5,
            )
            check(response.status_code == 200, "directional tile patch applied through live server")
            patched_tile = next(tile for tile in response.json()["tiles"] if tile["x"] == 1 and tile["y"] == 1)
            check(patched_tile["directional_blocks_vision"]["east"], "live mapeditor response includes directional state")

            event = read_directional_game_event(session, cursor)
            check(event["event_type"] == "spatial_tile_changed", "SSE game_event uses existing spatial event type")
            check(event["directional_position"] == [1, 1], "SSE game_event serializes directional_position")
            check(event["directional_directions"] == ["east"], "SSE game_event carries changed direction")
            check(event["directional_channels"] == ["vision"], "SSE game_event carries changed channel")
            check(event["directional_blocks_vision"]["east"] is True, "SSE game_event carries directional block map")

        print("\nLIVE UVICORN DIRECTIONAL EVENT STREAM TEST PASSED")
    finally:
        stop_server(server)


if __name__ == "__main__":
    main()
