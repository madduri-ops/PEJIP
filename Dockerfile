# PEJIP container image (ADR-0004). Built and scanned on every pull request that
# can change it, and pushed to ECR by the Deploy workflow on main.
#
# The default command serves the API. Batch commands run as one-off tasks from
# the same image with a command override, for example `pejip purge`.

# Base image pinned by digest; Dependabot (docker) keeps it current.
FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS build

WORKDIR /src
RUN pip install --no-cache-dir build==1.6.1
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m build --wheel --outdir /dist


FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PEJIP_HOST=0.0.0.0 \
    PEJIP_PORT=8000

# Only the built wheel is installed: no tests, CI scripts or dev tools ship.
RUN --mount=type=bind,from=build,source=/dist,target=/dist \
    pip install --no-cache-dir /dist/*.whl \
    && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin pejip

USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ['PEJIP_PORT']}/healthz\", timeout=4)"]
CMD ["python", "-m", "pejip.api"]
