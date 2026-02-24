#!/usr/bin/env bash
# patch_venv.sh — Apply compatibility fixes after `make build`.
#
# Three categories of patches are applied:
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
#
# C) CUSTOM INSTANCE REGISTRATIONS (patches/registry/)
#    Custom or fixed Instance registration modules for tasks that either
#    don't exist in the pip package or need modifications (e.g. non-root
#    test execution, custom parse_log). These are copied into the venv's
#    multi_swe_bench/harness/repos/ tree. Lost after every `uv sync`.
#
#    See docs/LIBUV_EVAL_POSTMORTEM.md for the full issue catalog.

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

# ── C) Custom instance registrations ─────────────────────────────────────────

REGISTRY_DIR="patches/registry"
REPOS_DIR="$SITE_PKG/multi_swe_bench/harness/repos"

if [ -d "$REGISTRY_DIR" ]; then
    INSTALLED=0
    # Walk patches/registry/{lang}/{org}/{repo}.py and copy into venv
    for reg_file in $(find "$REGISTRY_DIR" -name "*.py" -type f); do
        # Strip the patches/registry/ prefix to get relative path
        rel_path="${reg_file#$REGISTRY_DIR/}"
        target="$REPOS_DIR/$rel_path"
        target_dir=$(dirname "$target")

        mkdir -p "$target_dir"

        # Ensure __init__.py exists at every directory level
        current="$REPOS_DIR"
        IFS='/' read -ra parts <<< "$rel_path"
        # Skip the last element (the .py filename)
        for (( i=0; i<${#parts[@]}-1; i++ )); do
            current="$current/${parts[$i]}"
            if [ ! -f "$current/__init__.py" ]; then
                touch "$current/__init__.py"
            fi
        done

        cp "$reg_file" "$target"
        INSTALLED=$((INSTALLED + 1))
        printf "${GREEN}  ✓ Installed custom registry: $rel_path${RESET}\n"
    done

    if [ "$INSTALLED" -eq 0 ]; then
        printf "${YELLOW}  ⚠ No .py files found in $REGISTRY_DIR${RESET}\n"
    fi
else
    printf "${YELLOW}  ⚠ Custom registry dir not found ($REGISTRY_DIR), skipping${RESET}\n"
fi

printf "${GREEN}All patches applied successfully.${RESET}\n"
