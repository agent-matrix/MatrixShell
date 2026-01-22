#!/usr/bin/env bash
set -euo pipefail

echo "Build helpers:"
echo " - Windows .exe: use scripts/build_exe.ps1"
echo " - Linux packages: packaging/linux/build_linux_packages.sh"
echo " - Homebrew: packaging/homebrew/matrixsh.rb (template)"
echo " - Winget: packaging/winget/manifest.yaml (template)"
