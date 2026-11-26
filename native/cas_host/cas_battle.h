/*
 * SPDX-License-Identifier: GPL-3.0-only WITH additional permission (below)
 * Copyright (C) the arcane-server contributors
 *
 * This program (cas_host) is free software: you can redistribute it and/or modify it under the terms of the GNU
 * General Public License as published by the Free Software Foundation, version 3.
 *
 * Additional permission under GNU GPL version 3 section 7: if you modify cas_host by linking or combining it with
 * the battle engine library shipped in the game client (libcas-battle.so), or a modified version of that library,
 * the licensors of cas_host grant you additional permission to convey the resulting work. Corresponding Source for a
 * non-source form of such a combination need not include the source code of that library.
 *
 * This permission concerns cas_host only. It gives you no right to distribute the engine library itself, which
 * belongs to its owners: take it from your own copy of the game client; this project does not distribute it.
 */
/* The battle engine's exported functions cas_host calls (libcas-battle.so, from the game client). */
#ifndef CAS_BATTLE_H
#define CAS_BATTLE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

extern int Battle_GetVersion(void);
extern void Battle_SetMaxInstances(int maxBattles);
extern bool Battle_HadFatalError(int battleId);
extern const char *Battle_GetLastFatalError(int battleId);
extern bool Battle_Init(int *outBattleId);
extern void Battle_Shutdown(int battleId);
extern void Battle_Bootstrap(int battleId, uint8_t *script, size_t scriptLen, uint8_t *bootstrap, size_t bootstrapLen,
                             bool debug);
extern void Battle_Begin(int battleId);
extern void Battle_HandlePlayerMessage(int battleId, uint8_t playerId, uint8_t *msg, size_t offset, size_t len);
extern void Battle_HandlePlayerForfeit(int battleId, uint8_t playerId);
extern void Battle_SetBattleValue(int battleId, int32_t key, int64_t value);
extern void Battle_UpdateWithFlags(int battleId, float dt, float udt, int32_t hostFlags, int64_t unixNow);
extern uint8_t *Battle_GetUpdateResultBuffer(int battleId, size_t *len);
extern uint8_t *Battle_GetCatchUpBuffer(int battleId, size_t *len);
extern void Battle_FinishedReadingBuffer(int battleId);
extern uint32_t Battle_GetTotalMem(int battleId);
extern bool Battle_IsV2(int battleId);

#endif
