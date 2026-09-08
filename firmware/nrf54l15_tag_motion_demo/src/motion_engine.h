#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "pickup_v0_generated.h"

#ifdef __cplusplus
extern "C" {
#endif

#define PT_MOTION_ENGINE_REVISION 1U
#define PT_MOTION_BUFFER_SAMPLES 128U

/* Persistent state is generic physical evidence only. */
enum pt_motion_state {
    PT_MOTION_UNKNOWN = 0,
    PT_MOTION_STATIONARY = 1,
    PT_MOTION_ROLLING = 2,
    PT_MOTION_SETTLING = 3,
    PT_MOTION_CARRIED = 4,
    PT_MOTION_AIRBORNE = 5,
};

enum pt_motion_event_bits {
    PT_EVENT_NONE = 0,
    PT_EVENT_MOTION_ONSET = 1U << 0,
    PT_EVENT_PICKUP_SUSPECTED = 1U << 1,
    PT_EVENT_ROLLING_START = 1U << 2,
    PT_EVENT_SETTLED = 1U << 3,
    PT_EVENT_DROP_LANDING_CANDIDATE = 1U << 4,
    PT_EVENT_TEE_ARM_MARKER = 1U << 5,
};

enum pt_motion_quality_bits {
    PT_QUALITY_OK = 0,
    PT_QUALITY_SENSOR_INVALID = 1U << 0,
    PT_QUALITY_GYRO_CLIPPED = 1U << 1,
    PT_QUALITY_BASELINE_UNREADY = 1U << 2,
    PT_QUALITY_PICKUP_WINDOW_CLIPPED = 1U << 3,
    PT_QUALITY_SEQUENCE_OR_TIME_GAP = 1U << 4,
};

struct pt_motion_sample {
    uint32_t sequence;
    uint64_t source_time_us;
    int32_t accel_micro_ms2[3];
    int32_t gyro_micro_rads[3];
    uint32_t sensor_error_bits;
    bool bmi270_valid;
    bool gyro_clipped;
};

struct pt_motion_features {
    float baseline_accel_stdev_mps2;
    float baseline_gyro_rms_rads;
    float rolling_mean_gyro_rads;
    float rolling_axis_consistency;
    float positive_vertical_impulse_mps;
    float pickup_mean_gyro_rads;
    float pickup_axis_consistency;
};

struct pt_motion_output {
    enum pt_motion_state state;
    uint16_t event_bits;
    uint16_t confidence_permille;
    uint16_t quality_bits;
    uint16_t reserved;
    uint32_t source_sequence;
    uint64_t source_time_us;
    uint32_t model_hash32;
    uint32_t tee_arm_epoch;
    struct pt_motion_features features;
};

struct pt_motion_engine {
    struct pt_motion_sample samples[PT_MOTION_BUFFER_SAMPLES];
    uint16_t write_index;
    uint16_t sample_count;
    enum pt_motion_state state;
    uint32_t last_sequence;
    uint64_t last_time_us;
    uint32_t tee_arm_epoch;

    bool baseline_ready;
    float baseline_up[3];

    bool onset_candidate;
    uint64_t onset_time_us;
    uint32_t onset_sequence;

    bool freefall_active;
    uint64_t freefall_start_us;

    uint16_t last_quality_bits;
};

void pt_motion_engine_init(struct pt_motion_engine *engine);
void pt_motion_engine_arm_from_tee(struct pt_motion_engine *engine);

/*
 * Push one source-ordered 50 Hz BMI270 sample.
 * Returns true when a state/quality change or transient event should be emitted.
 */
bool pt_motion_engine_push(
    struct pt_motion_engine *engine,
    const struct pt_motion_sample *sample,
    struct pt_motion_output *output);

const char *pt_motion_state_name(enum pt_motion_state state);

#ifdef __cplusplus
}
#endif
