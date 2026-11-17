/* Derived from Re:coded EU nitro/types.h (CC0). Native DS alignment on Vita. */
#ifndef NITRO_TYPES_H
#define NITRO_TYPES_H

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef signed char s8;
typedef short s16;
typedef int s32;
typedef unsigned long long u64 __attribute__((aligned(4)));
typedef long long s64 __attribute__((aligned(4)));
typedef volatile u8 vu8;
typedef volatile u16 vu16;
typedef volatile u32 vu32;
typedef volatile u64 vu64;
typedef volatile s8 vs8;
typedef volatile s16 vs16;
typedef volatile s32 vs32;
typedef volatile s64 vs64;
typedef volatile u8 REGType8v;
typedef volatile u16 REGType16v;
typedef volatile u32 REGType32v;
typedef u16 REGType16;
typedef u32 REGType32;
typedef u64 REGType64;
typedef float f32;
typedef double f64;
typedef int BOOL;
typedef int fx32;
typedef short fx16;

#ifndef NULL
#define NULL ((void *)0)
#endif
#define TRUE 1
#define FALSE 0

#endif
