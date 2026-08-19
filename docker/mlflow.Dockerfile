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
RUN useradd --create-home --uid 10001 mlflow
USER mlflow

EXPOSE 5000
