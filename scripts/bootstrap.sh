#!/usr/bin/env bash
# GraphGuard-AI toolchain bootstrap.
#
# The project brings its own uv and its own Python, both pinned, installed
# inside the repo under .tools/. Nothing shared with LuBot, with root's
# ~/.local/bin, or with any other project on this box. The same script runs
# locally and in CI, so both get a byte-identical toolchain.
set -euo pipefail

UV_VERSION="0.12.5"
JUST_VERSION="1.58.0"
PREK_VERSION="0.2.9"
KAGGLE_VERSION="1.7.4.5"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="$REPO_ROOT/.tools"
BIN_DIR="$TOOLS_DIR/bin"

mkdir -p "$BIN_DIR"

# --- uv, pinned ------------------------------------------------------------
current=""
if [ -x "$BIN_DIR/uv" ]; then
  current="$("$BIN_DIR/uv" --version 2>/dev/null | awk '{print $2}')"
fi

if [ "$current" != "$UV_VERSION" ]; then
  echo "installing uv $UV_VERSION into .tools/bin"
  curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" \
    | UV_INSTALL_DIR="$BIN_DIR" INSTALLER_NO_MODIFY_PATH=1 sh >/dev/null
else
  echo "uv $UV_VERSION already present"
fi

# --- Python + dependencies -------------------------------------------------
# UV_PYTHON_INSTALL_DIR keeps the interpreter inside the repo rather than in
# the shared ~/.local/share/uv directory.
export UV_PYTHON_INSTALL_DIR="$TOOLS_DIR/python"

cd "$REPO_ROOT"
"$BIN_DIR/uv" python install
"$BIN_DIR/uv" sync --extra dev --extra gnn --locked

# --- just, pinned ----------------------------------------------------------
# Installed with the project's own uv, into the project's own bin dir.
if [ "$("$BIN_DIR/just" --version 2>/dev/null | awk '{print $2}')" != "$JUST_VERSION" ]; then
  echo "installing just $JUST_VERSION into .tools/bin"
  UV_TOOL_BIN_DIR="$BIN_DIR" UV_TOOL_DIR="$TOOLS_DIR/uv-tools" \
    "$BIN_DIR/uv" tool install --force "rust-just==$JUST_VERSION" >/dev/null
fi

# --- prek, pinned ----------------------------------------------------------
# pre-commit hook runner. Pinned so a hook cannot behave differently on two
# machines.
if [ "$("$BIN_DIR/prek" --version 2>/dev/null | awk '{print $2}')" != "$PREK_VERSION" ]; then
  echo "installing prek $PREK_VERSION into .tools/bin"
  UV_TOOL_BIN_DIR="$BIN_DIR" UV_TOOL_DIR="$TOOLS_DIR/uv-tools" \
    "$BIN_DIR/uv" tool install --force "prek==$PREK_VERSION" >/dev/null
fi

# --- kaggle CLI, pinned ----------------------------------------------------
# Used once, to fetch the dataset. Project-local like everything else.
if [ "$("$BIN_DIR/kaggle" --version 2>/dev/null | awk '{print $3}')" != "$KAGGLE_VERSION" ]; then
  echo "installing kaggle $KAGGLE_VERSION into .tools/bin"
  UV_TOOL_BIN_DIR="$BIN_DIR" UV_TOOL_DIR="$TOOLS_DIR/uv-tools" \
    "$BIN_DIR/uv" tool install --force "kaggle==$KAGGLE_VERSION" >/dev/null
fi

echo
echo "toolchain ready:"
echo "  uv:     $("$BIN_DIR/uv" --version)"
echo "  just:   $("$BIN_DIR/just" --version)"
echo "  prek:   $("$BIN_DIR/prek" --version)"
echo "  python: $("$BIN_DIR/uv" run python -c 'import sys; print(sys.version.split()[0])')"
