#ifndef KH_RECODED_REGISTER_VIEWS_H
#define KH_RECODED_REGISTER_VIEWS_H
#include "nitro/types.h"
#include_next "nitro/hw.h"
#include "nitro/kh_hw.h"
/* Existing *_ADDR macros are mapped by the generated EU hardware header.
 * DIV/SQRT result reads invoke the Days backend's computed-register handlers. */
#define REG_DIVCNT (*(vu16 *)REG_DIVCNT_ADDR)
#define REG_DIV_NUMER (*(vs64 *)REG_DIV_NUMER_ADDR)
#define REG_DIV_DENOM (*(vs64 *)REG_DIV_DENOM_ADDR)
#define REG_DIV_RESULT (*(vs64 *)REG_DIV_RESULT_ADDR)
#define REG_SQRTCNT_ADDR KH_HW(0x040002b0)
#define REG_SQRT_RESULT_ADDR KH_HW(0x040002b4)
#define REG_SQRT_PARAM_ADDR KH_HW(0x040002b8)
#define REG_SQRTCNT (*(vu16 *)REG_SQRTCNT_ADDR)
#define REG_SQRT_RESULT (*(vu32 *)REG_SQRT_RESULT_ADDR)
#define REG_SQRT_PARAM (*(vu64 *)REG_SQRT_PARAM_ADDR)
#endif
