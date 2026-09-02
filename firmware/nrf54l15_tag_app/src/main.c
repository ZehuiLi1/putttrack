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
#include <zephyr/drivers/hwinfo.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/mgmt/mcumgr/mgmt/handlers.h>
#include <zephyr/mgmt/mcumgr/mgmt/mgmt.h>
#include <zephyr/mgmt/mcumgr/smp/smp.h>
#include <zephyr/mgmt/mcumgr/transport/smp_bt.h>
#include <zephyr/pm/device.h>
#include <zephyr/random/random.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/util.h>
#include <zcbor_encode.h>

#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
#include <hal/nrf_nfct.h>
#include <nfc_t2t_lib.h>
#include <nfc/ndef/uri_msg.h>
#endif

#define PUTTTRACK_PROTOCOL_VERSION 1U
#define PUTTTRACK_FIRMWARE_VERSION "0.1.14"

#define PUTTTRACK_MGMT_GROUP_ID 64U
#define PUTTTRACK_MGMT_ID_STATUS 0U
#define PUTTTRACK_MGMT_ID_MOTION 1U
#define PUTTTRACK_MGMT_ID_WINDOW 2U
#define PUTTTRACK_MGMT_ID_FREEZE_HISTORY 3U
#define PUTTTRACK_MGMT_ID_FROZEN_CHUNK_BASE 4U
#define PUTTTRACK_MGMT_ID_POWER_AUTO 20U
#define PUTTTRACK_MGMT_ID_POWER_RESEARCH 21U
#define PUTTTRACK_MGMT_ID_POWER_IDLE 22U

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
static uint32_t notify_drop_count;
static uint32_t adxl367_clip_count;
static uint32_t bmi270_accel_clip_count;
static uint32_t bmi270_gyro_clip_count;
static bool adxl367_ready;
static bool bmi270_ready;
static atomic_t notify_enabled;
static atomic_t ble_connected;
static atomic_t power_policy = ATOMIC_INIT(PUTTTRACK_POWER_AUTO);
static atomic_t runtime_state = ATOMIC_INIT(PUTTTRACK_RUNTIME_ACTIVE);
static uint32_t power_transition_count;
static uint32_t advertising_start_error_count;
static uint32_t power_management_error_count;
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
static int32_t active_previous_adxl[3];
static bool active_previous_adxl_valid;
static int32_t idle_adxl_baseline[3];
static bool idle_adxl_baseline_valid;
static uint8_t idle_wake_samples;
static struct k_work_delayable advertise_work;

#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
#define NFC_NDEF_BUFFER_SIZE 160U
#define NFC_URI_BUFFER_SIZE 96U

static uint8_t nfc_ndef_buffer[NFC_NDEF_BUFFER_SIZE];
static atomic_t nfc_field_on_count;
static atomic_t nfc_field_off_count;
static int32_t nfc_setup_error;
#endif

K_MUTEX_DEFINE(packet_mutex);
K_SEM_DEFINE(power_event_sem, 0, 1);

static void build_status_packet(void);

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
	const char *policy_text = power_policy_name(policy);
	const char *state_text = runtime_state_name(state);
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
	uint32_t status_sequence;
	bool ok;

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
	     zcbor_bool_put(zse, false);

#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
	ok = ok &&
	     zcbor_tstr_put_lit(zse, "nfc_enabled") &&
	     zcbor_bool_put(zse, true) &&
	     zcbor_tstr_put_lit(zse, "nfc_setup_error") &&
	     zcbor_int32_put(zse, nfc_setup_error) &&
	     zcbor_tstr_put_lit(zse, "nfc_field_on") &&
	     zcbor_uint32_put(zse, (uint32_t)atomic_get(&nfc_field_on_count)) &&
	     zcbor_tstr_put_lit(zse, "nfc_field_off") &&
	     zcbor_uint32_put(zse, (uint32_t)atomic_get(&nfc_field_off_count));
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

static const struct mgmt_handler putttrack_mgmt_handlers[] = {
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
	int rc;

	ARG_UNUSED(work);
	if (atomic_get(&runtime_state) == PUTTTRACK_RUNTIME_IDLE) {
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
	if (atomic_get(&ble_connected) != 0) {
		return;
	}
	(void)bt_le_adv_stop();
	(void)k_work_reschedule(&advertise_work, K_NO_WAIT);
}

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
		sensor_error_count += failures;
		return -EIO;
	}
	return 0;
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
		sensor_error_count += failures;
		return -EIO;
	}
	return 0;
}

static void initialize_sensors(void)
{
	struct sensor_value value;

	adxl367_ready = device_is_ready(adxl367);
	bmi270_ready = device_is_ready(bmi270);

	if (bmi270_ready) {
		value = (struct sensor_value){.val1 = 16, .val2 = 0};
		if (sensor_attr_set(bmi270, SENSOR_CHAN_ACCEL_XYZ,
				    SENSOR_ATTR_FULL_SCALE, &value) != 0) {
			sensor_error_count++;
		}
		value = (struct sensor_value){.val1 = 2000, .val2 = 0};
		if (sensor_attr_set(bmi270, SENSOR_CHAN_GYRO_XYZ,
				    SENSOR_ATTR_FULL_SCALE, &value) != 0) {
			sensor_error_count++;
		}
	}

	(void)configure_active_sensors();
	last_active_motion_ms = k_uptime_get();
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
	}

	if (errors != 0U) {
		sensor_error_count++;
		motion_detected = true;
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
	sys_put_le64(k_ticks_to_us_floor64(k_uptime_ticks()), &snapshot[8]);

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

	return motion_detected;
}

static bool sample_idle_wake_sensor(void)
{
	struct sensor_value adxl_accel[3] = {0};
	int32_t current[3];
	int64_t squared_delta = 0;
	const int64_t squared_threshold =
		(int64_t)IDLE_WAKE_DELTA_MICRO_MS2 * IDLE_WAKE_DELTA_MICRO_MS2;

	if (!adxl367_ready || sensor_sample_fetch(adxl367) != 0 ||
	    sensor_channel_get(adxl367, SENSOR_CHAN_ACCEL_XYZ, adxl_accel) != 0) {
		sensor_error_count++;
		return false;
	}
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
		return false;
	}
	if (adxl367_ready) {
		rc = enable_idle_wake_interrupt();
		if (rc != 0) {
			power_management_error_count++;
		}
		rc = set_adxl367_wakeup_mode(true);
		if (rc != 0) {
			power_management_error_count++;
		}
	}
	if (bmi270_ready && atomic_get(&bmi270_spi_suspended) == 0) {
		rc = pm_device_action_run(bmi270_spi, PM_DEVICE_ACTION_SUSPEND);
		if (rc == 0) {
			atomic_set(&bmi270_spi_suspended, 1);
		} else {
			power_management_error_count++;
		}
	}
	current_stream_rate_hz = 0U;
	idle_adxl_baseline_valid = false;
	idle_wake_samples = 0U;
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
		power_management_error_count++;
		return false;
	}
	if (adxl367_ready && set_adxl367_wakeup_mode(false) != 0) {
		power_management_error_count++;
		return false;
	}
	if (bmi270_ready && atomic_get(&bmi270_spi_suspended) != 0) {
		rc = pm_device_action_run(bmi270_spi, PM_DEVICE_ACTION_RESUME);
		if (rc != 0) {
			power_management_error_count++;
			return false;
		}
		atomic_clear(&bmi270_spi_suspended);
	}
	if (configure_active_sensors() != 0) {
		return false;
	}
	k_mutex_lock(&packet_mutex, K_FOREVER);
	motion_ring_write_index = 0U;
	motion_ring_count = 0U;
	k_mutex_unlock(&packet_mutex);
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
		break;
	case NFC_T2T_EVENT_FIELD_OFF:
		atomic_inc(&nfc_field_off_count);
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

	initialize_identity();
	initialize_advertising_name();
	scan_response_data[0].data_len = (uint8_t)strlen(advertising_name);
	initialize_sensors();
#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
	(void)initialize_nfc_service();
#endif
	build_status_packet();

	k_work_init_delayable(&advertise_work, advertise);
	if (bt_enable(NULL) == 0) {
		(void)k_work_reschedule(&advertise_work, K_NO_WAIT);
	}

	next_sample_ms = k_uptime_get();
	while (true) {
		enum putttrack_power_policy policy = atomic_get(&power_policy);
		enum putttrack_runtime_state state = atomic_get(&runtime_state);
		uint32_t period_ms;
		int64_t now_ms;

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
			    k_uptime_get() - last_active_motion_ms >= AUTO_IDLE_TIMEOUT_MS) {
				(void)enter_idle_state();
			}
		} else if (atomic_get(&idle_wake_interrupt_enabled) != 0) {
			if (atomic_cas(&idle_wake_requested, 1, 0) &&
			    policy == PUTTTRACK_POWER_AUTO) {
				(void)enter_active_state();
			}
		} else if (sample_idle_wake_sensor() &&
			   policy == PUTTTRACK_POWER_AUTO) {
			(void)enter_active_state();
		}

		state = atomic_get(&runtime_state);
		if (state == PUTTTRACK_RUNTIME_IDLE &&
		    atomic_get(&idle_wake_interrupt_enabled) != 0) {
			previous_period_ms = 0U;
			k_sem_take(&power_event_sem, K_FOREVER);
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
