#ifndef KH_BUTTON_SPRITES_H
#define KH_BUTTON_SPRITES_H

#include <stdint.h>

/* Replace a recognized Re:coded A5I3 prompt in the copy sent to the renderer. */
int kh_button_texture(const uint8_t *texels, uint32_t size, uint8_t *out);

#endif
