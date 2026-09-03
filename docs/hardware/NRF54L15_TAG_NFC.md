# nRF54L15 Tag NFC feasibility

## Status

The powered PCA20072 NFC path passed end-to-end on 2026-09-03. A 26 mm,
1.0 uH flexible loop and provisional 220 pF values at both C17 and C19 let an
ESP32-C3/PN532 select the assembled research ball, read its PuttTrack service
URI and correlate RF field-on/field-off with the Tag's encrypted BLE status.
Firmware `0.1.16` passed the guarded BLE OTA flow and is now the active,
confirmed image. This is a powered service/read result, not a System OFF wake,
final tuning, range or battery-life claim. NFC remains a bounded service path,
not a gameplay dependency or replacement for BLE telemetry and signed BLE OTA.

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

The research-ball starting network is now populated, but is not a production
tuning result. Its values depend on the loop inductance,
loss, lead length, board parasitics, nearby battery and final enclosure. Before
freezing a custom PCB, record the antenna part number or geometry and its
specified inductance/tuning network. Prefer the antenna vendor's nRF reference
values or an LCR/VNA-assisted 13.56 MHz tuning pass. A close PN532 read validates
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

For the first physical trial, `0.1.13` was kept as the confirmed rollback image
while the NFC candidate booted unconfirmed. `0.1.16` was confirmed only after
BLE/SMP, NFC read/field loss, automatic idle and recovery access passed.

### Build and physical result — revalidated 2026-09-03

The repository now contains an explicitly optional Type 2 Tag service variant:

```bash
SIGNING_KEY=/absolute/private/key.pem \
scripts/nrf54l15_tag/build_tag_nfc_service.sh
```

The build applies `nfc_service.overlay` to both MCUboot and the application,
removes `nfct-pins-as-gpios`, enables the NFCT node and applies NFC Kconfig only
to the application image. Generated DTS inspection confirms the GPIO property
is absent and `nfct@d6000` is `okay` in both images. MCUboot itself does not
link the NFC Type 2 library.

The optional application also explicitly restores NFCT `PADCONFIG` immediately
before library initialization. This is required for the first application-only
BLE OTA test because the MCUboot already installed on the physical Tag was
built from the original GPIO-mode board definition. It lets the NFC candidate
remain an ordinary signed application OTA; DAPLink is not required merely to
change the pin mode. The dual-image overlay keeps future first-install images
internally consistent.

The application exposes a read-only URI:

```text
putttrack://service/tag/<opaque-device-id>?fw=0.1.16
```

It counts NFC field-on/field-off events and reports those plus initialization
status through the existing encrypted mcumgr status response. Each field rising
edge also opens one 10-second fast connectable-BLE discovery window. Repeated
field-on events while the same field remains present are counted and suppressed,
not used to extend the window. The idle 2.0–2.5 second advertisement remains
enabled after timeout, so this build does not claim System OFF or measured
energy savings. A field does not change identity, configuration or firmware.

NCS v3.4.0 physical lab-key build evidence for candidate `0.1.16+0`:

- application RRAM: `192,544 / 696,176 bytes` (`27.66%`);
- application RAM: `210,508 / 262,144 bytes` (`80.30%`);
- signed application image version: `0.1.16+0`;
- signed image passed `imgtool verify` with the existing lab Ed25519 key;
- signed OTA BIN SHA-256:
  `41c64709745cf7205c809a07cd7eef5a2a61494a14ed0eee4cfc80b74a342fc7`;
- first-install HEX SHA-256:
  `4b8cbcc8a1d511d336ad4369d1c3c42ae0fc4e719b7f2fcd4c61c5035db3042b`;
- MCUboot image digest:
  `4128faddacb1a7f785044c164750830d19e42aff28fbe659fc6a643dcb394ee92e99bdaecf4d0beb7f19bbae06b08e9981e883d24a024202a3ea83576723879e`;
- signed OTA and first-install artifacts were produced successfully;
- the image was uploaded, test-booted with confirmed `0.1.13` retained, checked
  through the physical gates below, confirmed remotely, and survived a reset as
  active and confirmed;
- a separate default build kept NFC disabled/GPIO pin mode and also passed
  signature verification.

The roughly 19.8% remaining RAM is enough for this bounded proof but argues
against adding a larger NFC application protocol before a physical NDEF read
establishes value.

## Experiment ladder

The powered PN532 reader-side prerequisite is documented in
[`ESP32C3_PN532_BRINGUP.md`](ESP32C3_PN532_BRINGUP.md). That bench passed SPI,
PN532 firmware discovery, NFC-A selection and blank NTAG213 Type 2 parsing. It
does not replace the powered nRF54L15 read or System OFF wake gates below.

The proposed service-state sequence, bounded BLE window, power measurements and
security controls are specified in
[`NFC_TRIGGERED_BLE_OTA.md`](NFC_TRIGGERED_BLE_OTA.md). That document preserves
BLE SMP as the signed firmware transport; NFC is the proximity wake and service
identity path.

1. **Build-only proof:** compile a minimal Type 2 Tag NDEF text/URI image for
   PCA20072 without installing it. **Passed 2026-09-02.**
2. **Powered read proof:** expose only opaque PuttTrack device identity and a
   firmware/version marker; count field-detected, field-lost and read events.
   **Passed 2026-09-03.** The PN532 strictly decoded
   `putttrack://service/tag/f383571202836e6f?fw=0.1.16`, reported
   `service_uri_ok=true`, and exceeded the 50-consecutive-read gate at an
   approximately 5 mm parallel-loop placement.
3. **NFC-to-BLE handoff:** an NFC touch opens a bounded connectable BLE service
   window. **Powered physical pass 2026-09-03.** Before reset, encrypted status
   recorded 11 field-on and 11 field-off events, four admitted service windows,
   seven duplicate-field suppressions and no NFC setup error. The 10-second
   window closed even while a field remained present. Encrypted BLE remains the lab channel for configuration,
   diagnostics and signed OTA; production controller authentication is open.
4. **System OFF proof:** only after ordinary reads are reliable, test NFC field
   detection as a wake source for `SHIPPING`/deep-service state.
5. **Regression proof:** **healthy-path pass 2026-09-03.** After field removal,
   `field_present=false`; automatic idle restored 2.0--2.5 second advertising,
   ADXL367 12 Hz wake mode and its interrupt while stopping BMI270 ODRs, the
   50 Hz stream and BMI270 SPI. SMP remained reachable, all sensor/power/NFC
   error counters remained zero, and confirmed `0.1.16` survived reset.
6. **Power proof:** measure NFC sensing, field-present and post-wake energy when
   a suitable current instrument is available.

### Reader compatibility finding

The nRF Type 2 emulator advertised 992 bytes of user memory while the actual
service message ended within the first 60 bytes. The initial reader rejected
any advertised area larger than its 512-byte bounded buffer, so it selected the
Tag but reported `type2_memory_out_of_range`. The reader now walks TLVs and
loads pages on demand: a single NDEF TLV must still fit inside the fixed local
bound, but a larger advertised Tag capacity is no longer mistaken for an
oversized message. The corrected firmware physically decoded the URI and
passed the 50-read gate.

NFC field presence is a wake signal, not authentication. A field detection may
open a short service window; identity-changing commands, provisioning secrets
and firmware updates still require an authorized service controller. The
current Just Works lab image provides encryption and signed-image verification,
but not MITM-authenticated controller identity.

## Product role and priority

The intended division of responsibility is:

```text
ADXL367 motion -> gameplay/handling wake
NFC touch      -> commissioning, assignment or service wake
BLE            -> encrypted lab communication and signed OTA;
                  authenticated controller required for production
```

NFC is useful because it can improve commissioning UX and provide an explicit
service wake for a future custom Ball PCB. It does not resolve the current
highest-risk questions: motion behavior inside a rolling/impacted ball and the
physical tee/cup evidence needed for an automatic one-hole experience.

The NFC spike is therefore time-boxed behind, or run during mechanical waiting
time for, the controlled research-ball core and physical one-hole work. Its
exit is a documented go/defer decision, not indefinite protocol development.
