# Architecture Research References

Sources below are grouped by authority. Public marketing claims are not treated as measured PuttTrack performance.

## Project-held vendor primary evidence

Bbo nRF54L15DK vendor package received and inspected 2026-08-18. The raw archive/vendor binaries/PDFs are not redistributed in this public repository; hashes and source-derived findings are registered under:

- [`../hardware/bbo-nrf54l15dk/README.md`](../hardware/bbo-nrf54l15dk/README.md)
- [`../hardware/bbo-nrf54l15dk/SOURCE_MANIFEST.md`](../hardware/bbo-nrf54l15dk/SOURCE_MANIFEST.md)
- [`../hardware/bbo-nrf54l15dk/HARDWARE_EVIDENCE.md`](../hardware/bbo-nrf54l15dk/HARDWARE_EVIDENCE.md)
- [`../hardware/bbo-nrf54l15dk/CHANNEL_SOUNDING_NOTES.md`](../hardware/bbo-nrf54l15dk/CHANNEL_SOUNDING_NOTES.md)

Archive SHA-256: `1650f1e38c9022d6a696bc9da285f141707c7fd31ea24ba1f105abd16fd74864`.

This evidence supports hardware bring-up/provenance decisions only. Vendor accuracy descriptions remain vendor claims until reproduced in PuttTrack datasets.

## Bluetooth Channel Sounding

1. Bluetooth SIG, *Bluetooth Core 6.0 feature overview — Channel Sounding*  
   https://www.bluetooth.com/core-specification-6-feature-overview/
2. Bluetooth SIG, *Bluetooth Channel Sounding*  
   https://www.bluetooth.com/learn-about-bluetooth/feature-enhancements/channel-sounding/
3. Bluetooth SIG, *High-precision distance measurement and its implementation*  
   https://www.bluetooth.com/blog/bluetooth-channel-sounding-high-precision-distance-measurement-and-its-implementation/
4. Nordic Semiconductor, *Channel Sounding*  
   https://www.nordicsemi.com/Products/Wireless/Bluetooth-Low-Energy/Channel-Sounding
5. Nordic Semiconductor, nRF Connect SDK CS samples and distance-estimation documentation  
   https://docs.nordicsemi.com/
6. Silicon Labs, *Channel Sounding performance metrics*  
   https://docs.silabs.com/rtl-lib/latest/rtl-lib-channel-sounding-dev-guide/07-channel-sounding-performance-metrics

Key interpretation:

- Standard CS is connected 1:1 Initiator/Reflector operation over encrypted ACL setup.
- PBR and RTT are measurements; application/vendor algorithms calculate distance.
- Single antenna works, while multiple paths may materially improve NLOS/tail behavior.
- Official measured examples show NLOS errors can be multiple metres, so no marketing “centimetre” claim is used as a PuttTrack acceptance gate.

## Nordic hardware and power

1. Nordic, *nRF54L15*  
   https://www.nordicsemi.com/Products/nRF54L15
2. Nordic, *nRF54L15 Tag* and Tag antenna documentation  
   https://www.nordicsemi.com/Products/Development-hardware/nRF54L15-Tag  
   https://docs.nordicsemi.com/r/bundle/ug_nrf54l15_tag/page/ug/nrf54l15_tag/antennas.html
3. Nordic, *nPM2100*  
   https://www.nordicsemi.com/Products/nPM2100
4. Nordic case study, upgraded Puttshack Trackaball  
   https://www.nordicsemi.com/Nordic-news/2025/08/Puttshack-Trackaball-uses-Nordic-nRF54L15-SoC-and-nPM2100-PMIC

Nordic documents the nRF54L15 Tag as a dual-antenna Channel Sounding prototyping platform; its Tag antenna documentation states that the two antennas are selected through an RF switch and switching is automatic when the NCS Channel Sounding library is enabled.

Puttshack battery life is a company estimate, not PuttTrack evidence.

## Seeed XIAO candidate hardware

1. Seeed Studio, *XIAO nRF54L15(Sense) getting started*  
   https://wiki.seeedstudio.com/xiao_nrf54l15_sense_getting_started/
2. Seeed Studio, *XIAO nRF54L15 Sense built-in sensor*  
   https://wiki.seeedstudio.com/xiao_nrf54l15_sense_built_in_sensor/
3. Seeed Studio, *2.4GHz FPC Antenna (1.86dBi) for XIAO nRF54L15*  
   https://www.seeedstudio.com/2-4GHz-FPC-Antenna-1-86dBi-for-XIAO-nRF54L15-p-6578.html

Seeed documents a 6-DOF LSM6DS3TR-C IMU on the Sense variant and an RF switch that selects the onboard ceramic or external antenna. The ordinary Seeed example switches one selected antenna at a time; PuttTrack must not assume this is already equivalent to Nordic Tag multi-path Channel Sounding. The external 2.4 GHz FPC is therefore an Anchor installation candidate first, with any CS multi-antenna use treated as a separate firmware/RF validation task.

## Scalability research

Schex, Cremer and Dettmar, *Connectionless Bluetooth LE Channel Sounding via PAwR for Scalable and Energy-Efficient Ranging* (2026 preprint)  
https://arxiv.org/abs/2605.17094

This is an experimental proof of concept, not the Production V1 Bluetooth interoperability contract.

## UWB comparison

1. Qorvo, *DWM3001C*  
   https://www.qorvo.com/products/p/DWM3001C
2. Qorvo UWB product comparison  
   https://www.qorvo.com/products/product-list
3. NXP, secure UWB fine ranging  
   https://www.nxp.com/company/about-nxp/newsroom/NW-UWB-FINE-RANGING

UWB becomes an evidence-triggered benchmark/fallback, not an assumed addition to the ball.

## Field network and time

1. TI, isolated/protected RS-485 references  
   https://www.ti.com/tool/TIDA-00333  
   https://www.ti.com/tool/TIDA-00731  
   https://www.ti.com/tool/TIDA-01365
2. LinuxPTP `ptp4l` / `phc2sys`  
   https://www.linuxptp.org/documentation/ptp4l/  
   https://www.linuxptp.org/documentation/phc2sys/

## Secure boot / update

1. Zephyr, Trusted Firmware-M / MCUboot overview  
   https://docs.zephyrproject.org/latest/services/tfm/overview.html
2. Nordic nRF54L15 security/product specification  
   https://docs.nordicsemi.com/r/bundle/ps_nrf54l15/page/overview.html

Exact boot/key/provisioning implementation must be validated against the selected production NCS release.

## Ball physical targets

R&A, *Conformance of Balls*: diameter >=42.67 mm and mass <=45.93 g for conforming balls.  
https://www.randa.org/roe/the-rules-of-equipment/part-4-conformance-of-balls

PuttTrack venue balls may not require tournament conformance; these are product/mechanical targets.

## Patent / public prior art research

1. `US9808677B2`, *Ball game apparatus*  
   https://patents.google.com/patent/US9808677B2/en
2. `US11724172B2`, *Ball game apparatus*  
   https://patents.google.com/patent/US11724172B2/en
3. Australian family/member status must be checked through current official records and patent counsel before commercial decisions.

These sources do not disclose Puttshack production firmware, thresholds, classifier, complete RF topology or current operational algorithms. Such details remain **UNKNOWN** unless independently published.
