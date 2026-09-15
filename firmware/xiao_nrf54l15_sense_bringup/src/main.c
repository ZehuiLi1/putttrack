/* SPDX-License-Identifier: Apache-2.0 */
#include <zephyr/kernel.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/hwinfo.h>
#include <zephyr/drivers/regulator.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/sys/atomic.h>
#include <hal/nrf_nfct.h>
#include <nfc_t2t_lib.h>
#include <nfc/ndef/uri_msg.h>
#include <stdio.h>
#include <string.h>

#define FW "xiao02"
static atomic_t field_on, field_off, data_reads, field_present;
static uint8_t ndef[160];
static char identity[33];
static int nfc_error;
static bool imu_ready;
static int imu_init_error;
static uint8_t imu_chip_id;
static uint32_t samples, errors;
static struct sensor_value accel[3], gyro[3];
static struct k_mutex status_lock;
static char status_json[512];
static char ble_name[24];
static void advertise(struct k_work *work);
K_WORK_DELAYABLE_DEFINE(adv_work, advertise);
static void advertise(struct k_work *work)
{
    ARG_UNUSED(work);
    const struct bt_data ad[] = {BT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)};
    const struct bt_data sd[] = {BT_DATA(BT_DATA_NAME_COMPLETE, ble_name, strlen(ble_name))};
    int rc = bt_le_adv_start(BT_LE_ADV_CONN_FAST_2, ad, ARRAY_SIZE(ad), sd, ARRAY_SIZE(sd));
    if (rc && rc != -EALREADY) k_work_reschedule(&adv_work, K_MSEC(500));
}
static void recycled(void) { k_work_reschedule(&adv_work, K_MSEC(250)); }
BT_CONN_CB_DEFINE(connection_callbacks) = { .recycled = recycled };

static ssize_t read_status(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                           void *buf, uint16_t len, uint16_t offset)
{
    /* One BLE connection: freeze the full response across ATT Read Blob offsets. */
    static char snapshot[sizeof(status_json)];
    if (offset == 0) {
        k_mutex_lock(&status_lock, K_FOREVER);
        memcpy(snapshot, status_json, sizeof(snapshot));
        k_mutex_unlock(&status_lock);
    }
    return bt_gatt_attr_read(conn, attr, buf, len, offset, snapshot, strlen(snapshot));
}
/* Dedicated diagnostic service: does not impersonate the production motion protocol. */
BT_GATT_SERVICE_DEFINE(diag,
 BT_GATT_PRIMARY_SERVICE(BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0x8f3a2000,0x6e7d,0x4b9a,0xa6e8,0x3f3f7d2c0001))),
 BT_GATT_CHARACTERISTIC(BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0x8f3a2001,0x6e7d,0x4b9a,0xa6e8,0x3f3f7d2c0001)),
 BT_GATT_CHRC_READ, BT_GATT_PERM_READ, read_status, NULL, NULL));

static void nfc_callback(void *ctx, nfc_t2t_event_t event, const uint8_t *data, size_t len)
{
    ARG_UNUSED(ctx); ARG_UNUSED(data); ARG_UNUSED(len);
    if (event == NFC_T2T_EVENT_FIELD_ON) { atomic_inc(&field_on); atomic_set(&field_present, 1); }
    if (event == NFC_T2T_EVENT_FIELD_OFF) { atomic_inc(&field_off); atomic_clear(&field_present); }
    if (event == NFC_T2T_EVENT_DATA_READ) { atomic_inc(&data_reads); }
}
static int nfc_start(void)
{
    char uri[96];
    uint32_t len = sizeof(ndef);
    snprintf(uri, sizeof(uri), "putttrack://service/tag/%s?fw=" FW, identity);
    nrf_nfct_pad_config_enable_set(NRF_NFCT, true);
    int rc = nfc_t2t_setup(nfc_callback, NULL);
    if (!rc) rc = nfc_ndef_uri_msg_encode(NFC_URI_NONE, (uint8_t *)uri, strlen(uri), ndef, &len);
    if (!rc) rc = nfc_t2t_payload_set(ndef, len);
    if (!rc) rc = nfc_t2t_emulation_start();
    return rc;
}
static void update_status(void)
{
    k_mutex_lock(&status_lock, K_FOREVER);
    snprintf(status_json, sizeof(status_json),
        "{\"event\":\"status\",\"device_id\":\"%s\",\"fw\":\"" FW "\","
        "\"uptime_ms\":%u,\"imu_ready\":%s,\"imu_init_error\":%d,\"imu_chip_id\":%u,\"imu_odr_hz\":104,\"samples\":%u,\"sensor_errors\":%u,"
        "\"nfc_setup_error\":%d,\"nfc_field_present\":%s,\"nfc_field_on\":%d,\"nfc_field_off\":%d,\"nfc_data_reads\":%d}",
        identity, k_uptime_get_32(), imu_ready ? "true":"false", imu_init_error, imu_chip_id, samples, errors, nfc_error,
        atomic_get(&field_present) ? "true":"false", (int)atomic_get(&field_on), (int)atomic_get(&field_off), (int)atomic_get(&data_reads));
    printk("%s\n", status_json);
    k_mutex_unlock(&status_lock);
}
static int64_t micro(const struct sensor_value *v) { return (int64_t)v->val1 * 1000000 + v->val2; }
static int initialize_imu(const struct device *imu)
{
    const struct device *power = DEVICE_DT_GET(DT_NODELABEL(pdm_imu_pwr));
    const struct i2c_dt_spec bus = I2C_DT_SPEC_GET(DT_ALIAS(imu0));
    if (!device_is_ready(power) || !i2c_is_ready_dt(&bus)) return -ENODEV;
    /* Start from an unpowered sensor even after MCU-only resets. */
    k_msleep(100);
    int rc = regulator_enable(power);
    if (rc) return rc;
    k_msleep(100);
    rc = i2c_reg_read_byte_dt(&bus, 0x0f, &imu_chip_id);
    if (rc) return rc;
    if (imu_chip_id != 0x6a) return -ENODEV;
    return device_init(imu);
}
int main(void)
{
    k_mutex_init(&status_lock);
    uint8_t id[16];
    ssize_t size = hwinfo_get_device_id(id, sizeof(id));
    if (size <= 0) { printk("{\"event\":\"fatal\",\"error\":\"identity_unavailable\"}\n"); return 0; }
    for (int i=0; i<size; ++i) snprintf(identity+i*2, 3, "%02x", id[i]);
    printk("{\"event\":\"boot\",\"app\":\"putttrack-xiao-sense\",\"device_id\":\"%s\"}\n", identity);
    const struct device *imu = DEVICE_DT_GET(DT_ALIAS(imu0));
    imu_init_error = initialize_imu(imu);
    imu_ready = imu_init_error == 0 && device_is_ready(imu);
    printk("{\"event\":\"imu_init\",\"error\":%d,\"chip_id\":%u}\n", imu_init_error, imu_chip_id);
    nfc_error = nfc_start();
    update_status();
    int rc = bt_enable(NULL);
    if (!rc) {
        snprintf(ble_name,sizeof(ble_name),"PT-XIAO-%.8s",identity);
        rc = bt_set_name(ble_name);
        if (!rc) {
            const struct bt_data ad[] = {BT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)};
            const struct bt_data sd[] = {BT_DATA(BT_DATA_NAME_COMPLETE, ble_name, strlen(ble_name))};
            rc = bt_le_adv_start(BT_LE_ADV_CONN_FAST_2,ad,ARRAY_SIZE(ad),sd,ARRAY_SIZE(sd));
            if (rc) k_work_reschedule(&adv_work, K_MSEC(500));
        }
    }
    printk("{\"event\":\"ble_ready\",\"error\":%d}\n",rc);
    /* Wait for initial conversions before publishing the first sample. */
    k_msleep(30);
    int64_t deadline = k_uptime_get();
    uint32_t ticks = 0;
    for (;;) {
        if (imu_ready) {
            rc = sensor_sample_fetch(imu);
            if (!rc) rc = sensor_channel_get(imu,SENSOR_CHAN_ACCEL_XYZ,accel);
            if (!rc) rc = sensor_channel_get(imu,SENSOR_CHAN_GYRO_XYZ,gyro);
            if (!rc) {
                samples++;
                if (ticks % 5 == 0) printk("{\"event\":\"imu\",\"uptime_ms\":%u,\"accel_um_s2\":[%lld,%lld,%lld],\"gyro_urad_s\":[%lld,%lld,%lld]}\n",
                    k_uptime_get_32(),micro(&accel[0]),micro(&accel[1]),micro(&accel[2]),micro(&gyro[0]),micro(&gyro[1]),micro(&gyro[2]));
            } else { errors++; }
        }
        if (ticks++ % 50 == 0) update_status();
        deadline += 20;
        k_sleep(K_TIMEOUT_ABS_MS(deadline));
    }
}
