"""Patch Adafruit PN532 1.3.4 to retain the active target number.

readPassiveTargetID() parses the target number but does not copy it into the
private field later used by inDataExchange().  Without this fix, Type 4 APDUs
are sent to target zero.  Keeping the patch in the build makes clean installs
of the pinned dependency behave consistently.
"""

from pathlib import Path

Import("env")  # type: ignore[name-defined]  # Provided by PlatformIO/SCons.

source = (
    Path(env.subst("$PROJECT_LIBDEPS_DIR"))
    / env.subst("$PIOENV")
    / "Adafruit PN532"
    / "Adafruit_PN532.cpp"
)
header = source.with_name("Adafruit_PN532.h")
needle = """  if (pn532_packetbuffer[7] != 1)\n    return 0;\n\n  uint16_t sens_res = pn532_packetbuffer[9];"""
replacement = """  if (pn532_packetbuffer[7] != 1)\n    return 0;\n\n  _inListedTag = pn532_packetbuffer[8];\n  uint16_t sens_res = pn532_packetbuffer[9];"""

text = source.read_text(encoding="utf-8")
if replacement not in text:
    if needle not in text:
        raise RuntimeError(
            "Adafruit PN532 source changed; target-number patch cannot be applied"
        )
    source.write_text(text.replace(needle, replacement, 1), encoding="utf-8")

header_needle = """  bool setPassiveActivationRetries(uint8_t maxRetries);"""
header_replacement = """  bool setRFField(bool enabled);\n  bool setPassiveActivationRetries(uint8_t maxRetries);"""
header_text = header.read_text(encoding="utf-8")
if header_replacement not in header_text:
    if header_needle not in header_text:
        raise RuntimeError("Adafruit PN532 header changed; RF-field patch cannot be applied")
    header.write_text(
        header_text.replace(header_needle, header_replacement, 1),
        encoding="utf-8",
    )

rf_marker = """/**************************************************************************/\n/*!\n    Sets the MxRtyPassiveActivation byte of the RFConfiguration register"""
rf_method = """/**************************************************************************/
/*!
    Enables or disables the PN532 RF field.
*/
/**************************************************************************/
bool Adafruit_PN532::setRFField(bool enabled) {
  pn532_packetbuffer[0] = PN532_COMMAND_RFCONFIGURATION;
  pn532_packetbuffer[1] = 0x01; // Config item 1: RF field
  pn532_packetbuffer[2] = enabled ? 0x01 : 0x00;

  if (!sendCommandCheckAck(pn532_packetbuffer, 3))
    return false;

  readdata(pn532_packetbuffer, 9);
  return pn532_packetbuffer[6] == (PN532_COMMAND_RFCONFIGURATION + 1U);
}

"""
text = source.read_text(encoding="utf-8")
if rf_method not in text:
    if rf_marker not in text:
        raise RuntimeError("Adafruit PN532 source changed; RF-field patch cannot be applied")
    source.write_text(text.replace(rf_marker, rf_method + rf_marker, 1), encoding="utf-8")

# Poll readiness more frequently without changing the protocol timeout budget.
# Use elapsed time so SPI transfer time counts too, and uint16_t cannot wrap.
wait_original = """bool Adafruit_PN532::waitready(uint16_t timeout) {
  uint16_t timer = 0;
  while (!isready()) {
    if (timeout != 0) {
      timer += 10;
      if (timer > timeout) {
#ifdef PN532DEBUG
        PN532DEBUGPRINT.println("TIMEOUT!");
#endif
        return false;
      }
    }
    delay(10);
  }
  return true;
}"""
wait_replacement = """bool Adafruit_PN532::waitready(uint16_t timeout) {
#ifndef PT_PN532_READY_POLL_MS
#define PT_PN532_READY_POLL_MS 10
#endif
  static_assert(PT_PN532_READY_POLL_MS >= 1, "Readiness polling must yield");
  const uint32_t started = millis();
  while (!isready()) {
    if (timeout != 0 && (millis() - started) >= timeout) {
      return false;
    }
    delay(PT_PN532_READY_POLL_MS);
  }
  return true;
}"""
text = source.read_text(encoding="utf-8")
if wait_replacement not in text:
    if wait_original not in text:
        raise RuntimeError("Adafruit PN532 source changed; ready-poll patch cannot be applied")
    source.write_text(text.replace(wait_original, wait_replacement, 1), encoding="utf-8")

# ReadRegister (UM0701-02 section 7.2.4), with full normal-frame validation.
register_decl = '  bool readRegisters(const uint16_t *addresses, uint8_t *values, uint8_t count);'
header_text = header.read_text(encoding='utf-8')
if register_decl not in header_text:
    header.write_text(header_text.replace('  bool setRFField(bool enabled);', register_decl + '\n  bool setRFField(bool enabled);', 1), encoding='utf-8')
register_method = '''bool Adafruit_PN532::readRegisters(const uint16_t *addresses, uint8_t *values, uint8_t count) {
  if (!addresses || !values || count == 0 || count > 16)
    return false;
  uint8_t command[33] = {0x06};
  for (uint8_t i = 0; i < count; ++i) {
    command[1 + 2 * i] = addresses[i] >> 8;
    command[2 + 2 * i] = addresses[i] & 0xff;
  }
  if (!sendCommandCheckAck(command, 1 + 2 * count, 250))
    return false;
  uint8_t frame[25] = {};
  readdata(frame, count + 9);
  if (frame[0] != 0 || frame[1] != 0 || frame[2] != 0xff ||
      frame[3] != count + 2 || uint8_t(frame[3] + frame[4]) != 0 ||
      frame[5] != 0xd5 || frame[6] != 0x07 || frame[count + 8] != 0)
    return false;
  uint8_t checksum = 0;
  for (uint8_t i = 5; i <= count + 7; ++i)
    checksum += frame[i];
  if (checksum != 0)
    return false;
  memcpy(values, frame + 7, count);
  return true;
}

'''
text = source.read_text(encoding='utf-8')
if register_method not in text:
    if rf_marker not in text:
        raise RuntimeError('Adafruit PN532 source changed; register-read patch cannot be applied')
    source.write_text(text.replace(rf_marker, register_method + rf_marker, 1), encoding='utf-8')

# Preserve SAK from activation so the application can choose Type 2 versus
# ISO-DEP before sending any protocol-specific command (NXP UM0701-02).
text = source.read_text(encoding='utf-8')
sak_needle = '  sens_res |= pn532_packetbuffer[10];'
sak_replacement = sak_needle + '\n  _lastTargetSAK = pn532_packetbuffer[11];'
if sak_replacement not in text:
    if sak_needle not in text:
        raise RuntimeError('PN532 SAK source patch cannot be applied')
    source.write_text(text.replace(sak_needle, sak_replacement, 1), encoding='utf-8')
text = header.read_text(encoding='utf-8')
getter = '  uint8_t lastTargetSAK() const { return _lastTargetSAK; }'
if getter not in text:
    if 'public:' not in text or 'private:' not in text:
        raise RuntimeError('PN532 SAK header patch cannot be applied')
    text = text.replace('public:', 'public:\n' + getter, 1)
    text = text.replace('private:', 'private:\n  uint8_t _lastTargetSAK = 0;', 1)
    header.write_text(text, encoding='utf-8')

# Keep the controller error distinct from host framing/timeout failures.
text = header.read_text(encoding='utf-8')
getter = '  uint16_t lastExchangeDiagnostic() const { return _lastExchangeDiagnostic; }'
if getter not in text:
    text = text.replace('public:', 'public:\n' + getter, 1)
    text = text.replace('private:', 'private:\n  uint16_t _lastExchangeDiagnostic = 0;', 1)
    header.write_text(text, encoding='utf-8')
text = source.read_text(encoding='utf-8')
start = text.index('bool Adafruit_PN532::inDataExchange(')
end = text.index('\n/**************************************************************************/', start)
method = text[start:end]
if '_lastExchangeDiagnostic' not in method:
    method = method.replace('  if (sendLength >', '  _lastExchangeDiagnostic = 0x100; // invalid outgoing length\n  if (sendLength >', 1)
    method = method.replace('  if (!sendCommandCheckAck', '  _lastExchangeDiagnostic = 0x101; // command/ACK/response-ready failure\n  if (!sendCommandCheckAck', 1)
    method = method.replace('  if (!waitready(1000))', '  _lastExchangeDiagnostic = 0x102; // response timeout\n  if (!waitready(1000))', 1)
    method = method.replace('  readdata(pn532_packetbuffer', '  _lastExchangeDiagnostic = 0x103; // unexpected host response frame\n  readdata(pn532_packetbuffer', 1)
    method = method.replace('      if ((pn532_packetbuffer[7] & 0x3f) != 0)', '      _lastExchangeDiagnostic = pn532_packetbuffer[7] & 0x3f;\n      if ((pn532_packetbuffer[7] & 0x3f) != 0)', 1)
    source.write_text(text[:start] + method + text[end:], encoding='utf-8')
