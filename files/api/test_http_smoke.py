"""Launch an isolated local service and exercise real HTTP, then stop it.

Only this script's child process and temporary database/log directory are
cleaned up. An existing user server and flood_data.db are never touched.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen


def run():
    with tempfile.TemporaryDirectory(prefix="floodwatch-http-") as directory:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        environment = dict(os.environ)
        environment.update(FLOOD_EWS_DATABASE_URL="sqlite:///" + (Path(directory) / "smoke.db").as_posix(),
                           FLOOD_EWS_RUNTIME_DIR=directory, FLOOD_EWS_NEWS_PROVIDER="off")
        child = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
                                 cwd=Path(__file__).parent, env=environment,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            base = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 40
            while True:
                if child.poll() is not None:
                    raise RuntimeError(child.communicate()[0])
                try:
                    with urlopen(base + "/health", timeout=10) as response:
                        health = json.load(response)
                        assert health["status"] == "ok" and health["database"] == "ok"
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.25)
            for route in ("/", "/dashboard", "/data", "/news", "/contact", "/evaluation", "/health", "/api/news-feed", "/static/js/news.js", "/static/js/evaluation.js", "/static/js/contact.js"):
                with urlopen(base + route, timeout=10) as response:
                    assert response.status == 200, route
                    assert response.read(), route
                    print(f"HTTP 200 {route}")
            print("[PASS] Isolated FastAPI HTTP smoke check; no demo data changed.")
        finally:
            child.terminate()
            try:
                child.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate()


if __name__ == "__main__":
    run()
