"""Passholder seasons: served gamedata rotation, weekly quests, trackers, XP, tier rewards, buying tiers."""

from __future__ import annotations

import struct

import pytest

from arcane_server.app import GAME
from arcane_server.handlers import leaderboards
from arcane_server.handlers import passport as P
from arcane_server.inventory import grant_item, item_count
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.served_gamedata import served_gamedata

GRAND = 7495537894870835
GEMS = 31
NOW = 1798774345  # 2027-01-01 03:32 UTC, inside a served season of the gamedata-length rotation


def game(client):
    return client.http.app[GAME]


def player(client) -> pb.Player:
    return game(client).player(client.public_id)


@pytest.fixture
def clock(monkeypatch, client):
    """A fixed time inside a served season, and a player who reached PASSPORT_SEASON (level 10)."""
    t = {"now": NOW}
    monkeypatch.setattr(P, "_now", lambda: t["now"])
    player(client).level = 10
    game(client).save(client.public_id)
    return t


def seasonal(p: pb.Player) -> dict[int, pb.PlayerActivity]:
    return {a.definition_id: a for a in p.activities if a.type in P.SEASONAL_TYPES}


def served_windows(data: bytes, cat: P.Catalog) -> dict[int, tuple[int, int]]:
    out = {}
    for sid, t in cat.table_pos.items():
        out[sid] = tuple(struct.unpack_from("<I", data, P._fb_field(data, t, f))[0] for f in (P.F_BEGIN, P.F_END))
    return out


async def test_catalog_serves_reconstructed_seasons(client):
    cat = P.catalog(game(client))
    assert len(cat.seasons) >= 90
    assert all(r in ("quest text unknown", "previewImage bundle missing") for r in cat.rejected.values())
    by_name = {s.name_key: s for s in cat.seasons}
    s = by_name["PASSHOLDER_202304_2_SEASON_NAME"]
    w0 = {q.definition_id: q for q in s.weeks[0]}
    # the game's text + counts
    assert w0[502021085323252].name_key == "PASSPORT_2020_April_WEEK_0_1_NAME"
    assert w0[502021085323252].spec.tracker == 3724590359083860 and w0[502021085323252].spec.required == 5
    assert w0[7806259917153547].spec.kinds == ("hero_campaign_battle",) and w0[7806259917153547].spec.required == 25
    # the game's February text for the 2020-05 set
    f = {q.definition_id: q for q in by_name["PASSHOLDER_202005_1_SEASON_NAME"].weeks[0]}
    assert f[5236654759589975].desc_key == "PASSPORT_2020_February_WEEK_0_3_DESC" and f[5236654759589975].spec.required == 15
    assert f[8590789539818830].spec.kinds == ("daily_event_battle",) and f[8590789539818830].spec.required == 12


# Every passholder quest: (id, name, type, required value,
# deep link, sort order, reward counts)
OFFICIAL_PASSPORT_QUESTS = (
    (4515310606825679, 'PASSPORT_2020_April_WEEK_0_0_NAME', 7, 5, 3, 10, [250]),
    (502021085323252, 'PASSPORT_2020_April_WEEK_0_1_NAME', 7, 5, 3, 20, [250]),
    (211550947512149, 'PASSPORT_2020_April_WEEK_0_3_NAME', 7, 10, 3, 40, [250]),
    (7302084992106933, 'PASSPORT_2020_April_WEEK_0_4_NAME', 4, 5, 3, 50, [500]),
    (7806259917153547, 'PASSPORT_2020_April_WEEK_0_5_NAME', 4, 25, 3, 60, [500]),
    (3975619712751594, 'PASSPORT_2020_April_WEEK_1_0_NAME', 7, 5, 3, 1010, [250]),
    (1536742290282907, 'PASSPORT_2020_April_WEEK_1_1_NAME', 7, 5, 3, 1020, [250]),
    (878315224288419, 'PASSPORT_2020_April_WEEK_1_2_NAME', 7, 2, 1, 1030, [250]),
    (7232089473019890, 'PASSPORT_2020_April_WEEK_1_4_NAME', 4, 5, 3, 1050, [500]),
    (4817993953521388, 'PASSPORT_2020_April_WEEK_1_5_NAME', 4, 6, 1, 1060, [500]),
    (2372793331509910, 'PASSPORT_2020_April_WEEK_4_1_NAME', 7, 5, 3, 4020, [250]),
    (7880744559902544, 'PASSPORT_2020_April_WEEK_4_2_NAME', 7, 5, 3, 4030, [250]),
    (6921589373050420, 'PASSPORT_2020_April_WEEK_4_5_NAME', 4, 5, 3, 4060, [500]),
    (5236654759589975, 'PASSPORT_2020_February_WEEK_0_3_NAME', 7, 15, 3, 40, [250]),
    (8590789539818830, 'PASSPORT_2020_February_WEEK_0_4_NAME', 4, 12, 7, 50, [500]),
    (912469557428490, 'PASSPORT_2020_February_WEEK_0_5_NAME', 4, 25, 3, 60, [500]),
)


def test_passport_quests_match_the_official_server(client):
    """Each passholder quest: same required count, deep link, slot (sort order, free /
    Gold), XP reward; e.g. the enchanted gear quest needs 6."""
    cat = P.catalog(game(client))
    official = {i: pb.PlayerActivity(definition_id=i, name=name, type=t, required_value=req, deep_link_location=link,
                                     sort_order=order, rewards=[pb.InventoryItem(count=n) for n in rewards])
                for i, name, t, req, link, order, rewards in OFFICIAL_PASSPORT_QUESTS}
    assert len(official) >= 16
    checked = 0
    for qid, a in official.items():
        found = next((s.quest(qid) for s in cat.seasons if s.quest(qid)), None)
        if found is None:
            continue  # a set we don't serve
        w, i, q = found
        assert (q.name_key, q.spec.required, q.spec.deep_link) == (a.name, a.required_value, a.deep_link_location), q.desc_key
        assert w * 1000 + (i + 1) * 10 == a.sort_order, q.desc_key
        assert (i < P.FREE_SLOTS) == (a.type == pb.SEASONAL_FREE_PLAYER_ACTIVITY), q.desc_key
        assert [r.count for r in a.rewards] == [P.FREE_XP if i < P.FREE_SLOTS else P.GOLD_XP], q.desc_key
        checked += 1
    assert checked == len(official)
    assert P.spec_for("Equip Enchanted Gear Pieces").required == 6


async def test_quests_handed_out_with_an_older_count_are_conformed(client, clock):
    g = game(client)
    slot = P.current_slot(g, NOW)
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    p = player(client)
    a = next(iter(seasonal(p).values()))
    want = (a.required_value, a.deep_link_location)
    a.required_value, a.deep_link_location = want[0] + 4, 0
    assert P.refresh(_session(client)) is True
    a = seasonal(player(client))[a.definition_id]
    assert (a.required_value, a.deep_link_location) == want
    assert slot.season.quest(a.definition_id) is not None


def test_season_lengths_follow_gamedata(client):
    """Each season runs as long as its original window (2023-24: 1st..16th and 16th..1st), not len(weeks) x 7."""
    g = game(client)
    cat = P.catalog(g)
    rows = {int(r["id"]): r for r in g.gamedata.table("passportSeason")}
    by_name = {s.name_key: s for s in cat.seasons}
    assert by_name["PASSHOLDER_202312_2_SEASON_NAME"].duration == 16 * P.DAY  # 12/16 .. 1/1
    assert by_name["PASSHOLDER_202402_2_SEASON_NAME"].duration == 14 * P.DAY  # 2/16 .. 3/1 (leap year)
    assert by_name["PASSHOLDER_202004_SEASON_NAME"].duration == 40 * P.DAY  # 5 quest weeks
    for s in cat.seasons:
        r = rows[s.id]
        assert abs(s.duration - (int(r["endTimestamp"]) - int(r["beginTimestamp"]))) <= 3600
        assert s.duration > (len(s.weeks) - 1) * P.WEEK
    assert cat.cycle == sum(s.duration for s in cat.seasons)


def test_transition_keeps_the_running_season(client):
    """The season running at TRANSITION_AFTER keeps its old (weeks x 7) window; the gamedata-length rotation starts
    when it ends, with the next season, back to back."""
    g = game(client)
    cat = P.catalog(g)
    before = P.layout(cat, P.TRANSITION_AFTER)
    cur = before[0]
    assert cur.end - cur.begin + 1 == cur.season.legacy_duration and cur.end + 1 == cat.cut
    after = P.layout(cat, cat.cut)
    assert after[0].run == cur.run + 1 and after[0].begin == cat.cut
    assert after[0].end - after[0].begin + 1 == after[0].season.duration
    assert [(s.run, s.begin) for s in before[1:]] == [(s.run, s.begin) for s in after[:-1]]
    for a, b in zip(after, after[1:]):
        assert b.begin == a.end + 1 and b.season is cat.seasons[b.run % len(cat.seasons)]
    later = P.layout(cat, cat.cut + 5 * cat.cycle + 12345)[0]
    assert later.begin <= cat.cut + 5 * cat.cycle + 12345 <= later.end


def test_spec_rules():
    assert P.spec_for("Use the Magical Meteor Spell").tracker == P.TRACKER_MAGICAL_METEOR
    assert P.spec_for("Use Aladdin's Street Rat Strike Ability").tracker == 354625640707613
    assert P.spec_for("Damage Enemies with Aladdin's Basic Ability").required == 15
    assert P.spec_for("Complete PvP Arena or Sorcerer's Tournament Battles").kinds == ("pvp_battle", "tournament_battle")
    assert P.spec_for("Win a raid") is None


async def test_served_gamedata_has_exactly_one_active_season_and_rotates(client, clock):
    g = game(client)
    cat = P.catalog(g)
    base = str(client.http.make_url("")).rstrip("/")  # the address the test client reaches the server at
    served = served_gamedata(g, base, now=NOW)
    win = served_windows(served.data, cat)
    active = [sid for sid, (b, e) in win.items() if b <= NOW <= e]
    slot = P.current_slot(g, NOW)
    assert active == [slot.season.id]
    assert win[slot.season.id] == (slot.begin, slot.end) and slot.end - slot.begin + 1 == slot.season.duration
    # forward layout: every served season is current or upcoming, back to back
    starts = sorted(win[s.id][0] for s in cat.seasons)
    assert starts[0] == slot.begin and all(b > slot.begin for b in starts[1:])
    # only the timestamps changed (and the news URLs: served_gamedata.py, tests/test_news.py)
    assert sum(a != b for a, b in zip(cat.gamedata, served.data)) <= 8 * len(cat.seasons) + 4 * 16
    # next run: new version, the next season active, consistent with the old layout's window for it
    nxt = served_gamedata(g, base, now=slot.end + 1)
    assert nxt.version != served.version
    nslot = P.current_slot(g, slot.end + 1)
    assert served_windows(nxt.data, cat)[nslot.season.id] == win[nslot.season.id] == (nslot.begin, nslot.end)
    # meta + CDN serve the rotated gamedata
    meta = await client.http.post("/meta", data=pb.RequestEnvelope(
        client_version=client_version(), payload=pb.MetadataRequest().SerializeToString()).SerializeToString())
    version = pb.MetadataResponse.FromString(pb.ResponseEnvelope.FromString(await meta.read()).payload).gamedata_version
    assert version == served.version
    r = await client.http.get(f"/gamedata/{version}/gamedata-static.bin")
    assert await r.read() == served.data


def client_version() -> str:
    from conftest import CLIENT_VERSION

    return CLIENT_VERSION


async def test_season_start_and_week_quests_unlock_weekly(client, clock):
    g = game(client)
    slot = P.current_slot(g, NOW)
    clock["now"] = slot.begin + 3600
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    p = player(client)
    assert item_count(p, slot.season.passport_item) == 0 and item_count(p, slot.season.platinum_item) == 0  # bought
    acts = seasonal(p)
    assert set(acts) == {q.definition_id for q in slot.season.weeks[0]}
    a = acts[slot.season.weeks[0][1].definition_id]
    assert a.type == pb.SEASONAL_FREE_PLAYER_ACTIVITY and a.sort_order == 20 and a.telemetry_ref_id == slot.begin
    assert [(r.id, r.count) for r in a.rewards] == [(slot.season.xp_item, 250)]
    gold = acts[slot.season.weeks[0][5].definition_id]
    assert gold.type == pb.SEASONAL_PLAYER_ACTIVITY and gold.rewards[0].count == 500
    # week 2 unlocks after 7 days and is pushed to the client
    clock["now"] = slot.begin + P.WEEK + 1
    await client.call("home", pb.HomeRequest(), pb.HomeResponse)
    pushed = [pb.PlayerActivity.FromString(m.payload) for m in client.last_envelope.dynamic_messages
              if m.type == pb.PLAYER_ACTIVITY_DYNAMIC_MESSAGE]
    w1 = {q.definition_id for q in slot.season.weeks[1]}
    assert w1 <= {a.definition_id for a in pushed}
    assert w1 <= set(seasonal(player(client)))
    assert min(a.sort_order for a in pushed if a.definition_id in w1) == 1010


def own_passes(client, slot) -> None:
    grant_item(player(client), slot.season.passport_item, 1)
    grant_item(player(client), slot.season.platinum_item, 1)


async def test_claiming_quests_levels_up_and_pays_all_three_tracks(client, clock):
    g = game(client)
    slot = P.current_slot(g, NOW)
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    own_passes(client, slot)
    p = player(client)
    free = [a for a in seasonal(p).values() if a.type == pb.SEASONAL_FREE_PLAYER_ACTIVITY][:2]
    for a in free:
        a.current_value = a.required_value
    first = await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=free[0].definition_id),
                              pb.ClaimActivityResponse)
    assert not first.inventory_delta.HasField("passport_season_level_up")  # 250 XP: still tier 1
    res = await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=free[1].definition_id),
                            pb.ClaimActivityResponse)
    assert item_count(player(client), slot.season.xp_item) == 500
    got = {it.id: it.count for it in res.inventory_delta.passport_season_level_up.inventory_delta.items}
    expected: dict[int, int] = {}
    for track in slot.season.rewards[2]:
        for item_id, n in track:
            expected[item_id] = expected.get(item_id, 0) + n
    assert len(slot.season.rewards[2]) == 3 and all(slot.season.rewards[2])  # free, gold and platinum
    for item_id, n in expected.items():
        assert got.get(item_id) == n or item_id == 30  # player XP may be consumed by a player level-up
    # idempotent: no second payout for the same tier
    d = pb.InventoryDelta()
    P.apply_level_ups(_session(client), d)
    assert not d.HasField("passport_season_level_up")


def _session(client):
    from arcane_server.rpc import Session

    return Session(client.public_id, game(client))


async def test_buy_level_costs_gems_and_reaches_next_tier(client, clock):
    g = game(client)
    slot = P.current_slot(g, NOW)
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    own_passes(client, slot)
    grant_item(player(client), GEMS, 1000)
    gems = item_count(player(client), GEMS)
    res = await client.call("buy_passport_season_level", pb.BuyPassportSeasonLevelRequest(),
                            pb.BuyPassportSeasonLevelResponse)
    d = {it.id: it.count for it in res.inventory_delta.items}
    assert d[GEMS] == -100 and d[slot.season.xp_item] == 500
    assert res.inventory_delta.passport_season_level_up.inventory_delta.items
    assert item_count(player(client), GEMS) == gems - 100 + sum(
        n for track in slot.season.rewards[2] for i, n in track if i == GEMS)
    assert P.level_for(P.catalog(g), item_count(player(client), slot.season.xp_item)) == 2


async def test_campaign_battle_trackers_counted_quests_and_energy_xp(client, clock):
    g = game(client)
    slot = P.current_slot(g, NOW)
    clock["now"] = slot.begin + P.WEEK + 1  # week 2 has a Grand campaign battles quest
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    p = player(client)
    units = [u.definition_id for u in sorted(p.unit_inventory, key=lambda u: -u.power_rating)[:5]]
    req = pb.PveBattleStartRequest(campaign_identifier=pb.CampaignIdentifier(campaign_id=GRAND, map_index=1),
                                   units=units, leader_unit=units[0],
                                   squad_save=pb.BattleSquadSaveInfo(game_mode=1, slot=GRAND))
    start = await client.call("pve_battle_start", req, pb.PveBattleStartResponse)
    bs = pb.BattleLib_Bootstrap.FromString(start.bootstrap_bytes)
    human = [pl for pl in bs.players if pl.is_human][0]
    # (a leaderboard contest running at the real date adds its own quest's tracker: not the passport's)
    trackers = {t.activity_id: t.tracker_id for t in human.activity_trackers
                if t.activity_id not in leaderboards.quest_ids()}
    tracked = {q.definition_id: q.spec.tracker for w in slot.season.weeks for q in w if q.spec.tracker}
    assert trackers == tracked  # every in-battle quest of weeks 1-2, none of the others
    aid, tid = next(iter(trackers.items()))
    res = await client.call("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3, activity_results=[
        pb.BattleActivityResult(battle_player_id=1, activity_def_id=aid, activity_value=3, tracker_def_id=tid)]),
        pb.PveBattleEndResponse)
    acts = seasonal(player(client))
    assert acts[aid].current_value == 3
    grand_q = next(q for q in slot.season.weeks[1] if q.spec.kinds == ("grand_campaign_battle",))
    assert acts[grand_q.definition_id].current_value == 1
    xp = {it.id: it.count for it in res.inventory_delta.items}[slot.season.xp_item]
    assert xp == P.XP_PER_ENERGY * 8  # grand map 1 node 0 costs 8 grand energy


async def test_new_run_resets_progress(client, clock):
    g = game(client)
    slot = P.current_slot(g, NOW)
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    grant_item(player(client), slot.season.xp_item, 5000)
    grant_item(player(client), slot.season.passport_item, 1)
    # the same season comes back one full cycle later: XP and quests start over
    cat = P.catalog(g)
    clock["now"] = NOW + cat.cycle
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    p = player(client)
    assert P.current_slot(g, clock["now"]).season.id == slot.season.id
    assert item_count(p, slot.season.xp_item) == 0
    assert item_count(p, slot.season.passport_item) == 0  # a bought pass lasts one run
    quests = {q.definition_id: q for w in slot.season.weeks for q in w}
    assert all(a.current_value == 0 for a in seasonal(p).values() if not quests[a.definition_id].spec.state)
    # next season: previous quests are gone
    clock["now"] = slot.end + 1 + cat.cycle
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    nxt = P.current_slot(g, clock["now"]).season
    assert set(seasonal(player(client))) == {q.definition_id for q in nxt.weeks[0]}


async def test_locked_passport_gives_nothing(client, monkeypatch):
    """Before PASSPORT_SEASON (level 10) there is no season: no passes, quests, XP or tier rewards. A tier reward sent
    to a locked player made the client reload home every ~2 s (its level-up popup finds no active season, closes
    without consuming the pending level-up, and home asks for it again)."""
    monkeypatch.setattr(P, "_now", lambda: NOW)
    p = player(client)
    assert p.level < 10
    await client.call("home", pb.HomeRequest(), pb.HomeResponse)
    p = player(client)
    slot = P.current_slot(game(client), NOW)
    assert not seasonal(p) and item_count(p, slot.season.passport_item) == 0
    grant_item(p, GEMS, 0)
    res = await client.call("pve_battle_start", pb.PveBattleStartRequest(
        campaign_identifier=pb.CampaignIdentifier(campaign_id=GRAND, map_index=1), units=[u.definition_id for u in p.unit_inventory[:3]]),
        pb.PveBattleStartResponse)
    assert not any(t.activity_id not in leaderboards.quest_ids()  # contest trackers are not the passport's
                   for h in pb.BattleLib_Bootstrap.FromString(res.bootstrap_bytes).players for t in h.activity_trackers)
    end = await client.call("pve_battle_end", pb.PveBattleEndRequest(win=True, star_level=3), pb.PveBattleEndResponse)
    assert not end.inventory_delta.HasField("passport_season_level_up")
    assert item_count(player(client), slot.season.xp_item) == 0


# --- passes bought in the store (toggle free_passport_passes off) ------------------------------------------------


def _pass_items(store: pb.StoreResponse) -> dict[str, pb.StoreItem]:
    return {it.name_key: it for t in store.tabs for it in t.items if P.is_pass_store_item(it)}


async def test_free_track_only_without_a_pass_then_buying_gold_pays_the_backlog(client, clock):
    g = game(client)
    slot = P.current_slot(g, NOW)
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    grant_item(player(client), slot.season.xp_item, P.catalog(g).xp_required[5])  # tier 5
    d = pb.InventoryDelta()
    P.apply_level_ups(_session(client), d)
    got = {it.id: it.count for it in d.passport_season_level_up.inventory_delta.items}
    free = {}
    for lv in range(2, 6):
        for i, n in slot.season.rewards[lv][0]:
            free[i] = free.get(i, 0) + n
    assert all(got.get(i) == n for i, n in free.items() if i != 30)
    gold_only = {i for lv in range(2, 6) for i, _ in slot.season.rewards[lv][1]} - set(free)
    assert not gold_only & set(got)  # no Gold rewards without Gold

    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    items = _pass_items(store)
    gold = items["STORE_ITEM_PASSHOLDER_NAME"]
    assert (gold.cost.item_id, gold.cost.count) == (GEMS, 1000)
    assert {c.item_id for c in gold.item_counts} >= {slot.season.passport_item}  # this season's pass, not season 14's
    assert P.ORIGINAL_GOLD not in {c.item_id for c in gold.item_counts} or slot.season.passport_item == P.ORIGINAL_GOLD
    assert gold.subtitle_key == slot.season.name_key and gold.expiry == slot.end
    lim = gold.purchase_limits.purchase_data[0]
    assert (lim.count, lim.remaining_purchases) == (0, 1)
    assert items["STORE_ITEM_PASSHOLDER_BOOSTER_NAME"].cost.count == 2000
    p = player(client)
    grant_item(p, GEMS, 5000)
    gems = item_count(p, GEMS)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=gold.id), pb.BuyStoreItemResponse)
    assert item_count(player(client), slot.season.passport_item) == 1
    backlog = {it.id: it.count for it in res.inventory_delta.passport_season_level_up.inventory_delta.items}
    for i, n in slot.season.rewards[3][1]:
        assert backlog.get(i, 0) >= n or i == 30  # the Gold rewards of the tiers already reached
    gold_gems = sum(n for lv in range(2, 6) for i, n in slot.season.rewards[lv][1] if i == GEMS)
    assert item_count(player(client), GEMS) == gems - 1000 + 200 + gold_gems  # the pack's 200 gems
    assert res.purchase_limits.purchase_data[0].count == 1  # 0 / 1 available
    again = await client.call_raw("buy_store_item", pb.BuyStoreItemRequest(store_item_id=gold.id))
    assert again.response_code == pb.BAD_REQUEST


async def test_platinum_needs_level_and_becomes_an_upgrade_after_gold(client, clock):
    g = game(client)
    slot = P.current_slot(g, NOW)
    assert slot.season.platinum_item and slot.season.platinum_level == 30
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    player(client).level = 29
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert "PASSHOLDER_PLATINUM_NAME" not in _pass_items(store)  # below platinumLevelRequirement
    player(client).level = 30
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    items = _pass_items(store)
    plat, booster = items["PASSHOLDER_PLATINUM_NAME"], items["PASSHOLDER_PLATINUM_BOOSTER_NAME"]
    # as in the game (season 13), the season's passes
    # in place of season 13's
    assert (plat.id, plat.cost.item_id, plat.cost.count) == (P.PLATINUM_STORE_ID, GEMS, 3000)
    assert plat.main_image == "store_pouch_2x_pass_gold_platinum/pouch_2x_pass_gold_platinum"
    assert [(c.item_id, c.count_min) for c in plat.item_counts] == [
        (GEMS, 500), (slot.season.platinum_item, 1), (6463010382463932, 100), (6490301028561825, 3),
        (slot.season.passport_item, 1)]
    assert (booster.id, booster.cost.count) == (P.PLATINUM_BOOSTER_STORE_ID, 5000)
    assert booster.main_image == "store_pouch_2x_pass_gold_platinum_xp/pouch_2x_pass_gold_platinum_xp"
    assert [(c.item_id, c.count_min) for c in booster.item_counts] == [
        (13, 1000000), (30, 1000), (GEMS, 1000), (32395651401654, 1), (slot.season.platinum_item, 1),
        (6463010382463932, 100), (6490301028561825, 3), (P.GENERIC_XP, 7500), (slot.season.passport_item, 1)]
    tab = next(t for t in store.tabs if any(P.is_pass_store_item(it) for it in t.items))
    assert [it.name_key for it in tab.items if P.is_pass_store_item(it)] == [
        "PASSHOLDER_PLATINUM_BOOSTER_NAME", "PASSHOLDER_PLATINUM_NAME", "STORE_ITEM_PASSHOLDER_BOOSTER_NAME",
        "STORE_ITEM_PASSHOLDER_NAME"]  # in this order
    assert not plat.iap_product_id_android and not booster.iap_product_id_android
    grant_item(player(client), slot.season.passport_item, 1)  # has Gold: the upgrade
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    up = _pass_items(store)["PASSHOLDER_PLATINUM_UPGRADE_NAME"]
    assert up.id == P.PLATINUM_STORE_ID and up.cost.count == P.PLATINUM_UPGRADE_GEMS
    assert slot.season.passport_item not in [c.item_id for c in up.item_counts]
    assert slot.season.platinum_item in [c.item_id for c in up.item_counts]
    booster = _pass_items(store)["PASSHOLDER_PLATINUM_BOOSTER_NAME"]
    assert booster.cost.count == 5000 and slot.season.passport_item not in [c.item_id for c in booster.item_counts]
    grant_item(player(client), GEMS, 2000)
    gems = item_count(player(client), GEMS)
    await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=up.id), pb.BuyStoreItemResponse)
    assert item_count(player(client), slot.season.platinum_item) == 1
    assert item_count(player(client), GEMS) >= gems - 2000 + 500  # the pack's 500 gems (+ any Platinum tier gems)
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    for name in ("PASSHOLDER_PLATINUM_NAME", "PASSHOLDER_PLATINUM_BOOSTER_NAME"):
        assert _pass_items(store)[name].purchase_limits.purchase_data[0].count == 1  # owned: 0 / 1 left


async def test_booster_xp_becomes_season_xp(client, clock):
    g = game(client)
    slot = P.current_slot(g, NOW)
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    booster = _pass_items(store)["STORE_ITEM_PASSHOLDER_BOOSTER_NAME"]
    grant_item(player(client), GEMS, 2000)
    res = await client.call("buy_store_item", pb.BuyStoreItemRequest(store_item_id=booster.id), pb.BuyStoreItemResponse)
    d = {it.id: it.count for it in res.inventory_delta.items}
    assert d[slot.season.xp_item] == 5000 and P.GENERIC_XP not in d
    assert item_count(player(client), P.GENERIC_XP) == 0 and item_count(player(client), slot.season.passport_item) == 1
    assert res.inventory_delta.passport_season_level_up.inventory_delta.items  # tiers 2..10 with Gold


async def test_gold_quests_need_gold(client, clock):
    g = game(client)
    slot = P.current_slot(g, NOW)
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    a = next(a for a in seasonal(player(client)).values() if a.type == pb.SEASONAL_PLAYER_ACTIVITY)
    a.current_value = a.required_value
    no = await client.call_raw("claim_activity", pb.ClaimActivityRequest(definition_id=a.definition_id))
    assert no.response_code == pb.BAD_REQUEST
    grant_item(player(client), slot.season.passport_item, 1)
    await client.call("claim_activity", pb.ClaimActivityRequest(definition_id=a.definition_id), pb.ClaimActivityResponse)


async def test_free_passport_passes_toggle_grants_both_each_run(client, clock):
    import dataclasses

    g = game(client)
    g.settings = dataclasses.replace(g.settings, toggles=dataclasses.replace(g.settings.toggles, free_passport_passes=True))
    slot = P.current_slot(g, NOW)
    await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)
    p = player(client)
    assert item_count(p, slot.season.passport_item) == 1 and item_count(p, slot.season.platinum_item) == 1
    store = await client.call("store", pb.StoreRequest(), pb.StoreResponse)
    assert not _pass_items(store)  # nothing to sell
