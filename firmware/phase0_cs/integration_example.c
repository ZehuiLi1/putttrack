/*
 * Documentation scaffold only; this is not a standalone application.
 *
 * Copy the small telemetry helper into the pinned Nordic RAS Initiator source
 * build, then call the function below after cs_de_calc() has populated a
 * cs_de_report_t. Keep Nordic's sample/RAS implementation pinned rather than
 * vendoring a moving copy into PuttTrack.
 */

#include <bluetooth/cs_de.h>

#include "putttrack_cs_telemetry.h"

static void putttrack_emit_cs_report(const cs_de_report_t *report, cs_de_quality_t quality)
{
    if (report == NULL) {
        return;
    }

    for (uint8_t path = 0; path < report->n_ap; ++path) {
        const cs_de_dist_estimates_t *estimate = &report->distance_estimates[path];
        struct pt_cs_range_sample sample = {
            .antenna_path = path,
            .distance_ifft_m = estimate->ifft,
            .distance_phase_m = estimate->phase_slope,
            .distance_rtt_m = estimate->rtt,
            .rssi_valid = false, /* populate if the selected source build has a link RSSI */
            .rssi_dbm = 0,
            .usable = quality == CS_DE_QUALITY_OK,
        };

        (void)pt_cs_telemetry_emit_range(&sample);
    }
}

/* Example initialization in main/application startup:
 *
 *   int err = pt_cs_telemetry_init("A");
 *   if (err) {
 *       LOG_ERR("PuttTrack telemetry init failed: %d", err);
 *       return err;
 *   }
 *
 * Example after a complete RAS report is assembled:
 *
 *   cs_de_quality_t quality = cs_de_calc(&report);
 *   putttrack_emit_cs_report(&report, quality);
 *
 * The exact callback/location differs by NCS revision. Confirm it against the
 * pinned RAS Initiator source instead of applying this file blindly.
 */
