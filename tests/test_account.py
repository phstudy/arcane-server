"""Accounts: new-account state, stat/power formulas vs the game's numbers, login normalization, profile
RPCs, and the player import tool."""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import pytest

from arcane_server import energy
from arcane_server import game as g
from arcane_server.app import GAME
from arcane_server.config import PROJECT_ROOT, load_settings
from arcane_server.db import Database
from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb

sys.path.insert(0, str(PROJECT_ROOT / "tools"))
import import_player  # noqa: E402

from official_units import MULAN, OFFICIAL_SPELL_POWER, official_units  # noqa: E402

from arcane_server import accounts  # noqa: E402

EXPORT_ID, EXPORT_NAME = "0000B001", "Player1"
EXPORTED_AT = 1_605_000_000  # 2020-11-10


@pytest.fixture(scope="module")
def gd() -> Gamedata:
    from conftest import require_client_data

    require_client_data()
    return Gamedata(load_settings().gamedata_json)


def export_file(tmp: Path) -> Path:
    """A profile export of a hand-built account (the game's units, three spells)."""
    p = pb.Player(id=EXPORT_ID, username=EXPORT_NAME, level=50, creation_timestamp=1_590_000_000)
    p.unit_inventory.extend(official_units())
    for i, (lv, power) in enumerate(OFFICIAL_SPELL_POWER.items()):
        p.spell_inventory.add(definition_id=i + 1, level=lv, power_rating=power)
    out = tmp / f"{EXPORT_ID}.json"
    out.write_bytes(accounts.export_json(p, EXPORTED_AT))
    return out


# --- formulas ----------------------------------------------------------------------------------


def test_power_rating_matches_the_official_server(gd):
    for u in official_units():
        assert g.unit_power_rating(gd, u) == u.power_rating, u.definition_id
    for lv, power in OFFICIAL_SPELL_POWER.items():
        assert g.spell_power_rating(gd, lv) == power


def test_unit_stats_match_the_official_server(gd):
    fields = ("offense", "defense", "health", "recovery", "speed", "crit_chance", "crit_power", "potency",
              "tenacity", "accuracy", "evasion")
    for cu in official_units():
        u = pb.Unit()
        u.CopyFrom(cu)
        g.compute_unit(gd, u)
        assert all(abs(getattr(u, f) - getattr(cu, f)) < 1e-3 for f in fields), cu.definition_id
    mulan = next(u for u in official_units() if u.definition_id == MULAN)  # L41 R5 T5 + speed stone
    calc = g.compute_unit(gd, pb.Unit.FromString(mulan.SerializeToString()))
    assert (calc.offense, calc.defense, calc.health) == (mulan.offense, mulan.defense, mulan.health)


def test_initial_ability_levels_indexed_by_ability_id(gd):
    mulan = gd.by_id("unit")[MULAN]
    levels = g.initial_ability_levels(mulan, 1)
    assert len(levels) == max(a["id"] for a in mulan["abilities"]) + 1
    for a in mulan["abilities"]:
        assert levels[a["id"]] == (1 if a["levels"][0]["requirements"]["gearTier"] <= 1 else 0)


# --- new account -------------------------------------------------------------------------------


async def test_new_account_state(client, gd):
    p = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    now = int(time.time())
    assert p.id == client.public_id
    assert p.age_gate_status == pb.PASSED_AGE_GATE
    assert {u.definition_id for u in p.unit_inventory} == {u["id"] for u in g.playable_units(gd)}
    assert len(p.unit_inventory) > 150
    # (tests start past the tutorial: skip_tutorial levels Mickey and tiers up Ariel)
    assert all(u.level >= 1 and u.gear_tier >= 1 and u.health > 0 and u.power_rating > 0 for u in p.unit_inventory)
    assert len(p.spell_inventory) == len(g.playable_spells(gd))
    assert now < p.day_end_timestamp <= now + 86400 + 3600
    assert p.current_calendar_date.year >= 2026
    tutorial = gd.single("constants")["tutorialBattle"]["campaign"]
    assert any(cp.campaign_identifier.campaign_id == tutorial and cp.star_level == 3 for cp in p.campaign_progress)
    assert set(p.unlocked_contextual_message_group_ids) >= set(gd.single("constants")["tutorialSkipInfo"]["messagesToShow"])
    ids = g.lockable_feature_ids()
    assert ids["GRAND_CAMPAIGN"] in p.unlocked_features and ids["PVP"] not in p.unlocked_features
    assert list(p.disabled_features) == sorted(ids[f] for f in g.DISABLED_FEATURES)
    energies = {ec["inventoryItem"] for ec in g.energy_constants(gd)}
    assert {t.item_id for t in p.energy_trackers} == energies
    assert all(now - 5 <= t.last_generated_timestamp <= now for t in p.energy_trackers)
    counts = {i.id: i.count for i in p.item_inventory}
    assert counts[13] > g.NEW_ACCOUNT_GOLD and counts[31] > g.NEW_ACCOUNT_GEMS  # + the skipped tutorial's rewards
    pve = gd.single("constants")["energyIds"]["pve"]["itemId"]
    assert counts[pve] == g.energy_cap(next(e for e in g.energy_constants(gd) if e["inventoryItem"] == pve), 1)


# --- normalization -----------------------------------------------------------------------------


def test_normalize_stale_account(gd):
    """An account last seen days ago: a new day, its daily counters reset."""
    old = int(time.time()) - 5 * 86400
    p = g.new_player(gd, "STALE001", old, "Asia/Shanghai")
    p.daily_login_status.today_claimed = True
    p.pvp_score.daily_battle_count = 3
    next(t for t in p.energy_trackers if t.item_id == 2694745420183802).daily_refreshes_purchased = 2
    now = int(time.time())
    assert g.normalize_player(gd, p, now, "Asia/Shanghai") is True
    start, end, local = g.local_day(now, "Asia/Shanghai")
    assert p.day_end_timestamp == end and (end - start) in (82800, 86400, 90000)
    assert (p.current_calendar_date.year, p.current_calendar_date.month, p.current_calendar_date.day) == (local.year, local.month, local.day)
    assert p.pvp_score.daily_battle_count == 0 and p.pvp_score.daily_battle_reset_time == end
    assert not p.daily_login_status.today_claimed
    pve = next(t for t in p.energy_trackers if t.item_id == 2694745420183802)
    assert pve.daily_refreshes_purchased == 0 and all(start <= d.start_timestamp < end for d in pve.daily_gifts)
    assert pve.last_generated_timestamp <= now
    # idempotent within the day
    before = p.SerializeToString()
    assert g.normalize_player(gd, p, now, "Asia/Shanghai") is False
    assert p.SerializeToString() == before


def test_energy_regen(gd):
    p = g.new_player(gd, "E", 1_000_000_000, "UTC")
    ec = next(e for e in g.energy_constants(gd) if e["inventoryItem"] == 2694745420183802)
    item = next(i for i in p.item_inventory if i.id == ec["inventoryItem"])
    item.count = 0
    tracker = g.energy_tracker(p, item.id)
    t0 = tracker.last_generated_timestamp
    freq = ec["generatedFrequencySeconds"]
    first = energy.next_tick(t0, freq)  # ticks fall at multiples of freq in the UTC day
    g.regen_energy(gd, p, first + 2 * freq + 5)
    assert item.count == 3 and tracker.last_generated_timestamp == first + 2 * freq
    g.regen_energy(gd, p, t0 + 10_000 * freq)
    assert item.count == g.energy_cap(ec, p.level)


# --- RPCs --------------------------------------------------------------------------------------


async def test_profile_rpcs(client):
    await client.call("update_player_profile", pb.UpdatePlayerProfileRequest(new_username="Mickey", new_avatar_id=2907476833071169),
                      pb.UpdatePlayerProfileResponse)
    await client.call("update_player_availability", pb.UpdatePlayerAvailabilityRequest(status=pb.PLAYER_TEMP_UNAVAILABLE),
                      pb.UpdatePlayerAvailabilityResponse)
    await client.call("age_gate", pb.AgeGateRequest(age=30), pb.AgeGateResponse)
    await client.call("skip_tutorial", pb.SkipTutorialRequest(), pb.SkipTutorialResponse)
    await client.call("dismiss_contextual_message", pb.DismissContextualMessageRequest(message_group_id=2350740263449760),
                      pb.DismissContextualMessageResponse)
    await client.call("set_active_benefits_are_visible", pb.SetActiveBenefitsAreVisibleRequest(are_active_benefits_visible=True),
                      pb.SetActiveBenefitsAreVisibleResponse)
    await client.call("set_last_known_email_connect_state", pb.SetLastKnownEmailConnectStateRequest(state=2),
                      pb.SetLastKnownEmailConnectStateResponse)
    await client.call("update_receive_player_online_popups_status",
                      pb.UpdateReceivePlayerOnlinePopupsStatusRequest(status=pb.RECEIVE_DISABLED),
                      pb.UpdateReceivePlayerOnlinePopupsStatusResponse)
    ts = await client.call("update_player_time_settings", pb.UpdatePlayerTimeSettingsRequest(koth_payout_custom_time_offset=20),
                           pb.UpdatePlayerTimeSettingsResponse)
    assert ts.time_settings_changed_count == 1 and ts.koth_payout_timestamp > time.time()

    p = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    assert p.username == "Mickey" and p.avatar_id == 2907476833071169
    assert p.availibility_status == pb.PLAYER_TEMP_UNAVAILABLE
    assert p.are_active_benefits_visible and p.last_known_email_connect_state == 2
    assert p.receive_player_online_popups == pb.RECEIVE_DISABLED
    assert p.koth_payout_custom_time_offset == 20

    bad = await client.call_raw("update_player_profile", pb.UpdatePlayerProfileRequest(new_username="x" * 40))
    assert bad.response_code == pb.BAD_REQUEST


async def test_squad_selection(client):
    p = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    units = [u.definition_id for u in p.unit_inventory[:5]]
    spells = [s.definition_id for s in p.spell_inventory[:2]]
    sel = pb.PlayerSquadSelection(game_mode=8, unit_ids=units, spell_ids=spells, leader_unit_id=units[0])
    await client.call("set_squad_selection", pb.SetPlayerSquadSelectionRequest(squad_selection=sel), pb.SetPlayerSquadSelectionResponse)
    sel2 = pb.PlayerSquadSelection(game_mode=8, unit_ids=units[::-1], spell_ids=spells, leader_unit_id=units[1])
    await client.call("set_squad_selection", pb.SetPlayerSquadSelectionRequest(squad_selection=sel2), pb.SetPlayerSquadSelectionResponse)
    p = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    squads = [s for s in p.squad_selections if s.game_mode == 8]
    assert len(squads) == 1 and squads[0] == sel2
    bad = await client.call_raw("set_squad_selection", pb.SetPlayerSquadSelectionRequest(
        squad_selection=pb.PlayerSquadSelection(game_mode=8, unit_ids=[123])))
    assert bad.response_code == pb.BAD_REQUEST


async def test_player_profile(client):
    res = await client.call("player_profile", pb.PlayerProfileRequest(id=client.public_id, include_player=True), pb.PlayerProfileResponse)
    assert res.player.id == client.public_id and res.player.unit_inventory
    assert res.player.unit_inventory[0].offense == 0 and res.player.unit_inventory[0].power_rating > 0
    assert not res.player.energy_trackers
    assert [s.stat_id for s in res.stats] == [36, 37]  # as the game answers player_profile
    missing = await client.call_raw("player_profile", pb.PlayerProfileRequest(id="NOPE0000"))
    assert missing.response_code == pb.NOT_FOUND


async def test_energy_refresh_and_gift(client, server):
    pve = 2694745420183802
    gems = {i.id: i.count for i in (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player.item_inventory}[31]
    res = await client.call("energy_refresh", pb.EnergyRefreshRequest(energy_item_id=pve), pb.EnergyRefreshResponse)
    assert res.daily_purchases == 1 and res.energy_item_id == pve
    # 120 refresh grant; VIP would add perRefreshBonus 10 (new accounts are not VIP)
    assert [(i.id, i.count) for i in res.inventory_delta.items] == [(pve, 120), (31, -50)]
    p = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    assert {i.id: i.count for i in p.item_inventory}[31] == gems - 50
    # no gift window open (unless the test happens to run inside one): either OK or BAD_REQUEST, never a crash
    r = await client.call_raw("claim_energy_gift", pb.ClaimDailyEnergyGiftRequest(energy_item_id=pve))
    assert r.response_code in (pb.OK, pb.BAD_REQUEST)


# --- import tool -------------------------------------------------------------------------------


def test_import_export_and_claim(tmp_path, gd):
    db = Database(tmp_path / "db.sqlite3")
    export = export_file(tmp_path)
    players = accounts.read_players(export, None, False)
    assert accounts.import_players(db, gd, players, replace=False).imported == [EXPORT_ID]
    assert accounts.import_players(db, gd, accounts.read_players(export, None, False), replace=False).imported == []
    p = db.load_player(EXPORT_ID)
    assert p.username == EXPORT_NAME and len(p.unit_inventory) == len(official_units())
    assert p.day_end_timestamp > time.time()
    phone = db.create_account("phone-anon-id")
    assert import_player.claim(db, EXPORT_ID, None, latest=True) == "phone-anon-id"
    assert db.account_by_anon_id("phone-anon-id").public_id == EXPORT_ID
    assert db.account_by_anon_id("phone-anon-id").public_id != phone.public_id


async def test_claimed_account_logs_in(server, tmp_path, gd, settings):
    """E2E: an imported account bound to a device's anon_id is what that device gets on its next login."""
    from conftest import GameClient

    db = Database(settings.db_path)
    accounts.import_players(db, gd, accounts.read_players(export_file(tmp_path), None, False), replace=False)
    phone = await GameClient(server, "phone-1").login()
    assert phone.public_id != EXPORT_ID
    await phone.ws.close()
    import_player.claim(db, EXPORT_ID, "phone-1", latest=False)
    phone = await GameClient(server, "phone-1").login()
    try:
        assert phone.public_id == EXPORT_ID
        p = (await phone.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
        assert p.username == EXPORT_NAME and p.day_end_timestamp > time.time()
    finally:
        await phone.ws.close()


async def test_new_account_is_not_vip(client):
    p = (await client.call("player", pb.PlayerRequest(), pb.PlayerResponse)).player
    assert p.vip_expire_timestamp == 0  # VIP only from a VIP card bought in the store (arcane_server.vip)


def test_vip_forever_toggle_keeps_vip_at_7_days(gd):
    now = int(time.time())
    assert g.new_player(gd, "NOVIP", now).vip_expire_timestamp == 0
    p = g.new_player(gd, "VIP", now, vip_forever=True)
    assert now + 7 * 86400 < p.vip_expire_timestamp <= now + 8 * 86400 + 3600


def test_club_without_valid_avatar_gets_a_pin(gd):
    # the client's profile view crashes when a club name comes with a non-pin avatar id
    p = g.new_player(gd, "CLUBTEST", int(time.time()))
    p.club_id, p.club_name, p.club_avatar_id = "0000C001", "Test Club", 0
    g.normalize_player(gd, p, int(time.time()))
    assert gd.by_id("inventoryItem")[p.club_avatar_id]["type"] == "LIMITED_PIN"
    p.club_avatar_id = 4983552140671558  # a pin avatar is kept
    g.normalize_player(gd, p, int(time.time()))
    assert p.club_avatar_id == 4983552140671558


async def test_new_account_profile_has_a_pvp_score(client):
    # the profile view and the PvP modes screen read player.pvp_score unconditionally (crashed on a fresh account)
    res = await client.call("player_profile", pb.PlayerProfileRequest(id=client.public_id, include_player=True),
                            pb.PlayerProfileResponse)
    assert res.player.HasField("pvp_score")


@pytest.mark.requires_client_data
def test_real_new_accounts_own_only_the_tutorial_battle_heroes(monkeypatch):
    from arcane_server import game as g
    from arcane_server.config import load_settings
    from arcane_server.gamedata import Gamedata

    monkeypatch.setattr(g, "NEW_ACCOUNT_ALL_UNITS", False)
    gd = Gamedata(load_settings().gamedata_json)
    p = g.new_player(gd, "TEST0001", 1794916800)
    names = {gd.by_id("unit")[u.definition_id]["nameKey"] for u in p.unit_inventory}
    spells = {gd.by_id("spell")[s.definition_id]["nameKey"] for s in p.spell_inventory}
    assert names == {"SORCERERSAPPRENTICEMICKEY_UNIT_NAME", "ARIEL_UNIT_NAME"}  # the rest comes in the tutorial
    assert spells == set()


@pytest.mark.requires_client_data
def test_pvp_score_is_always_present():
    """The client's PvP modes screen dereferences Player.pvp_score: imported profiles without one get it."""
    gd = Gamedata(load_settings().gamedata_json)
    p = pb.Player(id="X", level=30)
    g.normalize_player(gd, p, 1_700_000_000)
    assert p.HasField("pvp_score")


async def test_payout_time_changes_twice_per_365_day_period(client):
    """gamedata timeSettingsChangesAllowed = 2 per timeSettingsChangesPeriodDurationDays = 365 (twice a year)."""
    gd = client.http.app[GAME].gamedata
    for n in (1, 2):
        ts = await client.call("update_player_time_settings", pb.UpdatePlayerTimeSettingsRequest(
            koth_payout_custom_time_offset=20), pb.UpdatePlayerTimeSettingsResponse)
        assert ts.time_settings_changed_count == n
    third = await client.call_raw("update_player_time_settings",
                                  pb.UpdatePlayerTimeSettingsRequest(koth_payout_custom_time_offset=20))
    assert third.response_code == pb.BAD_REQUEST
    p = client.http.app[GAME].player(client.public_id)
    created, day = int(p.creation_timestamp), 86400
    g.roll_time_settings_period(gd, p, created + 100 * day, created + 364 * day)  # same period
    assert p.time_settings_changed_count == 2
    g.roll_time_settings_period(gd, p, created + 364 * day, created + 366 * day)  # next period
    assert p.time_settings_changed_count == 0


@pytest.mark.requires_client_data
def test_import_drops_content_the_client_does_not_know():
    """A backup from a later client (v29: Pumbaa, Timon, Nala, new items) keeps only what this gamedata defines;
    squads lose the unknown units and get a known leader."""
    from arcane_server import accounts

    gd = Gamedata(load_settings().gamedata_json)
    known_unit = next(iter(gd.by_id("unit")))
    known_item = next(iter(gd.by_id("inventoryItem")))
    unknown = 999_999_999_999
    p = pb.Player()
    p.unit_inventory.add(definition_id=known_unit)
    p.unit_inventory.add(definition_id=unknown)
    p.item_inventory.add(id=known_item, count=1)
    p.item_inventory.add(id=unknown, count=5)
    p.squad_selections.add(unit_ids=[unknown, known_unit], leader_unit_id=unknown)
    dropped = accounts.drop_unknown_content(gd, p)
    assert len(dropped) == 2
    assert [u.definition_id for u in p.unit_inventory] == [known_unit]
    assert [i.id for i in p.item_inventory] == [known_item]
    assert list(p.squad_selections[0].unit_ids) == [known_unit] and p.squad_selections[0].leader_unit_id == known_unit


def test_population_player_exports_import_whole():
    """A generated player saved as a profile export file keeps every unit, spell and item through the importer."""
    from arcane_server import accounts, population
    from conftest import archived_player_file, require_client_data

    require_client_data()
    gd = Gamedata.shared(load_settings().gamedata_json)
    population.install(population.generate(gd, 7))
    newest = max(population.players(), key=lambda e: e["player"]["level"])
    p = accounts.read_players(archived_player_file(newest["player"]["id"]), None, False)[0]
    assert len(p.unit_inventory) == len(newest["player"]["unitInventory"])
    assert accounts.drop_unknown_content(gd, p) == []


# --- Settings > Link Device ------------------------------------------------------------------------------------------


async def test_link_device_lets_the_secondary_device_play_the_primary_account(server):
    from conftest import GameClient

    primary = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    secondary = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    try:
        gen = await primary.call("generate_account_link_code", pb.GenerateAccountLinkCodeRequest(),
                                 pb.GenerateAccountLinkCodeResponse)
        assert gen.account_link_code and gen.code_expiration_timestamp > time.time()  # the code and its timer
        bad = await secondary.call_raw("enter_account_link_code", pb.EnterAccountLinkCodeRequest(account_link_code="ARCXXXXXX"))
        assert bad.response_code == pb.ACCOUNT_LINK_CODE_DOES_NOT_EXIST
        own = await primary.call_raw("enter_account_link_code", pb.EnterAccountLinkCodeRequest(account_link_code=gen.account_link_code))
        assert own.response_code == pb.ACCOUNT_LINK_CODE_DOES_NOT_EXIST  # not on the primary itself
        entered = await secondary.call("enter_account_link_code", pb.EnterAccountLinkCodeRequest(
            account_link_code=gen.account_link_code.lower()), pb.EnterAccountLinkCodeResponse)
        assert entered.account_link_verify_code and entered.verify_code_expiration_timestamp > time.time()
        push = await primary.next_push()  # the primary shows its verification code input
        assert push.type == pb.ACCOUNT_LINK_CODE_ENTERED_DYNAMIC_MESSAGE
        wrong = await primary.call_raw("verify_account_link_code", pb.VerifyAccountLinkCodeRequest(
            account_link_code=gen.account_link_code, account_link_verify_code="ZZZZZZ"))
        assert wrong.response_code == pb.ACCOUNT_LINK_VERIFY_CODE_DOES_NOT_EXIST
        await primary.call("verify_account_link_code", pb.VerifyAccountLinkCodeRequest(
            account_link_code=gen.account_link_code, account_link_verify_code=entered.account_link_verify_code),
            pb.VerifyAccountLinkCodeResponse)
        push = await secondary.next_push()
        assert push.type == pb.ACCOUNT_LINK_CODE_VERIFIED_DYNAMIC_MESSAGE
        new_anon = pb.AccountLinkCodeVerifiedDynamicMessage.FromString(push.payload).new_anon_id
        assert new_anon == primary.anon_id  # the secondary keeps it as its device id ...
        relaunched = await GameClient(server, new_anon).login()  # ... and logs in to the primary's account
        assert relaunched.public_id == primary.public_id
        await relaunched.ws.close()
        again = await primary.call_raw("verify_account_link_code", pb.VerifyAccountLinkCodeRequest(
            account_link_code=gen.account_link_code, account_link_verify_code=entered.account_link_verify_code))
        assert again.response_code == pb.ACCOUNT_LINK_CODE_DOES_NOT_EXIST  # used
        # a link code is not an admin claim code: renaming to it moves nothing
        gen2 = await primary.call("generate_account_link_code", pb.GenerateAccountLinkCodeRequest(),
                                  pb.GenerateAccountLinkCodeResponse)
        renamed = await secondary.call_raw("update_player_profile", pb.UpdatePlayerProfileRequest(new_username=gen2.account_link_code))
        assert renamed.response_code == pb.BAD_REQUEST
    finally:
        await primary.ws.close()
        await secondary.ws.close()


async def test_wrong_link_codes_are_throttled(server):
    import time_machine
    from conftest import GameClient

    from arcane_server import attempts

    primary = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    secondary = await GameClient(server, "test-" + uuid.uuid4().hex).login()
    try:
        gen = await primary.call("generate_account_link_code", pb.GenerateAccountLinkCodeRequest(),
                                 pb.GenerateAccountLinkCodeResponse)
        for _ in range(attempts.MAX_FAILURES):
            env = await secondary.call_raw("enter_account_link_code", pb.EnterAccountLinkCodeRequest(account_link_code="ARCGUESS2"))
            assert env.response_code == pb.ACCOUNT_LINK_CODE_DOES_NOT_EXIST
        env = await secondary.call_raw("enter_account_link_code", pb.EnterAccountLinkCodeRequest(
            account_link_code=gen.account_link_code))
        assert env.response_code == pb.ACCOUNT_LINK_CODE_DOES_NOT_EXIST  # blocked: the real code too
        assert not primary.pushes
        with time_machine.travel(time.time() + attempts.WINDOW_S + 1, tick=False):
            gen = await primary.call("generate_account_link_code", pb.GenerateAccountLinkCodeRequest(),
                                     pb.GenerateAccountLinkCodeResponse)
            await secondary.call("enter_account_link_code", pb.EnterAccountLinkCodeRequest(
                account_link_code=gen.account_link_code), pb.EnterAccountLinkCodeResponse)
    finally:
        await primary.ws.close()
        await secondary.ws.close()
