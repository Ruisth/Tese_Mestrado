# Dockerfile — egw-controller image (MQTT->Ditto bridge, CONTRACTS.md 5/8).
#
# Build context is src/. The image is built on a provisioning host by
# deployment/scripts/build-controller-image.sh (buildx, linux/arm64, `docker
# save` plus an identity record) and loaded into the gateway with `docker
# load`: deployment/compose.yaml has no "build:" for the controller and the
# gateway has no build context, no buildx and no pip. It is never pulled, so
# it is not listed in deployment/images.lock.env. The base image is pinned and
# the Python dependencies are locked: requirements-runtime.lock (ADR 0011,
# condition C7) carries a SHA-256 hash for every runtime and build
# distribution, resolved inside this base image on an aarch64 environment by
# deployment/scripts/generate-runtime-lock.sh's steps, installed below with
# --require-hashes and the project with --no-build-isolation --no-deps. Any
# change to pyproject.toml, the base-image digest or the Python version
# invalidates the lock and requires regeneration.
#
# Multi-arch friendly: the base image is pinned by its MULTI-ARCH
# manifest-list digest, so the same reference resolves to the native child
# image on any platform (linux/arm64 for the campaign VM; compose sets
# platform: linux/arm64). All Python dependencies (fastapi, uvicorn, httpx,
# jsonschema, paho-mqtt and transitive deps) publish universal or arm64
# wheels on PyPI; nothing below is architecture-specific.
#
# Base image pin: python:3.12.13-slim, the latest 3.12.x slim tag on Docker
# Hub as of 2026-08-07 (Docker Hub API, tag pushed 2026-08-07; linux/arm64
# child digest sha256:adbc7c33e0abc183557d1d14ce5eb5d261aaadff5451c81a8db636b3ebefcdf6).
FROM docker.io/library/python:3.12.13-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Project metadata, the three packages declared in [tool.setuptools].packages
# (setuptools requires all of them present even though only egw_controller
# runs in this image) and the JSON Schemas used for payload validation
# (EGW_SCHEMA_DIR=/app/schemas, set by compose).
COPY pyproject.toml ./
COPY requirements-runtime.lock ./
COPY egw_simulator/ egw_simulator/
COPY egw_controller/ egw_controller/
COPY egw_experiments/ egw_experiments/
COPY schemas/ schemas/

# Hash-locked install (deployment/README.md, "Runtime Python lock"): every
# distribution must match a hash of the lock, wheels only, and the project is
# built without isolation so that no unsealed backend can be downloaded.
RUN pip install --require-hashes --only-binary=:all: \
        -r requirements-runtime.lock \
    && pip install --no-build-isolation --no-deps . \
    && pip check

# Non-root runtime user (uid 1000). /data/events is the default event-log
# location (EGW_EVENT_LOG_DIR); in the compose stack the host directory
# deployment/data/events is bind-mounted over it so the experiments harness
# can read events.jsonl from the host.
RUN useradd --uid 1000 --user-group --shell /usr/sbin/nologin egw \
    && mkdir -p /data/events \
    && chown -R egw:egw /data
USER egw

EXPOSE 8000

# stdlib-only liveness probe: no curl/wget in the image and no httpx in the
# probe path. Mirrored in compose.yaml so orchestration semantics do not
# depend on image metadata.
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"]

# egw_controller.app deliberately exposes an application FACTORY
# (create_app_from_env, which wires MQTT/Ditto/schemas from EGW_* env vars),
# not a module-level "app" object, hence uvicorn's --factory mode.
CMD ["uvicorn", "--factory", "egw_controller.app:create_app_from_env", \
     "--host", "0.0.0.0", "--port", "8000"]
