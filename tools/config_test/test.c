#include "config.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <psp2/ctrl.h>
int kh_log_verbose;
void log_printf(const char *fmt, ...) { (void)fmt; }
FILE *config_test_open(const char *path, const char *mode)
{
    (void)path;
    return fopen("build/config_test.ini", mode);
}
int main(void)
{
    FILE *f=fopen("build/config_test.ini","w");
    assert(f);
    fputs("single_screen = 2\nhud_size = 87\npartner_swap = 1\nmission_balance = 1\n"
          "camera_stick = 0\ndpad_deck = 0\nr_toggle = 0\n"
          "render_scale = 4\nlayout = 4\ntexture_filter = 0\n"
          "filter_2d = 1\nvolume = 80\ninset_width = 99999999999999999999\n",f);
    fclose(f);
    config_load();
    assert(!kh_config.single_screen && !kh_config.partner_swap && !kh_config.mission_balance);
    assert(!kh_config.fullscreen_3d && kh_config.hud_size == 80);
    assert(kh_config.one_screen_map_size == 80 && kh_config.one_screen_tree_size == 80);
    assert(kh_config.camera_stick && kh_config.dpad_deck && kh_config.button_icons);
    assert(kh_config.vita_lock_on == 1);
    assert(kh_config.render_scale==4 && kh_config.layout==4 && !kh_config.texture_filter);
    assert(kh_config.filter_2d==1 && kh_config.volume==80 && kh_config.inset_width==224);
    kh_config.button[KH_BTN_A]=SCE_CTRL_SQUARE;
    kh_config.vita_lock_on=0;
    kh_config.button_icons=0;
    kh_config.single_screen = 1;
    kh_config.fullscreen_3d = 1;
    kh_config.hud_size = 60;
    kh_config.one_screen_map_size = 90;
    kh_config.one_screen_tree_size = 80;
    config_save();
    config_defaults();
    assert(kh_config.vita_lock_on == 1 && kh_config.button_icons == 1);
    assert(!kh_config.single_screen && !kh_config.fullscreen_3d && kh_config.hud_size == 100);
    assert(kh_config.one_screen_map_size == 100 && kh_config.one_screen_tree_size == 100);
    config_load();
    assert(kh_config.render_scale==4 && kh_config.layout==4 && kh_config.volume==80);
    assert(kh_config.button[KH_BTN_A]==SCE_CTRL_SQUARE);
    assert(kh_config.vita_lock_on == 0 && kh_config.button_icons == 0);
    assert(kh_config.single_screen == 1 && kh_config.fullscreen_3d == 1 && kh_config.hud_size == 60);
    assert(kh_config.one_screen_map_size == 90 && kh_config.one_screen_tree_size == 80);
    f=fopen("build/config_test.ini","r");
    char line[256];
    while(fgets(line,sizeof(line),f)) {
        assert(!strstr(line,"partner_swap"));
    }
    fclose(f);
    f = fopen("build/config_test.ini", "w");
    assert(f);
    fputs("hud_size = 70\none_screen_map_size = 99\none_screen_tree_size = 70\n", f);
    fclose(f);
    config_load();
    assert(kh_config.hud_size == 70 && kh_config.one_screen_map_size == 90);
    assert(kh_config.one_screen_tree_size == 80);
    remove("build/config_test.ini");
    puts("config_test: lock-on defaults, persistence, remapping and config validation OK");
}
