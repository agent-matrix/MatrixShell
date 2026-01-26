# MatrixShell Agent Design Analysis

## Overview

MatrixShell is a **Python-based AI-augmented shell wrapper** (approximately 1,057 lines of code) that implements an implicit agent architecture. While it doesn't use explicit "Agent" classes, the MatrixLLM component acts as the "brain" of an intelligent terminal assistant.

## Project Structure

```
/src/matrixsh/
├── __init__.py    - Version info
├── cli.py         - Main interactive loop and command handling
├── llm.py         - LLM client for MatrixLLM gateway communication
├── shell.py       - Shell execution (bash, PowerShell, cmd)
├── gateway.py     - MatrixLLM process management and health checks
├── safety.py      - Input classification and safety denylist
├── history.py     - Per-directory command history management
├── config.py      - Configuration loading/saving
├── pair.py        - Pairing token authentication
└── install.py     - Setup and installation helpers
```

## Agent Architecture

MatrixShell follows a **constrained agent pattern** with multiple layers of safety and user interaction.

### Core Components

| Component | Purpose | File |
|-----------|---------|------|
| `MatrixLLM` | The agent's "brain" - generates suggestions | `llm.py` |
| `shell.py` | Command execution backend | `shell.py` |
| `safety.py` | Guardrails and input classification | `safety.py` |
| `cli.py` | Main control loop | `cli.py` |
| `history.py` | Context memory | `history.py` |

### The MatrixLLM Agent

The `MatrixLLM` class (`llm.py`) is the central agent component:

```python
@dataclass
class Suggestion:
    explanation: str      # Natural language explanation
    command: str          # Suggested shell command
    risk: Risk           # low | medium | high

class MatrixLLM:
    def suggest(self, model, os_name, shell_mode, cwd, files, user_input) -> Suggestion
    def health(self) -> bool
    def chat_text(self, model, messages) -> str
    def chat_stream(self, model, messages) -> Iterator[str]
```

**Key Method**: `suggest()` transforms natural language input into actionable shell commands with risk assessment.

## Terminal Command Obedience

### Does MatrixShell Obey Terminal Commands?

**Yes, with safeguards!** The agent handles commands through two distinct paths:

### Path 1: Direct Shell Commands

Commands that look like shell syntax (e.g., `ls`, `git status`, `python script.py`) are executed immediately:

```python
# shell.py
def execute(shell_mode: str, command: str, cwd: str) -> ExecResult:
    if shell_mode == "bash":
        return _run_bash(command, cwd)
    elif shell_mode == "powershell":
        return _run_powershell(command, cwd)
    else:
        return _run_cmd(command, cwd)
```

### Path 2: Natural Language Queries

Natural language input goes through the AI agent:

1. **Classification** (`safety.py:looks_like_natural_language`)
2. **Context Gathering** (OS, cwd, files, history)
3. **LLM Suggestion** (structured JSON response)
4. **Denylist Check** (hard block dangerous commands)
5. **User Confirmation** (explicit yes/no)
6. **Execution** (only on approval)

### Input Classification Heuristics

```python
def looks_like_natural_language(s: str) -> bool:
    # Detects questions and multi-word sentences
    # Question words: how, what, why, where, when, can, could
    # Non-ASCII markers: come, cosa, perche, dove, quando (Italian)
    # Returns False for shell operators: |, &&, ||, >, <, ;
```

## Command Flow Architecture

```
User Input
    │
    ├──▶ Is "cd" command? ──▶ Handle in-process, update cwd
    │
    ├──▶ Is shell command? ──▶ Execute directly via shell.py
    │
    └──▶ Is natural language?
              │
              ▼
         Gather Context:
         - OS + shell mode
         - Current directory
         - File list (first 200)
         - Recent history (12 items)
              │
              ▼
         POST to MatrixLLM
         /v1/chat/completions
              │
              ▼
         Parse JSON Response:
         {
           "explanation": str,
           "command": str,
           "risk": "low|medium|high"
         }
              │
              ▼
         Denylist Check
         (hard block if matched)
              │
              ▼
         Display Suggestion + Risk
         "Execute? (yes/no)"
              │
              ├──▶ YES ──▶ Execute command
              │           Save to history
              │
              └──▶ NO ──▶ Cancel, continue loop
```

## Safety Mechanisms

### Hard Denylist (Irreversible Operations)

The agent **refuses** to execute certain dangerous commands regardless of user approval:

```python
# safety.py
patterns = [
    # Windows
    (r"\bformat(\.com)?\b", "Refusing disk format."),
    (r"\bdiskpart\b", "Refusing disk partitioning."),
    (r"\bbcdedit\b", "Refusing boot config edits."),

    # Linux/Mac
    (r"\bmkfs\.", "Refusing filesystem creation."),
    (r"\bdd\s+if=", "Refusing raw disk writes."),
    (r"\bparted\b|\bgdisk\b|\bfdisk\b", "Refusing partition tools."),

    # System-wide
    (r"\bshutdown\b|\breboot\b", "Refusing shutdown/reboot."),
    (r"\bapt\s+remove\b|\bapt\s+purge\b", "Refusing package removal."),
]
```

### Multi-Layer Safety

1. **Input Classification**: Distinguishes shell commands from natural language
2. **Command Not Found Detection**: Falls back to AI if command fails
3. **Risk Assessment**: LLM returns low/medium/high risk level
4. **Denylist Matching**: Hard blocks dangerous commands
5. **User Confirmation**: Explicit approval required before execution

## Communication Protocol

### HTTP REST API (OpenAI-compatible)

```
Endpoint: POST {base_url}/v1/chat/completions
Auth: Bearer token (pairing or API key)
```

**Request Structure**:
```python
messages = [
    {
        "role": "system",
        "content": "Return ONLY valid JSON with: explanation, command, risk"
    },
    {
        "role": "user",
        "content": {
            "os": "linux",
            "shell": "bash",
            "cwd": "/home/user/projects",
            "files": ["file1.py", ...],
            "input": "how do I find large files?"
        }
    }
]
```

**Response Format**:
```json
{
    "explanation": "Use du to find disk usage and sort by size",
    "command": "du -ah . | sort -hr | head -n 20",
    "risk": "low"
}
```

## Shell Execution Backends

### Bash (Linux/macOS/WSL)
```python
def _run_bash(command: str, cwd: str) -> ExecResult:
    bash = ["bash", "-lc", command]  # Login shell with command
    p = subprocess.run(bash, cwd=cwd, capture_output=True, text=True)
    return ExecResult(p.returncode, p.stdout, p.stderr)
```

### PowerShell (Windows/Cross-platform)
```python
def _run_powershell(command: str, cwd: str) -> ExecResult:
    ps = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
```

### CMD (Windows Legacy)
```python
def _run_cmd(command: str, cwd: str) -> ExecResult:
    p = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)
```

## History & Context Management

### Per-Directory History

```python
@dataclass
class HistoryItem:
    ts: str         # ISO timestamp
    cwd: str        # Current working directory
    kind: str       # "user" | "assistant" | "exec"
    text: str       # Input/response/command
```

**Storage**: `~/.matrixsh/history/{dir_hash}.jsonl`
- Hash Key: SHA256 of directory path (first 16 chars)
- Format: JSON Lines (one object per line)

## Design Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **Adapter** | Shell backends (bash/ps/cmd) unified interface | `shell.py:execute()` |
| **Strategy** | Authentication (pairing vs API key) | `pair.py`, `config.py` |
| **Repository** | History storage abstraction | `history.py` |
| **Config Provider** | Settings with priority chain | `config.py:Settings.load()` |
| **Chain of Responsibility** | Sequential safety checks | `cli.py:main()` |

## Configuration Priority

Settings are loaded with this priority (highest to lowest):

1. Command-line arguments
2. Environment variables
3. Config file (`~/.config/matrixsh/config.json`)
4. Built-in defaults

```python
@dataclass
class Settings:
    base_url: str = "http://localhost:11435/v1"
    api_key: str = ""
    token: str = ""
    model: str = "deepseek-r1"
    timeout_s: int = 120
```

## Conclusion

MatrixShell implements a **constrained agent architecture** where:

1. **Agent Role**: MatrixLLM acts as an intelligent suggestion engine, not autonomous executor
2. **Command Recognition**: Heuristics differentiate shell commands from natural language
3. **Obedience Mechanism**: Multi-layer approval (classification → LLM → denylist → user confirmation)
4. **Context Awareness**: Per-directory history and filesystem context for better suggestions
5. **Safety First**: Hard denylist prevents destructive operations regardless of approval
6. **Multi-Shell Support**: Unified interface for bash, PowerShell, and cmd

The agent is "obedient" to terminal commands but with essential safeguards: it executes shell commands directly, while AI-suggested commands require explicit user confirmation and pass through safety validation.
