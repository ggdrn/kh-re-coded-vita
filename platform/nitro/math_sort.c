#include <stdint.h>
/* ---- MATH_QSort (qsort.c), translated from the SDK's ARM ------------------------------------
 * Same pivot (the middle element swapped to the front), same partition and the same order of
 * pushes, so equal keys end up where the DS put them. */

typedef int32_t (*MATHCompareFunc)(void *a, void *b);

static void swap_elems(uint8_t *a, uint8_t *b, uint32_t width)
{
    if ((width & 3) == 0) {
        for (; width; width -= 4, a += 4, b += 4) {
            uint32_t t = *(uint32_t *)a;
            *(uint32_t *)a = *(uint32_t *)b;
            *(uint32_t *)b = t;
        }
    } else {
        for (; width; width--, a++, b++) {
            uint8_t t = *a;
            *a = *b;
            *b = t;
        }
    }
}

void Util_QuickSortWithWork(void *head, uint32_t num, uint32_t width, MATHCompareFunc comp,
                            void *stackBuf)
{
    uint8_t *local_stack[2 * 64];
    uint8_t **stack = stackBuf ? (uint8_t **)stackBuf : local_stack; /* the SDK sizes it 8 bytes per bit of num: 32 pairs at most */
    int sp = 0;
    if ((int32_t)num <= 1) return;
    if (!width) { (void)comp(head,head); return; }
    uint32_t shift = 32 - __builtin_clz(width);
    stack[sp++] = head;
    stack[sp++] = (uint8_t *)head + (num - 1) * width;

    while (sp) {
        uint8_t *right = stack[--sp];
        uint8_t *left = stack[--sp];
        uint8_t *l, *r, *mid;

        if ((uint32_t)(right - left) == width) {
            if (comp(left, right) > 0)
                swap_elems(left, right, width);
            continue;
        }
        mid = left + (((uint32_t)(right - left)) >> shift) * width;
        swap_elems(mid, left, width);

        l = left + width;
        r = right;
        for (;;) {
            while (l < right && comp(l, left) < 0)
                l += width;
            while (comp(r, left) > 0)
                r -= width;
            if (l >= r)
                break;
            swap_elems(l, r, width);
            l += width;
            r -= width;
            if (l > r)
                break;
        }
        swap_elems(left, r, width);

        if ((int32_t)(r - left) > (int32_t)(right - r)) {
            if ((uint32_t)(r - left) > width) {
                stack[sp++] = left;
                stack[sp++] = r - width;
            }
            if ((uint32_t)(right - r) > width) {
                stack[sp++] = r + width;
                stack[sp++] = right;
            }
        } else {
            if ((uint32_t)(right - r) > width) {
                stack[sp++] = r + width;
                stack[sp++] = right;
            }
            if ((uint32_t)(r - left) > width) {
                stack[sp++] = left;
                stack[sp++] = r - width;
            }
        }
    }
}


/* Same verified NitroSDK routine, retained numeric EU symbol. */
void func_0200dc4c(void *head, uint32_t num, uint32_t width, MATHCompareFunc comp, void *stackBuf)
{
    Util_QuickSortWithWork(head,num,width,comp,stackBuf);
}
