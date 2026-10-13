from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False)


API_PORT = int(os.getenv("API_PORT", "8001"))
UI_PORT = int(os.getenv("UI_PORT", "8501"))


def start(cmd: list[str]) -> subprocess.Popen:
    # The UI process must call the same mock API port this script starts.
    env = {**os.environ, "VENDOR_RISK_BASE_URL": f"http://127.0.0.1:{API_PORT}"}
    return subprocess.Popen(cmd, cwd=ROOT, env=env)


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_for_api(url: str, proc: subprocess.Popen, timeout_seconds: float = 10.0) -> None:
    """Wait until the mock API is reachable or fail with a useful message."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Vendor-risk API exited during startup with code {proc.returncode}. "
                "Check the terminal output above (a port conflict is a common cause)."
            )
        try:
            response = requests.get(url, timeout=0.5)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"Vendor-risk API did not become ready within {timeout_seconds:.0f}s: {url}")


def _handle_termination(signum: int, frame: object) -> None:
    """Route SIGTERM through normal cleanup (useful for IDE/terminal stop actions)."""
    raise KeyboardInterrupt


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_termination)
    procs: list[subprocess.Popen] = []
    busy = [p for p in (API_PORT, UI_PORT) if port_in_use(p)]
    if busy:
        raise SystemExit(f"Port(s) {busy} already in use. Stop the other process or choose ports, e.g. API_PORT=8011 UI_PORT=8511 python run_local.py")
    try:
        print(f"Starting vendor-risk API on http://127.0.0.1:{API_PORT} ...")
        api_proc = start(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "mock_api.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(API_PORT),
            ]
        )
        procs.append(api_proc)
        wait_for_api(f"http://127.0.0.1:{API_PORT}/health", api_proc)
        print("Vendor-risk API is ready.")

        try:
            __import__("streamlit")
        except ImportError:
            print("Streamlit is not installed. Run: pip install -r requirements.txt")
            print("The mock API is still running. Press Ctrl+C to stop.")
        else:
            print(f"Starting UI on http://127.0.0.1:{UI_PORT} ...")
            procs.append(
                start(
                    [
                        sys.executable,
                        "-m",
                        "streamlit",
                        "run",
                        "app.py",
                        "--server.port",
                        str(UI_PORT),
                        "--server.headless",
                        "true",
                    ]
                )
            )

        while True:
            time.sleep(1)
            for proc in procs:
                if proc.poll() is not None:
                    raise RuntimeError(f"A local process exited with code {proc.returncode}")
    except KeyboardInterrupt:
        print("\nStopping local services ...")
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
