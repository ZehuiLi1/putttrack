"""Explicit single-ball, optical-only bench adapter for the gameplay engine.

The cup cannot identify a ball. This mode uses the one ball selected at the tee;
production physical evidence policy is intentionally not changed.
"""
from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import threading
import time
import uuid

from .bench_stroke import BenchStrokeDetector

from putttrack.gameplay import GameplayEngine, GameplayEvent, EventType, HoleDefinition, Player, SessionState


class SingleHoleTest:
    def __init__(self, log_path: Path, history_paths=()):
        self.lock = threading.RLock()
        self.log_path = log_path
        self.detector = BenchStrokeDetector()
        self.imu = {"samples": 0, "last_at": None, "phase": "等待本局 IMU"}
        self.command = lambda command: None
        self.engine = None
        self.round_id = None
        self.mode = 'simulation'
        self.cancelled = False
        self.actions = set()
        self.cup = {'ready': False, 'blocked': None, 'boot_id': None, 'sequence': -1}
        self.cup_clear_after_stroke = False
        self.history = deque(maxlen=20)
        self.events = deque(maxlen=10)
        restored = {}
        for path in history_paths:
            with path.open() as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        result = event.get('result', {})
                        if event.get('kind') == 'round_completed' and all(k in result for k in ('round_id','player','device_id','strokes','cup_source','completed_at')):
                            restored[result['round_id']] = result
                    except (ValueError, TypeError, AttributeError):
                        continue  # Ignore a crash-truncated log tail.
        self.history.extend(sorted(restored.values(),key=lambda r:r['completed_at'],reverse=True)[:20])

    def _log(self, kind, **details):
        event = {'time': time.time(), 'kind': kind, 'round_id': self.round_id,
                 'test_mode': 'single_ball_optical_only', **details}
        if kind != 'imu_sample':
            self.events.appendleft(event)
        with self.log_path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')

    def snapshot(self):
        with self.lock:
            view = self.engine.presentation() if self.engine else None
            state = 'idle' if view is None else view['player_hole_state']['player']['status']
            if self.cancelled:
                state = 'cancelled'
            return {'round_id': self.round_id, 'stage': state, 'mode': self.mode,
                    'imu': {**self.imu, 'model': self.detector.VERSION, 'age_s': time.monotonic()-self.imu['last_at'] if self.imu['last_at'] else None}, 'game': view, 'cup': dict(self.cup), 'history': list(self.history),
                    'events': list(self.events), 'test_mode': 'single_ball_optical_only'}

    def active_identity(self):
        with self.lock:
            return self.engine.state.players['player'].ball_id if self.snapshot()['stage'] in ('armed','playing') else None

    def _event(self, kind, action_id, source):
        event = GameplayEvent(event_id=action_id, event_type=kind,
            timestamp_ms=time.monotonic_ns()//1_000_000, hole_id='H01',
            ball_id=self.engine.state.players['player'].ball_id, source=source,
            metadata={'test_mode': 'single_ball_optical_only'})
        self.engine.process(event)

    def start(self, player_name, recognition, mode, action_id):
        with self.lock:
            if action_id in self.actions:
                return
            if self.snapshot()['stage'] not in ('idle', 'complete', 'cancelled'):
                raise ValueError('当前一局尚未结束，请先完成或取消')
            if mode not in ('simulation','optical'):
                raise ValueError('请选择模拟入洞或真实光电')
            if not isinstance(player_name,str) or not 1 <= len(player_name.strip()) <= 30:
                raise ValueError('玩家名称需为 1–30 个字符')
            if recognition.get('stage') != 'complete' or not recognition.get('device_id'):
                raise ValueError('先把球放到发球垫，等待 NFC + BLE 识别完成')
            self.round_id = uuid.uuid4().hex
            player = Player('player', player_name.strip(), recognition['device_id'])
            hole = HoleDefinition('H01',1,'单洞测试',{1:0},instructions='IMU 实验计杆，单光电入洞')
            self.engine = GameplayEngine(SessionState(self.round_id,{'player':player},[hole]))
            self.mode, self.cancelled = mode, False
            self.detector = BenchStrokeDetector(recognition.get('sensor_layout'))
            self.imu = {'samples': 0, 'last_at': None, 'phase': '等待本局 IMU'}
            self.cup_clear_after_stroke = False
            self.actions.add(action_id)
            self._event(EventType.TEE_PRESENTED,action_id,'bench_nfc_ble')
            self._log('round_started', player=player.display_name, device_id=player.ball_id, cup_mode=mode,
                      firmware=recognition.get('firmware'), sensor_layout=recognition.get('sensor_layout'), model=self.detector.VERSION)

    def action(self, name, round_id, action_id):
        with self.lock:
            if not self.engine or round_id != self.round_id:
                raise ValueError('页面局号已过期，请刷新')
            if action_id in self.actions:
                return
            stage = self.snapshot()['stage']
            if name == 'stroke':
                if stage not in ('armed','playing'):
                    raise ValueError('只有准备完成或进行中的一局可以记杆')
                self._stroke(action_id, 'operator_button')
                self.detector.reset()
            elif name == 'simulate-cup':
                if self.mode != 'simulation':
                    raise ValueError('真实光电模式不能模拟入洞')
                self._complete(action_id,'simulation')
            elif name == 'cancel':
                if stage not in ('armed','playing'):
                    raise ValueError('没有进行中的一局')
                self.cancelled = True
                self._log('round_cancelled')
            else:
                raise ValueError('未知操作')
            self.actions.add(action_id)

    def _stroke(self, event_id, source):
        first = self.snapshot()['stage'] == 'armed'
        self._event(EventType.STROKE_CONFIRMED,event_id,source)
        if first and self.mode == 'optical':
            self.cup_clear_after_stroke = False
            self.command(f'cup arm {self.round_id}')
        self._log('stroke_recorded', source=source, model=self.detector.VERSION,
                  strokes=self.snapshot()['game']['player_hole_state']['player']['strokes'])

    def observe_motion(self, identity, boot, sample):
        with self.lock:
            if self.snapshot()['stage'] not in ('armed','playing') or identity != self.engine.state.players['player'].ball_id:
                return
            if self.imu.get('boot_id') != boot:
                self.detector.reset()
            self.imu.update(boot_id=boot, sensor_layout=sample.sensor_layout, samples=self.imu['samples']+1, last_at=time.monotonic())
            previous_phase = self.detector.phase
            fired = self.detector.feed(sample)
            if self.detector.phase != previous_phase:
                self._log('imu_phase', phase=self.detector.phase, sequence=sample.sequence,
                          source_monotonic_us=sample.source_monotonic_us, model=self.detector.VERSION)
            self.imu['phase'] = self.detector.phase
            self._log('imu_sample', device_id=identity, boot_id=boot, sample=sample.to_dict())
            if fired:
                self._stroke(f'imu:{boot}:{sample.sequence}', 'imu_experimental')

    def motion_disconnected(self):
        with self.lock:
            self.detector.reset()
            self.imu['phase'] = 'BLE 断开，等待重连和重新静止'

    def cancel_active(self, reason):
        with self.lock:
            if self.snapshot()['stage'] in ('armed','playing'):
                self.cancelled = True
                self._log('round_cancelled', reason=reason)

    def _complete(self, event_id, source):
        if self.snapshot()['stage'] != 'playing':
            raise ValueError('入洞前需至少记录一杆')
        self._event(EventType.CUP_CONFIRMED,event_id,source)
        player=self.engine.state.players['player']
        result={'round_id':self.round_id,'player':player.display_name,'device_id':player.ball_id,
                'strokes':self.engine.state.stats['player'].total_strokes,'cup_source':source,'completed_at':time.time()}
        self.history.appendleft(result)
        self._log('round_completed',result=result)

    def observe_cup(self, event):
        """Accept ordered node events; callers must supply the currently armed round ID."""
        with self.lock:
            if event.get('event') in ('boot','disconnected','cup_fault'):
                self.cup['ready'] = False
                self.cup_clear_after_stroke = False
                if (self.mode == 'optical' or event['event'] in ('boot','disconnected')) and self.snapshot()['stage'] in ('armed','playing'):
                    self.cancelled = True
                    self._log('round_cancelled', reason=event['event'])
                return
            if event.get('event') != 'cup_sensor':
                return
            seq,boot,blocked=event.get('sequence'),event.get('boot_id'),event.get('blocked')
            if type(seq) is not int or seq < 0 or not isinstance(boot,str) or not boot or type(blocked) is not bool:
                return
            if boot == self.cup['boot_id'] and seq <= self.cup['sequence']:
                return
            changed_boot=boot != self.cup['boot_id']
            old=self.cup['blocked']
            self.cup={'ready':event.get('healthy') is True,'blocked':blocked,'boot_id':boot,'sequence':seq}
            if changed_boot or not self.cup['ready']:
                self.cup_clear_after_stroke=False
            if event.get('round_id') != self.round_id or self.mode != 'optical' or self.snapshot()['stage']!='playing':
                return
            if self.cup['ready'] and not blocked:
                self.cup_clear_after_stroke=True
            elif self.cup['ready'] and blocked and old is False and self.cup_clear_after_stroke and not changed_boot:
                self.cup_clear_after_stroke=False
                self._complete(f'cup:{boot}:{seq}','optical_single_sensor')
