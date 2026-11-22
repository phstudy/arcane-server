"""Unit classes read from the client's own battle script (gamedata `battleScript`, zlib-compressed JS).

Every hero, minion and raid boss ability runs from this script. The server sends units inside the battle bootstrap;
for units with no content bootstrap (script_minions) their class, categories, ability slots and spawned units are
read here:

- `case <unit definition id>: return new <factory>(<UnitClass>, t, ..., [<category ids>])` - the unit's class and
  categories;
- the class constructor names its ability slots (`t.<slot>=0, t.<slot>=1, ...`) and a switch maps a slot to its
  ability class (`case this.<slot>: return <AbilityClass>`); an ability class reads its tuning through a parser, and
  unit-level handlers do the same per slot;
  (the script's names differ between client builds, so `Dialect` finds each one by the code shape around it)
"""

from __future__ import annotations

import bisect
import re
import zlib
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import NamedTuple

from arcane_server.gamedata import Gamedata

_ID = r"[A-Za-z0-9_$]+"


def decode_script(raw: bytes) -> str:
    """The battle script source: a '//$sz....' header, then a zlib stream."""
    return zlib.decompress(raw[raw.index(b"\x78\x9c"):]).decode("utf-8", "replace")


@cache
def _script(path: str) -> str:
    return decode_script(bytes(Gamedata(Path(path)).raw["battleScript"]))


def script(gd: Gamedata) -> str:
    return _script(str(gd.path))


@dataclass(frozen=True)
class Dialect:
    """The battle script's short names this module reads, found by the code shape around each (most frequent
    match), so a client build whose script renames them needs no new constants. tests pin them per release."""

    factory: str  # `case <id>:return new <factory>(<class>,t,..,..,[cats])`
    extend: str  # `return <extend>(t,n),t.prototype` (class inheritance helper)
    parser_of: str  # `=<parser>.<parser_of>(t.<slot_data>(t.<slot>),t)`
    slot_data: str  # ... <slot_data>
    ability_parser: str  # `t.<ability_parser>=<parser>.<parse>(t)` in an ability class
    parse: str  # ... <parse>
    slot_names: tuple[str, ...]  # the usual `t.<basic>=0,t.<special a>=1,t.<special b>=2,t.<passive>=3`
    passive_slots: tuple[str, ...]  # slot names a unit handles itself (no ability class)
    projectile_base: str  # ability base class of projectile basics (uses `t.sourcePos`)
    slot_switch: str  # `t.prototype.<slot_switch>=function(t){switch(t){case this.<slot>:return <ability class>`
    slot_ability: str  # `this.<slot_ability>(this.<slot>)`: a unit's own ability in a slot
    template_of: str  # an ability's summon template
    # `<template_of>(){return this.<battle>.<templates>[this.context.<unit_data>.<template_id>]}`
    battle: str  # ... the battle
    templates: str  # ... bootstrap units by bootstrap_unique_id
    unit_data: str  # ... a unit's / an ability's bootstrap data
    template_id: str  # ... Ability.add_unit's bootstrap_unique_id
    slot_abilities: str  # `this.<unit_data>.<slot_abilities>[this.<slot>]`: a unit's bootstrap abilities by slot
    # what an ability does to its target (ability_target)
    target: str  # `<target>(){return this.context.<...>}`: the ability's target (the Ability.target_* flags pick it)
    damage: tuple[str, ...]  # `<damage>(t,n){return this.<damage>(t,new <...>(n))}`: deal damage to a unit
    apply_effect: str  # `<apply_effect>(t,n){return t.<...>(this,n,...)}`: put an effect on a unit
    effect_kind: str  # `<effect_kind>()`: an effect's kind, `return <kinds>.<harmful>` / `<kinds>.<helpful>`
    kinds: str  # ... the kinds
    harmful: str  # ... the kind that tenacity resists
    helpful: str  # ... the helpful kind
    team_of: str  # `<team_of>(n,t)`: the units next to a unit in its own team's formation (and the unit itself if t)


def _most(pattern: str, src: str, what: str):
    found = Counter(re.findall(pattern, src)).most_common(1)
    if not found:
        raise ValueError(f"battle script: cannot find {what}")
    return found[0][0]


@cache
def dialect(src: str) -> Dialect:
    i = _ID
    factory = _most(rf"case (?:0x[0-9a-f]+|\d+):return new ({i})\({i},t,\d+,\d+,\[", src, "the unit factory")
    extend = _most(rf"return ({i})\(t,n\),t\.prototype", src, "the inheritance helper")
    parser_of, slot_data = _most(rf"=(?:{i})\.({i})\(t\.({i})\(t\.{i}\),t\)", src, "slot parsers")
    ability_parser, parse = _most(rf"t\.({i})=(?:{i})\.({i})\(t\),t\}}return {re.escape(extend)}\(t,n\)", src,
                                  "ability parsers")
    four = Counter(re.findall(rf"t\.({i})=0,t\.({i})=1,t\.({i})=2,t\.({i})=3", src)).most_common()
    if not four:
        raise ValueError("battle script: cannot find the ability slot names")
    names = four[0][0]
    # slot 3 under another name (a unit whose passive sits in slot 3 next to the usual i$ in slot 4)
    other3 = next((t[3] for t, _ in four if t[:3] == names[:3] and t[3] != names[3]), None)
    passive = (names[3],) + ((other3,) if other3 else ())
    bases = Counter(re.findall(rf"\}}\(({i})\)", src))
    proj = [n for n in _definitions(src)[0] if "t.sourcePos" in _body(src, n)]
    if not proj:
        raise ValueError("battle script: cannot find the projectile ability base")
    switch = _most(rf"t\.prototype\.({i})=function\(t\)\{{switch\(t\)\{{case this\.", src, "the slot switch")
    own = _most(rf"this\.({i})\(this\.{re.escape(names[3])}\)", src, "the slot ability getter")
    tpl = _most(rf"prototype\.({i})=function\(\)\{{return this\.({i})\.({i})\[this\.context\.({i})\.({i})\]\}}", src,
                "the summon template getter")
    _, battle, templates, unit_data, template_id = tpl
    by_slot = _most(rf"this\.{re.escape(unit_data)}\.({i})\[this\.{i}\][^{{}}]{{0,160}}?\.{re.escape(templates)}\[{i}\."
                    rf"{re.escape(template_id)}\]", src, "the abilities by slot")
    pn = _most(rf"this\.{i}=n,this\.({i})=i,this\.{i}={i}\.{i}\(\),this\.source=t", src, "the ability context")
    target = _most(rf"prototype\.({i})=function\(\)\{{return this\.context\.{re.escape(pn)}\}}", src,
                   "the ability target getter")
    damage = _most(rf"prototype\.({i})=function\(t,n\)\{{return this\.({i})\(t,new {i}\(n\)\)\}},t\.prototype\.\2=",
                   src, "the damage calls")
    apply_effect = _most(rf"prototype\.({i})=function\(t,n\)\{{return t\.{i}\(this,n,this\.{i}\(\)\)\}}", src,
                         "the effect call")
    effect_kind, kinds, harmful = _most(rf"n&&i\.({i})\(\)==({i})\.({i})&&this\.", src, "the harmful effect kind")
    kind_values = _most(rf"[,;]{re.escape(kinds)}=function\(\)\{{function t\(\)\{{\}}return t\.{i}=0,t\.({i})=1,"
                        rf"t\.({i})=2,t\}}", src, "the effect kinds")
    helpful = next(k for k in kind_values if k != harmful)
    team_of = _most(rf"prototype\.({i})=function\(n,t\)\{{var i=\[\];return\(t=void 0===t\?!1:t\)&&i\.push\(n\)",
                    src, "the formation neighbours")
    return Dialect(factory, extend, parser_of, slot_data, ability_parser, parse, names, passive,
                   max(proj, key=lambda n: bases[n]), switch, own, *tpl, by_slot, target, damage, apply_effect,
                   effect_kind, kinds, harmful, helpful, team_of)


def _num(s: str) -> int:
    return int(s, 16) if s.startswith("0x") else int(s)


def _id_pattern(definition_id: int) -> str:
    return f"(?:{definition_id}|{hex(definition_id)})"


@cache
def _definitions(src: str) -> tuple[dict[str, int], list[int]]:
    """Top-level `name=function(` positions (classes, parsers, value holders) and their sorted starts."""
    defs: dict[str, int] = {}
    for m in re.finditer(rf"[,;]({_ID})=function\(", src):
        defs.setdefault(m.group(1), m.start())
    return defs, sorted(defs.values())


def _body(src: str, name: str) -> str:
    """Source of definition `name`, up to the next top-level definition."""
    defs, starts = _definitions(src)
    pos = defs.get(name)
    if pos is None:
        return ""
    nxt = starts[bisect.bisect_right(starts, pos)] if bisect.bisect_right(starts, pos) < len(starts) else len(src)
    return src[pos:nxt]


# --- unit classes (minions without a content bootstrap, script_minions) ----------------------------------------------


def _parent(src: str, name: str) -> str | None:
    """The class `name` extends (`...}(<parent>)` at the end of its definition)."""
    m = re.search(rf"\}}\(({_ID})\)[,;]?\s*$", _body(src, name))
    return m.group(1) if m else None


def _head(body: str, d: Dialect) -> str:
    """A class definition's constructor (before its `<extend>(t,n)` inheritance call)."""
    return body.split(f"return {d.extend}(t,n)")[0]


def unit_class(src: str, definition_id: int) -> tuple[str, tuple[int, ...]] | None:
    """(unit class, category ids) of `case <definition id>:return new <factory>(<class>, ...)`."""
    factory = re.escape(dialect(src).factory)
    m = re.search(rf"case {_id_pattern(definition_id)}:return new {factory}\(({_ID}),t,\d+,\d+,\[([^\]]*)\]\)", src)
    if m is None:
        return None
    return m.group(1), tuple(_num(c) for c in m.group(2).split(",") if c)


class ScriptSlot(NamedTuple):
    cls: str  # ability class ("" for a slot the unit class handles itself)
    var: str  # the unit class's slot variable (Dialect.slot_names: basic, two specials, anything else a passive)
    kind: str  # basic | special | passive


def _chain(src: str, cls: str) -> list[str]:
    out: list[str] = []
    while cls and cls not in out:
        out.append(cls)
        cls = _parent(src, cls) or ""
    return out


def _slot_kind(d: Dialect, var: str) -> str:
    return "basic" if var == d.slot_names[0] else "special" if var in d.slot_names[1:3] else "passive"


@cache
def ability_slots(src: str, definition_id: int) -> dict[int, ScriptSlot]:
    """Ability slot -> (ability class, slot variable) of a unit; the slot numbers are the bootstrap's Ability.id.

    The unit class and its parents set the slot variables in their constructors (basic 0, specials 1 / 2 on the
    minion base, specials 2 / 3 and a passive 1 on heroes; a subclass's value wins), the nearest slot switch maps a
    slot to its ability class, and a passive the unit handles itself reads its slot's level (Dialect.slot_data /
    slot_ability). On every content minion and event boss this gives the content ability ids and types (basic,
    two specials, passives the rest), except three units whose content bootstrap predates the v28 script (Stone
    Troll special 1 where the class has 2, Kakamora v2 and Syndrome Security with specials the class no longer has;
    battle_bootstrap.script_aligned moves them onto these slots)."""
    d = dialect(src)
    uc = unit_class(src, definition_id)
    if uc is None:
        return {}
    values: dict[str, int] = {}
    cases: list[tuple[str, str]] | None = None
    passives: set[str] = set()
    for cls in _chain(src, uc[0]):
        body = _body(src, cls)
        for v, n in re.findall(rf"t\.({_ID})=(\d+)[,;]", _head(body, d)):
            values.setdefault(v, int(n))
        # a slot kept on the class itself (Snow White: `<Class>.<slot>=4`, read as `<Class>.<slot>`), named
        # "<class>.<name>" so it never meets an instance variable
        own = re.match(rf"[,;]?{re.escape(cls)}=function\({_ID}\)\{{function ({_ID})\(", body)
        static = re.escape(own.group(1)) if own else None
        if static:
            for v, n in re.findall(rf"[,;(]{static}\.({_ID})=(\d+)[,;)]", body):
                values.setdefault(f"{cls}.{v}", int(n))
        switch = rf"prototype\.{re.escape(d.slot_switch)}=function\(t\)\{{(.*?)\}}[}},]"
        if cases is None and (g5 := re.search(switch, body)):
            cases = re.findall(rf"case this\.({_ID}):return ({_ID})", g5.group(1))
            cases += re.findall(rf"if\(t===this\.({_ID})\)return ({_ID})", g5.group(1))
            if static:
                cases += [(f"{cls}.{v}", c) for v, c in re.findall(rf"case {static}\.({_ID}):return ({_ID})", g5.group(1))]
        passives |= set(re.findall(rf"(?:t|this)\.{re.escape(d.slot_data)}\((?:t|this)\.({_ID})\)", body))
        passives |= set(re.findall(rf"this\.{re.escape(d.slot_ability)}\(this\.({_ID})\)", body))
        if static:
            passives |= {f"{cls}.{v}" for v in re.findall(
                rf"(?:t|this)\.(?:{re.escape(d.slot_data)}|{re.escape(d.slot_ability)})\({static}\.({_ID})\)", body)}
    out: dict[int, ScriptSlot] = {}
    for v, c in cases or ():
        if v in values:
            out.setdefault(values[v], ScriptSlot(c, v, _slot_kind(d, v)))
    for v in sorted(passives):
        if v in values:
            out.setdefault(values[v], ScriptSlot("", v, _slot_kind(d, v)))
    return dict(sorted(out.items()))


def _slot_values(src: str, cls: str) -> dict[str, int]:
    """Slot variable -> slot number, set in the constructors of `cls` and its parents (a subclass's value wins)."""
    d = dialect(src)
    values: dict[str, int] = {}
    for c in _chain(src, cls):
        for v, n in re.findall(rf"t\.({_ID})=(\d+)[,;]", _head(_body(src, c), d)):
            values.setdefault(v, int(n))
    return values


@cache
def _template_holders(src: str) -> frozenset[str]:
    """Classes defining the summon template getter (the ability base: every ability inherits it)."""
    d = dialect(src)
    return frozenset(n for n in _definitions(src)[0] if f"prototype.{d.template_of}=function()" in _body(src, n))


@cache
def spawn_slots(src: str, definition_id: int) -> frozenset[int]:
    """Ability slots whose summon template (the bootstrap Ability.add_unit) the unit's class spawns: an ability class
    that reads its own template (Dialect.template_of) or the unit class reading a slot's template
    (Dialect.slot_abilities ... Dialect.templates, e.g. Gabby Gabby's Dummies, the Pixie Duster Grey's dusters).
    Without an add_unit on that slot the spawn does nothing."""
    d = dialect(src)
    uc = unit_class(src, definition_id)
    if uc is None:
        return frozenset()
    values = _slot_values(src, uc[0])
    out: set[int] = set()
    read = rf"this\.{re.escape(d.unit_data)}\.{re.escape(d.slot_abilities)}\[this\.({_ID})\]"
    spawn = rf"\.{re.escape(d.templates)}\[{_ID}\.{re.escape(d.template_id)}\]"
    for cls in _chain(src, uc[0]):
        body = _body(src, cls)
        for m in re.finditer(read, body):
            if m.group(1) in values and re.search(spawn, body[m.end():m.end() + 200]):
                out.add(values[m.group(1)])
    holders = _template_holders(src)
    for slot, s in ability_slots(src, definition_id).items():
        if s.cls and any(f".{d.template_of}()" in _body(src, c) for c in _chain(src, s.cls) if c not in holders):
            out.add(slot)
    return frozenset(out)


def basic_is_projectile(src: str, ability_class: str) -> bool:
    """Basic attacks extend the melee base (walks up and hits) or Dialect.projectile_base (launches a projectile)."""
    return _parent(src, ability_class) == dialect(src).projectile_base


@cache
def _shared_bases(src: str) -> frozenset[str]:
    """Classes many others extend (the ability bases: their code is every ability's, not one ability's own)."""
    parents = Counter(_parent(src, n) for n in _definitions(src)[0])
    return frozenset(p for p, n in parents.items() if p and n >= 20)


def _effect_kind(src: str, cls: str) -> str:
    """'harmful' / 'helpful' / '' of an effect class (`<effect_kind>(){return <kinds>.<harmful|helpful>}` on it or a
    parent)."""
    d = dialect(src)
    for c in _chain(src, cls):
        m = re.search(rf"prototype\.{re.escape(d.effect_kind)}=function\(\)\{{return {re.escape(d.kinds)}\.({_ID})\}}",
                      _body(src, c))
        if m:
            return {d.harmful: "harmful", d.helpful: "helpful"}.get(m.group(1), "")
    return ""


def _scope_end(body: str, pos: int) -> int:
    """End of the function / expression `pos` is in (where its brackets close)."""
    depth = 0
    for i in range(pos, len(body)):
        if body[i] in "{([":
            depth += 1
        elif body[i] in "})]":
            depth -= 1
            if depth < 0:
                return i
    return len(body)


@cache
def target_uses(src: str, ability_class: str) -> frozenset[str]:
    """What an ability class does to its target (`<v>=this.<target>()`, until `v` is reassigned or its function ends):
    'damage' (Dialect.damage on it), 'harmful' / 'helpful' (Dialect.apply_effect of an effect of that kind on it); an
    effect or damage on the target's formation neighbours (`<team_of>(v)`: the target's own team) counts as on the
    target."""
    d = dialect(src)
    dmg = "|".join(map(re.escape, d.damage))
    out: set[str] = set()
    for cls in _chain(src, ability_class):
        if cls in _shared_bases(src):
            break
        body = _body(src, cls)
        for m in re.finditer(rf"({_ID})=(?:{_ID})\.{re.escape(d.target)}\(\)", body):
            v = re.escape(m.group(1))
            seg = body[m.end():_scope_end(body, m.end())]
            if (again := re.search(rf"(?<![\w$.=!<>]){v}=(?!=)", seg)) is not None:
                seg = seg[:again.start()]
            who = v
            if (team := re.search(rf"\.{re.escape(d.team_of)}\({v}[,)]", seg)) is not None:
                who = _ID  # the neighbours, iterated under any name
                seg_team = seg[team.end():]
                if re.search(rf"\.(?:{dmg})\({_ID}[,)]", seg_team):
                    out.add("damage")
            if re.search(rf"\.(?:{dmg})\({v}[,)]", seg):
                out.add("damage")
            for e in re.finditer(rf"\.{re.escape(d.apply_effect)}\({who},(?:new ({_ID})\(|({_ID})\))", seg):
                effect = e.group(1)
                if effect is None:  # a variable: its last `x=new <Effect>(` before
                    made = re.findall(rf"(?<![\w$.]){re.escape(e.group(2))}=new ({_ID})\(", seg[:e.start()])
                    effect = made[-1] if made else None
                if effect and (kind := _effect_kind(src, effect)):
                    out.add(kind)
    return frozenset(out)


def ability_target(src: str, ability_class: str) -> str | None:
    """Whom an activated ability class must be pointed at (its Ability.target_* flags pick the target, Dialect.target):
    'enemy' when it damages or harms its target, 'ally' when it only helps it, None when it does neither (it acts on
    its caster or the field, or its code is beyond this reading). On every special of the gamedata heroes and the
    content minions, 'enemy' classes target enemies only and 'ally' classes never target enemies
    (tests/test_script_units.py)."""
    uses = target_uses(src, ability_class)
    if uses & {"damage", "harmful"}:
        return "enemy"
    return "ally" if "helpful" in uses else None


_SHARED_HOLDER = 40  # a holder naming more effects is the script's global table (UI, buffs: loaded by every battle)


@cache
def referenced_effects(src: str, definition_id: int, effect_ids: frozenset[int]) -> tuple[int, ...]:
    """Effect ids (gamedata abilityEffect) the unit's class and its ability classes play: the numbers in the
    constant-holder classes they reference (e.g. Benson's holder: e_benson_special_a). On the content Goon this
    is its bootstrap's effect_def_ids plus the shared hit / buff effects of its classes."""
    uc = unit_class(src, definition_id)
    if uc is None:
        return ()
    defs, _ = _definitions(src)
    out: set[int] = set()
    for name in {uc[0], *(s.cls for s in ability_slots(src, definition_id).values())} - {""}:
        # free identifiers only: `t.<slot>` is a property, which may share its short name with a global class
        for ref in {name, *(r for r in re.findall(rf"(?<![.\w$])({_ID})", _body(src, name)) if r in defs)}:
            body = _body(src, ref)
            if ref != name and "prototype" in body:
                continue  # behaviour classes; only constant holders name effects
            hits = {n for n in (_num(x) for x in re.findall(r"\b(0x[0-9a-f]+|\d{6,})\b", body)) if n in effect_ids}
            if len(hits) <= _SHARED_HOLDER:
                out |= hits
    return tuple(sorted(out))


# --- battle mutators --------------------------------------------------------------------------------------------

BASE_PVE_MUTATOR = 4424554285226317  # in every PvE bootstrap (battle_bootstrap.PVE_MUTATOR): a case of the factory


@cache
def mutator_classes(src: str) -> dict[int, str]:
    """The battle script's mutator factory (`switch(t){case <id>:return new <class>;...}`, the one that builds the base
    PvE mutator): mutator id -> class."""
    anchor = re.search(rf"case {_id_pattern(BASE_PVE_MUTATOR)}:return new {_ID};", src)
    if anchor is None:
        return {}
    last = src.find("{", src.rfind("switch(", 0, anchor.start())) + 1
    out: dict[int, str] = {}
    for m in re.compile(rf"case (0x[0-9a-f]+|\d+):return new ({_ID});").finditer(src, last):
        if m.start() != last:  # the cases run back to back; anything else ends the switch
            break
        out[_num(m.group(1))] = m.group(2)
        last = m.end()
    return out
