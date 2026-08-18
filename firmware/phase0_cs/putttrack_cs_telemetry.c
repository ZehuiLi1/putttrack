#include "putttrack_cs_telemetry.h"

#include <errno.h>
#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/random/random.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/time_units.h>

#define PT_DEVICE_ID_MAX 24
#define PT_BOOT_ID_LEN 22
#define PT_JSON_LINE_MAX 640

static char source_device_id[PT_DEVICE_ID_MAX];
static char source_boot_id[PT_BOOT_ID_LEN];
static uint32_t source_sequence;
static bool initialized;

static uint64_t source_monotonic_ns(void)
{
    int64_t ticks = k_uptime_ticks();

    if (ticks < 0) {
        return 0;
    }

    return k_ticks_to_ns_floor64((uint64_t)ticks);
}

static void distance_to_json(char *buffer, size_t buffer_size, float meters)
{
    if (!isfinite(meters)) {
        (void)snprintf(buffer, buffer_size, "null");
        return;
    }

    /* 1 mm text resolution is far below the Phase-0 ranging error target and
     * avoids requiring floating-point printf support in Zephyr logging. */
    int64_t milli = (int64_t)(meters * 1000.0f + (meters >= 0.0f ? 0.5f : -0.5f));
    bool negative = milli < 0;
    uint64_t magnitude = negative ? (uint64_t)(-milli) : (uint64_t)milli;

    (void)snprintf(
        buffer,
        buffer_size,
        "%s%llu.%03llu",
        negative ? "-" : "",
        (unsigned long long)(magnitude / 1000U),
        (unsigned long long)(magnitude % 1000U));
}

int pt_cs_telemetry_init(const char *device_id)
{
    if (device_id == NULL || device_id[0] == '\0') {
        return -EINVAL;
    }

    size_t length = strnlen(device_id, PT_DEVICE_ID_MAX);
    if (length >= PT_DEVICE_ID_MAX) {
        return -ENAMETOOLONG;
    }

    memcpy(source_device_id, device_id, length + 1U);

    /* This nonce defines a telemetry boot domain only. It is not a security
     * credential and intentionally uses Zephyr's non-cryptographic RNG. */
    uint32_t boot_hi = sys_rand32_get();
    uint32_t boot_lo = sys_rand32_get();
    (void)snprintf(
        source_boot_id,
        sizeof(source_boot_id),
        "boot-%08x%08x",
        boot_hi,
        boot_lo);

    source_sequence = 0U;
    initialized = true;

    /* Metadata is intentionally not JSON because the host CS parser treats
     * JSON lines as distance records. */
    printk(
        "PTMETA source=putttrack_source_firmware_v1 device=%s boot=%s\n",
        source_device_id,
        source_boot_id);

    return 0;
}

uint32_t pt_cs_telemetry_emit_range(const struct pt_cs_range_sample *sample)
{
    if (!initialized || sample == NULL) {
        return 0U;
    }

    uint32_t sequence = ++source_sequence;
    uint64_t timestamp_ns = source_monotonic_ns();

    char ifft[32];
    char phase[32];
    char rtt[32];
    char rssi[24];
    char line[PT_JSON_LINE_MAX];

    distance_to_json(ifft, sizeof(ifft), sample->distance_ifft_m);
    distance_to_json(phase, sizeof(phase), sample->distance_phase_m);
    distance_to_json(rtt, sizeof(rtt), sample->distance_rtt_m);

    if (sample->rssi_valid) {
        (void)snprintf(rssi, sizeof(rssi), "%d", sample->rssi_dbm);
    } else {
        (void)snprintf(rssi, sizeof(rssi), "null");
    }

    int written = snprintf(
        line,
        sizeof(line),
        "{\"source_device_id\":\"%s\","
        "\"source_boot_id\":\"%s\","
        "\"source_monotonic_ns\":%llu,"
        "\"source_sequence\":%u,"
        "\"procedure_id\":\"cs-%08u\","
        "\"antenna_path\":%u,"
        "\"distance_ifft_m\":%s,"
        "\"distance_phase_m\":%s,"
        "\"distance_rtt_m\":%s,"
        "\"rssi_dbm\":%s,"
        "\"quality\":{"
        "\"source\":\"putttrack_source_firmware_v1\","
        "\"cs_quality\":\"%s\"}}",
        source_device_id,
        source_boot_id,
        (unsigned long long)timestamp_ns,
        sequence,
        sequence,
        sample->antenna_path,
        ifft,
        phase,
        rtt,
        rssi,
        sample->usable ? "ok" : "do_not_use");

    if (written <= 0 || (size_t)written >= sizeof(line)) {
        printk(
            "PTERR telemetry_overflow sequence=%u device=%s boot=%s\n",
            sequence,
            source_device_id,
            source_boot_id);
        return sequence;
    }

    /* One printk call minimizes line interleaving with unrelated logs. */
    printk("%s\n", line);
    return sequence;
}

const char *pt_cs_telemetry_boot_id(void)
{
    return initialized ? source_boot_id : NULL;
}
