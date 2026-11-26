"""Admin unit and club item requests checked without the client content set: which unit lists are taken, and the
club item change rule (tests/test_admin.py runs the endpoints themselves against the content set)."""

from __future__ import annotations

import pytest
from aiohttp import web

from arcane_server.admin import api

PLAYABLE = {10, 11, 12, 13}


def test_unit_ids_takes_a_list_of_distinct_playable_ids():
    assert api.unit_ids({"units": [10, 12]}, PLAYABLE) == [10, 12]


@pytest.mark.parametrize("units", [
    None, [], "10", [10, 10], [10, True], [True], [10.0], [10, 99],
    list(range(api.MAX_UNITS_PER_REQUEST + 1)),
])
def test_unit_ids_refuses_missing_duplicate_boolean_unknown_or_too_many(units):
    playable = PLAYABLE | set(range(api.MAX_UNITS_PER_REQUEST + 1))
    with pytest.raises(web.HTTPBadRequest):
        api.unit_ids({"units": units}, playable if units and len(units) > 10 else PLAYABLE)


def test_club_item_change_refuses_zero_and_going_below_zero():
    assert api.club_item_after(100, 50) == 150
    assert api.club_item_after(100, -100) == 0
    for before, delta in ((100, 0), (100, -101)):
        with pytest.raises(web.HTTPBadRequest):
            api.club_item_after(before, delta)
