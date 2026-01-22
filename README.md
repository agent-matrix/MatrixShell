<p align="center">
  <img src="assets/logo.svg" alt="MatrixShell Logo" width="400">
</p>

<p align="center">
  <strong>Turn your terminal into a safe, AI-assisted shell</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#usage">Usage</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#security">Security</a> •
  <a href="docs/FAQ.md">FAQ</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/platform-Windows%20|%20macOS%20|%20Linux-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="License">
</p>

---

Type normal commands as usual.
Type **natural language** (any language) and MatrixShell suggests the right command, explains it, and runs it **only with your confirmation**.

```text
/home/user/projects$ come posso cancellare questa cartella

╭─────────────────────────────────── MatrixLLM ───────────────────────────────────╮
│ Per cancellare la cartella, usa questo comando:                                 │
│                                                                                 │
│     rm -rf "BOT-MMORPG-AI-DEV"                                                  │
│                                                                                 │
│ Questo eliminerà tutti i file definitivamente.                                  │
╰─────────────────────────────────────────────────────────────────────────────────╯
Suggested command:
rm -rf "BOT-MMORPG-AI-DEV"
Risk: high

Execute it? (yes/no)
```

---

## Features

- **Natural Language to Commands** — Describe what you want in plain English, Italian, Spanish, or any language
- **Smart Command Detection** — Automatically detects whether input is a command or natural language
- **Risk Assessment** — Every suggested command shows a risk level (low/medium/high)
- **Hard Safety Limits** — Dangerous operations (disk formatting, mass deletions) are blocked by default
- **Cross-Platform** — Works on Windows (CMD/PowerShell), macOS, and Linux (Bash)
- **One-Command Setup** — `matrixsh setup` handles everything automatically
- **Secure Pairing** — Local-only pairing mode ensures credentials stay on your machine
- **Context-Aware** — Maintains command history per directory for smarter suggestions

---

## Requirements

- **Python 3.9+**
- **MatrixLLM** — AI gateway (auto-installed by `matrixsh setup`)
- **uv** or **pipx** — For installing Python CLI tools (recommended)

---

## Installation

### Option A: Using pipx (Recommended)

**macOS / Linux / WSL**

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install matrixsh
```

**Windows PowerShell**

```powershell
python -m pip install --user pipx
python -m pipx ensurepath
pipx install matrixsh
```

### Option B: Using uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install matrixsh
```

### Option C: From Source (Dev Mode)

```bash
git clone https://github.com/agent-matrix/MatrixShell.git
cd MatrixShell
pip install -e .
```

---

## Quick Start

### 1) One-Command Setup

```bash
matrixsh setup
```

What it does:

- Ensures MatrixLLM is installed (auto-installs via `uv` or `pipx` if missing)
- Starts MatrixLLM locally in **pairing mode** on `127.0.0.1:11435`
- Prompts for a short pairing code (e.g., `483-921`)
- Stores a token so future runs are automatic

### 2) Run MatrixShell

```bash
matrixsh
```

That's it! You're ready to go.

---

## Usage

### Normal Commands (Pass-Through)

```bash
matrixsh
/home/user$ ls -la
/home/user$ cd projects
/home/user/projects$ git status
/home/user/projects$ docker ps
```

MatrixShell runs these commands normally and prints output. No AI involved.

### Natural Language Queries

Type what you want to do in any language:

**English:**
```
/home/user$ how can I find the biggest files here?
```

**Italian:**
```
C:\Users\rusla\temp> come posso cancellare questa cartella
```

**Spanish:**
```
/home/user$ cómo puedo ver los procesos que usan más memoria
```

MatrixShell detects natural language, asks MatrixLLM, and shows:

```
╭─────────────────────────────────── MatrixLLM ───────────────────────────────────╮
│ To find the biggest files, use this command which shows the top 20 largest:     │
╰─────────────────────────────────────────────────────────────────────────────────╯
Suggested command:
du -ah . | sort -hr | head -n 20
Risk: low

Execute it? (yes/no)
```

### Handling "Command Not Found"

If you type a word that isn't a command:

```bash
/home/user$ hello
bash: hello: command not found
```

MatrixShell automatically switches to AI help and may suggest:

```bash
echo "Hello!"
```

### Shell Modes

Force a specific shell mode:

```bash
matrixsh --mode powershell   # Windows PowerShell
matrixsh --mode cmd          # Windows CMD
matrixsh --mode bash         # Linux/macOS Bash
matrixsh --mode auto         # Auto-detect (default)
```

### Exit

```
/exit
```

---

## How It Works

### Step-by-Step Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              MatrixShell Flow                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   User Input                                                                    │
│       │                                                                         │
│       ▼                                                                         │
│   ┌───────────────────┐                                                         │
│   │ Is it a command?  │──── Yes ────▶ Execute directly ──▶ Show output          │
│   └───────────────────┘                                                         │
│       │ No / Failed                                                             │
│       ▼                                                                         │
│   ┌───────────────────┐                                                         │
│   │ Natural language  │                                                         │
│   │ or cmd not found  │                                                         │
│   └───────────────────┘                                                         │
│       │                                                                         │
│       ▼                                                                         │
│   ┌───────────────────┐      ┌─────────────────────────────────┐                │
│   │ Gather context:   │      │ MatrixLLM responds with:        │                │
│   │ • OS + shell      │─────▶│ • explanation                   │                │
│   │ • current dir     │      │ • suggested command             │                │
│   │ • file list       │      │ • risk level (low/medium/high)  │                │
│   │ • recent history  │      └─────────────────────────────────┘                │
│   └───────────────────┘                    │                                    │
│                                            ▼                                    │
│                               ┌───────────────────────┐                         │
│                               │ Show suggestion       │                         │
│                               │ Ask: Execute? (y/n)   │                         │
│                               └───────────────────────┘                         │
│                                            │                                    │
│                          ┌─────────────────┴─────────────────┐                  │
│                          │                                   │                  │
│                         Yes                                 No                  │
│                          │                                   │                  │
│                          ▼                                   ▼                  │
│                   ┌─────────────┐                    ┌──────────────┐           │
│                   │ Check       │                    │ Cancelled.   │           │
│                   │ denylist    │                    └──────────────┘           │
│                   └─────────────┘                                               │
│                          │                                                      │
│              ┌───────────┴───────────┐                                          │
│              │                       │                                          │
│           Allowed                 Denied                                        │
│              │                       │                                          │
│              ▼                       ▼                                          │
│       ┌─────────────┐      ┌─────────────────────┐                              │
│       │ Execute     │      │ Refusing to execute │                              │
│       │ Show output │      │ (safety denylist)   │                              │
│       └─────────────┘      └─────────────────────┘                              │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1) Smart Wrapper Shell

MatrixShell is not a plugin that modifies CMD/PowerShell/bash.
Instead, it runs its **own interactive loop**:

- Shows a normal prompt (like `C:\...>` or `/home/...$`)
- Reads what you type
- Decides what to do next

### 2) Tries Normal Commands First

If you type a real command (`dir`, `ls`, `cd`, `git status`, `python --version`), MatrixShell executes it using the selected shell mode:

- **Windows**: PowerShell by default (or CMD if you choose)
- **Linux/macOS/WSL**: Bash

If the command succeeds, it just prints output. No AI needed.

### 3) Detects Natural Language or "Command Not Found"

If you type something like:

- "come posso cancellare questa cartella?"
- "how do I find big files?"
- "why is port 11435 busy?"

Or you type a command that fails with "command not found", MatrixShell switches into **AI fallback mode**.

### 4) Sends Context to MatrixLLM

MatrixShell gathers helpful context:

- OS + shell mode
- Current directory
- List of files/folders in the directory
- Your last few messages (history per directory)

Then it calls MatrixLLM's endpoint: `POST /v1/chat/completions`

MatrixLLM responds with **structured JSON**:

```json
{
  "explanation": "...",
  "command": "...",
  "risk": "low|medium|high"
}
```

### 5) Shows Suggestion and Asks Permission

MatrixShell prints:

- Explanation (in your language)
- Suggested command
- Risk level

Then asks:

```
Execute it? (yes/no)
```

**Only if you answer yes**, it runs the command.

---

## Configuration

### Config File Location

| Platform | Path |
|----------|------|
| Linux/macOS/WSL | `~/.config/matrixsh/config.json` |
| Windows | `%APPDATA%\matrixsh\config.json` |

### Config File Format

```json
{
  "base_url": "http://localhost:11435/v1",
  "api_key": "",
  "token": "mtx_abc123...",
  "model": "deepseek-r1",
  "timeout_s": 120
}
```

### Environment Variables

Environment variables override config file settings:

| Variable | Description |
|----------|-------------|
| `MATRIXLLM_BASE_URL` | Gateway URL |
| `MATRIXSH_BASE_URL` | Alternative to above |
| `MATRIXLLM_API_KEY` | API key for authentication |
| `MATRIXSH_API_KEY` | Alternative to above |
| `MATRIXSH_TOKEN` | Pairing token (takes priority) |
| `MATRIXLLM_MODEL` | Model name |
| `MATRIXSH_MODEL` | Alternative to above |

### Priority Order

1. Command-line arguments (`--url`, `--key`, etc.)
2. Environment variables
3. Config file
4. Built-in defaults

---

## Commands Reference

| Command | Description |
|---------|-------------|
| `matrixsh` | Start interactive shell |
| `matrixsh setup` | One-command setup (install, start, pair) |
| `matrixsh install` | Write config and test gateway connection |
| `/exit` or `/quit` | Exit MatrixShell (inside the shell) |

### Setup Options

```bash
matrixsh setup --port 8080           # Custom port
matrixsh setup --model gpt-4         # Custom model
matrixsh setup --url http://...      # Custom URL (local only)
```

### Install Options

```bash
matrixsh install --url https://api.example.com/v1 --key "sk-..."
matrixsh install --token "mtx_..."
matrixsh install --model gpt-4
```

### Runtime Options

```bash
matrixsh --no-healthcheck            # Skip health check
matrixsh --stream                    # Enable streaming
matrixsh --url ... --model ... --key ...  # Override for session
```

---

## Security

### Confirmation Before Execution

MatrixShell **always** asks:

```
Execute it? (yes/no)
```

Nothing runs without your explicit approval.

### Hard Denylist

MatrixShell refuses to execute system-critical commands, even if you type "yes":

| Platform | Blocked Commands |
|----------|-----------------|
| **Windows** | `format`, `diskpart`, `bcdedit`, registry modifications |
| **Linux/macOS** | `mkfs.*`, `dd if=...`, `fdisk`, `parted` |
| **All** | `shutdown`, `reboot`, `init 0` |

You can still copy/paste manually if you truly intend it.

### Pairing Mode Security

- **Local-Only** — Pairing only works with `localhost`, `127.0.0.1`, or `::1`
- **One-Time Code** — 6-digit codes expire quickly
- **Token-Based Auth** — After pairing, a token (`mtx_...`) is saved locally
- **No Network Exposure** — Gateway binds to `127.0.0.1` by default

### Remote Gateways

For remote MatrixLLM instances, pairing is **disabled** for security.
Use API keys instead:

```bash
matrixsh install --url https://api.example.com/v1 --key "sk-..."
```

---

## What MatrixShell Sends to the Model

MatrixShell only sends lightweight context:

- Current directory path
- A list of file/folder names (not file contents)
- Your input and short local history

It does **not** read or upload your files unless you explicitly command it to (e.g., `cat file.txt`).

---

## Troubleshooting

### MatrixLLM Not Running

```
MatrixLLM not running. Start it now? [Y/n]
```

Press Enter to start automatically, or run:

```bash
matrixsh setup
```

### Unauthorized (401)

```
Unauthorized (401). MatrixLLM requires credentials.
```

**Solutions:**
- Local: `matrixsh setup`
- Remote: `matrixsh install --key "sk-..."`

### Pairing Not Enabled

```
Pairing is not enabled on this MatrixLLM instance.
```

Restart MatrixLLM with pairing:

```bash
matrixllm start --auth pairing --host 127.0.0.1 --port 11435
```

### WSL Can't Reach localhost

In most WSL2 setups, `localhost` works. If not:

- Try `http://127.0.0.1:11435/v1`
- Verify Windows firewall rules
- Ensure MatrixLLM is bound correctly

---

## Demo

Run the fake terminal demo:

```bash
make demo
```

Or record a real demo with asciinema:

```bash
bash demo/record_asciinema.sh
```

See [docs/DEMO.md](docs/DEMO.md) for detailed instructions.

---

## Documentation

- [FAQ](docs/FAQ.md) — Frequently asked questions
- [Demo Guide](docs/DEMO.md) — How to record demos

---

## License

Apache License 2.0 — See [LICENSE](LICENSE) for details.

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

---

<p align="center">
  <strong>MatrixShell</strong> — Your terminal, augmented with AI.
</p>
