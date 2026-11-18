#ifndef KH_SOUND_LOADER_VIEW_H
#define KH_SOUND_LOADER_VIEW_H
/* The EU loader wrappers only forward these pointers. Constants follow
 * libs/nns/snd/sndarc_loader_internal.h (shared source spells success SUCESS). */
typedef struct NNSSndArc NNSSndArc;
typedef struct NNSSndSeqData NNSSndSeqData;
typedef int NNSSndArcLoadResult;
enum { NNS_SND_ARC_LOAD_SUCESS = 0, NNS_SND_ARC_LOAD_ALL = 0xff };
#endif
