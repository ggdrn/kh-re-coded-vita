#include <stdint.h>

/* include/nitro/fx.h uses truncation by arithmetic shift for ScaleVecFx32. */
int32_t FX_MUL(int32_t left, int32_t right)
{
    return (int32_t)(((int64_t)left * right) >> 12);
}
