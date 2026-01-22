from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests


@dataclass
class GatewayProc:
    proc: subprocess.Popen[str]
    pairing_code: Optional[str] = None


def is_local_base_url(base_url: str) -> bool:
    """
    True if URL host is localhost / 127.0.0.1 / ::1
    """
    try:
        u = urlparse(base_url)
        host = (u.hostname or "").lower()
        return host in ("localhost", "127.0.0.1", "::1")
    except Exception:
        return False


def base_health_url(base_url: str) -> str:
    # base_url is like http://localhost:11435/v1
    return base_url.replace("/v1", "").rstrip("/") + "/health"


def probe_health(base_url: str, timeout_s: float = 1.5) -> bool:
    try:
        r = requests.get(base_health_url(base_url), timeout=timeout_s)
        return r.status_code == 200
    except Exception:
        return False


def wait_for_health(base_url: str, total_timeout_s: float = 20.0) -> bool:
    deadline = time.time() + total_timeout_s
    while time.time() < deadline:
        if probe_health(base_url, timeout_s=1.5):
            return True
        time.sleep(0.5)
    return False


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

    code = None
    # Try to read output for a short time to find "Pairing code:"
    deadline = time.time() + 15.0
    if proc.stdout:
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
            # echo server output lightly
            # (we keep it minimal to avoid flooding)
            if "Pairing code:" in line:
                # Expected: "Pairing code: 483-921"
                parts = line.split("Pairing code:", 1)
                if len(parts) == 2:
                    candidate = parts[1].strip()
                    if candidate:
                        code = candidate.split()[0]
                        break

    return GatewayProc(proc=proc, pairing_code=code)


def stop_gateway(gw: GatewayProc) -> None:
    try:
        gw.proc.terminate()
    except Exception:
        pass
