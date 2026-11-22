"""Every battle scene / cinematic a content event names (content/events/<name>.json "battle_environment",
"boss_cinematic", "intro_cinematic", per event or per tier) is "<bundle>/<asset>" with that asset inside that bundle of
the content set: the startup check (handlers/events._Checker.assets) only sees bundle names, and a wrong scene name
inside a right bundle (env_river_styx holds env_river_sticks) leaves the battle without a battleground."""

from __future__ import annotations


import pytest

from arcane_server.config import load_settings
from arcane_server.event_rosters import content_event_docs

UnityPy = pytest.importorskip("UnityPy")
KEYS = ("battle_environment", "boss_cinematic", "intro_cinematic")


def _refs() -> set[str]:
    out = set()
    for _, doc in content_event_docs():
        for spec in doc["events"]:
            out |= {spec[k] for k in KEYS if spec.get(k)}
            out |= {t[k] for t in spec["tiers"] for k in KEYS if t.get(k)}
    return out


@pytest.mark.parametrize("ref", sorted(_refs()))
def test_scene_asset_is_in_its_bundle(ref):
    bundle, name = ref.split("/", 1)
    path = load_settings().assets_dir / bundle
    if not path.exists():
        pytest.skip("content set not present")
    env = UnityPy.load(str(path))
    container = next(o for o in env.objects if o.type.name == "AssetBundle").read().m_Container
    names = {k.rsplit("/", 1)[-1].rsplit(".", 1)[0] for k, _ in container}
    assert name in names, f"{ref}: the bundle holds {sorted(names)[:4]}"
