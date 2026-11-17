#ifndef KH_RECODED_BOOT_H
#define KH_RECODED_BOOT_H
/* Boot prerequisites only. Caller must not launch NitroMain until the native
 * link, hardware rewrite and callback/ABI checks are all complete. */
int kh_recoded_prepare_memory(void);
#endif
