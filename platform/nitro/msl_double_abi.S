.syntax unified
.arm
.text
/* GCC callers use VFP registers. The MSL bodies use core registers. */
.macro entry name
.global \name
.type \name,%function
\name:
    push {r4,lr}
.endm

entry _dsub
    vmov r0,r1,d0
    vmov r2,r3,d1
    bl kh_raw_dsub
    vmov d0,r0,r1
    pop {r4,pc}
.size _dsub,.-_dsub

entry _dflt
    bl kh_raw_dflt
    vmov d0,r0,r1
    pop {r4,pc}
.size _dflt,.-_dflt

entry _d2f
    vmov r0,r1,d0
    bl kh_raw_d2f
    vmov s0,r0
    pop {r4,pc}
.size _d2f,.-_d2f
