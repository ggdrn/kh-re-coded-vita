/* Ordinary C replacements for BIOS services, using the contracts in
 * eu/docs/library/sdk_bios.md. No BIOS code or SWI runs on the Vita. */
#include <stdint.h>
uint16_t GetCRC16(uint16_t initial, const void *data, uint32_t size)
{
    const uint8_t *bytes = data;
    uint16_t crc = initial;
    while (size--) {
        crc ^= *bytes++;
        for (unsigned bit=0; bit<8; ++bit)
            crc = (uint16_t)((crc >> 1) ^ ((crc & 1) ? 0xa001u : 0));
    }
    return crc;
}
uint16_t Sqrt(uint32_t value)
{
    uint32_t root=0, bit=1u << 30;
    while (bit > value) bit >>= 2;
    while (bit) {
        if (value >= root + bit) {
            value -= root + bit;
            root = (root >> 1) + bit;
        } else root >>= 1;
        bit >>= 2;
    }
    return (uint16_t)root;
}
