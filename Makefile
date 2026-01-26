# MatrixShell (matrixsh) - Cross-platform Makefile (Windows + macOS + Linux)
# with uv-first installation workflow
#
# Requires:
# - GNU Make (recommended). On Windows: Git Bash / MSYS2 / WSL.
# - Python 3.9+
#
# Philosophy:
# - Prefer `uv` for venv + installs (fast).
# - Fall back to `python -m venv` + pip if uv not available.
#
# Targets:
#   make help
#   make venv             (uv venv / python -m venv)
#   make install          (uv pip install -e . / pip install -e .)
#   make install-dev      (adds dev tools like pyinstaller)
#   make run
#   make build-exe        (Windows PyInstaller onefile exe)
#   make build-linux      (Linux deb/rpm via fpm helper script)
#   make clean / clean-all

.DEFAULT_GOAL := help

# -----------------------------
# OS detection
# -----------------------------
ifeq ($(OS),Windows_NT)
  IS_WINDOWS := 1
else
  IS_WINDOWS := 0
endif

# -----------------------------
# Tools (override via env if you like)
# -----------------------------
UV ?= uv
PYTHON ?= python
PYTHON3 ?= python3
PIPX ?= pipx

# Choose python executable
ifeq ($(IS_WINDOWS),1)
  PY := $(PYTHON)
else
  PY := $(shell command -v $(PYTHON3) >/dev/null 2>&1 && echo $(PYTHON3) || echo $(PYTHON))
endif

# venv layout differs on Windows
VENV_DIR := .venv
ifeq ($(IS_WINDOWS),1)
  VENV_PY := $(VENV_DIR)\Scripts\python.exe
  VENV_PIP := $(VENV_DIR)\Scripts\pip.exe
  VENV_BIN := $(VENV_DIR)\Scripts
  SHELL := cmd.exe
  .SHELLFLAGS := /c
else
  VENV_PY := $(VENV_DIR)/bin/python
  VENV_PIP := $(VENV_DIR)/bin/pip
  VENV_BIN := $(VENV_DIR)/bin
endif

# -----------------------------
# Helpers
# -----------------------------
# Detect uv presence (works in bash; on Windows we run under cmd, so use where)
ifeq ($(IS_WINDOWS),1)
  HAVE_UV := $(shell where $(UV) >NUL 2>&1 && echo 1 || echo 0)
else
  HAVE_UV := $(shell command -v $(UV) >/dev/null 2>&1 && echo 1 || echo 0)
endif

# Pretty output
ifeq ($(IS_WINDOWS),1)
  OK := [OK]
  WARN := [WARN]
else
  OK := \033[32m✓\033[0m
  WARN := \033[33m!\033[0m
endif

# -----------------------------
# Help
# -----------------------------
.PHONY: help
help:
	@echo "MatrixShell (matrixsh) - Makefile (uv-first)"
	@echo ""
	@echo "Usage:"
	@echo "  make <target>"
	@echo ""
	@echo "Core:"
	@echo "  uv-install        Install uv (best effort)."
	@echo "  venv              Create .venv (uv venv preferred)."
	@echo "  install           Install editable into .venv (uv pip preferred)."
	@echo "  install-dev       Install dev tools (pyinstaller/build/twine)."
	@echo "  test              Run pytest test suite."
	@echo "  run               Run matrixsh from .venv."
	@echo ""
	@echo "User install:"
	@echo "  install-cli       pipx install . (end-user)."
	@echo ""
	@echo "Build / Packaging:"
	@echo "  build             Build wheel and sdist (python -m build)."
	@echo "  build-exe         Windows: build dist\\matrixsh.exe using PyInstaller."
	@echo "  build-linux       Linux: build .deb/.rpm using packaging/linux/build_linux_packages.sh (fpm)."
	@echo ""
	@echo "Housekeeping:"
	@echo "  clean             Remove build artifacts."
	@echo "  clean-all         Also remove .venv."
	@echo ""
	@echo "Detected:"
	@echo "  OS: $(if $(filter 1,$(IS_WINDOWS)),Windows,Unix-like)"
	@echo "  Python: $(PY)"
	@echo "  uv available: $(HAVE_UV)"

# -----------------------------
# Install uv (best effort)
# -----------------------------
.PHONY: uv-install
uv-install:
ifeq ($(IS_WINDOWS),1)
	@echo "Installing uv on Windows (best effort)..."
	@echo "If this fails, install uv manually: https://astral.sh/uv"
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" || (echo $(WARN) uv install failed; exit /b 0)
else
	@echo "Installing uv on Unix-like (best effort)..."
	@echo "If this fails, install uv manually: https://astral.sh/uv"
	@curl -LsSf https://astral.sh/uv/install.sh | sh || (echo "$(WARN) uv install failed"; exit 0)
endif
	@echo "$(OK) uv install attempted. Restart your shell if needed."

# -----------------------------
# Virtualenv
# -----------------------------
.PHONY: venv
venv:
ifeq ($(IS_WINDOWS),1)
	@if exist "$(VENV_PY)" (echo $(OK) venv exists) else ( \
		if "$(HAVE_UV)"=="1" ( \
			echo Using uv venv... && \
			$(UV) venv "$(VENV_DIR)" \
		) else ( \
			echo $(WARN) uv not found. Using python -m venv... && \
			$(PY) -m venv "$(VENV_DIR)" \
		) \
	)
	@$(VENV_PY) -m pip install -U pip setuptools wheel
else
	@if [ -x "$(VENV_PY)" ]; then echo "$(OK) venv exists"; else \
		if [ "$(HAVE_UV)" = "1" ]; then \
			echo "Using uv venv..." && \
			$(UV) venv "$(VENV_DIR)"; \
		else \
			echo "$(WARN) uv not found. Using python -m venv..." && \
			$(PY) -m venv "$(VENV_DIR)"; \
		fi; \
	fi
	@$(VENV_PY) -m pip install -U pip setuptools wheel
endif

# -----------------------------
# Install (editable) into venv - uv-first
# -----------------------------
.PHONY: install
install: venv
ifeq ($(IS_WINDOWS),1)
	@echo "Installing into venv (editable) using uv if available..."
	@if "$(HAVE_UV)"=="1" ( \
		$(UV) pip install -e . \
	) else ( \
		$(VENV_PY) -m pip install -e . \
	)
else
	@echo "Installing into venv (editable) using uv if available..."
	@if [ "$(HAVE_UV)" = "1" ]; then \
		$(UV) pip install -e .; \
	else \
		$(VENV_PY) -m pip install -e .; \
	fi
endif
	@echo "$(OK) installed"

# -----------------------------
# Install dev tools (PyInstaller, build, twine) - uv-first
# -----------------------------
.PHONY: install-dev
install-dev: venv
ifeq ($(IS_WINDOWS),1)
	@echo "Installing dev tools into venv..."
	@if "$(HAVE_UV)"=="1" ( \
		$(UV) pip install -U pyinstaller build twine \
	) else ( \
		$(VENV_PY) -m pip install -U pyinstaller build twine \
	)
else
	@echo "Installing dev tools into venv..."
	@if [ "$(HAVE_UV)" = "1" ]; then \
		$(UV) pip install -U pyinstaller build twine; \
	else \
		$(VENV_PY) -m pip install -U pyinstaller build twine; \
	fi
endif
	@echo "$(OK) dev tools installed"

# -----------------------------
# Build wheel and sdist
# -----------------------------
.PHONY: build
build: install-dev
ifeq ($(IS_WINDOWS),1)
	@echo "Building wheel and sdist..."
	@$(VENV_PY) -m build
	@echo $(OK) Built: dist/*.whl dist/*.tar.gz
else
	@echo "Building wheel and sdist..."
	@$(VENV_PY) -m build
	@echo "$(OK) Built: dist/*.whl dist/*.tar.gz"
	@ls -la dist/
endif

# -----------------------------
# Run
# -----------------------------
.PHONY: run
run: install
	@$(VENV_PY) -m matrixsh.cli --help

# -----------------------------
# User installation via pipx (end-user)
# -----------------------------
.PHONY: install-cli
install-cli:
ifeq ($(IS_WINDOWS),1)
	@where $(PIPX) >NUL 2>&1 || (echo $(WARN) pipx not found. Install: python -m pip install --user pipx && exit /b 1)
	@$(PIPX) install . || $(PIPX) install . --force
else
	@command -v $(PIPX) >/dev/null 2>&1 || (echo "$(WARN) pipx not found. Install: python3 -m pip install --user pipx" && exit 1)
	@$(PIPX) install . || $(PIPX) install . --force
endif
	@echo "$(OK) pipx installed. Try: matrixsh install"

# -----------------------------
# Build Windows .exe (PyInstaller)
# -----------------------------
.PHONY: build-exe
build-exe: install-dev
ifeq ($(IS_WINDOWS),1)
	@echo "Building one-file EXE with PyInstaller..."
	@$(VENV_PY) -m PyInstaller --name matrixsh --onefile --console --clean --paths src -m matrixsh.cli
	@echo $(OK) Built: dist\matrixsh.exe
else
	@echo "$(WARN) build-exe is intended to run on Windows."
	@echo "Build on Windows or use CI to produce dist/matrixsh.exe."
endif

# -----------------------------
# Linux packaging (.deb/.rpm) via fpm helper script
# -----------------------------
.PHONY: build-linux
build-linux: install
ifeq ($(IS_WINDOWS),1)
	@echo "$(WARN) build-linux is intended to run on Linux."
else
	@if [ -f packaging/linux/build_linux_packages.sh ]; then \
		echo "Running Linux packaging script..." && \
		bash packaging/linux/build_linux_packages.sh && \
		echo "$(OK) Linux packages built"; \
	else \
		echo "$(WARN) packaging/linux/build_linux_packages.sh not found"; \
		exit 1; \
	fi
endif

# -----------------------------
# Clean
# -----------------------------
# -----------------------------
# Test
# -----------------------------
.PHONY: test
test: install
ifeq ($(IS_WINDOWS),1)
	@echo "Running tests..."
	@if "$(HAVE_UV)"=="1" ( \
		$(UV) pip install -e ".[dev]" && \
		$(VENV_PY) -m pytest tests/ -v \
	) else ( \
		$(VENV_PY) -m pip install -e ".[dev]" && \
		$(VENV_PY) -m pytest tests/ -v \
	)
else
	@echo "Running tests..."
	@if [ "$(HAVE_UV)" = "1" ]; then \
		$(UV) pip install -e ".[dev]"; \
	else \
		$(VENV_PY) -m pip install -e ".[dev]"; \
	fi
	@$(VENV_PY) -m pytest tests/ -v
endif
	@echo "$(OK) tests passed"

# -----------------------------
# Clean
# -----------------------------
.PHONY: clean
clean:
ifeq ($(IS_WINDOWS),1)
	@if exist build (rmdir /S /Q build)
	@if exist dist (rmdir /S /Q dist)
	@for /d %%D in (*.egg-info) do rmdir /S /Q "%%D"
	@if exist __pycache__ (rmdir /S /Q __pycache__)
	@echo $(OK) cleaned
else
	@rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov __pycache__
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(OK) cleaned"
endif

.PHONY: clean-all
clean-all: clean
ifeq ($(IS_WINDOWS),1)
	@if exist $(VENV_DIR) (rmdir /S /Q $(VENV_DIR))
	@echo $(OK) removed .venv
else
	@rm -rf $(VENV_DIR)
	@echo "$(OK) removed .venv"
endif

# -----------------------------
# Demo
# -----------------------------
.PHONY: demo demo-record
demo:
ifeq ($(IS_WINDOWS),1)
	@echo "Running fake terminal demo..."
	@bash demo/fake_terminal_demo.sh
else
	@echo "Running fake terminal demo..."
	@bash demo/fake_terminal_demo.sh
endif

demo-record:
ifeq ($(IS_WINDOWS),1)
	@echo "$(WARN) demo-record requires asciinema (Unix-like systems)"
else
	@bash demo/record_asciinema.sh
endif
