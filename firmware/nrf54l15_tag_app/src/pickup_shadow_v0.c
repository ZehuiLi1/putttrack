#include "pickup_shadow_v0.h"

#include <float.h>
#include <math.h>
#include <string.h>

#define MICRO 1000000.0
#define EXPECTED_RATE_HZ 50.0
#define RATE_TOLERANCE_FRACTION 0.10
#define GRAVITY_MPS2 9.80665
#define BASELINE_WINDOW_US 1000000ULL
#define BASELINE_MINIMUM_DURATION_S 0.9
#define BASELINE_MINIMUM_SAMPLES 40U
#define BASELINE_MAX_ACCEL_SD_MPS2 0.15
#define BASELINE_MAX_GYRO_RMS_RADS 0.08
#define ONSET_SEARCH_DELAY_US 500000ULL
#define ONSET_LOOKAHEAD_SAMPLES 10U
#define ONSET_MINIMUM_ACTIVE_SAMPLES 6U
#define ONSET_ACCEL_DEVIATION_MPS2 0.5
#define ONSET_GYRO_RADS 0.25
#define IMPULSE_START_BEFORE_ONSET_US 100000ULL
#define IMPULSE_END_AFTER_ONSET_US 500000ULL
#define GYRO_END_AFTER_ONSET_US 1000000ULL
#define REQUIRED_IMPULSE_SAMPLES 24U
#define REQUIRED_GYRO_SAMPLES 40U
#define GYRO_CLIP_MICRO_RADS 34208453
#define MINIMUM_POSITIVE_IMPULSE_MPS 0.5
#define MAXIMUM_MEAN_GYRO_RADS 10.0
#define MAXIMUM_AXIS_CONSISTENCY 0.75

static double vector_norm_micro(const int32_t vector[3])
{
	double x = (double)vector[0] / MICRO;
	double y = (double)vector[1] / MICRO;
	double z = (double)vector[2] / MICRO;

	return sqrt(x * x + y * y + z * z);
}

static double vector_norm(const double vector[3])
{
	return sqrt(vector[0] * vector[0] + vector[1] * vector[1] +
		    vector[2] * vector[2]);
}

static double dot_accel_up(const int32_t accel[3], const double up[3])
{
	return ((double)accel[0] / MICRO) * up[0] +
	       ((double)accel[1] / MICRO) * up[1] +
	       ((double)accel[2] / MICRO) * up[2];
}

static void normalize(double vector[3])
{
	double magnitude = vector_norm(vector);

	if (magnitude <= DBL_EPSILON) {
		return;
	}
	for (size_t axis = 0U; axis < 3U; axis++) {
		vector[axis] /= magnitude;
	}
}

static void initialize_result(struct pt_pickup_shadow_result *result)
{
	memset(result, 0, sizeof(*result));
	result->decision = PT_PICKUP_SHADOW_UNKNOWN;
	result->onset_offset_from_go_s = -1.0;
	result->positive_vertical_impulse_mps = -1.0;
	result->mean_gyro_norm_1s_rads = -1.0;
	result->gyro_axis_consistency_1s = -1.0;
}

static bool sample_is_active(const struct pt_pickup_sample *sample)
{
	double accel_deviation = fabs(vector_norm_micro(sample->accel_micro_ms2) -
				      GRAVITY_MPS2);
	double gyro_norm = vector_norm_micro(sample->gyro_micro_rads);

	return accel_deviation >= ONSET_ACCEL_DEVIATION_MPS2 ||
	       gyro_norm >= ONSET_GYRO_RADS;
}

static size_t find_onset(const struct pt_pickup_sample *samples,
			 size_t sample_count, uint64_t go_us)
{
	size_t first = sample_count;

	for (size_t index = 0U; index < sample_count; index++) {
		if (samples[index].source_monotonic_us >=
		    go_us + ONSET_SEARCH_DELAY_US) {
			first = index;
			break;
		}
	}
	for (size_t index = first;
	     index < sample_count && sample_count - index >= ONSET_LOOKAHEAD_SAMPLES;
	     index++) {
		size_t active = 0U;

		for (size_t offset = 0U; offset < ONSET_LOOKAHEAD_SAMPLES; offset++) {
			if (sample_is_active(&samples[index + offset])) {
				active++;
			}
		}
		if (active >= ONSET_MINIMUM_ACTIVE_SAMPLES) {
			return index;
		}
	}
	return sample_count;
}

void pt_pickup_shadow_evaluate(const struct pt_pickup_sample *samples,
			       size_t sample_count, uint64_t go_us,
			       bool live_mode,
			       struct pt_pickup_shadow_result *result)
{
	uint32_t structural_reasons = 0U;
	uint64_t baseline_start_us;
	size_t baseline_start = sample_count;
	size_t baseline_end = sample_count;
	size_t onset_index;
	double duration_s;
	double accel_sum = 0.0;
	double accel_square_sum = 0.0;
	double gyro_square_sum = 0.0;
	double initial_up[3] = {0.0, 0.0, 0.0};

	initialize_result(result);
	if (samples == NULL || sample_count < 2U || go_us == 0U) {
		result->reason_mask = PT_PICKUP_REASON_INSUFFICIENT_SAMPLES;
		return;
	}

	for (size_t index = 1U; index < sample_count; index++) {
		if (samples[index].sequence != samples[index - 1U].sequence + 1U) {
			structural_reasons |= PT_PICKUP_REASON_SEQUENCE;
		}
		if (samples[index].source_monotonic_us <=
		    samples[index - 1U].source_monotonic_us) {
			structural_reasons |= PT_PICKUP_REASON_TIME;
		}
	}
	for (size_t index = 0U; index < sample_count; index++) {
		if (samples[index].adxl367_valid == 0U ||
		    samples[index].bmi270_valid == 0U ||
		    samples[index].sensor_error_bits != 0U) {
			structural_reasons |= PT_PICKUP_REASON_SENSOR_INVALID;
		}
	}
	duration_s = (samples[sample_count - 1U].source_monotonic_us -
		      samples[0].source_monotonic_us) / MICRO;
	if (duration_s > 0.0) {
		result->source_rate_hz = (sample_count - 1U) / duration_s;
	}
	if (result->source_rate_hz <= 0.0 ||
	    fabs(result->source_rate_hz - EXPECTED_RATE_HZ) >
		EXPECTED_RATE_HZ * RATE_TOLERANCE_FRACTION) {
		structural_reasons |= PT_PICKUP_REASON_SOURCE_RATE;
	}
	if (structural_reasons != 0U) {
		result->reason_mask = structural_reasons;
		return;
	}

	baseline_start_us = go_us > BASELINE_WINDOW_US ?
		go_us - BASELINE_WINDOW_US : 0U;
	for (size_t index = 0U; index < sample_count; index++) {
		uint64_t timestamp = samples[index].source_monotonic_us;

		if (timestamp >= baseline_start_us && timestamp < go_us) {
			if (baseline_start == sample_count) {
				baseline_start = index;
			}
			baseline_end = index + 1U;
		}
	}
	if (baseline_start == sample_count) {
		result->reason_mask = PT_PICKUP_REASON_BASELINE_SAMPLES;
		return;
	}
	result->baseline_sample_count = (uint32_t)(baseline_end - baseline_start);
	if (result->baseline_sample_count < BASELINE_MINIMUM_SAMPLES) {
		result->reason_mask = PT_PICKUP_REASON_BASELINE_SAMPLES;
		return;
	}
	result->baseline_duration_s =
		(samples[baseline_end - 1U].source_monotonic_us -
		 samples[baseline_start].source_monotonic_us) / MICRO;
	for (size_t index = baseline_start; index < baseline_end; index++) {
		double accel_norm = vector_norm_micro(samples[index].accel_micro_ms2);
		double gyro_norm = vector_norm_micro(samples[index].gyro_micro_rads);

		accel_sum += accel_norm;
		accel_square_sum += accel_norm * accel_norm;
		gyro_square_sum += gyro_norm * gyro_norm;
		for (size_t axis = 0U; axis < 3U; axis++) {
			initial_up[axis] +=
				(double)samples[index].accel_micro_ms2[axis] / MICRO;
		}
	}
	{
		double count = (double)result->baseline_sample_count;
		double mean = accel_sum / count;
		double variance = accel_square_sum / count - mean * mean;

		result->baseline_accel_norm_stdev_mps2 =
			sqrt(variance > 0.0 ? variance : 0.0);
		result->baseline_gyro_norm_rms_rads = sqrt(gyro_square_sum / count);
		for (size_t axis = 0U; axis < 3U; axis++) {
			initial_up[axis] /= count;
		}
	}
	if (result->baseline_duration_s < BASELINE_MINIMUM_DURATION_S ||
	    result->baseline_accel_norm_stdev_mps2 >
		BASELINE_MAX_ACCEL_SD_MPS2 ||
	    result->baseline_gyro_norm_rms_rads > BASELINE_MAX_GYRO_RMS_RADS ||
	    vector_norm(initial_up) <= DBL_EPSILON) {
		result->reason_mask = PT_PICKUP_REASON_BASELINE_NOT_STATIONARY;
		return;
	}

	onset_index = find_onset(samples, sample_count, go_us);
	if (onset_index == sample_count) {
		if (live_mode && samples[sample_count - 1U].source_monotonic_us <
				 go_us + PT_PICKUP_SHADOW_LIVE_OBSERVATION_US) {
			result->decision = PT_PICKUP_SHADOW_PENDING;
			return;
		}
		result->decision = PT_PICKUP_SHADOW_NOT_PICKUP;
		result->reason_mask = PT_PICKUP_REASON_NO_MOTION_ONSET;
		return;
	}

	{
		uint64_t onset_us = samples[onset_index].source_monotonic_us;
		uint64_t impulse_start_us = onset_us - IMPULSE_START_BEFORE_ONSET_US;
		uint64_t impulse_end_us = onset_us + IMPULSE_END_AFTER_ONSET_US;
		uint64_t gyro_end_us = onset_us + GYRO_END_AFTER_ONSET_US;
		double up[3] = {initial_up[0], initial_up[1], initial_up[2]};
		double gyro_sum[3] = {0.0, 0.0, 0.0};
		double gyro_norm_sum = 0.0;
		uint64_t previous_propagation_us = 0U;
		uint64_t previous_impulse_us = 0U;
		int32_t previous_gyro[3] = {0, 0, 0};

		result->onset_source_monotonic_us = onset_us;
		result->onset_offset_from_go_s = (onset_us - go_us) / MICRO;
		if (live_mode && samples[sample_count - 1U].source_monotonic_us <
				 gyro_end_us) {
			result->decision = PT_PICKUP_SHADOW_PENDING;
			return;
		}
		normalize(up);
		result->positive_vertical_impulse_mps = 0.0;
		for (size_t index = 0U; index < sample_count; index++) {
			const struct pt_pickup_sample *sample = &samples[index];
			uint64_t timestamp = sample->source_monotonic_us;

			if (timestamp < go_us || timestamp >= gyro_end_us + 20000ULL) {
				continue;
			}
			if (previous_propagation_us != 0U) {
				double dt = (timestamp - previous_propagation_us) / MICRO;
				double gyro[3] = {
					(double)previous_gyro[0] / MICRO,
					(double)previous_gyro[1] / MICRO,
					(double)previous_gyro[2] / MICRO,
				};
				double derivative[3] = {
					gyro[1] * up[2] - gyro[2] * up[1],
					gyro[2] * up[0] - gyro[0] * up[2],
					gyro[0] * up[1] - gyro[1] * up[0],
				};

				for (size_t axis = 0U; axis < 3U; axis++) {
					up[axis] -= derivative[axis] * dt;
				}
				normalize(up);
			}
			previous_propagation_us = timestamp;
			memcpy(previous_gyro, sample->gyro_micro_rads,
			       sizeof(previous_gyro));

			if (timestamp >= impulse_start_us && timestamp < impulse_end_us) {
				result->feature_sample_count_impulse++;
				if (previous_impulse_us != 0U) {
					double dt = (timestamp - previous_impulse_us) / MICRO;
					double vertical_dynamic =
						dot_accel_up(sample->accel_micro_ms2, up) -
						GRAVITY_MPS2;

					if (vertical_dynamic > 0.0) {
						result->positive_vertical_impulse_mps +=
							vertical_dynamic * dt;
					}
				}
				previous_impulse_us = timestamp;
			}
			if (timestamp >= onset_us && timestamp < gyro_end_us) {
				double norm = vector_norm_micro(sample->gyro_micro_rads);

				result->feature_sample_count_gyro++;
				gyro_norm_sum += norm;
				for (size_t axis = 0U; axis < 3U; axis++) {
					int64_t value = sample->gyro_micro_rads[axis];

					gyro_sum[axis] += (double)value / MICRO;
					if (value < 0) {
						value = -value;
					}
					if (value >= GYRO_CLIP_MICRO_RADS) {
						result->gyro_clip_samples++;
						break;
					}
				}
			}
		}
		if (result->feature_sample_count_impulse < REQUIRED_IMPULSE_SAMPLES ||
		    result->feature_sample_count_gyro < REQUIRED_GYRO_SAMPLES) {
			result->decision = live_mode ? PT_PICKUP_SHADOW_PENDING :
				PT_PICKUP_SHADOW_UNKNOWN;
			if (!live_mode) {
				result->reason_mask = PT_PICKUP_REASON_FEATURE_WINDOW;
			}
			return;
		}
		if (result->gyro_clip_samples != 0U) {
			result->decision = PT_PICKUP_SHADOW_UNKNOWN;
			result->reason_mask = PT_PICKUP_REASON_GYRO_CLIPPING;
			result->positive_vertical_impulse_mps = -1.0;
			return;
		}
		result->mean_gyro_norm_1s_rads =
			gyro_norm_sum / result->feature_sample_count_gyro;
		result->gyro_axis_consistency_1s = gyro_norm_sum > DBL_EPSILON ?
			vector_norm(gyro_sum) / gyro_norm_sum : 0.0;
	}

	if (result->positive_vertical_impulse_mps > MINIMUM_POSITIVE_IMPULSE_MPS) {
		result->rule_pass_mask |= PT_PICKUP_RULE_POSITIVE_IMPULSE;
	} else {
		result->reason_mask |= PT_PICKUP_REASON_POSITIVE_IMPULSE;
	}
	if (result->mean_gyro_norm_1s_rads < MAXIMUM_MEAN_GYRO_RADS) {
		result->rule_pass_mask |= PT_PICKUP_RULE_MEAN_GYRO;
	} else {
		result->reason_mask |= PT_PICKUP_REASON_MEAN_GYRO;
	}
	if (result->gyro_axis_consistency_1s < MAXIMUM_AXIS_CONSISTENCY) {
		result->rule_pass_mask |= PT_PICKUP_RULE_AXIS_CONSISTENCY;
	} else {
		result->reason_mask |= PT_PICKUP_REASON_AXIS_CONSISTENCY;
	}
	result->decision = result->rule_pass_mask ==
		(PT_PICKUP_RULE_POSITIVE_IMPULSE | PT_PICKUP_RULE_MEAN_GYRO |
		 PT_PICKUP_RULE_AXIS_CONSISTENCY) ?
		PT_PICKUP_SHADOW_SUSPECTED : PT_PICKUP_SHADOW_NOT_PICKUP;
}

const char *pt_pickup_shadow_decision_name(uint32_t decision)
{
	switch (decision) {
	case PT_PICKUP_SHADOW_PENDING:
		return "PENDING";
	case PT_PICKUP_SHADOW_SUSPECTED:
		return "PICKUP_SUSPECTED";
	case PT_PICKUP_SHADOW_NOT_PICKUP:
		return "NOT_PICKUP";
	case PT_PICKUP_SHADOW_UNKNOWN:
		return "UNKNOWN";
	case PT_PICKUP_SHADOW_UNARMED:
	default:
		return "UNARMED";
	}
}
