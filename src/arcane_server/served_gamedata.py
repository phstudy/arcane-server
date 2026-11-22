"""The gamedata .bin clients download (`meta` hands out its version, the CDN serves it): the content set's original
with the server's rewrites applied.

- Passholder seasons: begin/end rewritten to the rotation (handlers/passport.py `rotate_seasons`).
- News: constants.newsletterUrl / newsletterUrls / newsletterLastModifiedUrl point at this server's news page
  (news.py) on the address the client reached it at (`base_url`, as the CDN URL), so the hosted, offline and
  the Multiplayer app builds each get their own address and no host is hard-coded.
- Game speed (clock.py): the client computes some timers itself from gamedata (energy regeneration from
  `last_generated_timestamp` + generatedFrequencySeconds, energy gift windows, cooldowns, club week boundaries,
  stamp timers, ...). `GAMEDATA_FIELDS` classifies every gamedata number that looks like a time (tests check that
  none is unclassified): game durations are served in real seconds (/ speed, rounded up; whole hours / days / minutes
  too, rounded up), game timestamps with clock.to_real; battle, network and UI timings stay. The server itself
  computes with the original values in game time, so both agree.
- Stamp cards: stamps.killSwitch off (handlers/stamps.py `enable_in_gamedata`; the 2024-08 gamedata has the feature
  switched off, the end of service).

The version is a hash of what went into the rewrite (season layout, game calendar, base URL): it changes when the
result does, so clients re-download it then.
"""

from __future__ import annotations

import hashlib
import struct
import uuid
import weakref
from dataclasses import dataclass
from typing import TYPE_CHECKING

from arcane_server import clock, flatbuf, news
from arcane_server.handlers import passport, stamps
from arcane_server.wire_time import Kind

if TYPE_CHECKING:
    from arcane_server.game import Game

CACHED_VERSIONS = 6  # (season layout x client address) variants kept for CDN requests of a recent version


@dataclass(frozen=True)
class ServedGamedata:
    version: str
    data: bytes


_SERVED: "weakref.WeakKeyDictionary[Game, dict[str, ServedGamedata]]" = weakref.WeakKeyDictionary()

_F_CONSTANTS = flatbuf.field_index("StaticGamedata", "constants")
_F_NEWSLETTER_URL = flatbuf.field_index("Constants", "newsletterUrl")
_F_NEWSLETTER_LAST_MODIFIED = flatbuf.field_index("Constants", "newsletterLastModifiedUrl")
_F_NEWSLETTER_URLS = flatbuf.field_index("Constants", "newsletterUrls")
NEWSLETTER_LANGUAGES = flatbuf.schema_fields("NewsletterUrls")  # english, french, ..., portugueseBrazilian


def served_gamedata(game: "Game", base_url: str, version: str | None = None, now: int | None = None) -> ServedGamedata:
    """The gamedata for a client that reached this server at `base_url`. `version` (from a CDN URL) returns that
    variant if it was built recently, else the current one. `now`: game time (default: the calendar's now)."""
    cache = _SERVED.setdefault(game, {})
    if version is not None and version in cache:
        return cache[version]
    cat = passport.catalog(game)
    run = passport.current_slot(game, now).run
    c = clock.current()  # the real timestamps depend on the calendar's anchor and speed
    ver = str(uuid.uuid5(uuid.NAMESPACE_URL, f"arcane-gamedata:{cat.base_version}:passport-run:{run}"
                                             f":clock:{c.anchor_real}:{c.anchor_game}:{c.speed}:news:{base_url}:stamps:on"))
    if ver not in cache:
        buf = bytearray(cat.gamedata)  # the original .bin
        passport.rotate_seasons(game, buf, now)
        point_newsletter(buf, base_url)
        stamps.enable_in_gamedata(buf)
        scale_times(buf)
        cache[ver] = ServedGamedata(ver, bytes(buf))
        while len(cache) > CACHED_VERSIONS:
            cache.pop(next(iter(cache)))
    return cache[ver]


def point_newsletter(buf: bytearray, base_url: str) -> None:
    """Point every Constants row's newsletter URLs at this server's news page (one URL per client language)."""
    root = flatbuf.root(buf)
    vec = flatbuf.field(buf, root, _F_CONSTANTS)
    if vec is None:
        raise RuntimeError("gamedata has no constants")
    for t in flatbuf.vector_tables(buf, vec):
        flatbuf.replace_string(buf, t, _F_NEWSLETTER_URL, news.page_url(base_url, "english"))
        flatbuf.replace_string(buf, t, _F_NEWSLETTER_LAST_MODIFIED, news.page_url(base_url))
        urls = flatbuf.field(buf, t, _F_NEWSLETTER_URLS)
        if urls is None:
            raise RuntimeError("gamedata constants have no newsletterUrls")
        flatbuf.replace_string_table(buf, urls, [news.page_url(base_url, lang) for lang in NEWSLETTER_LANGUAGES])


# --- game speed ---------------------------------------------------------------------------------------------------

T, D, R, N = Kind.TIMESTAMP, Kind.DURATION, Kind.REAL, Kind.NOT_TIME
# names that look like time (tests/test_wire_time.py: every numeric gamedata field matching it is listed below)
GAMEDATA_TIME_NAME = (r"(?i:second|frequency|cooldown|minute|hour|days|duration|interval|delay|timestamp|time|lifespan"
                      r"|expire|period|timeout)|[a-z](S|M)$")
GAMEDATA_FIELDS: dict[str, Kind] = {
    # game durations: the client counts them on the device clock
    "EnergyConstants.generatedFrequencySeconds": D,  # regeneration, predicted by the client
    "EnergyConstants.dailyGiftSecondsFromDayStart": D,  # gift windows within the (game) day
    "EnergyConstants.dailyGiftExpireSeconds": D,
    "Constants.dailyLoginBonusEligibilitySeconds": D,
    "Constants.clubItemRequestLifespanHours": D,
    "Constants.clubAutoDemoteInactivityPeriodHours": D,
    "Constants.clubAutoPromoteActivityPeriodHours": D,
    "Constants.clubAutoDemoteInactiveLeaderPeriodHours": D,
    "Constants.joinClubLockTimeS": D,
    "Constants.joinClubLockResetTimeS": D,
    "Constants.clubDungeonDurationS": D,
    "Constants.shipmentRefreshTime": D,
    "Constants.kothShieldsCooldownSeconds": D,
    "Constants.kothLocalDayEndTimeSeconds": D,  # payout time within the (game) day
    "Constants.kothAttackCooldownSeconds": D,
    "Constants.kothAutoRefreshFrequencySeconds": D,
    "Constants.clubInviteExpireTime": D,
    "Constants.specialOfferPopupLimitCooldownS": D,
    "Constants.timeSettingsChangesPeriodDurationDays": D,
    "Constants.createClubCooldownTimeHours": D,  # the client adds it to create_club_timestamp
    "Constants.passportSeasonUpsellShowDaysFromEnd": D,
    "Constants.passportSeasonUpsellShowFrequencySeconds": D,
    "ClubSupport.requestFulfillCooldownS": D,
    "ClubWarPhase.durationS": D,
    "ClubWar.finalPhaseDurationM": D,
    "ClubWar.pointTickFrequencyS": D,
    "ClubWar.nodeRebuildDurationS": D,
    "StampSet.durationInMinutes": D,
    "RaidConstants.raidRewardDurationDays": D,
    "RaidConstants.raidRewardInactivityCutoffDays": D,
    # game timestamps
    "OfferWallSpecial.startTimestampS": T,
    "OfferWallSpecial.endTimestampS": T,
    "Constants.clubDungeonStartTimestamp": T,  # the club weeks' origin (with clubDungeonDurationS)
    "PassportSeason.beginTimestamp": T,  # rewritten by passport.rotate_seasons (already real)
    "PassportSeason.endTimestamp": T,
    # real: battle, network and UI timings
    "ClubWar.inBattleTimeoutSeconds": R,
    "Constants.kothInBattleTimeoutSeconds": R,
    "Constants.expeditionDefaultBattleTimeout": R,
    "Constants.adRewardValidationTimeoutS": R,
    "Constants.platformAuthTimeoutS": R,
    "Constants.socialPvpMatchRpcTimeout": R,
    "Constants.battleBadConnectionMaxClockDriftS": R,
    "Constants.battleBadConnectionUpdateWaitS": R,
    "Constants.battleBadConnectionMinDurationS": R,
    "Constants.deathSlowMoPreDurationS": R,
    "Constants.deathSlowMoPostDurationS": R,
    "Constants.deathSlowMoTimeScale": R,
    "Constants.battleCatchupDurationS": R,
    "Constants.battleCatchupTimeoutDurationS": R,
    "Constants.battleAbilityCastTimeScale": R,
    "Constants.carouselChangeTime": R,
    # not times
    "BattleNode.firstTimeLoot": N,
    "EnergyConstants.timesToApplyGeneratedBonus": N,
    "Constants.timeSettingsChangesAllowed": N,
    "ClubWar.pointsPerBasePerTimeUnit": N,
    "StoreTabIds.limitedTimeArenaTab": N,
}
_DONE_ELSEWHERE = {"PassportSeason.beginTimestamp", "PassportSeason.endTimestamp"}  # passport.rotate_seasons


def _scaled(v: int | float) -> int | float:
    if isinstance(v, float):
        return v / clock.speed()
    return clock.duration_to_real(v)


def _real(v: int) -> int:
    return clock.to_real(v) if v > 0 else v


def scale_times(buf: bytearray) -> None:
    """Game durations / timestamps of the gamedata in real time (see module doc); nothing at speed 1 without an
    offset."""
    if clock.is_identity():
        return
    edits = [(k.split(".", 1), kind) for k, kind in GAMEDATA_FIELDS.items()
             if kind in (D, T) and k not in _DONE_ELSEWHERE]
    tables = flatbuf.tables_of(buf, "StaticGamedata", frozenset(t for (t, _), _ in edits))
    for (table, name), kind in edits:
        for pos in tables[table]:
            flatbuf.map_scalar(buf, pos, table, name, _scaled if kind is D else _real)


# --- delta (the multiplayer app rebuilds the served gamedata from the player's own copy) -------------------------

DELTA_MAGIC = b"AGD1"


def delta(original: bytes, served: bytes) -> bytes:
    """What turns `original` into `served`, without any of the original's content: the changed byte runs (in place)
    and what follows the original's end (the rewrites append their new strings there).

        "AGD1" | sha256(original) (32) | len(served) u32 | count u32 | count x (offset u32, length u32, bytes)

    Bytes of `served` no run covers are the original's at the same offset (served is never shorter: rewrites only
    edit in place and append). The client's own copy rebuilds it (`apply_delta`; the multiplayer app's proxy does
    the same), so a server that does not serve client files (Toggles.serve_client_files) still serves its changes."""
    if len(served) < len(original):
        raise ValueError("served gamedata shorter than the original")
    runs = []
    i, n = 0, len(original)
    while i < n:
        if original[i] != served[i]:
            j = i
            while j < n and original[j] != served[j]:
                j += 1
            runs.append((i, served[i:j]))
            i = j
        else:
            i += 1
    if len(served) > n:
        runs.append((n, served[n:]))
    out = bytearray(DELTA_MAGIC + hashlib.sha256(original).digest())
    out += struct.pack("<II", len(served), len(runs))
    for off, data in runs:
        out += struct.pack("<II", off, len(data)) + data
    return bytes(out)


MAX_GROWTH = 16 * 1024 * 1024  # a delta never makes the gamedata more than this much bigger


def apply_delta(original: bytes, d: bytes) -> bytes:
    """`served` from `original` and its `delta`. ValueError for a delta of another original, or one that is cut short,
    has bytes after its last run, a run outside the declared size, or a size beyond MAX_GROWTH (the same checks as
    the multiplayer app's applier)."""
    if len(d) < 44 or d[:4] != DELTA_MAGIC:
        raise ValueError("not a gamedata delta")
    if d[4:36] != hashlib.sha256(original).digest():
        raise ValueError("the gamedata delta is for another gamedata")
    size, count = struct.unpack_from("<II", d, 36)
    if size < len(original) or size > len(original) + MAX_GROWTH:
        raise ValueError(f"gamedata delta size {size} out of range")
    out = bytearray(original) + bytearray(size - len(original))
    pos = 44
    for _ in range(count):
        if pos + 8 > len(d):
            raise ValueError("gamedata delta cut short")
        off, length = struct.unpack_from("<II", d, pos)
        pos += 8
        if off + length > size or pos + length > len(d):
            raise ValueError("gamedata delta run out of range")
        out[off:off + length] = d[pos:pos + length]
        pos += length
    if pos != len(d):
        raise ValueError("bytes after the gamedata delta's last run")
    return bytes(out)


_DELTAS: "weakref.WeakKeyDictionary[Game, dict[str, bytes]]" = weakref.WeakKeyDictionary()


def delta_for(game: "Game", served: ServedGamedata) -> bytes:
    """The delta of a served variant, computed once per variant (CACHED_VERSIONS kept, like the variants)."""
    cache = _DELTAS.setdefault(game, {})
    if served.version not in cache:
        cache[served.version] = delta(passport.catalog(game).gamedata, served.data)
        while len(cache) > CACHED_VERSIONS:
            cache.pop(next(iter(cache)))
    return cache[served.version]
