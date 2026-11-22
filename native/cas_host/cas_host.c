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
/*
 * cas_host: runs the client's battle engine (libcas-battle.so, Android arm64) as a server-side process.
 *
 * The engine library is loaded by bionic's linker; on the x86_64 battle host this whole process runs
 * under qemu-aarch64 with a minimal Android sysroot (see native/cas_host/build.sh).
 *
 * Protocol on stdin/stdout, all integers little endian. One process can host many battles.
 *   request : u32 len | u8 op | payload[len-1]
 *   response: u32 len | u8 status (0 ok, 1 error) | payload[len-1]
 * Ops (payload layouts):
 *   OP_VERSION   ()                                   -> i32 version
 *   OP_SCRIPT    (bytes script)                       -> ()            cache the battle script for later bootstraps
 *   OP_INIT      ()                                   -> i32 battle_id
 *   OP_BOOTSTRAP (i32 id, u8 debug, bytes bootstrap)  -> ()            uses the cached script
 *   OP_BEGIN     (i32 id)                             -> ()
 *   OP_MESSAGE   (i32 id, u8 player, bytes msg)       -> ()
 *   OP_FORFEIT   (i32 id, u8 player)                  -> ()
 *   OP_UPDATE    (i32 id, f32 dt, f32 udt, i32 flags, i64 now) -> bytes result (the update result buffer)
 *   OP_CATCHUP   (i32 id)                             -> bytes catch-up buffer
 *   OP_SETVALUE  (i32 id, i32 key, i64 value)         -> ()
 *   OP_SHUTDOWN  (i32 id)                             -> ()
 *   OP_ISV2      (i32 id)                             -> u8
 *   OP_MEM       (i32 id)                             -> u32 total mem
 * Every op that takes a battle id reports the engine's fatal error (status 1, payload = message) if the
 * battle has one after the call.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

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

enum {
    OP_VERSION = 1, OP_SCRIPT, OP_INIT, OP_BOOTSTRAP, OP_BEGIN, OP_MESSAGE, OP_FORFEIT, OP_UPDATE,
    OP_CATCHUP, OP_SETVALUE, OP_SHUTDOWN, OP_ISV2, OP_MEM,
};

static uint8_t *g_script;
static size_t g_script_len;

static bool read_full(void *buf, size_t n) {
    uint8_t *p = buf;
    while (n) {
        ssize_t r = read(0, p, n);
        if (r <= 0) return false;
        p += r;
        n -= (size_t)r;
    }
    return true;
}

static void write_full(const void *buf, size_t n) {
    const uint8_t *p = buf;
    while (n) {
        ssize_t r = write(1, p, n);
        if (r <= 0) exit(2);
        p += r;
        n -= (size_t)r;
    }
}

static void reply(uint8_t status, const void *payload, size_t len) {
    uint32_t total = (uint32_t)len + 1;
    write_full(&total, 4);
    write_full(&status, 1);
    if (len) write_full(payload, len);
}

static bool fatal(int id) {
    if (!Battle_HadFatalError(id)) return false;
    const char *msg = Battle_GetLastFatalError(id);
    if (!msg) msg = "fatal error";
    reply(1, msg, strlen(msg));
    return true;
}

static int32_t rd_i32(const uint8_t *p) { int32_t v; memcpy(&v, p, 4); return v; }
static int64_t rd_i64(const uint8_t *p) { int64_t v; memcpy(&v, p, 8); return v; }
static float rd_f32(const uint8_t *p) { float v; memcpy(&v, p, 4); return v; }

/* Get*Buffer locks the battle's mutex until FinishedReadingBuffer: no other Battle_* call in between. */
static void reply_buffer(int id, uint8_t *(*get)(int, size_t *)) {
    if (fatal(id)) return;
    size_t len = 0;
    uint8_t *buf = get(id, &len);
    reply(0, buf, buf ? len : 0);
    Battle_FinishedReadingBuffer(id);
}

int main(int argc, char **argv) {
    int max = argc > 1 ? atoi(argv[1]) : 64;
    Battle_SetMaxInstances(max);
    size_t cap = 1 << 16;
    uint8_t *buf = malloc(cap);
    for (;;) {
        uint32_t len;
        if (!read_full(&len, 4)) return 0;
        if (len == 0) return 3;
        if (len > cap) { free(buf); cap = len; buf = malloc(cap); }
        if (!read_full(buf, len)) return 0;
        uint8_t op = buf[0];
        uint8_t *p = buf + 1;
        size_t n = len - 1;
        int id = n >= 4 ? rd_i32(p) : -1;
        switch (op) {
        case OP_VERSION: { int32_t v = Battle_GetVersion(); reply(0, &v, 4); break; }
        case OP_SCRIPT:
            free(g_script);
            g_script = malloc(n ? n : 1);
            memcpy(g_script, p, n);
            g_script_len = n;
            reply(0, NULL, 0);
            break;
        case OP_INIT: {
            int32_t out = -1;
            if (!Battle_Init(&out)) { reply(1, "init failed", 11); break; }
            reply(0, &out, 4);
            break;
        }
        case OP_BOOTSTRAP:
            Battle_Bootstrap(id, g_script, g_script_len, p + 5, n - 5, p[4] != 0);
            if (!fatal(id)) reply(0, NULL, 0);
            break;
        case OP_BEGIN:
            Battle_Begin(id);
            if (!fatal(id)) reply(0, NULL, 0);
            break;
        case OP_MESSAGE:
            Battle_HandlePlayerMessage(id, p[4], p + 5, 0, n - 5);
            if (!fatal(id)) reply(0, NULL, 0);
            break;
        case OP_FORFEIT:
            Battle_HandlePlayerForfeit(id, p[4]);
            if (!fatal(id)) reply(0, NULL, 0);
            break;
        case OP_UPDATE:
            Battle_UpdateWithFlags(id, rd_f32(p + 4), rd_f32(p + 8), rd_i32(p + 12), rd_i64(p + 16));
            reply_buffer(id, Battle_GetUpdateResultBuffer);
            break;
        case OP_CATCHUP:
            reply_buffer(id, Battle_GetCatchUpBuffer);
            break;
        case OP_SETVALUE:
            Battle_SetBattleValue(id, rd_i32(p + 4), rd_i64(p + 8));
            if (!fatal(id)) reply(0, NULL, 0);
            break;
        case OP_SHUTDOWN:
            Battle_Shutdown(id);
            reply(0, NULL, 0);
            break;
        case OP_ISV2: { uint8_t v = Battle_IsV2(id); reply(0, &v, 1); break; }
        case OP_MEM: { uint32_t v = Battle_GetTotalMem(id); reply(0, &v, 4); break; }
        default: reply(1, "bad op", 6);
        }
    }
}
