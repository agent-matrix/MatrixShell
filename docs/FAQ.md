# MatrixShell FAQ

Frequently asked questions about MatrixShell (`matrixsh`).

---

## General

### What is MatrixShell?

MatrixShell (`matrixsh`) is an interactive wrapper shell that makes your terminal AI-assisted using MatrixLLM. It does **not** modify CMD/PowerShell/bash directly — it runs its own interactive loop that can execute commands in your preferred shell.

### What platforms are supported?

- **Windows** — PowerShell (default) or CMD
- **macOS** — Bash
- **Linux** — Bash
- **WSL** — Bash (Windows Subsystem for Linux)

### What languages does it understand?

MatrixShell can understand natural language in any language that the underlying model supports. This includes English, Italian, Spanish, French, German, Portuguese, Chinese, Japanese, and many more.

---

## Setup & Installation

### Do I need MatrixLLM running?

Not necessarily.

- If MatrixLLM is already running, MatrixShell connects to it.
- If it's not running locally, `matrixsh setup` can install/start it and pair automatically.

### What does "pairing" mean?

Pairing is a simple local login flow:

1. MatrixShell starts MatrixLLM in pairing mode (localhost only)
2. MatrixLLM prints a short pairing code like `483-921`
3. You enter it once in MatrixShell
4. MatrixShell saves a token and doesn't ask again

This avoids copy/pasting long API keys for local usage.

### When do I need an API key?

When you connect to a **remote** MatrixLLM gateway (LAN/server/cloud), pairing is disabled for security. In that case, use:

```bash
matrixsh install --url http://SERVER:11435/v1 --key "sk-..."
```

### How do I reset pairing?

Delete the stored token:

- Remove `token` from config file, or
- Delete the config file entirely

Then rerun:

```bash
matrixsh setup
```

---

## Usage

### Why does MatrixShell ask "Execute it? (yes/no)"?

Safety. Even if MatrixLLM suggests a command, MatrixShell will not execute it without your confirmation. This prevents accidental execution of destructive commands.

### Why are some commands refused even if I type "yes"?

MatrixShell includes a hard denylist for extremely high-risk commands, like:

- Disk formatting/partitioning (`format`, `mkfs`, `fdisk`)
- Raw disk writes (`dd if=...`)
- Registry edits (Windows)
- Shutdown/reboot commands

This is a safety valve to prevent accidental system damage. You can still copy/paste manually if you truly intend it.

### How does MatrixShell decide something is natural language?

It uses simple heuristics:

- Multiple words with spaces
- Question words (how, what, why, when, where)
- Non-ASCII characters common in natural language
- Sentences ending with `?`

If a command fails with "command not found", it also triggers AI fallback.

### Can I use it as my default system shell?

Not directly (because it's a wrapper), but you can:

- Open it instead of your usual terminal
- Alias it (e.g., `alias ai="matrixsh"`)
- Set your terminal app to run `matrixsh` on startup

---

## Privacy & Security

### Does MatrixShell send my files to the model?

**No.** MatrixShell only sends lightweight context:

- Current directory path
- A list of file/folder names (not file contents)
- Your input and short local history

It does not read or upload your files unless you explicitly command it to (e.g., `cat file.txt`).

### Is my data stored anywhere?

- **Locally**: Command history is stored per-directory in `~/.matrixsh/history/`
- **Gateway**: Depends on your MatrixLLM configuration. Local gateways don't send data externally.

### Why is pairing local-only?

Pairing uses a short code displayed on the server console. If the gateway were remote, anyone could see the code and pair maliciously. For remote gateways, use API keys which are transmitted securely over HTTPS.

---

## Configuration

### Where is config stored?

| Platform | Path |
|----------|------|
| Linux/macOS/WSL | `~/.config/matrixsh/config.json` |
| Windows | `%APPDATA%\matrixsh\config.json` |

### What environment variables are supported?

| Variable | Description |
|----------|-------------|
| `MATRIXLLM_BASE_URL` | Gateway URL |
| `MATRIXSH_BASE_URL` | Alternative to above |
| `MATRIXLLM_API_KEY` | API key for authentication |
| `MATRIXSH_API_KEY` | Alternative to above |
| `MATRIXSH_TOKEN` | Pairing token (takes priority) |
| `MATRIXLLM_MODEL` | Model name |
| `MATRIXSH_MODEL` | Alternative to above |

Environment variables override config file settings.

### What's the priority order for settings?

1. Command-line arguments (`--url`, `--key`, etc.)
2. Environment variables
3. Config file (`config.json`)
4. Built-in defaults

---

## Troubleshooting

### "401 Unauthorized"

This means the gateway requires credentials.

**Fix:**
- Local: `matrixsh setup`
- Remote: `matrixsh install --key "sk-..."`

### MatrixLLM not running

Run:

```bash
matrixsh setup
```

Or start MatrixLLM yourself:

```bash
matrixllm start --auth pairing --host 127.0.0.1 --port 11435 --model deepseek-r1
```

### WSL can't reach localhost

In most WSL2 setups, `localhost` works. If not:

- Try `http://127.0.0.1:11435/v1`
- Verify Windows firewall rules
- Ensure MatrixLLM is bound to `0.0.0.0` if you need WSL access

### Pairing code not showing

Make sure MatrixLLM is started with `--auth pairing`:

```bash
matrixllm start --auth pairing --host 127.0.0.1 --port 11435
```

The pairing code appears in the MatrixLLM server output.

### Command suggestions are wrong or unhelpful

Try:

1. Be more specific in your request
2. Include context (what you're trying to achieve)
3. Check that the correct model is configured
4. Ensure MatrixLLM is running the model you expect

### Health check keeps failing

1. Verify MatrixLLM is running: `curl http://localhost:11435/health`
2. Check the port is correct
3. Try `matrixsh --no-healthcheck` to skip the check temporarily

---

## Advanced

### Can I use a different model?

Yes! Set it in config or via command line:

```bash
matrixsh --model gpt-4
matrixsh setup --model claude-3-opus
```

Or in your config file:

```json
{
  "model": "your-model-name"
}
```

### Can I use a remote/cloud gateway?

Yes, but pairing is disabled for security. Use API keys:

```bash
matrixsh install --url https://your-gateway.com/v1 --key "sk-..."
```

### How do I see what's being sent to the model?

Currently, MatrixShell doesn't have a verbose/debug mode for this. You can inspect the MatrixLLM server logs to see incoming requests.

### Can I contribute?

Yes! Contributions are welcome. Please open an issue or submit a pull request on GitHub.

---

## Exit

To exit MatrixShell:

```
/exit
```

or

```
/quit
```

Or press `Ctrl+C` / `Ctrl+D`.
