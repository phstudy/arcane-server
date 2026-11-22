"""Raid chest cards (handlers/raids.chest_groups) come from each reward's structured fields (tier tag, region, kind),
and group exactly as recorded in tests/fixtures/raid_chest_groups.json: [draws, [[item, count, guaranteed], ...]] per
group, per tier, per raid content file."""

from __future__ import annotations

import json
from pathlib import Path

from arcane_server.handlers import raids as R

FIXTURE = Path(__file__).parent / "fixtures" / "raid_chest_groups.json"


def _infos():
    return R.RAIDS.values() if isinstance(R.RAIDS, dict) else R.RAIDS


def test_raid_rewards_carry_no_display_names():
    for info in _infos():
        for tier in R.raid_content(info.content)["tiers"]:
            for r in tier["rewards"]:
                assert "name" not in r, (info.content, r)
                assert set(r) <= {"id", "count", "guaranteed", "tier", "region", "kind"}, (info.content, r)


def test_raid_reward_fields_match_old_names():
    want = json.loads(FIXTURE.read_text())
    got = {info.content: [[[g.draws, [[r.item, r.count, r.guaranteed] for r in g.rewards]]
                           for g in R.chest_groups(info, t)]
                          for t in range(len(R.raid_content(info.content)["tiers"]))]
           for info in _infos()}
    assert got == want
