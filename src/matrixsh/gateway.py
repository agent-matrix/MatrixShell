from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Deque, Optional
from urllib.parse import urlparse

import threading
from collections import deque

import requests

from .urls import root_url


@dataclass
class GatewayProc:
    proc: subprocess.Popen[str]
    pairing_code: Optional[str] = None
    log_lines: Deque[str] | None = None


def is_local_base_url(base_url: str) -> bool:
    """
    True if URL host is localhost / 127.0.0.1 / ::1
    """
    try:
        u = urlparse(root_url(base_url))
        host = (u.hostname or "").lower()
        return host in ("localhost", "127.0.0.1", "::1")
    except Exception:
        return False


def base_health_url(base_url: str) -> str:
    # Health endpoint lives at server root.
    return root_url(base_url) + "/health"


def probe_health(base_url: str, timeout_s: float = 1.5) -> bool:
    try:
        r = requests.get(base_health_url(base_url), timeout=timeout_s)
        return r.status_code == 200
    except Exception:
        return False


def wait_for_health(base_url: str, total_timeout_s: float = 20.0) -> bool:
    """Wait until the gateway becomes healthy.

    This function intentionally does *not* assume that the gateway process is
    already listening. Newer MatrixLLM versions may spend significant time
    installing dependencies (e.g., Ollama) or pulling models before Uvicorn
    binds the port.
    """
    deadline = time.time() + total_timeout_s
    while time.time() < deadline:
        if probe_health(base_url, timeout_s=1.5):
            return True
        time.sleep(0.5)
    return False


def wait_for_health_or_exit(
    *,
    base_url: str,
    proc: subprocess.Popen[str],
    total_timeout_s: float,
    log_lines: Deque[str] | None = None,
) -> tuple[bool, str | None]:
    """Wait for health, but fail early if the process exits.

    Returns (ok, error_message). If ok is False and error_message is not None,
    it contains a short explanation.
    """
    deadline = time.time() + total_timeout_s
    while time.time() < deadline:
        # Process died -> stop waiting and surface info.
        rc = proc.poll()
        if rc is not None:
            tail = ""
            if log_lines:
                last = list(log_lines)[-25:]
                tail = "\n".join(last)
            msg = f"MatrixLLM exited early (exit code {rc})."
            if tail:
                msg += "\n\nLast output:\n" + tail
            return False, msg

        if probe_health(base_url, timeout_s=1.5):
            return True, None

        time.sleep(0.5)

    return False, None


def _have_cmd(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def ensure_matrixllm_installed(prefer_uv: bool = True) -> bool:
    """
    Ensure `matrixllm` command exists.
    If missing, try:
      - uv tool install matrixllm
      - pipx install matrixllm
    """
    if _have_cmd("matrixllm"):
        return True

    # Try uv tool
    if prefer_uv and _have_cmd("uv"):
        try:
            print("Installing MatrixLLM using: uv tool install matrixllm")
            subprocess.check_call(["uv", "tool", "install", "matrixllm"])
            return _have_cmd("matrixllm")
        except Exception:
            pass

    # Try pipx
    if _have_cmd("pipx"):
        try:
            print("Installing MatrixLLM using: pipx install matrixllm")
            subprocess.check_call(["pipx", "install", "matrixllm"])
            return _have_cmd("matrixllm")
        except Exception:
            pass

    print("MatrixLLM not found and auto-install failed.")
    print("Install it manually, then retry:")
    print("  uv tool install matrixllm")
    print("  or pipx install matrixllm")
    return False


def start_matrixllm_pairing(
    *,
    base_url: str,
    model: str,
    host: str = "127.0.0.1",
    port: int = 11435,
) -> GatewayProc:
    """
    Start MatrixLLM in pairing mode, capturing stdout so we can parse pairing code.
    """
    if not is_local_base_url(base_url):
        raise RuntimeError("Refusing to start pairing gateway for non-local base_url")

    cmd = [
        "matrixllm",
        "start",
        "--auth",
        "pairing",
        "--host",
        host,
        "--port",
        str(port),
        "--model",
        model,
    ]

    # Start process
    print("Starting MatrixLLM (pairing mode, local-only)...")
    print("Command:", " ".join(cmd))

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    # Keep a rolling log so we can show useful output if startup fails.
    logs: Deque[str] = deque(maxlen=500)
    gw = GatewayProc(proc=proc, pairing_code=None, log_lines=logs)

    def _reader() -> None:
        if not proc.stdout:
            return
        for raw in iter(proc.stdout.readline, ""):
            line = raw.rstrip("\n")
            if not line:
                continue
            logs.append(line)
            # Stream gateway output so users see slow first-run work
            # (model downloads, Ollama install, etc.).
            print(line)
            if gw.pairing_code is None and "Pairing code:" in line:
                parts = line.split("Pairing code:", 1)
                if len(parts) == 2:
                    candidate = parts[1].strip()
                    if candidate:
                        gw.pairing_code = candidate.split()[0]

    t = threading.Thread(target=_reader, name="matrixllm-stdout", daemon=True)
    t.start()

    return gw


def stop_gateway(gw: GatewayProc) -> None:
    try:
        gw.proc.terminate()
    except Exception:
        pass
