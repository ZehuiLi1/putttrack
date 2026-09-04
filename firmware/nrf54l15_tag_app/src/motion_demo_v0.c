#include "motion_demo_v0.h"

#include <string.h>

#define MICRO_F 1000000.0f
#define BASELINE_WINDOW_US 1000000ULL
#define IMPULSE_WINDOW_BEFORE_US 100000ULL
#define IMPULSE_WINDOW_AFTER_US 500000ULL
#define GYRO_WINDOW_US 1000000ULL
#define TRACKING_WINDOW_US 500000ULL
#define MIN_BASELINE_DURATION_US 900000ULL
#define MIN_TRACKING_SAMPLES 20U

_Static_assert(sizeof(struct motion_demo_v0) <=
                   MOTION_DEMO_V0_CONTEXT_RAM_BUDGET_BYTES,
               "motion demo context exceeds the research RAM budget");

struct motion_demo_window_stats {
    uint16_t count;
    uint64_t first_us;
    uint64_t last_us;
    float accel_norm_mean;
    float accel_norm_m2;
    float gyro_norm_sum;
    float gyro_norm_sq_sum;
    float gyro_vector_sum[3];
    bool invalid;
    bool gyro_clipped;
};

static float demo_absf(float value)
{
    return value < 0.0f ? -value : value;
}

static float demo_sqrtf(float value)
{
    if (value <= 0.0f) {
        return 0.0f;
    }
    float estimate = value > 1.0f ? value : 1.0f;
    for (size_t iteration = 0; iteration < 16U; iteration++) {
        estimate = 0.5f * (estimate + value / estimate);
    }
    return estimate;
}

static float vector_norm_micro(const int32_t vector[3])
{
    float squared = 0.0f;
    for (size_t axis = 0; axis < 3U; axis++) {
        float value = (float)vector[axis] / MICRO_F;
        squared += value * value;
    }
    return demo_sqrtf(squared);
}

static bool sample_is_valid(const struct motion_demo_v0_sample *sample)
{
    return sample->bmi270_valid && sample->sensor_error_bits == 0U;
}

static bool sample_gyro_clipped(const struct motion_demo_v0_sample *sample)
{
    for (size_t axis = 0; axis < 3U; axis++) {
        int64_t value = sample->gyro_micro_rads[axis];
        if (value < 0) {
            value = -value;
        }
        if (value >= MOTION_DEMO_V0_GYRO_CLIP_MICRO_RADS) {
            return true;
        }
    }
    return false;
}

static bool sample_is_active(const struct motion_demo_v0_sample *sample)
{
    float accel_norm = vector_norm_micro(sample->accel_micro_ms2);
    float gyro_norm = vector_norm_micro(sample->gyro_micro_rads);
    return demo_absf(accel_norm - MOTION_DEMO_V0_GRAVITY_MPS2) >=
               MOTION_DEMO_V0_ONSET_ACCEL_DEVIATION_MPS2 ||
           gyro_norm >= MOTION_DEMO_V0_ONSET_GYRO_RADS;
}

static uint16_t oldest_index(const struct motion_demo_v0 *context)
{
    return (uint16_t)((context->write_index + MOTION_DEMO_V0_BUFFER_SAMPLES -
                       context->count) %
                      MOTION_DEMO_V0_BUFFER_SAMPLES);
}

static const struct motion_demo_v0_sample *sample_at(
    const struct motion_demo_v0 *context, uint16_t logical_index)
{
    uint16_t index = (uint16_t)((oldest_index(context) + logical_index) %
                                MOTION_DEMO_V0_BUFFER_SAMPLES);
    return &context->samples[index];
}

static void store_sample(struct motion_demo_v0 *context,
                         const struct motion_demo_v0_sample *sample)
{
    context->samples[context->write_index] = *sample;
    context->write_index = (uint16_t)((context->write_index + 1U) %
                                      MOTION_DEMO_V0_BUFFER_SAMPLES);
    if (context->count < MOTION_DEMO_V0_BUFFER_SAMPLES) {
        context->count++;
    }
}

static bool set_state(struct motion_demo_v0 *context,
                      enum motion_demo_v0_state state,
                      uint64_t transition_us)
{
    if (context->state == state) {
        return false;
    }
    context->state = state;
    context->last_transition_us = transition_us;
    context->state_transition_count++;
    return true;
}

static void reset_candidate_features(struct motion_demo_v0 *context)
{
    context->baseline_stationary = false;
    context->pickup_rule_passed = false;
    context->rolling_rule_passed = false;
    context->vertical_impulse_milli_mps = 0;
    context->gyro_mean_milli_rads = 0;
    context->axis_consistency_milli = 0;
    context->onset_sequence = 0U;
    context->onset_us = 0U;
}

static void reset_history_after_fault(struct motion_demo_v0 *context)
{
    context->write_index = 0U;
    context->count = 0U;
    reset_candidate_features(context);
}

static void window_stats_add(struct motion_demo_window_stats *stats,
                             const struct motion_demo_v0_sample *sample)
{
    float accel_norm = vector_norm_micro(sample->accel_micro_ms2);
    float gyro_norm = vector_norm_micro(sample->gyro_micro_rads);
    stats->count++;
    if (stats->count == 1U) {
        stats->first_us = sample->source_monotonic_us;
        stats->accel_norm_mean = accel_norm;
    } else {
        float delta = accel_norm - stats->accel_norm_mean;
        stats->accel_norm_mean += delta / (float)stats->count;
        stats->accel_norm_m2 += delta *
                               (accel_norm - stats->accel_norm_mean);
    }
    stats->last_us = sample->source_monotonic_us;
    stats->gyro_norm_sum += gyro_norm;
    stats->gyro_norm_sq_sum += gyro_norm * gyro_norm;
    for (size_t axis = 0; axis < 3U; axis++) {
        stats->gyro_vector_sum[axis] +=
            (float)sample->gyro_micro_rads[axis] / MICRO_F;
    }
    stats->invalid |= !sample_is_valid(sample);
    stats->gyro_clipped |= sample_gyro_clipped(sample);
}

static struct motion_demo_window_stats window_stats(
    const struct motion_demo_v0 *context, uint64_t start_us, uint64_t end_us)
{
    struct motion_demo_window_stats stats = {0};
    for (uint16_t index = 0U; index < context->count; index++) {
        const struct motion_demo_v0_sample *sample = sample_at(context, index);
        if (sample->source_monotonic_us >= start_us &&
            sample->source_monotonic_us < end_us) {
            window_stats_add(&stats, sample);
        }
    }
    return stats;
}

static float window_accel_std(const struct motion_demo_window_stats *stats)
{
    if (stats->count < 2U) {
        return 0.0f;
    }
    return demo_sqrtf(stats->accel_norm_m2 / (float)stats->count);
}

static float window_gyro_rms(const struct motion_demo_window_stats *stats)
{
    if (stats->count == 0U) {
        return 0.0f;
    }
    return demo_sqrtf(stats->gyro_norm_sq_sum / (float)stats->count);
}

static float window_gyro_mean(const struct motion_demo_window_stats *stats)
{
    return stats->count == 0U ? 0.0f :
           stats->gyro_norm_sum / (float)stats->count;
}

static float window_axis_consistency(
    const struct motion_demo_window_stats *stats)
{
    float mean_norm = window_gyro_mean(stats);
    if (stats->count == 0U || mean_norm <= 0.000001f) {
        return 0.0f;
    }
    float squared = 0.0f;
    for (size_t axis = 0; axis < 3U; axis++) {
        float mean = stats->gyro_vector_sum[axis] / (float)stats->count;
        squared += mean * mean;
    }
    return demo_sqrtf(squared) / mean_norm;
}

static bool stationary_window(const struct motion_demo_v0 *context,
                              uint64_t end_us)
{
    uint64_t start_us = end_us > BASELINE_WINDOW_US ?
                        end_us - BASELINE_WINDOW_US : 0U;
    struct motion_demo_window_stats stats =
        window_stats(context, start_us, end_us + 1U);
    if (stats.count < MOTION_DEMO_V0_REQUIRED_BASELINE_SAMPLES ||
        stats.invalid || stats.last_us <= stats.first_us ||
        stats.last_us - stats.first_us < MIN_BASELINE_DURATION_US) {
        return false;
    }
    return window_accel_std(&stats) <=
               MOTION_DEMO_V0_STATIONARY_ACCEL_STD_MAX_MPS2 &&
           window_gyro_rms(&stats) <=
               MOTION_DEMO_V0_STATIONARY_GYRO_RMS_MAX_RADS;
}

static bool onset_block_ready(const struct motion_demo_v0 *context,
                              uint16_t *onset_logical_index)
{
    if (context->count < MOTION_DEMO_V0_ONSET_WINDOW_SAMPLES) {
        return false;
    }
    uint16_t start = (uint16_t)(context->count -
                                MOTION_DEMO_V0_ONSET_WINDOW_SAMPLES);
    uint16_t active = 0U;
    for (uint16_t offset = 0U;
         offset < MOTION_DEMO_V0_ONSET_WINDOW_SAMPLES; offset++) {
        const struct motion_demo_v0_sample *sample =
            sample_at(context, (uint16_t)(start + offset));
        active += sample_is_active(sample) ? 1U : 0U;
    }
    if (active < MOTION_DEMO_V0_ONSET_ACTIVE_SAMPLES) {
        return false;
    }
    *onset_logical_index = start;
    return true;
}

static bool baseline_before_onset(const struct motion_demo_v0 *context,
                                  uint64_t onset_us,
                                  float mean_accel[3])
{
    uint64_t start_us = onset_us > BASELINE_WINDOW_US ?
                        onset_us - BASELINE_WINDOW_US : 0U;
    struct motion_demo_window_stats stats =
        window_stats(context, start_us, onset_us);
    if (stats.count < MOTION_DEMO_V0_REQUIRED_BASELINE_SAMPLES ||
        stats.invalid || stats.last_us <= stats.first_us ||
        stats.last_us - stats.first_us < MIN_BASELINE_DURATION_US ||
        window_accel_std(&stats) >
            MOTION_DEMO_V0_STATIONARY_ACCEL_STD_MAX_MPS2 ||
        window_gyro_rms(&stats) >
            MOTION_DEMO_V0_STATIONARY_GYRO_RMS_MAX_RADS) {
        return false;
    }

    uint16_t count = 0U;
    for (uint16_t index = 0U; index < context->count; index++) {
        const struct motion_demo_v0_sample *sample = sample_at(context, index);
        if (sample->source_monotonic_us < start_us ||
            sample->source_monotonic_us >= onset_us) {
            continue;
        }
        for (size_t axis = 0U; axis < 3U; axis++) {
            mean_accel[axis] +=
                (float)sample->accel_micro_ms2[axis] / MICRO_F;
        }
        count++;
    }
    if (count == 0U) {
        return false;
    }
    for (size_t axis = 0U; axis < 3U; axis++) {
        mean_accel[axis] /= (float)count;
    }
    return true;
}

static bool normalize3(float vector[3])
{
    float squared = vector[0] * vector[0] + vector[1] * vector[1] +
                    vector[2] * vector[2];
    float magnitude = demo_sqrtf(squared);
    if (magnitude <= 0.000001f) {
        return false;
    }
    for (size_t axis = 0U; axis < 3U; axis++) {
        vector[axis] /= magnitude;
    }
    return true;
}

static void propagate_up(float up[3], const int32_t gyro_micro[3], float dt)
{
    float gyro[3];
    for (size_t axis = 0U; axis < 3U; axis++) {
        gyro[axis] = (float)gyro_micro[axis] / MICRO_F;
    }
    float cross[3] = {
        gyro[1] * up[2] - gyro[2] * up[1],
        gyro[2] * up[0] - gyro[0] * up[2],
        gyro[0] * up[1] - gyro[1] * up[0],
    };
    for (size_t axis = 0U; axis < 3U; axis++) {
        up[axis] -= cross[axis] * dt;
    }
    (void)normalize3(up);
}

static float dot_accel_up(const int32_t accel_micro[3], const float up[3])
{
    float value = 0.0f;
    for (size_t axis = 0U; axis < 3U; axis++) {
        value += ((float)accel_micro[axis] / MICRO_F) * up[axis];
    }
    return value;
}

static int32_t to_milli(float value)
{
    float scaled = value * 1000.0f;
    return (int32_t)(scaled >= 0.0f ? scaled + 0.5f : scaled - 0.5f);
}

static bool evaluate_pending_candidate(struct motion_demo_v0 *context,
                                       uint64_t now_us)
{
    float up[3] = {0.0f, 0.0f, 0.0f};
    if (!baseline_before_onset(context, context->onset_us, up) ||
        !normalize3(up)) {
        context->quality_flags =
            MOTION_DEMO_V0_QUALITY_BASELINE_NOT_STATIONARY;
        context->baseline_stationary = false;
        return set_state(context, MOTION_DEMO_V0_UNKNOWN_QUALITY, now_us);
    }
    context->baseline_stationary = true;

    uint64_t propagation_start = context->onset_us - BASELINE_WINDOW_US;
    uint64_t impulse_start = context->onset_us - IMPULSE_WINDOW_BEFORE_US;
    uint64_t impulse_end = context->onset_us + IMPULSE_WINDOW_AFTER_US;
    uint64_t gyro_end = context->onset_us + GYRO_WINDOW_US;
    float impulse = 0.0f;
    float gyro_norm_sum = 0.0f;
    float gyro_vector_sum[3] = {0.0f, 0.0f, 0.0f};
    uint16_t impulse_count = 0U;
    uint16_t gyro_count = 0U;
    bool clipped = false;
    const struct motion_demo_v0_sample *previous = NULL;
    const struct motion_demo_v0_sample *previous_impulse = NULL;

    for (uint16_t index = 0U; index < context->count; index++) {
        const struct motion_demo_v0_sample *sample = sample_at(context, index);
        if (sample->source_monotonic_us < propagation_start ||
            sample->source_monotonic_us >= gyro_end) {
            continue;
        }
        if (!sample_is_valid(sample)) {
            context->quality_flags =
                MOTION_DEMO_V0_QUALITY_SENSOR_INVALID;
            return set_state(context, MOTION_DEMO_V0_UNKNOWN_QUALITY, now_us);
        }
        if (previous != NULL) {
            float dt = (float)(sample->source_monotonic_us -
                               previous->source_monotonic_us) / MICRO_F;
            propagate_up(up, previous->gyro_micro_rads, dt);
        }

        if (sample->source_monotonic_us >= impulse_start &&
            sample->source_monotonic_us < impulse_end) {
            impulse_count++;
            if (previous_impulse != NULL) {
                float dt = (float)(sample->source_monotonic_us -
                                   previous_impulse->source_monotonic_us) /
                           MICRO_F;
                float dynamic = dot_accel_up(sample->accel_micro_ms2, up) -
                                MOTION_DEMO_V0_GRAVITY_MPS2;
                if (dynamic > 0.0f) {
                    impulse += dynamic * dt;
                }
            }
            previous_impulse = sample;
        }

        if (sample->source_monotonic_us >= context->onset_us) {
            float gyro_norm = vector_norm_micro(sample->gyro_micro_rads);
            gyro_norm_sum += gyro_norm;
            for (size_t axis = 0U; axis < 3U; axis++) {
                gyro_vector_sum[axis] +=
                    (float)sample->gyro_micro_rads[axis] / MICRO_F;
            }
            gyro_count++;
            clipped |= sample_gyro_clipped(sample);
        }
        previous = sample;
    }

    if (impulse_count < MOTION_DEMO_V0_REQUIRED_IMPULSE_SAMPLES ||
        gyro_count < MOTION_DEMO_V0_REQUIRED_GYRO_SAMPLES) {
        context->quality_flags =
            MOTION_DEMO_V0_QUALITY_INSUFFICIENT_WINDOW;
        return set_state(context, MOTION_DEMO_V0_UNKNOWN_QUALITY, now_us);
    }

    float gyro_mean = gyro_norm_sum / (float)gyro_count;
    float mean_vector_sq = 0.0f;
    for (size_t axis = 0U; axis < 3U; axis++) {
        float mean = gyro_vector_sum[axis] / (float)gyro_count;
        mean_vector_sq += mean * mean;
    }
    float axis_consistency = gyro_mean > 0.000001f ?
                             demo_sqrtf(mean_vector_sq) / gyro_mean : 0.0f;

    context->vertical_impulse_milli_mps = to_milli(impulse);
    context->gyro_mean_milli_rads = to_milli(gyro_mean);
    context->axis_consistency_milli = to_milli(axis_consistency);
    context->pickup_rule_passed =
        !clipped && impulse > MOTION_DEMO_V0_PICKUP_IMPULSE_MIN_MPS &&
        gyro_mean < MOTION_DEMO_V0_PICKUP_GYRO_MEAN_MAX_RADS &&
        axis_consistency < MOTION_DEMO_V0_PICKUP_AXIS_MAX;
    context->rolling_rule_passed =
        gyro_mean >= MOTION_DEMO_V0_ROLLING_GYRO_MEAN_MIN_RADS &&
        axis_consistency >= MOTION_DEMO_V0_ROLLING_AXIS_MIN;
    context->quality_flags = clipped ?
        MOTION_DEMO_V0_QUALITY_GYRO_CLIPPED : 0U;

    if (context->pickup_rule_passed) {
        context->last_event = MOTION_DEMO_V0_EVENT_PICKUP_FROM_REST;
        context->last_event_us = now_us;
        context->event_count++;
        return set_state(context, MOTION_DEMO_V0_CARRIED_CANDIDATE, now_us);
    }
    if (context->rolling_rule_passed) {
        return set_state(context, MOTION_DEMO_V0_ROLLING_CANDIDATE, now_us);
    }
    if (clipped) {
        return set_state(context, MOTION_DEMO_V0_UNKNOWN_QUALITY, now_us);
    }
    return set_state(context, MOTION_DEMO_V0_ACTIVE_UNKNOWN, now_us);
}

static bool recent_window_is_rolling(const struct motion_demo_v0 *context,
                                     uint64_t now_us)
{
    uint64_t start_us = now_us > TRACKING_WINDOW_US ?
                        now_us - TRACKING_WINDOW_US : 0U;
    struct motion_demo_window_stats stats =
        window_stats(context, start_us, now_us + 1U);
    if (stats.count < MIN_TRACKING_SAMPLES || stats.invalid) {
        return false;
    }
    return window_gyro_mean(&stats) >=
               MOTION_DEMO_V0_TRACKING_GYRO_MEAN_MIN_RADS &&
           window_axis_consistency(&stats) >=
               MOTION_DEMO_V0_TRACKING_AXIS_MIN;
}

void motion_demo_v0_init(struct motion_demo_v0 *context)
{
    memset(context, 0, sizeof(*context));
    context->state = MOTION_DEMO_V0_BOOTSTRAP;
    context->last_event = MOTION_DEMO_V0_EVENT_NONE;
}

bool motion_demo_v0_push(struct motion_demo_v0 *context,
                         const struct motion_demo_v0_sample *sample)
{
    bool changed = false;
    uint32_t fault_flags = 0U;

    if (context->have_previous) {
        if (sample->sequence != context->previous_sequence + 1U) {
            fault_flags |= MOTION_DEMO_V0_QUALITY_SEQUENCE_GAP;
        }
        if (sample->source_monotonic_us <= context->previous_time_us) {
            fault_flags |= MOTION_DEMO_V0_QUALITY_TIME_REGRESSION;
        }
    }
    if (!sample_is_valid(sample)) {
        fault_flags |= MOTION_DEMO_V0_QUALITY_SENSOR_INVALID;
    }

    if (fault_flags != 0U) {
        reset_history_after_fault(context);
        context->quality_flags = fault_flags;
        changed |= set_state(context, MOTION_DEMO_V0_UNKNOWN_QUALITY,
                             sample->source_monotonic_us);
    }

    store_sample(context, sample);
    context->previous_sequence = sample->sequence;
    context->previous_time_us = sample->source_monotonic_us;
    context->have_previous = true;

    if (fault_flags != 0U) {
        return changed;
    }

    bool stationary = stationary_window(context, sample->source_monotonic_us);
    if (context->state == MOTION_DEMO_V0_BOOTSTRAP ||
        context->state == MOTION_DEMO_V0_UNKNOWN_QUALITY) {
        if (stationary) {
            context->quality_flags = 0U;
            reset_candidate_features(context);
            changed |= set_state(context, MOTION_DEMO_V0_STATIONARY,
                                 sample->source_monotonic_us);
        }
        return changed;
    }

    if (context->state == MOTION_DEMO_V0_STATIONARY) {
        uint16_t onset_index;
        if (onset_block_ready(context, &onset_index)) {
            const struct motion_demo_v0_sample *onset =
                sample_at(context, onset_index);
            context->onset_sequence = onset->sequence;
            context->onset_us = onset->source_monotonic_us;
            context->baseline_stationary = true;
            context->pickup_rule_passed = false;
            context->rolling_rule_passed = false;
            context->quality_flags = 0U;
            changed |= set_state(context, MOTION_DEMO_V0_ACTIVE_PENDING,
                                 sample->source_monotonic_us);
        }
        return changed;
    }

    if (context->state == MOTION_DEMO_V0_ACTIVE_PENDING) {
        if (sample->source_monotonic_us >=
            context->onset_us + GYRO_WINDOW_US) {
            changed |= evaluate_pending_candidate(context,
                                                  sample->source_monotonic_us);
        }
        return changed;
    }

    if (stationary &&
        (context->state != MOTION_DEMO_V0_CARRIED_CANDIDATE ||
         sample->source_monotonic_us - context->last_event_us >= 1500000ULL)) {
        context->quality_flags = 0U;
        context->rolling_rule_passed = false;
        changed |= set_state(context, MOTION_DEMO_V0_STATIONARY,
                             sample->source_monotonic_us);
        return changed;
    }

    bool rolling = recent_window_is_rolling(context,
                                             sample->source_monotonic_us);
    if (context->state == MOTION_DEMO_V0_ROLLING_CANDIDATE && !rolling) {
        context->rolling_rule_passed = false;
        changed |= set_state(context, MOTION_DEMO_V0_ACTIVE_UNKNOWN,
                             sample->source_monotonic_us);
    }

    return changed;
}

void motion_demo_v0_get_snapshot(const struct motion_demo_v0 *context,
                                 struct motion_demo_v0_snapshot *snapshot)
{
    snapshot->state = context->state;
    snapshot->last_event = context->last_event;
    snapshot->quality_flags = context->quality_flags;
    snapshot->state_transition_count = context->state_transition_count;
    snapshot->event_count = context->event_count;
    snapshot->onset_sequence = context->onset_sequence;
    snapshot->last_transition_us = context->last_transition_us;
    snapshot->last_event_us = context->last_event_us;
    snapshot->vertical_impulse_milli_mps =
        context->vertical_impulse_milli_mps;
    snapshot->gyro_mean_milli_rads = context->gyro_mean_milli_rads;
    snapshot->axis_consistency_milli = context->axis_consistency_milli;
    snapshot->buffered_samples = context->count;
    snapshot->baseline_stationary = context->baseline_stationary;
    snapshot->pickup_rule_passed = context->pickup_rule_passed;
    snapshot->rolling_rule_passed = context->rolling_rule_passed;
}

const char *motion_demo_v0_state_name(enum motion_demo_v0_state state)
{
    switch (state) {
    case MOTION_DEMO_V0_STATIONARY:
        return "STATIONARY";
    case MOTION_DEMO_V0_ACTIVE_PENDING:
        return "ACTIVE_PENDING";
    case MOTION_DEMO_V0_ROLLING_CANDIDATE:
        return "ROLLING_CANDIDATE";
    case MOTION_DEMO_V0_CARRIED_CANDIDATE:
        return "CARRIED_CANDIDATE";
    case MOTION_DEMO_V0_ACTIVE_UNKNOWN:
        return "ACTIVE_UNKNOWN";
    case MOTION_DEMO_V0_UNKNOWN_QUALITY:
        return "UNKNOWN_QUALITY";
    case MOTION_DEMO_V0_BOOTSTRAP:
    default:
        return "BOOTSTRAP";
    }
}

const char *motion_demo_v0_event_name(enum motion_demo_v0_event event)
{
    return event == MOTION_DEMO_V0_EVENT_PICKUP_FROM_REST ?
           "PICKUP_FROM_REST" : "NONE";
}
