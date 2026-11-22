"""Who each event battle fights: the event's own bosses and minions, by battle script class.

An event battle's enemies are carried in its bootstrap; content/battles/ has two event battles (Money Bin
Heist, The Last Robot on Earth) and none of the events served here. What the client keeps of each event: its texts (tier
info naming the boss to defeat or the minions that join, ...)
and, in the battle script, the event's own unit classes plus the event mutators that look for them (`t instanceof <boss
class>`: the battle is won when that boss falls, its team is empowered, ...). So each roster names the classes the
event's text and mutators point to (script_minions: HERO_VARIANTS for the empowered heroes, MINIONS for the rest); the
reasoning is on each line. Rosters picked without such evidence are marked "guess".

`bosses` (and `companions`) appear once each; `minions` fill the squad up to five (handlers/events.event_enemy_plan);
`allies` fight on the player's side (No Capes' Edna Mode). `boss_from_tier`:
the first tier whose text names the bosses (Into the Unknown fights only the soldiers before tier IV).
`TIER_ROSTERS` (`event_roster`): a rebuilt tier whose own info text names other villains than its siblings' (each
platinum event tier of 2024-02 lists the villains empowered in it) replaces those fields for that tier only.

`EVENT_MUTATORS`: the battle mutators of each event's battles. The battle script builds mutators from their ids (its
mutator factory); a mutator shows its rule in battle as an aura (a battle message whose id is a gamedata
`aura` row with auraNameLocKey / auraDescriptionLocKey). An aura key named after the event
(EVENT_ALADDIN_LEGENDARY_C_AURA_NAME for Lamp Chamber, whose tiers are EVENT_ALADDIN_LEGENDARY_C_TIER_n) ties the
mutator to the event; most of them also test the event's boss class (`instanceof`). The content event battles carry the
base PvE mutator, their aura mutator(s) and a few unnamed buff mutators (not known for these events, not sent).
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path

from arcane_server import content_data

GOLDEN_GUARDIAN, MENACING_GUARDIAN = 1203141047063960, 3267254572192500  # cave guardians (script minions)
MIND_WORKER = 2406796535291490
KAKAMORAS = (209691744164169, 889442866646246)  # two Kakamora classes (the Kakamora Chief's class looks for both)
SECURITY_SNT, SECURITY_JJ = 5168849938429057, 6158746963335681
CARD_SOLDIERS = (8574344838966530, 6402017627526517, 1352955990830639, 8534259972173715)  # the four suits
MEMORY_SOLDIERS = (2725404754575561, 3065395847079534)  # Arendelle Memory Soldier / Guard
PIXIE_BOUNCER, PIXIE_BRAWLER, PIXIE_HELPFUL = 6793504973620608, 2736539521506414, 5671264099414844  # grey, blue, green
TRASH_CAN, UNICORN = 7473260072687503, 1195414538489109


@dataclass(frozen=True)
class Roster:
    bosses: tuple[int, ...] = ()
    minions: tuple[int, ...] = ()
    boss_from_tier: int = 0
    companions: tuple[int, ...] = ()  # characters at the bosses' side, once each, not bosses (Gothel's Rapunzel)
    # server-given units on the PLAYER's side (not owned by the player, not counted in the squad of five), built at
    # the tier's enemy stats (battle_bootstrap.ally_unit; shape of The Last Robot on Earth's WALL-E)
    allies: tuple[int, ...] = ()


EVENT_ROSTERS: dict[int, Roster] = {
    # Summoner Challenges (daily events): our choice of enemies for each; where an event mutator names a minion class
    # (the Program class with Quorra, the Hun Scout with Shan Yu, Jack Sparrow's) that id is used
    6425243089377372: Roster((553069276713467,), (1570366594174479,)),  # levels: Dr. Facilier + Card Soldiers
    6898342641369799: Roster((72,), (7803746740370685,)),  # offense & speed: Tinker Bell + Fair Folk
    2131194346691558: Roster((150,), (8144507024299462,)),  # gold: Jack Sparrow + Flying Dutchman Crew
    7565802179002800: Roster((36, 50), (758275367121177,)),  # health & recovery: Baloo, Shere Khan + Bandar-log
    3671536447000240: Roster((4914158096592074,), (3667354290875560,)),  # abilities: Quorra + Programs
    5963303581546527: Roster((1809998714774592,), (8449478245108925,)),  # defense & crit: Shan Yu + Hun Scouts
    # Intergalactic Rune Rumble: Zurg and Buzz are empowered (the event's 5 mutators name both);
    # both copy a Mind Worker on their team and spawn more (the tier text: Mind Workers join)
    4014865103971579: Roster((4234654631076577, 5217059940040723), (MIND_WORKER,)),
    # Heroic Showdown: the tier text names an empowered Syndrome: his event class (its mutator, aura
    # Event_Onboarding_Elastigirl_A, empowers him and his team); his minions: his Security (guess)
    1876905024679515: Roster((8063684444320327,), (3053795370654951,)),
    # Supers Collide: Supervillain Scuffle: the tier text empowers Syndrome and his Security (aura
    # Event_202004_Incredibles_C: 8 mutators, all on his class); the Security class with an evade-at-low-health
    # passive slot, also Security Breach's
    1156881387706621: Roster((640417862299850,), (SECURITY_SNT,)),
    4179587105432432: Roster((), (SECURITY_SNT,)),
    312475709934296: Roster((), (SECURITY_JJ,)),  # Flight or Fight: the other event Security class
    # The Cave of Wonders: Treasure Room: the tier text names the Cave Statue (its own class and mutator; it spawns
    # the guardians)
    2888864911071481: Roster((8720168900178268,)),
    # The Guardian Lair: its mutator (aura EVENT_ALADDIN_LEGENDARY_B) looks for a Jafar and a Genie class, as the
    # Jafar and Genie of tier III; their team: the guardians (guess)
    5690402817139380: Roster((3021632039659421, 7605712917452499), (GOLDEN_GUARDIAN, MENACING_GUARDIAN)),
    # Lamp Chamber: the tier text names an empowered Jafar: his class (its mutator empowers his team, the battle ends
    # when he falls);
    # his team: the cave guardians (guess)
    824459308071843: Roster((2808455732321530,), (GOLDEN_GUARDIAN,)),
    # The Diamond in the Rough (no named boss, no mutator in the script): the playable Jafar with the cave
    # guardians and cobras of tiers IV / V (guess)
    1180288022434680: Roster((4505487594415447,), (MENACING_GUARDIAN, GOLDEN_GUARDIAN)),
    # Coconut Crackdown: the empowered Kakamora (KAKAMORAS), the Kakamora Chief summons Kakamora teammates
    6509295448613065: Roster((), KAKAMORAS),
    7092802954430213: Roster((8869970885547499,), KAKAMORAS),
    # Into the Unknown: the tier texts name the Arendelle Memory Soldiers (Elsa too from tier IV): two classes run
    # Elsa's (Elsa the Fifth Spirit's) kit; which is the prestige one is a guess
    4816291935296672: Roster((5955019119988617,), MEMORY_SOLDIERS, boss_from_tier=3),
    2120263135446269: Roster((4372620401308922,), MEMORY_SOLDIERS),
    # Sorcerer stone events: the playable Horned King / Davy Jones (guess: no mutator of the script names these
    # events; the one once thought theirs is the expedition Horned King's), their films' minions (guess)
    1292335089535788: Roster((4996798494226789,), (2207399084365587,)),  # + Cauldron Born
    2176798730995631: Roster((2541505114257629,), (8144507024299462,)),  # + Flying Dutchman Crew
    # The Queen's Clash: the Queen of Hearts (her class, 8 mutators) and the card soldiers of the four suits
    6211230930835237: Roster((5848483329990929,), CARD_SOLDIERS),
    # Sally's Potent Potions: the tier text names Sally and the skeletons (the skeleton class shares her HERO category)
    3235322655256470: Roster((8040425887314762,), (5058125130786168,)),
    # "<hero> vs <villain>": the hero is the player's side; the villain's class has a mutator that ends the battle
    # when he falls
    # Goofy vs Scar: Scar (aura EVENT_202010_SENSATIONALSIX_1_B: a defeated hyena buffs Scar); the hyenas: the tower
    # ones the other event Scar calls (guess)
    5294044306083562: Roster((8435117305040257,), (8992628868600459, 8504390825460539)),
    1284646027873280: Roster((221403608613517,), (541339423403349, 1494696548715032)),  # Jafar + cobras (guess)
    5209236775002059: Roster((5559371775396751,), (7571174340397587,)),  # Hades + his imps
    # The Path of Peril: the tier texts name the Pixie Dusters (Bouncer, Brawler; Pixie Dusters Party adds the
    # Helpful one) and, in Trash Clash, the Trash Can (its mutator ends the battle when it falls) with the
    # Unicorns it calls; all four carry the Onward category
    4813965651358762: Roster((), (PIXIE_BOUNCER, PIXIE_BRAWLER)),
    5284501609403483: Roster((), (PIXIE_BOUNCER, PIXIE_BRAWLER, PIXIE_HELPFUL)),
    6355153775885394: Roster((TRASH_CAN,), (UNICORN,)),
}


# Event -> its mutators (module doc): one id for every tier, or one per tier (in the script's factory order: which
# tier carries which of these is server data, not known; they share the aura and differ only in buff sizes).
EVENT_MUTATORS: dict[int, tuple[int, ...]] = {
    312475709934296: (2476301242513824,),  # Flight or Fight (aura Event_202004_Incredibles_B)
    4179587105432432: (1618411954341754,),  # Security Breach (Event_202004_Incredibles_A)
    1876905024679515: (8508250022086893,),  # Heroic Showdown (Event_Onboarding_Elastigirl_A)
    # Supervillain Scuffle, 8 tiers (Event_202004_Incredibles_C)
    1156881387706621: (4387625281822977, 2945542638122503, 1181558821340751, 1554819890872280, 2215219447287179,
                       4834800281227596, 4634495079690230, 4230565391315805),
    2888864911071481: (360987527985156,),  # Treasure Room (Cave Statue, timed)
    5690402817139380: (482077128671583,),  # The Guardian Lair (every enemy)
    824459308071843: (1507424211389190,),  # Lamp Chamber (empowered Jafar)
    6509295448613065: (86240848505680,),  # Raft Rumble (empowered Kakamora)
    7092802954430213: (5154009814784623,),  # Kakamora Chief (empowered Kakamora Chief)
    1284646027873280: (3974087570524329,),  # Daisy Duck vs Jafar (Jafar)
    5294044306083562: (6139232925746593,),  # Goofy vs Scar (empowered Scar)
    5209236775002059: (8627462561748952,),  # Donald Duck vs Hades (empowered Hades)
    # Intergalactic Rune Rumble, 5 tiers (ST_202004_AbilityUpgradeMaterials_A)
    4014865103971579: (7377367719035033, 1180838314345557, 1512146827046010, 6155464067843667, 8572361299285712),
    # The Queen's Clash, 8 tiers (Event_202002_Villaintines_A)
    6211230930835237: (7336195870486951, 83159396627163, 1403434726387595, 1215839187618392, 4540174050226443,
                       4478501696728542, 7757705334166738, 7449393952058146),
    3235322655256470: (8920919594672857,),  # Sally's Potent Potions (ST_202004_XP_Mutator_A)
    # The Path of Peril
    4813965651358762: (5295633822110852,),  # Raven's Point Rumble (Event_202003_Onward_A)
    5284501609403483: (1683638555452858,),  # Pixie Dusters Party (Event_202003_Onward_B)
    6355153775885394: (1681847629850330,),  # Trash Clash (Event_202003_Onward_C; ends when the Trash Can falls)
}


# Rebuilt events (content/events/<name>.json) carry their own: each event's "roster" ({"bosses", "minions",
# "boss_from_tier", "companions", "allies"}) and "mutators" (ids, one or one per tier) sit next to its definition.
CONTENT_EVENTS_DIR = content_data.CONTENT / "events"
_NOT_EVENTS = {Path(content_data.EVENT_CATALOG).name, Path(content_data.DAILY_CHALLENGES).name}


def content_event_docs(directory: Path = CONTENT_EVENTS_DIR) -> list[tuple[str, dict]]:
    """(file name, document) of every rebuilt event, content/events/<name>.json, by name."""
    return [(p.name, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(directory.glob("*.json"))
            if p.name not in _NOT_EVENTS]


# (event, tier) -> the roster of that tier, where a content tier names its own ("roster": the fields it replaces)
TIER_ROSTERS: dict[tuple[int, int], Roster] = {}

# (event, tier) -> every mutator of that tier's battles, where a content battle shows them all (a content tier's
# "mutators": the aura mutator plus the buff mutators of the Last Robot on Earth event's tier VI)
TIER_MUTATORS: dict[tuple[int, int], tuple[int, ...]] = {}


def content_group_id(doc: dict) -> int:
    """The event group of a content/events document: its own ("event_group"), or the one it adds stages to
    ("group": a later run of another rebuilt event that gained a stage, e.g. Platinum Mickey's Platinum Battle in
    The Sensational Six: Part 2 of 2023-05)."""
    return int(doc["event_group"]["contentId"]) if "event_group" in doc else int(doc["group"])


def _load_content_events() -> None:
    for name, doc in content_event_docs():
        for spec in doc["events"]:
            cid = int(spec["event"]["contentId"])
            for table, key in ((EVENT_ROSTERS, "roster"), (EVENT_MUTATORS, "mutators")):
                if key in spec and cid in table:
                    raise RuntimeError(f"content/events/{name}: event {cid} already has a {key} in event_rosters.py")
            if r := spec.get("roster"):
                EVENT_ROSTERS[cid] = _roster(r)
            if m := spec.get("mutators"):
                EVENT_MUTATORS[cid] = tuple(int(x) for x in m)
            for i, tier in enumerate(spec.get("tiers", ())):
                if tm := tier.get("mutators"):
                    TIER_MUTATORS[(cid, i)] = tuple(int(x) for x in tm)
                if (tr := tier.get("roster")) is not None:
                    if cid not in EVENT_ROSTERS:
                        raise RuntimeError(f"content/events/{name}: event {cid} tier {i} has a roster, the event none")
                    if unknown := set(tr) - _ROSTER_FIELDS:
                        raise RuntimeError(f"content/events/{name}: event {cid} tier {i} roster: unknown {sorted(unknown)}")
                    TIER_ROSTERS[(cid, i)] = _roster(tr, EVENT_ROSTERS[cid])


_ROSTER_FIELDS = {"bosses", "minions", "boss_from_tier", "companions", "allies"}


def _roster(r: dict, base: Roster = Roster()) -> Roster:
    """A content file's roster: its fields, the others from `base` (the event's own, for a tier's roster)."""
    ids = {k: tuple(int(x) for x in r[k]) for k in ("bosses", "minions", "companions", "allies") if k in r}
    return dataclasses.replace(base, **ids, **({"boss_from_tier": int(r["boss_from_tier"])} if "boss_from_tier" in r else {}))


_load_content_events()


def event_roster(event_id: int, tier_index: int) -> Roster | None:
    """Who tier `tier_index` of event `event_id` fights (TIER_ROSTERS, else EVENT_ROSTERS)."""
    return TIER_ROSTERS.get((event_id, tier_index)) or EVENT_ROSTERS.get(event_id)


def event_mutators(event_id: int, tier_index: int) -> tuple[int, ...]:
    """The mutators of tier `tier_index` of event `event_id` (TIER_MUTATORS, else EVENT_MUTATORS)."""
    if (tier := TIER_MUTATORS.get((event_id, tier_index))) is not None:
        return tier
    ids = EVENT_MUTATORS.get(event_id, ())
    if len(ids) <= 1:
        return ids
    return (ids[min(tier_index, len(ids) - 1)],)

