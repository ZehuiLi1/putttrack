#ifndef PUTTTRACK_CS_TELEMETRY_H_
#define PUTTTRACK_CS_TELEMETRY_H_

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** One completed Channel Sounding distance report for one antenna path. */
struct pt_cs_range_sample {
    uint8_t antenna_path;
    float distance_ifft_m;
    float distance_phase_m;
    float distance_rtt_m;
    bool rssi_valid;
    int16_t rssi_dbm;
    bool usable;
};

/**
 * Initialize one boot-domain telemetry stream.
 *
 * @param source_device_id Stable experiment identity such as "A".
 * @return 0 on success, negative errno-style value on invalid input.
 */
int pt_cs_telemetry_init(const char *source_device_id);

/**
 * Emit one JSON-line distance record and increment the source sequence.
 *
 * The line contains source_device_id, source_boot_id, source_monotonic_ns,
 * source_sequence and a procedure_id derived from that sequence.
 *
 * @return Emitted source sequence, or 0 if telemetry was not initialized.
 */
uint32_t pt_cs_telemetry_emit_range(const struct pt_cs_range_sample *sample);

/** Current non-security boot-domain identifier. */
const char *pt_cs_telemetry_boot_id(void);

#ifdef __cplusplus
}
#endif

#endif /* PUTTTRACK_CS_TELEMETRY_H_ */
