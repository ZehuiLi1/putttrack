# nRF54L15 Tag NFC feasibility

## Status

The physical NFC path on PCA20072 is **present but unpopulated and not yet
validated**. The confirmed `0.1.13` Tag image remains unchanged. NFC is a
bounded service/provisioning experiment, not a new gameplay dependency and not
a replacement for BLE telemetry or signed BLE OTA.

## Hardware evidence

Nordic's nRF54L15 Tag product page lists NFC among the supported protocols.
The official PCA20072 revision 1.0.0 hardware package provides the more precise
board-level boundary:

- nRF54L15 `P1.02/NFC1` and `P1.03/NFC2` are routed to accessible board pads;
- `C17` and `C19` are shunt-to-ground 0402 tuning footprints marked `TBD`;
- the production pick-and-place file also lists `C17` and `C19` as `TBD`;
- the external NFC loop is connected between NFC1 and NFC2;
- the on-board `ANT1` and `ANT2` parts are separate 2.4 GHz antennas for BLE
  and possible Channel Sounding use. They are not the NFC loop.

The NCS v3.4.0 board DTS currently contains:

```dts
&uicr {
    nfct-pins-as-gpios;
};
```

and leaves `nfct` disabled. That is the default software configuration for an
unpopulated board, not proof that the PCB omitted the NFC route. The current
PuttTrack application does not otherwise allocate P1.02 or P1.03, so enabling
NFCT does not conflict with ADXL367 INT1, BMI270, SPI22, I2C21 or the 2.4 GHz RF
switch.

Primary sources:

- [Nordic nRF54L15 Tag product page](https://www.nordicsemi.com/Products/Development-hardware/nRF54L15-Tag/Downloads)
- [Nordic PCA20072 hardware package](https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/dev-kits/nrf54l15-tag/nrf54l15-tag---hardware-files-1_0_0.zip)
- [nRF54L15 NFCT/GPIO pin configuration](https://docs.nordicsemi.com/r/bundle/ps_nrf54l15/page/gpio.html-concept_o12_bgv_bs)

## Hardware boundary

Do not populate C17/C19 by guess. Their values depend on the loop inductance,
loss, lead length, board parasitics, nearby battery and final enclosure. Before
soldering, record the antenna part number or geometry and its specified
inductance/tuning network. Prefer the antenna vendor's nRF reference values or
an LCR/VNA-assisted 13.56 MHz tuning pass. A phone-read smoke test can validate
basic coupling but does not replace tuning evidence for the final Ball.

The first hardware check therefore requires:

1. a clear antenna identity, photograph and terminal mapping;
2. confirmation that the two antenna terminals go only to P1.02/NFC1 and
   P1.03/NFC2;
3. justified C17/C19 starting values;
4. continuity and short-circuit checks before inserting the CR2032.

## Software boundary

An application overlay must remove `nfct-pins-as-gpios` and enable `nfct`.
There is an additional MCUboot detail: the current bootloader was built from
the default Tag board definition and can configure the NFCT pads as GPIO before
handing control to the application. The nRF54L NFCT driver rejects
initialization when `PADCONFIG` still selects GPIO. A test build must therefore
prove one of these paths rather than assume the application overlay is enough:

- apply the NFC overlay consistently to MCUboot and the application; or
- explicitly restore NFCT pad mode early in the application before initializing
  the NFC library, with a verified reset/System OFF sequence.

Keep `0.1.13` confirmed as the rollback image. Any NFC candidate is uploaded as
an unconfirmed signed test image and is confirmed only after BLE/SMP, motion
wake, automatic idle and rollback access still pass.

## Experiment ladder

1. **Build-only proof:** compile a minimal Type 2 Tag NDEF text/URI image for
   PCA20072 without installing it.
2. **Powered read proof:** expose only opaque PuttTrack device identity and a
   firmware/version marker; count field-detected, field-lost and read events.
3. **NFC-to-BLE handoff:** an NFC touch opens a bounded connectable BLE service
   window. Encrypted BLE remains the channel for configuration, diagnostics and
   signed OTA.
4. **System OFF proof:** only after ordinary reads are reliable, test NFC field
   detection as a wake source for `SHIPPING`/deep-service state.
5. **Regression proof:** repeat ADXL367 motion wake/re-sleep, SMP reconnect,
   OTA rollback and false-wake checks.
6. **Power proof:** measure NFC sensing, field-present and post-wake energy when
   a suitable current instrument is available.

NFC field presence is a wake signal, not authentication. A field detection may
open a short service window; identity-changing commands, provisioning secrets
and firmware updates still require an authenticated protocol.

## Product role and priority

The intended division of responsibility is:

```text
ADXL367 motion -> gameplay/handling wake
NFC touch      -> commissioning, assignment or service wake
BLE            -> authenticated communication, telemetry and signed OTA
```

NFC is useful because it can improve commissioning UX and provide an explicit
service wake for a future custom Ball PCB. It does not resolve the current
highest-risk questions: motion behavior inside a rolling/impacted ball and the
physical tee/cup evidence needed for an automatic one-hole experience.

The NFC spike is therefore time-boxed behind, or run during mechanical waiting
time for, the controlled research-ball core and physical one-hole work. Its
exit is a documented go/defer decision, not indefinite protocol development.
