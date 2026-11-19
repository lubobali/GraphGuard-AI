# MLflow tracking server (S5b.7: 3.17.2, the same version as the client in uv.lock --
# tests/test_mlflow_version.py fails the build if they ever drift apart).
#
# Built rather than pulled because the official image ships without a PostgreSQL
# driver, and the backend store is Postgres. Supply chain as the serving image (S5b.2):
# digest-pinned base, Debian security updates, and every Python package installed by
# hash from docker/mlflow-requirements.txt (resolved with the 14-day rule; regenerate
# with `just mlflow-requirements`). An experiment log that cannot be reopened next month
# is not a record.
FROM python:3.12.14-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*

COPY docker/mlflow-requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt \
 && pip uninstall -y pip setuptools wheel 2>/dev/null || true

# Run as a non-root user. Nothing in this container needs root.
# The artifact directory must exist and belong to that user BEFORE the volume is
# first mounted: a new named volume copies this ownership (found in S5.6e).
RUN useradd --create-home --uid 10001 mlflow \
 && mkdir -p /mlflow/artifacts \
 && chown -R 10001:10001 /mlflow
USER mlflow

EXPOSE 5000
