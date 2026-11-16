#ifndef KH_HOST_PROCESSMGR_H
#define KH_HOST_PROCESSMGR_H
#include <stdint.h>
#include <time.h>
static inline uint64_t sceKernelGetProcessTimeWide(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000u + t.tv_nsec / 1000u;
}
#endif
