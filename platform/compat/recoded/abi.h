#ifndef KH_RECODED_ABI_H
#define KH_RECODED_ABI_H
/* EU os_interrupt_state.h models all three physical result registers. All active
 * callers use only r0 or discard the result. The Vita CPU backend returns r0's
 * previous mask as a scalar; NEVER erase value_in_regs on a struct return. */
#define NITRO_OS_INTERRUPT_STATE_H
#ifdef __cplusplus
extern "C" {
#endif
unsigned int OS_RestoreInterrupts(unsigned int state);
unsigned int OS_RestoreInterrupts_IrqAndFiq(unsigned int state);
#ifdef __cplusplus
}
#endif
#endif
