# Architecture Research References

Sources below are grouped by authority. Public marketing claims are not treated as measured PuttTrack performance.

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

Puttshack battery life is a company estimate, not PuttTrack evidence.

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
