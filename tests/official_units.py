"""Expected heroes (stats and power ratings at the given progression), written down as game
facts: the stat and power formulas (unit_stats.py) must reproduce them from the v29 gamedata."""

from __future__ import annotations

from arcane_server.proto import serverproto_pb2 as pb

# field -> expected value of pb.Unit
OFFICIAL_UNITS: tuple[dict, ...] = (
    {'definition_id': 6569997645566663, 'rarity': 5, 'level': 41, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 5, 'offense': 700, 'defense': 137, 'health': 5794, 'crit_chance': 0.05, 'crit_power': 1.5, 'attack_speed': 0.18, 'ability_level': [1, 1, 1, 1], 'power_rating': 428, 'sorcerer_stone_id': 6548409204418918, 'speed': 112, 'potency': 0.07, 'tenacity': 0.05, 'evasion': 0.04},  # Mulan
    {'definition_id': 3940153952957, 'rarity': 4, 'level': 35, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 4, 'offense': 284, 'defense': 143, 'health': 4977, 'crit_chance': 0.05, 'crit_power': 1.5, 'attack_speed': 0.16, 'ability_level': [1, 1, 1, 1, 1], 'power_rating': 268, 'speed': 93, 'potency': 0.03, 'tenacity': 0.08},  # Princeeric
    {'definition_id': 1225277242550499, 'rarity': 3, 'level': 8, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 2, 'offense': 88, 'defense': 39, 'health': 910, 'crit_chance': 0.05, 'crit_power': 1.5, 'attack_speed': 0.28, 'ability_level': [1, 0, 0, 1, 0, 1], 'power_rating': 97, 'speed': 90, 'tenacity': 0.05},  # Merlin
    {'definition_id': 150, 'rarity': 7, 'level': 52, 'gear_slot_equipped': [False, False, False, False, True, False], 'gear_tier': 5, 'offense': 1037, 'defense': 218, 'health': 10978, 'crit_chance': 0.09, 'crit_power': 1.5, 'attack_speed': 0.23, 'ability_level': [3, 1, 2, 3], 'power_rating': 566, 'sorcerer_stone_id': 6548409204418918, 'speed': 112, 'potency': 0.07, 'tenacity': 0.05, 'evasion': 0.05},  # Jacksparrow
    {'definition_id': 4655438307398817, 'rarity': 5, 'level': 35, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 4, 'offense': 505, 'defense': 126, 'health': 4560, 'crit_chance': 0.05, 'crit_power': 1.5, 'attack_speed': 0.18, 'ability_level': [1, 1, 1, 1], 'power_rating': 288, 'speed': 100, 'tenacity': 0.05},  # Queenofhearts
    {'definition_id': 801834318881896, 'rarity': 7, 'level': 50, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 6, 'offense': 835, 'defense': 458, 'health': 18392, 'crit_chance': 0.05, 'crit_power': 1.5, 'attack_speed': 3.68, 'ability_level': [3, 3, 1, 1], 'power_rating': 639, 'sorcerer_stone_id': 2330941015221671, 'speed': 99, 'potency': 0.04, 'tenacity': 0.17},  # Fred
    {'definition_id': 4661355706205481, 'rarity': 6, 'level': 41, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 5, 'offense': 770, 'defense': 161, 'health': 7695, 'crit_chance': 0.05, 'crit_power': 1.5, 'attack_speed': 0.24, 'ability_level': [2, 0, 1, 2, 1], 'power_rating': 478, 'sorcerer_stone_id': 6548409204418918, 'speed': 105, 'potency': 0.07, 'tenacity': 0.05},  # Judyhopps
    {'definition_id': 6953054855346287, 'rarity': 4, 'level': 19, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 2, 'offense': 180, 'defense': 39, 'health': 1449, 'crit_chance': 0.05, 'crit_power': 1.5, 'attack_speed': 0.18, 'ability_level': [1, 1, 0, 1, 0], 'power_rating': 128, 'speed': 100, 'tenacity': 0.05},  # Kingtriton
    {'definition_id': 151, 'rarity': 5, 'level': 41, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 5, 'offense': 440, 'defense': 179, 'health': 6435, 'crit_chance': 0.09, 'crit_power': 1.5, 'attack_speed': 0.2, 'ability_level': [1, 0, 1, 1, 1, 1], 'power_rating': 383, 'recovery': 557, 'speed': 83, 'potency': 0.07, 'tenacity': 0.08},  # Woody
    {'definition_id': 5702473871132078, 'rarity': 4, 'level': 43, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 5, 'offense': 610, 'defense': 115, 'health': 4463, 'crit_chance': 0.09, 'crit_power': 1.5, 'attack_speed': 0.23, 'ability_level': [1, 1, 1, 1], 'power_rating': 355, 'recovery': 292, 'speed': 104, 'tenacity': 0.05},  # Bigbaby
    {'definition_id': 8279082701199788, 'rarity': 7, 'level': 61, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 7, 'offense': 1050, 'defense': 398, 'health': 16220, 'crit_chance': 0.1, 'crit_power': 1.5, 'attack_speed': 0.23, 'ability_level': [3, 4, 3, 1, 2], 'power_rating': 860, 'recovery': 1077, 'sorcerer_stone_id': 8357249249127864, 'speed': 123, 'potency': 0.19, 'tenacity': 0.13, 'evasion': 0.15},  # Hirohamada
    {'definition_id': 1680592376157339, 'rarity': 5, 'level': 35, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 4, 'offense': 356, 'defense': 185, 'health': 7539, 'crit_chance': 0.05, 'crit_power': 1.5, 'attack_speed': 0.28, 'ability_level': [1, 1, 1, 1, 1], 'power_rating': 343, 'sorcerer_stone_id': 7247007240911497, 'speed': 90, 'tenacity': 0.08},  # Hopper
    {'definition_id': 1424534210893336, 'rarity': 4, 'level': 6, 'gear_slot_equipped': [True, True, True, False, False, False], 'gear_tier': 1, 'offense': 85, 'defense': 21, 'health': 525, 'crit_chance': 0.05, 'crit_power': 1.5, 'attack_speed': 0.23, 'ability_level': [1, 1, 0, 0], 'power_rating': 95, 'speed': 100, 'tenacity': 0.05},  # Jackjack
    {'definition_id': 2516666220254955, 'rarity': 4, 'level': 35, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 5, 'offense': 540, 'defense': 105, 'health': 4568, 'crit_chance': 0.12, 'crit_power': 1.5, 'attack_speed': 0.18, 'ability_level': [1, 1, 1, 1, 1], 'power_rating': 402, 'sorcerer_stone_id': 6548409204418918, 'speed': 108, 'potency': 0.04, 'tenacity': 0.05},  # Moana
    {'definition_id': 7037884731553552, 'rarity': 4, 'level': 35, 'gear_slot_equipped': [False, False, True, False, True, False], 'gear_tier': 3, 'offense': 226, 'defense': 96, 'health': 3178, 'crit_chance': 0.05, 'crit_power': 1.5, 'attack_speed': 0.2, 'ability_level': [1, 1, 1, 1], 'power_rating': 219, 'recovery': 177, 'speed': 80, 'tenacity': 0.05},  # Frozone
    {'definition_id': 124, 'rarity': 2, 'level': 8, 'gear_slot_equipped': [False, False, False, False, False, False], 'gear_tier': 2, 'offense': 76, 'defense': 39, 'health': 1112, 'crit_chance': 0.05, 'crit_power': 1.5, 'attack_speed': 0.23, 'ability_level': [1, 0, 1, 1, 0], 'power_rating': 82, 'speed': 90, 'tenacity': 0.05},  # Oogieboogie
)
# spell level -> expected power rating
OFFICIAL_SPELL_POWER = {1: 5, 2: 15, 3: 20}
MULAN = 6569997645566663  # level 41, 5 stars, gear tier 5, with a speed stone


def official_units() -> list[pb.Unit]:
    return [pb.Unit(**d) for d in OFFICIAL_UNITS]

