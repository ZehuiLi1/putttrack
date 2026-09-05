/*
 * PuttTrack nRF54L15 Tag firmware.
 *
 * The Ball reports identity, health and generic raw motion. It deliberately
 * contains no player, hole, score or authoritative gameplay logic.
 */

#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/hci.h>
#include <zephyr/device.h>
#include <zephyr/drivers/fuel_gauge.h>
#include <zephyr/drivers/hwinfo.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/linker/section_tags.h>
#include <zephyr/mgmt/mcumgr/mgmt/handlers.h>
#include <zephyr/mgmt/mcumgr/mgmt/mgmt.h>
#include <zephyr/mgmt/mcumgr/smp/smp.h>
#include <zephyr/mgmt/mcumgr/transport/smp_bt.h>
#include <zephyr/pm/device.h>
#include <zephyr/random/random.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/reboot.h>
#include <zephyr/sys/util.h>
#include <zcbor_encode.h>

#if defined(CONFIG_PUTTTRACK_MOTION_DEMO_V0)
#include "motion_demo_v0.h"
#endif
#if defined(CONFIG_PUTTTRACK_STROKE_PICKUP_V1)
#include "stroke_pickup_v1.h"
#endif

#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
#include <hal/nrf_nfct.h>
#include <nfc_t2t_lib.h>
#include <nfc/ndef/uri_msg.h>
#endif

#if defined(CONFIG_PUTTTRACK_NFC_SYSTEM_OFF_TEST)
#include <zephyr/sys/poweroff.h>
#include <nrfx.h>
#include <hal/nrf_power.h>
#if !NRF_POWER_HAS_RESETREAS
#include <hal/nrf_reset.h>
#endif
#endif

#define PUTTTRACK_PROTOCOL_VERSION 1U
#if defined(CONFIG_PUTTTRACK_STROKE_PICKUP_V1)
#define PUTTTRACK_FIRMWARE_VERSION "0.1.19"
#else
#define PUTTTRACK_FIRMWARE_VERSION "0.1.18"
#endif

#define PUTTTRACK_MGMT_GROUP_ID 64U
#define PUTTTRACK_MGMT_ID_STATUS 0U
#define PUTTTRACK_MGMT_ID_MOTION 1U
#define PUTTTRACK_MGMT_ID_WINDOW 2U
#define PUTTTRACK_MGMT_ID_FREEZE_HISTORY 3U
#define PUTTTRACK_MGMT_ID_FROZEN_CHUNK_BASE 4U
#define PUTTTRACK_MGMT_ID_POWER_AUTO 20U
#define PUTTTRACK_MGMT_ID_POWER_RESEARCH 21U
#define PUTTTRACK_MGMT_ID_POWER_IDLE 22U
#define PUTTTRACK_MGMT_ID_ENTER_SYSTEM_OFF 23U
#define PUTTTRACK_MGMT_ID_MOTION_DEMO 24U
#define PUTTTRACK_MGMT_ID_STROKE_PICKUP 25U
#define PUTTTRACK_MGMT_ID_SHADOW_NEW_TRIAL 26U

#define STATUS_PACKET_SIZE 64U
#define MOTION_PACKET_SIZE 56U
#define MOTION_WINDOW_SAMPLES 64U
#define MOTION_HISTORY_SAMPLES 1024U
#define MOTION_FROZEN_CHUNKS (MOTION_HISTORY_SAMPLES / MOTION_WINDOW_SAMPLES)
#define MOTION_WINDOW_BYTES (MOTION_PACKET_SIZE * MOTION_WINDOW_SAMPLES)
#define MOTION_WINDOW_HEX_BYTES (MOTION_WINDOW_BYTES * 2U)

#define MOTION_STREAM_RATE_HZ 50U
#define ADXL367_ODR_HZ 100U
#define ADXL367_RANGE_G 2U
#define BMI270_ACCEL_ODR_HZ 100U
#define BMI270_ACCEL_RANGE_G 16U
#define BMI270_GYRO_ODR_HZ 100U
#define BMI270_GYRO_RANGE_DPS 2000U

#define IDLE_ADXL367_ODR_HZ 12U
#define IDLE_WAKE_SAMPLE_PERIOD_MS 160U
#define IDLE_ACTIVITY_REFERENCE_SETTLE_MS 160U
#define AUTO_IDLE_TIMEOUT_MS 30000U
#define IDLE_WAKE_DELTA_MICRO_MS2 500000
/*
 * Every recorded stationary data set stays below 0.3 m/s^2 sample-to-sample,
 * including the CR2032/SWD diagnostic that exposed sporadic 0.182 m/s^2
 * changes. Real handling and pickup records exceed this threshold repeatedly;
 * gyro activity remains an independent keep-awake condition.
 */
#define ACTIVE_DELTA_MICRO_MS2 300000
#define ACTIVE_GYRO_MICRO_RADS 80000
#define IDLE_WAKE_REQUIRED_SAMPLES 2U
#define SENSOR_FAILURE_STREAK_LIMIT 5U
#define SENSOR_RECOVERY_MAX_ATTEMPTS 3U
#define SENSOR_RECOVERY_RETRY_INITIAL_MS 1000U
#define SENSOR_RECOVERY_RETRY_SECOND_MS 5000U
#define SENSOR_REBOOT_QUIET_MS 10000U
#define SENSOR_REBOOT_GUARD_CLEAR_MS 300000U
#define IDLE_SENSOR_HEALTH_CHECK_MS 600000U
#define SUSPECT_SENSOR_HEALTH_CHECK_MS 1000U
#define SENSOR_RETENTION_MAGIC 0x50544831U
#define ADVERTISING_RETRY_MS 250U
#define IDLE_ADV_INTERVAL_MIN_MS 2000U
#define IDLE_ADV_INTERVAL_MAX_MS 2500U
#define ADXL367_ACT_INACT_CTL_REG 0x27U
#define ADXL367_INTMAP1_LOWER_REG 0x2aU
#define ADXL367_POWER_CTL_REG 0x2dU
#define ADXL367_ACT_INACT_MODE_MASK GENMASK(5, 0)
#define ADXL367_REFERENCED_ACTIVITY_ONLY (BIT(1) | BIT(0))
#define ADXL367_INTMAP_ACTIVITY_BIT BIT(4)
#define ADXL367_INTMAP_INACTIVITY_BIT BIT(5)
#define ADXL367_POWER_CTL_WAKEUP_BIT BIT(3)

/* Count a sample as clipped just before the configured full-scale rail. */
#define ADXL367_CLIP_MICRO_MS2 19221034
#define BMI270_ACCEL_CLIP_MICRO_MS2 153768272
#define BMI270_GYRO_CLIP_MICRO_RADS 34208453
#define DEVICE_ID_MAX_SIZE 16U
#define BOOT_ID_SIZE 8U
#define ADVERTISING_NAME_PREFIX "PuttTrack-"
#define ADVERTISING_NAME_SUFFIX_BYTES 4U
#define ADVERTISING_NAME_BUFFER_SIZE \
	(sizeof(ADVERTISING_NAME_PREFIX) + ADVERTISING_NAME_SUFFIX_BYTES * 2U)

#define STATUS_FLAG_ADXL367_READY BIT(0)
#define STATUS_FLAG_BMI270_READY  BIT(1)
#define STATUS_FLAG_NOTIFY_ACTIVE BIT(2)
#define STATUS_FLAG_RUNTIME_ACTIVE BIT(3)
#define STATUS_FLAG_POWER_AUTO BIT(4)
#define STATUS_FLAG_POWER_RESEARCH BIT(5)
#define STATUS_FLAG_POWER_IDLE BIT(6)

#define MOTION_FLAG_ADXL367_VALID BIT(0)
#define MOTION_FLAG_BMI270_VALID  BIT(1)

#define SENSOR_ERROR_ADXL367_FETCH BIT(0)
#define SENSOR_ERROR_ADXL367_READ  BIT(1)
#define SENSOR_ERROR_BMI270_FETCH  BIT(2)
#define SENSOR_ERROR_BMI270_ACCEL  BIT(3)
#define SENSOR_ERROR_BMI270_GYRO   BIT(4)

enum putttrack_power_policy {
	PUTTTRACK_POWER_AUTO = 0,
	PUTTTRACK_POWER_RESEARCH = 1,
	PUTTTRACK_POWER_IDLE = 2,
};

enum putttrack_runtime_state {
	PUTTTRACK_RUNTIME_ACTIVE = 0,
	PUTTTRACK_RUNTIME_IDLE = 1,
};

enum putttrack_sensor_health {
	PUTTTRACK_SENSOR_HEALTHY = 0,
	PUTTTRACK_SENSOR_SUSPECT = 1,
	PUTTTRACK_SENSOR_RECOVERING = 2,
	PUTTTRACK_SENSOR_DEGRADED = 3,
	PUTTTRACK_SENSOR_QUARANTINED = 4,
};

struct sensor_reboot_retention {
	uint32_t magic;
	uint32_t guard;
	uint32_t reboot_count;
	uint32_t last_fault_bits;
};

/* PuttTrack telemetry service: 8f3a1000-6e7d-4b9a-a6e8-3f3f7d2c0001. */
static const struct bt_uuid_128 putttrack_service_uuid = BT_UUID_INIT_128(
	BT_UUID_128_ENCODE(0x8f3a1000, 0x6e7d, 0x4b9a, 0xa6e8, 0x3f3f7d2c0001));
static const struct bt_uuid_128 putttrack_status_uuid = BT_UUID_INIT_128(
	BT_UUID_128_ENCODE(0x8f3a1001, 0x6e7d, 0x4b9a, 0xa6e8, 0x3f3f7d2c0001));
static const struct bt_uuid_128 putttrack_motion_uuid = BT_UUID_INIT_128(
	BT_UUID_128_ENCODE(0x8f3a1002, 0x6e7d, 0x4b9a, 0xa6e8, 0x3f3f7d2c0001));

static const struct device *const adxl367 = DEVICE_DT_GET(DT_NODELABEL(adxl367));
static const struct device *const bmi270 = DEVICE_DT_GET(DT_NODELABEL(bmi270));
static const struct device *const bmi270_spi = DEVICE_DT_GET(DT_NODELABEL(spi22));
static const struct device *const battery_fuel_gauge =
	DEVICE_DT_GET(DT_ALIAS(battery_fuel_gauge));
static const struct i2c_dt_spec adxl367_i2c =
	I2C_DT_SPEC_GET(DT_NODELABEL(adxl367));
static const struct sensor_trigger idle_wake_trigger = {
	.type = SENSOR_TRIG_THRESHOLD,
	.chan = SENSOR_CHAN_ACCEL_XYZ,
};

static uint8_t status_packet[STATUS_PACKET_SIZE];
static uint8_t motion_packet[MOTION_PACKET_SIZE];
static uint8_t motion_ring[MOTION_HISTORY_SAMPLES][MOTION_PACKET_SIZE];
static uint16_t motion_ring_write_index;
static uint16_t motion_ring_count;
static uint8_t motion_window_snapshot[MOTION_WINDOW_BYTES];
static char motion_window_hex[MOTION_WINDOW_HEX_BYTES];
static uint8_t frozen_motion_history[MOTION_HISTORY_SAMPLES][MOTION_PACKET_SIZE];
static uint16_t frozen_motion_count;
static uint32_t frozen_capture_id;
static uint8_t device_id[DEVICE_ID_MAX_SIZE];
static uint8_t device_id_len;
static uint8_t boot_id[BOOT_ID_SIZE];
static char advertising_name[ADVERTISING_NAME_BUFFER_SIZE];
static uint32_t reset_cause;
static uint32_t sequence;
static uint32_t sensor_error_count;
static uint32_t sensor_fault_count;
static uint32_t sensor_recovery_generation;
static uint32_t sensor_recovery_attempt_count;
static uint32_t sensor_recovery_success_count;
static uint32_t sensor_recovery_failure_count;
static uint32_t adxl367_error_streak;
static uint32_t bmi270_error_streak;
static uint32_t last_sensor_error_bits;
static uint64_t last_sensor_error_uptime_ms;
static uint32_t notify_drop_count;
static uint32_t adxl367_clip_count;
static uint32_t bmi270_accel_clip_count;
static uint32_t bmi270_gyro_clip_count;
static bool adxl367_ready;
static bool bmi270_ready;
static atomic_t notify_enabled;
static atomic_t ble_connected;
static atomic_t bluetooth_ready;
static atomic_t power_policy = ATOMIC_INIT(PUTTTRACK_POWER_AUTO);
static atomic_t runtime_state = ATOMIC_INIT(PUTTTRACK_RUNTIME_ACTIVE);
static atomic_t sensor_health = ATOMIC_INIT(PUTTTRACK_SENSOR_HEALTHY);
static uint32_t power_transition_count;
static uint32_t advertising_start_error_count;
static uint32_t power_management_error_count;
static bool battery_supported;
static bool battery_sample_valid;
static int32_t battery_sample_error;
static uint32_t battery_voltage_mv;
static uint32_t battery_soc_percent;
static atomic_t bmi270_spi_suspended;
static atomic_t idle_wake_interrupt_enabled;
static atomic_t adxl367_wakeup_mode_enabled;
static atomic_t idle_wake_requested;
static uint32_t current_stream_rate_hz = MOTION_STREAM_RATE_HZ;
static uint32_t current_adxl367_odr_hz = ADXL367_ODR_HZ;
static uint32_t current_bmi270_accel_odr_hz = BMI270_ACCEL_ODR_HZ;
static uint32_t current_bmi270_gyro_odr_hz = BMI270_GYRO_ODR_HZ;
static uint32_t current_adv_interval_min_ms = 100U;
static uint32_t current_adv_interval_max_ms = 150U;
static int64_t last_active_motion_ms;
static int64_t sensor_healthy_since_ms;
static int64_t next_sensor_recovery_ms;
static int64_t last_idle_sensor_health_check_ms;
static uint8_t sensor_recovery_attempts_in_episode;
static int32_t active_previous_adxl[3];
static bool active_previous_adxl_valid;
static int32_t idle_adxl_baseline[3];
static bool idle_adxl_baseline_valid;
static uint8_t idle_wake_samples;
static struct k_work_delayable advertise_work;
static struct sensor_reboot_retention sensor_reboot_retention __noinit;
#if defined(CONFIG_PUTTTRACK_MOTION_DEMO_V0)
static struct motion_demo_v0 motion_demo;
#endif

#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
#define NFC_NDEF_BUFFER_SIZE 160U
#define NFC_URI_BUFFER_SIZE 96U
#define NFC_SERVICE_DISCOVERY_WINDOW_MS 10000U
#define NFC_SYSTEM_OFF_DELAY_MS 2000U

static uint8_t nfc_ndef_buffer[NFC_NDEF_BUFFER_SIZE];
static atomic_t nfc_field_on_count;
static atomic_t nfc_field_off_count;
static atomic_t nfc_data_read_count;
static atomic_t nfc_field_present;
static atomic_t nfc_service_window_active;
static atomic_t nfc_service_window_open_count;
static atomic_t nfc_service_window_suppressed_count;
static int32_t nfc_setup_error;
static atomic_t system_off_pending;
static int32_t system_off_entry_error;
static bool nfc_system_off_wake;
static struct k_work nfc_service_window_open_work;
static struct k_work_delayable nfc_service_window_close_work;
#if defined(CONFIG_PUTTTRACK_NFC_SYSTEM_OFF_TEST)
static struct k_work_delayable system_off_work;
#endif
#endif

K_MUTEX_DEFINE(packet_mutex);
#if defined(CONFIG_PUTTTRACK_MOTION_DEMO_V0)
K_MUTEX_DEFINE(motion_demo_mutex);
#endif
#if defined(CONFIG_PUTTTRACK_STROKE_PICKUP_V1)
static struct spv1_context shadow_engine;
/* Separate readback storage avoids >4KB stack frames in the SMP worker. */
static struct spv1_context shadow_readback;
static char shadow_event_hex[SPV1_EVENT_CAPACITY * 64U * 2U];
K_MUTEX_DEFINE(shadow_engine_mutex);
K_MUTEX_DEFINE(shadow_rpc_mutex);
#endif
K_SEM_DEFINE(power_event_sem, 0, 1);

static void build_status_packet(void);
static void begin_sensor_recovery(uint32_t error_bits);

static void sample_battery(void)
{
	static const fuel_gauge_prop_t properties[] = {
		FUEL_GAUGE_VOLTAGE,
		FUEL_GAUGE_RELATIVE_STATE_OF_CHARGE,
	};
	union fuel_gauge_prop_val values[ARRAY_SIZE(properties)];
	int rc;

	battery_supported = device_is_ready(battery_fuel_gauge);
	battery_sample_valid = false;
	if (!battery_supported) {
		battery_sample_error = -ENODEV;
		return;
	}

	rc = fuel_gauge_get_props(battery_fuel_gauge, properties, values,
				  ARRAY_SIZE(properties));
	if (rc != 0) {
		battery_sample_error = rc;
		return;
	}
	if (values[0].voltage < 0 ||
	    values[1].relative_state_of_charge > 100U) {
		battery_sample_error = -ERANGE;
		return;
	}

	battery_voltage_mv = (uint32_t)values[0].voltage / 1000U;
	battery_soc_percent = values[1].relative_state_of_charge;
	battery_sample_error = 0;
	battery_sample_valid = true;
}

static const char *power_policy_name(enum putttrack_power_policy policy)
{
	switch (policy) {
	case PUTTTRACK_POWER_RESEARCH:
		return "research";
	case PUTTTRACK_POWER_IDLE:
		return "idle";
	case PUTTTRACK_POWER_AUTO:
	default:
		return "auto";
	}
}

static const char *runtime_state_name(enum putttrack_runtime_state state)
{
	return state == PUTTTRACK_RUNTIME_ACTIVE ? "active" : "idle";
}

static const char *sensor_health_name(enum putttrack_sensor_health health)
{
	switch (health) {
	case PUTTTRACK_SENSOR_SUSPECT:
		return "suspect";
	case PUTTTRACK_SENSOR_RECOVERING:
		return "recovering";
	case PUTTTRACK_SENSOR_DEGRADED:
		return "degraded";
	case PUTTTRACK_SENSOR_QUARANTINED:
		return "quarantined";
	case PUTTTRACK_SENSOR_HEALTHY:
	default:
		return "healthy";
	}
}

static void bytes_to_hex(const uint8_t *input, size_t input_len, char *output)
{
	static const char digits[] = "0123456789abcdef";

	for (size_t index = 0; index < input_len; index++) {
		output[index * 2] = digits[input[index] >> 4];
		output[index * 2 + 1] = digits[input[index] & 0x0f];
	}
}

static void initialize_advertising_name(void)
{
	const size_t prefix_len = sizeof(ADVERTISING_NAME_PREFIX) - 1U;
	const size_t suffix_len = MIN((size_t)device_id_len,
				      (size_t)ADVERTISING_NAME_SUFFIX_BYTES);

	memcpy(advertising_name, ADVERTISING_NAME_PREFIX, prefix_len);
	bytes_to_hex(device_id, suffix_len, &advertising_name[prefix_len]);
	advertising_name[prefix_len + suffix_len * 2U] = '\0';
}

static int putttrack_mgmt_status(struct smp_streamer *ctxt)
{
	zcbor_state_t *zse = ctxt->writer->zs;
	enum putttrack_power_policy policy = atomic_get(&power_policy);
	enum putttrack_runtime_state state = atomic_get(&runtime_state);
	enum putttrack_sensor_health health = atomic_get(&sensor_health);
	const char *policy_text = power_policy_name(policy);
	const char *state_text = runtime_state_name(state);
	const char *health_text = sensor_health_name(health);
	char device_id_hex[DEVICE_ID_MAX_SIZE * 2];
	char boot_id_hex[BOOT_ID_SIZE * 2];
	struct zcbor_string device_id_value = {
		.value = (const uint8_t *)device_id_hex,
		.len = device_id_len * 2U,
	};
	struct zcbor_string boot_id_value = {
		.value = (const uint8_t *)boot_id_hex,
		.len = sizeof(boot_id) * 2U,
	};
	struct zcbor_string firmware_value = {
		.value = (const uint8_t *)PUTTTRACK_FIRMWARE_VERSION,
		.len = strlen(PUTTTRACK_FIRMWARE_VERSION),
	};
	struct zcbor_string power_policy_value = {
		.value = (const uint8_t *)policy_text,
		.len = strlen(policy_text),
	};
	struct zcbor_string runtime_state_value = {
		.value = (const uint8_t *)state_text,
		.len = strlen(state_text),
	};
	struct zcbor_string sensor_health_value = {
		.value = (const uint8_t *)health_text,
		.len = strlen(health_text),
	};
	uint32_t status_sequence;
	bool ok;

	sample_battery();
	bytes_to_hex(device_id, device_id_len, device_id_hex);
	bytes_to_hex(boot_id, sizeof(boot_id), boot_id_hex);
	build_status_packet();
	k_mutex_lock(&packet_mutex, K_FOREVER);
	status_sequence = sys_get_le32(&status_packet[4]);
	k_mutex_unlock(&packet_mutex);

	ok = zcbor_tstr_put_lit(zse, "proto") &&
	     zcbor_uint32_put(zse, PUTTTRACK_PROTOCOL_VERSION) &&
	     zcbor_tstr_put_lit(zse, "seq") &&
	     zcbor_uint32_put(zse, status_sequence) &&
	     zcbor_tstr_put_lit(zse, "uptime_ms") &&
	     zcbor_uint64_put(zse, (uint64_t)k_uptime_get()) &&
	     zcbor_tstr_put_lit(zse, "reset") &&
	     zcbor_uint32_put(zse, reset_cause) &&
	     zcbor_tstr_put_lit(zse, "sensor_errors") &&
	     zcbor_uint32_put(zse, sensor_error_count) &&
	     zcbor_tstr_put_lit(zse, "notify_drops") &&
	     zcbor_uint32_put(zse, notify_drop_count) &&
	     zcbor_tstr_put_lit(zse, "stream_hz") &&
	     zcbor_uint32_put(zse, current_stream_rate_hz) &&
	     zcbor_tstr_put_lit(zse, "adxl_odr_hz") &&
	     zcbor_uint32_put(zse, current_adxl367_odr_hz) &&
	     zcbor_tstr_put_lit(zse, "adxl_range_g") &&
	     zcbor_uint32_put(zse, ADXL367_RANGE_G) &&
	     zcbor_tstr_put_lit(zse, "bmi_accel_odr_hz") &&
	     zcbor_uint32_put(zse, current_bmi270_accel_odr_hz) &&
	     zcbor_tstr_put_lit(zse, "bmi_accel_range_g") &&
	     zcbor_uint32_put(zse, BMI270_ACCEL_RANGE_G) &&
	     zcbor_tstr_put_lit(zse, "bmi_gyro_odr_hz") &&
	     zcbor_uint32_put(zse, current_bmi270_gyro_odr_hz) &&
	     zcbor_tstr_put_lit(zse, "bmi_gyro_range_dps") &&
	     zcbor_uint32_put(zse, BMI270_GYRO_RANGE_DPS) &&
	     zcbor_tstr_put_lit(zse, "adxl_clips") &&
	     zcbor_uint32_put(zse, adxl367_clip_count) &&
	     zcbor_tstr_put_lit(zse, "bmi_accel_clips") &&
	     zcbor_uint32_put(zse, bmi270_accel_clip_count) &&
	     zcbor_tstr_put_lit(zse, "bmi_gyro_clips") &&
	     zcbor_uint32_put(zse, bmi270_gyro_clip_count) &&
	     zcbor_tstr_put_lit(zse, "adxl_ready") &&
	     zcbor_bool_put(zse, adxl367_ready) &&
	     zcbor_tstr_put_lit(zse, "bmi_ready") &&
	     zcbor_bool_put(zse, bmi270_ready) &&
	     zcbor_tstr_put_lit(zse, "device_id") &&
	     zcbor_tstr_encode(zse, &device_id_value) &&
	     zcbor_tstr_put_lit(zse, "boot_id") &&
	     zcbor_tstr_encode(zse, &boot_id_value) &&
	     zcbor_tstr_put_lit(zse, "fw") &&
	     zcbor_tstr_encode(zse, &firmware_value) &&
	     zcbor_tstr_put_lit(zse, "power_policy") &&
	     zcbor_tstr_encode(zse, &power_policy_value) &&
	     zcbor_tstr_put_lit(zse, "runtime_state") &&
	     zcbor_tstr_encode(zse, &runtime_state_value) &&
	     zcbor_tstr_put_lit(zse, "sensor_health") &&
	     zcbor_tstr_encode(zse, &sensor_health_value) &&
	     zcbor_tstr_put_lit(zse, "capture_safe") &&
	     zcbor_bool_put(zse, health == PUTTTRACK_SENSOR_HEALTHY &&
			    adxl367_ready && bmi270_ready &&
			    state == PUTTTRACK_RUNTIME_ACTIVE &&
			    current_stream_rate_hz == MOTION_STREAM_RATE_HZ) &&
	     zcbor_tstr_put_lit(zse, "sensor_faults") &&
	     zcbor_uint32_put(zse, sensor_fault_count) &&
	     zcbor_tstr_put_lit(zse, "recovery_generation") &&
	     zcbor_uint32_put(zse, sensor_recovery_generation) &&
	     zcbor_tstr_put_lit(zse, "recovery_attempts") &&
	     zcbor_uint32_put(zse, sensor_recovery_attempt_count) &&
	     zcbor_tstr_put_lit(zse, "recovery_successes") &&
	     zcbor_uint32_put(zse, sensor_recovery_success_count) &&
	     zcbor_tstr_put_lit(zse, "recovery_failures") &&
	     zcbor_uint32_put(zse, sensor_recovery_failure_count) &&
	     zcbor_tstr_put_lit(zse, "adxl_error_streak") &&
	     zcbor_uint32_put(zse, adxl367_error_streak) &&
	     zcbor_tstr_put_lit(zse, "bmi_error_streak") &&
	     zcbor_uint32_put(zse, bmi270_error_streak) &&
	     zcbor_tstr_put_lit(zse, "last_sensor_error_bits") &&
	     zcbor_uint32_put(zse, last_sensor_error_bits) &&
	     zcbor_tstr_put_lit(zse, "last_sensor_error_ms") &&
	     zcbor_uint64_put(zse, last_sensor_error_uptime_ms) &&
	     zcbor_tstr_put_lit(zse, "auto_reboots") &&
	     zcbor_uint32_put(zse, sensor_reboot_retention.reboot_count) &&
	     zcbor_tstr_put_lit(zse, "auto_reboot_fault_bits") &&
	     zcbor_uint32_put(zse, sensor_reboot_retention.last_fault_bits) &&
	     zcbor_tstr_put_lit(zse, "auto_reboot_guard") &&
	     zcbor_bool_put(zse, sensor_reboot_retention.guard != 0U) &&
	     zcbor_tstr_put_lit(zse, "auto_reboot_pending") &&
	     zcbor_bool_put(zse, health == PUTTTRACK_SENSOR_DEGRADED &&
			    sensor_reboot_retention.guard == 0U) &&
	     zcbor_tstr_put_lit(zse, "idle_health_check_ms") &&
	     zcbor_uint32_put(zse, IDLE_SENSOR_HEALTH_CHECK_MS) &&
	     zcbor_tstr_put_lit(zse, "power_transitions") &&
	     zcbor_uint32_put(zse, power_transition_count) &&
	     zcbor_tstr_put_lit(zse, "idle_timeout_ms") &&
	     zcbor_uint32_put(zse, AUTO_IDLE_TIMEOUT_MS) &&
	     zcbor_tstr_put_lit(zse, "wake_poll_ms") &&
	     zcbor_uint32_put(zse,
			      atomic_get(&idle_wake_interrupt_enabled) != 0 ?
			      0U : IDLE_WAKE_SAMPLE_PERIOD_MS) &&
	     zcbor_tstr_put_lit(zse, "wake_interrupt") &&
	     zcbor_bool_put(zse, atomic_get(&idle_wake_interrupt_enabled) != 0) &&
	     zcbor_tstr_put_lit(zse, "adxl_wakeup_mode") &&
	     zcbor_bool_put(zse, atomic_get(&adxl367_wakeup_mode_enabled) != 0) &&
	     zcbor_tstr_put_lit(zse, "adv_interval_min_ms") &&
	     zcbor_uint32_put(zse, current_adv_interval_min_ms) &&
	     zcbor_tstr_put_lit(zse, "adv_interval_max_ms") &&
	     zcbor_uint32_put(zse, current_adv_interval_max_ms) &&
	     zcbor_tstr_put_lit(zse, "adv_start_errors") &&
	     zcbor_uint32_put(zse, advertising_start_error_count) &&
	     zcbor_tstr_put_lit(zse, "pm_errors") &&
	     zcbor_uint32_put(zse, power_management_error_count) &&
	     zcbor_tstr_put_lit(zse, "bmi_spi_suspended") &&
	     zcbor_bool_put(zse, atomic_get(&bmi270_spi_suspended) != 0) &&
	     zcbor_tstr_put_lit(zse, "battery_supported") &&
	     zcbor_bool_put(zse, battery_supported) &&
	     zcbor_tstr_put_lit(zse, "battery_sample_valid") &&
	     zcbor_bool_put(zse, battery_sample_valid) &&
	     zcbor_tstr_put_lit(zse, "battery_sample_error") &&
	     zcbor_int32_put(zse, battery_sample_error) &&
	     zcbor_tstr_put_lit(zse, "battery_voltage_mv") &&
	     zcbor_uint32_put(zse, battery_voltage_mv) &&
	     zcbor_tstr_put_lit(zse, "battery_soc_percent") &&
	     zcbor_uint32_put(zse, battery_soc_percent) &&
	     zcbor_tstr_put_lit(zse, "battery_soc_estimated") &&
	     zcbor_bool_put(zse, true);

#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
	ok = ok &&
	     zcbor_tstr_put_lit(zse, "nfc_enabled") &&
	     zcbor_bool_put(zse, true) &&
	     zcbor_tstr_put_lit(zse, "nfc_setup_error") &&
	     zcbor_int32_put(zse, nfc_setup_error) &&
	     zcbor_tstr_put_lit(zse, "nfc_field_on") &&
	     zcbor_uint32_put(zse, (uint32_t)atomic_get(&nfc_field_on_count)) &&
	     zcbor_tstr_put_lit(zse, "nfc_field_off") &&
	     zcbor_uint32_put(zse, (uint32_t)atomic_get(&nfc_field_off_count)) &&
	     zcbor_tstr_put_lit(zse, "nfc_data_reads") &&
	     zcbor_uint32_put(zse, (uint32_t)atomic_get(&nfc_data_read_count)) &&
	     zcbor_tstr_put_lit(zse, "nfc_field_present") &&
	     zcbor_bool_put(zse, atomic_get(&nfc_field_present) != 0) &&
	     zcbor_tstr_put_lit(zse, "nfc_service_window") &&
	     zcbor_bool_put(zse, atomic_get(&nfc_service_window_active) != 0) &&
	     zcbor_tstr_put_lit(zse, "nfc_service_window_ms") &&
	     zcbor_uint32_put(zse, NFC_SERVICE_DISCOVERY_WINDOW_MS) &&
	     zcbor_tstr_put_lit(zse, "nfc_service_window_opens") &&
	     zcbor_uint32_put(zse,
			       (uint32_t)atomic_get(&nfc_service_window_open_count)) &&
	     zcbor_tstr_put_lit(zse, "nfc_service_window_suppressed") &&
	     zcbor_uint32_put(zse,
			       (uint32_t)atomic_get(
				       &nfc_service_window_suppressed_count)) &&
	     zcbor_tstr_put_lit(zse, "system_off_supported") &&
	     zcbor_bool_put(zse,
			     IS_ENABLED(CONFIG_PUTTTRACK_NFC_SYSTEM_OFF_TEST)) &&
	     zcbor_tstr_put_lit(zse, "system_off_pending") &&
	     zcbor_bool_put(zse, atomic_get(&system_off_pending) != 0) &&
	     zcbor_tstr_put_lit(zse, "system_off_entry_error") &&
	     zcbor_int32_put(zse, system_off_entry_error) &&
	     zcbor_tstr_put_lit(zse, "nfc_system_off_wake") &&
	     zcbor_bool_put(zse, nfc_system_off_wake);
#endif

	return ok ? MGMT_ERR_EOK : MGMT_ERR_EMSGSIZE;
}

static int putttrack_mgmt_motion(struct smp_streamer *ctxt)
{
	zcbor_state_t *zse = ctxt->writer->zs;
	uint8_t snapshot[MOTION_PACKET_SIZE];
	bool ok;

	k_mutex_lock(&packet_mutex, K_FOREVER);
	memcpy(snapshot, motion_packet, sizeof(snapshot));
	k_mutex_unlock(&packet_mutex);

	ok = zcbor_tstr_put_lit(zse, "proto") &&
	     zcbor_uint32_put(zse, snapshot[0]) &&
	     zcbor_tstr_put_lit(zse, "seq") &&
	     zcbor_uint32_put(zse, sys_get_le32(&snapshot[4])) &&
	     zcbor_tstr_put_lit(zse, "t_us") &&
	     zcbor_uint64_put(zse, sys_get_le64(&snapshot[8])) &&
	     zcbor_tstr_put_lit(zse, "errors") &&
	     zcbor_uint32_put(zse, sys_get_le32(&snapshot[52])) &&
	     zcbor_tstr_put_lit(zse, "adxl_valid") &&
	     zcbor_bool_put(zse, (snapshot[1] & MOTION_FLAG_ADXL367_VALID) != 0U) &&
	     zcbor_tstr_put_lit(zse, "bmi_valid") &&
	     zcbor_bool_put(zse, (snapshot[1] & MOTION_FLAG_BMI270_VALID) != 0U) &&
	     zcbor_tstr_put_lit(zse, "adxl_ax") &&
	     zcbor_int32_put(zse, (int32_t)sys_get_le32(&snapshot[16])) &&
	     zcbor_tstr_put_lit(zse, "adxl_ay") &&
	     zcbor_int32_put(zse, (int32_t)sys_get_le32(&snapshot[20])) &&
	     zcbor_tstr_put_lit(zse, "adxl_az") &&
	     zcbor_int32_put(zse, (int32_t)sys_get_le32(&snapshot[24])) &&
	     zcbor_tstr_put_lit(zse, "bmi_ax") &&
	     zcbor_int32_put(zse, (int32_t)sys_get_le32(&snapshot[28])) &&
	     zcbor_tstr_put_lit(zse, "bmi_ay") &&
	     zcbor_int32_put(zse, (int32_t)sys_get_le32(&snapshot[32])) &&
	     zcbor_tstr_put_lit(zse, "bmi_az") &&
	     zcbor_int32_put(zse, (int32_t)sys_get_le32(&snapshot[36])) &&
	     zcbor_tstr_put_lit(zse, "bmi_gx") &&
	     zcbor_int32_put(zse, (int32_t)sys_get_le32(&snapshot[40])) &&
	     zcbor_tstr_put_lit(zse, "bmi_gy") &&
	     zcbor_int32_put(zse, (int32_t)sys_get_le32(&snapshot[44])) &&
	     zcbor_tstr_put_lit(zse, "bmi_gz") &&
	     zcbor_int32_put(zse, (int32_t)sys_get_le32(&snapshot[48]));

	return ok ? MGMT_ERR_EOK : MGMT_ERR_EMSGSIZE;
}

static int putttrack_mgmt_window(struct smp_streamer *ctxt)
{
	zcbor_state_t *zse = ctxt->writer->zs;
	struct zcbor_string data_value;
	uint16_t sample_count;
	uint16_t start_index;
	uint32_t start_sequence = 0U;
	uint32_t end_sequence = 0U;
	bool ok;

	k_mutex_lock(&packet_mutex, K_FOREVER);
	sample_count = MIN(motion_ring_count, MOTION_WINDOW_SAMPLES);
	start_index = (motion_ring_write_index + MOTION_HISTORY_SAMPLES - sample_count) %
		      MOTION_HISTORY_SAMPLES;
	for (size_t index = 0; index < sample_count; index++) {
		memcpy(&motion_window_snapshot[index * MOTION_PACKET_SIZE],
		       motion_ring[(start_index + index) % MOTION_HISTORY_SAMPLES],
		       MOTION_PACKET_SIZE);
	}
	k_mutex_unlock(&packet_mutex);

	if (sample_count > 0U) {
		start_sequence = sys_get_le32(&motion_window_snapshot[4]);
		end_sequence = sys_get_le32(
			&motion_window_snapshot[(sample_count - 1U) * MOTION_PACKET_SIZE + 4U]);
	}
	bytes_to_hex(motion_window_snapshot,
		     (size_t)sample_count * MOTION_PACKET_SIZE,
		     motion_window_hex);
	data_value = (struct zcbor_string) {
		.value = (const uint8_t *)motion_window_hex,
		.len = (size_t)sample_count * MOTION_PACKET_SIZE * 2U,
	};

	ok = zcbor_tstr_put_lit(zse, "proto") &&
	     zcbor_uint32_put(zse, PUTTTRACK_PROTOCOL_VERSION) &&
	     zcbor_tstr_put_lit(zse, "sample_size") &&
	     zcbor_uint32_put(zse, MOTION_PACKET_SIZE) &&
	     zcbor_tstr_put_lit(zse, "count") &&
	     zcbor_uint32_put(zse, sample_count) &&
	     zcbor_tstr_put_lit(zse, "start_seq") &&
	     zcbor_uint32_put(zse, start_sequence) &&
	     zcbor_tstr_put_lit(zse, "end_seq") &&
	     zcbor_uint32_put(zse, end_sequence) &&
	     zcbor_tstr_put_lit(zse, "data_hex") &&
	     zcbor_tstr_encode(zse, &data_value);

	return ok ? MGMT_ERR_EOK : MGMT_ERR_EMSGSIZE;
}

static int putttrack_mgmt_freeze_history(struct smp_streamer *ctxt)
{
	zcbor_state_t *zse = ctxt->writer->zs;
	uint16_t sample_count;
	uint16_t start_index;
	uint32_t capture_id;
	uint32_t start_sequence = 0U;
	uint32_t end_sequence = 0U;
	bool ok;

	k_mutex_lock(&packet_mutex, K_FOREVER);
	sample_count = motion_ring_count;
	start_index = (motion_ring_write_index + MOTION_HISTORY_SAMPLES - sample_count) %
		      MOTION_HISTORY_SAMPLES;
	for (size_t index = 0; index < sample_count; index++) {
		memcpy(frozen_motion_history[index],
		       motion_ring[(start_index + index) % MOTION_HISTORY_SAMPLES],
		       MOTION_PACKET_SIZE);
	}
	frozen_motion_count = sample_count;
	frozen_capture_id++;
	capture_id = frozen_capture_id;
	if (sample_count > 0U) {
		start_sequence = sys_get_le32(&frozen_motion_history[0][4]);
		end_sequence = sys_get_le32(&frozen_motion_history[sample_count - 1U][4]);
	}
	k_mutex_unlock(&packet_mutex);

	ok = zcbor_tstr_put_lit(zse, "proto") &&
	     zcbor_uint32_put(zse, PUTTTRACK_PROTOCOL_VERSION) &&
	     zcbor_tstr_put_lit(zse, "capture_id") &&
	     zcbor_uint32_put(zse, capture_id) &&
	     zcbor_tstr_put_lit(zse, "sample_size") &&
	     zcbor_uint32_put(zse, MOTION_PACKET_SIZE) &&
	     zcbor_tstr_put_lit(zse, "count") &&
	     zcbor_uint32_put(zse, sample_count) &&
	     zcbor_tstr_put_lit(zse, "chunk_size") &&
	     zcbor_uint32_put(zse, MOTION_WINDOW_SAMPLES) &&
	     zcbor_tstr_put_lit(zse, "chunk_count") &&
	     zcbor_uint32_put(zse,
			       DIV_ROUND_UP(sample_count, MOTION_WINDOW_SAMPLES)) &&
	     zcbor_tstr_put_lit(zse, "start_seq") &&
	     zcbor_uint32_put(zse, start_sequence) &&
	     zcbor_tstr_put_lit(zse, "end_seq") &&
	     zcbor_uint32_put(zse, end_sequence);

	return ok ? MGMT_ERR_EOK : MGMT_ERR_EMSGSIZE;
}

static int putttrack_mgmt_frozen_chunk(struct smp_streamer *ctxt,
				       uint16_t chunk_index)
{
	zcbor_state_t *zse = ctxt->writer->zs;
	struct zcbor_string data_value;
	uint16_t sample_offset = chunk_index * MOTION_WINDOW_SAMPLES;
	uint16_t sample_count;
	uint16_t total_count;
	uint32_t capture_id;
	uint32_t start_sequence = 0U;
	uint32_t end_sequence = 0U;
	bool ok;

	k_mutex_lock(&packet_mutex, K_FOREVER);
	total_count = frozen_motion_count;
	capture_id = frozen_capture_id;
	if (sample_offset >= total_count) {
		sample_count = 0U;
	} else {
		sample_count = MIN(total_count - sample_offset, MOTION_WINDOW_SAMPLES);
		for (size_t index = 0; index < sample_count; index++) {
			memcpy(&motion_window_snapshot[index * MOTION_PACKET_SIZE],
			       frozen_motion_history[sample_offset + index],
			       MOTION_PACKET_SIZE);
		}
	}
	k_mutex_unlock(&packet_mutex);

	if (sample_count > 0U) {
		start_sequence = sys_get_le32(&motion_window_snapshot[4]);
		end_sequence = sys_get_le32(
			&motion_window_snapshot[(sample_count - 1U) * MOTION_PACKET_SIZE + 4U]);
	}
	bytes_to_hex(motion_window_snapshot,
		     (size_t)sample_count * MOTION_PACKET_SIZE,
		     motion_window_hex);
	data_value = (struct zcbor_string) {
		.value = (const uint8_t *)motion_window_hex,
		.len = (size_t)sample_count * MOTION_PACKET_SIZE * 2U,
	};

	ok = zcbor_tstr_put_lit(zse, "proto") &&
	     zcbor_uint32_put(zse, PUTTTRACK_PROTOCOL_VERSION) &&
	     zcbor_tstr_put_lit(zse, "capture_id") &&
	     zcbor_uint32_put(zse, capture_id) &&
	     zcbor_tstr_put_lit(zse, "chunk_index") &&
	     zcbor_uint32_put(zse, chunk_index) &&
	     zcbor_tstr_put_lit(zse, "sample_size") &&
	     zcbor_uint32_put(zse, MOTION_PACKET_SIZE) &&
	     zcbor_tstr_put_lit(zse, "count") &&
	     zcbor_uint32_put(zse, sample_count) &&
	     zcbor_tstr_put_lit(zse, "start_seq") &&
	     zcbor_uint32_put(zse, start_sequence) &&
	     zcbor_tstr_put_lit(zse, "end_seq") &&
	     zcbor_uint32_put(zse, end_sequence) &&
	     zcbor_tstr_put_lit(zse, "data_hex") &&
	     zcbor_tstr_encode(zse, &data_value);

	return ok ? MGMT_ERR_EOK : MGMT_ERR_EMSGSIZE;
}

#define DEFINE_FROZEN_CHUNK_HANDLER(index)                                      \
	static int putttrack_mgmt_frozen_chunk_##index(struct smp_streamer *ctxt) \
	{                                                                          \
		return putttrack_mgmt_frozen_chunk(ctxt, index);                     \
	}

DEFINE_FROZEN_CHUNK_HANDLER(0)
DEFINE_FROZEN_CHUNK_HANDLER(1)
DEFINE_FROZEN_CHUNK_HANDLER(2)
DEFINE_FROZEN_CHUNK_HANDLER(3)
DEFINE_FROZEN_CHUNK_HANDLER(4)
DEFINE_FROZEN_CHUNK_HANDLER(5)
DEFINE_FROZEN_CHUNK_HANDLER(6)
DEFINE_FROZEN_CHUNK_HANDLER(7)
DEFINE_FROZEN_CHUNK_HANDLER(8)
DEFINE_FROZEN_CHUNK_HANDLER(9)
DEFINE_FROZEN_CHUNK_HANDLER(10)
DEFINE_FROZEN_CHUNK_HANDLER(11)
DEFINE_FROZEN_CHUNK_HANDLER(12)
DEFINE_FROZEN_CHUNK_HANDLER(13)
DEFINE_FROZEN_CHUNK_HANDLER(14)
DEFINE_FROZEN_CHUNK_HANDLER(15)

static int putttrack_mgmt_set_power_policy(
	struct smp_streamer *ctxt, enum putttrack_power_policy policy)
{
	zcbor_state_t *zse = ctxt->writer->zs;
	const char *policy_text = power_policy_name(policy);
	const char *state_text = runtime_state_name(atomic_get(&runtime_state));
	struct zcbor_string policy_value = {
		.value = (const uint8_t *)policy_text,
		.len = strlen(policy_text),
	};
	struct zcbor_string state_value = {
		.value = (const uint8_t *)state_text,
		.len = strlen(state_text),
	};

	atomic_set(&power_policy, policy);
	k_sem_give(&power_event_sem);
	bool ok = zcbor_tstr_put_lit(zse, "accepted") &&
		  zcbor_bool_put(zse, true) &&
		  zcbor_tstr_put_lit(zse, "power_policy") &&
		  zcbor_tstr_encode(zse, &policy_value) &&
		  zcbor_tstr_put_lit(zse, "runtime_state_before_apply") &&
		  zcbor_tstr_encode(zse, &state_value);

	return ok ? MGMT_ERR_EOK : MGMT_ERR_EMSGSIZE;
}

static int putttrack_mgmt_power_auto(struct smp_streamer *ctxt)
{
	return putttrack_mgmt_set_power_policy(ctxt, PUTTTRACK_POWER_AUTO);
}

static int putttrack_mgmt_power_research(struct smp_streamer *ctxt)
{
	return putttrack_mgmt_set_power_policy(ctxt, PUTTTRACK_POWER_RESEARCH);
}

static int putttrack_mgmt_power_idle(struct smp_streamer *ctxt)
{
	return putttrack_mgmt_set_power_policy(ctxt, PUTTTRACK_POWER_IDLE);
}


#if defined(CONFIG_PUTTTRACK_STROKE_PICKUP_V1)
static int putttrack_mgmt_stroke_pickup(struct smp_streamer *ctxt)
{
    zcbor_state_t *zse = ctxt->writer->zs;
    uint8_t wire[64];
    char id_hex[DEVICE_ID_MAX_SIZE * 2U], boot_hex[BOOT_ID_SIZE * 2U];
    bool ok;
    k_mutex_lock(&shadow_rpc_mutex, K_FOREVER);
    k_mutex_lock(&shadow_engine_mutex, K_FOREVER);
    shadow_readback = shadow_engine;
    k_mutex_unlock(&shadow_engine_mutex);
    const struct spv1_context *c = &shadow_readback;
    uint32_t first_id = c->event_count ? c->latest_id - c->event_count + 1U : 0U;
    for (uint32_t i = 0U; i < c->event_count; i++) {
        const struct spv1_event *e = &c->events[(first_id + i - 1U) % SPV1_EVENT_CAPACITY];
        sys_put_le32(e->id, wire); sys_put_le32(e->type, wire + 4);
        sys_put_le32(e->reason, wire + 8); sys_put_le32(e->quality, wire + 12);
        sys_put_le32(e->onset_seq, wire + 16); sys_put_le32(e->end_seq, wire + 20);
        sys_put_le64(e->onset_us, wire + 24); sys_put_le64(e->decision_us, wire + 32);
        sys_put_le32((uint32_t)e->impulse_milli, wire + 40);
        sys_put_le32((uint32_t)e->gyro_mean_milli, wire + 44);
        sys_put_le32(e->direction_milli, wire + 48); sys_put_le32(e->axial_milli, wire + 52);
        sys_put_le32(e->impact_milli, wire + 56); sys_put_le32(e->clip_permille, wire + 60);
        bytes_to_hex(wire, sizeof(wire), shadow_event_hex + i * 128U);
    }
    bytes_to_hex(device_id, device_id_len, id_hex);
    bytes_to_hex(boot_id, sizeof(boot_id), boot_hex);
    struct zcbor_string id = {.value = (const uint8_t *)id_hex, .len = device_id_len * 2U};
    struct zcbor_string boot = {.value = (const uint8_t *)boot_hex, .len = sizeof(boot_id) * 2U};
    struct zcbor_string data = {.value = (const uint8_t *)shadow_event_hex, .len = c->event_count * 128U};
    ok = zcbor_tstr_put_lit(zse, "algorithm_id") && zcbor_tstr_put_lit(zse, SPV1_ID) &&
         zcbor_tstr_put_lit(zse, "config_sha256") && zcbor_tstr_put_lit(zse, SPV1_CONFIG_SHA256) &&
         zcbor_tstr_put_lit(zse, "firmware_version") && zcbor_tstr_put_lit(zse, PUTTTRACK_FIRMWARE_VERSION) &&
         zcbor_tstr_put_lit(zse, "authority") && zcbor_bool_put(zse, false) &&
         zcbor_tstr_put_lit(zse, "candidate_only") && zcbor_bool_put(zse, true) &&
         zcbor_tstr_put_lit(zse, "device_id") && zcbor_tstr_encode(zse, &id) &&
         zcbor_tstr_put_lit(zse, "boot_id") && zcbor_tstr_encode(zse, &boot) &&
         zcbor_tstr_put_lit(zse, "stream_hz") && zcbor_uint32_put(zse, current_stream_rate_hz) &&
         zcbor_tstr_put_lit(zse, "generation") && zcbor_uint32_put(zse, c->generation) &&
         zcbor_tstr_put_lit(zse, "sensor_recovery_generation") && zcbor_uint32_put(zse, sensor_recovery_generation) &&
         zcbor_tstr_put_lit(zse, "source_seq") && zcbor_uint32_put(zse, c->source_sequence) &&
         zcbor_tstr_put_lit(zse, "source_us") && zcbor_uint64_put(zse, c->source_us) &&
         zcbor_tstr_put_lit(zse, "state") && zcbor_uint32_put(zse, c->state) &&
         zcbor_tstr_put_lit(zse, "armed") && zcbor_bool_put(zse, c->armed) &&
         zcbor_tstr_put_lit(zse, "held_hint") && zcbor_bool_put(zse, c->held_hint) &&
         zcbor_tstr_put_lit(zse, "count_incomplete") && zcbor_bool_put(zse, c->count_incomplete) &&
         zcbor_tstr_put_lit(zse, "stroke_candidates") && zcbor_uint32_put(zse, c->stroke_candidates) &&
         zcbor_tstr_put_lit(zse, "pickup_candidates") && zcbor_uint32_put(zse, c->pickup_candidates) &&
         zcbor_tstr_put_lit(zse, "ambiguous_contacts") && zcbor_uint32_put(zse, c->ambiguous_contacts) &&
         zcbor_tstr_put_lit(zse, "unknown_onsets") && zcbor_uint32_put(zse, c->unknown_onsets) &&
         zcbor_tstr_put_lit(zse, "quality_breaks") && zcbor_uint32_put(zse, c->quality_breaks) &&
         zcbor_tstr_put_lit(zse, "quality_flags") && zcbor_uint32_put(zse, c->current_quality) &&
         zcbor_tstr_put_lit(zse, "first_event_id") && zcbor_uint32_put(zse, first_id) &&
         zcbor_tstr_put_lit(zse, "latest_event_id") && zcbor_uint32_put(zse, c->latest_id) &&
         zcbor_tstr_put_lit(zse, "overwritten_events") && zcbor_uint32_put(zse, c->overwritten) &&
         zcbor_tstr_put_lit(zse, "event_size") && zcbor_uint32_put(zse, 64U) &&
         zcbor_tstr_put_lit(zse, "event_count") && zcbor_uint32_put(zse, c->event_count) &&
         zcbor_tstr_put_lit(zse, "events_hex") && zcbor_tstr_encode(zse, &data);
    k_mutex_unlock(&shadow_rpc_mutex);
    return ok ? MGMT_ERR_EOK : MGMT_ERR_EMSGSIZE;
}

static int putttrack_mgmt_shadow_new_trial(struct smp_streamer *ctxt)
{
    /* Explicit research command: operator has placed/released the ball.
     * This is not physical ground truth and never touches Gameplay. */
    if (atomic_get(&power_policy) != PUTTTRACK_POWER_RESEARCH ||
        atomic_get(&runtime_state) != PUTTTRACK_RUNTIME_ACTIVE ||
        atomic_get(&sensor_health) != PUTTTRACK_SENSOR_HEALTHY ||
        !adxl367_ready || !bmi270_ready) return MGMT_ERR_EINVAL;
    k_mutex_lock(&shadow_engine_mutex, K_FOREVER);
    spv1_new_trial(&shadow_engine);
    uint32_t generation = shadow_engine.generation;
    k_mutex_unlock(&shadow_engine_mutex);
    zcbor_state_t *zse = ctxt->writer->zs;
    bool ok = zcbor_tstr_put_lit(zse, "accepted") && zcbor_bool_put(zse, true) &&
              zcbor_tstr_put_lit(zse, "authority") && zcbor_bool_put(zse, false) &&
              zcbor_tstr_put_lit(zse, "generation") && zcbor_uint32_put(zse, generation);
    return ok ? MGMT_ERR_EOK : MGMT_ERR_EMSGSIZE;
}
#endif

#if defined(CONFIG_PUTTTRACK_MOTION_DEMO_V0)
static int putttrack_mgmt_motion_demo(struct smp_streamer *ctxt)
{
	zcbor_state_t *zse = ctxt->writer->zs;
	struct motion_demo_v0_snapshot snapshot;
	uint64_t now_us = k_ticks_to_us_floor64(k_uptime_ticks());
	uint64_t event_age_ms = 0U;
	const char *state_text;
	const char *event_text;
	struct zcbor_string state_value;
	struct zcbor_string event_value;
	struct zcbor_string detector_value = {
		.value = (const uint8_t *)MOTION_DEMO_V0_DETECTOR_ID,
		.len = sizeof(MOTION_DEMO_V0_DETECTOR_ID) - 1U,
	};
	struct zcbor_string config_hash_value = {
		.value = (const uint8_t *)MOTION_DEMO_V0_PICKUP_CONFIG_SHA256,
		.len = sizeof(MOTION_DEMO_V0_PICKUP_CONFIG_SHA256) - 1U,
	};
	bool ok;

	k_mutex_lock(&motion_demo_mutex, K_FOREVER);
	motion_demo_v0_get_snapshot(&motion_demo, &snapshot);
	k_mutex_unlock(&motion_demo_mutex);
	state_text = motion_demo_v0_state_name(snapshot.state);
	event_text = motion_demo_v0_event_name(snapshot.last_event);
	state_value = (struct zcbor_string) {
		.value = (const uint8_t *)state_text,
		.len = strlen(state_text),
	};
	event_value = (struct zcbor_string) {
		.value = (const uint8_t *)event_text,
		.len = strlen(event_text),
	};
	if (snapshot.last_event_us != 0U && now_us >= snapshot.last_event_us) {
		event_age_ms = (now_us - snapshot.last_event_us) / 1000U;
	}

	ok = zcbor_tstr_put_lit(zse, "demo_id") &&
	     zcbor_tstr_encode(zse, &detector_value) &&
	     zcbor_tstr_put_lit(zse, "authority") &&
	     zcbor_bool_put(zse, false) &&
	     zcbor_tstr_put_lit(zse, "candidate_only") &&
	     zcbor_bool_put(zse, true) &&
	     zcbor_tstr_put_lit(zse, "state") &&
	     zcbor_tstr_encode(zse, &state_value) &&
	     zcbor_tstr_put_lit(zse, "state_code") &&
	     zcbor_uint32_put(zse, (uint32_t)snapshot.state) &&
	     zcbor_tstr_put_lit(zse, "last_event") &&
	     zcbor_tstr_encode(zse, &event_value) &&
	     zcbor_tstr_put_lit(zse, "event_code") &&
	     zcbor_uint32_put(zse, (uint32_t)snapshot.last_event) &&
	     zcbor_tstr_put_lit(zse, "quality_flags") &&
	     zcbor_uint32_put(zse, snapshot.quality_flags) &&
	     zcbor_tstr_put_lit(zse, "transition_count") &&
	     zcbor_uint32_put(zse, snapshot.state_transition_count) &&
	     zcbor_tstr_put_lit(zse, "event_count") &&
	     zcbor_uint32_put(zse, snapshot.event_count) &&
	     zcbor_tstr_put_lit(zse, "event_age_ms") &&
	     zcbor_uint64_put(zse, event_age_ms) &&
	     zcbor_tstr_put_lit(zse, "onset_seq") &&
	     zcbor_uint32_put(zse, snapshot.onset_sequence) &&
	     zcbor_tstr_put_lit(zse, "last_transition_ms") &&
	     zcbor_uint64_put(zse, snapshot.last_transition_us / 1000U) &&
	     zcbor_tstr_put_lit(zse, "impulse_milli_mps") &&
	     zcbor_int32_put(zse, snapshot.vertical_impulse_milli_mps) &&
	     zcbor_tstr_put_lit(zse, "gyro_mean_milli_rads") &&
	     zcbor_int32_put(zse, snapshot.gyro_mean_milli_rads) &&
	     zcbor_tstr_put_lit(zse, "axis_milli") &&
	     zcbor_int32_put(zse, snapshot.axis_consistency_milli) &&
	     zcbor_tstr_put_lit(zse, "buffered_samples") &&
	     zcbor_uint32_put(zse, snapshot.buffered_samples) &&
	     zcbor_tstr_put_lit(zse, "baseline_stationary") &&
	     zcbor_bool_put(zse, snapshot.baseline_stationary) &&
	     zcbor_tstr_put_lit(zse, "pickup_rule") &&
	     zcbor_bool_put(zse, snapshot.pickup_rule_passed) &&
	     zcbor_tstr_put_lit(zse, "rolling_rule") &&
	     zcbor_bool_put(zse, snapshot.rolling_rule_passed) &&
	     zcbor_tstr_put_lit(zse, "pickup_config_sha256") &&
	     zcbor_tstr_encode(zse, &config_hash_value) &&
	     zcbor_tstr_put_lit(zse, "stream_hz") &&
	     zcbor_uint32_put(zse, current_stream_rate_hz);

	return ok ? MGMT_ERR_EOK : MGMT_ERR_EMSGSIZE;
}
#endif

#if defined(CONFIG_PUTTTRACK_NFC_SYSTEM_OFF_TEST)
static void enter_system_off(struct k_work *work)
{
	ARG_UNUSED(work);

	if (!atomic_cas(&system_off_pending, 1, 0)) {
		return;
	}
	if (atomic_get(&nfc_field_present) != 0) {
		system_off_entry_error = -EBUSY;
		return;
	}

	system_off_entry_error = 0;
	sys_poweroff();
}

static int putttrack_mgmt_enter_system_off(struct smp_streamer *ctxt)
{
	zcbor_state_t *zse = ctxt->writer->zs;
	bool accepted = false;
	int32_t error = 0;
	bool ok;

	if (nfc_setup_error != 0) {
		error = nfc_setup_error;
	} else if (atomic_get(&nfc_field_present) != 0) {
		error = -EBUSY;
	} else if (!atomic_cas(&system_off_pending, 0, 1)) {
		error = -EALREADY;
	} else {
		int rc = k_work_reschedule(&system_off_work,
					   K_MSEC(NFC_SYSTEM_OFF_DELAY_MS));

		if (rc < 0) {
			atomic_clear(&system_off_pending);
			error = rc;
		} else {
			accepted = true;
		}
	}

	system_off_entry_error = error;
	ok = zcbor_tstr_put_lit(zse, "accepted") &&
	     zcbor_bool_put(zse, accepted) &&
	     zcbor_tstr_put_lit(zse, "delay_ms") &&
	     zcbor_uint32_put(zse, NFC_SYSTEM_OFF_DELAY_MS) &&
	     zcbor_tstr_put_lit(zse, "error") &&
	     zcbor_int32_put(zse, error);

	return ok ? MGMT_ERR_EOK : MGMT_ERR_EMSGSIZE;
}
#endif

static const struct mgmt_handler putttrack_mgmt_handlers[] = {
#if defined(CONFIG_PUTTTRACK_STROKE_PICKUP_V1)
    [PUTTTRACK_MGMT_ID_STROKE_PICKUP] = {.mh_read = putttrack_mgmt_stroke_pickup, .mh_write = NULL},
    [PUTTTRACK_MGMT_ID_SHADOW_NEW_TRIAL] = {.mh_read = NULL, .mh_write = putttrack_mgmt_shadow_new_trial},
#endif
	[PUTTTRACK_MGMT_ID_STATUS] = {
		.mh_read = putttrack_mgmt_status,
		.mh_write = NULL,
	},
	[PUTTTRACK_MGMT_ID_MOTION] = {
		.mh_read = putttrack_mgmt_motion,
		.mh_write = NULL,
	},
	[PUTTTRACK_MGMT_ID_WINDOW] = {
		.mh_read = putttrack_mgmt_window,
		.mh_write = NULL,
	},
	[PUTTTRACK_MGMT_ID_FREEZE_HISTORY] = {
		.mh_read = putttrack_mgmt_freeze_history,
		.mh_write = NULL,
	},
	[4] = {.mh_read = putttrack_mgmt_frozen_chunk_0, .mh_write = NULL},
	[5] = {.mh_read = putttrack_mgmt_frozen_chunk_1, .mh_write = NULL},
	[6] = {.mh_read = putttrack_mgmt_frozen_chunk_2, .mh_write = NULL},
	[7] = {.mh_read = putttrack_mgmt_frozen_chunk_3, .mh_write = NULL},
	[8] = {.mh_read = putttrack_mgmt_frozen_chunk_4, .mh_write = NULL},
	[9] = {.mh_read = putttrack_mgmt_frozen_chunk_5, .mh_write = NULL},
	[10] = {.mh_read = putttrack_mgmt_frozen_chunk_6, .mh_write = NULL},
	[11] = {.mh_read = putttrack_mgmt_frozen_chunk_7, .mh_write = NULL},
	[12] = {.mh_read = putttrack_mgmt_frozen_chunk_8, .mh_write = NULL},
	[13] = {.mh_read = putttrack_mgmt_frozen_chunk_9, .mh_write = NULL},
	[14] = {.mh_read = putttrack_mgmt_frozen_chunk_10, .mh_write = NULL},
	[15] = {.mh_read = putttrack_mgmt_frozen_chunk_11, .mh_write = NULL},
	[16] = {.mh_read = putttrack_mgmt_frozen_chunk_12, .mh_write = NULL},
	[17] = {.mh_read = putttrack_mgmt_frozen_chunk_13, .mh_write = NULL},
	[18] = {.mh_read = putttrack_mgmt_frozen_chunk_14, .mh_write = NULL},
	[19] = {.mh_read = putttrack_mgmt_frozen_chunk_15, .mh_write = NULL},
	[PUTTTRACK_MGMT_ID_POWER_AUTO] = {
		.mh_read = NULL,
		.mh_write = putttrack_mgmt_power_auto,
	},
	[PUTTTRACK_MGMT_ID_POWER_RESEARCH] = {
		.mh_read = NULL,
		.mh_write = putttrack_mgmt_power_research,
	},
	[PUTTTRACK_MGMT_ID_POWER_IDLE] = {
		.mh_read = NULL,
		.mh_write = putttrack_mgmt_power_idle,
	},
#if defined(CONFIG_PUTTTRACK_MOTION_DEMO_V0)
	[PUTTTRACK_MGMT_ID_MOTION_DEMO] = {
		.mh_read = putttrack_mgmt_motion_demo,
		.mh_write = NULL,
	},
#endif
#if defined(CONFIG_PUTTTRACK_NFC_SYSTEM_OFF_TEST)
	[PUTTTRACK_MGMT_ID_ENTER_SYSTEM_OFF] = {
		.mh_read = NULL,
		.mh_write = putttrack_mgmt_enter_system_off,
	},
#endif
};

static struct mgmt_group putttrack_mgmt_group = {
	.mg_handlers = putttrack_mgmt_handlers,
	.mg_handlers_count = ARRAY_SIZE(putttrack_mgmt_handlers),
	.mg_group_id = PUTTTRACK_MGMT_GROUP_ID,
};

static void putttrack_mgmt_register_group(void)
{
	mgmt_register_group(&putttrack_mgmt_group);
}

MCUMGR_HANDLER_DEFINE(putttrack_mgmt, putttrack_mgmt_register_group);

static int32_t sensor_value_to_i32_micro(const struct sensor_value *value)
{
	int64_t micro = sensor_value_to_micro(value);

	if (micro > INT32_MAX) {
		return INT32_MAX;
	}
	if (micro < INT32_MIN) {
		return INT32_MIN;
	}
	return (int32_t)micro;
}

static bool packet_vector_clipped(const uint8_t *packet, size_t offset,
				  int32_t threshold)
{
	for (size_t index = 0; index < 3; index++) {
		int64_t value = (int32_t)sys_get_le32(&packet[offset + index * 4U]);

		if (value < 0) {
			value = -value;
		}
		if (value >= threshold) {
			return true;
		}
	}
	return false;
}

static void build_status_packet(void)
{
	uint8_t flags = 0U;
	enum putttrack_power_policy policy = atomic_get(&power_policy);
	const size_t fw_len = MIN(strlen(PUTTTRACK_FIRMWARE_VERSION), 8U);

	if (adxl367_ready) {
		flags |= STATUS_FLAG_ADXL367_READY;
	}
	if (bmi270_ready) {
		flags |= STATUS_FLAG_BMI270_READY;
	}
	if (atomic_get(&notify_enabled) != 0) {
		flags |= STATUS_FLAG_NOTIFY_ACTIVE;
	}
	if (atomic_get(&runtime_state) == PUTTTRACK_RUNTIME_ACTIVE) {
		flags |= STATUS_FLAG_RUNTIME_ACTIVE;
	}
	if (policy == PUTTTRACK_POWER_RESEARCH) {
		flags |= STATUS_FLAG_POWER_RESEARCH;
	} else if (policy == PUTTTRACK_POWER_IDLE) {
		flags |= STATUS_FLAG_POWER_IDLE;
	} else {
		flags |= STATUS_FLAG_POWER_AUTO;
	}

	k_mutex_lock(&packet_mutex, K_FOREVER);
	memset(status_packet, 0, sizeof(status_packet));
	status_packet[0] = PUTTTRACK_PROTOCOL_VERSION;
	status_packet[1] = flags;
	sys_put_le16(STATUS_PACKET_SIZE, &status_packet[2]);
	sys_put_le32(sequence, &status_packet[4]);
	sys_put_le64(k_uptime_get(), &status_packet[8]);
	sys_put_le32(reset_cause, &status_packet[16]);
	sys_put_le32(sensor_error_count, &status_packet[20]);
	sys_put_le32(notify_drop_count, &status_packet[24]);
	status_packet[28] = device_id_len;
	status_packet[29] = BOOT_ID_SIZE;
	status_packet[30] = fw_len;
	memcpy(&status_packet[32], device_id, device_id_len);
	memcpy(&status_packet[48], boot_id, BOOT_ID_SIZE);
	memcpy(&status_packet[56], PUTTTRACK_FIRMWARE_VERSION, fw_len);
	k_mutex_unlock(&packet_mutex);
}

static ssize_t read_status(struct bt_conn *conn, const struct bt_gatt_attr *attr,
			   void *buf, uint16_t len, uint16_t offset)
{
	uint8_t snapshot[STATUS_PACKET_SIZE];

	build_status_packet();
	k_mutex_lock(&packet_mutex, K_FOREVER);
	memcpy(snapshot, status_packet, sizeof(snapshot));
	k_mutex_unlock(&packet_mutex);

	return bt_gatt_attr_read(conn, attr, buf, len, offset, snapshot, sizeof(snapshot));
}

static ssize_t read_motion(struct bt_conn *conn, const struct bt_gatt_attr *attr,
			   void *buf, uint16_t len, uint16_t offset)
{
	uint8_t snapshot[MOTION_PACKET_SIZE];

	k_mutex_lock(&packet_mutex, K_FOREVER);
	memcpy(snapshot, motion_packet, sizeof(snapshot));
	k_mutex_unlock(&packet_mutex);

	return bt_gatt_attr_read(conn, attr, buf, len, offset, snapshot, sizeof(snapshot));
}

static void motion_ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
	ARG_UNUSED(attr);
	atomic_set(&notify_enabled, value == BT_GATT_CCC_NOTIFY);
}

BT_GATT_SERVICE_DEFINE(putttrack_service,
	BT_GATT_PRIMARY_SERVICE(&putttrack_service_uuid.uuid),
	BT_GATT_CHARACTERISTIC(&putttrack_status_uuid.uuid,
			       BT_GATT_CHRC_READ,
			       BT_GATT_PERM_READ_ENCRYPT,
			       read_status, NULL, NULL),
	BT_GATT_CHARACTERISTIC(&putttrack_motion_uuid.uuid,
			       BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY,
			       BT_GATT_PERM_READ_ENCRYPT,
			       read_motion, NULL, NULL),
	BT_GATT_CCC(motion_ccc_changed,
		    BT_GATT_PERM_READ_ENCRYPT | BT_GATT_PERM_WRITE_ENCRYPT));

static const struct bt_data advertising_data[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR),
	BT_DATA_BYTES(BT_DATA_UUID128_ALL, SMP_BT_SVC_UUID_VAL),
};

static struct bt_data scan_response_data[] = {
	{
		.type = BT_DATA_NAME_COMPLETE,
		.data_len = 0U,
		.data = (const uint8_t *)advertising_name,
	},
};

static const struct bt_le_adv_param active_advertising = BT_LE_ADV_PARAM_INIT(
	BT_LE_ADV_OPT_CONN, BT_GAP_ADV_FAST_INT_MIN_2,
	BT_GAP_ADV_FAST_INT_MAX_2, NULL);
static const struct bt_le_adv_param idle_advertising = BT_LE_ADV_PARAM_INIT(
	BT_LE_ADV_OPT_CONN, BT_GAP_MS_TO_ADV_INTERVAL(IDLE_ADV_INTERVAL_MIN_MS),
	BT_GAP_MS_TO_ADV_INTERVAL(IDLE_ADV_INTERVAL_MAX_MS), NULL);

static void advertise(struct k_work *work)
{
	const struct bt_le_adv_param *parameters;
	enum putttrack_sensor_health health = atomic_get(&sensor_health);
	int rc;

	ARG_UNUSED(work);
	if ((atomic_get(&runtime_state) == PUTTTRACK_RUNTIME_IDLE ||
	     health == PUTTTRACK_SENSOR_DEGRADED ||
	     health == PUTTTRACK_SENSOR_QUARANTINED)
#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
	    && atomic_get(&nfc_service_window_active) == 0
#endif
	) {
		parameters = &idle_advertising;
		current_adv_interval_min_ms = IDLE_ADV_INTERVAL_MIN_MS;
		current_adv_interval_max_ms = IDLE_ADV_INTERVAL_MAX_MS;
	} else {
		parameters = &active_advertising;
		current_adv_interval_min_ms = 100U;
		current_adv_interval_max_ms = 150U;
	}
	rc = bt_le_adv_start(parameters,
			     advertising_data, ARRAY_SIZE(advertising_data),
			     scan_response_data, ARRAY_SIZE(scan_response_data));
	if (rc != 0 && rc != -EALREADY) {
		advertising_start_error_count++;
		(void)k_work_reschedule(&advertise_work,
					K_MSEC(ADVERTISING_RETRY_MS));
	}
}

static void refresh_advertising(void)
{
	if (atomic_get(&bluetooth_ready) == 0 ||
	    atomic_get(&ble_connected) != 0) {
		return;
	}
	(void)bt_le_adv_stop();
	(void)k_work_reschedule(&advertise_work, K_NO_WAIT);
}

#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
static void close_nfc_service_window(struct k_work *work)
{
	ARG_UNUSED(work);

	if (atomic_cas(&nfc_service_window_active, 1, 0)) {
		refresh_advertising();
	}
}

static void open_nfc_service_window(struct k_work *work)
{
	ARG_UNUSED(work);

	/* A held field must not extend or repeatedly reopen the bounded window. */
	if (!atomic_cas(&nfc_service_window_active, 0, 1)) {
		atomic_inc(&nfc_service_window_suppressed_count);
		return;
	}
	atomic_inc(&nfc_service_window_open_count);
	refresh_advertising();
	(void)k_work_reschedule(&nfc_service_window_close_work,
				K_MSEC(NFC_SERVICE_DISCOVERY_WINDOW_MS));
}
#endif

static void connected(struct bt_conn *conn, uint8_t err)
{
	ARG_UNUSED(conn);
	if (err != 0U) {
		(void)k_work_reschedule(&advertise_work, K_NO_WAIT);
	} else {
		atomic_set(&ble_connected, 1);
	}
}

static void disconnected(struct bt_conn *conn, uint8_t reason)
{
	ARG_UNUSED(conn);
	ARG_UNUSED(reason);
	atomic_clear(&notify_enabled);
	atomic_clear(&ble_connected);
}

static void recycled(void)
{
	(void)k_work_reschedule(&advertise_work, K_NO_WAIT);
}

BT_CONN_CB_DEFINE(connection_callbacks) = {
	.connected = connected,
	.disconnected = disconnected,
	.recycled = recycled,
};

static void initialize_identity(void)
{
	ssize_t result;

#if defined(CONFIG_PUTTTRACK_NFC_SYSTEM_OFF_TEST)
	uint32_t raw_reset_cause;

#if NRF_POWER_HAS_RESETREAS
	raw_reset_cause = nrf_power_resetreas_get(NRF_POWER);
	nfc_system_off_wake =
		(raw_reset_cause & NRF_POWER_RESETREAS_NFC_MASK) != 0U;
#else
	raw_reset_cause = nrf_reset_resetreas_get(NRF_RESET);
	nfc_system_off_wake =
		(raw_reset_cause & NRF_RESET_RESETREAS_NFC_MASK) != 0U;
#endif
#endif

	result = hwinfo_get_device_id(device_id, sizeof(device_id));
	if (result > 0) {
		device_id_len = MIN((size_t)result, sizeof(device_id));
	} else {
		device_id_len = 0U;
	}

	(void)sys_csrand_get(boot_id, sizeof(boot_id));
	(void)hwinfo_get_reset_cause(&reset_cause);
	(void)hwinfo_clear_reset_cause();
}

static void initialize_sensor_reboot_retention(void)
{
	if (sensor_reboot_retention.magic != SENSOR_RETENTION_MAGIC) {
		sensor_reboot_retention = (struct sensor_reboot_retention) {
			.magic = SENSOR_RETENTION_MAGIC,
		};
	}
}

static int set_sensor_frequency(const struct device *device,
				enum sensor_channel channel, int32_t frequency_hz)
{
	struct sensor_value value = {.val1 = frequency_hz, .val2 = 0};

	return sensor_attr_set(device, channel, SENSOR_ATTR_SAMPLING_FREQUENCY,
			       &value);
}

static int set_adxl367_wakeup_mode(bool enable)
{
	uint8_t register_address = ADXL367_POWER_CTL_REG;
	uint8_t value;
	uint8_t readback;
	uint8_t write_buffer[2];
	int rc;

	rc = i2c_write_read_dt(&adxl367_i2c, &register_address,
			       sizeof(register_address), &value, sizeof(value));
	if (rc != 0) {
		return rc;
	}
	if (enable) {
		value |= ADXL367_POWER_CTL_WAKEUP_BIT;
	} else {
		value &= ~ADXL367_POWER_CTL_WAKEUP_BIT;
	}
	write_buffer[0] = ADXL367_POWER_CTL_REG;
	write_buffer[1] = value;
	rc = i2c_write_dt(&adxl367_i2c, write_buffer, sizeof(write_buffer));
	if (rc != 0) {
		return rc;
	}
	rc = i2c_write_read_dt(&adxl367_i2c, &register_address,
			       sizeof(register_address), &readback, sizeof(readback));
	if (rc != 0) {
		return rc;
	}
	if ((readback & ADXL367_POWER_CTL_WAKEUP_BIT) !=
	    (enable ? ADXL367_POWER_CTL_WAKEUP_BIT : 0U)) {
		return -EIO;
	}
	atomic_set(&adxl367_wakeup_mode_enabled, enable ? 1 : 0);
	return 0;
}

static int update_adxl367_register(uint8_t register_address, uint8_t mask,
				   uint8_t value)
{
	uint8_t current;
	uint8_t readback;
	uint8_t write_buffer[2];
	int rc;

	rc = i2c_write_read_dt(&adxl367_i2c, &register_address,
			       sizeof(register_address), &current, sizeof(current));
	if (rc != 0) {
		return rc;
	}
	write_buffer[0] = register_address;
	write_buffer[1] = (current & ~mask) | (value & mask);
	rc = i2c_write_dt(&adxl367_i2c, write_buffer, sizeof(write_buffer));
	if (rc != 0) {
		return rc;
	}
	rc = i2c_write_read_dt(&adxl367_i2c, &register_address,
			       sizeof(register_address), &readback, sizeof(readback));
	if (rc != 0) {
		return rc;
	}
	return (readback & mask) == (value & mask) ? 0 : -EIO;
}

static int arm_adxl367_activity_detector(void)
{
	int rc;

	/* Re-engaging referenced activity captures the current stationary
	 * orientation as its reference. Default mode keeps activity detection
	 * armed continuously; inactivity must not wake the MCU.
	 */
	rc = update_adxl367_register(ADXL367_ACT_INACT_CTL_REG,
				     ADXL367_ACT_INACT_MODE_MASK, 0U);
	if (rc != 0) {
		return rc;
	}
	return update_adxl367_register(ADXL367_ACT_INACT_CTL_REG,
				       ADXL367_ACT_INACT_MODE_MASK,
				       ADXL367_REFERENCED_ACTIVITY_ONLY);
}

static void adxl367_motion_trigger(const struct device *device,
				   const struct sensor_trigger *trigger)
{
	ARG_UNUSED(device);
	ARG_UNUSED(trigger);
	atomic_set(&idle_wake_requested, 1);
	k_sem_give(&power_event_sem);
}

static int enable_idle_wake_interrupt(void)
{
	int rc;

	if (!adxl367_ready) {
		return -ENODEV;
	}
	rc = arm_adxl367_activity_detector();
	if (rc != 0) {
		return rc;
	}
	/* Referenced activity captures its reference while measurement mode is
	 * engaged. Allow two 12.5 Hz samples to settle before clearing status,
	 * mapping ACT to INT1 and finally selecting wake-up mode.
	 */
	k_sleep(K_MSEC(IDLE_ACTIVITY_REFERENCE_SETTLE_MS));
	rc = sensor_trigger_set(adxl367, &idle_wake_trigger,
				adxl367_motion_trigger);
	if (rc != 0) {
		return rc;
	}
	/* Zephyr maps ACT and INACT together for SENSOR_TRIG_THRESHOLD.
	 * Preserve the GPIO callback but narrow the sensor-side INT1 map so a
	 * stationary INACT event can never be mistaken for motion.
	 */
	rc = update_adxl367_register(ADXL367_INTMAP1_LOWER_REG,
				     ADXL367_INTMAP_ACTIVITY_BIT |
					     ADXL367_INTMAP_INACTIVITY_BIT,
				     ADXL367_INTMAP_ACTIVITY_BIT);
	if (rc != 0) {
		(void)sensor_trigger_set(adxl367, &idle_wake_trigger, NULL);
		return rc;
	}
	atomic_set(&idle_wake_interrupt_enabled, 1);
	return 0;
}

static int disable_idle_wake_interrupt(void)
{
	int rc;

	if (atomic_get(&idle_wake_interrupt_enabled) == 0) {
		return 0;
	}
	rc = sensor_trigger_set(adxl367, &idle_wake_trigger, NULL);
	if (rc == 0) {
		atomic_clear(&idle_wake_interrupt_enabled);
		atomic_clear(&idle_wake_requested);
	}
	return rc;
}

static void increment_saturating(uint32_t *value)
{
	if (*value != UINT32_MAX) {
		(*value)++;
	}
}

static void clear_motion_history(void)
{
#if defined(CONFIG_PUTTTRACK_STROKE_PICKUP_V1)
    k_mutex_lock(&shadow_engine_mutex, K_FOREVER);
    spv1_invalidate(&shadow_engine);
    k_mutex_unlock(&shadow_engine_mutex);
#endif
	k_mutex_lock(&packet_mutex, K_FOREVER);
	motion_ring_write_index = 0U;
	motion_ring_count = 0U;
	frozen_motion_count = 0U;
	frozen_capture_id++;
	k_mutex_unlock(&packet_mutex);
#if defined(CONFIG_PUTTTRACK_MOTION_DEMO_V0)
	k_mutex_lock(&motion_demo_mutex, K_FOREVER);
	motion_demo_v0_init(&motion_demo);
	k_mutex_unlock(&motion_demo_mutex);
#endif
}

static void begin_sensor_recovery(uint32_t error_bits)
{
	enum putttrack_sensor_health health = atomic_get(&sensor_health);

	if (health == PUTTTRACK_SENSOR_RECOVERING ||
	    health == PUTTTRACK_SENSOR_DEGRADED ||
	    health == PUTTTRACK_SENSOR_QUARANTINED) {
		return;
	}

	last_sensor_error_bits = error_bits;
	last_sensor_error_uptime_ms = (uint64_t)k_uptime_get();
	increment_saturating(&sensor_fault_count);
	increment_saturating(&sensor_recovery_generation);
	sensor_recovery_attempts_in_episode = 0U;
	next_sensor_recovery_ms = k_uptime_get();
	current_stream_rate_hz = 0U;
	active_previous_adxl_valid = false;
	idle_adxl_baseline_valid = false;
	idle_wake_samples = 0U;

	if ((error_bits & (SENSOR_ERROR_ADXL367_FETCH |
			   SENSOR_ERROR_ADXL367_READ)) != 0U) {
		adxl367_ready = false;
		adxl367_error_streak = SENSOR_FAILURE_STREAK_LIMIT;
	}
	if ((error_bits & (SENSOR_ERROR_BMI270_FETCH |
			   SENSOR_ERROR_BMI270_ACCEL |
			   SENSOR_ERROR_BMI270_GYRO)) != 0U) {
		bmi270_ready = false;
		bmi270_error_streak = SENSOR_FAILURE_STREAK_LIMIT;
	}
	if (atomic_get(&idle_wake_interrupt_enabled) != 0 &&
	    disable_idle_wake_interrupt() != 0) {
		increment_saturating(&power_management_error_count);
	}
	clear_motion_history();
	atomic_set(&runtime_state, PUTTTRACK_RUNTIME_ACTIVE);
	atomic_set(&sensor_health, PUTTTRACK_SENSOR_RECOVERING);
	refresh_advertising();
}

static void record_sensor_sample_result(uint32_t error_bits)
{
	if (error_bits == 0U) {
		adxl367_error_streak = 0U;
		bmi270_error_streak = 0U;
		if (atomic_get(&sensor_health) == PUTTTRACK_SENSOR_SUSPECT) {
			atomic_set(&sensor_health, PUTTTRACK_SENSOR_HEALTHY);
			sensor_healthy_since_ms = k_uptime_get();
		}
		return;
	}

	increment_saturating(&sensor_error_count);
	last_sensor_error_bits = error_bits;
	last_sensor_error_uptime_ms = (uint64_t)k_uptime_get();
	if ((error_bits & (SENSOR_ERROR_ADXL367_FETCH |
			   SENSOR_ERROR_ADXL367_READ)) != 0U) {
		increment_saturating(&adxl367_error_streak);
	} else {
		adxl367_error_streak = 0U;
	}
	if ((error_bits & (SENSOR_ERROR_BMI270_FETCH |
			   SENSOR_ERROR_BMI270_ACCEL |
			   SENSOR_ERROR_BMI270_GYRO)) != 0U) {
		increment_saturating(&bmi270_error_streak);
	} else {
		bmi270_error_streak = 0U;
	}

	if (adxl367_error_streak >= SENSOR_FAILURE_STREAK_LIMIT ||
	    bmi270_error_streak >= SENSOR_FAILURE_STREAK_LIMIT) {
		begin_sensor_recovery(error_bits);
	} else if (atomic_get(&sensor_health) == PUTTTRACK_SENSOR_HEALTHY) {
		atomic_set(&sensor_health, PUTTTRACK_SENSOR_SUSPECT);
	}
}

static uint32_t verify_active_sensor_samples(void)
{
	struct sensor_value adxl_accel[3];
	struct sensor_value bmi_accel[3];
	struct sensor_value bmi_gyro[3];
	uint32_t errors = 0U;

	if (!device_is_ready(adxl367) || sensor_sample_fetch(adxl367) != 0) {
		errors |= SENSOR_ERROR_ADXL367_FETCH;
	} else if (sensor_channel_get(adxl367, SENSOR_CHAN_ACCEL_XYZ,
				      adxl_accel) != 0) {
		errors |= SENSOR_ERROR_ADXL367_READ;
	}

	if (!device_is_ready(bmi270) || sensor_sample_fetch(bmi270) != 0) {
		errors |= SENSOR_ERROR_BMI270_FETCH;
	} else {
		if (sensor_channel_get(bmi270, SENSOR_CHAN_ACCEL_XYZ,
				       bmi_accel) != 0) {
			errors |= SENSOR_ERROR_BMI270_ACCEL;
		}
		if (sensor_channel_get(bmi270, SENSOR_CHAN_GYRO_XYZ,
				       bmi_gyro) != 0) {
			errors |= SENSOR_ERROR_BMI270_GYRO;
		}
	}
	return errors;
}

static int configure_active_sensors(void)
{
	int failures = 0;

	if (adxl367_ready) {
		if (set_sensor_frequency(adxl367, SENSOR_CHAN_ACCEL_XYZ,
					 ADXL367_ODR_HZ) == 0) {
			current_adxl367_odr_hz = ADXL367_ODR_HZ;
		} else {
			failures++;
		}
	}
	if (bmi270_ready) {
		if (set_sensor_frequency(bmi270, SENSOR_CHAN_ACCEL_XYZ,
					 BMI270_ACCEL_ODR_HZ) == 0) {
			current_bmi270_accel_odr_hz = BMI270_ACCEL_ODR_HZ;
		} else {
			failures++;
		}
		if (set_sensor_frequency(bmi270, SENSOR_CHAN_GYRO_XYZ,
					 BMI270_GYRO_ODR_HZ) == 0) {
			current_bmi270_gyro_odr_hz = BMI270_GYRO_ODR_HZ;
		} else {
			failures++;
		}
	}
	if (failures != 0) {
		for (int failure = 0; failure < failures; failure++) {
			increment_saturating(&sensor_error_count);
		}
		return -EIO;
	}
	return 0;
}

static int configure_bmi270_full_scale(void)
{
	struct sensor_value value;

	if (!bmi270_ready) {
		return -ENODEV;
	}
	value = (struct sensor_value){.val1 = BMI270_ACCEL_RANGE_G, .val2 = 0};
	if (sensor_attr_set(bmi270, SENSOR_CHAN_ACCEL_XYZ,
			    SENSOR_ATTR_FULL_SCALE, &value) != 0) {
		return -EIO;
	}
	value = (struct sensor_value){.val1 = BMI270_GYRO_RANGE_DPS, .val2 = 0};
	return sensor_attr_set(bmi270, SENSOR_CHAN_GYRO_XYZ,
			       SENSOR_ATTR_FULL_SCALE, &value);
}

static int configure_idle_sensors(void)
{
	int failures = 0;

	/* Disable the high-power gyro and BMI270 acceleration path before
	 * reducing the always-on ADXL367 output rate.
	 */
	if (bmi270_ready) {
		if (set_sensor_frequency(bmi270, SENSOR_CHAN_GYRO_XYZ, 0) == 0) {
			current_bmi270_gyro_odr_hz = 0U;
		} else {
			failures++;
		}
		if (set_sensor_frequency(bmi270, SENSOR_CHAN_ACCEL_XYZ, 0) == 0) {
			current_bmi270_accel_odr_hz = 0U;
		} else {
			failures++;
		}
	}
	if (adxl367_ready) {
		if (set_sensor_frequency(adxl367, SENSOR_CHAN_ACCEL_XYZ,
					 IDLE_ADXL367_ODR_HZ) == 0) {
			current_adxl367_odr_hz = IDLE_ADXL367_ODR_HZ;
		} else {
			failures++;
		}
	}
	if (failures != 0) {
		for (int failure = 0; failure < failures; failure++) {
			increment_saturating(&sensor_error_count);
		}
		return -EIO;
	}
	return 0;
}

static void initialize_sensors(void)
{
	uint32_t errors = 0U;

	adxl367_ready = device_is_ready(adxl367);
	bmi270_ready = device_is_ready(bmi270);

	if (!adxl367_ready) {
		errors |= SENSOR_ERROR_ADXL367_FETCH;
	}
	if (!bmi270_ready || configure_bmi270_full_scale() != 0) {
		errors |= SENSOR_ERROR_BMI270_FETCH;
	}
	if (configure_active_sensors() != 0) {
		errors |= SENSOR_ERROR_ADXL367_FETCH | SENSOR_ERROR_BMI270_FETCH;
	}
	for (size_t sample = 0U; errors == 0U && sample < 3U; sample++) {
		errors = verify_active_sensor_samples();
		if (errors == 0U && sample < 2U) {
			k_sleep(K_MSEC(20));
		}
	}
	if (errors != 0U) {
		increment_saturating(&sensor_error_count);
		begin_sensor_recovery(errors);
	} else {
		atomic_set(&sensor_health, PUTTTRACK_SENSOR_HEALTHY);
		sensor_healthy_since_ms = k_uptime_get();
	}

	last_active_motion_ms = k_uptime_get();
}

static uint32_t recovery_retry_delay_ms(uint8_t attempts)
{
	return attempts <= 1U ? SENSOR_RECOVERY_RETRY_INITIAL_MS :
		SENSOR_RECOVERY_RETRY_SECOND_MS;
}

static void attempt_sensor_recovery(void)
{
	uint32_t errors;
	int rc;

	if (atomic_get(&sensor_health) != PUTTTRACK_SENSOR_RECOVERING ||
	    k_uptime_get() < next_sensor_recovery_ms) {
		return;
	}

	increment_saturating(&sensor_recovery_attempt_count);
	sensor_recovery_attempts_in_episode++;
	if (atomic_get(&bmi270_spi_suspended) != 0) {
		rc = pm_device_action_run(bmi270_spi, PM_DEVICE_ACTION_RESUME);
		if (rc == 0) {
			atomic_clear(&bmi270_spi_suspended);
		} else {
			increment_saturating(&power_management_error_count);
		}
	}

	adxl367_ready = device_is_ready(adxl367);
	bmi270_ready = device_is_ready(bmi270);
	errors = 0U;
	if (!adxl367_ready) {
		errors |= SENSOR_ERROR_ADXL367_FETCH;
	}
	if (!bmi270_ready || configure_bmi270_full_scale() != 0) {
		errors |= SENSOR_ERROR_BMI270_FETCH;
	}
	if (errors == 0U && configure_active_sensors() != 0) {
		errors |= SENSOR_ERROR_ADXL367_FETCH | SENSOR_ERROR_BMI270_FETCH;
	}
	for (size_t sample = 0U; errors == 0U && sample < 3U; sample++) {
		errors = verify_active_sensor_samples();
		if (errors == 0U && sample < 2U) {
			k_sleep(K_MSEC(20));
		}
	}

	if (errors == 0U) {
		adxl367_ready = true;
		bmi270_ready = true;
		adxl367_error_streak = 0U;
		bmi270_error_streak = 0U;
		increment_saturating(&sensor_recovery_success_count);
		atomic_set(&sensor_health, PUTTTRACK_SENSOR_HEALTHY);
		sensor_healthy_since_ms = k_uptime_get();
		last_active_motion_ms = k_uptime_get();
		current_stream_rate_hz = MOTION_STREAM_RATE_HZ;
		clear_motion_history();
		return;
	}

	increment_saturating(&sensor_recovery_failure_count);
	last_sensor_error_bits = errors;
	last_sensor_error_uptime_ms = (uint64_t)k_uptime_get();
	adxl367_ready = (errors & (SENSOR_ERROR_ADXL367_FETCH |
				  SENSOR_ERROR_ADXL367_READ)) == 0U;
	bmi270_ready = (errors & (SENSOR_ERROR_BMI270_FETCH |
				SENSOR_ERROR_BMI270_ACCEL |
				SENSOR_ERROR_BMI270_GYRO)) == 0U;
	if (sensor_recovery_attempts_in_episode >= SENSOR_RECOVERY_MAX_ATTEMPTS) {
		atomic_set(&sensor_health, PUTTTRACK_SENSOR_DEGRADED);
		refresh_advertising();
		return;
	}
	next_sensor_recovery_ms = k_uptime_get() +
		recovery_retry_delay_ms(sensor_recovery_attempts_in_episode);
}

static void service_sensor_recovery_policy(void)
{
	enum putttrack_sensor_health health = atomic_get(&sensor_health);
	int64_t now_ms = k_uptime_get();

	if (health == PUTTTRACK_SENSOR_RECOVERING) {
		attempt_sensor_recovery();
		return;
	}
	if (health == PUTTTRACK_SENSOR_HEALTHY) {
		if (sensor_reboot_retention.guard != 0U &&
		    now_ms - sensor_healthy_since_ms >= SENSOR_REBOOT_GUARD_CLEAR_MS) {
			sensor_reboot_retention.guard = 0U;
		}
		return;
	}
	if (health != PUTTTRACK_SENSOR_DEGRADED ||
	    now_ms - last_active_motion_ms < SENSOR_REBOOT_QUIET_MS ||
	    atomic_get(&ble_connected) != 0) {
		return;
	}
	if (sensor_reboot_retention.guard != 0U) {
		atomic_set(&sensor_health, PUTTTRACK_SENSOR_QUARANTINED);
		refresh_advertising();
		return;
	}

	sensor_reboot_retention.guard = 1U;
	increment_saturating(&sensor_reboot_retention.reboot_count);
	sensor_reboot_retention.last_fault_bits = last_sensor_error_bits;
	sys_reboot(SYS_REBOOT_WARM);
}

static bool vector_delta_exceeds(const struct sensor_value values[3],
				 int32_t previous[3], bool *previous_valid,
				 int32_t threshold)
{
	int32_t current[3];
	int64_t squared_delta = 0;
	int64_t squared_threshold = (int64_t)threshold * threshold;

	for (size_t index = 0; index < 3; index++) {
		current[index] = sensor_value_to_i32_micro(&values[index]);
	}
	if (!*previous_valid) {
		memcpy(previous, current, sizeof(current));
		*previous_valid = true;
		return false;
	}
	for (size_t index = 0; index < 3; index++) {
		int64_t delta = (int64_t)current[index] - previous[index];

		squared_delta += delta * delta;
	}
	memcpy(previous, current, sizeof(current));
	return squared_delta >= squared_threshold;
}

static bool gyro_exceeds(const struct sensor_value values[3], int32_t threshold)
{
	for (size_t index = 0; index < 3; index++) {
		int64_t value = sensor_value_to_i32_micro(&values[index]);

		if (value < 0) {
			value = -value;
		}
		if (value >= threshold) {
			return true;
		}
	}
	return false;
}

static bool sample_motion(void)
{
	struct sensor_value adxl_accel[3] = {0};
	struct sensor_value bmi_accel[3] = {0};
	struct sensor_value bmi_gyro[3] = {0};
	uint8_t flags = 0U;
	uint32_t errors = 0U;
	uint8_t snapshot[MOTION_PACKET_SIZE];
	uint64_t source_monotonic_us;
	int rc;
	bool motion_detected = false;

	sequence++;
	if (adxl367_ready) {
		rc = sensor_sample_fetch(adxl367);
		if (rc != 0) {
			errors |= SENSOR_ERROR_ADXL367_FETCH;
		} else if (sensor_channel_get(adxl367, SENSOR_CHAN_ACCEL_XYZ,
					      adxl_accel) != 0) {
			errors |= SENSOR_ERROR_ADXL367_READ;
		} else {
			flags |= MOTION_FLAG_ADXL367_VALID;
		}
	} else {
		errors |= SENSOR_ERROR_ADXL367_FETCH;
	}

	if (bmi270_ready) {
		rc = sensor_sample_fetch(bmi270);
		if (rc != 0) {
			errors |= SENSOR_ERROR_BMI270_FETCH;
		} else {
			if (sensor_channel_get(bmi270, SENSOR_CHAN_ACCEL_XYZ,
					       bmi_accel) != 0) {
				errors |= SENSOR_ERROR_BMI270_ACCEL;
			}
			if (sensor_channel_get(bmi270, SENSOR_CHAN_GYRO_XYZ,
					       bmi_gyro) != 0) {
				errors |= SENSOR_ERROR_BMI270_GYRO;
			}
			if ((errors & (SENSOR_ERROR_BMI270_ACCEL |
				       SENSOR_ERROR_BMI270_GYRO)) == 0U) {
				flags |= MOTION_FLAG_BMI270_VALID;
			}
		}
	} else {
		errors |= SENSOR_ERROR_BMI270_FETCH;
	}

	if ((flags & MOTION_FLAG_ADXL367_VALID) != 0U) {
		motion_detected |= vector_delta_exceeds(
			adxl_accel, active_previous_adxl,
			&active_previous_adxl_valid, ACTIVE_DELTA_MICRO_MS2);
	}
	if ((flags & MOTION_FLAG_BMI270_VALID) != 0U) {
		motion_detected |= gyro_exceeds(bmi_gyro, ACTIVE_GYRO_MICRO_RADS);
	}

	memset(snapshot, 0, sizeof(snapshot));
	snapshot[0] = PUTTTRACK_PROTOCOL_VERSION;
	snapshot[1] = flags;
	sys_put_le16(MOTION_PACKET_SIZE, &snapshot[2]);
	sys_put_le32(sequence, &snapshot[4]);
	source_monotonic_us = k_ticks_to_us_floor64(k_uptime_ticks());
	sys_put_le64(source_monotonic_us, &snapshot[8]);

	for (size_t index = 0; index < 3; index++) {
		sys_put_le32(sensor_value_to_i32_micro(&adxl_accel[index]),
			     &snapshot[16 + index * 4]);
		sys_put_le32(sensor_value_to_i32_micro(&bmi_accel[index]),
			     &snapshot[28 + index * 4]);
		sys_put_le32(sensor_value_to_i32_micro(&bmi_gyro[index]),
			     &snapshot[40 + index * 4]);
	}
	if ((flags & MOTION_FLAG_ADXL367_VALID) != 0U &&
	    packet_vector_clipped(snapshot, 16U, ADXL367_CLIP_MICRO_MS2)) {
		adxl367_clip_count++;
	}
	if ((flags & MOTION_FLAG_BMI270_VALID) != 0U &&
	    packet_vector_clipped(snapshot, 28U, BMI270_ACCEL_CLIP_MICRO_MS2)) {
		bmi270_accel_clip_count++;
	}
	if ((flags & MOTION_FLAG_BMI270_VALID) != 0U &&
	    packet_vector_clipped(snapshot, 40U, BMI270_GYRO_CLIP_MICRO_RADS)) {
		bmi270_gyro_clip_count++;
	}
	sys_put_le32(errors, &snapshot[52]);
#if defined(CONFIG_PUTTTRACK_STROKE_PICKUP_V1)
    struct spv1_sample shadow_sample = {
        .sequence = sequence, .time_us = source_monotonic_us,
        .valid = (flags & MOTION_FLAG_BMI270_VALID) != 0U, .sensor_errors = errors,
    };
    for (size_t i = 0U; i < 3U; i++) {
        shadow_sample.accel_micro[i] = (int32_t)sys_get_le32(&snapshot[28U + i * 4U]);
        shadow_sample.gyro_micro[i] = (int32_t)sys_get_le32(&snapshot[40U + i * 4U]);
    }
    k_mutex_lock(&shadow_engine_mutex, K_FOREVER);
    spv1_push(&shadow_engine, &shadow_sample);
    k_mutex_unlock(&shadow_engine_mutex);
#endif


#if defined(CONFIG_PUTTTRACK_MOTION_DEMO_V0)
	struct motion_demo_v0_sample demo_sample = {
		.sequence = sequence,
		.source_monotonic_us = source_monotonic_us,
		.bmi270_valid = (flags & MOTION_FLAG_BMI270_VALID) != 0U,
		.sensor_error_bits = errors,
	};
	for (size_t index = 0; index < 3; index++) {
		demo_sample.accel_micro_ms2[index] =
			(int32_t)sys_get_le32(&snapshot[28 + index * 4U]);
		demo_sample.gyro_micro_rads[index] =
			(int32_t)sys_get_le32(&snapshot[40 + index * 4U]);
	}
	k_mutex_lock(&motion_demo_mutex, K_FOREVER);
	(void)motion_demo_v0_push(&motion_demo, &demo_sample);
	k_mutex_unlock(&motion_demo_mutex);
#endif

	k_mutex_lock(&packet_mutex, K_FOREVER);
	memcpy(motion_packet, snapshot, sizeof(motion_packet));
	memcpy(motion_ring[motion_ring_write_index], snapshot, sizeof(snapshot));
	motion_ring_write_index = (motion_ring_write_index + 1U) % MOTION_HISTORY_SAMPLES;
	if (motion_ring_count < MOTION_HISTORY_SAMPLES) {
		motion_ring_count++;
	}
	k_mutex_unlock(&packet_mutex);

	if (atomic_get(&notify_enabled) != 0) {
		rc = bt_gatt_notify(NULL, &putttrack_service.attrs[4],
				    snapshot, sizeof(snapshot));
		if (rc != 0 && rc != -ENOTCONN) {
			notify_drop_count++;
		}
	}
	record_sensor_sample_result(errors);

	return motion_detected;
}

static bool sample_idle_wake_sensor(void)
{
	struct sensor_value adxl_accel[3] = {0};
	int32_t current[3];
	int64_t squared_delta = 0;
	const int64_t squared_threshold =
		(int64_t)IDLE_WAKE_DELTA_MICRO_MS2 * IDLE_WAKE_DELTA_MICRO_MS2;

	if (!adxl367_ready || sensor_sample_fetch(adxl367) != 0) {
		record_sensor_sample_result(SENSOR_ERROR_ADXL367_FETCH);
		return false;
	}
	if (sensor_channel_get(adxl367, SENSOR_CHAN_ACCEL_XYZ, adxl_accel) != 0) {
		record_sensor_sample_result(SENSOR_ERROR_ADXL367_READ);
		return false;
	}
	record_sensor_sample_result(0U);
	for (size_t index = 0; index < 3; index++) {
		current[index] = sensor_value_to_i32_micro(&adxl_accel[index]);
	}
	if (!idle_adxl_baseline_valid) {
		memcpy(idle_adxl_baseline, current, sizeof(current));
		idle_adxl_baseline_valid = true;
		idle_wake_samples = 0U;
		return false;
	}
	for (size_t index = 0; index < 3; index++) {
		int64_t delta = (int64_t)current[index] - idle_adxl_baseline[index];

		squared_delta += delta * delta;
	}
	if (squared_delta >= squared_threshold) {
		idle_wake_samples++;
		return idle_wake_samples >= IDLE_WAKE_REQUIRED_SAMPLES;
	}

	idle_wake_samples = 0U;
	for (size_t index = 0; index < 3; index++) {
		idle_adxl_baseline[index] =
			(int32_t)(((int64_t)idle_adxl_baseline[index] * 7 +
				   current[index]) / 8);
	}
	return false;
}

static bool enter_idle_state(void)
{
	int rc;

	if (atomic_get(&runtime_state) == PUTTTRACK_RUNTIME_IDLE) {
		return true;
	}
	if (configure_idle_sensors() != 0) {
		begin_sensor_recovery(SENSOR_ERROR_ADXL367_FETCH |
				      SENSOR_ERROR_BMI270_FETCH);
		return false;
	}
	if (adxl367_ready) {
		rc = enable_idle_wake_interrupt();
		if (rc != 0) {
			increment_saturating(&power_management_error_count);
			begin_sensor_recovery(SENSOR_ERROR_ADXL367_FETCH);
			return false;
		}
		rc = set_adxl367_wakeup_mode(true);
		if (rc != 0) {
			increment_saturating(&power_management_error_count);
			begin_sensor_recovery(SENSOR_ERROR_ADXL367_FETCH);
			return false;
		}
	} else {
		begin_sensor_recovery(SENSOR_ERROR_ADXL367_FETCH);
		return false;
	}
	if (bmi270_ready && atomic_get(&bmi270_spi_suspended) == 0) {
		rc = pm_device_action_run(bmi270_spi, PM_DEVICE_ACTION_SUSPEND);
		if (rc == 0) {
			atomic_set(&bmi270_spi_suspended, 1);
		} else {
			increment_saturating(&power_management_error_count);
		}
	}
	current_stream_rate_hz = 0U;
	idle_adxl_baseline_valid = false;
	idle_wake_samples = 0U;
	last_idle_sensor_health_check_ms = k_uptime_get();
	atomic_set(&runtime_state, PUTTTRACK_RUNTIME_IDLE);
	current_adv_interval_min_ms = IDLE_ADV_INTERVAL_MIN_MS;
	current_adv_interval_max_ms = IDLE_ADV_INTERVAL_MAX_MS;
	power_transition_count++;
	refresh_advertising();
	return true;
}

static bool enter_active_state(void)
{
	int rc;

	if (atomic_get(&runtime_state) == PUTTTRACK_RUNTIME_ACTIVE) {
		return true;
	}
	if (disable_idle_wake_interrupt() != 0) {
		increment_saturating(&power_management_error_count);
		begin_sensor_recovery(SENSOR_ERROR_ADXL367_FETCH);
		return false;
	}
	if (adxl367_ready && set_adxl367_wakeup_mode(false) != 0) {
		increment_saturating(&power_management_error_count);
		begin_sensor_recovery(SENSOR_ERROR_ADXL367_FETCH);
		return false;
	}
	if (bmi270_ready && atomic_get(&bmi270_spi_suspended) != 0) {
		rc = pm_device_action_run(bmi270_spi, PM_DEVICE_ACTION_RESUME);
		if (rc != 0) {
			increment_saturating(&power_management_error_count);
			begin_sensor_recovery(SENSOR_ERROR_BMI270_FETCH);
			return false;
		}
		atomic_clear(&bmi270_spi_suspended);
	}
	if (configure_active_sensors() != 0) {
		begin_sensor_recovery(SENSOR_ERROR_ADXL367_FETCH |
				      SENSOR_ERROR_BMI270_FETCH);
		return false;
	}
	clear_motion_history();
	current_stream_rate_hz = MOTION_STREAM_RATE_HZ;
	active_previous_adxl_valid = false;
	last_active_motion_ms = k_uptime_get();
	atomic_set(&runtime_state, PUTTTRACK_RUNTIME_ACTIVE);
	current_adv_interval_min_ms = 100U;
	current_adv_interval_max_ms = 150U;
	power_transition_count++;
	refresh_advertising();
	return true;
}

#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
static void nfc_callback(void *context, nfc_t2t_event_t event,
			 const uint8_t *data, size_t data_length)
{
	ARG_UNUSED(context);
	ARG_UNUSED(data);
	ARG_UNUSED(data_length);

	switch (event) {
	case NFC_T2T_EVENT_FIELD_ON:
		atomic_inc(&nfc_field_on_count);
#if defined(CONFIG_PUTTTRACK_NFC_SYSTEM_OFF_TEST)
		if (atomic_cas(&system_off_pending, 1, 0)) {
			(void)k_work_cancel_delayable(&system_off_work);
			system_off_entry_error = -EBUSY;
		}
#endif
		if (atomic_cas(&nfc_field_present, 0, 1)) {
			(void)k_work_submit(&nfc_service_window_open_work);
		} else {
			atomic_inc(&nfc_service_window_suppressed_count);
		}
		break;
	case NFC_T2T_EVENT_FIELD_OFF:
		atomic_inc(&nfc_field_off_count);
		atomic_clear(&nfc_field_present);
		break;
	case NFC_T2T_EVENT_DATA_READ:
		atomic_inc(&nfc_data_read_count);
		break;
	default:
		break;
	}
}

static int initialize_nfc_service(void)
{
	char device_id_hex[DEVICE_ID_MAX_SIZE * 2U + 1U];
	char uri[NFC_URI_BUFFER_SIZE];
	uint32_t ndef_length = sizeof(nfc_ndef_buffer);
	int uri_length;
	int rc;

	bytes_to_hex(device_id, device_id_len, device_id_hex);
	device_id_hex[device_id_len * 2U] = '\0';
	uri_length = snprintf(uri, sizeof(uri),
			      "putttrack://service/tag/%s?fw=%s",
			      device_id_hex, PUTTTRACK_FIRMWARE_VERSION);
	if (uri_length < 0 || (size_t)uri_length >= sizeof(uri)) {
		nfc_setup_error = -ENOSPC;
		return nfc_setup_error;
	}

	/*
	 * An OTA candidate may boot through the already-installed v0.1.13
	 * MCUboot image, whose board definition selects these pads as GPIO. Restore
	 * NFCT mode before nrfx validates PADCONFIG so the first NFC experiment does
	 * not require replacing MCUboot over SWD.
	 */
	nrf_nfct_pad_config_enable_set(NRF_NFCT, true);
	rc = nfc_t2t_setup(nfc_callback, NULL);
	if (rc == 0) {
		rc = nfc_ndef_uri_msg_encode(NFC_URI_NONE,
					     (const uint8_t *)uri,
					     (uint16_t)uri_length,
					     nfc_ndef_buffer,
					     &ndef_length);
	}
	if (rc == 0) {
		rc = nfc_t2t_payload_set(nfc_ndef_buffer, ndef_length);
	}
	if (rc == 0) {
		rc = nfc_t2t_emulation_start();
	}
	nfc_setup_error = rc;

	return rc;
}
#endif

int main(void)
{
	int64_t next_sample_ms;
	uint32_t previous_period_ms = 0U;

    initialize_sensor_reboot_retention();
#if defined(CONFIG_PUTTTRACK_STROKE_PICKUP_V1)
    spv1_init(&shadow_engine);
#endif
#if defined(CONFIG_PUTTTRACK_MOTION_DEMO_V0)
	motion_demo_v0_init(&motion_demo);
#endif
	initialize_identity();
	initialize_advertising_name();
	scan_response_data[0].data_len = (uint8_t)strlen(advertising_name);
	k_work_init_delayable(&advertise_work, advertise);
#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
	k_work_init(&nfc_service_window_open_work, open_nfc_service_window);
	k_work_init_delayable(&nfc_service_window_close_work,
			      close_nfc_service_window);
#if defined(CONFIG_PUTTTRACK_NFC_SYSTEM_OFF_TEST)
	k_work_init_delayable(&system_off_work, enter_system_off);
#endif
#endif
	sample_battery();
	initialize_sensors();
	if (bt_enable(NULL) == 0) {
		atomic_set(&bluetooth_ready, 1);
		(void)k_work_reschedule(&advertise_work, K_NO_WAIT);
	}
#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
	if (initialize_nfc_service() == 0 && nfc_system_off_wake) {
		(void)k_work_submit(&nfc_service_window_open_work);
	}
#endif
	build_status_packet();

	next_sample_ms = k_uptime_get();
	while (true) {
		enum putttrack_power_policy policy = atomic_get(&power_policy);
		enum putttrack_runtime_state state = atomic_get(&runtime_state);
		enum putttrack_sensor_health health;
		uint32_t period_ms;
		uint32_t idle_health_interval_ms;
		int64_t now_ms;
		int64_t guard_wait_ms;
		int64_t idle_health_wait_ms;
		int64_t event_wait_ms;

		service_sensor_recovery_policy();
		health = atomic_get(&sensor_health);
		if (health == PUTTTRACK_SENSOR_RECOVERING ||
		    health == PUTTTRACK_SENSOR_DEGRADED ||
		    health == PUTTTRACK_SENSOR_QUARANTINED) {
			previous_period_ms = 250U;
			k_sleep(K_MSEC(250));
			continue;
		}

		if (policy == PUTTTRACK_POWER_IDLE &&
		    state != PUTTTRACK_RUNTIME_IDLE) {
			(void)enter_idle_state();
		} else if (policy == PUTTTRACK_POWER_RESEARCH &&
			   state != PUTTTRACK_RUNTIME_ACTIVE) {
			(void)enter_active_state();
		}

		state = atomic_get(&runtime_state);
		if (state == PUTTTRACK_RUNTIME_ACTIVE) {
			if (sample_motion()) {
				last_active_motion_ms = k_uptime_get();
			}
			if (policy == PUTTTRACK_POWER_AUTO &&
			    atomic_get(&sensor_health) == PUTTTRACK_SENSOR_HEALTHY &&
			    k_uptime_get() - last_active_motion_ms >= AUTO_IDLE_TIMEOUT_MS) {
				(void)enter_idle_state();
			}
		} else if (atomic_get(&idle_wake_interrupt_enabled) != 0) {
			if (atomic_cas(&idle_wake_requested, 1, 0) &&
			    policy == PUTTTRACK_POWER_AUTO) {
				(void)enter_active_state();
			} else {
				idle_health_interval_ms =
					atomic_get(&sensor_health) == PUTTTRACK_SENSOR_SUSPECT ?
					SUSPECT_SENSOR_HEALTH_CHECK_MS :
					IDLE_SENSOR_HEALTH_CHECK_MS;
				if (k_uptime_get() - last_idle_sensor_health_check_ms >=
				    idle_health_interval_ms) {
					last_idle_sensor_health_check_ms = k_uptime_get();
					if (sample_idle_wake_sensor() &&
					    policy == PUTTTRACK_POWER_AUTO) {
						(void)enter_active_state();
					}
				}
			}
		} else if (sample_idle_wake_sensor() &&
			   policy == PUTTTRACK_POWER_AUTO) {
			(void)enter_active_state();
		}

		state = atomic_get(&runtime_state);
		if (state == PUTTTRACK_RUNTIME_IDLE &&
		    atomic_get(&idle_wake_interrupt_enabled) != 0) {
			previous_period_ms = 0U;
			health = atomic_get(&sensor_health);
			idle_health_interval_ms =
				health == PUTTTRACK_SENSOR_SUSPECT ?
				SUSPECT_SENSOR_HEALTH_CHECK_MS :
				IDLE_SENSOR_HEALTH_CHECK_MS;
			idle_health_wait_ms = idle_health_interval_ms -
				(k_uptime_get() - last_idle_sensor_health_check_ms);
			event_wait_ms = idle_health_wait_ms;
			guard_wait_ms = SENSOR_REBOOT_GUARD_CLEAR_MS -
				(k_uptime_get() - sensor_healthy_since_ms);
			if (sensor_reboot_retention.guard != 0U && guard_wait_ms > 0 &&
			    guard_wait_ms < event_wait_ms) {
				event_wait_ms = guard_wait_ms;
			}
			if (event_wait_ms > 0) {
				(void)k_sem_take(&power_event_sem, K_MSEC(event_wait_ms));
			} else {
				k_yield();
			}
			continue;
		}
		period_ms = state == PUTTTRACK_RUNTIME_ACTIVE ?
			20U : IDLE_WAKE_SAMPLE_PERIOD_MS;
		now_ms = k_uptime_get();
		if (period_ms != previous_period_ms) {
			next_sample_ms = now_ms + period_ms;
		} else {
			next_sample_ms += period_ms;
			if (next_sample_ms <= now_ms) {
				next_sample_ms = now_ms + period_ms;
			}
		}
		previous_period_ms = period_ms;
		k_sleep(K_TIMEOUT_ABS_MS(next_sample_ms));
	}

	return 0;
}
