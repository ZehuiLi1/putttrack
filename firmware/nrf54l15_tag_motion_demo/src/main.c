/*
 * PuttTrack embedded-motion demo firmware.
 *
 * This translation unit reuses the physically proven nrf54l15_tag_app source
 * unchanged, then adds a separate research-only Motion Evidence service and a
 * polling thread that consumes the already-produced 50 Hz raw motion packet.
 * No player/hole/score authority is added to the Ball.
 */

#ifndef PT_BASELINE_MAIN_SOURCE
#define PT_BASELINE_MAIN_SOURCE "../../nrf54l15_tag_app/src/main.c"
#endif
#include PT_BASELINE_MAIN_SOURCE
#include "motion_engine.h"

#define MOTION_EVIDENCE_PACKET_SIZE 28U
#define MOTION_EVIDENCE_PROTOCOL_VERSION 1U
#define MOTION_EVIDENCE_THREAD_STACK 3072U
#define MOTION_EVIDENCE_THREAD_PRIORITY 6

/* Separate demo service so the proven raw telemetry service stays byte-stable. */
static const struct bt_uuid_128 putttrack_motion_evidence_service_uuid =
    BT_UUID_INIT_128(BT_UUID_128_ENCODE(
        0x8f3a1100, 0x6e7d, 0x4b9a, 0xa6e8, 0x3f3f7d2c0001));
static const struct bt_uuid_128 putttrack_motion_evidence_uuid =
    BT_UUID_INIT_128(BT_UUID_128_ENCODE(
        0x8f3a1101, 0x6e7d, 0x4b9a, 0xa6e8, 0x3f3f7d2c0001));

static struct pt_motion_engine embedded_motion_engine;
static uint8_t motion_evidence_packet[MOTION_EVIDENCE_PACKET_SIZE];
static atomic_t motion_evidence_notify_enabled;
static uint32_t motion_evidence_notify_drop_count;

static void encode_motion_evidence_packet(const struct pt_motion_output *output,
                                          uint8_t packet[MOTION_EVIDENCE_PACKET_SIZE])
{
    memset(packet, 0, MOTION_EVIDENCE_PACKET_SIZE);
    packet[0] = MOTION_EVIDENCE_PROTOCOL_VERSION;
    packet[1] = (uint8_t)output->state;
    sys_put_le16(output->event_bits, &packet[2]);
    sys_put_le32(output->source_sequence, &packet[4]);
    sys_put_le64(output->source_time_us, &packet[8]);
    sys_put_le16(output->confidence_permille, &packet[16]);
    sys_put_le16(output->quality_bits, &packet[18]);
    sys_put_le32(output->model_hash32, &packet[20]);
    sys_put_le32(output->tee_arm_epoch, &packet[24]);
}

static ssize_t read_motion_evidence(struct bt_conn *conn,
                                    const struct bt_gatt_attr *attr,
                                    void *buf, uint16_t len, uint16_t offset)
{
    uint8_t snapshot[MOTION_EVIDENCE_PACKET_SIZE];

    k_mutex_lock(&packet_mutex, K_FOREVER);
    memcpy(snapshot, motion_evidence_packet, sizeof(snapshot));
    k_mutex_unlock(&packet_mutex);
    return bt_gatt_attr_read(conn, attr, buf, len, offset,
                             snapshot, sizeof(snapshot));
}

static void motion_evidence_ccc_changed(const struct bt_gatt_attr *attr,
                                        uint16_t value)
{
    ARG_UNUSED(attr);
    atomic_set(&motion_evidence_notify_enabled,
               value == BT_GATT_CCC_NOTIFY ? 1 : 0);
}

BT_GATT_SERVICE_DEFINE(putttrack_motion_evidence_service,
    BT_GATT_PRIMARY_SERVICE(&putttrack_motion_evidence_service_uuid.uuid),
    BT_GATT_CHARACTERISTIC(&putttrack_motion_evidence_uuid.uuid,
                           BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY,
                           BT_GATT_PERM_READ_ENCRYPT,
                           read_motion_evidence, NULL, NULL),
    BT_GATT_CCC(motion_evidence_ccc_changed,
                BT_GATT_PERM_READ_ENCRYPT | BT_GATT_PERM_WRITE_ENCRYPT));

static void publish_motion_evidence(struct pt_motion_output *output,
                                    uint16_t extra_events)
{
    uint8_t packet[MOTION_EVIDENCE_PACKET_SIZE];
    int rc;

    output->event_bits |= extra_events;
    encode_motion_evidence_packet(output, packet);
    k_mutex_lock(&packet_mutex, K_FOREVER);
    memcpy(motion_evidence_packet, packet, sizeof(packet));
    k_mutex_unlock(&packet_mutex);

    if (atomic_get(&motion_evidence_notify_enabled) == 0) {
        return;
    }
    rc = bt_gatt_notify(NULL, &putttrack_motion_evidence_service.attrs[2],
                        packet, sizeof(packet));
    if (rc != 0 && rc != -ENOTCONN) {
        motion_evidence_notify_drop_count++;
    }
}

static void motion_evidence_thread(void *unused1, void *unused2, void *unused3)
{
    uint32_t last_sequence_seen = 0U;
#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
    uint32_t last_nfc_read_count = 0U;
#endif

    ARG_UNUSED(unused1);
    ARG_UNUSED(unused2);
    ARG_UNUSED(unused3);
    pt_motion_engine_init(&embedded_motion_engine);
    k_sleep(K_MSEC(500));

    while (true) {
        uint8_t raw[MOTION_PACKET_SIZE];
        struct pt_motion_sample sample = {0};
        struct pt_motion_output output = {0};
        uint16_t extra_events = 0U;
        uint32_t seq;
        bool emit;

#if defined(CONFIG_PUTTTRACK_NFC_SERVICE)
        {
            uint32_t nfc_reads = (uint32_t)atomic_get(&nfc_data_read_count);
            if (nfc_reads != last_nfc_read_count) {
                last_nfc_read_count = nfc_reads;
                pt_motion_engine_arm_from_tee(&embedded_motion_engine);
                extra_events |= PT_EVENT_TEE_ARM_MARKER;
                /* Reuse the proven auto wake path; the Tee does not grant score authority. */
                if (atomic_get(&power_policy) == PUTTTRACK_POWER_AUTO &&
                    atomic_get(&runtime_state) == PUTTTRACK_RUNTIME_IDLE) {
                    atomic_set(&idle_wake_requested, 1);
                    k_sem_give(&power_event_sem);
                }
            }
        }
#endif

        k_mutex_lock(&packet_mutex, K_FOREVER);
        memcpy(raw, motion_packet, sizeof(raw));
        k_mutex_unlock(&packet_mutex);
        seq = sys_get_le32(&raw[4]);
        if (seq == 0U || seq == last_sequence_seen) {
            if (extra_events != 0U) {
                output.state = embedded_motion_engine.state;
                output.event_bits = extra_events;
                output.quality_bits = PT_QUALITY_BASELINE_UNREADY;
                output.model_hash32 = PT_PICKUP_V0_CONFIG_HASH32;
                output.tee_arm_epoch = embedded_motion_engine.tee_arm_epoch;
                output.source_sequence = last_sequence_seen;
                publish_motion_evidence(&output, 0U);
            }
            k_sleep(K_MSEC(10));
            continue;
        }
        last_sequence_seen = seq;

        sample.sequence = seq;
        sample.source_time_us = sys_get_le64(&raw[8]);
        sample.bmi270_valid = (raw[1] & MOTION_FLAG_BMI270_VALID) != 0U;
        sample.sensor_error_bits = sys_get_le32(&raw[52]);
        for (size_t axis = 0; axis < 3; ++axis) {
            sample.accel_micro_ms2[axis] =
                (int32_t)sys_get_le32(&raw[28 + axis * 4U]);
            sample.gyro_micro_rads[axis] =
                (int32_t)sys_get_le32(&raw[40 + axis * 4U]);
        }
        sample.gyro_clipped =
            sample.bmi270_valid &&
            packet_vector_clipped(raw, 40U, BMI270_GYRO_CLIP_MICRO_RADS);

        emit = pt_motion_engine_push(&embedded_motion_engine, &sample, &output);
        if (emit || extra_events != 0U) {
            publish_motion_evidence(&output, extra_events);
        }
        k_sleep(K_MSEC(5));
    }
}

K_THREAD_DEFINE(putttrack_motion_evidence_thread,
                MOTION_EVIDENCE_THREAD_STACK,
                motion_evidence_thread,
                NULL, NULL, NULL,
                MOTION_EVIDENCE_THREAD_PRIORITY,
                0, 700);
