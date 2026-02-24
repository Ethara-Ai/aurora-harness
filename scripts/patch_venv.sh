#!/usr/bin/env bash
# patch_venv.sh — Apply compatibility fixes after `make build`.
#
# Two categories of patches are applied:
#
# A) VENDOR PATCHES (patches/ directory)
#    Patches applied to the vendored software-agent-sdk submodule using
#    standard .patch files (industry standard approach for patching
#    third-party dependencies you don't own). Re-applied after every
#    `git submodule update` since the submodule resets to the pinned commit.
#
#    patches/sdk-mac-compat.patch:
#      - build.py: pass --platform to docker buildx in local (--load) mode.
#        On Apple Silicon, omitting --platform defaults to arm64; Multi-SWE-Bench
#        base images are linux/amd64 only, causing container startup failures.
#      - Dockerfile: add --extra boto3 to uv sync. boto3 is an optional
#        dependency required when using AWS Bedrock as the LLM provider.
#        Without it the agent-server crashes on the first LLM call.
#
# B) VENV PATCHES (sed in-place)
#    Bugs in the installed multi-swe-bench package. Lost after every `uv sync`
#    since .venv is not tracked in git.
#
#    Fix 1 — qiskit → Qiskit import case:
#      The package imports from ...python.qiskit (lowercase) but the directory
#      on disk is Qiskit (capitalised). Causes ModuleNotFoundError during
#      evaluation for ALL languages.
#
#    Fix 2 — Docker client timeout 60s → 600s:
#      The default 60s timeout is too short for Docker image builds running
#      under QEMU x86_64 emulation on Apple Silicon.

set -euo pipefail

GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'

# Cross-platform sed in-place: macOS requires '' after -i, Linux doesn't
sed_inplace() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

# ── A) Vendor patches ─────────────────────────────────────────────────────────

SDK_DIR="vendor/software-agent-sdk"
PATCHES_DIR="patches"

if [ -d "$SDK_DIR" ] && [ -d "$PATCHES_DIR" ]; then
    PATCHES_ABS="$(cd "$PATCHES_DIR" && pwd)"
    for patch_file in "$PATCHES_ABS"/*.patch; do
        [ -f "$patch_file" ] || continue
        patch_name=$(basename "$patch_file")
        if git -C "$SDK_DIR" apply --check "$patch_file" 2>/dev/null; then
            # Patch applies cleanly — not yet applied
            git -C "$SDK_DIR" apply "$patch_file"
            printf "${GREEN}  ✓ Applied vendor patch: $patch_name${RESET}\n"
        elif git -C "$SDK_DIR" apply --check -R "$patch_file" 2>/dev/null; then
            # Reverse check succeeds — patch already applied, skip
            printf "${YELLOW}  ⚠ Vendor patch already applied: $patch_name (skipping)${RESET}\n"
        else
            printf "${RED}  ✗ Vendor patch failed to apply: $patch_name${RESET}\n"
            exit 1
        fi
    done
else
    printf "${YELLOW}  ⚠ SDK dir or patches dir not found, skipping vendor patches${RESET}\n"
fi

# ── B) Venv patches ───────────────────────────────────────────────────────────

SITE_PKG=$(ls -d .venv/lib/python*/site-packages 2>/dev/null | head -1)

if [ -z "$SITE_PKG" ]; then
    printf "${RED}Error: .venv not found. Run 'make build' first.${RESET}\n"
    exit 1
fi

# Fix 1: qiskit import case
QISKIT_FILE="$SITE_PKG/multi_swe_bench/harness/repos/python/__init__.py"
if [ -f "$QISKIT_FILE" ]; then
    sed_inplace \
        's|from multi_swe_bench.harness.repos.python.qiskit import \*|from multi_swe_bench.harness.repos.python.Qiskit import *|g' \
        "$QISKIT_FILE"
    printf "${GREEN}  ✓ Fixed qiskit → Qiskit import case${RESET}\n"
else
    printf "${YELLOW}  ⚠ qiskit fix: file not found, skipping${RESET}\n"
fi

# Fix 2: Docker client timeout
DOCKER_UTIL="$SITE_PKG/multi_swe_bench/utils/docker_util.py"
if [ -f "$DOCKER_UTIL" ]; then
    sed_inplace \
        's|docker_client = docker.from_env()|docker_client = docker.from_env(timeout=600)|g' \
        "$DOCKER_UTIL"
    printf "${GREEN}  ✓ Fixed Docker client timeout to 600s${RESET}\n"
else
    printf "${YELLOW}  ⚠ docker_util fix: file not found, skipping${RESET}\n"
fi

printf "${GREEN}All patches applied successfully.${RESET}\n"
