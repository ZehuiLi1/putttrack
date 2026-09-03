#pragma once

// AirM2M CORE ESP32-C3 Arduino variant defaults. Override any value with a
// PlatformIO build_flag if your particular carrier exposes different pins.
#ifndef PT_PN532_SCK
#define PT_PN532_SCK 6
#endif

#ifndef PT_PN532_MISO
#define PT_PN532_MISO 10
#endif

#ifndef PT_PN532_MOSI
#define PT_PN532_MOSI 3
#endif

#ifndef PT_PN532_SS
#define PT_PN532_SS 2
#endif

#ifndef PT_SERIAL_BAUD
#define PT_SERIAL_BAUD 115200
#endif

// ZDT/"Zhang Da Tou" Emm_V5 TTL UART. The RX4/TX5 direction below was
// confirmed on the assembled bench with a valid 0x1F reply and bidirectional
// 30 RPM runs. GPIO11 must not be used on ESP32-C3:
// it is VDD_SPI by default and changing it into a GPIO requires board-specific
// flash wiring plus an irreversible eFuse operation. GPIO4/GPIO5 are unused by
// the PN532 SPI mapping above.
#ifndef PT_MOTOR_RX
#define PT_MOTOR_RX 4
#endif

#ifndef PT_MOTOR_TX
#define PT_MOTOR_TX 5
#endif

#ifndef PT_MOTOR_BAUD
#define PT_MOTOR_BAUD 115200
#endif

#ifndef PT_MOTOR_ADDRESS
#define PT_MOTOR_ADDRESS 1
#endif

// Bring-up limit. Raise only after the roller is mechanically guarded and the
// low-speed direction/stop test has passed.
#ifndef PT_MOTOR_MAX_RPM
#define PT_MOTOR_MAX_RPM 300
#endif

#ifndef PT_MOTOR_MAX_RUN_SECONDS
#define PT_MOTOR_MAX_RUN_SECONDS 30
#endif

#ifndef PT_MOTOR_ARM_WINDOW_MS
#define PT_MOTOR_ARM_WINDOW_MS 10000
#endif

#ifndef PT_MOTOR_PROBE_VALID_MS
#define PT_MOTOR_PROBE_VALID_MS 60000
#endif

#ifndef PT_SCAN_TIMEOUT_MS
#define PT_SCAN_TIMEOUT_MS 350
#endif

#ifndef PT_SCAN_GAP_MS
#define PT_SCAN_GAP_MS 80
#endif

#ifndef PT_TAG_REMOVED_MS
#define PT_TAG_REMOVED_MS 1200
#endif

#ifndef PT_STABLE_READ_TARGET
#define PT_STABLE_READ_TARGET 50
#endif

// Bound the individual TLV/message materialized by the reader. The Tag may
// advertise a larger user area; pages are loaded on demand and oversized
// messages are rejected instead of silently truncating identity data.
#ifndef PT_MAX_NDEF_BYTES
#define PT_MAX_NDEF_BYTES 512
#endif
