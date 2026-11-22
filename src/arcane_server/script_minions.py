"""Enemies with no content bootstrap, built from what the client ships (campaign, tower and dungeon enemies).

A battle bootstrap carries every enemy as a full unit (battle_bootstrap). The gamedata has no definitions for these
units; some have one in content/battles/ (battle_bootstrap.known_minion_templates), not the ones below:
most of them only have node previews (EnemyUnitPreview: id, name, portrait, range), the first twelve not even that
(campaign enemies with no preview). The client still ships them whole:

- Behaviour: the battle script (gamedata `battleScript`, raid_kits) has a unit class per unit, picked by the
  bootstrap's definition id (`case <id>:return new <factory>(<class>, ..., [<category ids>])`). Its ability classes
  are picked by the bootstrap's Ability.id (raid_kits.ability_slots: the slot variables of the class and its
  parents, a basic, two specials, others passives; on 28 of the 31 content minions and event bosses exactly the
  content ability ids and types), and they compute their effects from the script's own tables at the ability
  level. Which class is which minion: the preview's definition id, or for the twelve without one the class that plays
  the minion's own abilityEffect visuals (e.g. Benson's holds e_benson_special_a) and carries its film's category.
- Looks: the preview's name and portrait; the prefab is the unit_<name> bundle matching the portrait (its only
  u_<name> prefab; the color variants without a portrait of their own, e.g. unit_fairfolk_green, are not used).
- Effects to preload (Unit.effect_def_ids): the bundle's own abilityEffect rows, the effects its classes name
  (raid_kits.referenced_effects) and the shared hit / buff effects of its content stand-in.

NOT in the client, so our choice: the stats, mana costs and the few unit numbers the script does not
hold (crit, attack speed, walk speed, radius, speed, tenacity) are those of a content minion of the same role
(category OFFENSE / DEFENSE / SUPPORT) and range class (`model`), re-levelled along the minion stat curve like
every minion (battle_bootstrap.scaled_minion). The attack range is the preview's (on every content minion the
preview's range is the battle unit's); without a preview: melee basics (the script's melee base class) 1,
projectile basics (Dialect.projectile_base) the model's.

Hero variants (`HERO_VARIANTS`: bosses with an id and a class of their own built on a playable hero's kit: the
Towers of Endurance bosses, e.g. the tower's Jafar; the events' empowered bosses, e.g. Goofy vs Scar's Scar, whose
event mutators look for that class; the Inferno / Ascension arena Hades and Mickey) are the hero's
gamedata unit relabelled with the variant's id and categories: the variant class picks its own ability classes for
the hero's ability ids. A hero leader ability on a passive slot of the class becomes a passive (Syndrome's of the event
Syndromes), a passive slot the hero has no ability for gets a passive (the event Hades' imp-summoning slot 4),
and a variant may wear one of the hero's skins and carry its own name (the arena Hades and Mickey).

Summons (`SUMMONS`): a class that spawns reads the template from the spawning slot's Ability.add_unit
(raid_kits.spawn_slots); the template is the script minion named here, shaped like a content raid boss summon (the
script sets every stat of what it spawns, mostly copied from a unit of that kind on the field). A hero variant keeps
its hero's gamedata summon unless this names another.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from arcane_server import raid_kits
from arcane_server.gamedata import Gamedata
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.content_data import client_key

B = pb.BattleLib_Bootstrap
BASIC, SPECIAL, PASSIVE = 1, 3, 4  # Ability.ability_type, as the client expects it
KIND = {"basic": BASIC, "special": SPECIAL, "passive": PASSIVE}
GEO = 44  # Ability.geo_id of every content minion ability
NPC_ICON = "icons_units_shared/npc_attack"  # every content minion ability's icon
# Ability name keys follow the content minions': <NAME>_ABILBASIC_NAME, _ABILSPECIALA_NAME / B (the two specials),
# <NAME> = the unit name key's stem without underscores (CARD_SOLDIER -> CARDSOLDIER), unless the localization
# has the keys spelled otherwise.
ABILITY_NAME_STEM = {"BANDAR_LOG_MONKEY_UNIT_NAME": "BANDAR_LOG_MONKEY"}


@dataclass(frozen=True)
class ScriptMinion:
    definition_id: int  # the battle script's unit class id
    asset: str  # <bundle>/<prefab>
    name_key: str
    icon: str
    range: float = 0.0  # attack range (the preview's); 0: by the basic attack (see the module doc)

    @property
    def bundle(self) -> str:
        return self.asset.split("/")[0]


MINIONS = (
    # Never previewed: campaign enemies matched to their class by effects (see the module doc)
    ScriptMinion(7589648724658440, "unit_benson/u_benson", "BENSON_UNIT_NAME", "icons_units_benson/portrait_benson"),
    ScriptMinion(4518135635864306, "unit_dummy/u_dummy", "", "icons_units_dummy/portrait_dummy"),  # no name text
    ScriptMinion(6845400675393552, "unit_gabby_gabby/u_gabby_gabby", "GABBY_GABBY_UNIT_NAME",
                 "icons_units_gabby_gabby/portrait_gabby_gabby"),
    ScriptMinion(2736539521506414, "unit_pixie_blue/u_pixie_blue", "PIXIE_DUSTER_BLUE_UNIT_NAME", ""),  # no portrait
    ScriptMinion(5671264099414844, "unit_pixie_green/u_pixie_green", "PIXIE_DUSTER_GREEN_UNIT_NAME", ""),
    ScriptMinion(6793504973620608, "unit_pixie_grey/u_pixie_grey", "PIXIE_DUSTER_GREY_UNIT_NAME", ""),
    ScriptMinion(1195414538489109, "unit_unicorn/u_unicorn", "", "icons_units_unicorn/portrait_unicorn"),  # no name
    # The Path of Peril's Trash Can (Onward categories; finds a Unicorn teammate on start and its basic spawns
    # Unicorns with that one's stats; an event mutator ends the battle when it falls): the unicorn bundle's
    # u_unicorn_props (mesh unicorn_props_trash) and portrait_unicorn_trash
    ScriptMinion(7473260072687503, "unit_unicorn/u_unicorn_props", "TRASH_CAN_UNIT_NAME",
                 "icons_units_unicorn/portrait_unicorn_trash"),
    ScriptMinion(2725404754575561, "unit_memory_guard_offense/u_memory_guard_offense",
                 "ARENDELLE_MEMORY_SOLDIER_UNIT_NAME", "icons_units_memory_guard/portrait_memory_guard_offense"),
    ScriptMinion(3065395847079534, "unit_memory_guard_defense/u_memory_guard_defense",
                 "ARENDELLE_MEMORY_GUARD_UNIT_NAME", "icons_units_memory_guard/portrait_memory_guard_defense"),
    # Towers of Endurance previews
    ScriptMinion(3524431964886272, "unit_hyena_bone_skull/u_hyena_bone_skull", "HYENA_BONE_SKULL_UNIT_NAME",
                 "icons_units_hyena_bone_skull/portrait_hyena_bone_skull", 1.0),
    ScriptMinion(541339423403349, "unit_guardian_cobra/u_guardian_cobra", "GUARDIAN_COBRA_UNIT_NAME",
                 "icons_units_cobra/portrait_cobra_guardian", 1.0),
    ScriptMinion(1494696548715032, "unit_vicious_cobra/u_vicious_cobra", "VICIOUS_COBRA_UNIT_NAME",
                 "icons_units_cobra/portrait_cobra_vicious", 18.0),
    # Club dungeon: content battles have them with speed 0 and no crit / tenacity (not usable as is); looks as there
    ScriptMinion(6637607033365366, "unit_kakamora_v2/u_kakamora_v2", "KAKAMORA_UNIT_NAME",
                 "icons_units_kakamora/portrait_kakamora", 4.0),
    ScriptMinion(8543978357888024, "unit_jolly_roger_pirate_v1/u_jolly_roger_pirate_v1", "JOLLY_ROGER_CREW_UNIT_NAME",
                 "icons_units_jolly_roger_pirate/portrait_jollyrogerpirate2", 1.0),
    # Previewed only (campaign_detail of the campaigns, the Towers of Endurance), by definition id; ids sharing a
    # name are separate classes (the tower ones mostly differ from the campaign ones)
    ScriptMinion(5440443151823389, "unit_atlantean/u_atlantean", "ATLANTEAN_UNIT_NAME",
                 "icons_units_atlantean/portrait_atlantean", 4.0),  # Towers of Endurance
    ScriptMinion(638386329928383, "unit_bandar_log_monkey/u_bandar_log_monkey", "BANDAR_LOG_MONKEY_UNIT_NAME",
                 "icons_units_bandar_log_monkey/portrait_bandarlogmonkey", 80.0),  # Towers of Endurance
    ScriptMinion(758275367121177, "unit_bandar_log_monkey/u_bandar_log_monkey", "BANDAR_LOG_MONKEY_UNIT_NAME",
                 "icons_units_bandar_log_monkey/portrait_bandarlogmonkey", 80.0),  # campaign
    ScriptMinion(5091614101029844, "unit_bandar_log_monkey/u_bandar_log_monkey", "BANDAR_LOG_MONKEY_UNIT_NAME",
                 "icons_units_bandar_log_monkey/portrait_bandarlogmonkey", 80.0),  # campaign
    ScriptMinion(2590439287758574, "unit_blackpearl_crew_female/u_blackpearl_crew_female", "BLACK_PEARL_CREW_UNIT_NAME",
                 "icons_units_blackpearl_crew/portrait_blackpearl_crew_female", 4.0),  # Towers of Endurance
    ScriptMinion(8169073350788817, "unit_blackpearl_crew_female/u_blackpearl_crew_female", "BLACK_PEARL_CREW_UNIT_NAME",
                 "icons_units_blackpearl_crew/portrait_blackpearl_crew_female", 4.0),  # campaign
    ScriptMinion(4084663015782354, "unit_card_soldier_v4/u_card_soldier_v4", "CARD_SOLDIER_UNIT_NAME",
                 "icons_units_card_soldier/portrait_cardsoldier4", 1.0),  # Towers of Endurance
    ScriptMinion(7015898826449311, "unit_card_soldier_v2/u_card_soldier_v2", "CARD_SOLDIER_UNIT_NAME",
                 "icons_units_card_soldier/portrait_cardsoldier2", 1.0),  # Towers of Endurance
    ScriptMinion(2207399084365587, "unit_cauldron_born/u_cauldron_born_a", "CAULDRON_BORN_UNIT_NAME",
                 "icons_units_cauldron_born/portrait_cauldron_born1", 4.0),  # campaign
    ScriptMinion(2985347567858697, "unit_cauldron_born/u_cauldron_born_a", "CAULDRON_BORN_UNIT_NAME",
                 "icons_units_cauldron_born/portrait_cauldron_born1", 4.0),  # Towers of Endurance
    ScriptMinion(3026417329322044, "unit_cy_bug/u_cy_bug", "CY_BUG_UNIT_NAME",
                 "icons_units_cy_bug/portrait_cybug", 4.0),  # campaign
    ScriptMinion(1839743717606697, "unit_dunbroch_warrior/u_dunbroch_warrior", "DUNBROCH_WARRIOR_UNIT_NAME",
                 "icons_units_dunbroch_warrior/portrait_dunbroch_warrior", 4.0),  # Towers of Endurance
    ScriptMinion(6991657211317282, "unit_fairfolk_blue/u_fairfolk_blue", "FAIR_FOLK_UNIT_NAME",
                 "icons_units_fairfolk/portrait_fairfolk_blue", 4.0),  # Towers of Endurance
    ScriptMinion(7803746740370685, "unit_fairfolk_blue/u_fairfolk_blue", "FAIR_FOLK_UNIT_NAME",
                 "icons_units_fairfolk/portrait_fairfolk_blue", 4.0),  # campaign
    ScriptMinion(6222977093438968, "unit_feisty_furniture/u_feisty_furniture", "FEISTY_FURNITURE_UNIT_NAME",
                 "icons_units_feisty_furniture/portrait_feisty_furniture", 4.0),  # Towers of Endurance
    ScriptMinion(5249573924933804, "unit_flying_dutchman_crew/u_flying_dutchman_a", "FLYING_DUTCHMAN_CREW_UNIT_NAME",
                 "icons_units_flying_dutchman_crew/portrait_flyingdutchcrew", 1.0),  # Towers of Endurance
    ScriptMinion(1203141047063960, "unit_golden_cave_guardian/u_golden_cave_guardian", "GOLDEN_CAVE_GUARDIAN_UNIT_NAME",
                 "icons_units_cave_guardian/portrait_golden_cave_guard", 4.0),  # Towers of Endurance
    ScriptMinion(8445892977727726, "unit_goon/u_goon", "GOON_UNIT_NAME",
                 "icons_units_goon/portrait_goon", 1.0),  # Towers of Endurance
    ScriptMinion(2484121334851183, "unit_grasshopper/u_grasshopper", "GRASSHOPPER_UNIT_NAME",
                 "icons_units_grasshopper/portrait_grasshopper", 1.0),  # campaign
    ScriptMinion(2940201677595372, "unit_grasshopper/u_grasshopper", "GRASSHOPPER_UNIT_NAME",
                 "icons_units_grasshopper/portrait_grasshopper", 1.0),  # Towers of Endurance
    ScriptMinion(849875388301141, "unit_heros_duty_soldier/u_heros_duty_soldier", "HEROS_DUTY_SOLDIER_UNIT_NAME",
                 "icons_units_hero_duty_soldier/portrait_hero_duty_soldier", 4.0),  # Towers of Endurance
    ScriptMinion(135, "unit_hyena/u_hyena", "HYENA_UNIT_NAME", "icons_units_hyena/portrait_hyena", 1.0),  # campaign
    ScriptMinion(8504390825460539, "unit_hyena_ranged/u_hyena_ranged", "HYENA_UNIT_NAME",
                 "icons_units_hyena/portrait_hyena", 4.0),  # Towers of Endurance
    ScriptMinion(8992628868600459, "unit_hyena/u_hyena", "HYENA_UNIT_NAME",
                 "icons_units_hyena/portrait_hyena", 1.0),  # Towers of Endurance
    ScriptMinion(3460959051686191, "unit_imp/u_imp", "IMP_UNIT_NAME", "icons_units_imp/portrait_imp", 1.0),  # campaign
    ScriptMinion(8899475157202489, "unit_imp/u_imp", "IMP_UNIT_NAME",
                 "icons_units_imp/portrait_imp", 1.0),  # Towers of Endurance
    ScriptMinion(4170618875395494, "unit_jellyfish/u_jellyfish", "JELLYFISH_UNIT_NAME",
                 "icons_units_jellyfish/portrait_jellyfish", 1.0),  # Towers of Endurance
    ScriptMinion(4215626028839896, "unit_jellyfish/u_jellyfish", "JELLYFISH_UNIT_NAME",
                 "icons_units_jellyfish/portrait_jellyfish", 1.0),  # campaign
    ScriptMinion(2019480900514920, "unit_jolly_roger_pirate/u_jolly_roger_pirate", "JOLLY_ROGER_CREW_UNIT_NAME",
                 "icons_units_jolly_roger_pirate/portrait_jollyrogerpirate", 1.0),  # Towers of Endurance
    ScriptMinion(808904782695858, "unit_kakamora_v1/u_kakamora_v1", "KAKAMORA_UNIT_NAME",
                 "icons_units_kakamora/portrait_kakamora", 4.0),  # Towers of Endurance
    ScriptMinion(7507860139929848, "unit_kuzco_guard/u_kuzco_guard", "KUZCOS_GUARD_UNIT_NAME",
                 "icons_units_kuzco_guard/portrait_kuzco_guard", 1.0),  # Towers of Endurance
    ScriptMinion(2292698284869983, "unit_lonesome_ghost/u_lonesome_ghost", "LONESOME_GHOST_UNIT_NAME",
                 "icons_units_lonesome_ghost/portrait_lonesomeghost", 4.0),  # Towers of Endurance
    ScriptMinion(6001881699133543, "unit_lonesome_ghost/u_lonesome_ghost", "LONESOME_GHOST_UNIT_NAME",
                 "icons_units_lonesome_ghost/portrait_lonesomeghost", 4.0),  # campaign
    ScriptMinion(3267254572192500, "unit_menacing_cave_guardian/u_menacing_cave_guardian", "MENACING_CAVE_GUARDIAN_UNIT_NAME",
                 "icons_units_cave_guardian/portrait_menace_cave_guard", 1.0),  # Towers of Endurance
    ScriptMinion(2430723353594835, "unit_mermaid/u_mermaid_01", "MERFOLK_UNIT_NAME",
                 "icons_units_mermaid/portrait_mermaid_01", 1.0),  # Towers of Endurance
    ScriptMinion(381651270270350, "unit_mind_worker/u_mind_worker", "MIND_WORKER_UNIT_NAME",
                 "icons_units_mind_worker/portrait_mind_worker", 4.0),  # campaign
    ScriptMinion(1902156554687391, "unit_mind_worker/u_mind_worker", "MIND_WORKER_UNIT_NAME",
                 "icons_units_mind_worker/portrait_mind_worker", 4.0),  # Towers of Endurance
    ScriptMinion(2429308545686747, "unit_mrbig_guard/u_mrbig_guard", "MR_BIG_BODYGUARD_UNIT_NAME",
                 "icons_units_mrbig_guard/portrait_mrbig_guard", 1.0),  # Towers of Endurance
    ScriptMinion(78234537649464, "unit_nymph_a/u_nymph_a", "NYMPH_UNIT_NAME",
                 "icons_units_nymph/portrait_nymph_a", 1.0),  # Towers of Endurance
    ScriptMinion(4775228554624780, "unit_nymph_a/u_nymph_a", "NYMPH_UNIT_NAME",
                 "icons_units_nymph/portrait_nymph_a", 1.0),  # campaign
    ScriptMinion(8778460337674494, "unit_pig_archer/u_pig_archer", "PIG_ARCHER_UNIT_NAME",
                 "icons_units_pig_archer/portrait_pig_archer", 4.0),  # Towers of Endurance
    ScriptMinion(4597344022550447, "unit_ram/u_ram", "RAM_UNIT_NAME",
                 "icons_units_ram/portrait_ram", 1.0),  # Towers of Endurance
    ScriptMinion(1696330972093964, "unit_rhino_guard/u_rhino_guard", "RHINO_GUARD_UNIT_NAME",
                 "icons_units_rhino_guard/portrait_rhinoguard", 1.0),  # Towers of Endurance
    ScriptMinion(2616075322296139, "unit_rhino_guard/u_rhino_guard", "RHINO_GUARD_UNIT_NAME",
                 "icons_units_rhino_guard/portrait_rhinoguard", 1.0),  # campaign
    ScriptMinion(8348586603157706, "unit_robot_dog/u_robot_dog", "ROBOT_DOG_UNIT_NAME",
                 "icons_units_robot_dog/portrait_robotdog", 1.0),  # Towers of Endurance
    ScriptMinion(4223125015619336, "unit_satyr_brown/u_satyr_brown", "SATYR_UNIT_NAME",
                 "icons_units_satyr/portrait_satyr_brown", 4.0),  # campaign
    ScriptMinion(4777236140521767, "unit_satyr_brown/u_satyr_brown", "SATYR_UNIT_NAME",
                 "icons_units_satyr/portrait_satyr_brown", 4.0),  # Towers of Endurance
    ScriptMinion(7194846455928239, "unit_sea_turtle/u_sea_turtle", "SEA_TURTLE_UNIT_NAME",
                 "icons_units_sea_turtle/portrait_sea_turtle", 1.0),  # Towers of Endurance
    ScriptMinion(1333223846534530, "unit_silly_symphonies_skeleton/u_silly_symphonies_skeleton", "SILLY_SYMPHONIES_SKELETON_UNIT_NAME",
                 "icons_units_silly_symphonies_skeleton/portrait_silly_symphonies_skeleton", 1.0),  # campaign
    ScriptMinion(5411986143930567, "unit_steel_gargoyle/u_steel_gargoyle", "STEEL_GARGOYLE_UNIT_NAME",
                 "icons_units_steel_gargoyle/portrait_steelgargoyle", 1.0),  # campaign
    ScriptMinion(4317389957707012, "unit_stone_troll/u_stone_troll", "STONE_TROLL_UNIT_NAME",
                 "icons_units_stone_troll/portrait_stone_troll", 80.0),  # Towers of Endurance
    ScriptMinion(108161813674962, "unit_syndrome_security/u_syndrome_security", "SYNDROME_SECURITY_UNIT_NAME",
                 "icons_units_syndrome_security/portrait_syndromesecurity", 4.0),  # Towers of Endurance
    ScriptMinion(3667354290875560, "unit_tron_program/u_tron_program", "TRON_PROGRAM_UNIT_NAME",
                 "icons_units_tron_program/portrait_tron_program", 1.0),  # Towers of Endurance
    ScriptMinion(4799029638292706, "unit_tron_program/u_tron_program", "TRON_PROGRAM_UNIT_NAME",
                 "icons_units_tron_program/portrait_tron_program", 1.0),  # campaign
    ScriptMinion(8478790837286655, "unit_weasel/u_weasel", "WEASEL_UNIT_NAME",
                 "icons_units_weasel/portrait_weasel", 80.0),  # Towers of Endurance
    # Event enemies (handlers/events.EVENT_ROSTERS), by the bundle their classes play and the event text
    ScriptMinion(2406796535291490, "unit_mind_worker/u_mind_worker", "MIND_WORKER_UNIT_NAME",
                 "icons_units_mind_worker/portrait_mind_worker", 4.0),  # Intergalactic Rune Rumble (class GN)
    ScriptMinion(8869970885547499, "unit_kakamora_chief/u_kakamora_chief", "KAKAMORA_CHIEF_UNIT_NAME",
                 "icons_units_kakamora_chief/portrait_kakamora_chief"),  # Kakamora Chief (KQ)
    ScriptMinion(209691744164169, "unit_kakamora_v1/u_kakamora_v1", "KAKAMORA_UNIT_NAME",
                 "icons_units_kakamora/portrait_kakamora", 4.0),  # Raft Rumble / Kakamora Chief (Aq)
    ScriptMinion(889442866646246, "unit_kakamora_v1/u_kakamora_v1", "KAKAMORA_UNIT_NAME",
                 "icons_units_kakamora/portrait_kakamora", 4.0),  # Raft Rumble / Kakamora Chief (jY)
    ScriptMinion(8720168900178268, "unit_cave_statue/u_cave_statue", "CAVE_STATUE_UNIT_NAME",
                 "icons_units_cave_statue/portrait_cave_statue"),  # The Cave of Wonders: Treasure Room (hz)
    # The Queen's Clash card soldiers (the four suits; which model is which suit is not in the client: guessed)
    ScriptMinion(8574344838966530, "unit_card_soldier_v1/u_card_soldier_v1", "CARD_SOLDIER_UNIT_NAME",
                 "icons_units_card_soldier/portrait_cardsoldier", 1.0),  # IQ
    ScriptMinion(6402017627526517, "unit_card_soldier_v2/u_card_soldier_v2", "CARD_SOLDIER_UNIT_NAME",
                 "icons_units_card_soldier/portrait_cardsoldier2", 1.0),  # yJ
    ScriptMinion(1352955990830639, "unit_card_soldier_v3/u_card_soldier_v3", "CARD_SOLDIER_UNIT_NAME",
                 "icons_units_card_soldier/portrait_cardsoldier3", 1.0),  # E$
    ScriptMinion(8534259972173715, "unit_card_soldier_v4/u_card_soldier_v4", "CARD_SOLDIER_UNIT_NAME",
                 "icons_units_card_soldier/portrait_cardsoldier4", 1.0),  # Wtt (SUPPORT: hearts heal allies)
    ScriptMinion(7571174340397587, "unit_imp/u_imp", "IMP_UNIT_NAME",
                 "icons_units_imp/portrait_imp", 1.0),  # Donald Duck vs Hades (F$: the event Hades' imps)
    ScriptMinion(5058125130786168, "unit_silly_symphonies_skeleton/u_silly_symphonies_skeleton",
                 "SILLY_SYMPHONIES_SKELETON_UNIT_NAME",
                 "icons_units_silly_symphonies_skeleton/portrait_silly_symphonies_skeleton", 1.0),  # Sally (B$)
    ScriptMinion(5168849938429057, "unit_syndrome_security/u_syndrome_security", "SYNDROME_SECURITY_UNIT_NAME",
                 "icons_units_syndrome_security/portrait_syndromesecurity", 4.0),  # Supers Collide (snt)
    ScriptMinion(6158746963335681, "unit_syndrome_security/u_syndrome_security", "SYNDROME_SECURITY_UNIT_NAME",
                 "icons_units_syndrome_security/portrait_syndromesecurity", 4.0),  # Supers Collide (jJ)
)
BY_ID = {m.definition_id: m for m in MINIONS}

@dataclass(frozen=True)
class HeroVariant:
    hero: int  # the playable hero (gamedata unit) whose kit the variant class runs
    skin: int = 0  # one of the hero's gamedata skins (skinItemId) the variant wears
    name_key: str = ""  # its own name (else the hero's)


# Towers of Endurance hero variants (from the tower previews): the variant classes use the hero's ability ids; Horned
# King, Robin Hood and the Sheriff swap one ability class for a tower one (slot 2, 2 and 1).
_TOWER_VARIANTS = {
    697612268669496: 149,  # Captain Hook
    4966935831092661: 2541505114257629,  # Davy Jones
    8898161250932666: 3793696733556542,  # Demona
    769941980471067: 4264839534548679,  # Hades
    6329262511482740: 1680592376157339,  # Hopper
    2140143946676504: 4996798494226789,  # Horned King
    8311027445320116: 150,  # Jack Sparrow
    7842699187365115: 4505487594415447,  # Jafar
    5853332874999445: 6248908469179626,  # Kronk
    6265747626877995: 1833609470868558,  # Maui
    5858239058428052: 508341540759214,  # Merida
    5116906015396729: 4655438307398817,  # Queen of Hearts
    3544880188109125: 5710225926985727,  # Robin Hood
    3808122087034322: 5584717432624453,  # Scar
    7055485146292770: 7266520144288097,  # Sheriff of Nottingham
    7874108184169021: 72,  # Tinker Bell
}
SYNDROME, JAFAR, HADES, ELSA2 = 3368663937660261, 4505487594415447, 4264839534548679, 3077390668497398
HERO_VARIANTS: dict[int, HeroVariant] = {vid: HeroVariant(h) for vid, h in _TOWER_VARIANTS.items()} | {
    # Inferno / Ascension campaign bosses (the arena Hades / Mickey; the Hades class's abilities look for the Mickey)
    1861638347042510: HeroVariant(HADES, 161988159679003, client_key("arena_hades_name")),  # the arena Hades skin
    9003565924362054: HeroVariant(39, 4822342859084907, client_key("arena_mickey_name")),  # the arena Mickey skin
    # Event bosses (handlers/events.EVENT_ROSTERS): the classes the events' mutators look for
    4234654631076577: HeroVariant(8079429168333959),  # Emperor Zurg (Intergalactic Rune Rumble)
    5217059940040723: HeroVariant(11),  # Buzz Lightyear (Intergalactic Rune Rumble)
    640417862299850: HeroVariant(SYNDROME),  # Supervillain Scuffle: its 8 mutators, aura Event_202004_Incredibles_C
    8063684444320327: HeroVariant(SYNDROME),  # Heroic Showdown: aura Event_Onboarding_Elastigirl_A
    3043900226130490: HeroVariant(5584717432624453),  # Scar (aura EVENT_202002_LIONKING_C: Scar's Lair, Final Showdown)
    8435117305040257: HeroVariant(5584717432624453),  # Scar (Goofy vs Scar: aura ..._SENSATIONALSIX_1_B)
    5848483329990929: HeroVariant(4655438307398817),  # Queen of Hearts (The Queen's Clash)
    8040425887314762: HeroVariant(370744954140450),  # Sally (Sally's Potent Potions)
    3021632039659421: HeroVariant(JAFAR),  # The Guardian Lair, with the Genie below
    7605712917452499: HeroVariant(1198211944242711),  # Genie
    2808455732321530: HeroVariant(JAFAR),  # Lamp Chamber: a mutator empowers his team, wins on his defeat
    221403608613517: HeroVariant(JAFAR),  # Daisy Duck vs Jafar: the "vs" events' shape
    5559371775396751: HeroVariant(HADES),  # Donald Duck vs Hades: its slot 4 summons imps
    # Mother Knows Best: its mutator (aura EVENT_202102_MOTHERGOTHEL) is won when one unit falls, lost when another does
    5955019119988617: HeroVariant(ELSA2),  # Elsa (Into the Unknown)
    4372620401308922: HeroVariant(ELSA2),  # Elsa (Prestige: Into the Unknown)
}

# Units whose class spawns (raid_kits.spawn_slots): unit -> {ability slot: summoned script minion}. The script sets
# every stat of the spawned unit, so the template's stats are those of a content raid boss summon
# (battle_bootstrap.RAID_SUMMON_STATS). The cap is not in the client: SUMMON_MAX_COUNT.
SUMMONS = {
    # Pixie Duster Grey: slot 2's template with the stats of a Green Pixie Duster on the field, or slot 1's with a
    # Blue one's: slot 1 summons the Blue, slot 2 the Green
    6793504973620608: {1: 2736539521506414, 2: 5671264099414844},
    7473260072687503: {0: 1195414538489109},  # Trash Can (its basic): a Unicorn with a field Unicorn's stats
    6845400675393552: {2: 4518135635864306},  # Gabby Gabby: 3 of slot 2's with a field Dummy's stats
    8869970885547499: {2: 209691744164169},  # Kakamora Chief (special B): with a field Kakamora's stats
    # Cave Statue (its two specials): its guardians (which slot spawns which is a guess)
    8720168900178268: {1: 1203141047063960, 2: 3267254572192500},
    4234654631076577: {4: 2406796535291490},  # event Zurg: a Mind Worker with a field one's stats
    5217059940040723: {4: 2406796535291490},  # event Buzz: the same, on the start of his turn
    # event Scar: hyenas, melee or ranged, whichever is fewer (the event's mutator names both)
    3043900226130490: {1: 8992628868600459, 3: 8504390825460539},
    5559371775396751: {4: 7571174340397587},  # event Hades (slot 4): his imps
    3021632039659421: {3: 541339423403349},  # Guardian Lair Jafar: a Guardian Cobra (guess)
}


def _load_content_events() -> None:
    """Rebuilt events (content/events/<name>.json) bring their own units: "script_minions" ([{"id", "asset",
    "name_key", "icon", "range"?}]), "hero_variants" ([{"id", "hero", "skin"?, "name_key"?}]), "summons"
    ({unit id: {ability slot: script minion id}}) and "spell_summons" ({unit id: {ability slot: spell id}}, see
    SPELL_SUMMONS)."""
    from arcane_server.event_rosters import content_event_docs

    global MINIONS
    for name, doc in content_event_docs():
        for m in doc.get("script_minions", ()):
            sm = ScriptMinion(int(m["id"]), m["asset"], m.get("name_key", ""), m.get("icon", ""), float(m.get("range", 0.0)))
            if sm.definition_id in BY_ID or sm.definition_id in HERO_VARIANTS:
                raise RuntimeError(f"content/events/{name}: unit {sm.definition_id} is already defined")
            MINIONS += (sm,)
            BY_ID[sm.definition_id] = sm
        for v in doc.get("hero_variants", ()):
            vid = int(v["id"])
            if vid in BY_ID or vid in HERO_VARIANTS:
                raise RuntimeError(f"content/events/{name}: unit {vid} is already defined")
            HERO_VARIANTS[vid] = HeroVariant(int(v["hero"]), int(v.get("skin", 0)), v.get("name_key", ""))
        for uid, slots in (doc.get("summons") or {}).items():
            if int(uid) in SUMMONS:
                raise RuntimeError(f"content/events/{name}: summons of {uid} are already defined")
            SUMMONS[int(uid)] = {int(k): int(x) for k, x in slots.items()}
        for uid, slots in (doc.get("spell_summons") or {}).items():
            if int(uid) in SPELL_SUMMONS:
                raise RuntimeError(f"content/events/{name}: spell summons of {uid} are already defined")
            SPELL_SUMMONS[int(uid)] = {int(k): int(x) for k, x in slots.items()}


SUMMON_MAX_COUNT = 5  # estimate: the most common add_unit_max_count of the content summons
# Units whose class spawns a gamedata unit some spell summons: unit -> {ability slot: spell}; the template is that
# spell's addUnit row (unit, max count, stats). The tower Sheriff's slot 1 class spawns its template (offense
# 0.8x, health 0.3x and the speed of the Sheriff) when an opponent gains a helpful effect: Trigger's Tower, which
# stands on the enemy side of Tower I-B next to the Sheriff with an enemy health bar (measured on the device), the unit
# of the Trigger's Tower spell
# (unit 6297569901211626, spell_trigger/u_trigger). The spawn uses the Scar summon puff (e_scar_special_b_spawn).
SPELL_SUMMONS = {7055485146292770: {1: 8847748074180172}}

_load_content_events()


def _role(gd: Gamedata, categories: tuple[int, ...]) -> int:
    from arcane_server import battle_bootstrap as bb

    return next((c for c in categories if c in bb.role_categories(gd)), 0)


def _effects(gd: Gamedata, src: str, m: ScriptMinion, model: B.Unit) -> list[int]:
    """The bundle's own effects, those its script classes name, and the shared (unit_shared_*) hit / buff effects its
    content stand-in carries (the list a content minion of that role and range has)."""
    rows = gd.by_id("abilityEffect")
    own = {i for i, e in rows.items() if str(e.get("assetId", "")).split("/")[0] == m.bundle}
    shared = {i for i in model.effect_def_ids if i in rows and str(rows[i].get("assetId", "")).startswith("unit_shared")}
    return sorted(own | shared | set(raid_kits.referenced_effects(src, m.definition_id, frozenset(rows))))


def _ability_stem(m: ScriptMinion) -> str:
    stem = m.name_key.removesuffix("_UNIT_NAME") or m.bundle.removeprefix("unit_").upper()
    return ABILITY_NAME_STEM.get(m.name_key, stem.replace("_", ""))


def build(gd: Gamedata, m: ScriptMinion) -> B.Unit | None:
    built = _build(gd, m)
    return built[0] if built else None


def _build(gd: Gamedata, m: ScriptMinion) -> tuple[B.Unit, float] | None:
    """The minion at its model's level / rarity / gear tier (a minion template), None if the script lacks it."""
    from arcane_server import battle_bootstrap as bb

    src = raid_kits.script(gd)
    uc = raid_kits.unit_class(src, m.definition_id)
    slots = raid_kits.ability_slots(src, m.definition_id)
    if uc is None or 0 not in slots:
        return None
    categories = uc[1]
    projectile = raid_kits.basic_is_projectile(src, slots[0].cls)
    range_cls = bb.range_class(m.range) if m.range else 1 if projectile else 0
    model_id = bb.stand_in_minion(gd, range_cls, _role(gd, categories), m.bundle.removeprefix("unit_"))
    model_t = bb.known_minion_templates(gd)[model_id]
    model = model_t.unit
    u = B.Unit()
    u.CopyFrom(model)
    u.definition_id, u.name_key, u.icon, u.asset_id = m.definition_id, m.name_key, m.icon, m.asset
    u.attack_range = m.range or (model.attack_range if projectile else 1.0)
    del u.effect_def_ids[:], u.abilities[:], u.category_ids[:], u.alt_prefabs[:]
    u.effect_def_ids.extend(_effects(gd, src, m, model))
    u.category_ids.extend(categories)
    specials = [a for a in model.abilities if a.ability_type == SPECIAL]
    stem = _ability_stem(m)
    n_special = 0
    for slot, s in slots.items():
        kind = KIND[s.kind]
        a = u.abilities.add(id=slot, level=1, shape=1, geo_id=GEO, ability_type=kind, sort_order=slot, icon=NPC_ICON,
                            activated=kind != PASSIVE, target_enemy=kind != PASSIVE, target_self=kind == PASSIVE)
        if kind == BASIC:
            a.name_key = f"{stem}_ABILBASIC_NAME"
        elif kind == SPECIAL:
            like = specials[min(n_special, len(specials) - 1)] if specials else None
            letter = "AB"[raid_kits.dialect(src).slot_names[1:3].index(s.var)]  # first special -> A, second -> B
            a.name_key = f"{stem}_ABILSPECIAL{letter}_NAME"
            a.mana_cost = like.mana_cost if like else 3
            a.initial_mana = like.initial_mana if like else 0
            if like is not None and (like.target_ally or (like.target_self and not like.target_enemy)):
                a.target_enemy, a.target_ally, a.target_self = False, like.target_ally, like.target_self
            a.target_enemy, a.target_ally, a.target_self = special_target(
                gd, s.cls, (a.target_enemy, a.target_ally, a.target_self))
            n_special += 1
        else:
            a.name_key = f"{stem}_ABILPASSIVEA_NAME"
        if (add := _summon(gd, m.definition_id, slot)) is not None:
            a.add_unit.CopyFrom(add)
            a.add_unit_max_count = SUMMON_MAX_COUNT
    return u, model_t.gear_progress


Target = tuple[bool, bool, bool]  # Ability (target_enemy, target_ally, target_self)


@cache
def official_targets(gd: Gamedata) -> dict[str, Target]:
    """Ability class -> the target flags known data gives its specials (gamedata heroes, content minions); a
    class given different flags by two of them is left out."""
    from arcane_server import battle_bootstrap as bb

    src = raid_kits.script(gd)
    seen: dict[str, set[Target]] = {}
    for unit in gd.table("unit"):
        slots = raid_kits.ability_slots(src, int(unit["id"]))
        for ab in unit.get("abilities") or []:
            s = slots.get(int(ab.get("id", 0)))
            if s and s.cls and s.kind == "special" and ab.get("levels"):
                lv = ab["levels"][0]
                seen.setdefault(s.cls, set()).add(
                    (bool(lv.get("targetEnemy")), bool(lv.get("targetAlly")), bool(lv.get("targetSelf"))))
    for t in bb.known_minion_templates(gd).values():
        slots = raid_kits.ability_slots(src, t.unit.definition_id)
        for ab in t.unit.abilities:
            s = slots.get(ab.id)
            if s and s.cls and s.kind == "special":
                seen.setdefault(s.cls, set()).add((ab.target_enemy, ab.target_ally, ab.target_self))
    return {cls: next(iter(flags)) for cls, flags in seen.items() if len(flags) == 1}


def special_target(gd: Gamedata, ability_class: str, stand_in: Target) -> Target:
    """The target flags of a script minion's special. The client points an activated ability at a unit its flags
    allow (the ability data's target check: self / ally / enemy) and the class acts on that unit, so a class that
    strikes its target sent with the stand-in's self-only flags strikes its own caster (the campaign Grasshopper's
    taunting strike hurt the Grasshopper). Known flags of the same class win (official_targets); else what the
    class does to its target (raid_kits.ability_target): an attack targets enemies only, a class that only helps its
    target keeps the stand-in's friendly flags or gets ally + self (as the gamedata healers); else the stand-in's."""
    if (official := official_targets(gd).get(ability_class)) is not None:
        return official
    kind = raid_kits.ability_target(raid_kits.script(gd), ability_class)
    if kind == "enemy":
        return True, False, False
    if kind == "ally" and stand_in[0]:
        return False, True, True
    return stand_in


def target_problems(src: str, u: B.Unit) -> list[str]:
    """Specials of `u` whose target flags contradict their class (raid_kits.ability_target): an attack that may be
    pointed at its own team, or a helping class pointed at enemies."""
    slots = raid_kits.ability_slots(src, u.definition_id)
    out = []
    for a in u.abilities:
        s = slots.get(a.id)
        if a.ability_type != SPECIAL or s is None or not s.cls:
            continue
        kind = raid_kits.ability_target(src, s.cls)
        if (kind == "enemy" and (a.target_ally or a.target_self or not a.target_enemy)) or \
                (kind == "ally" and a.target_enemy):
            out.append(f"special {a.id} ({s.cls}) attacks / helps its target ({kind}) but targets "
                       f"enemy={a.target_enemy} ally={a.target_ally} self={a.target_self}")
    return out


@cache
def _templates(gd: Gamedata) -> tuple[tuple[int, B.Unit, float], ...]:
    return tuple((m.definition_id, *b) for m in MINIONS if (b := _build(gd, m)) is not None)


def templates(gd: Gamedata) -> dict[int, B.Unit]:
    """definition id -> unit (at its model's level / rarity / gear tier) of every minion the script defines."""
    return {mid: u for mid, u, _ in _templates(gd)}


def gear_progress(gd: Gamedata) -> dict[int, float]:
    """definition id -> the gear progress of the content stand-in its stats are copied from (MinionTemplate): the
    stats are that battle's, so they move along the stat curve from the same point."""
    return {mid: p for mid, _, p in _templates(gd)}


def _summon(gd: Gamedata, definition_id: int, slot: int) -> B.Unit | None:
    """The template `definition_id`'s ability `slot` spawns (SUMMONS), shaped as a summon."""
    from arcane_server import battle_bootstrap as bb

    sid = SUMMONS.get(definition_id, {}).get(slot, 0)
    if (udef := gd.by_id("unit").get(sid)) is not None:  # a gamedata SPAWNED_ADD unit (the Giant Cy-Bug's eggs)
        return bb.summon_unit(gd, udef, bb.RAID_SUMMON_STATS)
    summoned = BY_ID.get(sid)
    built = _build(gd, summoned) if summoned is not None else None
    return bb.as_summon(built[0], bb.RAID_SUMMON_STATS) if built is not None else None


def hero_variant(gd: Gamedata, definition_id: int, level: int, rarity: int, gear_tier: int, ability_level: int = 0,
                 gear_progress: float = 0.0) -> B.Unit:
    """A hero variant: its hero's gamedata unit with the variant's id, categories, skin and name, abilities on the
    variant class's slots (see the module doc)."""
    from arcane_server import battle_bootstrap as bb

    v = HERO_VARIANTS[definition_id]
    u = bb.gamedata_unit(gd, v.hero, level, rarity, gear_tier, ability_level, gear_progress, enemy=True)
    src = raid_kits.script(gd)
    uc = raid_kits.unit_class(src, definition_id)
    u.definition_id = definition_id
    if uc is not None:
        del u.category_ids[:]
        u.category_ids.extend(uc[1])
    if v.name_key:
        u.name_key = v.name_key
    skin = next((k for k in gd.by_id("unit")[v.hero].get("skins") or [] if int(k.get("skinItemId", 0)) == v.skin), None)
    if skin is not None:
        u.skin_item_id = v.skin
        u.asset_id = skin.get("battlePrefab") or u.asset_id
        u.icon = skin.get("unitIcon") or u.icon
    slots = raid_kits.ability_slots(src, definition_id)
    have = {a.id: a for a in u.abilities}
    for a in u.abilities:  # a leader ability the class runs as a passive (the variant leads no squad)
        if a.ability_type == bb.ABILITY_TYPE["LEADER"] and a.id in slots and slots[a.id].kind == "passive":
            a.ability_type = PASSIVE
    top = max((a.level for a in u.abilities), default=1)
    for slot, s in slots.items():
        if slot not in have and s.kind == "passive":
            have[slot] = u.abilities.add(id=slot, level=top, shape=1, geo_id=GEO, ability_type=PASSIVE,
                                         sort_order=slot, icon=NPC_ICON, target_self=True)
    for slot in SUMMONS.get(definition_id, {}):
        if slot in have and (add := _summon(gd, definition_id, slot)) is not None:
            have[slot].add_unit.CopyFrom(add)
            have[slot].add_unit_max_count = have[slot].add_unit_max_count or SUMMON_MAX_COUNT
    for slot, spell in SPELL_SUMMONS.get(definition_id, {}).items():
        if slot in have and (summon := bb.spell_summon(gd, spell, 1, (level, rarity, gear_tier))) is not None:
            have[slot].add_unit.CopyFrom(summon[0])
            have[slot].add_unit_max_count = summon[1]
    return u


def problems(gd: Gamedata, bundles: set[str] | None = None) -> list[str]:
    """Startup check: every listed minion has a script class with a basic attack and its bundles exist; every hero
    variant has a class whose ability ids are its hero's; no special of theirs is pointed at a unit its class would
    hurt or help wrongly (target_problems)."""
    out = []
    built = templates(gd)
    src = raid_kits.script(gd)
    units = gd.by_id("unit")
    for m in MINIONS:
        if m.definition_id in units:
            out.append(f"script minion {m.asset} ({m.definition_id}) is a gamedata unit")
        if m.definition_id not in built:
            out.append(f"script minion {m.asset} ({m.definition_id}): no unit class / basic attack in the battle script")
        for ref in (m.asset, m.icon):
            if bundles is not None and ref and ref.split("/")[0] not in bundles:
                out.append(f"script minion {m.asset} ({m.definition_id}): missing bundle {ref.split('/')[0]}")
    for vid, v in HERO_VARIANTS.items():
        hero = units.get(v.hero)
        slots = raid_kits.ability_slots(src, vid)
        mine = {int(a.get("id", 0)) for a in (hero or {}).get("abilities") or []}
        extra = {s for s in slots if s not in mine and slots[s].kind != "passive"}
        if hero is None or not slots or not mine <= set(slots) or extra:
            out.append(f"hero variant {vid}: script ability slots {sorted(slots)} do not hold hero {v.hero}'s ability "
                       f"ids {sorted(mine)} (or add a non-passive slot)")
        if v.skin and not any(int(k.get("skinItemId", 0)) == v.skin for k in (hero or {}).get("skins") or []):
            out.append(f"hero variant {vid}: hero {v.hero} has no skin {v.skin}")
    for uid, u in [*built.items(), *((vid, hero_variant(gd, vid, 1, 1, 1)) for vid in HERO_VARIANTS)]:
        out += [f"unit {uid}: {p}" for p in target_problems(src, u)]
    for uid, by_slot in SUMMONS.items():
        for slot, sid in by_slot.items():
            if sid not in BY_ID and units.get(sid, {}).get("unitType") != "SPAWNED_ADD":
                out.append(f"summons of {uid}: slot {slot} names {sid}, not a script minion or a gamedata summon")
    return out
