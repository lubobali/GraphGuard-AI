# GraphGuard-AI task runner.
#
# SINGLE SOURCE OF TRUTH for how tests and lint are invoked.
# prek hooks and Forgejo CI both call these recipes rather than repeating the
# flags. Drift between the two is a known failure mode from LuBot, and this is
# the structural fix: there is only one place the flags exist.

# xdist settings, shared by every test recipe.
# loadgroup keeps tests marked with the same xdist_group on one worker.
XDIST := "-n 4 --dist=loadgroup"

default:
    @just --list

# Set up from a clean clone. The one command the Phase 0 gate names.
setup:
    uv sync --extra dev

# Fast loop: everything except tests marked slow.
test:
    uv run pytest {{XDIST}} -m "not slow"

# Everything, including slow.
test-all:
    uv run pytest {{XDIST}}

lint:
    uv run ruff check .

format:
    uv run ruff format .

format-check:
    uv run ruff format --check .

# The Phase 0 gate. CI runs exactly this.
check: lint format-check test
