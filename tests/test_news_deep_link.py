"""The News page's deep links name the client's scheme and app package from the release definition
(content/clients/<release>.json), the package of the build the server serves: the patcher installs the multiplayer
variant as <package>.multiplayer; ARCANE_CLIENT_PACKAGE overrides it (the offline variant sets its own)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from arcane_server import news, schedule
from arcane_server.config import PROJECT_ROOT, load_settings

RELEASE = json.loads((PROJECT_ROOT / "content" / "clients" / "v29.json").read_text())


def _item():
    kind = next(k for k, v in schedule.KINDS.items() if v.link)
    return SimpleNamespace(kind=kind, link_sub="")


def test_release_names_the_client_app():
    assert RELEASE["app_package"] and RELEASE["deep_link_scheme"]


def test_app_package_per_profile(monkeypatch):
    monkeypatch.delenv("ARCANE_CLIENT_PACKAGE", raising=False)
    monkeypatch.setenv("ARCANE_PROFILE", "single")
    assert load_settings().app_package == RELEASE["app_package"]
    monkeypatch.setenv("ARCANE_PROFILE", "multiplayer")
    assert load_settings().app_package == RELEASE["app_package"] + ".multiplayer"
    monkeypatch.setenv("ARCANE_CLIENT_PACKAGE", "org.example.game.offline")
    assert load_settings().app_package == "org.example.game.offline"


def test_deep_link_uses_the_release_scheme():
    link = news.deep_link("org.example.game", _item())
    assert f";scheme={RELEASE['deep_link_scheme']};" in link
    assert link.endswith(";package=org.example.game;end")


def test_deep_link_without_package_names_none():
    assert ";package=" not in news.deep_link("", _item())
