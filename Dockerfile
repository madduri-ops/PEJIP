# PEJIP container image (ADR-0005). Built and scanned on every pull request that
# can change it, and pushed to ECR by the Deploy workflow on main.
#
# The default command serves the API. Batch commands run as one-off tasks from
# the same image with a command override, for example `pejip purge`.

# Base image pinned by digest; Dependabot (docker) keeps it current. Alpine,
# because the Debian slim image carries dozens of high-severity OS package
# findings (util-linux, gcc runtime, pcre2, acl) that the image scan blocks on.
FROM python:3.12-alpine@sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 AS build

WORKDIR /src
RUN pip install --no-cache-dir build==1.6.1
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m build --wheel --outdir /dist


FROM python:3.12-alpine@sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PEJIP_HOST=0.0.0.0 \
    PEJIP_PORT=8000

# OS packages are upgraded first so security fixes published after the base
# image was built are picked up (the image scan blocks on high and critical).
# Only the built wheel is installed: no tests, CI scripts or dev tools ship.
# pip is removed afterwards; nothing installs packages at runtime.
RUN --mount=type=bind,from=build,source=/dist,target=/dist \
    apk upgrade --no-cache \
    && pip install --no-cache-dir /dist/*.whl \
    && pip uninstall --yes pip \
    && adduser -S -D -H -u 10001 -s /sbin/nologin pejip

USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ['PEJIP_PORT']}/healthz\", timeout=4)"]
CMD ["python", "-m", "pejip.api"]
