/*
 * Frozen Pickup V0 evaluation kernel shared by nRF54L15 firmware and native
 * parity tests. Results are research-only shadow evidence, never Gameplay
 * authority.
 */

#ifndef PUTTTRACK_PICKUP_SHADOW_V0_H_
#define PUTTTRACK_PICKUP_SHADOW_V0_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum pt_pickup_shadow_decision {
	PT_PICKUP_SHADOW_UNARMED = 0,
	PT_PICKUP_SHADOW_PENDING = 1,
	PT_PICKUP_SHADOW_SUSPECTED = 2,
	PT_PICKUP_SHADOW_NOT_PICKUP = 3,
	PT_PICKUP_SHADOW_UNKNOWN = 4,
};

enum pt_pickup_shadow_reason {
	PT_PICKUP_REASON_INSUFFICIENT_SAMPLES = (1U << 0),
	PT_PICKUP_REASON_SEQUENCE = (1U << 1),
	PT_PICKUP_REASON_TIME = (1U << 2),
	PT_PICKUP_REASON_SENSOR_INVALID = (1U << 3),
	PT_PICKUP_REASON_SOURCE_RATE = (1U << 4),
	PT_PICKUP_REASON_BASELINE_SAMPLES = (1U << 5),
	PT_PICKUP_REASON_BASELINE_NOT_STATIONARY = (1U << 6),
	PT_PICKUP_REASON_FEATURE_WINDOW = (1U << 7),
	PT_PICKUP_REASON_GYRO_CLIPPING = (1U << 8),
	PT_PICKUP_REASON_POSITIVE_IMPULSE = (1U << 9),
	PT_PICKUP_REASON_MEAN_GYRO = (1U << 10),
	PT_PICKUP_REASON_AXIS_CONSISTENCY = (1U << 11),
	PT_PICKUP_REASON_NO_MOTION_ONSET = (1U << 12),
};

#define PT_PICKUP_RULE_POSITIVE_IMPULSE (1U << 0)
#define PT_PICKUP_RULE_MEAN_GYRO (1U << 1)
#define PT_PICKUP_RULE_AXIS_CONSISTENCY (1U << 2)

#define PT_PICKUP_SHADOW_DETECTOR_ID "pickup_detector_v0_stationary_start"
#define PT_PICKUP_SHADOW_DETECTOR_SHA256 \
	"62c82c1a313f70912a5bb6c2f53c635fe179c537cdb3738dbc5d2a347050c8ad"

struct pt_pickup_sample {
	uint32_t sequence;
	uint64_t source_monotonic_us;
	int32_t accel_micro_ms2[3];
	int32_t gyro_micro_rads[3];
	uint32_t sensor_error_bits;
	uint8_t adxl367_valid;
	uint8_t bmi270_valid;
	uint8_t reserved[2];
};

struct pt_pickup_shadow_result {
	uint32_t decision;
	uint32_t reason_mask;
	uint32_t rule_pass_mask;
	uint32_t baseline_sample_count;
	uint32_t feature_sample_count_gyro;
	uint32_t feature_sample_count_impulse;
	uint32_t gyro_clip_samples;
	uint64_t onset_source_monotonic_us;
	double source_rate_hz;
	double baseline_duration_s;
	double baseline_accel_norm_stdev_mps2;
	double baseline_gyro_norm_rms_rads;
	double onset_offset_from_go_s;
	double positive_vertical_impulse_mps;
	double mean_gyro_norm_1s_rads;
	double gyro_axis_consistency_1s;
};

/* Minimum time after GO before a no-onset result is final in live mode. */
#define PT_PICKUP_SHADOW_LIVE_OBSERVATION_US 3000000ULL

void pt_pickup_shadow_evaluate(const struct pt_pickup_sample *samples,
			       size_t sample_count, uint64_t go_us,
			       bool live_mode,
			       struct pt_pickup_shadow_result *result);

const char *pt_pickup_shadow_decision_name(uint32_t decision);

#ifdef __cplusplus
}
#endif

#endif /* PUTTTRACK_PICKUP_SHADOW_V0_H_ */
