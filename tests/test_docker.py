"""The Docker setup (Dockerfile, compose.yaml, .dockerignore) stays consistent with python -m arcane_server.local and
never puts the player's files into the image. Checked by reading the files (no Docker, no YAML dependency)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from yaml_lines import colon_in_plain_values

from arcane_server import local

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from android_package import FOLDERS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text()
COMPOSE = (ROOT / "compose.yaml").read_text()
IGNORE = [line for line in (ROOT / ".dockerignore").read_text().splitlines() if line and not line.startswith("#")]

# What the image may hold: this repository's code and committed release definitions, nothing the player supplies.
ALLOWED_SOURCES = {"pyproject.toml", "uv.lock", "LICENSE", "src", "content", "proto", "tools"}


def _copies() -> list[list[str]]:
    return [line.split()[1:-1] for line in DOCKERFILE.splitlines()
            if line.startswith("COPY ") and "--from=" not in line]


def test_the_image_copies_only_code():
    sources = {s.removeprefix("./").rstrip("/") for srcs in _copies() for s in srcs}
    assert sources <= ALLOWED_SOURCES, f"the image must not hold {sources - ALLOWED_SOURCES}"
    # what the server reads at run time: the same folders as the server zip the patcher embeds
    runtime = {folder.split("/")[0] for folder in FOLDERS}
    assert runtime <= sources, f"the image lacks {runtime - sources}, which the server reads at run time"
    assert "ADD " not in DOCKERFILE, "use COPY of a listed path (ADD can fetch and unpack archives)"


def test_the_build_context_is_an_allowlist():
    """.dockerignore excludes everything, then lets back only what the Dockerfile copies: var/, data/, APKs and
    builds never reach the Docker daemon."""
    assert IGNORE[0] == "*"
    allowed = {line.removeprefix("!").rstrip("/") for line in IGNORE if line.startswith("!")}
    assert allowed == ALLOWED_SOURCES


def test_the_image_runs_the_local_command():
    assert re.search(r'^CMD \["python", "-m", "arcane_server\.local"\]$', DOCKERFILE, re.MULTILINE)


def test_qemu_is_installed_on_amd64_only():
    assert re.search(r'dpkg --print-architecture\)" = "amd64" \]; then\s*\\\s*\n\s*apt-get update && apt-get '
                     r'install -y --no-install-recommends qemu-user-static', DOCKERFILE)


def test_base_and_uv_images_are_pinned():
    stages = set(re.findall(r"^FROM \S+ AS (\S+)$", DOCKERFILE, re.MULTILINE))
    for line in DOCKERFILE.splitlines():
        for image in re.findall(r"(?:^FROM |--from=)(\S+)", line):
            if image in stages:
                continue
            assert ":" in image and not image.endswith((":latest", ":3")), f"pin {image}"


def test_the_hints_name_the_compose_service():
    service = re.search(r"^services:\n  ([\w-]+):", COMPOSE, re.MULTILINE).group(1)
    prefix = re.search(rf'{local.RUN_PREFIX_ENV}="([^"]+)"', DOCKERFILE).group(1)
    assert prefix == f"docker compose run --rm {service}"


def test_compose_mounts_the_player_folders_and_publishes_both_ports():
    assert "      - ./var:/app/var" in COMPOSE.splitlines()
    assert "      - ./data:/app/data" in COMPOSE.splitlines()
    port = local.DEFAULT_PORT
    for p in (port, port + 1):
        assert f'      - "127.0.0.1:{p}:{p}"' in COMPOSE.splitlines()
        assert str(p) in re.search(r"^EXPOSE (.*)$", DOCKERFILE, re.MULTILINE).group(1).split()
    assert re.search(r"^    init: true$", COMPOSE, re.MULTILINE), "an init reaps the servers' children (PID 1)"


def test_compose_is_valid_yaml_shape():
    """No plain value with ': ' (as in the workflows), two-space indentation, no tabs."""
    bad = colon_in_plain_values(COMPOSE)
    for n, line in enumerate(COMPOSE.splitlines(), 1):
        if "\t" in line or (len(line) - len(line.lstrip(" "))) % 2:
            bad.append(f"{n}: indentation: {line}")
    assert not bad, "\n".join(bad)


def test_the_servers_run_as_the_invoking_user_not_root():
    """Files the container writes into the mounted var/ and data/ belong to the user who runs compose: compose
    passes that user's ids (ARCANE_UID/ARCANE_GID, 1000 when unset) and the image's default user is not root either."""
    assert '    user: "${ARCANE_UID:-1000}:${ARCANE_GID:-1000}"' in COMPOSE.splitlines()
    users = re.findall(r"^USER (\S+)$", DOCKERFILE, re.MULTILINE)
    assert users and users[-1].split(":")[0] not in ("0", "root"), "the image's last USER must not be root"
    # a home any uid can write (Python and uv look there), and the listen address the published ports need
    assert re.search(r"^\s*HOME=/tmp\b", DOCKERFILE, re.MULTILINE)
    assert re.search(r"^\s*ARCANE_HOST=0\.0\.0\.0\b", DOCKERFILE, re.MULTILINE)


def test_compose_explains_the_user_ids():
    """The shells' UID/GID cannot be passed as they are (read-only in bash, setuid in zsh, GID unset in bash): the
    setup comment says how to pass the ids compose reads."""
    assert "ARCANE_UID=%s\\nARCANE_GID=%s\\n' $(id -u) $(id -g)" in COMPOSE


def test_the_image_has_the_pinned_flatc():
    """import-client inside the container converts a content set without gamedata-static.json: the image carries the
    flatc version the release's JSON hash was made with, built from its checked source."""
    from arcane_server.client_import import FLATC_VERSION

    assert f"ARG FLATC_VERSION={FLATC_VERSION}" in DOCKERFILE.splitlines()
    assert re.search(r"^ARG FLATC_SHA256=[0-9a-f]{64}$", DOCKERFILE, re.MULTILINE)
    assert 'sha256sum -c -' in DOCKERFILE
    assert "COPY --from=flatc /usr/local/bin/flatc /usr/local/bin/flatc" in DOCKERFILE.splitlines()


def test_compose_rebuilds_the_image_from_the_checkout():
    """After a player updates the checkout, `docker compose run` / `up` must not keep using the image built from the
    old code (compose reuses an existing image by default): pull_policy build rebuilds it every time (a cache hit
    when nothing changed)."""
    assert "    pull_policy: build" in COMPOSE.splitlines()
