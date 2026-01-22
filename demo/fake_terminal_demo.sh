#!/usr/bin/env bash
# =============================================================================
# MatrixShell Fake Terminal Demo
# =============================================================================
# A "fake typing" demo you can screen-record with any tool.
# It prints a realistic MatrixShell session without needing MatrixLLM running.
#
# Usage:
#   bash demo/fake_terminal_demo.sh
#
# Great for:
#   - Quick screen recordings
#   - README GIF creation
#   - Consistent output across OS
# =============================================================================

set -euo pipefail

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# Typing speed (seconds per character)
TYPING_SPEED=0.03
FAST_SPEED=0.01

type_line() {
    local s="$1"
    local speed="${2:-$TYPING_SPEED}"
    local i
    for ((i=0; i<${#s}; i++)); do
        printf "%s" "${s:$i:1}"
        sleep "$speed"
    done
    printf "\n"
}

type_instant() {
    printf "%s\n" "$1"
}

pause() {
    sleep "${1:-0.8}"
}

clear_screen() {
    clear 2>/dev/null || printf "\033c"
}

# =============================================================================
# Demo Script
# =============================================================================

clear_screen

echo ""
type_instant "${BOLD}MatrixShell Demo${NC}"
type_instant "================"
echo ""
pause 1

# Welcome panel
type_instant "${CYAN}╭────────────────────────────────────────── matrixsh ──────────────────────────────────────────╮${NC}"
type_instant "${CYAN}│${NC} ${BOLD}MatrixShell${NC} (powered by MatrixLLM)                                                        ${CYAN}│${NC}"
type_instant "${CYAN}│${NC} OS: linux  |  Mode: bash                                                                   ${CYAN}│${NC}"
type_instant "${CYAN}│${NC} Gateway: http://localhost:11435/v1                                                         ${CYAN}│${NC}"
type_instant "${CYAN}│${NC} Model: deepseek-r1                                                                         ${CYAN}│${NC}"
type_instant "${CYAN}│${NC}                                                                                            ${CYAN}│${NC}"
type_instant "${CYAN}│${NC} ${BOLD}Tips${NC}                                                                                       ${CYAN}│${NC}"
type_instant "${CYAN}│${NC}  - Type normal commands as usual.                                                          ${CYAN}│${NC}"
type_instant "${CYAN}│${NC}  - If you type natural language OR an unknown command, MatrixShell will ask MatrixLLM.     ${CYAN}│${NC}"
type_instant "${CYAN}│${NC}  - Use /exit to quit.                                                                      ${CYAN}│${NC}"
type_instant "${CYAN}╰──────────────────────────────────────────────────────────────────────────────────────────────╯${NC}"
echo ""
pause 1.5

# Demo 1: Normal command
printf "${GREEN}${BOLD}/home/user/projects$ ${NC}"
type_line "ls" "$FAST_SPEED"
pause 0.3
type_instant "README.md  src/  tests/  requirements.txt  setup.py"
echo ""
pause 1

# Demo 2: Natural language (Italian)
printf "${GREEN}${BOLD}/home/user/projects$ ${NC}"
type_line "come posso cancellare questa cartella"
pause 0.5
echo ""

type_instant "${CYAN}╭─────────────────────────────────────── MatrixLLM ───────────────────────────────────────────╮${NC}"
type_instant "${CYAN}│${NC} Per cancellare la cartella, usa questo comando:                                             ${CYAN}│${NC}"
type_instant "${CYAN}│${NC}                                                                                             ${CYAN}│${NC}"
type_instant "${CYAN}│${NC}     ${BOLD}rm -rf \"old-project\"${NC}                                                                    ${CYAN}│${NC}"
type_instant "${CYAN}│${NC}                                                                                             ${CYAN}│${NC}"
type_instant "${CYAN}│${NC} ${YELLOW}Attenzione: Questo eliminerà tutti i file definitivamente.${NC}                                ${CYAN}│${NC}"
type_instant "${CYAN}╰───────────────────────────────────────────────────────────────────────────────────────────────╯${NC}"
echo ""
type_instant "${BOLD}Suggested command:${NC}"
type_instant "rm -rf \"old-project\""
type_instant "Risk: ${RED}${BOLD}high${NC}"
echo ""
pause 0.5

printf "Execute it? (yes/no) "
type_line "no" "$FAST_SPEED"
type_instant "${CYAN}Cancelled.${NC}"
echo ""
pause 1

# Demo 3: Natural language (English)
printf "${GREEN}${BOLD}/home/user/projects$ ${NC}"
type_line "how can I find the biggest files here"
pause 0.5
echo ""

type_instant "${CYAN}╭─────────────────────────────────────── MatrixLLM ───────────────────────────────────────────╮${NC}"
type_instant "${CYAN}│${NC} To find the biggest files in this directory, use the following command which shows          ${CYAN}│${NC}"
type_instant "${CYAN}│${NC} the top 20 largest files sorted by size:                                                    ${CYAN}│${NC}"
type_instant "${CYAN}╰───────────────────────────────────────────────────────────────────────────────────────────────╯${NC}"
echo ""
type_instant "${BOLD}Suggested command:${NC}"
type_instant "du -ah . | sort -hr | head -n 20"
type_instant "Risk: ${GREEN}${BOLD}low${NC}"
echo ""
pause 0.5

printf "Execute it? (yes/no) "
type_line "yes" "$FAST_SPEED"
pause 0.3
type_instant "1.2G    ./node_modules"
type_instant "450M    ./dist"
type_instant "120M    ./src/assets"
type_instant "45M     ./tests/fixtures"
type_instant "12M     ./README.md"
type_instant "${GREEN}Done.${NC}"
echo ""
pause 1

# Demo 4: Command not found fallback
printf "${GREEN}${BOLD}/home/user/projects$ ${NC}"
type_line "gitstat"
pause 0.3
type_instant "${RED}bash: gitstat: command not found${NC}"
echo ""
pause 0.5

type_instant "${CYAN}╭─────────────────────────────────────── MatrixLLM ───────────────────────────────────────────╮${NC}"
type_instant "${CYAN}│${NC} It looks like you meant 'git status'. This command shows the current state of your         ${CYAN}│${NC}"
type_instant "${CYAN}│${NC} Git repository, including modified files and staging status.                               ${CYAN}│${NC}"
type_instant "${CYAN}╰───────────────────────────────────────────────────────────────────────────────────────────────╯${NC}"
echo ""
type_instant "${BOLD}Suggested command:${NC}"
type_instant "git status"
type_instant "Risk: ${GREEN}${BOLD}low${NC}"
echo ""
pause 0.5

printf "Execute it? (yes/no) "
type_line "yes" "$FAST_SPEED"
pause 0.3
type_instant "On branch main"
type_instant "Your branch is up to date with 'origin/main'."
type_instant ""
type_instant "nothing to commit, working tree clean"
type_instant "${GREEN}Done.${NC}"
echo ""
pause 1

# Demo 5: Safety denylist
printf "${GREEN}${BOLD}/home/user/projects$ ${NC}"
type_line "format my hard drive"
pause 0.5
echo ""

type_instant "${CYAN}╭─────────────────────────────────────── MatrixLLM ───────────────────────────────────────────╮${NC}"
type_instant "${CYAN}│${NC} To format a drive on Linux, you would typically use mkfs. However, this is an extremely    ${CYAN}│${NC}"
type_instant "${CYAN}│${NC} dangerous operation that will permanently destroy all data.                                ${CYAN}│${NC}"
type_instant "${CYAN}╰───────────────────────────────────────────────────────────────────────────────────────────────╯${NC}"
echo ""
type_instant "${BOLD}Suggested command:${NC}"
type_instant "mkfs.ext4 /dev/sda1"
type_instant "Risk: ${RED}${BOLD}high${NC}"
echo ""
pause 0.5

type_instant "${RED}Refusing to execute:${NC} Disk formatting commands are blocked for safety."
type_instant "${YELLOW}You can still copy the command manually if you really intend it.${NC}"
echo ""
pause 1

# Exit
printf "${GREEN}${BOLD}/home/user/projects$ ${NC}"
type_line "/exit" "$FAST_SPEED"
type_instant "${CYAN}Bye.${NC}"
echo ""
pause 0.5

echo ""
type_instant "${DIM}--- End of MatrixShell Demo ---${NC}"
echo ""
