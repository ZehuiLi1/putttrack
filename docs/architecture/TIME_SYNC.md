# Time Synchronization and Ordering

## 1. Design principle

Capture time at the measurement source and process ranges asynchronously. Do not use USB/Edge arrival time as acquisition time and do not manufacture a simultaneous multi-Anchor frame from sequential CS procedures.

## 2. Clock domains

| Domain | Clock | Purpose |
|---|---|---|
| Ball | monotonic counter + boot ID | IMU/motion ordering and connection-relative timing |
| Anchor | monotonic counter + boot ID | CS procedure/subevent observation time |
| Zone Gateway | monotonic clock synchronized to Edge | RF scheduling, field event aggregation |
| Edge | monotonic + wall clock | authoritative event ordering, persistence, UI/cloud time |
| Camera | frame clock/timecode | research ground truth only |

## 3. Required fields

Every source record includes:

- source device ID;
- boot ID;
- monotonic timestamp;
- monotonically increasing sequence;
- clock-sync epoch/version;
- estimated offset/uncertainty if known;
- Edge receive timestamp.

Boot ID prevents sequence/timestamp ambiguity after restart.

## 4. Synchronization hierarchy

### Edge <-> Gateways

- NTP is the minimum baseline.
- PTP/IEEE 1588 with hardware timestamps is preferred where production NICs/switches support it.
- The system must expose current offset and sync health rather than assuming synchronization succeeded.

### Gateway <-> RS-485 field nodes

Gateway sends periodic sync frames and measures round-trip/offset. Field nodes maintain monotonic clocks and calibration estimates. The scheduled bus avoids uncontrolled collisions.

### Ball <-> local RF cell

Use BLE connection/CS timing references plus protocol timestamp exchange to estimate Ball-to-Gateway offset for motion-event fusion. Do not require the ball to maintain UTC.

## 5. Initial accuracy targets

- Gateway-to-Edge: <=1 ms preferred, <=2 ms required for pilot event fusion.
- Anchor/source relative within a zone: <=2 ms target.
- Ball motion event to Gateway/Edge alignment: <=5 ms target initially.
- Research camera trajectory alignment: <=5 ms.

These are architecture targets to validate; CS PHY timing remains controller-managed and is not replaced by application clock sync.

## 6. Camera ground-truth sync

Use a gateway-controlled sync LED or hardware marker visible to the camera:

```text
Gateway records SYNC event T0
 -> drives LED pulse
 -> camera frame observes pulse
 -> fit camera-time to Edge-time mapping
```

Repeat pulses during long experiments to measure drift. Store mapping coefficients/uncertainty in the dataset manifest.

## 7. Tracker treatment

The range-domain EKF updates state at each observation's source time. A short reorder buffer handles bounded network jitter. Measurements too late for live state are retained for audit/research but do not silently rewrite completed gameplay events.

## 8. Restart and gap handling

- New boot ID resets per-device sequence domain.
- Gateway/Edge records explicit `time_sync_lost`, `clock_step`, `buffer_gap` and `recovered` events.
- A clock jump quarantines affected measurements until offset is re-established.
- Wall-clock changes never change source monotonic ordering.

## 9. Research reporting

Every published dataset/result must state:

- time-source method;
- measured sync residual/uncertainty;
- camera alignment method;
- reorder/interpolation policy;
- how sequential Anchor ranges were handled.
