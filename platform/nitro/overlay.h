#ifndef KH_NITRO_OVERLAY_H
#define KH_NITRO_OVERLAY_H
#include <stdint.h>

/* FSOverlayInfo (include/nitro/fs.h) */
typedef struct {
    uint32_t id;
    uintptr_t ram_address;
    uint32_t ram_size;
    uint32_t bss_size;
    uintptr_t sinit_init;
    uintptr_t sinit_init_end;
    uint32_t file_id;
    uint32_t flags;
    uint32_t target;
    uint32_t file_offset, file_length;
} FSOverlayInfo;


int FS_LoadOverlayImage(FSOverlayInfo *ovi);
void FS_ClearOverlayImage(FSOverlayInfo *ovi);
void FS_StartOverlay(FSOverlayInfo *ovi);
void FS_EndOverlay(FSOverlayInfo *ovi);

/* Copy every overlay's initial .data (before the game runs), for FS_LoadOverlayImage. */
int kh_overlays_snapshot(void);
/* Whether overlay id is loaded now (its DS range not taken over by another since). */
int kh_overlay_loaded(int id);

#endif
