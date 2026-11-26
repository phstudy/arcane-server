"""Downloads the player's machine makes at setup, each checked against a sha256: Google's Android system image for the
battle host (hash pinned in battle_host/host.py), and release assets of this project and of the browser client (the
cas_host helper, the browser client's build), checked against the `<asset>.sha256` file published next to each.

Every download has a socket timeout, checks the free disk space against the announced size first, and leaves no
partial file behind when it fails.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

TIMEOUT_S = 60.0  # per socket operation: a stalled server fails the download instead of hanging setup
SERVER_RELEASES = "https://github.com/phstudy/arcane-server/releases/download"
WEB_RELEASES = "https://github.com/phstudy/arcane-web/releases/download"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class DownloadError(Exception):
    """A download failed or did not match its sha256; the message names the URL."""


def ensure_free_space(folder: Path, need: int, what: str) -> None:
    """DownloadError unless `folder` (or its nearest existing parent) has `need` bytes free."""
    probe = folder
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free < need:
        raise DownloadError(f"{what} needs {_mb(need)} MB free in {folder}, only {_mb(free)} MB are: free some space "
                            "and run this again")


def _mb(n: int) -> int:
    return n >> 20


def download(url: str, dest: Path, *, sha256: str, size: int | None = None, log: Callable[[str], None] = print,
             timeout: float = TIMEOUT_S) -> None:
    """Stream `url` into `dest`, checking its sha256 (and the free space, when the size is known)."""
    h, done, next_report = hashlib.sha256(), 0, 100 << 20
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            announced = int(r.headers.get("Content-Length") or 0) or size
            if announced:
                ensure_free_space(dest.parent, announced, url)
            with dest.open("wb") as f:
                for chunk in iter(lambda: r.read(1 << 20), b""):
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    if done >= next_report:
                        log(f"  {_mb(done)} MB" + (f" of {_mb(announced)} MB" if announced else ""))
                        next_report += 100 << 20
        if h.hexdigest() != sha256:
            raise DownloadError(f"{url}: sha256 {h.hexdigest()}, expected {sha256}: refusing it")
    except (OSError, ValueError) as e:  # URLError, timeouts and a full disk are OSErrors
        dest.unlink(missing_ok=True)
        raise DownloadError(f"download failed: {url}: {e}") from e
    except DownloadError:
        dest.unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class ReleaseAsset:
    """A file attached to a GitHub release `v<version>`, with `<name>.sha256` (`<hex>  <name>`) beside it."""

    releases: str  # .../releases/download
    version: str
    name: str

    @property
    def url(self) -> str:
        return f"{self.releases}/v{self.version}/{self.name}"


def published_sha256(asset: ReleaseAsset, timeout: float = TIMEOUT_S) -> str:
    url = asset.url + ".sha256"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            text = r.read(4096).decode("ascii", "replace")
    except OSError as e:
        raise DownloadError(f"{url}: {e} (is there a release v{asset.version} with {asset.name}?)") from e
    first = (text.split() or [""])[0].lower()
    if not _SHA256.fullmatch(first):
        raise DownloadError(f"{url}: not a sha256 file")
    return first


def fetch_release_asset(asset: ReleaseAsset, dest: Path, log: Callable[[str], None] = print,
                        timeout: float = TIMEOUT_S) -> None:
    log(f"Downloading {asset.url}")
    download(asset.url, dest, sha256=published_sha256(asset, timeout), log=log, timeout=timeout)
