# matrixsh_project/src/matrixsh/history.py

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def _base_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".matrixsh"


def _history_dir() -> Path:
    return _base_dir() / "history"


def _dir_key(cwd: str) -> str:
    """Stable per-directory key (so each folder has its own history file)."""
    h = hashlib.sha256(cwd.encode("utf-8", errors="ignore")).hexdigest()
    return h[:16]


def history_path_for_cwd(cwd: str) -> Path:
    return _history_dir() / f"{_dir_key(cwd)}.jsonl"


@dataclass
class HistoryItem:
    ts: str
    cwd: str
    kind: str  # "user" | "assistant" | "exec"
    text: str


def append_history(cwd: str, kind: str, text: str) -> None:
    _history_dir().mkdir(parents=True, exist_ok=True)
    item = HistoryItem(
        ts=datetime.now().isoformat(timespec="seconds"),
        cwd=cwd,
        kind=kind,
        text=text,
    )
    path = history_path_for_cwd(cwd)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item.__dict__, ensure_ascii=False) + "\n")


def load_recent(cwd: str, limit: int = 50) -> list[HistoryItem]:
    path = history_path_for_cwd(cwd)
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    lines = lines[-limit:]

    out: list[HistoryItem] = []
    for ln in lines:
        try:
            obj = json.loads(ln)
            out.append(HistoryItem(**obj))
        except Exception:
            continue
    return out
