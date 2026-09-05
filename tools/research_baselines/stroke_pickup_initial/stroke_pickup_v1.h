/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PT_STROKE_PICKUP_V1_H
#define PT_STROKE_PICKUP_V1_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "stroke_pickup_config.h"

/* Candidate counters are telemetry, NEVER authoritative strokes or penalties. */
enum spv1_state { SP_BOOTSTRAP, SP_QUIET, SP_MOVING, SP_ROTATION, SP_DEGRADED };
enum spv1_event_type {
    SP_STROKE_LIKE = 1, SP_PICKUP_SUSPECTED, SP_CONTACT_MOVING,
    SP_ONSET_UNRESOLVED, SP_QUALITY_BREAK
};
enum spv1_quality {
    SP_SENSOR = 1U, SP_SEQUENCE = 2U, SP_TIME = 4U,
    SP_ACCEL_RAIL = 8U, SP_GYRO_RAIL = 16U, SP_NO_BASELINE = 32U,
    SP_WINDOW = 64U, SP_HELD_CONTEXT = 128U, SP_COUNTER_OVERFLOW = 256U
};
enum spv1_reason {
    SP_HAS_EARLY_TRANSIENT = 1U, SP_HAS_ROTATION = 2U,
    SP_HAS_LIFT_SCORE = 4U, SP_NEEDS_CONTACT_SOURCE = 8U,
    SP_FROM_MOVING = 16U, SP_WEAK_OR_UNSUPPORTED = 32U,
    SP_HELD_UNRESOLVED = 64U, SP_INTERRUPTED = 128U
};
struct spv1_sample {
    uint32_t sequence;
    uint64_t time_us;
    int32_t accel_micro[3], gyro_micro[3];
    bool valid;
    uint32_t sensor_errors;
};
/* Fixed wire layout is serialized explicitly, not by dumping this structure. */
struct spv1_event {
    uint32_t id, type, reason, quality, onset_seq, end_seq;
    uint64_t onset_us, decision_us;
    int32_t impulse_milli, gyro_mean_milli;
    uint32_t direction_milli, axial_milli, impact_milli, clip_permille;
};
struct spv1_window {
    bool active, up_valid;
    uint64_t start_us;
    uint32_t start_seq, samples, active_samples, clip_samples, quality;
    float up[3], gravity, impulse, gyro_sum, gyro_vector[3], moment[6];
    float impact_max;
};
struct spv1_context {
    struct spv1_event events[SPV1_EVENT_CAPACITY];
    struct spv1_window window;
    enum spv1_state state;
    bool have_previous, armed, held_hint, count_incomplete;
    uint32_t generation, latest_id, event_count, overwritten;
    uint32_t stroke_candidates, pickup_candidates, ambiguous_contacts, unknown_onsets;
    uint32_t quality_breaks, current_quality, source_sequence;
    uint64_t source_us, quiet_start_us, last_contact_us;
    uint32_t quiet_samples;
    float quiet_accel_sum[3], gravity, previous_accel[3], previous_gyro[3];
};
void spv1_init(struct spv1_context *c);
void spv1_invalidate(struct spv1_context *c);
void spv1_push(struct spv1_context *c, const struct spv1_sample *s);
/* Copy chronological events. Caller must hold its application mutex. */
size_t spv1_events(const struct spv1_context *c, struct spv1_event *out, size_t capacity);
const char *spv1_event_name(uint32_t type);
#endif
