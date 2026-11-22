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

# xdist settings, shared by every test recipe (prek and CI both call `just test`).
# 2 workers, not 4: every worker imports every test module (torch + torch_geometric
# alone ~300 MB), and with 4 the suite peaked at 2.25 GB -- over the CI job's 2 GB cap,
# which OOM-killed workers on 55d29ad. Measured 2026-11-18: -n 4 2,250 MB / 26 s,
# -n 3 1,715 MB / 29 s, -n 2 1,195 MB / 34 s.
XDIST := "-n 2 --dist=loadgroup"

IMAGE_TAG := "0.1.13"

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
    {{UV}} run --no-sync python -m graphguard.ops.jobs run build-artifacts

# CSV -> bronze -> silver (+ sealed) -> gold, as new Iceberg snapshots (S5.6a).
lakehouse-build:
    {{UV}} run --no-sync python -m graphguard.ops.jobs run lakehouse-build

# --- the lakehouse catalog: Lakekeeper (S5.6c) --------------------------------
# Start only Lakekeeper (migrate first). --no-deps: never restarts MLflow or Redis.
# The catalog and what it needs (S5.6c-d): OpenFGA (grants), Dex (logins), Lakekeeper.
# --no-deps everywhere: never restarts MLflow, its Postgres or Redis.
lakekeeper-up:
    docker compose --env-file {{ENVFILE}} up --no-deps openfga-migrate
    docker compose --env-file {{ENVFILE}} up -d --no-deps --wait openfga dex
    docker compose --env-file {{ENVFILE}} up --no-deps lakekeeper-migrate
    docker compose --env-file {{ENVFILE}} up -d --no-deps --wait lakekeeper

lakekeeper-down:
    docker compose --env-file {{ENVFILE}} stop lakekeeper dex openfga

# Generate any missing identity/service secrets in .secrets/ (600). Never overwrites.
identity-secrets:
    {{UV}} run python -m graphguard.lakehouse.lakekeeper secrets

# Bootstrap (as admin), warehouse, namespaces, register missing tables, apply the
# access policy (governance.py). Idempotent.
lakekeeper-init:
    {{UV}} run python -m graphguard.lakehouse.lakekeeper

# Save every table's metadata location + snapshot id (the catalog's rollback point).
lakekeeper-export:
    {{UV}} run python -m graphguard.lakehouse.lakekeeper export

# Exit 1 unless Lakekeeper, Dex and OpenFGA are all healthy.
lakekeeper-status:
    @docker stats --no-stream --format '{{{{.Name}}: {{{{.MemUsage}}' graphguard-lakekeeper graphguard-dex graphguard-openfga
    @for c in graphguard-lakekeeper graphguard-dex graphguard-openfga; do h=$(docker inspect -f '{{{{.State.Health.Status}}' $c 2>/dev/null); echo "$c: ${h:-missing}"; [ "$h" = healthy ] || { echo "UNHEALTHY: $c" >&2; exit 1; }; done
    @curl -sf http://127.0.0.1:8181/health > /dev/null && echo "lakekeeper health endpoint: ok" || (echo "LAKEKEEPER UNHEALTHY" >&2; exit 1)

# Ad-hoc SQL over the lakehouse with DuckDB (read-only views, capped at 512MB).
#   just sql "select count(*) from silver_transactions"
sql query="":
    {{UV}} run --no-sync python -m graphguard.ops.jobs run sql "{{query}}"

# Fill Redis from gold.account_features_asof. No retraining. In place: the store
# is never empty mid-reload.
store-load:
    {{UV}} run --no-sync python -m graphguard.ops.jobs run store-load

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

# --- kubernetes -------------------------------------------------------------
# Build the serving image and import it straight into k3s containerd. No
# registry: this is a single node, and pushing 2.3GB to a registry to pull it
# back onto the same disk would be theatre.
#
# The import is PINNED. With no registry, an unpinned image is one disk-full
# day from deletion by kubelet's image GC, after which IfNotPresent has nowhere
# to pull from. That happened once and the scorer was down 18 days (S5.2).
image-build:
    docker build -t graphguard/serving:{{IMAGE_TAG}} .
    just image-import

# Import the existing Docker image into k3s and pin it. No rebuild.
image-import:
    docker save graphguard/serving:{{IMAGE_TAG}} | k3s ctr images import -
    k3s ctr -n k8s.io images label docker.io/graphguard/serving:{{IMAGE_TAG}} io.cri-containerd.pinned=pinned

# S7.0: keep the running scorer image + one rollback; remove our older tags from k3s and
# Docker (dry run first: `{{UV}} run python -m graphguard.ops.images`).
image-prune:
    {{UV}} run python -m graphguard.ops.images --apply

k8s-deploy:
    k3s kubectl apply -f k8s/namespace.yaml
    k3s kubectl apply -f k8s/networkpolicy.yaml
    k3s kubectl apply -f k8s/rayservice.yaml

k8s-status:
    @k3s kubectl get rayservice -n graphguard
    @k3s kubectl get pods -n graphguard
    @just k8s-check

# Exit 1, loudly, if any scorer pod is not ready or the image is missing or
# unpinned. Safe to run from cron.
k8s-check:
    @{{UV}} run python -m graphguard.ops.k8s_health docker.io/graphguard/serving:{{IMAGE_TAG}}

# Score a sample transaction through the cluster service.
k8s-smoke:
    @k3s kubectl exec -n graphguard $(k3s kubectl get pods -n graphguard --no-headers | awk '{print $1}' | head -1) -- \
      bash -lc 'wget -q -O- http://graphguard-scorer-serve-svc:8000/health'
    @echo

k8s-logs:
    k3s kubectl logs -n graphguard -l ray.io/node-type=head --tail=50

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

# --- S5.6e: lineage, Feast (measured, isolated), worksheets -------------------

# The lineage graph: newest run per job, with the table snapshots it read and wrote.
lineage:
    {{UV}} run python -m graphguard.lakehouse.lineage_events

# Feast lives in its own uv project (featurestore/), never in the main lock.
feast-sync:
    cd featurestore && UV_PYTHON_INSTALL_DIR={{justfile_directory()}}/.tools/python {{UV}} sync -q --group dev

# Materialise gold into Feast's SQLite online store and measure it. Never touches
# the live Redis. Capped at 4.5 GB: it peaked at 3.96 GB (2026-11-18) -- don't run it
# while MLflow or a build is busy.
feast-trial: feast-sync
    systemd-run --scope -q -p MemoryMax=4500M -p MemorySwapMax=0 featurestore/.venv/bin/python featurestore/run.py

# Feast's values vs the live store, every account (read-only).
feast-parity:
    {{UV}} run python -m graphguard.lakehouse.feast_parity

# Feast's own tests (the point-in-time tie characterisation), in Feast's environment.
feast-test: feast-sync
    cd featurestore && .venv/bin/python -m pytest -q -p no:cacheprovider tests

# A marimo worksheet over the lakehouse, as `reader` (no test window). 127.0.0.1 only,
# token in the printed URL, capped at 1 GB (headless run peaked at 591 MB). Not a
# service: Ctrl-C stops it. From a laptop: ssh -L 2718:127.0.0.1:2718 <box>.
notebook:
    {{UV}} run --no-sync python -m graphguard.ops.jobs run notebook

# --- S5b.1: Redis users ---------------------------------------------------------
# Passwords (once, never rotated by accident) + the ACL file Redis loads at start.
# After changing users: run this, then `docker compose ... restart redis` and
# `just store-load` (Redis keeps nothing on disk).
redis-secrets:
    {{UV}} run python -m graphguard.serving.redis_acl

# The scorer's Redis URL as a Kubernetes Secret, piped on stdin (never on a command line).
k8s-redis-secret:
    {{UV}} run python -m graphguard.serving.redis_acl k8s-secret | k3s kubectl apply -f -

# Postgres access rules -> docker/postgres/pg_hba.conf (no secrets; committed). After a
# change: `docker compose --env-file .secrets/mlflow.env restart mlflow-db`.
pg-access:
    {{UV}} run python -m graphguard.ops.pg_access

# --- S5b.2: CI ------------------------------------------------------------------
# The CI job image (docker/ci.Dockerfile). After a rebuild with a new tag, update
# runner/config.yml's label and tests/test_ci_supply_chain.py, then restart the runner.
ci-image:
    docker build -t graphguard/ci:1 -f docker/ci.Dockerfile docker/

# The isolation probe, locally, exactly as a CI job runs it.
ci-probe:
    docker network create gg-probe-net >/dev/null
    -docker run --rm --network gg-probe-net --memory 256m --pids-limit 512 --cap-drop ALL --security-opt no-new-privileges -v {{justfile_directory()}}/scripts/ci:/p:ro graphguard/ci:1 bash /p/isolation-probe.sh
    docker network rm gg-probe-net >/dev/null

# --- S5b.2: secrets and dependencies ------------------------------------------
# Staged changes only (the pre-commit hook). Redacted: a finding never prints the secret.
secrets-staged:
    {{justfile_directory()}}/.tools/bin/betterleaks git . --staged --pre-commit --redact --no-banner

# Every commit on every branch (CI, ~1 s). .betterleaks-baseline.json lists accepted
# historical findings, each one reviewed (today: one deliberately wrong test password).
secrets-history:
    {{justfile_directory()}}/.tools/bin/betterleaks git . --log-opts="--all" --redact --no-banner --baseline-path .betterleaks-baseline.json

# Lockfiles current (main + the isolated Feast project) and no known vulnerability in
# either (OSV database). A new advisory fails the build; to accept one, add it to
# osv-scanner.toml with the reason.
deps-check:
    {{UV}} lock --check
    cd featurestore && UV_PYTHON_INSTALL_DIR={{justfile_directory()}}/.tools/python {{UV}} lock --check
    {{justfile_directory()}}/.tools/bin/osv-scanner scan source --lockfile uv.lock --lockfile featurestore/uv.lock

# Every CI step on the committed HEAD, inside the real job sandbox (graphguard/ci:1, own
# network, no capabilities, no-new-privileges, 2 GB). Use this, not a host-side copy,
# before pushing CI changes: a host copy runs with root powers and hides failures (S5b.2:
# `tar` needing CAP_CHOWN passed on the host and failed in CI).
ci-sandbox:
    #!/usr/bin/env bash
    set -euo pipefail
    d=$(mktemp -d); trap 'rm -rf "$d"; docker network rm gg-sandbox-net >/dev/null 2>&1 || true' EXIT
    git clone -q {{justfile_directory()}} "$d/repo"
    docker network create gg-sandbox-net >/dev/null
    docker run --rm --network gg-sandbox-net --memory 2g --memory-swap 2g --cpus 2 --pids-limit 512 \
      --cap-drop ALL --security-opt no-new-privileges \
      -e GRAPHGUARD_SKIP_REDIS_TESTS=1 -e GRAPHGUARD_SKIP_LAKEKEEPER_TESTS=1 \
      -v "$d/repo":/w -w /w graphguard/ci:1 bash -c '
        git config --global --add safe.directory /w
        set -e
        bash scripts/ci/isolation-probe.sh
        ./scripts/bootstrap.sh > /tmp/boot.log 2>&1 || { tail -20 /tmp/boot.log; exit 1; }
        for r in toolchain lint format-check guards secrets-history deps-check test startup-check; do
          echo "== $r"; ./.tools/bin/just $r
        done'

# Wait for CI on a commit (default HEAD); exit 0 green, 1 red. Read-only Forgejo token.
ci-wait *args:
    {{UV}} run python -m graphguard.ops.ci_status wait {{args}}

# --- S5b.3: backups ------------------------------------------------------------
backup:
    {{UV}} run python -m graphguard.ops.backup backup

restore-check:
    {{UV}} run python -m graphguard.ops.backup restore-check

# Exit 1 if the last backup is older than 2 days, the last drill older than 8, or either failed.
backup-status:
    {{UV}} run python -m graphguard.ops.backup status

# Install/refresh the two systemd timers from systemd/ (a system-wide install, approved in S5b.3).
backup-install:
    mkdir -p {{justfile_directory()}}/.tools/restic-cache {{justfile_directory()}}/.tools/uv-cache-backup {{justfile_directory()}}/private/backups
    install -m 644 systemd/graphguard-backup.service systemd/graphguard-backup.timer systemd/graphguard-restore-check.service systemd/graphguard-restore-check.timer /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now graphguard-backup.timer graphguard-restore-check.timer
    systemctl list-timers 'graphguard-*' --no-pager

# --- S5b.5: one user per job ---------------------------------------------------
# The jobs above run as gg-builder / gg-trainer / gg-reader (graphguard.ops.jobs).
job-users-install:
    install -d -m 755 /etc/sysusers.d
    install -m 644 systemd/graphguard-sysusers.conf /etc/sysusers.d/graphguard.conf
    systemd-sysusers /etc/sysusers.d/graphguard.conf
    chgrp -R gg-trainer models/production && chmod 2775 models/production
    chgrp -R gg-jobs lakehouse/lineage notebooks && chmod 2775 lakehouse/lineage notebooks
    mkdir -p lakehouse/tmp && chgrp gg-builder lakehouse/tmp && chmod 2770 lakehouse/tmp

# --- S5b.6: secrets -------------------------------------------------------------
# Exit 1 if a secret is overdue, untracked, missing, or has the wrong mode/owner.
secrets-status:
    {{UV}} run python -m graphguard.ops.secrets_registry status

# Type a console key into the box (hidden input). Never paste keys into chat.
secret-set name:
    {{UV}} run python -m graphguard.ops.secrets_registry set {{name}}

# Rotate one Postgres role: mlflow_app | lakekeeper | dex | openfga | lakehouse | superuser
rotate-pg role:
    {{UV}} run python -m graphguard.ops.rotate pg {{role}}

rotate-identities:
    {{UV}} run python -m graphguard.ops.rotate identities

rotate-openfga:
    {{UV}} run python -m graphguard.ops.rotate openfga

# Two short Redis restarts + refills; the scorer rolls with zero downtime in between.
rotate-redis:
    {{UV}} run python -m graphguard.ops.rotate redis

# --- S5.7: the model on S3 ------------------------------------------------------
# CI's startup stage: import the app, load the model through the S3 path, score once.
startup-check:
    {{UV}} run --no-sync pytest -q -n 0 -p no:cacheprovider tests/serving/test_startup.py
# Publish models/production as an immutable, content-addressed version; prints the two
# lines to pin in k8s/rayservice.yaml. Same bytes again = no-op.
model-publish:
    {{UV}} run --no-sync python -m graphguard.serving.model_store publish

# The scorer's read-only S3 key as a Kubernetes Secret, piped on stdin (never argv).
k8s-model-secret:
    {{UV}} run --no-sync python -m graphguard.serving.model_k8s secret | k3s kubectl apply -f -

# The scorer's egress to S3: regenerate from AWS's published address ranges.
k8s-s3-egress:
    {{UV}} run --no-sync python -m graphguard.serving.model_k8s egress

# --- S5b.7: MLflow 3 ------------------------------------------------------------
# Rehearse an MLflow server upgrade on a restored backup (nothing live touched).
mlflow-rehearse new="graphguard/mlflow:3.17.2" old="graphguard/mlflow:2.19.0":
    {{UV}} run --no-sync python -m graphguard.ops.mlflow_upgrade rehearse {{new}} {{old}}

# The login: users, grants, auth database (idempotent).
mlflow-auth-setup:
    {{UV}} run --no-sync python -m graphguard.ops.mlflow_auth setup

rotate-mlflow-users:
    {{UV}} run --no-sync python -m graphguard.ops.mlflow_auth rotate

# Lubo's MLflow UI password -- run it in YOUR terminal, never paste it into chat.
mlflow-admin-password:
    @{{UV}} run --no-sync python -m graphguard.ops.mlflow_auth admin-password

# Server requirements with hashes, 14-day rule (then rebuild the image).
mlflow-requirements version:
    printf 'mlflow[auth]=={{version}}\npsycopg2-binary\n' > /tmp/gg-mlflow-req.in
    {{UV}} pip compile /tmp/gg-mlflow-req.in --python-version 3.12 --python-platform x86_64-manylinux_2_28 --exclude-newer "$(date -u -d '14 days ago' +%Y-%m-%dT00:00:00Z)" --generate-hashes --no-header --quiet -o docker/mlflow-requirements.txt

# --- S5b.4: the front door ------------------------------------------------------
# Print the commands `edge-apply` would run (nothing changes).
edge-dry-run:
    {{UV}} run python -m graphguard.ops.edge dry-run

# Apply the guard with a 5-minute automatic undo; `just edge-confirm` keeps it.
edge-apply:
    systemd-run --unit=graphguard-edge-undo --on-active=5min --working-directory={{justfile_directory()}} {{justfile_directory()}}/.tools/bin/uv run --no-sync python -m graphguard.ops.edge remove
    {{UV}} run python -m graphguard.ops.edge apply
    @echo "auto-undo in 5 minutes unless: just edge-confirm"

edge-confirm:
    systemctl stop graphguard-edge-undo.timer
    @echo "kept"

edge-remove:
    {{UV}} run python -m graphguard.ops.edge remove

# Exit 1 if the last check failed or is older than 2 days, or the guard is missing.
edge-status:
    {{UV}} run python -m graphguard.ops.edge status

edge-check:
    {{UV}} run python -m graphguard.ops.edge check

# Accept today's cloud rules and public listeners as the baseline (private/edge/).
edge-baseline:
    {{UV}} run python -m graphguard.ops.edge baseline

# Every health check in one go (backups, edge, secrets, alert, k3s); exit 1 if any fails.
health:
    #!/usr/bin/env bash
    fail=0
    for r in backup-status edge-status secrets-status alert-status k8s-check; do
      echo "== $r"; just "$r" || fail=1
    done
    exit $fail

# --- Kafka (S6.4): one broker, SCRAM logins, deny by default --------------------------
KAFKA_COMPOSE := "docker compose --env-file .secrets/mlflow.env"

# Passwords + cluster id, once (never rotates an existing one).
kafka-secrets:
    {{UV}} run python -m graphguard.stream.kafka_admin secrets

# First start only: the data dir (uid 10380, 700) and the KRaft storage format.
kafka-init: kafka-secrets
    mkdir -p {{justfile_directory()}}/kafka-data
    chown 10380:10380 {{justfile_directory()}}/kafka-data
    chmod 700 {{justfile_directory()}}/kafka-data
    {{KAFKA_COMPOSE}} run --rm --no-deps -e KAFKA_HEAP_OPTS=-Xmx128m --entrypoint /opt/kafka/bin/kafka-storage.sh kafka format --standalone -t $({{UV}} run python -m graphguard.stream.kafka_admin cluster-id) -c /etc/kafka/server.properties

kafka-up:
    {{KAFKA_COMPOSE}} up -d --no-deps kafka

kafka-down:
    {{KAFKA_COMPOSE}} stop kafka

# The admin login (once, after the first start), then logins, topics and ACLs (idempotent).
kafka-bootstrap:
    {{UV}} run python -m graphguard.stream.kafka_admin bootstrap

kafka-setup:
    {{UV}} run python -m graphguard.stream.kafka_admin setup

# Replay the validation window into Kafka as user gg-reader, e.g.
#   just replay --run demo --speed 600        just replay --run chaos --speed max --faults chaos
replay *args:
    mkdir -p {{justfile_directory()}}/stream-runs && chgrp gg-jobs {{justfile_directory()}}/stream-runs && chmod 2770 {{justfile_directory()}}/stream-runs
    {{UV}} run --no-sync python -m graphguard.ops.jobs run replay {{args}}

# The consumer pod (S6.6): its Secret on stdin, then the Deployment + its egress policies.
k8s-stream-secret:
    {{UV}} run python -m graphguard.stream.k8s secret | k3s kubectl apply -f -

k8s-consumer-deploy:
    k3s kubectl apply -f k8s/consumer.yaml -f k8s/networkpolicy-s3-consumer.yaml

# The shadow pod (S6.10): its Secret, then its Deployment + egress policies.
k8s-shadow-deploy:
    {{UV}} run python -m graphguard.stream.k8s shadow-secret | k3s kubectl apply -f -
    k3s kubectl apply -f k8s/shadow.yaml -f k8s/networkpolicy-s3-shadow.yaml

shadow-report:
    {{UV}} run python -m graphguard.stream.shadow report

consumer-logs:
    k3s kubectl logs -n graphguard deploy/graphguard-consumer --tail=50

# Reset the stream to the start: empty the topics and the decision tables, reload Redis.
# S7.1: the investigator demo's own database (roles + tables), then its data from the
# stream's validation decisions (refuses an incomplete stream). Stream resets never touch it.
demo-setup:
    {{UV}} run python -m graphguard.ops.pg_access
    {{UV}} run python -m graphguard.demo.db setup

demo-build:
    systemd-run --scope --quiet -p MemoryMax=2560M {{UV}} run python -m graphguard.demo.build

# S7.6: the demo's read API (127.0.0.1:8130; reach it over the ssh tunnel).
# --env-file + --no-deps: without the env file compose sees a "changed" Postgres and
# recreates it (it happened once, 2026-11-22: ~1 min of database downtime).
demo-api-up:
    docker compose --env-file {{ENVFILE}} up -d --no-deps --wait demo-api

demo-api-down:
    docker compose --env-file {{ENVFILE}} stop demo-api

demo-api-logs:
    docker logs --tail 100 graphguard-demo-api

stream-reset:
    {{UV}} run python -c "from graphguard.stream import e2e; e2e.reset()"

# New passwords for every Kafka login, proven, rolled back on failure (S5b.6 pattern).
rotate-kafka:
    {{UV}} run python -m graphguard.stream.kafka_admin rotate

kafka-status:
    @docker ps --filter name=graphguard-kafka --format '{{{{.Names}} {{{{.Status}}'
    @docker stats --no-stream --format '{{{{.Name}} {{{{.MemUsage}}' graphguard-kafka
    {{UV}} run python -m graphguard.stream.kafka_admin status

# --- Scorer alert (S6.1): email on state change only -----------------------------
# Exit 1 if the alert check is stale, its mail is failing, or the scorer is broken.
alert-status:
    {{UV}} run python -m graphguard.ops.alert status

# One check now (what the 5-minute timer runs).
alert-check:
    {{UV}} run python -m graphguard.ops.alert check

# Two real emails marked DRILL ("down", "recovered"). Never touches the scorer.
alert-drill:
    {{UV}} run python -m graphguard.ops.alert drill

# Silence emails during planned work, e.g. `just alert-pause 2h` (state is still tracked).
alert-pause duration:
    {{UV}} run python -m graphguard.ops.alert pause {{duration}}

alert-resume:
    {{UV}} run python -m graphguard.ops.alert resume

alert-install:
    mkdir -p {{justfile_directory()}}/private/alerts {{justfile_directory()}}/.tools/uv-cache-backup
    chmod 700 {{justfile_directory()}}/private/alerts
    install -m 644 systemd/graphguard-alert.service systemd/graphguard-alert.timer /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now graphguard-alert.timer

edge-install:
    mkdir -p {{justfile_directory()}}/private/edge {{justfile_directory()}}/.tools/uv-cache-backup
    chmod 700 {{justfile_directory()}}/private/edge
    install -m 644 systemd/graphguard-edge.service systemd/graphguard-edge-check.service systemd/graphguard-edge-check.timer /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable graphguard-edge.service
    systemctl enable --now graphguard-edge-check.timer
