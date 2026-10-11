# PEJIP container image (ADR-0005). Built and scanned on every pull request that
# can change it, and pushed to ECR by the Deploy workflow on main.
#
# The default command serves the API. Batch commands run as one-off tasks from
# the same image with a command override, for example `pejip purge`.

# Base image pinned by digest; Dependabot (docker) keeps it current. Alpine,
# because the Debian slim image carries dozens of high-severity OS package
# findings (util-linux, gcc runtime, pcre2, acl) that the image scan blocks on.
FROM python:3.14-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72 AS build

WORKDIR /src
RUN pip install --no-cache-dir build==1.6.1
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m build --wheel --outdir /dist


FROM python:3.14-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PEJIP_HOST=0.0.0.0 \
    PEJIP_PORT=8000 \
    PEJIP_CONFIG=/etc/pejip/search.yaml

# OS packages are upgraded first so security fixes published after the base
# image was built are picked up (the image scan blocks on high and critical).
# Only the built wheel is installed: no tests, CI scripts or dev tools ship.
# pip is removed afterwards; nothing installs packages at runtime.
RUN --mount=type=bind,from=build,source=/dist,target=/dist \
    apk upgrade --no-cache \
    && pip install --no-cache-dir /dist/*.whl \
    && pip uninstall --yes pip \
    && adduser -S -D -H -u 10001 -s /sbin/nologin pejip

# The search configuration `pejip run` reads. It holds no personal data; the
# career profile comes from SSM at run time (docs/design/0012-daily-run-and-storage.md).
COPY config/search.yaml /etc/pejip/search.yaml

# Fargate copies a VOLUME's image permissions (here /tmp's 1777) into the
# task-local volume mounted there, so the app user can write temp files even
# though the root filesystem is read-only.
VOLUME ["/tmp"]

USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ['PEJIP_PORT']}/healthz\", timeout=4)"]
CMD ["python", "-m", "pejip.api"]
