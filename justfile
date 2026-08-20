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

# --- services ---------------------------------------------------------------
# MLflow + its own Postgres. Isolated from LuBot: own compose project, network,
# volumes and ports, all bound to 127.0.0.1, both memory-capped.

ENVFILE := justfile_directory() / ".secrets/mlflow.env"

mlflow-up:
    docker compose --env-file {{ENVFILE}} up -d

mlflow-down:
    docker compose --env-file {{ENVFILE}} down

mlflow-logs:
    docker compose --env-file {{ENVFILE}} logs -f --tail=100

mlflow-status:
    @docker compose --env-file {{ENVFILE}} ps
    @echo "UI: http://127.0.0.1:5010  (localhost only - tunnel over ssh to view)"

# Download the raw dataset. Needs .secrets/kaggle.json.
data-download:
    KAGGLE_CONFIG_DIR={{justfile_directory()}}/.secrets {{justfile_directory()}}/.tools/bin/kaggle \
      datasets download ealtman2019/ibm-transactions-for-anti-money-laundering-aml \
      -f HI-Small_Trans.csv -p data/raw --force
    KAGGLE_CONFIG_DIR={{justfile_directory()}}/.secrets {{justfile_directory()}}/.tools/bin/kaggle \
      datasets download ealtman2019/ibm-transactions-for-anti-money-laundering-aml \
      -f HI-Small_accounts.csv -p data/raw --force
    KAGGLE_CONFIG_DIR={{justfile_directory()}}/.secrets {{justfile_directory()}}/.tools/bin/kaggle \
      datasets download ealtman2019/ibm-transactions-for-anti-money-laundering-aml \
      -f HI-Small_Patterns.txt -p data/raw --force

# Compute the temporal split once and freeze it. Rerunning is safe: it is
# deterministic. Changing it fails split_integrity_check until the recorded
# checksum is updated in the same commit.
freeze-split:
    {{UV}} run python -m graphguard.evaluation.freeze_split

# Train the tabular baseline and score it on validation, with and without the
# suspected generator artifacts.
train-tabular:
    {{UV}} run python -m graphguard.models.train_tabular

# Score the two dumb baselines on validation and record them in MLflow.
baselines:
    {{UV}} run python -m graphguard.evaluation.run_baselines

# Print the dataset's shape, date range and class balance.
data-summary:
    {{UV}} run python -m graphguard.data.summary

# The three leakage-contract guards. Each turns a rule that nobody rereads
# into a build failure.
guards:
    {{UV}} run python scripts/guards/leakage_guard.py
    {{UV}} run python scripts/guards/split_integrity_check.py
    {{UV}} run python scripts/guards/test_set_touch_check.py

# Install the git pre-commit hooks. Run once per clone.
hooks:
    {{PREK}} install

# Run every hook against the whole repo, not just staged files.
hooks-all:
    {{PREK}} run --all-files

# The Phase 0 gate. CI runs exactly this.
check: lint format-check guards test
