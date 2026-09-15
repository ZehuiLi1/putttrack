"""USB-powered bench identification: NFC identity matched to read-only BLE status.

This does not grant player/hole activation authority or migrate BLE ownership.
"""
from __future__ import annotations

import asyncio
from collections import Counter, deque
from contextlib import suppress
import json
from pathlib import Path
import threading
import time

from putttrack.service.nfc import parse_nfc_reader_event, ServiceTouchError

MANUAL_PLACEMENT_TIMEOUT_S = 10
RECOGNITION_ABSENCE_GRACE_S = 3
REMOVAL_CONFIRM_S = 3


class Recognition:
    def __init__(self, log_path: Path | None = None):
        self.lock = threading.Lock()
        self.log_path = log_path
        self.generation = 0
        self.trials = deque(maxlen=50)
        self.trial = None
        self.totals = Counter()
        self.latency_sum = 0
        self.latency_max = 0
        self.pinned_identity = None
        self.game_target = None
        self.power_restore = {}
        self.motion_callback = None
        self.motion_disconnect = None
        self.identity = None
        self.last_verified = None
        self.identity_cache = log_path.with_name('nfc_last_verified.json') if log_path else None
        if self.identity_cache and self.identity_cache.exists():
            try:
                cached = json.loads(self.identity_cache.read_text())
                identity = cached.get('device_id')
                if isinstance(identity, str) and len(identity) == 16 and all(c in '0123456789abcdef' for c in identity) and isinstance(cached.get('address'), str):
                    self.last_verified = {'device_id':identity,'address':cached['address']}
            except (OSError, ValueError, AttributeError):
                pass

        self.manual_trials = []
        self.manual_trial = None
        self.manual_actions = set()

        self.off_request = False
        self.off_result = {}
        self.last_seen = 0.0
        self.started = 0.0
        self.attempts = 0
        self.result = {"stage": "waiting", "authority": False}

    def _manual_finish(self, outcome, reason=''):
        t = self.manual_trial
        if not t or t['outcome'] != 'pending':
            return
        t.update(outcome=outcome, reason=reason,
                 elapsed_ms=round((time.monotonic()-t['start_monotonic'])*1000))
        self._log('manual_placement_result', **t)

    def _manual_tick(self):
        t = self.manual_trial
        if t and t['outcome'] == 'pending' and time.monotonic()-t['start_monotonic'] >= MANUAL_PLACEMENT_TIMEOUT_S:
            self._manual_finish('timeout', '10 秒内未完成 NFC + BLE 身份核对')

    def manual_action(self, action, action_id):
        with self.lock:
            self._manual_tick()
            if action_id in self.manual_actions:
                return
            if action == 'start':
                if self.manual_trial and self.manual_trial['outcome'] == 'pending':
                    raise ValueError('本次仍在计时')
                if self.pinned_identity or (self.game_target and self.game_target()):
                    raise ValueError('请先结束当前一局')
                if self.off_request or self.off_result.get('stage') == 'command_accepted':
                    raise ValueError('请先完成休眠唤醒测试')
                if time.monotonic()-self.last_seen < REMOVAL_CONFIRM_S:
                    raise ValueError('请先拿离球，等待约 3 秒后再开始')
                self._clear('manual_test_start')
                t = {'id':len(self.manual_trials)+1, 'outcome':'pending',
                     'started_at':time.time(), 'start_monotonic':time.monotonic(),
                     'expected_device_id':(self.last_verified or {}).get('device_id'),
                     'device_id':None, 'nfc_ms':None, 'elapsed_ms':None}
                self.manual_trial = t
                self.manual_trials.append(t)
                self._log('manual_placement_started', **t)
            elif action == 'cancel':
                self._manual_finish('cancelled', '用户取消')
            else:
                raise ValueError('未知测试操作')
            self.manual_actions.add(action_id)

    def _manual_snapshot(self):
        self._manual_tick()
        resolved = [t for t in self.manual_trials if t['outcome'] in ('success','timeout','failure')]
        successes = [t for t in resolved if t['outcome'] == 'success']
        return {'current':dict(self.manual_trial) if self.manual_trial else None,
                'elapsed_ms':round((time.monotonic()-self.manual_trial['start_monotonic'])*1000) if self.manual_trial and self.manual_trial['outcome']=='pending' else None,
                'trials':[dict(t) for t in reversed(self.manual_trials)],
                'resolved':len(resolved), 'success':len(successes),
                'cancelled':sum(t['outcome']=='cancelled' for t in self.manual_trials),
                'within_2s':sum(t['elapsed_ms']<=2000 for t in successes),
                'within_5s':sum(t['elapsed_ms']<=5000 for t in successes),
                'success_rate':100*len(successes)/len(resolved) if resolved else None}

    def _log(self, event, **details):
        if self.log_path:
            with self.log_path.open('a') as log:
                log.write(json.dumps({"time": time.time(), "event": event, **details}) + '\n')

    def _finish_trial(self, outcome, reason=''):
        if not self.trial or self.trial['outcome'] != 'pending':
            return
        self.trial.update(outcome=outcome, reason=reason)
        self.totals[outcome] += 1
        if outcome == 'success':
            elapsed = round((time.monotonic() - self.started) * 1000)
            self.trial['recognition_ms'] = elapsed
            self.latency_sum += elapsed
            self.latency_max = max(self.latency_max, elapsed)
        self._log('placement_result', **self.trial)

    def _clear(self, reason='removed'):
        if self.trial:
            self._finish_trial('interrupted', reason)
            self.trial.update(closed=True, end_reason=reason)
            self._log('placement_closed', **self.trial)
            self.trial = None
        self.generation += 1
        self.identity = None
        self.attempts = 0
        self.result = {"stage": "waiting", "authority": False}

    def observe(self, event: dict):
        with self.lock:
            self._manual_tick()
            if event.get('event') in ('boot', 'disconnected', 'fatal'):
                self._manual_finish('failure', '读卡器中断：'+event['event'])
                self._clear(event['event'])
                return
            # A reader removal event can be a brief RF dropout. Confirm absence
            # with the same 3-second valid-identity grace used by the worker.
            if event.get('event') != 'nfc_tag':
                return
            try:
                touch = parse_nfc_reader_event(event)
            except (ServiceTouchError, ValueError, TypeError):
                return
            now = time.monotonic()
            t = self.manual_trial
            if t and t['outcome'] == 'pending':
                if t['expected_device_id'] and touch.device_id != t['expected_device_id']:
                    self._manual_finish('failure', '识别到另一颗球')
                elif t['nfc_ms'] is None:
                    t.update(device_id=touch.device_id, nfc_ms=round((now-t['start_monotonic'])*1000))
            if self.off_result.get('stage') == 'command_accepted' and self.off_result.get('device_id') == touch.device_id and 'first_nfc_at' not in self.off_result:
                self.off_result.update(first_nfc_at=time.time(), first_nfc_monotonic=now)
                self._log('first_nfc_after_sleep', device_id=touch.device_id, first_nfc_at=self.off_result['first_nfc_at'])
            if self.pinned_identity and touch.device_id != self.pinned_identity:
                return
            if self.identity != touch.device_id or (not self.pinned_identity and now - self.last_seen > RECOGNITION_ABSENCE_GRACE_S):
                self._clear('changed_ball' if self.identity and self.identity != touch.device_id else 'absence')
                self.identity = touch.device_id
                self.started = now
                self.totals['placements'] += 1
                self.trial = {'id': self.totals['placements'], 'device_id': touch.device_id,
                              'started_at': time.time(), 'outcome': 'pending', 'closed': False,
                              'attempts': 0, 'ble_interruptions': 0}
                self.trials.appendleft(self.trial)
                self._log('placement_started', **self.trial)
                self.result = {"stage": "nfc_identified", "authority": False}
            self.last_seen = now

    def snapshot(self):
        with self.lock:
            if self.identity and not self.pinned_identity and time.monotonic() - self.last_seen > RECOGNITION_ABSENCE_GRACE_S:
                self._clear('absence')
            resolved = self.totals['success'] + self.totals['failure'] + self.totals['interrupted']
            summary = {**self.totals, 'resolved': resolved,
                       'success_rate': 100*self.totals['success']/resolved if resolved else None,
                       'mean_ms': self.latency_sum/self.totals['success'] if self.totals['success'] else None,
                       'max_ms': self.latency_max if self.totals['success'] else None}
            return {**self.result, "manual_placement": self._manual_snapshot(), "device_id": self.identity,
                    "generation": self.generation, "attempts": self.attempts,
                    "summary": summary, "trials": [dict(t) for t in self.trials],
                    "last_verified": self.last_verified, "system_off": dict(self.off_result)}

    def update(self, generation: int, stage: str, **details):
        with self.lock:
            if generation != self.generation or not self.identity or (not self.pinned_identity and time.monotonic() - self.last_seen > RECOGNITION_ABSENCE_GRACE_S):
                return False
            previous_stage = self.result['stage']
            self.result = {**self.result, **details, "stage": stage, "authority": False}
            if stage == 'complete':
                self._manual_tick()
                t = self.manual_trial
                if t and t['nfc_ms'] is not None and t['device_id'] == self.identity:
                    self._manual_finish('success')
                self._finish_trial('success')
                self.last_verified = {"device_id": self.identity, "address": details.get('address')}
                if self.off_result.get('stage') == 'command_accepted' and self.off_result.get('device_id') == self.identity:
                    before = self.off_result.get('boot_id_before')
                    if before and details.get('boot_id') and before != details['boot_id'] and details.get('nfc_system_off_wake') is True:
                        self.off_result.update(stage='wake_verified', boot_id_after=details['boot_id'], status_after=details.get('wake_status'), recognition_ms=round((time.monotonic()-self.started)*1000), wake_to_ble_ms=round((time.monotonic()-self.off_result['first_nfc_monotonic'])*1000) if 'first_nfc_monotonic' in self.off_result else None, message='已验证 NFC 从 System OFF 唤醒，且 BLE 身份核对完成。')
                        self._log('system_off_result', **self.off_result)
                    elif before and details.get('boot_id') and details['boot_id'] != before:
                        debug = bool(details.get('reset_cause', 0) & 32)
                        self.off_result.update(stage='wake_unverified', reset_cause=details.get('reset_cause'),
                            boot_id_after=details['boot_id'], message='小球已重启，但原因是调试接口复位/唤醒，未通过 NFC 唤醒验证。' if debug else '小球已重启，但固件未报告 NFC 唤醒；本次未通过验证。')
                        self._log('system_off_result', **self.off_result)
                    elif details.get('boot_id') == before:
                        self.off_result['message'] = 'BLE 已恢复，但启动标识未变化，尚未证明进入过 System OFF；可能放回过早。'

            if stage == 'scanning':
                self.attempts += 1
                if self.trial:
                    self.trial['attempts'] = self.attempts
            if stage == 'error':
                if self.trial and previous_stage == 'complete':
                    self.trial['ble_interruptions'] += 1
                    self._log('placement_ble_interruption', **self.trial)
                if self.attempts >= 3:
                    self._finish_trial('failure', details.get('error', 'BLE failed'))
            if self.log_path:
                with self.log_path.open('a') as log:
                    log.write(json.dumps({"time": time.time(), "device_id": self.identity,
                                          "generation": generation, **self.result}) + '\n')
            return True


    def request_retry(self):
        with self.lock:
            if not self.identity or self.result.get('stage') != 'error':
                raise ValueError('仅在已识别 NFC 且 BLE 失败时重试')
            self.attempts = 0
            self.result.update(stage='nfc_identified', error='')
            self._log('ble_retry_requested', device_id=self.identity)

    def request_system_off(self):
        with self.lock:
            if self.pinned_identity:
                raise ValueError('先结束或取消本局，再执行休眠')
            if not self.last_verified:
                raise ValueError('请先完成一次 NFC + BLE 身份核对')
            if self.off_request or self.off_result.get('stage') == 'sending':
                raise ValueError('System OFF 命令正在处理')
            if self.identity and time.monotonic() - self.last_seen <= REMOVAL_CONFIRM_S:
                raise ValueError('请先把小球拿离发球垫，等待 3 秒后再点击')
            self.off_request = True
            self.off_result = {'stage': 'sending', 'device_id': self.last_verified['device_id']}
            self._log('system_off_requested', **self.off_result)


async def send_system_off(state: Recognition):
    from bleak import BleakClient
    from putttrack.tag.ble_smp import BleSmp, find_tag_device
    with state.lock:
        target = dict(state.last_verified)
        state.off_request = False
    try:
        async with asyncio.timeout(25):
            device = await find_tag_device(target['device_id'], address=target.get('address'), timeout=10)
            if device is None:
                raise RuntimeError('未发现已核对的小球')
            async with BleakClient(device, timeout=10) as client:
                async with BleSmp(client, timeout=5) as smp:
                    status = await smp.request(64, 0)
                    check_ble_identity(target['device_id'], status)
                    if status.get('system_off_supported') is not True or status.get('nfc_enabled') is not True or status.get('nfc_setup_error') != 0:
                        raise RuntimeError('固件未报告可用的 NFC / System OFF 能力')
                    if status.get('nfc_field_present'):
                        raise RuntimeError('小球仍检测到 NFC 场，请拿远后重试')
                    if status.get('system_off_pending'):
                        raise RuntimeError('固件已经在等待进入 System OFF')
                    ack = await smp.request(64, 23, write=True)
                    if ack.get('accepted') is not True:
                        raise RuntimeError('固件拒绝 System OFF 命令')
                    result = {'stage': 'command_accepted', 'device_id': target['device_id'],
                              'boot_id_before': status.get('boot_id'), 'reset_before': status.get('reset'),
                              'ack': ack, 'status_before': status,
                              'message': '命令已接受；等待至少 3 秒后放回发球垫。尚未确认实际休眠。'}
        with state.lock:
            state.off_result = result
            state._log('system_off_ack', **result)
    except Exception as exc:
        with state.lock:
            state.off_result = {'stage': 'error', 'message': str(exc) or type(exc).__name__}
            state._log('system_off_error', **state.off_result)


def check_ble_identity(expected: str, status: dict):
    if status.get('device_id', '').lower() != expected:
        raise RuntimeError('BLE 身份与 NFC 不一致')
    if type(status.get('ble_security_level')) is not int or status['ble_security_level'] < 2:
        raise RuntimeError('BLE 加密连接尚未建立')


def describe_ble_error(error: str, identity: str) -> str:
    if 'Peer removed pairing information' in error:
        return f'macOS 配对记录已失效：请忽略对应小球 PuttTrack-{identity[:8]} 的蓝牙记录，然后重试 BLE。'
    if 'Insufficient Encryption' in error:
        return 'BLE 加密协商未完成（ATT 0x0F）；NFC 已识别，但尚不能读取 BLE 数据。'
    return error


async def identify(state: Recognition, target: dict):
    from bleak import BleakClient
    from putttrack.tag.ble_smp import BleSmp, find_tag_device
    from putttrack.tag.telemetry import STATUS_CHARACTERISTIC_UUID, MOTION_CHARACTERISTIC_UUID, parse_status, parse_motion, TelemetryProtocolError

    generation, identity = target['generation'], target['device_id']
    state.update(generation, 'scanning', error='', elapsed_ms=None)
    started = time.monotonic()
    closing = False
    def disconnected(_):
        if not closing:
            state.update(generation, 'error', error='BLE 连接已断开')
    try:
        async with asyncio.timeout(25):
            known = state.last_verified or {}
            address = known.get('address') if known.get('device_id') == identity else None
            device = await find_tag_device(identity, address=address, timeout=10)
            if device is None:
                raise RuntimeError('未发现对应小球的 BLE 广播')
            state.update(generation, 'connecting')
            client = BleakClient(device, timeout=10, disconnected_callback=disconnected)
            await client.connect()
            try:
                state.update(generation, 'verifying')
                status = parse_status(await client.read_gatt_char(STATUS_CHARACTERISTIC_UUID))
                if status.device_id != identity:
                    raise RuntimeError('BLE GATT 身份与 NFC 不一致')
                async with BleSmp(client, timeout=5) as smp:
                    verified = await smp.request(64, 0)
                check_ble_identity(identity, verified)
            except BaseException:
                closing = True
                await client.disconnect()
                raise
        elapsed_ms = round((time.monotonic() - started)*1000)
        # Notifications share the verified connection; the active game pins it.
        def on_motion(_, data):
            try:
                sample = parse_motion(data)
            except TelemetryProtocolError:
                if state.motion_disconnect:
                    state.motion_disconnect()
                return
            if sample.protocol_version != status.protocol_version:
                if state.motion_disconnect:
                    state.motion_disconnect()
                return
            if state.motion_callback and generation == state.generation:
                state.motion_callback(identity, status.boot_id, sample)
        # Keep one connection for this placement; NFC reads do not reconnect it.
        try:
            if state.motion_callback:
                await client.start_notify(MOTION_CHARACTERISTIC_UUID, on_motion)
            async with BleSmp(client, timeout=5) as smp:
                original_policy = state.power_restore.get(identity, verified.get('power_policy', 'auto'))
                changed_power = identity in state.power_restore
                current_policy = verified.get('power_policy', 'auto')
                next_status = 0
                try:
                    while True:
                        want_stream = state.pinned_identity == identity
                        desired_policy = 'research' if want_stream else original_policy
                        if current_policy != desired_policy or (changed_power and not want_stream):
                            command = 21 if want_stream else {'auto':20,'research':21,'idle':22}.get(original_policy,20)
                            if want_stream:
                                state.power_restore[identity] = original_policy
                            ack = await smp.request(64, command, write=True)
                            if ack.get('accepted') is not True:
                                raise RuntimeError('IMU 采样电源策略未被接受')
                            changed_power = want_stream
                            current_policy = desired_policy
                            if not want_stream:
                                state.power_restore.pop(identity, None)
                            next_status = 0
                        if time.monotonic() >= next_status:
                            verified = await smp.request(64, 0)
                            check_ble_identity(identity, verified)
                            if verified.get('boot_id') != status.boot_id:
                                raise RuntimeError('小球重启，需要重新建立 IMU 数据基线')
                            state.update(generation, 'complete', firmware=verified.get('fw'), address=device.address,
                                         security_level=verified['ble_security_level'],
                                         elapsed_ms=elapsed_ms, boot_id=verified.get('boot_id'),
                                         power_policy=verified.get('power_policy'), stream_hz=verified.get('stream_hz'),
                                         protocol_version=status.protocol_version, sensor_layout=status.sensor_layout,
                                         nfc_system_off_wake=verified.get('nfc_system_off_wake'),
                                         wake_status={k:verified.get(k) for k in ('device_id','fw','boot_id','reset','nfc_system_off_wake','ble_security_level','ble_bond_persistence','battery_supported','battery_presence_known','battery_sample_valid','battery_voltage_mv','battery_soc_percent','battery_soc_estimated','sensor_health','adxl_ready','bmi_ready','runtime_state','power_policy','stream_hz')},
                                         reset_cause=verified.get('reset'),
                                         system_off_pending=verified.get('system_off_pending'),
                                         system_off_entry_error=verified.get('system_off_entry_error'))
                            next_status = time.monotonic()+2
                        await asyncio.sleep(.2)
                        if not client.is_connected:
                            raise RuntimeError('BLE 连接已断开')
                finally:
                    if identity in state.power_restore and client.is_connected:
                        await smp.request(64, {'auto':20,'research':21,'idle':22}.get(original_policy,20), write=True)
                        restored = await smp.request(64, 0)
                        if restored.get('power_policy') != original_policy:
                            raise RuntimeError('未确认恢复原电源策略')
                        state.power_restore.pop(identity, None)
        finally:
            closing = True
            if state.motion_disconnect:
                state.motion_disconnect()
            await client.disconnect()
    except Exception as exc:
        error = str(exc) or type(exc).__name__
        state.update(generation, 'error', error=describe_ble_error(error, identity))


async def run_recognition(state: Recognition, identify_fn=identify, *, retry_delay=5.0, poll_interval=.2, stop_event=None):
    task = None
    token = None
    retry_at = 0.0
    try:
        while stop_event is None or not stop_event.is_set():
            if state.game_target:
                state.pinned_identity = state.game_target()
            if state.off_request:
                if task:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                    task = None
                await send_system_off(state)
                retry_at = 0
            target = state.snapshot()
            current = target['generation'] if target['device_id'] else None
            if task and current != token:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                task = None
                retry_at = 0
            if task and task.done():
                await task
                task = None
                retry_at = time.monotonic() + retry_delay
            if current is not None and task is None and (target['attempts'] < 3 or state.pinned_identity == target['device_id']) and time.monotonic() >= retry_at:
                token = current
                task = asyncio.create_task(identify_fn(state, target))
            await asyncio.sleep(poll_interval)
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
