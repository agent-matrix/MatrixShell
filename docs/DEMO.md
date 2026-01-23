# MatrixShell Demo Guide

This guide explains how to create demos and recordings of MatrixShell for documentation, presentations, or sharing.

---

## Quick Start

### Run the Fake Demo (No Setup Required)

The fake demo simulates a MatrixShell session without needing MatrixLLM running:

```bash
# From project root
make demo

# Or directly
bash demo/fake_terminal_demo.sh
```

This is perfect for:
- Quick demonstrations
- Screen recording for GIFs
- Consistent output across systems

---

## Recording Options

### Option 1: Fake Terminal Demo

**Best for:** README GIFs, consistent demos, no dependencies

```bash
cd demo
make demo
```

The fake demo shows:
1. Welcome panel
2. Normal command execution (`ls`)
3. Italian natural language query
4. English natural language query
5. Command-not-found fallback
6. Safety denylist blocking

**To create a GIF:**

1. Start a screen recorder (e.g., LICEcap, Kap, OBS)
2. Run `make demo`
3. Save the recording as GIF

### Option 2: Real Recording with Asciinema

**Best for:** Authentic demos, shareable recordings

#### Prerequisites

```bash
# Install asciinema
pipx install asciinema

# Or on macOS
brew install asciinema

# Or on Ubuntu/Debian
sudo apt-get install asciinema
```

#### Record

```bash
cd demo
make record
```

This will:
1. Start asciinema recording
2. Open a new shell
3. You run `matrixsh` and interact with it
4. Type `exit` to end recording

#### Playback

```bash
asciinema play demo/matrixsh-demo.cast
```

#### Upload to asciinema.org

```bash
asciinema upload demo/matrixsh-demo.cast
```

#### Convert to GIF

Requires [agg](https://github.com/asciinema/agg):

```bash
# Install agg
cargo install agg

# Convert
cd demo
make gif
```

---

## Platform-Specific Demos

### Linux/macOS/WSL

Use the bash demos:

```bash
make demo          # Fake demo
make record        # Real recording
```

### Windows PowerShell

A sample transcript is provided at `demo/powershell_demo.txt`.

For real Windows recording, use:
- [Windows Terminal](https://github.com/microsoft/terminal) with built-in recording
- [ScreenToGif](https://www.screentogif.com/)
- PowerShell's `Start-Transcript` command

```powershell
# Start transcript
Start-Transcript -Path "demo.txt"

# Run MatrixShell
matrixsh

# ... interact ...

# Stop transcript
Stop-Transcript
```

---

## Demo Script Suggestions

When recording a real demo, try these interactions:

### Basic Commands
```
ls -la
git status
cd ..
```

### Natural Language (English)
```
how can I find large files in this directory
show me processes using the most memory
what's using port 8080
```

### Natural Language (Italian)
```
come posso cancellare questa cartella
mostrami i file più grandi
quali processi usano più memoria
```

### Natural Language (Spanish)
```
cómo puedo encontrar archivos grandes
muéstrame los procesos activos
```

### Command Not Found
```
gitstat
pythno --version
```

### Safety Demo
```
format my hard drive
delete everything in root
```

---

## Customizing the Fake Demo

Edit `demo/fake_terminal_demo.sh` to:

- Change typing speed: Modify `TYPING_SPEED` and `FAST_SPEED`
- Add new examples: Follow the existing pattern
- Change colors: Modify the color variables at the top

```bash
# Typing speed (seconds per character)
TYPING_SPEED=0.03    # Normal typing
FAST_SPEED=0.01      # Fast typing for commands
```

---

## Makefile Targets

From the `demo/` directory:

| Target | Description |
|--------|-------------|
| `make demo` | Run fake terminal demo |
| `make record` | Record with asciinema |
| `make gif` | Convert .cast to .gif |
| `make clean` | Remove generated files |
| `make help` | Show available targets |

---

## Tips for Good Demos

1. **Clear the terminal** before starting
2. **Use a clean directory** with a few example files
3. **Type slowly** for readability (the fake demo handles this)
4. **Show both success and safety** features
5. **Include multiple languages** to show multilingual support
6. **End cleanly** with `/exit`

---

## Generated Files

| File | Description |
|------|-------------|
| `demo/matrixsh-demo.cast` | Asciinema recording |
| `demo/matrixsh-demo.gif` | Converted GIF animation |
| `demo/powershell_demo.txt` | Windows PowerShell transcript |

---

## Embedding in README

### Asciinema Player

```markdown
[![asciicast](https://asciinema.org/a/YOUR_ID.svg)](https://asciinema.org/a/YOUR_ID)
```

### GIF

```markdown
![MatrixShell Demo](demo/matrixsh-demo.gif)
```

### Static Code Block

```markdown
```text
/home/user$ matrixsh
...
```
```

---

## Troubleshooting

### asciinema: command not found

```bash
pipx install asciinema
# or
pip install --user asciinema
```

### agg: command not found

```bash
cargo install agg
```

### Recording shows wrong colors

Try setting `TERM=xterm-256color` before recording:

```bash
TERM=xterm-256color asciinema rec demo.cast
```

### MatrixLLM not running during real demo

Either:
- Start MatrixLLM first: `matrixllm start --auth pairing ...`
- Or let MatrixShell start it: answer "Y" when prompted


