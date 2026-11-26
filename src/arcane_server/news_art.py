"""Images of the news page: the art the client itself shows for a scheduled item (event tiles, Summoner Showdown
banners, passholder previews, store packs), taken from the content set's asset bundles.

An image id is the client's "<bundle>/<texture>" (the same ids the server sends in its responses). Its file is a
small WebP under `art_dir(settings)` (var/cache/news_art/<client>/v<ART_VERSION>/<bundle>/<texture>.webp; var/cache
is a cache), at the aspect ratio the client shows it at (`FAMILIES`), scaled down, never cropped or padded;
`size` reads its pixel size back for the page's width / height attributes.

Unity stored the textures resized to power-of-two sizes (1024 x 1024, 2048 x 1024, ...) and the client stretches them
back through its UI layout: the shape is the layout size of the image that shows them, not the texture's. Every
image the schedules can show belongs to one family of `FAMILIES` (the one list: client slot, display size, ids);
`family` fails on an id no family claims (tests/test_news.py runs it over every image the schedules show). Hosted servers extract a texture the first time the page needs it (UnityPy, the `art` extra) and keep the
file; nothing is extracted at startup. The offline variant cannot run UnityPy on the phone, so
its News page shows items without images; so does any server without the file and without UnityPy.
"""

from __future__ import annotations

import io
import logging
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from arcane_server.config import VAR_DIR

if TYPE_CHECKING:
    from arcane_server.config import Settings
    from arcane_server.game import Game

log = logging.getLogger(__name__)

ART_VERSION = 3  # in the cache path: bump when the extraction changes (v1: 480 px square box; v2: texture aspect)
MAX_WIDTH = 640  # px: a phone-width card (banners span it); the textures are up to 2048
MAX_HEIGHT = 800  # px: tall portraits (1024 x 2048) stay readable without a huge file
QUALITY = 70
_SAFE = re.compile(r"^[A-Za-z0-9_.-]+$")
_LOCK = threading.Lock()  # one extraction at a time (a bundle is loaded whole)
_MISSING: set[tuple[str, str]] = set()  # (client, image id) not extractable: don't retry per request


@dataclass(frozen=True)
class Family:
    """Images the client shows in one UI slot. `display`: that image's size in the client's layout (its own
    size, or the parent's size plus its offset for stretched anchors; the whole texture is shown, never fitted to its
    aspect): the shape the art was drawn at. `kinds`: the schedule kinds (schedule.KINDS) that show it."""
    slot: str  # where the client shows it, the source of `display`
    display: tuple[float, float]  # width, height in the prefab's units
    kinds: tuple[str, ...]
    ids: tuple[str, ...]  # regular expressions over the whole image id "<bundle>/<texture>"

    @property
    def aspect(self) -> float:
        return self.display[0] / self.display[1]


_EVENTS = r"icons_scheduled_events_[^/]+"
FAMILIES: dict[str, Family] = {
    # The home screen's event portal: a square quad in the home scene (uniform scale, material tiling 1, 1).
    # Event_portal_*, the event group's marqueeImage (the page shows it only for a group without an image).
    "event_portal": Family("home screen: active event portal", (1, 1),
                           ("event", "permanent_event", "trial", "tower"),
                           (rf"{_EVENTS}/(?i:[a-z0-9_]*portal[a-z0-9_]*)",)),
    # An event's tile in an event group (and the Summoner Challenges): a tile of 815 x 790 whose image is stretched
    # with sizeDelta -29.132 x -430.4. Covers and the daily challenges' art.
    "event_cover": Family("events screen: event tile", (815 - 29.132, 790 - 430.4), ("daily",),
                          (rf"{_EVENTS}/[A-Za-z0-9_]*_cover(_[A-Za-z0-9_]+)?", r"icons_daily_events/challenge_[a-z0-9_]+")),
    # An event group's card on the events screen (scheduled events, towers, Sorcerer's Trials, leaderboard contests,
    # Summoner Showdown: every kind of event group): the card's image, 555 x 880.
    # (The tower select screen shows tower art at 416 x 763.1, a little narrower.)
    "event_group": Family("events screen: event group card", (555, 880),
                          ("event", "permanent_event", "trial", "tower", "contest", "showdown"),
                          (rf"{_EVENTS}/(?!passport_)[A-Za-z0-9_]*meta[A-Za-z0-9_]*",
                           rf"{_EVENTS}/event_platinum_mickey_bookcover")),
    # Passholder season showcase (passportSeason.homeShowcaseImage) on the home screen: 552.96 x 1021 (its top half
    # shows through a 553.2 x 535.7 clip mask).
    "passport_showcase": Family("home screen: passholder season showcase",
                                (552.96, 1021), ("passport",),
                                (rf"{_EVENTS}/passport_(homescreen_[a-z0-9_]+|[a-z0-9_]+_homescreen|"
                                 r"home_banner_[a-z0-9_]+|[a-z0-9_]+_offer_banner)",)),
    # Raid and Club Expedition cards on the raid select screen (raid imageAssetPath; raidConstants
    # clubExpeditionDefaultPreviewImagePath): the card's parallax background, 2048 x 880 (clipped to the 800 or 1750
    # wide card, sliding with the scroll).
    "raid_select": Family("raid select screen: raid card background", (2048, 880),
                          ("raid", "expedition", "festival_bonus"),
                          (r"raids_[a-z0-9_]+/[A-Za-z0-9_]+", r"icons_club_expeditions/club_expeditions_default")),
    # Special offers and Mystic Leap in the store and the offer popup: the special offer card's main image,
    # 1875.7 x 652.
    "store_special_offer": Family("store: special offer card", (1875.7, 652),
                                  ("special_offer", "mystic_leap"), (r"store_special_[a-z0-9_-]+/[A-Za-z0-9_-]+",)),
    # Festival chests and pouches in their PACKS store tab (item_size MEDIUM): the medium store card's main image,
    # 650 x 709.
    "store_medium": Family("store: medium pack card", (650, 709), ("festival",),
                           (r"store_(chest|pouch)_[a-z0-9_]+/[A-Za-z0-9_]+",)),
}
_PATTERNS = [(name, re.compile(rx)) for name, f in FAMILIES.items() for rx in f.ids]


class UnknownArt(ValueError):
    """An image id no family of FAMILIES claims: find the client slot that shows it and add it there."""


def family(image_id: str) -> str:
    """The FAMILIES name of an image id (the first family whose pattern matches the whole id)."""
    for name, rx in _PATTERNS:
        if rx.fullmatch(image_id):
            return name
    raise UnknownArt(f"news art: no image family for {image_id!r} (news_art.FAMILIES)")


def display_size(texture: tuple[int, int], aspect: float) -> tuple[int, int]:
    """Pixel size of a texture shown at `aspect` (width / height): stretched back to that shape without making
    either side larger than the texture's, then scaled down into MAX_WIDTH x MAX_HEIGHT."""
    w, h = texture
    w, h = min(w, h * aspect), min(h, w / aspect)
    k = min(1.0, MAX_WIDTH / w, MAX_HEIGHT / h)
    return max(1, round(w * k)), max(1, round(h * k))


def art_dir(settings: "Settings") -> Path:
    return VAR_DIR / "cache" / "news_art" / settings.client / f"v{ART_VERSION}"


def split(image_id: str) -> tuple[str, str] | None:
    """(bundle, texture) of an image id, None if it is not one (or not a safe file name)."""
    bundle, _, name = image_id.partition("/")
    if not name or not _SAFE.match(bundle) or not _SAFE.match(name):
        return None
    return bundle, name


def path_of(settings: "Settings", image_id: str) -> Path | None:
    parts = split(image_id)
    return art_dir(settings) / parts[0] / f"{parts[1]}.webp" if parts else None


def extractor_available() -> bool:
    try:
        import UnityPy  # noqa: F401
    except ImportError:
        return False
    return True


def available(game: "Game", image_id: str) -> bool:
    """The image can be served: its file exists, or it can be extracted here (bundle in the content set)."""
    p = path_of(game.settings, image_id)
    if p is None or not game.settings.toggles.serve_client_files:  # a hosted server shows no art of the client
        return False
    try:
        family(image_id)
    except UnknownArt as e:  # tests/test_news.py keeps this from happening; shown without image, not a broken page
        log.error("%s", e)
        return False
    if p.is_file():
        return True
    return ((game.settings.client, image_id) not in _MISSING and extractor_available()
            and game.content.bundle_path(image_id.split("/")[0]) is not None)


def image(game: "Game", image_id: str) -> bytes | None:
    """The WebP of an image id (extracted and cached on first use), None if there is none."""
    p = path_of(game.settings, image_id)
    if p is None or not game.settings.toggles.serve_client_files:
        return None
    if p.is_file():
        return p.read_bytes()
    if not available(game, image_id):
        return None
    with _LOCK:
        if not p.is_file():
            data = extract(game.content.bundle_path(image_id.split("/")[0]), image_id.split("/")[1],
                           FAMILIES[family(image_id)].aspect)
            if data is None:
                _MISSING.add((game.settings.client, image_id))
                log.warning("news art: no texture %s", image_id)
                return None
            store(p, data)
    return p.read_bytes()


def store(p: Path, data: bytes) -> None:
    """Write a cache file whole (readers never see part of it). Several processes may extract the same image at once
    (servers and test workers share the cache; _LOCK only covers this process): each writes its own temporary file and
    the last rename wins."""
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def extract(bundle: Path | None, texture: str, aspect: float) -> bytes | None:
    """The texture (or sprite) named `texture` in a bundle file as a WebP at `aspect` (width / height: its family's
    display shape), scaled down to at most MAX_WIDTH x MAX_HEIGHT."""
    import UnityPy
    from PIL import Image

    if bundle is None:
        return None
    env = UnityPy.load(str(bundle))
    found = {}
    for obj in env.objects:  # the client looks assets up by name ignoring case (e.g. special_offer_BH6_team)
        if obj.type.name in ("Texture2D", "Sprite"):
            data = obj.read()
            name = getattr(data, "m_Name", "")
            if name.lower() == texture.lower():
                found[(name != texture, obj.type.name != "Texture2D")] = data
    if not found:
        return None
    img = found[min(found)].image  # exact name first, Texture2D before Sprite
    img = img.resize(display_size(img.size, aspect), Image.LANCZOS)
    out = io.BytesIO()
    img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB").save(out, "WEBP", quality=QUALITY)
    return out.getvalue()


_SIZES: dict[Path, tuple[int, int]] = {}


def size(game: "Game", image_id: str) -> tuple[int, int] | None:
    """(width, height) in pixels of an extracted image (read from its WebP header), None if it has no file yet."""
    p = path_of(game.settings, image_id)
    if p is None or not p.is_file() or not game.settings.toggles.serve_client_files:
        return None
    if p not in _SIZES:
        dims = webp_size(p.read_bytes()[:30])
        if dims is None:
            return None
        _SIZES[p] = dims
    return _SIZES[p]


def webp_size(head: bytes) -> tuple[int, int] | None:
    """Pixel size from a WebP file's first 30 bytes (lossy VP8, lossless VP8L or extended VP8X)."""
    if len(head) < 30 or head[:4] != b"RIFF" or head[8:12] != b"WEBP":
        return None
    chunk = head[12:16]
    if chunk == b"VP8 ":
        return int.from_bytes(head[26:28], "little") & 0x3FFF, int.from_bytes(head[28:30], "little") & 0x3FFF
    if chunk == b"VP8L":
        b = int.from_bytes(head[21:25], "little")
        return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X":
        return int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1
    return None


def prebuild(game: "Game", image_ids: set[str]) -> tuple[int, list[str]]:
    """Extract every image id into art_dir (build time: the offline payload). Returns (files, missing ids). Fails,
    listing them all, when an id belongs to no family."""
    unknown = []
    for image_id in sorted(image_ids):
        try:
            family(image_id)
        except UnknownArt:
            unknown.append(image_id)
    if unknown:
        raise UnknownArt(f"news art: no image family (news_art.FAMILIES) for {unknown}")
    missing = []
    for image_id in sorted(image_ids):
        if image(game, image_id) is None:
            missing.append(image_id)
    return len(image_ids) - len(missing), missing
