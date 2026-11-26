#ifndef KH_NITRO_LZ_H
#define KH_NITRO_LZ_H

#include <stdint.h>

/* Decode an LZ11 entry from the verified cartridge, including its four-byte header. */
int kh_nitro_lz11(const uint8_t *src, uint32_t size, uint8_t *dst, uint32_t capacity);

#endif
