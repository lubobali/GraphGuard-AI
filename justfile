# GraphGuard-AI task runner.
#
# SINGLE SOURCE OF TRUTH for how tests and lint are invoked. CI and the local
# loop both call these recipes, so the flags cannot drift apart.
#
# Every command runs through the project's OWN uv and OWN Python under
# .tools/, never the shared ones in /root. Run scripts/bootstrap.sh first.

UV := justfile_directory() / ".tools/bin/uv"
PREK := justfile_directory() / ".tools/bin/prek"

# Keep interpreters inside the repo rather than the shared uv directory.
export UV_PYTHON_INSTALL_DIR := justfile_directory() / ".tools/python"

# xdist settings, shared by every test recipe.
XDIST := "-n 4 --dist=loadgroup"

default:
    @just --list

# Set up from a clean clone. The one command the Phase 0 gate names.
setup:
    ./scripts/bootstrap.sh

# Fast loop: everything except tests marked slow.
test:
    {{UV}} run pytest {{XDIST}} -m "not slow"

# Everything, including slow.
test-all:
    {{UV}} run pytest {{XDIST}}

lint:
    {{UV}} run ruff check .

format:
    {{UV}} run ruff format .

format-check:
    {{UV}} run ruff format --check .

# Prove the toolchain is the pinned one, not a shared binary.
toolchain:
    @echo "uv:     $({{UV}} --version)"
    @echo "python: $({{UV}} run python -c 'import sys; print(sys.version.split()[0])')"

# Install the git pre-commit hooks. Run once per clone.
hooks:
    {{PREK}} install

# Run every hook against the whole repo, not just staged files.
hooks-all:
    {{PREK}} run --all-files

# The Phase 0 gate. CI runs exactly this.
check: lint format-check test
