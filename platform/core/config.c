#include "config.h"

#include "log.h"
#include "paths.h"

#include <psp2/ctrl.h>
#include <stdio.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define CONFIG_VERSION 17

static const KhConfig s_defaults = {
    .render_scale = 3, .layout = 0, .inset_width = 224, .aspect = KH_ASPECT_4_3,
    .frame_interpolation = 0, .dynamic_res = 1, .partner_swap = 0, .swap_roxas_items = 0, .swap_roxas_magic = 0, .texture_filter = 1, .filter_2d = 2, .hud = 0, .screen_effect = 0,
    .inset_corner = 0, .inset_opacity = 100, .rear_touch = 0, .stick_deadzone = 2, .r_toggle = 0,
    .fast_forward = 2, .camera_stick = 1, .camera_speed = 2,
    .camera_invert_x = 0, .camera_invert_y = 0, .camera_follow = 0, .dpad_deck = 1, .show_fps = 0, .volume = 100,
    .button_icons = 0, .confirm_cross = 1, .single_screen = 0, .panel_opacity = 90, .language = 1, .hud_size = 100,
    /* the mission screen's bottom-screen parts (sx sy sw sh anchor dx dy scale), measured on
     * the DS's bottom screen in a mission: the INFORMATION bar top-left, the map in the
     * top-right corner with the target beside it (below the top screen's enemy name and HP),
     * the objective and mission gauge along the bottom between the commands and the HP */
    .panel = { /* top centre, clear of the chain counter, the bar's whole width (a long
                * message ran past 180 pixels); the game shows a new message on the top screen
                * itself, so this one only comes with the pause menu */
               { 2, 6, 252, 24, KH_PANEL_TOP_CENTER, 0, 4, 170, KH_STYLE_PLAIN, 10,
                 KH_SHOW_ON_PAUSE },
               { 102, 54, 120, 86, KH_PANEL_TOP_RIGHT, 6, 60, 130, KH_STYLE_INVERT_GREYS, 6,
                 KH_SHOW_ALWAYS },
               /* only with a target (its red tab); shorter than the map */
               { 33, 53, 64, 87, KH_PANEL_TOP_RIGHT, 166, 60, 100, KH_STYLE_WHITE_TO_BLACK, 6,
                 KH_SHOW_ON_RED },
               /* between the commands and the HP gauge of the stretched HUD; shown when the
                * gauge moves */
               { 7, 149, 241, 43, KH_PANEL_BOTTOM_CENTER, 0, 0, 120, KH_STYLE_PLAIN, 10,
                 KH_SHOW_ON_CHANGE } },
    .debug = 0,
    /* positional, as on the DS: the right face button is A, the bottom one B */
    .button = { SCE_CTRL_CIRCLE, SCE_CTRL_CROSS, SCE_CTRL_TRIANGLE, SCE_CTRL_SQUARE,
                SCE_CTRL_LTRIGGER, SCE_CTRL_RTRIGGER, SCE_CTRL_START, SCE_CTRL_SELECT },
};

KhConfig kh_config;

static const struct {
    const char *name;
    uint32_t mask;
} s_vita_buttons[KH_VITA_BUTTONS] = {
    { "cross", SCE_CTRL_CROSS }, { "circle", SCE_CTRL_CIRCLE }, { "square", SCE_CTRL_SQUARE },
    { "triangle", SCE_CTRL_TRIANGLE }, { "l", SCE_CTRL_LTRIGGER }, { "r", SCE_CTRL_RTRIGGER },
    { "start", SCE_CTRL_START }, { "select", SCE_CTRL_SELECT },
};
static const char *const s_ds_buttons[KH_BTN_COUNT] = { "button_a", "button_b", "button_x",
    "button_y", "button_l", "button_r", "button_start", "button_select" };

const char *config_vita_button_name(int i) { return s_vita_buttons[i].name; }
uint32_t config_vita_button_mask(int i) { return s_vita_buttons[i].mask; }

int config_vita_button_index(uint32_t mask)
{
    int i;
    for (i = 0; i < KH_VITA_BUTTONS; i++)
        if (s_vita_buttons[i].mask == mask)
            return i;
    return 0;
}

void config_defaults(void)
{
    const int debug = kh_config.debug; /* a diagnostic switch, not a preference */
    kh_config = s_defaults;
    kh_config.debug = debug;
}

static int clampi(int v, int lo, int hi)
{
    return v < lo ? lo : v > hi ? hi : v;
}

/* Re:coded whitelist: unavailable Days hooks cannot be enabled from config.ini. */
static const struct { const char *key; size_t offset; int lo, hi; } settings[] = {
#define SET(k, lo, hi) { #k, offsetof(KhConfig, k), lo, hi }
    SET(render_scale,1,4), SET(layout,0,4), SET(inset_width,128,480),
    SET(aspect,0,2), SET(frame_interpolation,0,1), SET(dynamic_res,0,1),
    SET(texture_filter,0,1), SET(filter_2d,0,2), SET(screen_effect,0,2),
    SET(inset_corner,0,3), SET(inset_opacity,50,100), SET(rear_touch,0,2),
    SET(stick_deadzone,1,3),  SET(fast_forward,2,3),
    SET(confirm_cross,0,1), SET(show_fps,0,1), SET(volume,0,100),
    SET(language,1,5), SET(debug,0,1),
#undef SET
};
void config_save(void)
{
    FILE *f = fopen(KH_CONFIG_PATH, "w");
    if (!f) return;
    fprintf(f, "# khrecoded-vita: two DS screens; L+R+Select opens settings.\n");
    for (unsigned i=0; i<sizeof(settings)/sizeof(settings[0]); ++i)
        fprintf(f, "%s = %d\n", settings[i].key,
                *(int *)((char *)&kh_config + settings[i].offset));
    for (int i=0; i<KH_BTN_COUNT; ++i)
        fprintf(f, "%s = %s\n", s_ds_buttons[i],
                s_vita_buttons[config_vita_button_index(kh_config.button[i])].name);
    fclose(f);
}
void config_load(void)
{
    kh_config = s_defaults;
    FILE *f = fopen(KH_CONFIG_PATH, "r");
    if (!f) { config_save(); return; }
    char line[256], key[64], val[64];
    while (fgets(line,sizeof(line),f)) {
        if (sscanf(line," %63[a-zA-Z0-9_] = %63s",key,val)!=2) continue;
        for (unsigned i=0; i<sizeof(settings)/sizeof(settings[0]); ++i) {
            if (strcmp(key,settings[i].key)) continue;
            char *end; long v=strtol(val,&end,10);
            if (*end || v < settings[i].lo || v > settings[i].hi) continue;
            *(int *)((char *)&kh_config+settings[i].offset)=(int)v;
        }
        for (int i=0;i<KH_BTN_COUNT;++i)
            if (!strcmp(key,s_ds_buttons[i]))
                for (int j=0;j<KH_VITA_BUTTONS;++j)
                    if (!strcmp(val,s_vita_buttons[j].name)) kh_config.button[i]=s_vita_buttons[j].mask;
    }
    fclose(f);
    kh_log_verbose=kh_config.debug;
}
int kh_vita_mission_balance(void) { return 0; }
int kh_vita_mission_hp_tenths(void) { return 30; }
