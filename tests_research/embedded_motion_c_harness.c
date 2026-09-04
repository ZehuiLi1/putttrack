#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "motion_engine.h"

#define G_MICRO 9806650

static void push_sample(struct pt_motion_engine *engine,
                        uint32_t seq,
                        int32_t ax, int32_t ay, int32_t az,
                        int32_t gx, int32_t gy, int32_t gz,
                        struct pt_motion_output *out)
{
    struct pt_motion_sample sample = {
        .sequence = seq,
        .source_time_us = (uint64_t)seq * 20000ULL,
        .accel_micro_ms2 = {ax, ay, az},
        .gyro_micro_rads = {gx, gy, gz},
        .sensor_error_bits = 0U,
        .bmi270_valid = true,
        .gyro_clipped = false,
    };
    (void)pt_motion_engine_push(engine, &sample, out);
}

static void test_stationary_then_roll_then_settle(void)
{
    struct pt_motion_engine engine;
    struct pt_motion_output out;
    uint32_t seq = 1U;

    pt_motion_engine_init(&engine);
    for (int i = 0; i < 60; ++i, ++seq) {
        push_sample(&engine, seq, 0, 0, G_MICRO, 0, 0, 0, &out);
    }
    assert(out.state == PT_MOTION_STATIONARY);
    assert(engine.baseline_ready);

    for (int i = 0; i < 30; ++i, ++seq) {
        push_sample(&engine, seq, 0, 0, G_MICRO, 5000000, 0, 0, &out);
    }
    assert(out.state == PT_MOTION_ROLLING);

    for (int i = 0; i < 10; ++i, ++seq) {
        push_sample(&engine, seq, 0, 0, G_MICRO, 800000, 0, 0, &out);
    }
    assert(out.state == PT_MOTION_SETTLING || out.state == PT_MOTION_ROLLING);

    for (int i = 0; i < 60; ++i, ++seq) {
        push_sample(&engine, seq, 0, 0, G_MICRO, 0, 0, 0, &out);
    }
    assert(out.state == PT_MOTION_STATIONARY);
}

static void test_stationary_pickup_v0(void)
{
    struct pt_motion_engine engine;
    struct pt_motion_output out;
    uint32_t seq = 1U;
    bool saw_pickup = false;

    pt_motion_engine_init(&engine);
    for (int i = 0; i < 60; ++i, ++seq) {
        push_sample(&engine, seq, 0, 0, G_MICRO, 0, 0, 0, &out);
    }
    assert(out.state == PT_MOTION_STATIONARY);

    /* Upward acceleration with alternating multi-axis hand rotation. */
    for (int i = 0; i < 70; ++i, ++seq) {
        int phase = i % 4;
        int32_t gx = 0, gy = 0;
        if (phase == 0) gx = 3000000;
        if (phase == 1) gy = 3000000;
        if (phase == 2) gx = -3000000;
        if (phase == 3) gy = -3000000;
        push_sample(&engine, seq, 0, 0, 12500000, gx, gy, 0, &out);
        if ((out.event_bits & PT_EVENT_PICKUP_SUSPECTED) != 0U) {
            saw_pickup = true;
        }
    }
    assert(saw_pickup);
    assert(out.state == PT_MOTION_CARRIED || out.state == PT_MOTION_UNKNOWN);
}

static void test_gap_fails_closed(void)
{
    struct pt_motion_engine engine;
    struct pt_motion_output out;

    pt_motion_engine_init(&engine);
    push_sample(&engine, 1U, 0, 0, G_MICRO, 0, 0, 0, &out);
    push_sample(&engine, 3U, 0, 0, G_MICRO, 0, 0, 0, &out);
    assert(out.state == PT_MOTION_UNKNOWN);
    assert((out.quality_bits & PT_QUALITY_SEQUENCE_OR_TIME_GAP) != 0U);
}

int main(void)
{
    test_stationary_then_roll_then_settle();
    test_stationary_pickup_v0();
    test_gap_fails_closed();
    puts("PASS: embedded motion C harness");
    return 0;
}
