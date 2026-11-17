#ifndef KH_RECODED_HW_H
#define KH_RECODED_HW_H
#ifdef __cplusplus
extern "C" {
#endif
#include "kh_hw_map.h"
void kh_gx_cmd(volatile void *reg, unsigned long value);
#ifdef __cplusplus
}
#endif
#define KH_GX_CMD(reg, value) kh_gx_cmd((volatile void *)&(reg), (unsigned long)(value))
#endif
