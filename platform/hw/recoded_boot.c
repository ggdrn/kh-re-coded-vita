#include "hw/recoded_boot.h"
#include "nitro/overlay.h"
#include "log.h"
extern void kh_recoded_init_dtcm(void); /* generated from reconstructed C DATA */
int kh_recoded_prepare_memory(void)
{
    LOG("recoded boot: restoring DTCM including the native IRQ handler table");
    kh_recoded_init_dtcm();
    if (!kh_overlays_snapshot()) {
        LOG("recoded boot: overlay state allocation failed");
        return 0;
    }
    LOG("recoded boot: DATA/BSS overlay snapshots ready");
    return 1;
}
