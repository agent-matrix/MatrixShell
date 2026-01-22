from **future** import annotations

import json
from dataclasses import dataclass
from typing import Dict, Iterator, Literal, Optional

import requests

Risk = Literal["low", "medium", "high"]

@dataclass
class Suggestion:
explanation: str
command: str
risk: Risk

class MatrixLLM:
def **init**(self, base_url: str, api_key: str, timeout_s: int = 120):
self.base_url = base_url.rstrip("/")
self.api_key = api_key
self.timeout_s = timeout_s

```
def _headers(self) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if self.api_key:
        h["Authorization"] = f"Bearer {self.api_key}"
    return h

def health(self) -> bool:
    try:
        url = self.base_url.replace("/v1", "") + "/health"
        r = requests.get(url, timeout=8)
        return r.status_code == 200
    except Exception:
        return False

def _post_chat(self, payload: dict, stream: bool) -> requests.Response:
    url = f"{self.base_url}/chat/completions"
    r = requests.post(
        url,
        headers=self._headers(),
        json=payload,
        timeout=self.timeout_s if not stream else None,
        stream=stream,
    )
    r.raise_for_status()
    return r

def chat_text(self, *, model: str, messages: list[dict], temperature: float = 0.2) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    r = self._post_chat(payload, stream=False)
    data = r.json()
    return data["choices"][0]["message"]["content"]

def chat_stream(self, *, model: str, messages: list[dict], temperature: float = 0.2) -> Iterator[str]:
    """
    OpenAI-compatible streaming uses SSE lines like:
      data: {"choices":[{"delta":{"content":"..."} }]}
      data: [DONE]
    We'll yield only the content deltas.
    """
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    r = self._post_chat(payload, stream=True)

    for raw in r.iter_lines(decode_unicode=True):
        if not raw:
            continue
        line = raw.strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if data == "[DONE]":
            break
        try:
            obj = json.loads(data)
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            chunk = delta.get("content")
            if chunk:
                yield chunk
        except Exception:
            continue

def suggest(self, *, model: str, os_name: str, shell_mode: str, cwd: str, files: list[str], user_input: str) -> Suggestion:
    system = (
        "You are a terminal assistant.\n"
        "Return ONLY valid JSON with keys: explanation, command, risk.\n"
        "risk must be one of: low, medium, high.\n"
        "Rules:\n"
        "- Use the user's language.\n"
        "- Generate a command appropriate to OS + shell.\n"
        "- If it deletes/moves/overwrites, modifies system settings, network config, disks, or registry: risk=high.\n"
        "- Do NOT include markdown. JSON only.\n"
    )

    user = {
        "os": os_name,
        "shell": shell_mode,
        "cwd": cwd,
        "files": files[:200],
        "input": user_input,
    }

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]

    content = self.chat_text(model=model, messages=messages, temperature=0.2)

    try:
        obj = json.loads(content)
        explanation = str(obj.get("explanation", "")).strip()
        command = str(obj.get("command", "")).strip()
        risk = obj.get("risk", "medium")
        if risk not in ("low", "medium", "high"):
            risk = "medium"
        if not command:
            raise ValueError("Empty command")
        return Suggestion(explanation=explanation, command=command, risk=risk)  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Model returned invalid JSON: {e}\nRaw:\n{content}")
```

