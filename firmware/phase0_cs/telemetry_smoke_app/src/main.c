#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include "putttrack_cs_telemetry.h"

int main(void)
{
    int err = pt_cs_telemetry_init("CI-SMOKE");
    if (err != 0) {
        printk("PTERR init=%d\n", err);
        return err;
    }

    const struct pt_cs_range_sample sample = {
        .antenna_path = 0,
        .distance_ifft_m = 1.000f,
        .distance_phase_m = 1.010f,
        .distance_rtt_m = 1.080f,
        .rssi_valid = true,
        .rssi_dbm = -48,
        .usable = true,
    };

    (void)pt_cs_telemetry_emit_range(&sample);
    printk("PTMETA smoke_done boot=%s\n", pt_cs_telemetry_boot_id());
    return 0;
}
