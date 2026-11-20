/* Script VM trace (ScriptVm_RunFrame, EU 0x02025b18).
 *
 * Every command handler the VM runs, and every wait (resume) that ends, goes through
 * kh_script_run / kh_script_resume: the command bytes, the handler and its result are kept
 * in a ring of the last 128 and written to the log for the first KH_SCRIPT_LOG_LINES. The
 * fault report prints the ring, so a crash shows the script commands that led to it
 * ("script:" lines; tools/symbolize.py names the handlers).
 * Results: 0 = wait (the resume runs every frame until it returns non-zero), 1 = next
 * command, 2 = same command again, 3 = stop this frame, 4 = return, 6 = next and stop. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <psp2/kernel/processmgr.h>
#include "log.h"

#define KH_SCRIPT_RING 128
#define KH_SCRIPT_LOG_LINES 6000

typedef int (*kh_script_fn)(void *vm, void *arg);

struct kh_script_event {
    uint32_t ms;
    uint32_t header;     /* group, index, field/length halfword (0 for a resume) */
    uintptr_t fn;
    int32_t result;
    uint8_t resume;
};

static struct kh_script_event s_ring[KH_SCRIPT_RING];
static unsigned s_next, s_logged;

static void record(kh_script_fn fn, const uint8_t *cmd, int result, int resume)
{
    struct kh_script_event *e = &s_ring[s_next++ % KH_SCRIPT_RING];
    e->ms = sceKernelGetProcessTimeLow() / 1000;
    e->header = cmd ? (uint32_t)cmd[0] | (uint32_t)cmd[1] << 8 | (uint32_t)(cmd[2] | cmd[3] << 8) << 16 : 0;
    e->fn = (uintptr_t)fn;
    e->result = result;
    e->resume = (uint8_t)resume;
    if (s_logged < KH_SCRIPT_LOG_LINES) {
        s_logged++;
        if (resume)
            LOG("script: wait done, resume handler %08x -> %d", (unsigned)e->fn, result);
        else
            LOG("script: cmd %02x:%02x len %u field %u handler %08x -> %d", cmd[0], cmd[1],
                (unsigned)((cmd[2] | cmd[3] << 8) & 0x7ff), (unsigned)((cmd[2] | cmd[3] << 8) >> 11),
                (unsigned)e->fn, result);
    }
}

int kh_script_run(kh_script_fn fn, void *vm, uint8_t *operands)
{
    int result = fn(vm, operands);
    record(fn, operands - 4, result, 0);
    return result;
}

int kh_script_resume(kh_script_fn fn, void *vm, intptr_t arg)
{
    int result = fn(vm, (void *)arg);
    if (result != 0)
        record(fn, NULL, result, 1);
    return result;
}

void kh_script_trace_dump(void)
{
    char buf[160];
    unsigned i, start = s_next > KH_SCRIPT_RING ? s_next - KH_SCRIPT_RING : 0;
    for (i = start; i < s_next; i++) {
        const struct kh_script_event *e = &s_ring[i % KH_SCRIPT_RING];
        int n = e->resume
            ? snprintf(buf, sizeof(buf), "  script %6ums resume handler %08x -> %d\n",
                       (unsigned)e->ms, (unsigned)e->fn, (int)e->result)
            : snprintf(buf, sizeof(buf), "  script %6ums cmd %02x:%02x hw %04x handler %08x -> %d\n",
                       (unsigned)e->ms, (unsigned)(e->header & 0xff), (unsigned)(e->header >> 8 & 0xff),
                       (unsigned)(e->header >> 16), (unsigned)e->fn, (int)e->result);
        log_write_raw(buf, n);
    }
}

/* A DS store through a NULL object pointer (it lands in the ITCM mirror there): skipped,
 * logged once per routine and index. */
void kh_ds_null_store(const char *what, int index)
{
    static uintptr_t s_seen[32];
    uintptr_t key = (uintptr_t)what ^ ((uintptr_t)index << 24);
    unsigned i;
    for (i = 0; i < 32 && s_seen[i] && s_seen[i] != key; i++)
        ;
    if (i < 32 && !s_seen[i]) {
        s_seen[i] = key;
        LOG("ds: %s(%d): NULL object, the DS store to the ITCM mirror is skipped", what, index);
    }
}

void kh_trace_stage_event(const char *action, int event, int detail, int state)
{
    LOG("stage: %s event=%d detail=%d state=%d", action, event, detail, state);
}

/* A stage can retry spawning on every frame. Log changes per record only. */
void kh_trace_stage_spawn(unsigned record, const char *reason, int state, int value)
{
    static const char *last_reason[256];

    if (record >= sizeof(last_reason) / sizeof(last_reason[0]) || last_reason[record] == reason) return;
    last_reason[record] = reason;
    LOG("stage: spawn record=%u result=%s state=%d value=%d", record, reason, state, value);
}

void kh_trace_field_resume(int stage, int entry, int before, int after)
{
    LOG("save: field stage=%d entry=%d resume=%d after setup=%d", stage, entry, before, after);
}

/* Player actor trace (ov052): state changes, animation picks, weapon sub-models and
 * display mode, so a log shows what the game asks for when Sora rolls or sheathes the
 * Keyblade. Repeats of the same event in a row are counted, not logged. */
void kh_actor_trace(const char *what, unsigned int entity, int a, int b)
{
    static const char *s_what;
    static unsigned int s_entity;
    static int s_a, s_b, s_logged;
    static unsigned s_repeat;
    if (what == s_what && entity == s_entity && a == s_a && b == s_b) {
        s_repeat++;
        return;
    }
    if (s_logged >= 8000)
        return;
    s_logged++;
    if (s_repeat)
        LOG("actor: (x%u)", s_repeat);
    s_what = what, s_entity = entity, s_a = a, s_b = b, s_repeat = 0;
    LOG("actor: %s %08x %d %d", what, (unsigned)entity, a, b);
}

/* Motion file loads (ov021 AcquireSharedRecordState) and body animation picks
 * (ov052 SetBlendTableAndBlendTrack): the counts are the five u16 track counts at the start
 * of a blend table (0 = the track has no animation and the pick is ignored). */
void kh_motion_trace(const char *what, const void *obj, const char *name, int a, const void *table)
{
    static int s_logged;
    const unsigned short *c = (const unsigned short *)table;
    (void)name; /* the key is not always a string: a file id in some callers (0.0.23) */
    if (s_logged >= 4000)
        return;
    s_logged++;
    if (what[0] == 'l' && what[4] == 0) /* "load": a = initialized, table = the key */
        LOG("motion: load %08x key %08x initialized %d", (unsigned)(uintptr_t)obj,
            (unsigned)(uintptr_t)table, a);
    else if (c)
        LOG("motion: %s %08x %d counts %u %u %u %u %u", what, (unsigned)(uintptr_t)obj,
            a, c[0], c[1], c[2], c[3], c[4]);
    else
        LOG("motion: %s %08x %d table NULL", what, (unsigned)(uintptr_t)obj, a);
}
