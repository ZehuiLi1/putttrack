#pragma once

#if defined(CONFIG_PUTTTRACK_NFC_READ_LED)
void nfc_read_led_init(void);
void nfc_read_led_notify(void);
void nfc_read_led_stop(void);
int nfc_read_led_error(void);
unsigned int nfc_read_led_pulses(void);
#else
static inline void nfc_read_led_init(void) {}
static inline void nfc_read_led_notify(void) {}
static inline void nfc_read_led_stop(void) {}
static inline int nfc_read_led_error(void) { return 0; }
static inline unsigned int nfc_read_led_pulses(void) { return 0; }
#endif
