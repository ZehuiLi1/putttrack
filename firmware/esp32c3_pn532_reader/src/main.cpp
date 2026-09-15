#include <Adafruit_PN532.h>
#include <Arduino.h>
#include <SPI.h>

#include "app_config.h"
#include "cup_sensor.h"
#include "roller_motor.h"

namespace {

Adafruit_PN532 pn532(PT_PN532_SS, &SPI);
HardwareSerial motor_uart(1);
bool handleNfcConsoleCommand(const String &line);
RollerMotor roller_motor(motor_uart, handleNfcConsoleCommand);

struct NdefResult {
  bool type2 = false;
  bool type4 = false;
  bool valid = false;
  size_t type2_advertised_bytes = 0;
  size_t type2_loaded_bytes = 0;
  String text;
  String ball_id;
  String uri;
  String device_id;
  String firmware_version;
  bool service_uri = false;
  String error;
};

String active_uid;
String active_device_id;
bool active_type4 = false;
uint32_t consecutive_reads = 0;
uint32_t last_seen_ms = 0;
bool stable_reported = false;
bool rf_paused = false;
uint32_t rf_resume_at = 0;

String uidToHex(const uint8_t *uid, uint8_t uid_length) {
  static constexpr char HEX_DIGITS[] = "0123456789ABCDEF";
  String result;
  result.reserve(uid_length * 2U);
  for (uint8_t i = 0; i < uid_length; ++i) {
    result += HEX_DIGITS[(uid[i] >> 4) & 0x0F];
    result += HEX_DIGITS[uid[i] & 0x0F];
  }
  return result;
}

void printJsonString(const String &value) {
  Serial.print('"');
  for (size_t i = 0; i < value.length(); ++i) {
    const char ch = value[i];
    switch (ch) {
      case '\\':
        Serial.print("\\\\");
        break;
      case '"':
        Serial.print("\\\"");
        break;
      case '\n':
        Serial.print("\\n");
        break;
      case '\r':
        Serial.print("\\r");
        break;
      case '\t':
        Serial.print("\\t");
        break;
      default:
        if (static_cast<uint8_t>(ch) < 0x20) {
          Serial.print('?');
        } else {
          Serial.print(ch);
        }
        break;
    }
  }
  Serial.print('"');
}

String extractBallId(const String &text) {
  static const String PREFIX = "BALL_ID=";
  const int start = text.indexOf(PREFIX);
  if (start < 0) {
    return "";
  }

  const size_t value_start = static_cast<size_t>(start) + PREFIX.length();
  size_t end = value_start;
  while (end < text.length()) {
    const char ch = text[end];
    if (ch == '\r' || ch == '\n' || ch == ';' || ch == '\0') {
      break;
    }
    ++end;
  }

  String ball_id = text.substring(value_start, end);
  ball_id.trim();
  return ball_id;
}

bool isHexDeviceId(const String &value) {
  if (value.length() < 2U || value.length() > 32U ||
      (value.length() % 2U) != 0U) {
    return false;
  }
  for (size_t i = 0; i < value.length(); ++i) {
    const char ch = value[i];
    if (!((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f') ||
          (ch >= 'A' && ch <= 'F'))) {
      return false;
    }
  }
  return true;
}

bool isFirmwareVersion(const String &value) {
  if (value.isEmpty() || value.length() > 8U) {
    return false;
  }
  for (size_t i = 0; i < value.length(); ++i) {
    const char ch = value[i];
    if (!((ch >= '0' && ch <= '9') || (ch >= 'A' && ch <= 'Z') ||
          (ch >= 'a' && ch <= 'z') || ch == '.' || ch == '-' || ch == '+')) {
      return false;
    }
  }
  return true;
}

bool parseServiceUri(const String &uri, String &device_id,
                     String &firmware_version, String &error) {
  static const String PREFIX = "putttrack://service/tag/";
  if (!uri.startsWith(PREFIX)) {
    return false;
  }

  const size_t value_start = PREFIX.length();
  const int query_index = uri.indexOf("?fw=", value_start);
  if (query_index < 0) {
    error = "service_uri_missing_firmware";
    return false;
  }
  const size_t value_end = static_cast<size_t>(query_index);
  device_id = uri.substring(value_start, value_end);
  if (!isHexDeviceId(device_id)) {
    error = "service_uri_invalid_device_id";
    device_id = "";
    return false;
  }
  device_id.toLowerCase();

  const size_t firmware_start = value_end + 4U;
  firmware_version = uri.substring(firmware_start);
  if (!isFirmwareVersion(firmware_version)) {
    error = "service_uri_invalid_firmware";
    device_id = "";
    firmware_version = "";
    return false;
  }
  return true;
}

bool decodeUriPrefix(uint8_t identifier_code, String &prefix) {
  switch (identifier_code) {
    case 0x00:
      prefix = "";
      return true;
    case 0x01:
      prefix = "http://www.";
      return true;
    case 0x02:
      prefix = "https://www.";
      return true;
    case 0x03:
      prefix = "http://";
      return true;
    case 0x04:
      prefix = "https://";
      return true;
    default:
      return false;
  }
}

bool parseNdefRecords(const uint8_t *message, size_t message_length,
                      NdefResult &result) {
  size_t offset = 0;
  bool found_text = false;
  bool found_supported_record = false;

  while (offset < message_length) {
    if (message_length - offset < 3) {
      result.error = "short_ndef_record";
      return false;
    }

    const uint8_t header = message[offset++];
    const bool short_record = (header & 0x10U) != 0;
    const bool has_id = (header & 0x08U) != 0;
    const bool chunked = (header & 0x20U) != 0;
    const bool message_end = (header & 0x40U) != 0;
    const uint8_t tnf = header & 0x07U;
    const uint8_t type_length = message[offset++];

    if (chunked) {
      result.error = "chunked_ndef_not_supported";
      return false;
    }

    uint32_t payload_length = 0;
    if (short_record) {
      if (offset >= message_length) {
        result.error = "missing_payload_length";
        return false;
      }
      payload_length = message[offset++];
    } else {
      if (message_length - offset < 4) {
        result.error = "missing_payload_length";
        return false;
      }
      payload_length = (static_cast<uint32_t>(message[offset]) << 24U) |
                       (static_cast<uint32_t>(message[offset + 1]) << 16U) |
                       (static_cast<uint32_t>(message[offset + 2]) << 8U) |
                       static_cast<uint32_t>(message[offset + 3]);
      offset += 4;
    }

    uint8_t id_length = 0;
    if (has_id) {
      if (offset >= message_length) {
        result.error = "missing_id_length";
        return false;
      }
      id_length = message[offset++];
    }

    const size_t record_bytes = static_cast<size_t>(type_length) + id_length +
                                static_cast<size_t>(payload_length);
    if (record_bytes > message_length - offset) {
      result.error = "ndef_record_out_of_bounds";
      return false;
    }

    const uint8_t *type = message + offset;
    offset += type_length;
    offset += id_length;
    const uint8_t *payload = message + offset;
    offset += payload_length;

    // NFC Forum well-known Text record: type "T", then status byte,
    // language code, and UTF-8/UTF-16 text.
    if (tnf == 0x01 && type_length == 1 && type[0] == 'T' &&
        payload_length >= 1) {
      const uint8_t status = payload[0];
      const uint8_t language_length = status & 0x3FU;
      const bool utf16 = (status & 0x80U) != 0;
      if (utf16) {
        result.error = "utf16_text_not_supported";
        return false;
      }
      if (static_cast<uint32_t>(language_length) + 1U > payload_length) {
        result.error = "invalid_text_language_length";
        return false;
      }

      if (found_text) {
        result.text += '\n';
      }
      const size_t text_start = static_cast<size_t>(language_length) + 1U;
      for (size_t i = text_start; i < payload_length; ++i) {
        result.text += static_cast<char>(payload[i]);
      }
      found_text = true;
      found_supported_record = true;
    } else if (tnf == 0x01 && type_length == 1 && type[0] == 'U' &&
               payload_length >= 1) {
      String prefix;
      if (decodeUriPrefix(payload[0], prefix)) {
        result.uri = prefix;
        for (size_t i = 1; i < payload_length; ++i) {
          result.uri += static_cast<char>(payload[i]);
        }
        if (result.uri.startsWith("putttrack://service/tag/")) {
          if (!parseServiceUri(result.uri, result.device_id,
                               result.firmware_version, result.error)) {
            return false;
          }
          result.service_uri = true;
        }
        found_supported_record = true;
      }
    }

    if (message_end) {
      break;
    }
  }

  if (!found_supported_record) {
    result.error = "no_supported_text_or_uri_record";
    return false;
  }

  result.ball_id = extractBallId(result.text);
  result.valid = true;
  return true;
}

bool exchangeApdu(const uint8_t *command, size_t command_length,
                  uint8_t *response, uint8_t &response_length) {
  if (command_length > 62U) return false;
  const bool exchanged = pn532.inDataExchange(const_cast<uint8_t *>(command),
                            static_cast<uint8_t>(command_length), response,
                            &response_length);
  const int status_word = exchanged && response_length >= 2U
      ? (response[response_length - 2U] << 8U) | response[response_length - 1U]
      : -1;
  if (!exchanged || status_word != 0x9000) {
    Serial.printf("{\"event\":\"apdu_failure\",\"ins\":%u,\"p1\":%u,\"p2\":%u,"
                  "\"transport_ok\":%s,\"diagnostic\":%u,\"status_word\":%d}\n",
                  command[1], command[2], command[3], exchanged ? "true" : "false",
                  pn532.lastExchangeDiagnostic(), status_word);
    return false;
  }
  response_length -= 2U;
  return true;
}

bool selectType4Ndef() {
  static const uint8_t SELECT_NDEF_APPLICATION[] = {
      0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76,
      0x00, 0x00, 0x85, 0x01, 0x01, 0x00};
  static const uint8_t SELECT_NDEF_FILE[] = {0x00, 0xA4, 0x00, 0x0C,
                                              0x02, 0xE1, 0x04};
  uint8_t response[16] = {};
  uint8_t response_length = sizeof(response);

  if (!exchangeApdu(SELECT_NDEF_APPLICATION, sizeof(SELECT_NDEF_APPLICATION),
                    response, response_length)) {
    return false;
  }
  response_length = sizeof(response);
  return exchangeApdu(SELECT_NDEF_FILE, sizeof(SELECT_NDEF_FILE), response,
                      response_length);
}

bool readBinary(uint16_t offset, uint8_t *data, uint8_t length) {
  uint8_t command[] = {0x00, 0xB0, static_cast<uint8_t>(offset >> 8U),
                       static_cast<uint8_t>(offset), length};
  uint8_t response[52] = {};
  uint8_t response_length = sizeof(response);

  if (!exchangeApdu(command, sizeof(command), response, response_length) ||
      response_length != length) {
    return false;
  }
  memcpy(data, response, length);
  return true;
}

bool updateBinary(uint16_t offset, const uint8_t *data, uint8_t length) {
  uint8_t command[5U + 32U] = {0x00, 0xD6,
                               static_cast<uint8_t>(offset >> 8U),
                               static_cast<uint8_t>(offset), length};
  uint8_t response[8] = {};
  uint8_t response_length = sizeof(response);

  if (length > 32U) {
    return false;
  }
  memcpy(&command[5], data, length);
  return exchangeApdu(command, 5U + length, response, response_length) &&
         response_length == 0U;
}

NdefResult readType4Ndef() {
  NdefResult result;
  uint8_t nlen_bytes[2] = {};

  // The build-time Adafruit PN532 patch records the target selected by the
  // immediately preceding readPassiveTargetID(), so no second RF activation is
  // needed before the Type 4 APDU exchange.
  if (!selectType4Ndef()) {
    result.error = "not_type4_ndef";
    return result;
  }
  result.type4 = true;
  if (!readBinary(0U, nlen_bytes, sizeof(nlen_bytes))) {
    result.error = "type4_nlen_unreadable";
    return result;
  }
  const size_t ndef_length =
      (static_cast<size_t>(nlen_bytes[0]) << 8U) | nlen_bytes[1];
  if (ndef_length == 0U || ndef_length > PT_MAX_NDEF_BYTES) {
    result.error = "type4_ndef_length_out_of_range";
    return result;
  }

  static uint8_t message[PT_MAX_NDEF_BYTES];
  size_t loaded = 0;
  while (loaded < ndef_length) {
    const uint8_t chunk = static_cast<uint8_t>(
        min(static_cast<size_t>(48U), ndef_length - loaded));
    if (!readBinary(static_cast<uint16_t>(2U + loaded), &message[loaded],
                    chunk)) {
      result.error = "type4_ndef_unreadable";
      return result;
    }
    loaded += chunk;
  }
  parseNdefRecords(message, ndef_length, result);
  return result;
}

bool writeType4Ndef(const uint8_t *message, size_t message_length) {
  static const uint8_t EMPTY_NLEN[2] = {0x00, 0x00};

  if (message_length == 0U || message_length > 0xFFFFU ||
      !selectType4Ndef() || !updateBinary(0U, EMPTY_NLEN, sizeof(EMPTY_NLEN))) {
    return false;
  }
  size_t written = 0;
  while (written < message_length) {
    const uint8_t chunk = static_cast<uint8_t>(
        min(static_cast<size_t>(32U), message_length - written));
    if (!updateBinary(static_cast<uint16_t>(2U + written), &message[written],
                      chunk)) {
      return false;
    }
    written += chunk;
  }
  const uint8_t nlen[] = {static_cast<uint8_t>(message_length >> 8U),
                          static_cast<uint8_t>(message_length)};
  return updateBinary(0U, nlen, sizeof(nlen));
}

bool readType2Page(uint8_t page, uint8_t *out) {
  // inDataExchange waits for the response-ready signal. Adafruit's NTAG
  // helper reads immediately after ACK, which races the emulated Tag.
  uint8_t command[] = {0x30, page};
  uint8_t response[16] = {};
  uint8_t length = sizeof(response);
  if (!pn532.inDataExchange(command, sizeof(command), response, &length) ||
      length != sizeof(response)) {
    return false;
  }
  memcpy(out, response, 4);
  return true;
}

bool loadType2UserBytes(uint8_t *memory, size_t capacity,
                        size_t advertised_bytes, size_t required_bytes,
                        size_t &loaded_bytes) {
  if (required_bytes > advertised_bytes || required_bytes > capacity) {
    return false;
  }

  while (loaded_bytes < required_bytes) {
    if (capacity - loaded_bytes < 4U ||
        advertised_bytes - loaded_bytes < 4U) {
      return false;
    }
    const size_t page_number = 4U + (loaded_bytes / 4U);
    if (page_number > 0xFFU ||
        !readType2Page(static_cast<uint8_t>(page_number),
                               memory + loaded_bytes)) {
      return false;
    }
    loaded_bytes += 4U;
  }
  return true;
}

NdefResult readType2Ndef() {
  NdefResult result;
  uint8_t page[4] = {};

  // Page 3 is the NFC Forum Type 2 capability container.
  if (!readType2Page(3, page)) {
    result.error = "capability_container_unreadable";
    return result;
  }
  if (page[0] != 0xE1) {
    result.error = "not_type2_ndef";
    return result;
  }
  result.type2 = true;

  const size_t advertised_bytes = static_cast<size_t>(page[2]) * 8U;
  result.type2_advertised_bytes = advertised_bytes;
  if (advertised_bytes == 0) {
    result.error = "type2_memory_out_of_range";
    return result;
  }

  static uint8_t user_memory[PT_MAX_NDEF_BYTES];
  size_t loaded_bytes = 0;

  // The nRF Type 2 emulator can advertise a user area larger than the bounded
  // reader buffer even though the NDEF TLV itself is near the beginning. Read
  // only the bytes needed to walk the TLVs and decode the selected message.
  // An individual TLV still has to fit completely inside the local bound.
  const auto ensure_loaded = [&](size_t required_bytes) {
    const bool loaded = loadType2UserBytes(
        user_memory, sizeof(user_memory), advertised_bytes, required_bytes,
        loaded_bytes);
    result.type2_loaded_bytes = loaded_bytes;
    return loaded;
  };

  // Find the NDEF Message TLV (0x03), skipping NULL and proprietary TLVs.
  size_t offset = 0;
  while (offset < advertised_bytes) {
    if (!ensure_loaded(offset + 1U)) {
      result.error = offset + 1U > sizeof(user_memory)
                         ? "type2_reader_limit_reached"
                         : "type2_page_unreadable";
      return result;
    }
    const uint8_t type = user_memory[offset++];
    if (type == 0x00) {
      continue;
    }
    if (type == 0xFE) {
      break;
    }
    if (offset >= advertised_bytes || !ensure_loaded(offset + 1U)) {
      result.error = "type2_page_unreadable";
      return result;
    }

    size_t length = user_memory[offset++];
    if (length == 0xFFU) {
      if (advertised_bytes - offset < 2U) {
        result.error = "short_extended_tlv_length";
        return result;
      }
      if (!ensure_loaded(offset + 2U)) {
        result.error = offset + 2U > sizeof(user_memory)
                           ? "type2_reader_limit_reached"
                           : "type2_page_unreadable";
        return result;
      }
      length = (static_cast<size_t>(user_memory[offset]) << 8U) |
               user_memory[offset + 1];
      offset += 2;
    }
    if (length > advertised_bytes - offset) {
      result.error = "tlv_out_of_bounds";
      return result;
    }
    if (length > sizeof(user_memory) - offset) {
      result.error = "ndef_tlv_exceeds_reader_limit";
      return result;
    }
    if (!ensure_loaded(offset + length)) {
      result.error = "type2_page_unreadable";
      return result;
    }

    if (type == 0x03) {
      if (length == 0) {
        result.error = "empty_ndef_message";
        return result;
      }
      parseNdefRecords(user_memory + offset, length, result);
      return result;
    }
    offset += length;
  }

  result.error = "ndef_tlv_not_found";
  return result;
}

bool isHexNonce(const String &value) {
  if (value.length() != 32U) {
    return false;
  }
  for (size_t i = 0; i < value.length(); ++i) {
    const char ch = value[i];
    if (!((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'))) {
      return false;
    }
  }
  return true;
}

void printMigrationResult(bool accepted, const String &device_id,
                          const String &nonce, const char *reason = nullptr) {
  Serial.print(F("{\"event\":\"nfc_migration_command\",\"accepted\":"));
  Serial.print(accepted ? F("true") : F("false"));
  Serial.print(F(",\"device_id\":"));
  printJsonString(device_id);
  Serial.print(F(",\"nonce\":"));
  printJsonString(nonce);
  if (reason != nullptr) {
    Serial.print(F(",\"reason\":"));
    printJsonString(reason);
  }
  Serial.println('}');
}

bool rf_status_pending = true;

void printRfStatus() {
  // Capture the live NFC-A configuration after a successful transaction;
  // power-on reset values are not necessarily the active reader settings.
  static const uint16_t addresses[] = {0x6304, 0x6305, 0x6316, 0x6317,
                                        0x6318, 0x6319, 0x6308};
  uint8_t values[7] = {};
  if (!pn532.readRegisters(addresses, values, 7)) {
    Serial.println(F("{\"event\":\"rf_status\",\"ok\":false}"));
    return;
  }
  Serial.printf("{\"event\":\"rf_status\",\"ok\":true,"
                "\"context\":\"after_ndef_read\",\"tx_control\":%u,\"tx_auto\":%u,"
                "\"rf_cfg\":%u,\"gs_n_on\":%u,\"cw_gs_p\":%u,"
                "\"mod_gs_p\":%u,\"rx_threshold\":%u,"
                "\"p_driver\":%u,\"n_driver\":%u}\n",
                values[0], values[1], values[2], values[3], values[4],
                values[5], values[6], values[4] & 0x3fU, values[3] >> 4U);
}

bool handleNfcConsoleCommand(const String &line) {
  if (cupCommand(line)) return true;
  if (line == "nfc rf pause" || line == "nfc rf resume") {
    const bool pause = line == "nfc rf pause";
    const bool ok = pn532.setRFField(!pause);
    if (ok) {
      rf_paused = pause;
      rf_resume_at = millis() + 60000U;
      active_uid = "";
      active_device_id = "";
      active_type4 = false;
      consecutive_reads = 0;
      stable_reported = false;
    }
    Serial.printf("{\"event\":\"rf_control\",\"ok\":%s,\"paused\":%s,\"lease_ms\":%u}\n",
                  ok ? "true" : "false", rf_paused ? "true" : "false",
                  rf_paused ? 60000U : 0U);
    return true;
  }
  if (line == "nfc rf status") {
    rf_status_pending = true;
    Serial.println(F("{\"event\":\"rf_status_pending\"}"));
    return true;
  }
  if (line == "nfc help") {
    Serial.println(F("{\"event\":\"nfc_help\",\"commands\":["
                     "\"nfc rf status\",\"nfc rf pause\",\"nfc rf resume\",\"nfc migrate <device_id> <nonce_32_hex>\"]}"));
    return true;
  }
  if (!line.startsWith("nfc migrate ")) {
    return false;
  }

  char device_id_buffer[33] = {};
  char nonce_buffer[33] = {};
  char trailing = '\0';
  const int fields = sscanf(line.c_str(), "nfc migrate %32s %32s %c",
                            device_id_buffer, nonce_buffer, &trailing);
  String requested_device_id(device_id_buffer);
  String nonce(nonce_buffer);
  if (fields != 2 || !isHexDeviceId(requested_device_id) ||
      !isHexNonce(nonce)) {
    printMigrationResult(false, requested_device_id, nonce,
                         "invalid_command");
    return true;
  }
  requested_device_id.toLowerCase();
  if (PT_NFC_STRESS_TEST) {
    printMigrationResult(false, requested_device_id, nonce,
                         "stress_test_read_only");
    return true;
  }
  if (active_uid.isEmpty() || millis() - last_seen_ms > PT_TAG_REMOVED_MS) {
    printMigrationResult(false, requested_device_id, nonce, "no_tag_present");
    return true;
  }
  if (!active_type4 || active_device_id != requested_device_id) {
    printMigrationResult(false, requested_device_id, nonce,
                         "target_identity_mismatch");
    return true;
  }

  const String text =
      "PUTTTRACK:MIGRATE:1:" + requested_device_id + ":" + nonce;
  uint8_t message[128] = {};
  const size_t payload_length = 3U + text.length();
  const size_t message_length = 4U + payload_length;
  if (payload_length > 255U || message_length > sizeof(message)) {
    printMigrationResult(false, requested_device_id, nonce,
                         "command_too_large");
    return true;
  }
  message[0] = 0xD1U;
  message[1] = 0x01U;
  message[2] = static_cast<uint8_t>(payload_length);
  message[3] = 'T';
  message[4] = 0x02U;
  message[5] = 'e';
  message[6] = 'n';
  memcpy(&message[7], text.c_str(), text.length());

  if (!writeType4Ndef(message, message_length)) {
    printMigrationResult(false, requested_device_id, nonce,
                         "type4_write_failed");
    return true;
  }
  printMigrationResult(true, requested_device_id, nonce);
  return true;
}

void printTagEvent(const String &uid, const NdefResult &ndef) {
  Serial.print(F("{\"event\":\"nfc_tag\",\"uid\":"));
  printJsonString(uid);
  Serial.print(F(",\"consecutive_reads\":"));
  Serial.print(consecutive_reads);
  Serial.print(F(",\"stable_target\":"));
  Serial.print(PT_STABLE_READ_TARGET);
  Serial.print(F(",\"ndef_ok\":"));
  Serial.print(ndef.valid ? F("true") : F("false"));
  Serial.printf(",\"sak\":%u", unsigned(pn532.lastTargetSAK()));
  if (ndef.type2) {
    Serial.print(F(",\"type2_advertised_bytes\":"));
    Serial.print(ndef.type2_advertised_bytes);
    Serial.print(F(",\"type2_loaded_bytes\":"));
    Serial.print(ndef.type2_loaded_bytes);
  }
  if (ndef.type4) {
    Serial.print(F(",\"type4\":true"));
  }
  if (ndef.valid) {
    Serial.print(F(",\"ndef_text\":"));
    printJsonString(ndef.text);
    if (!ndef.ball_id.isEmpty()) {
      Serial.print(F(",\"ball_id\":"));
      printJsonString(ndef.ball_id);
    }
    if (!ndef.uri.isEmpty()) {
      Serial.print(F(",\"ndef_uri\":"));
      printJsonString(ndef.uri);
      Serial.print(F(",\"service_uri_ok\":"));
      Serial.print(ndef.service_uri ? F("true") : F("false"));
    }
    if (!ndef.device_id.isEmpty()) {
      Serial.print(F(",\"device_id\":"));
      printJsonString(ndef.device_id);
    }
    if (!ndef.firmware_version.isEmpty()) {
      Serial.print(F(",\"firmware_version\":"));
      printJsonString(ndef.firmware_version);
    }
  } else {
    Serial.print(F(",\"ndef_error\":"));
    printJsonString(ndef.error);
  }
  Serial.println('}');
}

[[noreturn]] void haltWithError(const __FlashStringHelper *message) {
  Serial.print(F("{\"event\":\"fatal\",\"message\":\""));
  Serial.print(message);
  Serial.println(F("\"}"));
  while (true) {
    delay(1000);
  }
}

}  // namespace

void setup() {
  // Keep the PN532 deselected before the SPI peripheral starts. GPIO2 is also
  // an ESP32-C3 strapping pin; an external pull-up still protects the earlier
  // reset-sampling window, before application code can run.
  pinMode(PT_PN532_SS, OUTPUT);
  digitalWrite(PT_PN532_SS, HIGH);

  Serial.begin(PT_SERIAL_BAUD);
  delay(800);

  Serial.println(F("{\"event\":\"boot\",\"app\":\"putttrack-pn532-reader\"}"));
  Serial.printf("{\"event\":\"spi_config\",\"sck\":%d,\"miso\":%d,"
                "\"mosi\":%d,\"ss\":%d}\n",
                PT_PN532_SCK, PT_PN532_MISO, PT_PN532_MOSI, PT_PN532_SS);

  roller_motor.begin();
  cupBegin();

  SPI.begin(PT_PN532_SCK, PT_PN532_MISO, PT_PN532_MOSI, PT_PN532_SS);
  pn532.begin();

  const uint32_t version = pn532.getFirmwareVersion();
  if (version == 0) {
    haltWithError(F("pn532_not_found_check_power_wiring_and_spi_switch"));
  }

  Serial.printf("{\"event\":\"pn532_ready\",\"chip\":%u,"
                "\"firmware_major\":%u,\"firmware_minor\":%u}\n",
                static_cast<unsigned>((version >> 24U) & 0xFFU),
                static_cast<unsigned>((version >> 16U) & 0xFFU),
                static_cast<unsigned>((version >> 8U) & 0xFFU));

  if (!pn532.SAMConfig()) {
    haltWithError(F("pn532_sam_config_failed"));
  }
  if (!pn532.setPassiveActivationRetries(0x00)) {
    haltWithError(F("pn532_passive_retry_config_failed"));
  }
  Serial.printf("{\"event\":\"scan_ready\",\"technology\":\"NFC-A\","
                "\"stress_test\":%s,\"scan_timeout_ms\":%u,\"scan_gap_ms\":%u,"
                "\"command_window_ms\":%u,\"field_off_ms\":%u}\n",
                PT_NFC_STRESS_TEST ? "true" : "false",
                unsigned(PT_SCAN_TIMEOUT_MS), unsigned(PT_SCAN_GAP_MS),
                unsigned(PT_TYPE4_COMMAND_WINDOW_MS), unsigned(PT_TYPE4_FIELD_OFF_MS));
}

void loop() {
  cupService();
  roller_motor.serviceConsole();
  roller_motor.serviceDeadline();

  if (rf_paused) {
    if (static_cast<int32_t>(millis() - rf_resume_at) >= 0) {
      handleNfcConsoleCommand("nfc rf resume");
    }
    delay(2);
    return;
  }

  // During a timed roller run, prioritize the stop deadline and host emergency
  // command. PN532 polling can block for hundreds of milliseconds and is not
  // needed while collecting controlled-motion data.
  if (roller_motor.running()) {
    delay(2);
    return;
  }

  uint8_t uid[10] = {};
  uint8_t uid_length = 0;
  const bool found = pn532.readPassiveTargetID(
      PN532_MIFARE_ISO14443A, uid, &uid_length, PT_SCAN_TIMEOUT_MS);
  const uint32_t now = millis();

  if (found) {
    const String uid_hex = uidToHex(uid, uid_length);
    if (uid_hex == active_uid) {
      ++consecutive_reads;
    } else {
      active_uid = uid_hex;
      consecutive_reads = 1;
      stable_reported = false;
    }
    last_seen_ms = now;

    // SAK bit 5 advertises ISO-DEP support. Do not probe a Type 2 tag
    // with a Type 4 SELECT APDU: it can end the session and leave a delayed
    // PN532 response that breaks the fallback activation.
    const bool iso_dep = (pn532.lastTargetSAK() & 0x20U) != 0U;
    NdefResult ndef = iso_dep ? readType4Ndef() : readType2Ndef();
    active_type4 = ndef.type4 && ndef.valid && ndef.service_uri;
    active_device_id = active_type4 ? ndef.device_id : "";
    printTagEvent(uid_hex, ndef);
    if (rf_status_pending && ndef.valid && ndef.type4) {
      rf_status_pending = false;
      printRfStatus();
    }

    if (active_type4 && !PT_NFC_STRESS_TEST) {
      // Keep a short window for a host-triggered migration write, then cycle
      // the RF field so the Type 4 target starts a fresh transaction without
      // requiring the operator to lift and replace the Ball.
      const uint32_t command_deadline = millis() + PT_TYPE4_COMMAND_WINDOW_MS;
      while (static_cast<int32_t>(command_deadline - millis()) > 0) {
        roller_motor.serviceConsole();
        roller_motor.serviceDeadline();
        delay(1);
      }
    }

    if (!stable_reported && consecutive_reads >= PT_STABLE_READ_TARGET) {
      Serial.print(F("{\"event\":\"stability_pass\",\"uid\":"));
      printJsonString(uid_hex);
      Serial.print(F(",\"reads\":"));
      Serial.print(consecutive_reads);
      Serial.println('}');
      stable_reported = true;
    }
  } else if (!active_uid.isEmpty()) {
    if (consecutive_reads > 0) {
      Serial.print(F("{\"event\":\"scan_miss\",\"uid\":"));
      printJsonString(active_uid);
      Serial.print(F(",\"completed_reads\":"));
      Serial.print(consecutive_reads);
      Serial.println('}');
      consecutive_reads = 0;
      stable_reported = false;
    }

    if ((now - last_seen_ms) >= PT_TAG_REMOVED_MS) {
      Serial.print(F("{\"event\":\"tag_removed\",\"uid\":"));
      printJsonString(active_uid);
      Serial.println('}');
      active_uid = "";
      active_device_id = "";
      active_type4 = false;
    }
  }

  // Reset even after a failed activation: a target left selected by a partial
  // transaction must be able to start over without physical removal.
  active_type4 = false;
  active_device_id = "";
  // A pause received in the migration window must survive this loop's tail.
  if (rf_paused) return;
  if (!pn532.setRFField(false)) {
    Serial.println(F("{\"event\":\"rf_cycle_failed\",\"phase\":\"off\"}"));
  }
  delay(PT_TYPE4_FIELD_OFF_MS);
  if (!pn532.setRFField(true)) {
    Serial.println(F("{\"event\":\"rf_cycle_failed\",\"phase\":\"on\"}"));
  }
  delay(PT_SCAN_GAP_MS);
}
