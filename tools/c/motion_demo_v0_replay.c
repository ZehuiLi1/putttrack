#include "motion_demo_v0.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    struct motion_demo_v0 context;
    struct motion_demo_v0_snapshot snapshot;
    char line[512];
    uint32_t seen_state_mask = 0U;
    uint32_t pushed = 0U;

    motion_demo_v0_init(&context);
    while (fgets(line, sizeof(line), stdin) != NULL) {
        struct motion_demo_v0_sample sample = {0};
        int valid = 0;
        int fields = sscanf(
            line,
            "%" SCNu32 ",%" SCNu64 ",%" SCNd32 ",%" SCNd32
            ",%" SCNd32 ",%" SCNd32 ",%" SCNd32 ",%" SCNd32
            ",%d,%" SCNu32,
            &sample.sequence,
            &sample.source_monotonic_us,
            &sample.accel_micro_ms2[0],
            &sample.accel_micro_ms2[1],
            &sample.accel_micro_ms2[2],
            &sample.gyro_micro_rads[0],
            &sample.gyro_micro_rads[1],
            &sample.gyro_micro_rads[2],
            &valid,
            &sample.sensor_error_bits);
        if (fields != 10) {
            fprintf(stderr, "invalid replay row: %s", line);
            return 2;
        }
        sample.bmi270_valid = valid != 0;
        (void)motion_demo_v0_push(&context, &sample);
        motion_demo_v0_get_snapshot(&context, &snapshot);
        if ((uint32_t)snapshot.state < 32U) {
            seen_state_mask |= 1U << (uint32_t)snapshot.state;
        }
        pushed++;
    }

    motion_demo_v0_get_snapshot(&context, &snapshot);
    printf(
        "{\"samples\":%" PRIu32
        ",\"context_bytes\":%zu"
        ",\"state\":\"%s\",\"state_code\":%u"
        ",\"event\":\"%s\",\"event_count\":%" PRIu32
        ",\"quality_flags\":%" PRIu32
        ",\"transition_count\":%" PRIu32
        ",\"seen_state_mask\":%" PRIu32
        ",\"impulse_milli_mps\":%" PRId32
        ",\"gyro_mean_milli_rads\":%" PRId32
        ",\"axis_milli\":%" PRId32 "}\n",
        pushed,
        sizeof(context),
        motion_demo_v0_state_name(snapshot.state),
        (unsigned int)snapshot.state,
        motion_demo_v0_event_name(snapshot.last_event),
        snapshot.event_count,
        snapshot.quality_flags,
        snapshot.state_transition_count,
        seen_state_mask,
        snapshot.vertical_impulse_milli_mps,
        snapshot.gyro_mean_milli_rads,
        snapshot.axis_consistency_milli);
    return 0;
}
