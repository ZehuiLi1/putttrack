#ifndef PUTTTRACK_PICKUP_RULE_BOUND_H
#define PUTTTRACK_PICKUP_RULE_BOUND_H

#include <stdbool.h>
#include <stdint.h>

/*
 * Research primitive only. This does not alter frozen Pickup V0 and has no
 * Gameplay/scoring authority.
 *
 * The current stationary-start Pickup V0 requires mean_gyro_norm < 10 rad/s.
 * If k of N samples have at least one gyro axis at the BMI270 clipping boundary
 * (34.208453 rad/s), then mean_gyro_norm >= k/N * 34.208453 rad/s.
 *
 * REJECTED therefore means only that the existing mean-gyro predicate cannot
 * hold for this complete, valid window. It does NOT mean physical pickup is
 * impossible and does NOT classify the motion as rolling.
 *
 * Caller responsibilities before invoking:
 * - validated identity / device / boot context;
 * - valid sequence and monotonic time continuity;
 * - valid sensor health;
 * - complete feature window and expected sampling definition;
 * - stationary-start context;
 * - clipping count uses the exact configured per-sample definition.
 */

typedef enum {
    PT_BOUND_UNAVAILABLE = 0,
    PT_BOUND_NO_CONCLUSION = 1,
    PT_PICKUP_RULE_REJECTED = 2
} pt_pickup_bound_result;

static inline pt_pickup_bound_result pt_pickup_rule_bound(
    bool window_valid,
    uint32_t sample_count,
    uint32_t clipped_count)
{
    if (!window_valid || sample_count == 0U || clipped_count > sample_count) {
        return PT_BOUND_UNAVAILABLE;
    }

    /*
     * Fixed-point form of:
     *   clipped_count / sample_count * 34.208453 >= 10.0
     *
     * Strict Pickup V0 predicate is '< 10', so equality rejects it.
     * uint64_t avoids intermediate overflow.
     */
    if ((uint64_t)clipped_count * UINT64_C(34208453) >=
        (uint64_t)sample_count * UINT64_C(10000000)) {
        return PT_PICKUP_RULE_REJECTED;
    }

    return PT_BOUND_NO_CONCLUSION;
}

#endif /* PUTTTRACK_PICKUP_RULE_BOUND_H */
