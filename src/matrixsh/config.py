from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .env import load_env_files
from .urls import api_base_url

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
    # Context Forge settings
    context_forge_url: str = ""
    context_forge_token: str = ""

    @staticmethod
    def load(path: Optional[Path] = None) -> "Settings":
        path = path or config_path()

        # Load .env files before reading environment variables
        # Priority: config dir .env < current dir .env < existing env vars
        load_env_files(config_dir())

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
            context_forge_url=str(data.get("context_forge_url", Settings.context_forge_url)),
            context_forge_token=str(data.get("context_forge_token", Settings.context_forge_token)),
        )

        # Environment overrides (highest priority)
        s.base_url = os.environ.get("MATRIXLLM_BASE_URL", os.environ.get("MATRIXSH_BASE_URL", s.base_url))
        s.api_key = os.environ.get("MATRIXLLM_API_KEY", os.environ.get("MATRIXSH_API_KEY", s.api_key))
        s.token = os.environ.get("MATRIXSH_TOKEN", s.token)
        s.model = os.environ.get("MATRIXLLM_MODEL", os.environ.get("MATRIXSH_MODEL", s.model))

        # Context Forge environment overrides
        s.context_forge_url = os.environ.get("CONTEXT_FORGE_URL", s.context_forge_url)
        s.context_forge_token = os.environ.get("CONTEXT_FORGE_TOKEN", s.context_forge_token)

        # Normalize to OpenAI-compatible base URL that ends with /v1
        s.base_url = api_base_url(s.base_url)

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
            "context_forge_url": self.context_forge_url,
            "context_forge_token": self.context_forge_token,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
