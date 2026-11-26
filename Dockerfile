# The game server, its battle server and the browser client in one container: `docker compose up` runs
# `python -m arcane_server.local`, the same command as on a checkout. The image holds this repository's code and
# public packages only. The player's files are made inside the container on the mounted volumes (compose.yaml):
# the battle host in var/battle_host/ (from your APK and Google's public Android image), the content set in data/,
# the browser client in var/web_client/. `python -m arcane_server.local --check` lists what is still missing.

# flatc 23.5.26, the version whose JSON the client release pins (client_import.FLATC_VERSION), built from its source
# (there is no arm64 Linux binary): import-client runs it for a content set without gamedata/gamedata-static.json.
FROM python:3.12-slim-bookworm AS flatc
ARG FLATC_VERSION=23.5.26
ARG FLATC_SHA256=1cce06b17cddd896b6d73cc047e36a254fb8df4d7ea18a46acf16c4c0cd3f3f3
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl cmake g++ make \
    && curl -fsSL -o /tmp/flatbuffers.tar.gz \
        "https://github.com/google/flatbuffers/archive/refs/tags/v${FLATC_VERSION}.tar.gz" \
    && echo "${FLATC_SHA256}  /tmp/flatbuffers.tar.gz" | sha256sum -c - \
    && tar xzf /tmp/flatbuffers.tar.gz -C /tmp \
    && cmake -S "/tmp/flatbuffers-${FLATC_VERSION}" -B /tmp/build -DCMAKE_BUILD_TYPE=Release \
        -DFLATBUFFERS_BUILD_TESTS=OFF -DFLATBUFFERS_BUILD_FLATLIB=OFF -DFLATBUFFERS_BUILD_FLATHASH=OFF \
    && cmake --build /tmp/build --target flatc -j"$(nproc)" \
    && install -m 0755 /tmp/build/flatc /usr/local/bin/flatc

FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /usr/local/bin/uv

# The battle engine is arm64: an x86_64 host runs it under qemu-aarch64 (user mode); arm64 runs it natively.
RUN if [ "$(dpkg --print-architecture)" = "amd64" ]; then \
        apt-get update && apt-get install -y --no-install-recommends qemu-user-static \
        && rm -rf /var/lib/apt/lists/*; \
    fi

COPY --from=flatc /usr/local/bin/flatc /usr/local/bin/flatc

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    ARCANE_HOST=0.0.0.0 \
    ARCANE_LOCAL_RUN="docker compose run --rm arcane"

COPY pyproject.toml uv.lock LICENSE ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY content ./content
COPY proto ./proto
COPY tools ./tools
RUN uv sync --locked --no-dev

EXPOSE 18080 18081
# Not root: what the servers write into the mounted folders belongs to the user (compose.yaml passes their ids).
USER 1000:1000
CMD ["python", "-m", "arcane_server.local"]
