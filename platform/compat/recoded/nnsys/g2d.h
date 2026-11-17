#ifndef KH_RECODED_G2D_H
#define KH_RECODED_G2D_H
#include_next "nnsys/g2d.h"
/* Values are the pixel bit depths consumed by the native character canvas. */
typedef enum NNSG2dCharaColorMode {
    NNS_G2D_CHARA_COLORMODE_16 = 4,
    NNS_G2D_CHARA_COLORMODE_256 = 8
} NNSG2dCharaColorMode;
typedef struct NNSG2dGlyph {
    const NNSG2dCharWidths *pWidths;
    const u8 *image;
} NNSG2dGlyph;
struct NNSiG2dCharCanvasVTable {
    void (*pDrawGlyph)(const NNSG2dCharCanvas *, const NNSG2dFont *, int, int, int, const NNSG2dGlyph *);
    void (*pClear)(const NNSG2dCharCanvas *, int);
    void (*pClearArea)(const NNSG2dCharCanvas *, int, int, int, int, int);
};
typedef struct NNSG2dTextRect { int width, height; } NNSG2dTextRect;
#endif
