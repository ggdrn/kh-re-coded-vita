#include <math.h>

#include "hw/camera_interp.h"

typedef struct {
    uint32_t key;
    int start, count;
} VertexRun;

typedef struct {
    int previous;
    float distance;
    int same_uv;
} RunMatch;

/* As in the Days renderer, search near the original draw order and use distance to
 * disambiguate repeated materials. BEGIN boundaries keep independent draws apart. */
#define RUN_WINDOW 48

static int collect_runs(const KhGxVertex *vertices, int count, VertexRun *runs)
{
    int n = 0;
    for (int i = 0; i < count;) {
        const uint32_t tag = vertices[i].tag;
        const uint32_t key = tag & ~KH_GX_VERTEX_RUN_START;
        const int start = i++;
        while (i < count && vertices[i].tag == key)
            i++;
        if (key & KH_GX_VERTEX_CAMERA)
            runs[n++] = (VertexRun){ key, start, i - start };
    }
    return n;
}

static float clip_distance(const KhGxVertex *a, const KhGxVertex *b)
{
    /* Avoid dividing by w itself: near-plane vertices can project off to infinity. */
    const float depth = fmaxf(4096.0f, fmaxf(fabsf(a->w), fabsf(b->w)));
    return (fabsf(a->x - b->x) + fabsf(a->y - b->y) +
            0.5f * (fabsf(a->z - b->z) + fabsf(a->w - b->w))) / depth;
}

static int prefer(RunMatch candidate, RunMatch current)
{
    return current.previous < 0 || candidate.same_uv > current.same_uv ||
           (candidate.same_uv == current.same_uv && candidate.distance < current.distance);
}

static int safe_run(const KhGxVertex *a, const KhGxVertex *b, int count, int particle)
{
    const float limit = particle ? 0.18f : 0.65f;
    for (int k = 0; k < count; k++) {
        if ((particle && (a[k].w <= 0.0f || b[k].w <= 0.0f)) ||
            clip_distance(&a[k], &b[k]) > limit)
            return 0;
    }
    return 1;
}

unsigned kh_motion_midpoint(const KhGxVertex *a, int count_a, KhGxVertex *b, int count_b)
{
    /* Only the display thread calls this. Reserve enough for the worst case of one run
     * per vertex and keep the scratch data off the Vita's display thread stack. */
    static VertexRun runs_a[KH_GX_MAX_VERTICES], runs_b[KH_GX_MAX_VERTICES];
    static RunMatch matches[KH_GX_MAX_VERTICES];
    static int owner[KH_GX_MAX_VERTICES];
    const int na = collect_runs(a, count_a, runs_a);
    const int nb = collect_runs(b, count_b, runs_b);
    int cursor = 0;
    unsigned moved = 0;

    for (int i = 0; i < na; i++)
        owner[i] = -1;
    for (int j = 0; j < nb; j++) {
        const VertexRun run = runs_b[j];
        const KhGxVertex *bv = &b[run.start];
        const int samples[] = { 0, run.count / 2, run.count - 1 };
        const int lo = cursor > RUN_WINDOW ? cursor - RUN_WINDOW : 0;
        const int hi = cursor + RUN_WINDOW < na ? cursor + RUN_WINDOW : na;
        const int particle = run.count <= 8 && bv->a > 0 && bv->a < 31;
        RunMatch best = { .previous = -1 };
        for (int k = lo; k < hi; k++) {
            if (runs_a[k].key != run.key || runs_a[k].count != run.count)
                continue;
            const KhGxVertex *av = &a[runs_a[k].start];
            RunMatch match = { .previous = k, .same_uv = 1 };
            for (int i = 0; i < 3; i++) {
                const int index = samples[i];
                match.same_uv &= av[index].s == bv[index].s && av[index].t == bv[index].t;
                match.distance += clip_distance(&av[index], &bv[index]);
            }
            match.distance /= 3.0f;
            const float limit = particle ? 0.12f : match.same_uv ? 0.42f : 0.08f;
            if (match.distance > limit || (particle && !match.same_uv))
                continue;
            if (prefer(match, best) ||
                (match.same_uv == best.same_uv && match.distance == best.distance && k == cursor))
                best = match;
            if (k == cursor && match.same_uv && match.distance == 0.0f)
                break;
        }
        matches[j] = best;
        if (best.previous >= 0) {
            const int previous_owner = owner[best.previous];
            if (previous_owner < 0 || prefer(best, matches[previous_owner]))
                owner[best.previous] = j;
            cursor = best.previous + 1;
        }
    }

    for (int j = 0; j < nb; j++) {
        const int i = matches[j].previous;
        if (i < 0 || owner[i] != j)
            continue;
        const VertexRun run = runs_b[j];
        const KhGxVertex *av = a + runs_a[i].start;
        KhGxVertex *bv = b + run.start;
        const int particle = run.count <= 8 && bv->a > 0 && bv->a < 31;
        if (!safe_run(av, bv, run.count, particle))
            continue;
        for (int k = 0; k < run.count; k++) {
            if (av[k].x == bv[k].x && av[k].y == bv[k].y &&
                av[k].z == bv[k].z && av[k].w == bv[k].w)
                continue;
            bv[k].x = 0.5f * (av[k].x + bv[k].x);
            bv[k].y = 0.5f * (av[k].y + bv[k].y);
            bv[k].z = 0.5f * (av[k].z + bv[k].z);
            bv[k].w = 0.5f * (av[k].w + bv[k].w);
            /* The new material stays intact, including wrapped or scrolled UVs. */
            moved++;
        }
    }
    return moved;
}
