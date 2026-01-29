"""Simple .env file loader.

Loads environment variables from .env files without external dependencies.
Priority order (highest to lowest):
1. Existing environment variables (never overwritten)
2. .env in current working directory
3. .env in config directory (~/.config/matrixsh/.env)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


def parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a .env file and return key-value pairs.

    Handles:
    - Comments (lines starting with #)
    - Empty lines
    - KEY=value format
    - Quoted values (single or double quotes)
    - Export prefix (export KEY=value)
    """
    result: Dict[str, str] = {}

    if not path.exists():
        return result

    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return result

    for line in content.splitlines():
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Handle 'export KEY=value' format
        if line.startswith("export "):
            line = line[7:].strip()

        # Split on first '='
        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        # Remove surrounding quotes
        if len(value) >= 2:
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

        if key:
            result[key] = value

    return result


def load_env_files(config_dir: Path) -> None:
    """Load .env files into environment.

    Priority (loaded first = lower priority, can be overwritten):
    1. Config directory .env (~/.config/matrixsh/.env)
    2. Current working directory .env

    Existing environment variables are NEVER overwritten.
    """
    env_files = [
        config_dir / ".env",           # Config dir (lower priority)
        Path.cwd() / ".env",           # Current directory (higher priority)
    ]

    # Collect all env vars, later files override earlier
    combined: Dict[str, str] = {}

    for env_file in env_files:
        parsed = parse_env_file(env_file)
        combined.update(parsed)

    # Set environment variables (only if not already set)
    for key, value in combined.items():
        if key not in os.environ:
            os.environ[key] = value
