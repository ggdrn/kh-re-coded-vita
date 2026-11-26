#ifndef KH_HW_CAMERA_INTERP_H
#define KH_HW_CAMERA_INTERP_H

#include "hw/gx3d.h"

typedef enum {
    KH_CAMERA_CUT,
    KH_CAMERA_STILL,
    KH_CAMERA_MOVING,
} KhCameraMotion;

/* For a moving camera, both transforms reproject to the same midpoint view. */
KhCameraMotion kh_camera_midpoint(const KhGxCamera *a, const KhGxCamera *b,
                                  float from_a[16], float from_b[16]);
/* out may alias vertices. */
void kh_camera_reproject(KhGxVertex *out, const KhGxVertex *vertices, int count,
                         const float matrix[16]);

/* Blend matching perspective geometry already in the same view, into B. Returns the
 * number of vertices whose positions changed. A and B must use separate storage. */
unsigned kh_motion_midpoint(const KhGxVertex *a, int count_a, KhGxVertex *b, int count_b);

#endif
