# Bbo nRF54L15DK Source Manifest

## Archive identity

| Field | Value |
|---|---|
| Source archive | `Bbo nRF54L15DK.zip` |
| Inspection date | 2026-08-18 |
| Size | 86,814,834 bytes |
| ZIP entries | 306 |
| ZIP uncompressed payload | 105,172,758 bytes |
| SHA-256 | `1650f1e38c9022d6a696bc9da285f141707c7fd31ea24ba1f105abd16fd74864` |

## Key-file digests

| Vendor path | Size (bytes) | SHA-256 | Role |
|---|---:|---|---|
| `Bbo nRF54L 开发指南v1.3.pdf` | 3,286,108 | `0e37196379bdd7f5acd0674c2e26d6566f4c9f47dd59d112bc8939a74dfbfc68` | hardware/NCS/CS development guide |
| `SCH_nRF54L15DK.pdf` | 281,472 | `3c38dc6d5e78da78447c167b64aa3cba3f60fdb2a3630aab5b0b4808a22d4085` | inspected core-board schematic |
| `Bbo nRF54L15 DK串口升级指导.pdf` | 202,019 | `8b1a6ac3b9c0ab0dcfdf2f718a8aa35dd0b263d674cb41b20c5f47d00c59698e` | serial boot/update procedure |
| `测试bin文件/channel_sounding_ras_initiator.signed.bin` | 306,616 | `ac1b12fb582c84a24df97736472a4fd6860b34b67232e262c6bf09d9e66fcb85` | supplied Channel Sounding Initiator smoke-test image |
| `测试bin文件/channel_sounding_ras_reflector.signed.bin` | 260,908 | `4b1e55ce89828c1ca6f5f9dab6ec4c851ce725d6cc782a5ac7ba315c11c1df01` | supplied Channel Sounding Reflector smoke-test image |
| `测试bin文件/release_boot_01.hex` | 164,102 | `d776615648bd8fba55f6e29efa0b5ab3eb8b7ae28d7e8f612313ca57dfa87e0a` | vendor bootloader recovery image |

## Relevant archive structure

The inspected package contains, at minimum:

- `demo/v3.0.2/`
- `demo/v3.3.0/`
- `dfu_config/`
- `hci_log/`
- `测试bin文件/`
- `BboTool.exe`
- `BboTool(ubuntu版本)`
- Bluetooth reference PDFs
- Nordic preliminary nRF54L15 family datasheet
- Matter development material

The ordinary demo trees include examples such as `hello_world`, `lsm6ds3tr`, `sd_fs`, `spi_flash`, `dmic_capture`, `grtc` and Zephyr tests. No standalone Channel Sounding Initiator/Reflector source tree was found inside the vendor package during this inspection; the package supplies signed CS test binaries and points to the nRF Connect SDK samples.

## Binary provenance observations

Printable strings in the supplied Initiator image include:

- `WEST_TOPDIR/nrf/applications/channel_sounding_ras_initiator/src/main.c`
- `Starting Channel Sounding Initiator Sample`
- `Distance estimates on antenna path %u: ifft: %f, phase_slope: %f, rtt: %f`
- `Sleeping for a few seconds...`
- `*** Booting nRF Connect SDK v3.0.2-89ba1294ac9b ***`
- `*** Using Zephyr OS v4.0.99-f791c49f492c ***`

Printable strings in the supplied Reflector image include:

- `Starting Channel Sounding Reflector Sample`
- `Nordic CS Reflector`
- the same NCS 3.0.2 / Zephyr version banners.

These strings are provenance evidence, not a substitute for source-controlled builds. Production/research firmware must pin and record its own NCS/toolchain version.
