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
    [START_TOTALS]   = { 1, { 4, 146,  72,  44 }, { 780, 400, 160,  70 } },
    [START_CONTROLS] = { 1, { 86,146, 170,  44 }, {  12, 466, 302,  71 } },
};

/* Keep the Matrix editors' authored surfaces and touch grids intact during
 * their initial migration. The two panes use the same fit on every page. */
static const StartRegion matrix_regions[] = {
    { 0, { 0, 0, DS_SCREEN_W, DS_SCREEN_H }, {  12, 101, 460, 345 } },
    { 1, { 0, 0, DS_SCREEN_W, DS_SCREEN_H }, { 488, 101, 460, 345 } },
};

/* The menu content on engine A keeps its native layers and touch coordinates
 * in a wider viewport. The nominal screen indices assume engine A is below B. */
static const StartRegion wide_menu_content = {
    1, { 0, 0, DS_SCREEN_W, DS_SCREEN_H }, { 20, 56, 640, 418 },
};
static const StartRegion wide_matrix_content = {
    1, { 0, 0, DS_SCREEN_W, DS_SCREEN_H }, { 12, 56, 652, 410 },
};
/* Other ov073 pages have their own lists and use the complete surface. */
static const StartRegion full_menu_status = {
    0, { 0, 0, DS_SCREEN_W, DS_SCREEN_H }, { 684, 32, 256, 192 },
};

/* Widgets from the ov073 Stats page. The footer stays live and can contain
 * the selected chip description, Munny and time, or menu-specific controls. */
enum { STATUS_HEADING, STATUS_PORTRAIT, STATUS_FOOTER };
static const StartRegion status_widgets[] = {
    [STATUS_HEADING]  = { 0, {  0,   0, 256, 22 }, { 684,  32, 256,  22 } },
    [STATUS_PORTRAIT] = { 0, { 16,  24,  80, 80 }, { 762,  65, 100, 100 } },
    [STATUS_FOOTER]   = { 0, {  0, 145, 256, 47 }, { 684, 428, 256,  47 } },
};

/* ov073 draws the command list and its scrollbar together. The Overclocks
 * page needs the full row width for the rightmost trees and their links. */
static const StartRegion matrix_status_body[] = {
    [VIDEO_STATUS_COMMANDS]   = { 0, { 24, 20, 224, 125 }, { 686, 76, 252, 180 } },
    [VIDEO_STATUS_OVERCLOCKS] = { 0, {  0, 20, 256, 125 }, { 684, 76, 256, 180 } },
};
static const StartRegion matrix_status_footer = {
    0, { 0, 145, 256, 47 }, { 684, 280, 256, 47 },
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
