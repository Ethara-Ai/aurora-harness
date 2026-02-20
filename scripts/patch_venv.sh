#!/usr/bin/env bash
# patch_venv.sh — Apply compatibility fixes to the installed multi-swe-bench package.
#
# These are bugs in multi-swe-bench that are not yet fixed upstream. Because .venv
# is not tracked in git, these fixes are lost after every `uv sync` and must be
# re-applied. This script is called automatically by `make build` and can also be
# run manually after any dependency update.
#
# Fixes applied:
#   1. qiskit → Qiskit import case: The installed package imports from
#      multi_swe_bench.harness.repos.python.qiskit (lowercase) but the actual
#      directory on disk is Qiskit (capitalised). This causes ModuleNotFoundError
#      during evaluation for ALL languages since Python repos are loaded at module
#      import time.
#
#   2. Docker client timeout 60s → 600s: The default 60s Docker SDK timeout is too
#      short for Docker image builds running under QEMU x86_64 emulation on Apple
#      Silicon, causing evaluation to abort mid-build with a timeout error.

set -euo pipefail

GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'

SITE_PKG=$(ls -d .venv/lib/python*/site-packages 2>/dev/null | head -1)

if [ -z "$SITE_PKG" ]; then
    printf "${RED}Error: .venv not found. Run 'make build' first.${RESET}\n"
    exit 1
fi

# Fix 1: qiskit import case
QISKIT_FILE="$SITE_PKG/multi_swe_bench/harness/repos/python/__init__.py"
if [ -f "$QISKIT_FILE" ]; then
    sed -i '' \
        's|from multi_swe_bench.harness.repos.python.qiskit import \*|from multi_swe_bench.harness.repos.python.Qiskit import *|g' \
        "$QISKIT_FILE"
    printf "${GREEN}  ✓ Fixed qiskit → Qiskit import case${RESET}\n"
else
    printf "${YELLOW}  ⚠ qiskit fix: file not found, skipping${RESET}\n"
fi

# Fix 2: Docker client timeout
DOCKER_UTIL="$SITE_PKG/multi_swe_bench/utils/docker_util.py"
if [ -f "$DOCKER_UTIL" ]; then
    sed -i '' \
        's|docker_client = docker.from_env()|docker_client = docker.from_env(timeout=600)|g' \
        "$DOCKER_UTIL"
    printf "${GREEN}  ✓ Fixed Docker client timeout to 600s${RESET}\n"
else
    printf "${YELLOW}  ⚠ docker_util fix: file not found, skipping${RESET}\n"
fi

printf "${GREEN}Venv patches applied successfully.${RESET}\n"
