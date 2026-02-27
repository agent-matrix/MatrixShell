from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Literal, Optional

import requests

Risk = Literal["low", "medium", "high"]


class UnauthorizedError(RuntimeError):
    pass


@dataclass
class ToolCallRequest:
    """A request to call a tool."""
    tool_name: str
    namespace: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.namespace}.{self.tool_name}"


@dataclass
class Suggestion:
    explanation: str
    command: str
    risk: Risk


@dataclass
class ToolAwareSuggestion:
    """Suggestion that may include tool calls."""
    explanation: str
    command: str = ""
    risk: Risk = "low"
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    use_tools: bool = False


class MatrixLLM:
    def __init__(self, base_url: str, api_key: str, token: str = "", timeout_s: int = 120):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token
        self.timeout_s = timeout_s

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Content-Type": "application/json"}

        # Prefer pairing token if present
        cred = (self.token or "").strip() or (self.api_key or "").strip()
        if cred:
            h["Authorization"] = f"Bearer {cred}"

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

        if r.status_code == 401:
            raise UnauthorizedError(
                "Unauthorized (401). MatrixLLM requires credentials.\n"
                "Fix options:\n"
                "  - If local: run `matrixsh setup` to start/pair automatically\n"
                "  - Or set API key: matrixsh install --key \"sk-...\"\n"
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

            data = line[len("data:") :].strip()
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

    def suggest(
        self,
        *,
        model: str,
        os_name: str,
        shell_mode: str,
        cwd: str,
        files: list[str],
        user_input: str,
    ) -> Suggestion:
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
            return Suggestion(explanation=explanation, command=command, risk=risk)  # type: ignore[arg-type]
        except Exception as e:
            raise RuntimeError(f"Model returned invalid JSON: {e}\nRaw:\n{content}")

    def suggest_with_tools(
        self,
        *,
        model: str,
        os_name: str,
        shell_mode: str,
        cwd: str,
        files: list[str],
        user_input: str,
        available_tools: list[dict],
    ) -> ToolAwareSuggestion:
        """Get a suggestion that may include tool calls.

        When tools are available, the LLM can choose to:
        1. Suggest a shell command (traditional behavior)
        2. Suggest using one or more tools from the available tools list
        """
        # Build tool descriptions for the prompt
        tool_descriptions = []
        for tool in available_tools:
            ns = tool.get("namespace", "")
            name = tool.get("name", "")
            desc = tool.get("description", "")
            schema = tool.get("input_schema", {})

            tool_desc = f"- {ns}.{name}: {desc}"
            if schema and schema.get("properties"):
                params = list(schema["properties"].keys())
                tool_desc += f" (params: {', '.join(params)})"
            tool_descriptions.append(tool_desc)

        tools_section = "\n".join(tool_descriptions) if tool_descriptions else "No tools available"

        system = f"""You are a terminal assistant with access to tools.

AVAILABLE TOOLS:
{tools_section}

Return ONLY valid JSON with these fields:
- explanation: What you're going to do
- use_tools: boolean, true if you'll use tools
- tool_calls: array of tool calls (if use_tools is true)
  Each tool call has: namespace, tool_name, arguments, description
- command: shell command (if use_tools is false)
- risk: "low", "medium", or "high"

RULES:
- Use tools when they match the user's request better than shell commands
- For file operations (find large files, scan directories, etc.), prefer tools if available
- If no suitable tool exists, fall back to shell commands
- Use the user's language for explanation
- Generate commands appropriate to OS + shell
- If command deletes/moves/overwrites, modifies system settings: risk=high

EXAMPLE (using tool):
{{"explanation": "I'll use the storagepilot tool to find large files", "use_tools": true, "tool_calls": [{{"namespace": "catalog.storagepilot", "tool_name": "find_large_files", "arguments": {{"path": "/home/user", "min_size_mb": 100}}, "description": "Finding files larger than 100MB"}}], "risk": "low"}}

EXAMPLE (shell command):
{{"explanation": "I'll list the files in the current directory", "use_tools": false, "command": "ls -la", "risk": "low"}}
"""

        user = {
            "os": os_name,
            "shell": shell_mode,
            "cwd": cwd,
            "files": files[:100],
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
            use_tools = bool(obj.get("use_tools", False))
            command = str(obj.get("command", "")).strip()
            risk = obj.get("risk", "low")

            if risk not in ("low", "medium", "high"):
                risk = "low"

            tool_calls = []
            if use_tools and obj.get("tool_calls"):
                for tc in obj["tool_calls"]:
                    tool_calls.append(ToolCallRequest(
                        namespace=tc.get("namespace", ""),
                        tool_name=tc.get("tool_name", ""),
                        arguments=tc.get("arguments", {}),
                        description=tc.get("description", ""),
                    ))

            return ToolAwareSuggestion(
                explanation=explanation,
                command=command,
                risk=risk,
                tool_calls=tool_calls,
                use_tools=use_tools,
            )
        except Exception as e:
            # Fall back to regular suggestion behavior
            return ToolAwareSuggestion(
                explanation=f"Could not parse response: {e}",
                command="",
                risk="high",
                use_tools=False,
            )
