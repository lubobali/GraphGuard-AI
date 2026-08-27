# Serving image for GraphGuard-AI.
#
# Built from the committed lockfile, the same one CI and the local toolchain
# use, so the container cannot quietly run a different dependency set from the
# one the results were produced with.
#
# Base dependencies only -- no dev, no gnn. The GNN is the research arm and not
# the served model (PLAN.md R-1), and leaving torch out keeps roughly 1.2GB of
# it out of the image.
FROM python:3.12.14-slim

# uv pinned to the same version as the project toolchain.
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

# wget is not decoration. KubeRay's head readiness probe runs
#   wget -T 2 -q -O- http://localhost:52365/api/local_raylet_healthz
# and python:3.12-slim ships with neither wget nor curl. Without it the probe
# fails forever, the pod never becomes ready, KubeRay refuses to deploy Serve
# because the pod is not ready, and nothing ever converges.
RUN apt-get update \
 && apt-get install -y --no-install-recommends wget \
 && rm -rf /var/lib/apt/lists/*

# The user is created before anything is copied, and owns /app from the start.
# A `chown -R` after the fact would rewrite every file in the venv and add a
# second full copy of it as a new layer -- 1.4GB, measured.
RUN useradd --create-home --uid 10001 serve && mkdir -p /app && chown serve:serve /app

WORKDIR /app
USER serve

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1

# Dependencies first, so a source change does not re-resolve the environment.
COPY --chown=serve:serve pyproject.toml uv.lock README.md ./
COPY --chown=serve:serve src ./src

# UV_NO_CACHE keeps uv's download cache out of the layer. Without it the cache
# alone was 1.2GB of the image.
RUN uv sync --frozen --no-dev --no-editable

# KubeRay launches the Ray head through a login shell, which sources
# /etc/profile and resets PATH -- so the venv on PATH from ENV, and even PATH
# set in the pod spec, are both lost by the time `ray start` runs. Symlinking
# into /usr/local/bin puts the binaries where a login shell already looks,
# which survives however the command is invoked.
USER root
RUN ln -s /app/.venv/bin/ray /usr/local/bin/ray \
 && ln -s /app/.venv/bin/serve /usr/local/bin/serve \
 && ln -s /app/.venv/bin/python /usr/local/bin/gg-python
USER serve

# The trained artifact. Baked in for now so the running version is traceable to
# an image tag; Phase 5's S3 step replaces this with a pull at startup.
COPY --chown=serve:serve models/production ./models/production

ENV PATH="/app/.venv/bin:$PATH" \
    GRAPHGUARD_BUNDLE=/app/models/production \
    GRAPHGUARD_REDIS_URL=redis://10.42.0.1:6380/0

EXPOSE 8000
CMD ["serve", "run", "graphguard.serving.app:app"]
