from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class PairInfo:
    pairing: bool
    expires_in: int
    local_only: bool
    auth_mode: str


def _pair_info_url(base_url: str) -> str:
    return base_url.replace("/v1", "").rstrip("/") + "/pair/info"


def _pair_submit_url(base_url: str) -> str:
    return base_url.replace("/v1", "").rstrip("/") + "/pair"


def get_pair_info(base_url: str) -> Optional[PairInfo]:
    try:
        r = requests.get(_pair_info_url(base_url), timeout=3)
        if r.status_code != 200:
            return None
        obj = r.json()
        return PairInfo(
            pairing=bool(obj.get("pairing")),
            expires_in=int(obj.get("expires_in", 0)),
            local_only=bool(obj.get("local_only", True)),
            auth_mode=str(obj.get("auth_mode", "")),
        )
    except Exception:
        return None


def submit_pair_code(base_url: str, code: str, client_name: str = "matrixsh") -> str:
    payload = {"code": code, "client_name": client_name}
    r = requests.post(_pair_submit_url(base_url), json=payload, timeout=8)
    r.raise_for_status()
    obj = r.json()
    token = str(obj.get("token", "")).strip()
    if not token:
        raise RuntimeError("Pair response missing token")
    return token
