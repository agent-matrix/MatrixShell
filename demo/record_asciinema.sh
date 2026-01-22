#!/usr/bin/env bash
# =============================================================================
# MatrixShell Asciinema Recording Script
# =============================================================================
# Record a real demo with asciinema for embedding in README or sharing.
#
# Requirements:
#   - asciinema installed (pipx install asciinema)
#   - matrixsh installed
#   - MatrixLLM running (or will be started by matrixsh)
#
# Usage:
#   bash demo/record_asciinema.sh
#
# Output:
#   demo/matrixsh-demo.cast
#
# To play back:
#   asciinema play demo/matrixsh-demo.cast
#
# To upload to asciinema.org:
#   asciinema upload demo/matrixsh-demo.cast
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="${SCRIPT_DIR}/matrixsh-demo.cast"

echo "=============================================="
echo "  MatrixShell Asciinema Recording"
echo "=============================================="
echo ""

# Check for asciinema
if ! command -v asciinema >/dev/null 2>&1; then
    echo "Error: asciinema not found."
    echo ""
    echo "Install it with:"
    echo "  pipx install asciinema"
    echo "  or: sudo apt-get install asciinema"
    echo "  or: brew install asciinema"
    exit 1
fi

# Check for matrixsh
if ! command -v matrixsh >/dev/null 2>&1; then
    echo "Warning: matrixsh not found in PATH."
    echo "Make sure it's installed: pip install -e ."
    echo ""
fi

echo "Output file: ${OUTPUT_FILE}"
echo ""
echo "Instructions:"
echo "  1. Recording will start in a new shell"
echo "  2. Run: matrixsh"
echo "  3. Try some commands:"
echo "     - Normal: ls, git status"
echo "     - Natural language: 'how do I find large files'"
echo "     - Italian: 'come posso vedere i processi'"
echo "  4. Type /exit to quit MatrixShell"
echo "  5. Type 'exit' to end recording"
echo ""
echo "Press Enter to start recording..."
read -r

echo "Starting recording..."
echo ""

asciinema rec \
    --title "MatrixShell Demo" \
    --idle-time-limit 2 \
    "${OUTPUT_FILE}"

echo ""
echo "=============================================="
echo "Recording saved to: ${OUTPUT_FILE}"
echo ""
echo "To play back:"
echo "  asciinema play ${OUTPUT_FILE}"
echo ""
echo "To upload to asciinema.org:"
echo "  asciinema upload ${OUTPUT_FILE}"
echo ""
echo "To convert to GIF (requires agg):"
echo "  agg ${OUTPUT_FILE} demo/matrixsh-demo.gif"
echo "=============================================="
