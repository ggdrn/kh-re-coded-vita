#ifndef KH_START_LAYOUT_H
#define KH_START_LAYOUT_H

#include "core/video.h"

typedef struct {
    int screen;
    ScreenRect source;
    ScreenRect display;
} StartRegion;

enum { START_HEADER, START_OPTIONS, START_MODEL, START_TABS, START_STATUS_HEADER, START_STATUS, START_HELP, START_TOTALS, START_CONTROLS };

/* Source rectangles in the native menu's 256×192 screens. Destination coordinates
 * use the Vita's 960×544 display. Preserve each widget as a separate region. */
static const StartRegion start_regions[] = {
    [START_HEADER]   = { 0, { 0,   0, 256,  20 }, {  12,  12, 936,  40 } },
    [START_OPTIONS]  = { 0, { 6,  24, 114, 114 }, {  12,  76, 264, 294 } },
    [START_MODEL]    = { 0, { 120, 22, 132, 130 }, { 288,  91, 252, 248 } },
    [START_TABS]     = { 1, { 154, 0,  96,  21 }, { 552,  76, 396,  49 } },
    [START_STATUS_HEADER] = { 1, { 0, 0, 105, 21 }, { 552, 133, 206,  38 } },
    [START_STATUS]   = { 1, { 0,  21, 256, 123 }, { 552, 171, 396, 199 } },
    [START_HELP]     = { 0, { 0, 163, 256,  29 }, {  12, 410, 624,  56 } },
    [START_TOTALS]   = { 1, { 0, 146,  84,  44 }, { 762, 400, 186,  88 } },
    [START_CONTROLS] = { 1, { 86,146, 170,  44 }, {  12, 466, 302,  71 } },
};

/* Keep the Matrix editors' authored surfaces and touch grids intact during
 * their initial migration. The two panes use the same fit on every page. */
static const StartRegion matrix_regions[] = {
    { 0, { 0, 0, DS_SCREEN_W, DS_SCREEN_H }, {  12, 101, 460, 345 } },
    { 1, { 0, 0, DS_SCREEN_W, DS_SCREEN_H }, { 488, 101, 460, 345 } },
};

static inline int start_region_contains(const StartRegion *region, int px, int py)
{
    const ScreenRect *r = &region->display;
    return px >= r->x && px < r->x + r->w && py >= r->y && py < r->y + r->h;
}

static inline void start_region_touch(const StartRegion *region, int px, int py, int *x, int *y)
{
    const ScreenRect *r = &region->display;
    const ScreenRect *s = &region->source;
    const int u = px < r->x ? 0 : px >= r->x + r->w ? r->w - 1 : px - r->x;
    const int v = py < r->y ? 0 : py >= r->y + r->h ? r->h - 1 : py - r->y;
    *x = s->x + u * s->w / r->w;
    *y = s->y + v * s->h / r->h;
}

#endif
