"""The browser can seek local videos using ordinary HTTP byte ranges."""

from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from devtools.animation_review.serve import ReviewFileHandler


@pytest.fixture
def video_url(tmp_path: Path):
    (tmp_path / "clip.mp4").write_bytes(bytes(range(100)))
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(ReviewFileHandler, directory=str(tmp_path)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/clip.mp4"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.mark.parametrize(("requested", "start", "end"), [
    ("bytes=10-19", 10, 19), ("bytes=90-", 90, 99), ("bytes=-5", 95, 99),
])
def test_video_seek_returns_the_requested_bytes(video_url: str, requested: str, start: int, end: int) -> None:
    for method in ("GET", "HEAD"):
        with urlopen(Request(video_url, headers={"Range": requested}, method=method)) as response:
            assert response.status == 206
            assert response.headers["Accept-Ranges"] == "bytes"
            assert response.headers["Content-Range"] == f"bytes {start}-{end}/100"
            assert response.headers["Content-Length"] == str(end - start + 1)
            assert response.read() == (bytes(range(start, end + 1)) if method == "GET" else b"")


def test_impossible_seek_reports_the_actual_file_length(video_url: str) -> None:
    with pytest.raises(HTTPError) as error:
        urlopen(Request(video_url, headers={"Range": "bytes=101-"}))
    assert error.value.code == 416
    assert error.value.headers["Content-Range"] == "bytes */100"
