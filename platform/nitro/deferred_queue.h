#ifndef KH_DEFERRED_QUEUE_H
#define KH_DEFERRED_QUEUE_H
#include <stddef.h>
typedef struct Deferred {
    void (*fn)(void *a, void *b, void *c);
    void *a, *b, *c;
    struct Deferred *next;
} Deferred;
/* The caller owns the queue lock. Unlink before dispatch to allow nested polling. */
static inline Deferred *kh_take_completion(Deferred *volatile *link, void (*filter)(void *, void *, void *))
{
    while (*link && filter && (*link)->fn != filter)
        link = &(*link)->next;
    Deferred *item = *link;
    if (item) {
        *link = item->next;
        item->next = NULL;
    }
    return item;
}
#endif
