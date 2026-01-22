# MatrixShell (matrixsh)

An AI-augmented shell wrapper powered by MatrixLLM.

## Requirements
- Python 3.9+
- MatrixLLM gateway running (default: http://localhost:11435/v1)

## Install (recommended: pipx)

### Windows (PowerShell)
```powershell
python -m pip install --user pipx
python -m pipx ensurepath
pipx install .
````

### macOS / Linux / WSL

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install .
```

## First-time setup (writes config + tests gateway)

```bash
matrixsh install --url http://localhost:11435/v1 --model deepseek-r1
```

## Run

```bash
matrixsh
```

Force shell mode:

```bash
matrixsh --mode cmd
matrixsh --mode powershell
matrixsh --mode bash
```

Streaming mode:

```bash
matrixsh --stream
```

## Env vars

* MATRIXLLM_BASE_URL (default [http://localhost:11435/v1](http://localhost:11435/v1))
* MATRIXLLM_API_KEY
* MATRIXLLM_MODEL
