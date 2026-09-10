"""Serve local review files with byte ranges for native video seeking."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re


class ReviewFileHandler(SimpleHTTPRequestHandler):
    """Standard static-file handler plus the browser's single-range requests."""

    def end_headers(self) -> None:
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_GET(self) -> None:
        if not self.serve_range(head_only=False):
            super().do_GET()

    def do_HEAD(self) -> None:
        if not self.serve_range(head_only=True):
            super().do_HEAD()

    def serve_range(self, *, head_only: bool) -> bool:
        requested = self.headers.get("Range")
        path = Path(self.translate_path(self.path))
        if requested is None or not path.is_file():
            return False
        length = path.stat().st_size
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
        start, end = 0, length - 1
        if match and any(match.groups()):
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(int(right), length - 1) if right else length - 1
            else:
                start = max(0, length - int(right))
        else:
            start = length
        if start > end or start >= length:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{length}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return True
        with path.open("rb") as source:
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(str(path)))
            self.send_header("Content-Range", f"bytes {start}-{end}/{length}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            if not head_only:
                source.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = source.read(min(remaining, 64 * 1024))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(".runtime/animation-review"))
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                 partial(ReviewFileHandler, directory=str(args.directory.resolve())))
    print(f"Animation review: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
