from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

APP = "matrixsh"


def config_dir() -> Path:
    """
    Cross-platform config directory:
      - Windows: %APPDATA%\\matrixsh
      - macOS/Linux: $XDG_CONFIG_HOME/matrixsh or ~/.config/matrixsh
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / APP
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / APP


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class Settings:
    base_url: str = "http://localhost:11435/v1"
    api_key: str = ""     # classic MatrixLLM key (sk-...)
    token: str = ""       # pairing token (mtx_...)
    model: str = "deepseek-r1"
    timeout_s: int = 120

    @staticmethod
    def load(path: Optional[Path] = None) -> "Settings":
        path = path or config_path()
        data: dict = {}

        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}

        s = Settings(
            base_url=str(data.get("base_url", Settings.base_url)),
            api_key=str(data.get("api_key", Settings.api_key)),
            token=str(data.get("token", Settings.token)),
            model=str(data.get("model", Settings.model)),
            timeout_s=int(data.get("timeout_s", Settings.timeout_s)),
        )

        # Environment overrides (highest priority)
        s.base_url = os.environ.get("MATRIXLLM_BASE_URL", os.environ.get("MATRIXSH_BASE_URL", s.base_url))
        s.api_key = os.environ.get("MATRIXLLM_API_KEY", os.environ.get("MATRIXSH_API_KEY", s.api_key))
        s.token = os.environ.get("MATRIXSH_TOKEN", s.token)
        s.model = os.environ.get("MATRIXLLM_MODEL", os.environ.get("MATRIXSH_MODEL", s.model))

        return s

    def save(self, path: Optional[Path] = None) -> Path:
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "token": self.token,
            "model": self.model,
            "timeout_s": self.timeout_s,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
