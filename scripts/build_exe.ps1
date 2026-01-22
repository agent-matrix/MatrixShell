
# Build a standalone matrixsh.exe using PyInstaller

# Run in PowerShell:

# cd matrixsh_project

# python -m venv .venv

# ..venv\Scripts\Activate.ps1

# pip install -U pip

# pip install -e .

# pip install pyinstaller

# .\scripts\build_exe.ps1

$ErrorActionPreference = "Stop"

pyinstaller `  --name matrixsh`
--onefile `  --console`
--clean `  --paths src`
-m matrixsh.cli

Write-Host "Built: dist\matrixsh.exe"
