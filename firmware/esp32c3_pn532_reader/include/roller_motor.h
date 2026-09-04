#pragma once

#include <Arduino.h>

class RollerMotor {
 public:
  explicit RollerMotor(HardwareSerial &uart);

  void begin();
  void serviceConsole();
  void serviceDeadline();
  bool running() const;

 private:
  static constexpr uint8_t kChecksum = 0x6B;
  static constexpr uint8_t kDefaultAcceleration = 20;
  static constexpr size_t kConsoleLineBytes = 96;

  HardwareSerial &uart_;
  char console_line_[kConsoleLineBytes] = {};
  size_t console_length_ = 0;
  bool probe_ok_ = false;
  bool armed_ = false;
  bool running_ = false;
  bool enabled_ = false;
  bool ramp_stop_requested_ = false;
  uint8_t deceleration_ = 0;
  int running_rpm_ = 0;
  uint8_t address_ = 1;
  uint32_t baud_ = 115200;
  uint32_t probe_deadline_ms_ = 0;
  uint32_t arm_deadline_ms_ = 0;
  uint32_t stop_deadline_ms_ = 0;

  void handleLine(String line);
  void printHelp() const;
  void probe();
  void scan();
  void status();
  void arm();
  void run(int rpm, uint32_t seconds, uint8_t acceleration, int deceleration);
  void stop(const char *reason);
  void rampStop(const char *reason);
  void disable();

  void drainRx();
  void sendFrame(uint8_t command, const uint8_t *payload, size_t payload_length);
  bool readReply(uint8_t expected_command, uint8_t *reply, size_t reply_length,
                 uint32_t timeout_ms = 180);
  bool readCommand(uint8_t command, uint8_t *reply, size_t reply_length,
                   uint32_t timeout_ms = 180);
  bool action(uint8_t command, const uint8_t *payload, size_t payload_length,
              const char *name);
  bool issueImmediateStop(int16_t &last_rpm, bool &accepted);
  bool waitForZeroSpeed(uint32_t timeout_ms, int16_t &last_rpm);
  bool deadlineReached(uint32_t deadline_ms) const;
};
