# The image Testament's runners execute prawduct's pytest suite in (`.testament.toml` [image]).
# Python 3.14 is the CI matrix's current leg; git because the suite builds scratch repositories
# and runs the hook's git plumbing; uv to install the `dev` extra from uv.lock (`[setup]`).
FROM ghcr.io/astral-sh/uv:0.11.32 AS uv
FROM python:3.14-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates procps \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /uvx /usr/local/bin/
RUN useradd -m -s /bin/bash lane
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
USER lane
CMD ["sleep", "infinity"]
