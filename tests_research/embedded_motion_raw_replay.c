#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "motion_engine.h"

int main(void)
{
    struct pt_motion_engine engine;
    struct pt_motion_output output = {0};
    struct pt_motion_sample sample;
    char line[512];
    uint32_t samples = 0U;
    uint32_t seen_state_mask = 0U;
    uint32_t quality_or = 0U;
    uint32_t pickup_events = 0U;
    uint32_t rolling_start_events = 0U;
    uint32_t settled_events = 0U;
    uint32_t landing_events = 0U;
    uint32_t state_changes = 0U;
    uint32_t maximum_confidence = 0U;
    enum pt_motion_state previous_state = PT_MOTION_UNKNOWN;

    pt_motion_engine_init(&engine);
    while (fgets(line, sizeof(line), stdin) != NULL) {
        int valid = 0;
        int clipped = 0;
        int fields = sscanf(
            line,
            "%" SCNu32 ",%" SCNu64 ",%" SCNd32 ",%" SCNd32
            ",%" SCNd32 ",%" SCNd32 ",%" SCNd32 ",%" SCNd32
            ",%" SCNu32 ",%d,%d",
            &sample.sequence,
            &sample.source_time_us,
            &sample.accel_micro_ms2[0],
            &sample.accel_micro_ms2[1],
            &sample.accel_micro_ms2[2],
            &sample.gyro_micro_rads[0],
            &sample.gyro_micro_rads[1],
            &sample.gyro_micro_rads[2],
            &sample.sensor_error_bits,
            &valid,
            &clipped);
        if (fields != 11) {
            fprintf(stderr, "invalid replay row: %s", line);
            return 2;
        }
        sample.bmi270_valid = valid != 0;
        sample.gyro_clipped = clipped != 0;
        (void)pt_motion_engine_push(&engine, &sample, &output);

        if ((uint32_t)output.state < 32U) {
            seen_state_mask |= 1U << (uint32_t)output.state;
        }
        if (samples > 0U && output.state != previous_state) {
            state_changes++;
        }
        previous_state = output.state;
        quality_or |= output.quality_bits;
        pickup_events +=
            (output.event_bits & PT_EVENT_PICKUP_SUSPECTED) != 0U ? 1U : 0U;
        rolling_start_events +=
            (output.event_bits & PT_EVENT_ROLLING_START) != 0U ? 1U : 0U;
        settled_events +=
            (output.event_bits & PT_EVENT_SETTLED) != 0U ? 1U : 0U;
        landing_events +=
            (output.event_bits & PT_EVENT_DROP_LANDING_CANDIDATE) != 0U ? 1U : 0U;
        if (output.confidence_permille > maximum_confidence) {
            maximum_confidence = output.confidence_permille;
        }
        samples++;
    }

    printf(
        "{\"samples\":%" PRIu32
        ",\"context_bytes\":%zu"
        ",\"final_state\":\"%s\""
        ",\"final_state_code\":%u"
        ",\"seen_state_mask\":%" PRIu32
        ",\"state_changes\":%" PRIu32
        ",\"quality_or\":%" PRIu32
        ",\"pickup_events\":%" PRIu32
        ",\"rolling_start_events\":%" PRIu32
        ",\"settled_events\":%" PRIu32
        ",\"landing_events\":%" PRIu32
        ",\"maximum_confidence\":%" PRIu32 "}\n",
        samples,
        sizeof(engine),
        pt_motion_state_name(output.state),
        (unsigned int)output.state,
        seen_state_mask,
        state_changes,
        quality_or,
        pickup_events,
        rolling_start_events,
        settled_events,
        landing_events,
        maximum_confidence);
    return 0;
}
