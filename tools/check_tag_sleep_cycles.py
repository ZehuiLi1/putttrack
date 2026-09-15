#!/usr/bin/env python3
"""Battery bench: cycle PN532 RF, verify System OFF wake and encrypted IMU.

Stop the dashboard first (exclusive serial/BLE ownership). Leave the Tag on the
pad. RF pause expires in firmware after 60 seconds; finally also resumes it.
This verifies functionality, not sleep current or physical placement coverage.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
import time

import serial
from bleak import BleakClient, BleakScanner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from putttrack.service.nfc import parse_nfc_reader_event, ServiceTouchError
from putttrack.tag.ble_smp import BleSmp
from putttrack.tag.recognition import check_ble_identity
from putttrack.tag.telemetry import STATUS_CHARACTERISTIC_UUID, parse_status
from check_tag_motion_link import check as check_motion


class Reader:
    def __init__(self, port, log):
        self.port, self.log = port, log
        self.events = []
        self.task = None

    async def pump(self):
        while True:
            raw = await asyncio.to_thread(self.port.readline)
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            now = time.monotonic()
            self.events.append((now, event))
            self.log.write(json.dumps({'time': time.time(), 'event': event}) + '\n')
            self.log.flush()

    async def wait(self, predicate, since, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.task.done():
                self.task.result()
                raise RuntimeError('Reader stopped')
            for at, event in self.events:
                if at >= since and predicate(event):
                    return at, event
            await asyncio.sleep(.05)
        raise TimeoutError('Reader event timed out')

    async def rf(self, pause):
        start = time.monotonic()
        self.port.write(('nfc rf ' + ('pause' if pause else 'resume') + '\n').encode())
        _, event = await self.wait(lambda e: e.get('event') == 'rf_control', start, 5)
        if event.get('ok') is not True or event.get('paused') is not pause:
            raise RuntimeError(f'RF command failed: {event}')
        return start


@asynccontextmanager
async def connection(args):
    async with BleakClient(args.address, timeout=8) as client:
        gatt = parse_status(await client.read_gatt_char(STATUS_CHARACTERISTIC_UUID))
        if gatt.device_id != args.device_id:
            raise RuntimeError('GATT identity mismatch')
        async with BleSmp(client, timeout=5) as smp:
            status = await smp.request(64, 0)
            check_ble_identity(args.device_id, status)
            yield smp, status


def wake_errors(before, after):
    errors = []
    if not before.get('boot_id') or not after.get('boot_id') or before['boot_id'] == after['boot_id']:
        errors.append('Boot ID did not change')
    if after.get('nfc_system_off_wake') is not True:
        errors.append('Missing NFC System OFF wake flag')
    if after.get('fw') != before.get('fw'):
        errors.append('Firmware changed')
    if after.get('ble_bond_persistence') is not True:
        errors.append('Bond persistence disabled')
    if after.get('ble_pairings') != 0 or after.get('ble_pairing_failures') != 0:
        errors.append('New pairing or pairing failure after wake')
    if after.get('sensor_health') != 'healthy':
        errors.append('Sensors unhealthy')
    return errors


async def run(args):
    result = {'device_id': args.device_id, 'requested_cycles': args.cycles,
              'passed': False, 'cycles': [], 'method': 'PN532 RF switching; battery-powered Tag'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    port = serial.Serial(port=None, baudrate=115200, timeout=.2, exclusive=True)
    port.dtr = port.rts = False
    port.port = args.serial_port
    reader = None
    with args.output.with_suffix('.reader.jsonl').open('w') as log:
        try:
            port.open()
            port.rts = True
            await asyncio.sleep(.2)
            port.reset_input_buffer()
            port.rts = False
            reader = Reader(port, log)
            reader.task = asyncio.create_task(reader.pump())
            await reader.wait(lambda e: e.get('event') == 'scan_ready', time.monotonic(), 15)
            def target(event):
                try:
                    return parse_nfc_reader_event(event).device_id == args.device_id
                except ServiceTouchError:
                    return False
            # Clear a selected/partial session left by the previous owner.
            # Require a fresh, real NDEF after the field is restored.
            await reader.rf(True)
            await asyncio.sleep(3)
            resumed = await reader.rf(False)
            result['stage'] = 'initial_ndef'
            save()
            await reader.wait(target, resumed, 60)
            for index in range(1, args.cycles + 1):
                cycle = {'index': index, 'passed': False}
                result['cycles'].append(cycle)
                result['stage'] = 'sleep_preflight'
                await reader.rf(True)
                await asyncio.sleep(1)
                async with connection(args) as (smp, before):
                    cycle['status_before'] = before
                    if (before.get('system_off_supported') is not True or
                        before.get('nfc_enabled') is not True or before.get('nfc_setup_error') != 0 or
                        before.get('nfc_field_present') is not False or before.get('system_off_pending') or
                        before.get('ble_bond_persistence') is not True):
                        raise RuntimeError('System OFF preflight failed')
                    images = await smp.request(1, 0)
                    if not any(i.get('active') and i.get('confirmed') for i in images.get('images', [])):
                        raise RuntimeError('Active firmware is not confirmed')
                    ack = await smp.request(64, 23, write=True)
                    cycle['ack'] = ack
                    if ack.get('accepted') is not True:
                        raise RuntimeError('System OFF rejected')
                await asyncio.sleep(max(3, ack.get('delay_ms', 2000) / 1000 + 1))
                result['stage'] = 'sleep_scan'
                devices = await BleakScanner.discover(timeout=5)
                cycle['sleep_scan_seconds'] = 5
                cycle['advertised_while_asleep'] = any(d.address == args.address for d in devices)
                if cycle['advertised_while_asleep']:
                    raise RuntimeError('Tag still advertising after sleep')
                resumed = await reader.rf(False)
                result['stage'] = 'wake_ndef'
                save()
                ndef_at, event = await reader.wait(target, resumed, 60)
                cycle['ndef'] = event
                cycle['rf_resume_to_ndef_ms'] = round((ndef_at - resumed) * 1000)
                async with connection(args) as (_, after):
                    cycle['status_after'] = after
                    cycle['ndef_to_ble_ms'] = round((time.monotonic() - ndef_at) * 1000)
                    cycle['rf_resume_to_ble_ms'] = round((time.monotonic() - resumed) * 1000)
                    errors = wake_errors(before, after)
                    if errors:
                        raise RuntimeError('; '.join(errors))
                motion_path = args.output.with_name(args.output.stem + f'.cycle{index}.motion.json')
                cycle['motion'] = await check_motion(args.device_id, args.address, 5, motion_path)
                if not cycle['motion']['passed']:
                    raise RuntimeError('Post-wake IMU check failed')
                cycle['passed'] = True
                save()
                print(json.dumps({'cycle': index, 'passed': True, 'ndef_to_ble_ms': cycle['ndef_to_ble_ms'],
                                  'samples': cycle['motion']['samples']}) , flush=True)
            result['passed'] = True
            result['stage'] = 'complete'
        except Exception as exc:
            result['error'] = str(exc) or type(exc).__name__
        finally:
            if reader:
                try:
                    await reader.rf(False)
                    result['rf_restored'] = True
                except Exception as exc:
                    result['rf_restored'] = False
                    result['restore_error'] = str(exc)
                    result['passed'] = False
                reader.task.cancel()
                await asyncio.gather(reader.task, return_exceptions=True)
            if port.is_open:
                port.close()
            save()
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device-id', required=True)
    p.add_argument('--address', required=True)
    p.add_argument('--serial-port', required=True)
    p.add_argument('--cycles', type=int, default=3)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not 1 <= args.cycles <= 10:
        p.error('cycles must be 1–10')
    result = asyncio.run(run(args))
    print(json.dumps({'passed': result['passed'], 'error': result.get('error'),
                      'report': str(args.output)}, ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)
