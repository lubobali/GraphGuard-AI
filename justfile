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

# Optuna search for the tabular baseline. 20 trials, ~13 minutes.
tune-tabular:
    {{UV}} run python -m graphguard.models.tune_tabular

# Train the GNN. --parity-features gives it exactly the columns the tabular
# model got, so the comparison isolates what graph structure adds.
train-gnn:
    {{UV}} run python -m graphguard.graph.run_gnn --epochs 3 --parity-features \
      --hidden 128 --dropout 0.30 --lr 0.005222 --pos-weight 6.338 \
      --max-rows-per-day 120000

# Optuna search for the GNN, same 20-trial budget the baseline received.
tune-gnn:
    {{UV}} run python -m graphguard.graph.tune_gnn

# What a periodically refreshed online store costs, measured not assumed.
measure-staleness:
    {{UV}} run python -m graphguard.serving.measure_staleness

# Train the production model, save the bundle, fill the online store.
build-artifacts:
    {{UV}} run python -m graphguard.serving.build_artifacts

# End-to-end scoring latency against real Redis and the real model.
measure-latency:
    {{UV}} run python -m graphguard.serving.measure_latency

# Start the Ray head node (capped: this box runs LuBot production too).
# Uses the venv binaries directly: launching via `uv run` makes Ray record
# .tools/bin/uv as the interpreter, a relative path its workers cannot find.
ray-up:
    {{justfile_directory()}}/.venv/bin/ray start --head --num-cpus=2 \
      --object-store-memory=200000000 --dashboard-host=127.0.0.1 \
      --dashboard-port=8265 --disable-usage-stats

ray-down:
    {{justfile_directory()}}/.venv/bin/ray stop

# Deploy the scorer. Endpoint at http://127.0.0.1:8000/
serve-up:
    {{justfile_directory()}}/.venv/bin/serve run graphguard.serving.app:app --non-blocking

serve-status:
    {{justfile_directory()}}/.venv/bin/serve status

# Score a sample transaction against the live endpoint.
serve-smoke:
    @curl -s http://127.0.0.1:8000/health
    @echo
    @curl -s -X POST http://127.0.0.1:8000/ -H 'Content-Type: application/json' -d @scripts/sample_request.json
    @echo

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
