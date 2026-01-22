from **future** import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from typing import Tuple

@dataclass
class ExecResult:
code: int
stdout: str
stderr: str

def os_name() -> str:
return platform.system().lower()

def detect_default_mode() -> str:
if os.name == "nt":
return "powershell"
return "bash"

def list_files(cwd: str) -> list[str]:
try:
return sorted(os.listdir(cwd))
except Exception:
return []

def _run_cmd(command: str, cwd: str) -> ExecResult:
p = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)
return ExecResult(p.returncode, p.stdout or "", p.stderr or "")

def _run_powershell(command: str, cwd: str) -> ExecResult:
ps = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
p = subprocess.run(ps, cwd=cwd, capture_output=True, text=True)
return ExecResult(p.returncode, p.stdout or "", p.stderr or "")

def _run_bash(command: str, cwd: str) -> ExecResult:
bash = ["bash", "-lc", command]
p = subprocess.run(bash, cwd=cwd, capture_output=True, text=True)
return ExecResult(p.returncode, p.stdout or "", p.stderr or "")

def execute(command: str, mode: str, cwd: str) -> ExecResult:
if mode == "cmd":
return _run_cmd(command, cwd)
if mode == "powershell":
return _run_powershell(command, cwd)
return _run_bash(command, cwd)

def handle_cd(user_input: str, cwd: str, mode: str) -> Tuple[bool, str, str]:
s = user_input.strip()
if not s:
return False, cwd, ""

```
parts = s.split(maxsplit=1)
if parts[0].lower() != "cd":
    return False, cwd, ""

target = parts[1].strip().strip('"') if len(parts) > 1 else os.path.expanduser("~")

if mode == "cmd" and target.lower().startswith("/d "):
    target = target[3:].strip().strip('"')

new_path = os.path.abspath(os.path.join(cwd, target)) if not os.path.isabs(target) else os.path.abspath(target)

if os.path.isdir(new_path):
    return True, new_path, ""
return True, cwd, f"cd: no such directory: {target}"
```

def prompt_string(mode: str, cwd: str) -> str:
if os.name == "nt":
return f"{cwd}> "
return f"{cwd}$ "
