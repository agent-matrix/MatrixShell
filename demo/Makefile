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

.PHONY: demo record gif clean help

# Default target
help:
	@echo "MatrixShell Demo Makefile"
	@echo "========================="
	@echo ""
	@echo "Targets:"
	@echo "  make demo     - Run fake terminal demo (no MatrixLLM needed)"
	@echo "  make record   - Record real demo with asciinema"
	@echo "  make gif      - Convert asciinema recording to GIF"
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

# Convert asciinema recording to GIF (requires agg)
gif: matrixsh-demo.cast
	@if command -v agg >/dev/null 2>&1; then \
		echo "Converting to GIF..."; \
		agg matrixsh-demo.cast matrixsh-demo.gif \
			--font-size 14 \
			--font-family "JetBrains Mono,Menlo,Monaco,monospace" \
			--theme monokai; \
		echo "Created: matrixsh-demo.gif"; \
	else \
		echo "Error: agg not found."; \
		echo "Install it with: cargo install agg"; \
		exit 1; \
	fi

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	@rm -f matrixsh-demo.cast matrixsh-demo.gif
	@echo "Done."

# Check that cast file exists for gif target
matrixsh-demo.cast:
	@echo "Error: matrixsh-demo.cast not found."
	@echo "Run 'make record' first to create a recording."
	@exit 1
