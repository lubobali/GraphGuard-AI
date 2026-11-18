# MLflow tracking server.
#
# Built rather than pulled because the official image ships without a
# PostgreSQL driver, and the backend store is Postgres. Versions are pinned:
# an experiment log that cannot be reopened next month is not a record.
FROM python:3.12.14-slim

RUN pip install --no-cache-dir \
      mlflow==2.19.0 \
      psycopg2-binary==2.9.10

# Run as a non-root user. Nothing in this container needs root.
# The artifact directory must exist and belong to that user BEFORE the volume is
# first mounted: a new named volume copies this ownership. Without it the volume
# was root-owned and MLflow could not store a single artifact (found in S5.6e;
# every earlier run logged params and metrics only).
RUN useradd --create-home --uid 10001 mlflow \
 && mkdir -p /mlflow/artifacts \
 && chown -R 10001:10001 /mlflow
USER mlflow

EXPOSE 5000
