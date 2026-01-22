#!/usr/bin/env bash
set -euo pipefail

# Build .deb and .rpm using fpm (simple packaging approach)

# Requirements (Ubuntu/Debian):

# sudo apt-get install -y ruby ruby-dev build-essential

# sudo gem install --no-document fpm

#

# Then:

# cd matrixsh_project

# python3 -m venv .venv && source .venv/bin/activate

# pip install -e .

# ./packaging/linux/build_linux_packages.sh

VERSION="0.3.0"
NAME="matrixsh"

rm -rf dist_pkg
mkdir -p dist_pkg/usr/local/bin

# Put an entrypoint script that calls python module from installed env OR ship a single binary later

cat > dist_pkg/usr/local/bin/matrixsh <<'SH'
#!/usr/bin/env bash
python3 -m matrixsh.cli "$@"
SH
chmod +x dist_pkg/usr/local/bin/matrixsh

# Deb

fpm -s dir -t deb -n "$NAME" -v "$VERSION" 
--prefix=/ 
-C dist_pkg 
--description "MatrixShell: AI-augmented shell wrapper powered by MatrixLLM" 
--license "MIT" 
--maintainer "MatrixLLM" 
.

# Rpm

fpm -s dir -t rpm -n "$NAME" -v "$VERSION" 
--prefix=/ 
-C dist_pkg 
--description "MatrixShell: AI-augmented shell wrapper powered by MatrixLLM" 
--license "MIT" 
--maintainer "MatrixLLM" 
.
