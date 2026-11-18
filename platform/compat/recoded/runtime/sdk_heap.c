#include <stddef.h>
#include <stdint.h>

/* NNSFndAllocator, from include/nnsys/fnd.h in the EU reconstruction. */
typedef struct {
    const void *functions;
    void *heap;
    uint32_t arena;
    uint32_t param2;
} Allocator;

_Static_assert(sizeof(Allocator) == 16 && offsetof(Allocator, heap) == 4 &&
               offsetof(Allocator, arena) == 8, "NNS allocator ARM32 layout");
extern void *OS_AllocFromHeap(int arena, int heap, uint32_t size);
extern void OS_FreeToHeap(int arena, int heap, void *block);

void *AllocatorAllocForSDKHeap(Allocator *allocator, uint32_t size)
{
    return OS_AllocFromHeap(allocator->arena, (int)(intptr_t)allocator->heap, size);
}

void AllocatorFreeForSDKHeap(Allocator *allocator, void *block)
{
    OS_FreeToHeap(allocator->arena, (int)(intptr_t)allocator->heap, block);
}
