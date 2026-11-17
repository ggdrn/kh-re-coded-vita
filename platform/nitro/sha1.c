#include <stdint.h>
/* ---- SHA-1 block transform (DGT's libdgt.a) ------------------------------------------------ */

#define ROL(x, n) (((x) << (n)) | ((x) >> (32 - (n))))

void DGTi_Hash2ProcessBlock(uint32_t *h, const uint8_t *p, unsigned long len)
{
    for (; len >= 64; len -= 64, p += 64) {
        uint32_t w[80], a, b, c, d, e, t;
        int i;
        for (i = 0; i < 16; i++)
            w[i] = (uint32_t)p[i * 4] << 24 | (uint32_t)p[i * 4 + 1] << 16 |
                   (uint32_t)p[i * 4 + 2] << 8 | p[i * 4 + 3];
        for (; i < 80; i++)
            w[i] = ROL(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
        a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
        for (i = 0; i < 80; i++) {
            uint32_t f, k;
            if (i < 20)      f = (b & c) | (~b & d),          k = 0x5a827999;
            else if (i < 40) f = b ^ c ^ d,                   k = 0x6ed9eba1;
            else if (i < 60) f = (b & c) | (b & d) | (c & d), k = 0x8f1bbcdc;
            else             f = b ^ c ^ d,                   k = 0xca62c1d6;
            t = ROL(a, 5) + f + e + k + w[i];
            e = d, d = c, c = ROL(b, 30), b = a, a = t;
        }
        h[0] += a, h[1] += b, h[2] += c, h[3] += d, h[4] += e;
    }
}


/* EU context: five chaining words followed by one 64-byte input block.
 * Only the chaining words are modified, as in eu/docs/library/sdk_math.md. */
void MATHi_SHA1ProcessBlock(void *context)
{
    DGTi_Hash2ProcessBlock((uint32_t *)context,(const uint8_t *)context+0x14,64);
}
