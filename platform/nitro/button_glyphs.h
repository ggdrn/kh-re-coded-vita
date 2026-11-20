#ifndef KH_BUTTON_GLYPHS_H
#define KH_BUTTON_GLYPHS_H

#include <stdint.h>

/* Capture the prompt style and input mapping before NitroMain loads the UI. */
void kh_button_icons_init(void);
/* Five 5-bit rows (left pixel in bit 4) for the Vita button mapped to a DS button. */
const uint8_t *kh_button_symbol(int ds_button);

#endif
