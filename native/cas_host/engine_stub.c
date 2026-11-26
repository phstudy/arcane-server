/*
 * SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) the arcane-server contributors
 */
/*
 * Link-time stand-in for the battle engine: build.sh links cas_host against this library (soname libcas-battle.so)
 * so the helper builds without the game's library; at run time the linker loads the real libcas-battle.so from the
 * battle host's sysroot. Including cas_battle.h makes the compiler check every signature; a function missing here
 * fails the helper's link. Never installed or run.
 */
#include "cas_battle.h"

int Battle_GetVersion(void) { return 0; }
void Battle_SetMaxInstances(int maxBattles) { (void)maxBattles; }
bool Battle_HadFatalError(int battleId) { (void)battleId; return false; }
const char *Battle_GetLastFatalError(int battleId) { (void)battleId; return ""; }
bool Battle_Init(int *outBattleId) { (void)outBattleId; return false; }
void Battle_Shutdown(int battleId) { (void)battleId; }
void Battle_Bootstrap(int battleId, uint8_t *script, size_t scriptLen, uint8_t *bootstrap, size_t bootstrapLen,
                      bool debug) {
    (void)battleId; (void)script; (void)scriptLen; (void)bootstrap; (void)bootstrapLen; (void)debug;
}
void Battle_Begin(int battleId) { (void)battleId; }
void Battle_HandlePlayerMessage(int battleId, uint8_t playerId, uint8_t *msg, size_t offset, size_t len) {
    (void)battleId; (void)playerId; (void)msg; (void)offset; (void)len;
}
void Battle_HandlePlayerForfeit(int battleId, uint8_t playerId) { (void)battleId; (void)playerId; }
void Battle_SetBattleValue(int battleId, int32_t key, int64_t value) { (void)battleId; (void)key; (void)value; }
void Battle_UpdateWithFlags(int battleId, float dt, float udt, int32_t hostFlags, int64_t unixNow) {
    (void)battleId; (void)dt; (void)udt; (void)hostFlags; (void)unixNow;
}
uint8_t *Battle_GetUpdateResultBuffer(int battleId, size_t *len) { (void)battleId; *len = 0; return 0; }
uint8_t *Battle_GetCatchUpBuffer(int battleId, size_t *len) { (void)battleId; *len = 0; return 0; }
void Battle_FinishedReadingBuffer(int battleId) { (void)battleId; }
uint32_t Battle_GetTotalMem(int battleId) { (void)battleId; return 0; }
bool Battle_IsV2(int battleId) { (void)battleId; return false; }
