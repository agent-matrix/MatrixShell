# =============================================================================
# MatrixShell Demo Makefile
# =============================================================================
# Targets for running and recording MatrixShell demos.
#
# Usage:
#   make demo          - Run fake terminal demo (no MatrixLLM needed)
#   make record        - Record real demo with asciinema
#   make gif           - Convert asciinema recording to GIF
#   make clean         - Remove generated files
# =============================================================================

# Optimization settings
GIF_FPS := 10
GIF_SPEED := 2
GIF_THEME := monokai

.PHONY: demo record gif clean help

# Default target
help:
	@echo "MatrixShell Demo Makefile"
	@echo "========================="
	@echo ""
	@echo "Targets:"
	@echo "  make demo     - Run fake terminal demo (no MatrixLLM needed)"
	@echo "  make record   - Record real demo with asciinema"
	@echo "  make gif      - Convert to GIF (Optimized: $(GIF_FPS)fps @ $(GIF_SPEED)x speed)"
	@echo "  make clean    - Remove generated files"
	@echo ""

# Run the fake terminal demo
demo:
	@echo "Running fake terminal demo..."
	@bash fake_terminal_demo.sh

# Record a real demo with asciinema
record:
	@echo "Starting asciinema recording..."
	@bash record_asciinema.sh

# Convert asciinema recording to GIF
# 1. Installs agg (if missing)
# 2. Downloads JetBrains Mono font locally (if missing)
# 3. Renders with optimized FPS and Speed settings
gif: matrixsh-demo.cast
	@echo "Checking for agg (asciinema gif generator)..."
	@if ! command -v agg >/dev/null 2>&1; then \
		echo "⚠️  agg not found."; \
		if command -v cargo >/dev/null 2>&1; then \
			echo "📦 Cargo found. Installing agg automatically from GitHub..."; \
			cargo install --git https://github.com/asciinema/agg; \
		else \
			echo "❌ Error: Neither 'agg' nor 'cargo' (Rust) found."; \
			echo "👉 Please install Rust to auto-fix: https://rustup.rs/"; \
			exit 1; \
		fi \
	fi
	@echo "Checking for local fonts..."
	@mkdir -p .fonts
	@if [ ! -f .fonts/JetBrainsMono-Regular.ttf ]; then \
		echo "⬇️  Downloading JetBrains Mono font for renderer..."; \
		wget -q -O .fonts/JetBrainsMono-Regular.ttf https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf/JetBrainsMono-Regular.ttf; \
	fi
	@echo "🎥 Converting to GIF (FPS Cap: $(GIF_FPS), Speed: $(GIF_SPEED)x)..."
	@# We add ~/.cargo/bin to PATH temporarily and point agg to local fonts
	@PATH="$$HOME/.cargo/bin:$$PATH" agg matrixsh-demo.cast matrixsh-demo.gif \
		--font-dir .fonts \
		--font-family "JetBrains Mono" \
		--font-size 14 \
		--theme $(GIF_THEME) \
		--fps-cap $(GIF_FPS) \
		--speed $(GIF_SPEED)
	@echo "✅ Created: matrixsh-demo.gif"

# Clean generated files and local fonts
clean:
	@echo "Cleaning generated files..."
	@rm -f matrixsh-demo.cast matrixsh-demo.gif
	@rm -rf .fonts
	@echo "Done."

# Check that cast file exists for gif target
matrixsh-demo.cast:
	@echo "❌ Error: matrixsh-demo.cast not found."
	@echo "👉 Run 'make record' first to create a recording."
	@exit 1