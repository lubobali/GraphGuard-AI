# GraphGuard's CI job image (S5b.2). Built locally, never pushed.
#
# The Forgejo runner starts every CI job in this image. git, curl and CA certificates
# are baked in, so a job never runs apt-get -- which is what lets the job container
# start with --cap-drop=ALL and no-new-privileges (apt needs root powers). It also
# saves ~7 s per job. Node stays (actions/checkout is a Node action): 22, the supported
# LTS -- Node 20 reached end-of-life in April 2026.
#
# Rebuild: just ci-image   (then bump the tag in runner/config.yml and the test)
FROM node@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee

RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
