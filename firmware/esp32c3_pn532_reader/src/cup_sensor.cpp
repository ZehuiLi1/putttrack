#include "cup_sensor.h"
#include "app_config.h"
#include <esp_system.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>

#ifndef PT_CUP_GPIO
#define PT_CUP_GPIO 7
#endif
#ifndef PT_CUP_ACTIVE_LOW
#define PT_CUP_ACTIVE_LOW 1
#endif
#ifndef PT_CUP_DEBOUNCE_MS
#define PT_CUP_DEBOUNCE_MS 5
#endif
static_assert(PT_CUP_GPIO != PT_PN532_SCK && PT_CUP_GPIO != PT_PN532_MISO &&
              PT_CUP_GPIO != PT_PN532_MOSI && PT_CUP_GPIO != PT_PN532_SS &&
              PT_CUP_GPIO != PT_MOTOR_RX && PT_CUP_GPIO != PT_MOTOR_TX,
              "Cup input conflicts with another peripheral");
namespace {
struct Sample {uint32_t sequence; uint32_t at; bool blocked; char round[33];};
QueueHandle_t samples;
portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
char active_round[33] = "";
char boot_id[17];
uint32_t sequence = 0;
bool stable = false;
bool overflow = false;
void emit(bool blocked) {
  Sample sample{};
  portENTER_CRITICAL(&mux);
  sample.sequence = ++sequence;
  sample.at = millis();
  sample.blocked = blocked;
  memcpy(sample.round, active_round, sizeof(active_round));
  portEXIT_CRITICAL(&mux);
  if (xQueueSend(samples, &sample, 0) != pdTRUE) {
    portENTER_CRITICAL(&mux); overflow = true; portEXIT_CRITICAL(&mux);
  }
}
void poll(void *) {
  bool candidate = digitalRead(PT_CUP_GPIO) == (PT_CUP_ACTIVE_LOW ? LOW : HIGH);
  uint32_t since = millis(), heartbeat = 0;
  for (;;) {
    const uint32_t now = millis();
    const bool current = digitalRead(PT_CUP_GPIO) == (PT_CUP_ACTIVE_LOW ? LOW : HIGH);
    if (current != candidate) {candidate = current; since = now;}
    if ((now - since) >= PT_CUP_DEBOUNCE_MS && candidate != stable) {
      stable = candidate;
      emit(stable);
      heartbeat = now;
    } else if ((now - heartbeat) >= 500) {
      emit(stable);
      heartbeat = now;
    }
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}
}
void cupBegin() {
  pinMode(PT_CUP_GPIO, INPUT_PULLUP);
  snprintf(boot_id, sizeof(boot_id), "%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random());
  samples = xQueueCreate(16, sizeof(Sample));
  if (!samples || xTaskCreate(poll, "cup-input", 2048, nullptr, 1, nullptr) != pdPASS) {
    Serial.println(F("{\"event\":\"cup_fault\",\"reason\":\"task_start_failed\"}"));
    return;
  }
  Serial.printf("{\"event\":\"cup_ready\",\"gpio\":%u,\"active_low\":%s,\"debounce_ms\":%u}\n",
                PT_CUP_GPIO, PT_CUP_ACTIVE_LOW ? "true" : "false", PT_CUP_DEBOUNCE_MS);
}
bool cupCommand(const String &line) {
  if (!line.startsWith("cup arm ")) return false;
  const String token = line.substring(8);
  if (token.length() != 32) return true;
  for (size_t i=0; i<token.length(); ++i) if (!isxdigit(token[i])) return true;
  portENTER_CRITICAL(&mux);
  memcpy(active_round, token.c_str(), 33);
  portEXIT_CRITICAL(&mux);
  return true;
}
void cupService() {
  if (!samples) return;
  portENTER_CRITICAL(&mux); bool lost = overflow; overflow = false; portEXIT_CRITICAL(&mux);
  if (lost) Serial.println(F("{\"event\":\"cup_fault\",\"reason\":\"queue_overflow\"}"));
  Sample sample;
  while (xQueueReceive(samples, &sample, 0) == pdTRUE) {
    Serial.printf("{\"event\":\"cup_sensor\",\"boot_id\":\"%s\",\"sequence\":%lu,\"at_ms\":%lu,"
                  "\"blocked\":%s,\"healthy\":%s,\"round_id\":\"%s\"}\n", boot_id,
                  (unsigned long)sample.sequence, (unsigned long)sample.at,
                  sample.blocked ? "true" : "false", lost ? "false" : "true", sample.round);
  }
}
