#include "roller_motor.h"

#include <cstdlib>

#include "app_config.h"

namespace {

constexpr uint32_t kBusGapMs = 2;

enum class DiagnosticChecksumMode : uint8_t {
  kFixed6b,
  kXor,
  kCrc8,
  kModbusCrc16,
};

uint8_t checksumXor(const uint8_t *bytes, size_t length) {
  uint8_t result = 0;
  for (size_t i = 0; i < length; ++i) {
    result ^= bytes[i];
  }
  return result;
}

uint8_t checksumCrc8(const uint8_t *bytes, size_t length) {
  uint8_t crc = 0;
  for (size_t i = 0; i < length; ++i) {
    crc ^= bytes[i];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x80U) != 0U ? static_cast<uint8_t>((crc << 1U) ^ 0x07U)
                                : static_cast<uint8_t>(crc << 1U);
    }
  }
  return crc;
}

uint16_t checksumModbus(const uint8_t *bytes, size_t length) {
  uint16_t crc = 0xFFFFU;
  for (size_t i = 0; i < length; ++i) {
    crc ^= bytes[i];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x0001U) != 0U
                ? static_cast<uint16_t>((crc >> 1U) ^ 0xA001U)
                : static_cast<uint16_t>(crc >> 1U);
    }
  }
  return crc;
}

size_t appendChecksum(DiagnosticChecksumMode mode, uint8_t *frame,
                      size_t length) {
  switch (mode) {
    case DiagnosticChecksumMode::kXor:
      frame[length] = checksumXor(frame, length);
      return length + 1U;
    case DiagnosticChecksumMode::kCrc8:
      frame[length] = checksumCrc8(frame, length);
      return length + 1U;
    case DiagnosticChecksumMode::kModbusCrc16: {
      const uint16_t crc = checksumModbus(frame, length);
      frame[length] = static_cast<uint8_t>(crc & 0xFFU);
      frame[length + 1U] = static_cast<uint8_t>(crc >> 8U);
      return length + 2U;
    }
    case DiagnosticChecksumMode::kFixed6b:
    default:
      frame[length] = 0x6BU;
      return length + 1U;
  }
}

bool checksumValid(DiagnosticChecksumMode mode, const uint8_t *frame,
                   size_t length) {
  if (length < 3U) {
    return false;
  }
  switch (mode) {
    case DiagnosticChecksumMode::kXor:
      return frame[length - 1U] == checksumXor(frame, length - 1U);
    case DiagnosticChecksumMode::kCrc8:
      return frame[length - 1U] == checksumCrc8(frame, length - 1U);
    case DiagnosticChecksumMode::kModbusCrc16: {
      if (length < 4U) {
        return false;
      }
      const uint16_t expected = checksumModbus(frame, length - 2U);
      const uint16_t received =
          static_cast<uint16_t>(frame[length - 2U]) |
          (static_cast<uint16_t>(frame[length - 1U]) << 8U);
      return received == expected;
    }
    case DiagnosticChecksumMode::kFixed6b:
    default:
      return frame[length - 1U] == 0x6BU;
  }
}

const char *checksumModeName(DiagnosticChecksumMode mode) {
  switch (mode) {
    case DiagnosticChecksumMode::kXor:
      return "xor";
    case DiagnosticChecksumMode::kCrc8:
      return "crc8_atm";
    case DiagnosticChecksumMode::kModbusCrc16:
      return "modbus_crc16";
    case DiagnosticChecksumMode::kFixed6b:
    default:
      return "fixed_6b";
  }
}

void printHexByte(uint8_t value) {
  if (value < 0x10U) {
    Serial.print('0');
  }
  Serial.print(value, HEX);
}

}  // namespace

RollerMotor::RollerMotor(HardwareSerial &uart) : uart_(uart) {}

void RollerMotor::begin() {
  // Enter a known-safe state on every MCU boot. This also stops a prior speed
  // command if the ESP32 reset while the separately powered driver stayed on.
  address_ = PT_MOTOR_ADDRESS;
  baud_ = PT_MOTOR_BAUD;
  uart_.begin(baud_, SERIAL_8N1, PT_MOTOR_RX, PT_MOTOR_TX);
  Serial.printf(
      "{\"event\":\"motor_uart_ready\",\"rx_gpio\":%d,\"tx_gpio\":%d,"
      "\"baud\":%d,\"address\":%d,\"automatic_motion\":false}\n",
      PT_MOTOR_RX, PT_MOTOR_TX, PT_MOTOR_BAUD, PT_MOTOR_ADDRESS);
  stop("boot_safe_state");
  disable();
  // The proven controller waits 1.5 s for the driver power rail and firmware.
  // Repeat the safe-state pair afterwards so a simultaneous cold start is
  // covered without delaying the first best-effort stop.
  delay(1500);
  stop("post_power_settle_safe_state");
  disable();
  printHelp();
}

bool RollerMotor::running() const { return running_; }

bool RollerMotor::deadlineReached(uint32_t deadline_ms) const {
  return static_cast<int32_t>(millis() - deadline_ms) >= 0;
}

void RollerMotor::serviceConsole() {
  while (Serial.available() > 0) {
    const int raw = Serial.read();
    if (raw < 0) {
      break;
    }
    const char ch = static_cast<char>(raw);
    if (ch == '\r') {
      continue;
    }
    if (ch == '\n') {
      console_line_[console_length_] = '\0';
      if (console_length_ > 0U) {
        handleLine(String(console_line_));
      }
      console_length_ = 0;
      continue;
    }
    if (console_length_ + 1U >= sizeof(console_line_)) {
      console_length_ = 0;
      Serial.println(F("{\"event\":\"motor_command_rejected\","
                       "\"reason\":\"line_too_long\"}"));
      continue;
    }
    console_line_[console_length_++] = ch;
  }
}

void RollerMotor::serviceDeadline() {
  if (armed_ && deadlineReached(arm_deadline_ms_)) {
    armed_ = false;
    Serial.println(F("{\"event\":\"motor_disarmed\",\"reason\":\"arm_timeout\"}"));
  }
  if (running_ && deadlineReached(stop_deadline_ms_)) {
    stop("run_timeout");
    disable();
  }
}

void RollerMotor::handleLine(String line) {
  line.trim();
  line.toLowerCase();

  if (line == "motor help") {
    printHelp();
    return;
  }
  if (line == "motor probe") {
    probe();
    return;
  }
  if (line == "motor scan") {
    scan();
    return;
  }
  if (line == "motor status") {
    status();
    return;
  }
  if (line == "motor arm") {
    arm();
    return;
  }
  if (line == "motor stop") {
    stop("host_command");
    return;
  }
  if (line == "motor disable") {
    disable();
    return;
  }

  long rpm = 0;
  unsigned long seconds = 0;
  char trailing = '\0';
  if (sscanf(line.c_str(), "motor run %ld %lu %c", &rpm, &seconds, &trailing) == 2) {
    if (rpm < -PT_MOTOR_MAX_RPM || rpm > PT_MOTOR_MAX_RPM) {
      Serial.println(F("{\"event\":\"motor_command_rejected\","
                       "\"reason\":\"unsafe_run_limits\"}"));
      return;
    }
    run(static_cast<int>(rpm), static_cast<uint32_t>(seconds));
    return;
  }

  Serial.println(F("{\"event\":\"motor_command_rejected\","
                   "\"reason\":\"unknown_command\"}"));
  printHelp();
}

void RollerMotor::printHelp() const {
  Serial.printf(
      "{\"event\":\"motor_help\",\"commands\":[\"motor probe\","
      "\"motor scan\",\"motor status\",\"motor arm\","
      "\"motor run <signed_rpm> <seconds>\",\"motor stop\","
      "\"motor disable\"],\"max_abs_rpm\":%d,"
      "\"max_seconds\":%d}\n",
      PT_MOTOR_MAX_RPM, PT_MOTOR_MAX_RUN_SECONDS);
}

void RollerMotor::drainRx() {
  while (uart_.available() > 0) {
    uart_.read();
  }
}

void RollerMotor::sendFrame(uint8_t command, const uint8_t *payload,
                            size_t payload_length) {
  uint8_t frame[16] = {};
  size_t length = 0;
  frame[length++] = address_;
  frame[length++] = command;
  for (size_t i = 0; i < payload_length && length + 1U < sizeof(frame); ++i) {
    frame[length++] = payload[i];
  }
  frame[length++] = kChecksum;
  delay(kBusGapMs);
  uart_.write(frame, length);
  uart_.flush();
  delay(kBusGapMs);
}

bool RollerMotor::readReply(uint8_t expected_command, uint8_t *reply,
                            size_t reply_length, uint32_t timeout_ms) {
  size_t received = 0;
  const uint32_t started_ms = millis();
  while (static_cast<uint32_t>(millis() - started_ms) <= timeout_ms) {
    while (uart_.available() > 0) {
      const int raw = uart_.read();
      if (raw < 0) {
        continue;
      }
      const uint8_t value = static_cast<uint8_t>(raw);
      if (received == 0U && value != address_) {
        continue;
      }
      if (received == 1U && value != expected_command) {
        // The documented error response is 01 00 EE 6B. Report it as a
        // failed command instead of accidentally accepting it as payload.
        if (value == 0x00U) {
          reply[received++] = value;
          while (received < reply_length && uart_.available() > 0) {
            reply[received++] = static_cast<uint8_t>(uart_.read());
          }
          return false;
        }
        received = 0;
        continue;
      }
      reply[received++] = value;
      if (received == reply_length) {
        return reply[reply_length - 1U] == kChecksum;
      }
    }
    delay(1);
  }
  return false;
}

bool RollerMotor::readCommand(uint8_t command, uint8_t *reply,
                              size_t reply_length, uint32_t timeout_ms) {
  drainRx();
  sendFrame(command, nullptr, 0);
  return readReply(command, reply, reply_length, timeout_ms);
}

bool RollerMotor::action(uint8_t command, const uint8_t *payload,
                         size_t payload_length, const char *name) {
  uint8_t reply[4] = {};
  drainRx();
  sendFrame(command, payload, payload_length);
  const bool frame_ok = readReply(command, reply, sizeof(reply));
  // Fielded EMM revisions have used both 0x00 and the documented 0x02 for a
  // successful write acknowledgement.
  const bool accepted = frame_ok && (reply[2] == 0x00U || reply[2] == 0x02U);
  Serial.print(F("{\"event\":\"motor_action_ack\",\"action\":\""));
  Serial.print(name);
  Serial.print(F("\",\"accepted\":"));
  Serial.print(accepted ? F("true") : F("false"));
  Serial.print(F(",\"reply\":\""));
  for (size_t i = 0; i < sizeof(reply); ++i) {
    printHexByte(reply[i]);
  }
  Serial.println(F("\"}"));
  return accepted;
}

void RollerMotor::probe() {
  uint8_t reply[5] = {};
  probe_ok_ = readCommand(0x1F, reply, sizeof(reply));
  if (probe_ok_) {
    probe_deadline_ms_ = millis() + PT_MOTOR_PROBE_VALID_MS;
  }
  Serial.print(F("{\"event\":\"motor_probe\",\"ok\":"));
  Serial.print(probe_ok_ ? F("true") : F("false"));
  if (probe_ok_) {
    Serial.print(F(",\"firmware_code\":"));
    Serial.print(reply[2]);
    Serial.print(F(",\"hardware_code\":"));
    Serial.print(reply[3]);
  }
  Serial.println('}');
}

void RollerMotor::scan() {
  // These are the exact read-only compatibility candidates used by the
  // already proven esp32s3_eth_ball_BACK controller.
  // Every rate offered by the Emm42_V5 menu. The older controller's six-rate
  // probe omitted 25 kbit/s and the three high-speed settings.
  static constexpr uint32_t BAUD_RATES[] = {
      115200, 57600, 38400, 25000, 19200, 9600, 256000, 512000, 921600};
  static constexpr DiagnosticChecksumMode CHECKSUM_MODES[] = {
      DiagnosticChecksumMode::kFixed6b, DiagnosticChecksumMode::kXor,
      DiagnosticChecksumMode::kCrc8, DiagnosticChecksumMode::kModbusCrc16};
  static constexpr uint32_t HEADER_TIMEOUT_MS = 60;
  static constexpr uint32_t BYTE_TIMEOUT_MS = 15;

  probe_ok_ = false;
  armed_ = false;

  // Route UART RX to the TX pin briefly and send only the read-version frame.
  // This verifies the ESP32 UART and GPIO matrix without requiring an external
  // loopback wire and cannot request motor motion.
  uart_.end();
  uart_.begin(PT_MOTOR_BAUD, SERIAL_8N1, PT_MOTOR_TX, PT_MOTOR_TX);
  drainRx();
  const uint8_t loopback_request[] = {PT_MOTOR_ADDRESS, 0x1FU, kChecksum};
  uart_.write(loopback_request, sizeof(loopback_request));
  uart_.flush();
  uint8_t loopback_reply[sizeof(loopback_request)] = {};
  size_t loopback_received = 0;
  const uint32_t loopback_started_ms = millis();
  while (millis() - loopback_started_ms < 50U &&
         loopback_received < sizeof(loopback_reply)) {
    while (uart_.available() > 0 &&
           loopback_received < sizeof(loopback_reply)) {
      loopback_reply[loopback_received++] =
          static_cast<uint8_t>(uart_.read());
    }
    delay(1);
  }
  const bool loopback_ok =
      loopback_received == sizeof(loopback_request) &&
      memcmp(loopback_request, loopback_reply, sizeof(loopback_request)) == 0;
  Serial.print(F("{\"event\":\"motor_uart_loopback\",\"ok\":"));
  Serial.print(loopback_ok ? F("true") : F("false"));
  Serial.print(F(",\"observed_bytes\":"));
  Serial.print(loopback_received);
  Serial.println('}');
  uart_.end();
  uart_.begin(PT_MOTOR_BAUD, SERIAL_8N1, PT_MOTOR_RX, PT_MOTOR_TX);
  baud_ = PT_MOTOR_BAUD;
  address_ = PT_MOTOR_ADDRESS;
  delay(10);

  // First observe the RX line without transmitting. A correctly wired UART
  // should be idle here; bytes indicate a floating/noisy line, an electrical
  // level problem, or unsolicited traffic from the driver.
  drainRx();
  uint8_t idle_bytes[16] = {};
  size_t idle_total = 0;
  const uint32_t idle_started_ms = millis();
  while (millis() - idle_started_ms < 500U) {
    while (uart_.available() > 0) {
      const int raw = uart_.read();
      if (raw < 0) {
        continue;
      }
      if (idle_total < sizeof(idle_bytes)) {
        idle_bytes[idle_total] = static_cast<uint8_t>(raw);
      }
      ++idle_total;
    }
    delay(1);
  }
  Serial.print(F("{\"event\":\"motor_rx_idle\",\"duration_ms\":500,"
                 "\"rx_gpio\":"));
  Serial.print(PT_MOTOR_RX);
  Serial.print(F(",\"rx_idle_level\":"));
  Serial.print(digitalRead(PT_MOTOR_RX));
  Serial.print(F(",\"observed_bytes\":"));
  Serial.print(idle_total);
  if (idle_total > 0U) {
    Serial.print(F(",\"sample_hex\":\""));
    const size_t shown =
        idle_total < sizeof(idle_bytes) ? idle_total : sizeof(idle_bytes);
    for (size_t i = 0; i < shown; ++i) {
      printHexByte(idle_bytes[i]);
    }
    Serial.print('"');
  }
  Serial.println('}');

  size_t observed_bytes = 0;
  uint8_t first_observed[16] = {};
  size_t first_observed_length = 0;
  uint32_t first_observed_baud = 0;
  uint8_t first_observed_address = 0;
  DiagnosticChecksumMode first_observed_mode =
      DiagnosticChecksumMode::kFixed6b;
  Serial.println(F("{\"event\":\"motor_scan_started\","
                   "\"read_only\":true,\"addresses\":16,\"baud_rates\":9,"
                   "\"checksum_modes\":4}"));
  for (const uint32_t candidate_baud : BAUD_RATES) {
    baud_ = candidate_baud;
    uart_.updateBaudRate(baud_);
    delay(25);
    for (uint8_t candidate_address = 1; candidate_address <= 16;
         ++candidate_address) {
      address_ = candidate_address;
      for (const DiagnosticChecksumMode mode : CHECKSUM_MODES) {
        drainRx();
        uint8_t request[4] = {address_, 0x1FU, 0, 0};
        const size_t request_length = appendChecksum(mode, request, 2U);
        delay(kBusGapMs);
        uart_.write(request, request_length);
        uart_.flush();
        delay(kBusGapMs);

        const size_t expected_length =
            mode == DiagnosticChecksumMode::kModbusCrc16 ? 6U : 5U;
        uint8_t reply[6] = {};
        size_t received = 0;
        const uint32_t started_ms = millis();
        uint32_t last_byte_ms = started_ms;
        while (received < expected_length) {
          if (uart_.available() > 0) {
            reply[received++] = static_cast<uint8_t>(uart_.read());
            last_byte_ms = millis();
            continue;
          }
          const uint32_t now = millis();
          if ((received == 0U && now - started_ms > HEADER_TIMEOUT_MS) ||
              (received > 0U && now - last_byte_ms > BYTE_TIMEOUT_MS)) {
            break;
          }
          delay(1);
        }
        observed_bytes += received;
        if (received > 0U && first_observed_length == 0U) {
          first_observed_length =
              received < sizeof(first_observed) ? received
                                                : sizeof(first_observed);
          memcpy(first_observed, reply, first_observed_length);
          first_observed_baud = candidate_baud;
          first_observed_address = candidate_address;
          first_observed_mode = mode;
        }
        if (received != expected_length || reply[0] != address_ ||
            reply[1] != 0x1FU || !checksumValid(mode, reply, received)) {
          continue;
        }

        const bool motion_ready = mode == DiagnosticChecksumMode::kFixed6b;
        probe_ok_ = motion_ready;
        if (probe_ok_) {
          probe_deadline_ms_ = millis() + PT_MOTOR_PROBE_VALID_MS;
        }
        Serial.printf(
            "{\"event\":\"motor_scan\",\"ok\":true,"
            "\"motion_ready\":%s,\"baud\":%lu,\"address\":%u,"
            "\"checksum_mode\":\"%s\",\"firmware_code\":%u,"
            "\"hardware_code\":%u}\n",
            motion_ready ? "true" : "false", static_cast<unsigned long>(baud_),
            address_, checksumModeName(mode), reply[2], reply[3]);
        return;
      }
    }
  }

  baud_ = PT_MOTOR_BAUD;
  address_ = PT_MOTOR_ADDRESS;
  uart_.updateBaudRate(baud_);
  Serial.print(F("{\"event\":\"motor_scan\",\"ok\":false,"
                 "\"observed_bytes\":"));
  Serial.print(observed_bytes);
  if (first_observed_length > 0U) {
    Serial.print(F(",\"first_observed_baud\":"));
    Serial.print(first_observed_baud);
    Serial.print(F(",\"first_observed_address\":"));
    Serial.print(first_observed_address);
    Serial.print(F(",\"first_observed_checksum\":\""));
    Serial.print(checksumModeName(first_observed_mode));
    Serial.print(F("\",\"first_observed_hex\":\""));
    for (size_t i = 0; i < first_observed_length; ++i) {
      printHexByte(first_observed[i]);
    }
    Serial.print('"');
  }
  Serial.println('}');
}

void RollerMotor::status() {
  uint8_t voltage_reply[5] = {};
  uint8_t speed_reply[6] = {};
  uint8_t position_reply[8] = {};
  uint8_t state_reply[4] = {};
  const bool voltage_ok = readCommand(0x24, voltage_reply, sizeof(voltage_reply));
  const bool speed_ok = readCommand(0x35, speed_reply, sizeof(speed_reply));
  const bool position_ok =
      readCommand(0x36, position_reply, sizeof(position_reply));
  const bool state_ok = readCommand(0x3A, state_reply, sizeof(state_reply));

  const uint16_t millivolts =
      (static_cast<uint16_t>(voltage_reply[2]) << 8U) | voltage_reply[3];
  const int16_t magnitude = static_cast<int16_t>(
      (static_cast<uint16_t>(speed_reply[3]) << 8U) | speed_reply[4]);
  const int16_t rpm = speed_reply[2] == 0x01U ? -magnitude : magnitude;
  const uint32_t position_magnitude =
      (static_cast<uint32_t>(position_reply[3]) << 24U) |
      (static_cast<uint32_t>(position_reply[4]) << 16U) |
      (static_cast<uint32_t>(position_reply[5]) << 8U) |
      static_cast<uint32_t>(position_reply[6]);
  const int64_t position_raw = position_reply[2] == 0x01U
                                   ? -static_cast<int64_t>(position_magnitude)
                                   : static_cast<int64_t>(position_magnitude);
  const uint8_t flags = state_reply[2];

  Serial.print(F("{\"event\":\"motor_status\",\"ok\":"));
  Serial.print((voltage_ok && speed_ok && position_ok && state_ok) ? F("true")
                                                                   : F("false"));
  if (voltage_ok) {
    Serial.print(F(",\"bus_mv\":"));
    Serial.print(millivolts);
  }
  if (speed_ok) {
    Serial.print(F(",\"rpm\":"));
    Serial.print(rpm);
  }
  if (position_ok) {
    Serial.print(F(",\"position_raw\":"));
    Serial.printf("%lld", static_cast<long long>(position_raw));
  }
  if (state_ok) {
    Serial.print(F(",\"enabled\":"));
    Serial.print((flags & 0x01U) ? F("true") : F("false"));
    Serial.print(F(",\"in_position\":"));
    Serial.print((flags & 0x02U) ? F("true") : F("false"));
    Serial.print(F(",\"stalled\":"));
    Serial.print((flags & 0x04U) ? F("true") : F("false"));
    Serial.print(F(",\"stall_protect\":"));
    Serial.print((flags & 0x08U) ? F("true") : F("false"));
  }
  Serial.println('}');
}

void RollerMotor::arm() {
  if (!probe_ok_ || deadlineReached(probe_deadline_ms_)) {
    probe_ok_ = false;
    Serial.println(F("{\"event\":\"motor_command_rejected\","
                     "\"reason\":\"fresh_probe_required\"}"));
    return;
  }
  if (running_) {
    Serial.println(F("{\"event\":\"motor_command_rejected\","
                     "\"reason\":\"already_running\"}"));
    return;
  }
  armed_ = true;
  arm_deadline_ms_ = millis() + PT_MOTOR_ARM_WINDOW_MS;
  Serial.printf("{\"event\":\"motor_armed\",\"window_ms\":%d}\n",
                PT_MOTOR_ARM_WINDOW_MS);
}

void RollerMotor::run(int rpm, uint32_t seconds) {
  if (!probe_ok_ || !armed_) {
    Serial.println(F("{\"event\":\"motor_command_rejected\","
                     "\"reason\":\"probe_and_arm_required\"}"));
    return;
  }
  if (deadlineReached(arm_deadline_ms_)) {
    armed_ = false;
    Serial.println(F("{\"event\":\"motor_command_rejected\","
                     "\"reason\":\"arm_timeout\"}"));
    return;
  }
  armed_ = false;  // One arm permits exactly one run command.
  if (rpm == 0 || abs(rpm) > PT_MOTOR_MAX_RPM || seconds == 0U ||
      seconds > PT_MOTOR_MAX_RUN_SECONDS) {
    Serial.println(F("{\"event\":\"motor_command_rejected\","
                     "\"reason\":\"unsafe_run_limits\"}"));
    return;
  }

  const uint8_t enable_payload[] = {0xAB, 0x01, 0x00};
  if (!action(0xF3, enable_payload, sizeof(enable_payload), "enable")) {
    stop("enable_not_acknowledged");
    return;
  }
  enabled_ = true;

  const uint16_t magnitude = static_cast<uint16_t>(abs(rpm));
  const uint8_t speed_payload[] = {
      static_cast<uint8_t>(rpm > 0 ? 0x01 : 0x00),
      static_cast<uint8_t>(magnitude >> 8U),
      static_cast<uint8_t>(magnitude & 0xFFU), kAcceleration, 0x00};
  if (!action(0xF6, speed_payload, sizeof(speed_payload), "run")) {
    stop("run_not_acknowledged");
    disable();
    return;
  }

  running_ = true;
  stop_deadline_ms_ = millis() + seconds * 1000U;
  Serial.printf("{\"event\":\"motor_running\",\"rpm\":%d,\"seconds\":%lu}\n",
                rpm, static_cast<unsigned long>(seconds));
}

void RollerMotor::stop(const char *reason) {
  const uint8_t stop_payload[] = {0x98, 0x00};
  // Match the proven controller's redundant immediate-stop policy. Keep the
  // drive enabled briefly while speed settles; disabling immediately can let
  // the mechanism coast freely even though the first STOP was acknowledged.
  static constexpr uint16_t STOP_INTERVALS_MS[] = {0, 8, 24};
  bool accepted = false;
  for (const uint16_t interval_ms : STOP_INTERVALS_MS) {
    if (interval_ms > 0U) {
      delay(interval_ms);
    }
    accepted =
        action(0xFE, stop_payload, sizeof(stop_payload), "stop") || accepted;
  }
  int16_t last_rpm = 0;
  const bool settled = waitForZeroSpeed(750U, last_rpm);
  running_ = false;
  armed_ = false;
  Serial.print(F("{\"event\":\"motor_stopped\",\"reason\":\""));
  Serial.print(reason);
  Serial.print(F("\",\"acknowledged\":"));
  Serial.print(accepted ? F("true") : F("false"));
  Serial.print(F(",\"settled\":"));
  Serial.print(settled ? F("true") : F("false"));
  Serial.print(F(",\"final_rpm\":"));
  Serial.print(last_rpm);
  Serial.println('}');
}

bool RollerMotor::waitForZeroSpeed(uint32_t timeout_ms, int16_t &last_rpm) {
  bool read_ok = false;
  const uint32_t started_ms = millis();
  do {
    uint8_t speed_reply[6] = {};
    read_ok = readCommand(0x35, speed_reply, sizeof(speed_reply), 80U);
    if (read_ok) {
      const int16_t magnitude = static_cast<int16_t>(
          (static_cast<uint16_t>(speed_reply[3]) << 8U) | speed_reply[4]);
      last_rpm = speed_reply[2] == 0x01U ? -magnitude : magnitude;
      if (last_rpm == 0) {
        return true;
      }
    }
    delay(40);
  } while (millis() - started_ms < timeout_ms);
  return false;
}

void RollerMotor::disable() {
  if (running_) {
    stop("disable_requested");
  }
  const uint8_t disable_payload[] = {0xAB, 0x00, 0x00};
  const bool accepted = action(0xF3, disable_payload, sizeof(disable_payload),
                               "disable");
  if (accepted) {
    enabled_ = false;
  }
}
