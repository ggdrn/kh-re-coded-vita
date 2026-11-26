#include <math.h>
#include <string.h>

#include "hw/camera_interp.h"

static void view_projection(const KhGxCamera *camera, float out[16])
{
    for (int row = 0; row < 4; row++) {
        for (int col = 0; col < 4; col++) {
            float value = row == 3 ? (float)camera->projection[12 + col] : 0.0f;
            for (int k = 0; k < 3; k++)
                value += (float)camera->view[row * 3 + k] *
                         ((float)camera->projection[k * 4 + col] / 4096.0f);
            out[row * 4 + col] = value / 4096.0f;
        }
    }
}

static int inverse_matrix(const float matrix[16], float out[16])
{
    float aug[4][8] = {{0}};
    for (int row = 0; row < 4; row++) {
        memcpy(aug[row], matrix + 4 * row, 4 * sizeof(float));
        aug[row][4 + row] = 1.0f;
    }
    for (int col = 0; col < 4; col++) {
        int pivot = col;
        for (int row = col + 1; row < 4; row++) {
            if (fabsf(aug[row][col]) > fabsf(aug[pivot][col]))
                pivot = row;
        }
        if (fabsf(aug[pivot][col]) < 1e-6f)
            return 0;
        if (pivot != col) {
            float temp[8];
            memcpy(temp, aug[col], sizeof(temp));
            memcpy(aug[col], aug[pivot], sizeof(temp));
            memcpy(aug[pivot], temp, sizeof(temp));
        }
        const float divisor = aug[col][col];
        for (int k = col; k < 8; k++)
            aug[col][k] /= divisor;
        for (int row = 0; row < 4; row++) {
            if (row != col) {
                const float factor = aug[row][col];
                for (int k = col; k < 8; k++)
                    aug[row][k] -= factor * aug[col][k];
            }
        }
    }
    for (int row = 0; row < 4; row++)
        memcpy(out + 4 * row, aug[row] + 4, 4 * sizeof(float));
    return 1;
}

static float eye_component(const int32_t view[12], int row)
{
    /* A view matrix has translation -eye * R, so eye = -translation * R^T. */
    float value = 0.0f;
    for (int k = 0; k < 3; k++)
        value -= ((float)view[9 + k] / 4096.0f) * ((float)view[row * 3 + k] / 4096.0f);
    return value;
}

static int midpoint_transform(const float clip[16], const float other[16],
                              float wide_x, float out[16])
{
    float inverse[16];
    if (!inverse_matrix(clip, inverse))
        return 0;

    /* inverse(clip) * ((clip + other) / 2), with widescreen folded in. */
    for (int row = 0; row < 4; row++) {
        for (int col = 0; col < 4; col++) {
            float delta = 0.0f;
            for (int k = 0; k < 4; k++)
                delta += inverse[4 * row + k] * (other[4 * k + col] - clip[4 * k + col]);
            if (row == 0)
                delta /= wide_x;
            if (col == 0)
                delta *= wide_x;
            out[4 * row + col] = (float)(row == col) + 0.5f * delta;
        }
    }
    return 1;
}

KhCameraMotion kh_camera_midpoint(const KhGxCamera *a, const KhGxCamera *b,
                                  float from_a[16], float from_b[16])
{
    float old_clip[16], new_clip[16];
    float distance2 = 0.0f, trace = 0.0f;

    if (!a->valid || !b->valid || a->wide_x != b->wide_x || !(b->wide_x > 0.0f))
        return KH_CAMERA_CUT;
    if (!memcmp(a->view, b->view, sizeof(a->view)) &&
        !memcmp(a->projection, b->projection, sizeof(a->projection)))
        return KH_CAMERA_STILL;
    for (int row = 0; row < 3; row++) {
        const float delta = eye_component(a->view, row) - eye_component(b->view, row);
        distance2 += delta * delta;
    }
    for (int k = 0; k < 9; k++)
        trace += ((float)a->view[k] / 4096.0f) * ((float)b->view[k] / 4096.0f);
    /* A cut can put the old and new views on different sides of nearby geometry. */
    if (distance2 > 64.0f * 64.0f || trace < 2.73f)
        return KH_CAMERA_CUT;
    for (int k = 0; k < 16; k++) {
        const float p = (float)a->projection[k], q = (float)b->projection[k];
        if (fabsf(p - q) > 16.0f + 0.2f * fmaxf(fabsf(p), fabsf(q)))
            return KH_CAMERA_CUT;
    }

    view_projection(a, old_clip);
    view_projection(b, new_clip);
    return midpoint_transform(old_clip, new_clip, a->wide_x, from_a) &&
           midpoint_transform(new_clip, old_clip, b->wide_x, from_b)
               ? KH_CAMERA_MOVING : KH_CAMERA_CUT;
}

void kh_camera_reproject(KhGxVertex *out, const KhGxVertex *vertices, int count,
                         const float matrix[16])
{
    for (int i = 0; i < count; i++) {
        const KhGxVertex v = vertices[i];
        out[i] = v;
        if (v.tag & KH_GX_VERTEX_CAMERA) {
            out[i].x = v.x * matrix[0] + v.y * matrix[4] + v.z * matrix[8] + v.w * matrix[12];
            out[i].y = v.x * matrix[1] + v.y * matrix[5] + v.z * matrix[9] + v.w * matrix[13];
            out[i].z = v.x * matrix[2] + v.y * matrix[6] + v.z * matrix[10] + v.w * matrix[14];
            out[i].w = v.x * matrix[3] + v.y * matrix[7] + v.z * matrix[11] + v.w * matrix[15];
        }
    }
}
