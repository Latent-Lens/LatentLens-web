from __future__ import annotations

import argparse
import mimetypes
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent
WATCH_EXTENSIONS = {".css", ".html", ".js", ".json", ".md", ".svg", ".webp", ".png", ".jpg", ".jpeg"}
BUILD_INPUTS = {Path("data/projects.md")}
BUILD_OUTPUTS = {
    Path("pages/projects.html"),
    Path("pages/projects/ptm-proteomics.html"),
    Path("pages/projects/clinical-data-tools.html"),
    Path("pages/projects/research-reports.html"),
}

LIVE_RELOAD_SCRIPT = """
<script>
(() => {
  const events = new EventSource('/__live-reload');
  events.onmessage = (event) => {
    if (event.data === 'reload') window.location.reload();
  };
})();
</script>
"""


class ChangeTracker:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.version = 0
        self._snapshot = self._scan()
        self._lock = threading.Lock()
        self._building = False

    def _scan(self) -> dict[str, float]:
        snapshot: dict[str, float] = {}
        for path in self.root.rglob("*"):
            if path.is_file() and path.suffix.lower() in WATCH_EXTENSIONS:
                snapshot[str(path.relative_to(self.root))] = path.stat().st_mtime
        return snapshot

    def _run_build(self) -> None:
        if self._building:
            return

        self._building = True
        try:
            result = subprocess.run(
                [sys.executable, "build_projects.py"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip(), file=sys.stderr)
            if result.returncode != 0:
                print(f"build_projects.py failed with exit code {result.returncode}", file=sys.stderr)
        finally:
            self._building = False

    def watch(self) -> None:
        while True:
            time.sleep(0.5)
            next_snapshot = self._scan()
            if next_snapshot == self._snapshot:
                continue

            changed = {
                Path(path)
                for path, mtime in next_snapshot.items()
                if self._snapshot.get(path) != mtime
            }
            changed.update(Path(path) for path in self._snapshot if path not in next_snapshot)

            if changed & BUILD_INPUTS:
                self._run_build()
                next_snapshot = self._scan()
            elif changed and changed <= BUILD_OUTPUTS:
                self._snapshot = next_snapshot
                continue

            with self._lock:
                self._snapshot = next_snapshot
                self.version += 1

    def current_version(self) -> int:
        with self._lock:
            return self.version


tracker = ChangeTracker(ROOT)


class LiveReloadHandler(BaseHTTPRequestHandler):
    server_version = "LatentLensLiveReload/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/__live-reload":
            self._send_live_reload_stream()
            return

        requested = unquote(parsed.path.lstrip("/")) or "index.html"
        target = (ROOT / requested).resolve()

        if not self._is_safe_path(target):
            self.send_error(403)
            return

        if target.is_dir():
            target = target / "index.html"

        if not target.exists() or not target.is_file():
            self.send_error(404)
            return

        content = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"

        if target.suffix.lower() == ".html":
            html = content.decode("utf-8")
            html = html.replace("</body>", f"{LIVE_RELOAD_SCRIPT}</body>")
            content = html.encode("utf-8")
            content_type = "text/html; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_live_reload_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        seen_version = tracker.current_version()
        while True:
            time.sleep(0.5)
            next_version = tracker.current_version()
            if next_version != seen_version:
                seen_version = next_version
                try:
                    self.wfile.write(b"data: reload\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break

    def _is_safe_path(self, target: Path) -> bool:
        try:
            return os.path.commonpath([ROOT, target]) == str(ROOT)
        except ValueError:
            return False

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the static site with markdown rebuilds and live reload.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    tracker._run_build()
    threading.Thread(target=tracker.watch, daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), LiveReloadHandler)
    print(f"Serving {ROOT} at http://{args.host}:{args.port}")
    print("Saving data/projects.md rebuilds project HTML before the browser refreshes.")
    server.serve_forever()


if __name__ == "__main__":
    main()
