#ifndef PUTTTRACK_MOTION_DEMO_V0_H_
#define PUTTTRACK_MOTION_DEMO_V0_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MOTION_DEMO_V0_BUFFER_SAMPLES 128U
#define MOTION_DEMO_V0_CONTEXT_RAM_BUDGET_BYTES 8192U
#define MOTION_DEMO_V0_DETECTOR_ID "mcu_motion_demo_v0"
#define MOTION_DEMO_V0_PICKUP_CONFIG_SHA256 \
    "62c82c1a313f70912a5bb6c2f53c635fe179c537cdb3738dbc5d2a347050c8ad"

/* Frozen stationary-start pickup V0 values, in SI units. */
#define MOTION_DEMO_V0_GRAVITY_MPS2 9.80665f
#define MOTION_DEMO_V0_STATIONARY_ACCEL_STD_MAX_MPS2 0.15f
#define MOTION_DEMO_V0_STATIONARY_GYRO_RMS_MAX_RADS 0.08f
#define MOTION_DEMO_V0_ONSET_ACCEL_DEVIATION_MPS2 0.5f
#define MOTION_DEMO_V0_ONSET_GYRO_RADS 0.25f
#define MOTION_DEMO_V0_ONSET_WINDOW_SAMPLES 10U
#define MOTION_DEMO_V0_ONSET_ACTIVE_SAMPLES 6U
#define MOTION_DEMO_V0_PICKUP_IMPULSE_MIN_MPS 0.5f
#define MOTION_DEMO_V0_PICKUP_GYRO_MEAN_MAX_RADS 10.0f
#define MOTION_DEMO_V0_PICKUP_AXIS_MAX 0.75f

/* Post-hoc rolling display gate. It is a demo candidate, not product truth. */
#define MOTION_DEMO_V0_ROLLING_GYRO_MEAN_MIN_RADS 8.0f
#define MOTION_DEMO_V0_ROLLING_AXIS_MIN 0.90f
#define MOTION_DEMO_V0_TRACKING_GYRO_MEAN_MIN_RADS 2.0f
#define MOTION_DEMO_V0_TRACKING_AXIS_MIN 0.85f

#define MOTION_DEMO_V0_GYRO_CLIP_MICRO_RADS 34208453
#define MOTION_DEMO_V0_REQUIRED_BASELINE_SAMPLES 40U
#define MOTION_DEMO_V0_REQUIRED_IMPULSE_SAMPLES 24U
#define MOTION_DEMO_V0_REQUIRED_GYRO_SAMPLES 40U
#define MOTION_DEMO_V0_PICKUP_EVENT_LATCH_US 5000000ULL

#define MOTION_DEMO_V0_QUALITY_SENSOR_INVALID (1U << 0)
#define MOTION_DEMO_V0_QUALITY_SEQUENCE_GAP (1U << 1)
#define MOTION_DEMO_V0_QUALITY_TIME_REGRESSION (1U << 2)
#define MOTION_DEMO_V0_QUALITY_BASELINE_NOT_STATIONARY (1U << 3)
#define MOTION_DEMO_V0_QUALITY_INSUFFICIENT_WINDOW (1U << 4)
#define MOTION_DEMO_V0_QUALITY_GYRO_CLIPPED (1U << 5)

struct motion_demo_v0_sample {
    uint32_t sequence;
    uint64_t source_monotonic_us;
    int32_t accel_micro_ms2[3];
    int32_t gyro_micro_rads[3];
    bool bmi270_valid;
    uint32_t sensor_error_bits;
};

enum motion_demo_v0_state {
    MOTION_DEMO_V0_BOOTSTRAP = 0,
    MOTION_DEMO_V0_STATIONARY = 1,
    MOTION_DEMO_V0_ACTIVE_PENDING = 2,
    MOTION_DEMO_V0_ROLLING_CANDIDATE = 3,
    MOTION_DEMO_V0_CARRIED_CANDIDATE = 4,
    MOTION_DEMO_V0_ACTIVE_UNKNOWN = 5,
    MOTION_DEMO_V0_UNKNOWN_QUALITY = 6,
};

enum motion_demo_v0_event {
    MOTION_DEMO_V0_EVENT_NONE = 0,
    MOTION_DEMO_V0_EVENT_PICKUP_FROM_REST = 1,
};

struct motion_demo_v0_snapshot {
    enum motion_demo_v0_state state;
    enum motion_demo_v0_event last_event;
    uint32_t quality_flags;
    uint32_t state_transition_count;
    uint32_t event_count;
    uint32_t onset_sequence;
    uint64_t last_transition_us;
    uint64_t last_event_us;
    int32_t vertical_impulse_milli_mps;
    int32_t gyro_mean_milli_rads;
    int32_t axis_consistency_milli;
    uint16_t buffered_samples;
    bool baseline_stationary;
    bool pickup_rule_passed;
    bool rolling_rule_passed;
};

struct motion_demo_v0 {
    struct motion_demo_v0_sample samples[MOTION_DEMO_V0_BUFFER_SAMPLES];
    uint16_t write_index;
    uint16_t count;
    enum motion_demo_v0_state state;
    enum motion_demo_v0_event last_event;
    uint32_t quality_flags;
    uint32_t state_transition_count;
    uint32_t event_count;
    uint32_t onset_sequence;
    uint64_t onset_us;
    uint64_t last_transition_us;
    uint64_t last_event_us;
    uint32_t previous_sequence;
    uint64_t previous_time_us;
    bool have_previous;
    bool baseline_stationary;
    bool pickup_rule_passed;
    bool rolling_rule_passed;
    int32_t vertical_impulse_milli_mps;
    int32_t gyro_mean_milli_rads;
    int32_t axis_consistency_milli;
};

void motion_demo_v0_init(struct motion_demo_v0 *context);
bool motion_demo_v0_push(struct motion_demo_v0 *context,
                         const struct motion_demo_v0_sample *sample);
void motion_demo_v0_get_snapshot(const struct motion_demo_v0 *context,
                                 struct motion_demo_v0_snapshot *snapshot);
const char *motion_demo_v0_state_name(enum motion_demo_v0_state state);
const char *motion_demo_v0_event_name(enum motion_demo_v0_event event);

#ifdef __cplusplus
}
#endif

#endif /* PUTTTRACK_MOTION_DEMO_V0_H_ */
