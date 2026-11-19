/* Host test for the divider and square-root unit (CP): the registers behind KH_HW
 * (platform/hw/memmap.c), the context switch (platform/nitro/cp.c) and the decomp's own FX
 * routines that drive them (FX_Div, FX_Inv, FX_DivFx64c, FX_InvFx64c, FX_Sqrt and the async /
 * result halves), checked against a reference written from GBATEK's description of the
 * hardware, not from the port's code.
 *
 *     tools/cp_register_test/run.sh */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "kh_hw_map.h"

unsigned char kh_ds_io[0x2000] __attribute__((aligned(32)));
unsigned char kh_ds_dtcm[0x4000], kh_ds_shared_area[0x1000];
volatile int kh_probe_armed;
void kh_probe_hit(const char *where) { (void)where; }
void kh_cpu_poll(void) {}
void kh_timers_update(void) {}
void kh_gx3d_sync_gxstat(void) {}
uint64_t sceKernelGetProcessTimeWide(void) { return 0; }

/* the decomp's FX routines (EU names), compiled from build/decomp with the port's rewrites */
int FX_Div(int numer, int denom);
int FX_Inv(int x);
long long FX_DivFx64c(int numer, int denom);
long long FX_InvFx64c(int x);
int FX_Sqrt(int x);
void FX_DivAsync(int numer, int denom);
void FX_InvAsync(int x);
int FX_GetDivResult(void);
long long FX_GetDivResultFx64c(void);
void CP_SaveContext(void *ctx);
void CPi_RestoreContext(const void *ctx);

static int s_failures, s_checks;

#define CHECK(cond, ...)                                                                   \
    do {                                                                                   \
        s_checks++;                                                                        \
        if (!(cond) && s_failures++ < 20) {                                                \
            printf("FAIL %s:%d: ", __FILE__, __LINE__);                                    \
            printf(__VA_ARGS__);                                                           \
            printf("\n");                                                                  \
        }                                                                                  \
    } while (0)

#define R16(a) (*(volatile uint16_t *)KH_HW(a))
#define R32(a) (*(volatile uint32_t *)KH_HW(a))
#define R64(a) (*(volatile int64_t *)KH_HW(a))

/* ---- GBATEK reference ------------------------------------------------------------------
 * DIVCNT 0: 32/32, 1: 64/32, 2: 64/64, 3: as 1. Division by zero: quotient -1 for a
 * numerator >= 0, +1 for a negative one, and in 32-bit mode the upper word of that result
 * inverted; remainder = numerator. -MAX/-1 overflows to the positive value the width cannot
 * hold (32-bit: 0x0000000080000000; 64-bit: 0x8000000000000000). Bit 14: the full 64-bit
 * DIV_DENOM is zero. SQRTCNT 0: 32-bit, 1: 64-bit; result floor(sqrt). */
static void div_ref(int mode, int64_t n64, int64_t d64, int64_t *q, int64_t *r)
{
    if (mode == 0) {
        int32_t n = (int32_t)n64, d = (int32_t)d64;
        if (d == 0) {
            *q = n >= 0 ? -1 : 1;
            *q ^= (int64_t)0xffffffff00000000ull;
            *r = n;
        } else if (n == INT32_MIN && d == -1) {
            *q = 0x80000000ll;
            *r = 0;
        } else {
            *q = n / d;
            *r = n % d;
        }
        return;
    }
    {
        int64_t d = mode == 2 ? d64 : (int32_t)d64;
        if (d == 0) {
            *q = n64 >= 0 ? -1 : 1;
            *r = n64;
        } else if (n64 == INT64_MIN && d == -1) {
            *q = INT64_MIN;
            *r = 0;
        } else {
            *q = n64 / d;
            *r = n64 % d;
        }
    }
}

static uint32_t sqrt_ref(uint64_t v)
{
    uint64_t lo = 0, hi = 0xffffffffull;
    while (lo < hi) {               /* largest r with r*r <= v, by bisection */
        uint64_t mid = lo + (hi - lo + 1) / 2;
        if ((unsigned __int128)mid * mid <= v)
            lo = mid;
        else
            hi = mid - 1;
    }
    return (uint32_t)lo;
}

static uint64_t s_rng = 0x9e3779b97f4a7c15ull;
static uint64_t rnd(void)
{
    s_rng ^= s_rng << 13;
    s_rng ^= s_rng >> 7;
    s_rng ^= s_rng << 17;
    return s_rng;
}
static int64_t interesting(void)
{
    static const int64_t edge[] = { 0, 1, -1, 2, -2, 0x1000, -0x1000, INT32_MAX, INT32_MIN,
                                    (int64_t)INT32_MAX + 1, (int64_t)INT32_MIN - 1, INT64_MAX,
                                    INT64_MIN, 0x100000000ll, -0x100000000ll,
                                    (int64_t)0xffffffff00000000ull };
    switch (rnd() % 4) {
    case 0: return edge[rnd() % (sizeof edge / sizeof edge[0])];
    case 1: return (int32_t)rnd();
    case 2: return (int16_t)rnd();
    default: return (int64_t)rnd();
    }
}

static void program(int mode, int64_t n, int64_t d)
{
    R16(0x04000280) = (uint16_t)mode;
    R64(0x04000290) = n;
    R64(0x04000298) = d;
}

static void test_divider(void)
{
    int i;
    for (i = 0; i < 400000; i++) {
        const int mode = (int)(rnd() % 4);
        const int64_t n = interesting(), d = interesting();
        int64_t q, r;
        program(mode, n, d);
        div_ref(mode, n, d, &q, &r);
        CHECK(R64(0x040002a0) == q, "mode %d %lld/%lld: quotient %llx, expected %llx", mode,
              (long long)n, (long long)d, (unsigned long long)R64(0x040002a0), (unsigned long long)q);
        CHECK(R64(0x040002a8) == r, "mode %d %lld/%lld: remainder %llx, expected %llx", mode,
              (long long)n, (long long)d, (unsigned long long)R64(0x040002a8), (unsigned long long)r);
        /* the flag, read straight after the parameters (DIVCNT, before any result) */
        program(mode, n, d);
        CHECK(((R16(0x04000280) >> 14) & 1) == (d == 0), "mode %d denom %llx: DIV0 flag %d", mode,
              (unsigned long long)d, (R16(0x04000280) >> 14) & 1);
        CHECK((R16(0x04000280) & 3) == mode, "mode %d kept", mode);
    }
    /* GBATEK's cases, spelled out */
    program(0, 7, 0);
    CHECK(R64(0x040002a0) == 0x00000000ffffffffll && R64(0x040002a8) == 7, "32-bit 7/0");
    program(0, -7, 0);
    CHECK(R64(0x040002a0) == (int64_t)0xffffffff00000001ull && R64(0x040002a8) == -7, "32-bit -7/0");
    program(0, 5, (int64_t)0x100000000ll);  /* low word zero, high not: divides by 0, no flag */
    CHECK(R64(0x040002a0) == 0x00000000ffffffffll && !(R16(0x04000280) & 0x4000), "32-bit 5/(1<<32)");
    program(0, INT32_MIN, -1);
    CHECK(R64(0x040002a0) == 0x80000000ll && R64(0x040002a8) == 0, "32-bit MIN/-1");
    program(1, INT64_MIN, -1);
    CHECK(R64(0x040002a0) == INT64_MIN && R64(0x040002a8) == 0, "64/32 MIN/-1");
    program(2, -9, 0);
    CHECK(R64(0x040002a0) == 1 && R64(0x040002a8) == -9 && (R16(0x04000280) & 0x4000), "64/64 -9/0");
    program(3, (int64_t)100 << 32, 3);
    CHECK(R64(0x040002a0) == ((int64_t)100 << 32) / 3, "mode 3 as mode 1");
}

static void test_sqrt(void)
{
    int i;
    for (i = 0; i < 200000; i++) {
        const int mode = (int)(rnd() & 1);
        uint64_t v = (uint64_t)interesting();
        R16(0x040002b0) = (uint16_t)mode;
        *(volatile uint64_t *)KH_HW(0x040002b8) = v;
        if (!mode)
            v = (uint32_t)v;
        CHECK(R32(0x040002b4) == sqrt_ref(v), "sqrt mode %d of %llx: %x, expected %x", mode,
              (unsigned long long)v, R32(0x040002b4), sqrt_ref(v));
        CHECK(!(R16(0x040002b0) & 0x8000) && (R16(0x040002b0) & 1) == mode, "SQRTCNT after %d", mode);
    }
    R16(0x040002b0) = 1;
    *(volatile uint64_t *)KH_HW(0x040002b8) = UINT64_MAX;
    CHECK(R32(0x040002b4) == 0xffffffffu, "sqrt of 2^64-1");
}

/* NitroSDK: FX_Div = (a << 32) / b in 64/32 mode, rounded to fx32 ((q + 2^19) >> 20);
 * FX_Inv = FX_Div(1.0, x); the Fx64c forms return the raw 64-bit quotient; FX_Sqrt: 64-bit
 * square root of (x << 32), rounded ((r + 0x200) >> 10), 0 for x <= 0. */
static int fx_div_ref(int a, int b)
{
    int64_t q, r;
    div_ref(1, (int64_t)a << 32, b, &q, &r);
    return (int)(((uint64_t)q + 0x80000) >> 20);
}

static void test_fx(void)
{
    int i;
    CHECK(FX_Div(3 << 12, 2 << 12) == 0x1800, "FX_Div(3, 2) = %x", FX_Div(3 << 12, 2 << 12));
    CHECK(FX_Div(-1 << 12, 4 << 12) == -0x400, "FX_Div(-1, 4) = %x", FX_Div(-1 << 12, 4 << 12));
    CHECK(FX_Inv(2 << 12) == 0x800, "FX_Inv(2) = %x", FX_Inv(2 << 12));
    CHECK(FX_Sqrt(4 << 12) == 2 << 12, "FX_Sqrt(4) = %x", FX_Sqrt(4 << 12));
    CHECK(FX_Sqrt(1 << 12) == 1 << 12, "FX_Sqrt(1) = %x", FX_Sqrt(1 << 12));
    CHECK(FX_Sqrt(0) == 0 && FX_Sqrt(-5) == 0, "FX_Sqrt of 0 and negatives");
    for (i = 0; i < 100000; i++) {
        const int a = (int32_t)rnd() >> (rnd() % 20), b = (int32_t)rnd() >> (rnd() % 20);
        int64_t q, r;
        CHECK(FX_Div(a, b) == fx_div_ref(a, b), "FX_Div(%x, %x) = %x, expected %x", a, b,
              FX_Div(a, b), fx_div_ref(a, b));
        CHECK(FX_Inv(b) == fx_div_ref(0x1000, b), "FX_Inv(%x)", b);
        div_ref(1, (int64_t)a << 32, b, &q, &r);
        CHECK(FX_DivFx64c(a, b) == q, "FX_DivFx64c(%x, %x)", a, b);
        div_ref(1, (int64_t)0x1000 << 32, b, &q, &r);
        CHECK(FX_InvFx64c(b) == q, "FX_InvFx64c(%x)", b);
        if (a > 0)
            CHECK(FX_Sqrt(a) == (int)(((uint64_t)sqrt_ref((uint64_t)a << 32) + 0x200) >> 10),
                  "FX_Sqrt(%x)", a);
        FX_DivAsync(a, b);
        CHECK(FX_GetDivResult() == fx_div_ref(a, b), "FX_DivAsync + FX_GetDivResult(%x, %x)", a, b);
        div_ref(1, (int64_t)a << 32, b, &q, &r);
        FX_DivAsync(a, b);
        CHECK(FX_GetDivResultFx64c() == q, "FX_DivAsync + FX_GetDivResultFx64c(%x, %x)", a, b);
    }
}

/* a thread switch in the middle of a division and a square root */
static void test_context(void)
{
    uint8_t ctx[28];
    int64_t q, r;
    program(2, 1000000007ll << 20, 12345);
    R16(0x040002b0) = 0;
    *(volatile uint64_t *)KH_HW(0x040002b8) = 99980001;      /* 9999^2 */
    CP_SaveContext(ctx);
    program(0, 5, 0);                                        /* the other thread divides by 0 */
    R16(0x040002b0) = 1;
    *(volatile uint64_t *)KH_HW(0x040002b8) = 4;
    CHECK(R16(0x04000280) & 0x4000, "the other thread's DIV0");
    CPi_RestoreContext(ctx);
    div_ref(2, 1000000007ll << 20, 12345, &q, &r);
    CHECK(R64(0x040002a0) == q && R64(0x040002a8) == r, "division after restore");
    CHECK(!(R16(0x04000280) & 0x4000) && (R16(0x04000280) & 3) == 2, "DIVCNT after restore %x",
          R16(0x04000280));
    CHECK(R32(0x040002b4) == 9999 && (R16(0x040002b0) & 1) == 0, "square root after restore");
    /* the flag is current right after the restore, with no result read in between */
    program(1, 3, 0);
    CP_SaveContext(ctx);
    program(1, 3, 1);
    CPi_RestoreContext(ctx);
    CHECK(kh_ds_io[0x281] & 0x40, "DIV0 restored without a read");
}

int main(void)
{
    test_divider();
    test_sqrt();
    test_fx();
    test_context();
    printf("cp_register_test: %d checks, %d failures\n", s_checks, s_failures);
    return s_failures != 0;
}
