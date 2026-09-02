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

// A Type 2 Tag advertises its available user memory in the capability
// container. This limit bounds RAM use and deliberately rejects oversized
// payloads instead of silently truncating identity data.
#ifndef PT_MAX_NDEF_BYTES
#define PT_MAX_NDEF_BYTES 512
#endif
