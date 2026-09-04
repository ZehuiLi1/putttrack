#include "motion_engine.h"

#include <math.h>
#include <string.h>

#define MICRO_SCALE 1000000.0f
#define ROLL_WINDOW_SAMPLES 20U
#define STATIONARY_WINDOW_SAMPLES 50U
#define SETTLING_GYRO_MIN_RADS 0.25f
#define ROLLING_GYRO_MIN_RADS 3.0f
#define ROLLING_AXIS_MIN 0.72f
#define FREEFALL_ACCEL_MAX_MPS2 2.0f
#define LANDING_ACCEL_MIN_MPS2 25.0f
#define FREEFALL_LANDING_MAX_US 400000ULL
#define SOURCE_GAP_MAX_US 50000ULL

static float vec_norm3f(float x, float y, float z)
{
    return sqrtf(x * x + y * y + z * z);
}

static float sample_accel_norm(const struct pt_motion_sample *sample)
{
    return vec_norm3f(
        sample->accel_micro_ms2[0] / MICRO_SCALE,
        sample->accel_micro_ms2[1] / MICRO_SCALE,
        sample->accel_micro_ms2[2] / MICRO_SCALE);
}

static float sample_gyro_norm(const struct pt_motion_sample *sample)
{
    return vec_norm3f(
        sample->gyro_micro_rads[0] / MICRO_SCALE,
        sample->gyro_micro_rads[1] / MICRO_SCALE,
        sample->gyro_micro_rads[2] / MICRO_SCALE);
}

static uint16_t oldest_index(const struct pt_motion_engine *engine)
{
    return (uint16_t)((engine->write_index + PT_MOTION_BUFFER_SAMPLES -
                       engine->sample_count) % PT_MOTION_BUFFER_SAMPLES);
}

static const struct pt_motion_sample *sample_from_oldest(
    const struct pt_motion_engine *engine, uint16_t offset)
{
    uint16_t index = (uint16_t)((oldest_index(engine) + offset) %
                                PT_MOTION_BUFFER_SAMPLES);
    return &engine->samples[index];
}

static const struct pt_motion_sample *sample_from_newest(
    const struct pt_motion_engine *engine, uint16_t offset)
{
    uint16_t index = (uint16_t)((engine->write_index + PT_MOTION_BUFFER_SAMPLES -
                                 1U - offset) % PT_MOTION_BUFFER_SAMPLES);
    return &engine->samples[index];
}

static void append_sample(struct pt_motion_engine *engine,
                          const struct pt_motion_sample *sample)
{
    engine->samples[engine->write_index] = *sample;
    engine->write_index = (uint16_t)((engine->write_index + 1U) %
                                     PT_MOTION_BUFFER_SAMPLES);
    if (engine->sample_count < PT_MOTION_BUFFER_SAMPLES) {
        engine->sample_count++;
    }
}

static bool valid_sample(const struct pt_motion_sample *sample)
{
    return sample->bmi270_valid && sample->sensor_error_bits == 0U;
}

static bool compute_stationary_window(
    const struct pt_motion_engine *engine,
    float *accel_stdev,
    float *gyro_rms,
    float mean_accel[3])
{
    float accel_sum = 0.0f;
    float accel_sq_sum = 0.0f;
    float gyro_sq_sum = 0.0f;
    float axis_sum[3] = {0.0f, 0.0f, 0.0f};

    if (engine->sample_count < STATIONARY_WINDOW_SAMPLES) {
        return false;
    }

    for (uint16_t i = 0; i < STATIONARY_WINDOW_SAMPLES; ++i) {
        const struct pt_motion_sample *sample = sample_from_newest(engine, i);
        float accel;
        float gyro;

        if (!valid_sample(sample)) {
            return false;
        }
        accel = sample_accel_norm(sample);
        gyro = sample_gyro_norm(sample);
        accel_sum += accel;
        accel_sq_sum += accel * accel;
        gyro_sq_sum += gyro * gyro;
        for (size_t axis = 0; axis < 3; ++axis) {
            axis_sum[axis] += sample->accel_micro_ms2[axis] / MICRO_SCALE;
        }
    }

    {
        const float n = (float)STATIONARY_WINDOW_SAMPLES;
        const float mean = accel_sum / n;
        const float variance = fmaxf(0.0f, accel_sq_sum / n - mean * mean);
        *accel_stdev = sqrtf(variance);
        *gyro_rms = sqrtf(gyro_sq_sum / n);
        for (size_t axis = 0; axis < 3; ++axis) {
            mean_accel[axis] = axis_sum[axis] / n;
        }
    }
    return true;
}

static bool compute_gyro_shape_last(
    const struct pt_motion_engine *engine,
    uint16_t count,
    float *mean_norm,
    float *axis_consistency,
    bool *clipped)
{
    float norm_sum = 0.0f;
    float mean_vector[3] = {0.0f, 0.0f, 0.0f};

    if (engine->sample_count < count || count == 0U) {
        return false;
    }
    *clipped = false;
    for (uint16_t i = 0; i < count; ++i) {
        const struct pt_motion_sample *sample = sample_from_newest(engine, i);
        float gyro[3];
        float norm;

        if (!valid_sample(sample)) {
            return false;
        }
        for (size_t axis = 0; axis < 3; ++axis) {
            gyro[axis] = sample->gyro_micro_rads[axis] / MICRO_SCALE;
            mean_vector[axis] += gyro[axis];
        }
        norm = vec_norm3f(gyro[0], gyro[1], gyro[2]);
        norm_sum += norm;
        *clipped |= sample->gyro_clipped;
    }

    *mean_norm = norm_sum / (float)count;
    if (*mean_norm <= 1.0e-6f) {
        *axis_consistency = 0.0f;
    } else {
        float vector_norm;
        for (size_t axis = 0; axis < 3; ++axis) {
            mean_vector[axis] /= (float)count;
        }
        vector_norm = vec_norm3f(mean_vector[0], mean_vector[1], mean_vector[2]);
        *axis_consistency = vector_norm / *mean_norm;
    }
    return true;
}

static bool is_active_sample(const struct pt_motion_sample *sample)
{
    float accel = sample_accel_norm(sample);
    float gyro = sample_gyro_norm(sample);
    return fabsf(accel - PT_PICKUP_V0_GRAVITY_MPS2) >=
               PT_PICKUP_V0_ONSET_ACCEL_DEVIATION ||
           gyro >= PT_PICKUP_V0_ONSET_GYRO_NORM;
}

static bool detect_onset_lookahead(const struct pt_motion_engine *engine,
                                   uint64_t *onset_time_us,
                                   uint32_t *onset_sequence)
{
    uint16_t active = 0U;
    int first_active_from_newest = -1;

    if (engine->sample_count < PT_PICKUP_V0_ONSET_LOOKAHEAD_SAMPLES) {
        return false;
    }
    for (uint16_t i = 0; i < PT_PICKUP_V0_ONSET_LOOKAHEAD_SAMPLES; ++i) {
        const struct pt_motion_sample *sample = sample_from_newest(engine, i);
        if (!valid_sample(sample)) {
            return false;
        }
        if (is_active_sample(sample)) {
            active++;
            first_active_from_newest = (int)i;
        }
    }
    if (active < PT_PICKUP_V0_ONSET_MIN_ACTIVE_SAMPLES ||
        first_active_from_newest < 0) {
        return false;
    }
    {
        const struct pt_motion_sample *first =
            sample_from_newest(engine, (uint16_t)first_active_from_newest);
        *onset_time_us = first->source_time_us;
        *onset_sequence = first->sequence;
    }
    return true;
}

static void normalize3(float value[3])
{
    float norm = vec_norm3f(value[0], value[1], value[2]);
    if (norm <= 1.0e-6f) {
        return;
    }
    value[0] /= norm;
    value[1] /= norm;
    value[2] /= norm;
}

static void propagate_up(float up[3], const float gyro[3], float dt)
{
    float cross[3] = {
        gyro[1] * up[2] - gyro[2] * up[1],
        gyro[2] * up[0] - gyro[0] * up[2],
        gyro[0] * up[1] - gyro[1] * up[0],
    };
    up[0] -= cross[0] * dt;
    up[1] -= cross[1] * dt;
    up[2] -= cross[2] * dt;
    normalize3(up);
}

static bool compute_pickup_features(
    const struct pt_motion_engine *engine,
    uint64_t onset_time_us,
    float *positive_impulse,
    float *mean_gyro_norm,
    float *axis_consistency,
    bool *gyro_clipped)
{
    const int64_t impulse_start_us =
        (int64_t)onset_time_us +
        (int64_t)(PT_PICKUP_V0_IMPULSE_START_S * 1000000.0f);
    const int64_t impulse_end_us =
        (int64_t)onset_time_us +
        (int64_t)(PT_PICKUP_V0_IMPULSE_END_S * 1000000.0f);
    const int64_t gyro_start_us =
        (int64_t)onset_time_us +
        (int64_t)(PT_PICKUP_V0_GYRO_WINDOW_START_S * 1000000.0f);
    const int64_t gyro_end_us =
        (int64_t)onset_time_us +
        (int64_t)(PT_PICKUP_V0_GYRO_WINDOW_END_S * 1000000.0f);
    float up[3] = {engine->baseline_up[0], engine->baseline_up[1],
                   engine->baseline_up[2]};
    float impulse = 0.0f;
    float gyro_norm_sum = 0.0f;
    float gyro_vector_sum[3] = {0.0f, 0.0f, 0.0f};
    uint16_t gyro_count = 0U;
    uint16_t impulse_count = 0U;
    uint64_t previous_time_us = 0U;

    *gyro_clipped = false;
    if (!engine->baseline_ready || engine->sample_count < 2U) {
        return false;
    }
    normalize3(up);

    for (uint16_t i = 0; i < engine->sample_count; ++i) {
        const struct pt_motion_sample *sample = sample_from_oldest(engine, i);
        int64_t time_us = (int64_t)sample->source_time_us;
        float accel[3];
        float gyro[3];
        float gyro_norm;

        if (!valid_sample(sample)) {
            continue;
        }
        if (time_us < impulse_start_us) {
            continue;
        }
        if (time_us > gyro_end_us) {
            break;
        }
        for (size_t axis = 0; axis < 3; ++axis) {
            accel[axis] = sample->accel_micro_ms2[axis] / MICRO_SCALE;
            gyro[axis] = sample->gyro_micro_rads[axis] / MICRO_SCALE;
        }
        gyro_norm = vec_norm3f(gyro[0], gyro[1], gyro[2]);

        if (previous_time_us != 0U) {
            float dt = (float)(sample->source_time_us - previous_time_us) /
                       1000000.0f;
            if (dt > 0.0f && dt < 0.1f) {
                propagate_up(up, gyro, dt);
                if (time_us <= impulse_end_us) {
                    float vertical = accel[0] * up[0] + accel[1] * up[1] +
                                     accel[2] * up[2] -
                                     PT_PICKUP_V0_GRAVITY_MPS2;
                    if (vertical > 0.0f) {
                        impulse += vertical * dt;
                    }
                    impulse_count++;
                }
            }
        }
        previous_time_us = sample->source_time_us;

        if (time_us >= gyro_start_us && time_us <= gyro_end_us) {
            gyro_norm_sum += gyro_norm;
            for (size_t axis = 0; axis < 3; ++axis) {
                gyro_vector_sum[axis] += gyro[axis];
            }
            gyro_count++;
            *gyro_clipped |= sample->gyro_clipped;
        }
    }

    if (gyro_count < 40U || impulse_count < 20U) {
        return false;
    }
    *positive_impulse = impulse;
    *mean_gyro_norm = gyro_norm_sum / (float)gyro_count;
    if (*mean_gyro_norm <= 1.0e-6f) {
        *axis_consistency = 0.0f;
    } else {
        float mean_vector[3];
        for (size_t axis = 0; axis < 3; ++axis) {
            mean_vector[axis] = gyro_vector_sum[axis] / (float)gyro_count;
        }
        *axis_consistency = vec_norm3f(mean_vector[0], mean_vector[1],
                                       mean_vector[2]) /
                            *mean_gyro_norm;
    }
    return true;
}

static void fill_output(const struct pt_motion_engine *engine,
                        const struct pt_motion_sample *sample,
                        struct pt_motion_output *output,
                        uint16_t event_bits,
                        uint16_t confidence,
                        uint16_t quality_bits,
                        const struct pt_motion_features *features)
{
    memset(output, 0, sizeof(*output));
    output->state = engine->state;
    output->event_bits = event_bits;
    output->confidence_permille = confidence;
    output->quality_bits = quality_bits;
    output->source_sequence = sample->sequence;
    output->source_time_us = sample->source_time_us;
    output->model_hash32 = PT_PICKUP_V0_CONFIG_HASH32;
    output->tee_arm_epoch = engine->tee_arm_epoch;
    if (features != NULL) {
        output->features = *features;
    }
}

void pt_motion_engine_init(struct pt_motion_engine *engine)
{
    memset(engine, 0, sizeof(*engine));
    engine->state = PT_MOTION_UNKNOWN;
}

void pt_motion_engine_arm_from_tee(struct pt_motion_engine *engine)
{
    engine->write_index = 0U;
    engine->sample_count = 0U;
    engine->baseline_ready = false;
    engine->onset_candidate = false;
    engine->freefall_active = false;
    engine->state = PT_MOTION_UNKNOWN;
    engine->last_sequence = 0U;
    engine->last_time_us = 0U;
    engine->last_quality_bits = PT_QUALITY_BASELINE_UNREADY;
    engine->tee_arm_epoch++;
}

bool pt_motion_engine_push(struct pt_motion_engine *engine,
                           const struct pt_motion_sample *sample,
                           struct pt_motion_output *output)
{
    enum pt_motion_state previous_state = engine->state;
    uint16_t quality = PT_QUALITY_OK;
    uint16_t events = PT_EVENT_NONE;
    uint16_t confidence = 0U;
    struct pt_motion_features features = {0};
    float baseline_mean_accel[3] = {0.0f, 0.0f, 0.0f};
    bool stationary_window = false;
    bool stationary_now = false;
    bool rolling_now = false;
    bool rolling_clipped = false;
    bool active_now = false;
    float accel_norm;

    if (engine == NULL || sample == NULL || output == NULL) {
        return false;
    }

    if (engine->last_sequence != 0U &&
        (sample->sequence != engine->last_sequence + 1U ||
         sample->source_time_us <= engine->last_time_us ||
         sample->source_time_us - engine->last_time_us > SOURCE_GAP_MAX_US)) {
        quality |= PT_QUALITY_SEQUENCE_OR_TIME_GAP;
        engine->onset_candidate = false;
        engine->baseline_ready = false;
    }
    engine->last_sequence = sample->sequence;
    engine->last_time_us = sample->source_time_us;

    if (!valid_sample(sample)) {
        quality |= PT_QUALITY_SENSOR_INVALID;
    }
    if (sample->gyro_clipped) {
        quality |= PT_QUALITY_GYRO_CLIPPED;
    }

    append_sample(engine, sample);
    accel_norm = sample_accel_norm(sample);
    active_now = valid_sample(sample) && is_active_sample(sample);

    stationary_window = compute_stationary_window(
        engine,
        &features.baseline_accel_stdev_mps2,
        &features.baseline_gyro_rms_rads,
        baseline_mean_accel);
    if (stationary_window) {
        stationary_now =
            features.baseline_accel_stdev_mps2 <=
                PT_PICKUP_V0_BASELINE_ACCEL_STDEV_MAX &&
            features.baseline_gyro_rms_rads <=
                PT_PICKUP_V0_BASELINE_GYRO_RMS_MAX;
        if (stationary_now) {
            float norm = vec_norm3f(baseline_mean_accel[0],
                                    baseline_mean_accel[1],
                                    baseline_mean_accel[2]);
            if (norm > 1.0e-6f) {
                for (size_t axis = 0; axis < 3; ++axis) {
                    engine->baseline_up[axis] = baseline_mean_accel[axis] / norm;
                }
                engine->baseline_ready = true;
            }
        }
    }
    if (!engine->baseline_ready) {
        quality |= PT_QUALITY_BASELINE_UNREADY;
    }

    if (compute_gyro_shape_last(engine, ROLL_WINDOW_SAMPLES,
                                &features.rolling_mean_gyro_rads,
                                &features.rolling_axis_consistency,
                                &rolling_clipped)) {
        rolling_now =
            features.rolling_mean_gyro_rads >= ROLLING_GYRO_MIN_RADS &&
            features.rolling_axis_consistency >= ROLLING_AXIS_MIN;
        if (rolling_clipped) {
            quality |= PT_QUALITY_GYRO_CLIPPED;
        }
    }

    /* Simple freefall/landing candidate. This is generic evidence, not cup truth. */
    if (valid_sample(sample) && accel_norm <= FREEFALL_ACCEL_MAX_MPS2) {
        if (!engine->freefall_active) {
            engine->freefall_active = true;
            engine->freefall_start_us = sample->source_time_us;
        }
        engine->state = PT_MOTION_AIRBORNE;
        confidence = 900U;
    } else if (engine->freefall_active) {
        uint64_t elapsed = sample->source_time_us - engine->freefall_start_us;
        if (elapsed <= FREEFALL_LANDING_MAX_US &&
            accel_norm >= LANDING_ACCEL_MIN_MPS2) {
            events |= PT_EVENT_DROP_LANDING_CANDIDATE;
        }
        if (elapsed > FREEFALL_LANDING_MAX_US ||
            accel_norm >= LANDING_ACCEL_MIN_MPS2) {
            engine->freefall_active = false;
        }
    }

    /* Arm the stationary-start V0 transition only after a measured rest baseline. */
    if (!engine->onset_candidate && engine->baseline_ready &&
        (previous_state == PT_MOTION_STATIONARY || stationary_now)) {
        uint64_t onset_time_us;
        uint32_t onset_sequence;
        if (detect_onset_lookahead(engine, &onset_time_us, &onset_sequence)) {
            engine->onset_candidate = true;
            engine->onset_time_us = onset_time_us;
            engine->onset_sequence = onset_sequence;
            events |= PT_EVENT_MOTION_ONSET;
        }
    }

    if (engine->onset_candidate &&
        sample->source_time_us >= engine->onset_time_us + 1000000ULL) {
        bool pickup_clipped = false;
        if (compute_pickup_features(
                engine,
                engine->onset_time_us,
                &features.positive_vertical_impulse_mps,
                &features.pickup_mean_gyro_rads,
                &features.pickup_axis_consistency,
                &pickup_clipped)) {
            if (pickup_clipped) {
                quality |= PT_QUALITY_PICKUP_WINDOW_CLIPPED;
            } else if (features.positive_vertical_impulse_mps >
                           PT_PICKUP_V0_IMPULSE_MIN_MPS &&
                       features.pickup_mean_gyro_rads <
                           PT_PICKUP_V0_GYRO_MEAN_MAX_RADS &&
                       features.pickup_axis_consistency <
                           PT_PICKUP_V0_AXIS_CONSISTENCY_MAX) {
                engine->state = PT_MOTION_CARRIED;
                events |= PT_EVENT_PICKUP_SUSPECTED;
                confidence = 990U;
            }
        }
        engine->onset_candidate = false;
    }

    if (engine->state != PT_MOTION_CARRIED &&
        engine->state != PT_MOTION_AIRBORNE) {
        if (stationary_now) {
            engine->state = PT_MOTION_STATIONARY;
            confidence = 990U;
            if (previous_state == PT_MOTION_ROLLING ||
                previous_state == PT_MOTION_SETTLING) {
                events |= PT_EVENT_SETTLED;
            }
        } else if (rolling_now) {
            engine->state = PT_MOTION_ROLLING;
            confidence = features.rolling_axis_consistency >= 0.85f ? 960U : 880U;
            if (previous_state != PT_MOTION_ROLLING) {
                events |= PT_EVENT_ROLLING_START;
            }
        } else if (previous_state == PT_MOTION_ROLLING && active_now) {
            engine->state = PT_MOTION_SETTLING;
            confidence = 800U;
        } else if (previous_state == PT_MOTION_SETTLING && active_now) {
            engine->state = PT_MOTION_SETTLING;
            confidence = 760U;
        } else if (active_now && engine->onset_candidate) {
            engine->state = PT_MOTION_UNKNOWN;
            confidence = 0U;
        }
    } else if (engine->state == PT_MOTION_CARRIED && stationary_now) {
        engine->state = PT_MOTION_STATIONARY;
        confidence = 980U;
    }

    if ((quality & PT_QUALITY_SENSOR_INVALID) != 0U ||
        (quality & PT_QUALITY_SEQUENCE_OR_TIME_GAP) != 0U) {
        engine->state = PT_MOTION_UNKNOWN;
        confidence = 0U;
    }

    fill_output(engine, sample, output, events, confidence, quality, &features);
    {
        bool emit = engine->state != previous_state || events != PT_EVENT_NONE ||
                    quality != engine->last_quality_bits;
        engine->last_quality_bits = quality;
        return emit;
    }
}

const char *pt_motion_state_name(enum pt_motion_state state)
{
    switch (state) {
    case PT_MOTION_STATIONARY:
        return "STATIONARY";
    case PT_MOTION_ROLLING:
        return "ROLLING";
    case PT_MOTION_SETTLING:
        return "SETTLING";
    case PT_MOTION_CARRIED:
        return "CARRIED";
    case PT_MOTION_AIRBORNE:
        return "AIRBORNE";
    case PT_MOTION_UNKNOWN:
    default:
        return "UNKNOWN";
    }
}
