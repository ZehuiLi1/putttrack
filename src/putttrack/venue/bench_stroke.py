"""Provisional causal bench detector, NOT a trained/calibrated stroke model.

Follows recognizer_v1's stationary -> impact -> sustained motion context.
Thresholds are explicit trial values; handling may still trigger false strokes.
"""
import math


class LegacyStrokeDetector:
    VERSION = 'bench-stroke-v0-unvalidated'

    def __init__(self):
        self.last = None
        self.quiet_since = None
        self.armed = False
        self.pending = None
        self.moving_since = None
        self.last_stroke = -10_000_000
        self.phase = '等待静止 0.6 秒'

    def reset(self):
        self.__init__()

    def feed(self, sample):
        t = sample.source_monotonic_us
        if self.last and (sample.sequence != self.last[0] + 1 or not 0 < t-self.last[1] <= 100_000):
            self.reset()
        self.last = (sample.sequence, t)
        if not sample.bmi270_valid or sample.sensor_error_bits:
            self.reset()
            self.phase = 'IMU 数据无效'
            return False
        a = math.sqrt(sum((x/1e6)**2 for x in sample.bmi270_accel_micro_ms2))
        g = math.sqrt(sum((x/1e6)**2 for x in sample.bmi270_gyro_micro_rads))
        if not math.isfinite(a+g):
            self.reset()
            return False
        quiet = abs(a-9.80665) < 1.5 and g < .5
        if quiet:
            if self.quiet_since is None:
                self.quiet_since = t
            if t-self.quiet_since >= 600_000 and t-self.last_stroke >= 1_500_000:
                self.armed = True
                self.phase = '已静止，等待击打'
        else:
            self.quiet_since = None
        if self.pending is not None:
            if a < 3 or t-self.pending > 700_000:
                self.pending = self.moving_since = None
                self.phase = '未确认击打，等待重新静止'
            elif g > 2:
                if self.moving_since is None:
                    self.moving_since = t
                if t-self.moving_since >= 160_000:
                    self.last_stroke = t
                    self.pending = self.moving_since = None
                    self.phase = '已记杆，等待球重新静止'
                    return True
            else:
                self.moving_since = None
        elif self.armed and not quiet:
            # Only abrupt onset immediately after rest may open a candidate.
            self.armed = False
            if a > 14:
                self.pending = t
                self.phase = '冲击候选，检查后续运动'
            else:
                self.phase = '普通移动，等待重新静止'
        return False


class XiaoStrokeDetector:
    """Experimental XIAO profile; thresholds require further handling trials."""
    VERSION = 'bench-stroke-xiao-v1-unvalidated'

    def __init__(self):
        self.last = None
        self.quiet_since = None
        self.armed = False
        self.wobble_since = None
        self.pending = None
        self.low_since = None
        self.gap_since = None
        self.support_us = 0
        self.last_stroke = None
        self.phase = '等待静止 0.6 秒'

    def reset(self):
        self.__init__()

    def reject(self, reason):
        self.pending = None
        self.armed = False
        self.quiet_since = self.wobble_since = None
        self.phase = reason

    def feed(self, sample):
        t = sample.source_monotonic_us
        if self.last and (sample.sequence != self.last[0]+1 or not 0 < t-self.last[1] <= 100_000):
            self.reset()
            self.phase = '数据中断，重新等待静止'
        dt = t-self.last[1] if self.last else 0
        self.last = (sample.sequence, t)
        if not sample.bmi270_valid or sample.sensor_error_bits:
            self.reset()
            self.phase = 'IMU 数据无效，重新等待静止'
            return False
        a = math.hypot(*(v/1e6 for v in sample.bmi270_accel_micro_ms2))
        g = math.hypot(*(v/1e6 for v in sample.bmi270_gyro_micro_rads))
        if not math.isfinite(a+g):
            self.reset()
            return False
        if self.pending is not None:
            if a < 3:
                if self.low_since is None:
                    self.low_since = t
            else:
                self.low_since = None
            if self.low_since is not None and t-self.low_since >= 80_000:
                self.reject('持续低加速度，候选取消')
            elif t-self.pending > 700_000:
                self.reject('后续运动不足，候选取消')
            elif a >= 3 and g > 2:
                if self.gap_since is not None and t-self.gap_since > 80_000:
                    self.support_us = 0
                self.gap_since = None
                self.support_us += dt
                if self.support_us >= 160_000:
                    self.last_stroke = t
                    self.reject('已记杆，等待球停稳')
                    return True
            else:
                if self.gap_since is None:
                    self.gap_since = t
                if t-self.gap_since > 80_000:
                    self.support_us = 0
            return False
        quiet = abs(a-9.80665) < 1.5 and g < .5
        if quiet:
            self.wobble_since = None
            if self.quiet_since is None:
                self.quiet_since = t
            # Initial acquisition stays conservative. Repeat strokes require
            # fresh rest AND the existing 1.5 s refractory period.
            rest_us = 600_000 if self.last_stroke is None else 160_000
            if t-self.quiet_since >= rest_us and (self.last_stroke is None or t-self.last_stroke >= 1_500_000):
                self.armed = True
                self.phase = '已停稳，等待击打'
            return False
        self.quiet_since = None
        if not self.armed:
            return False
        if a > 14:
            self.pending = t
            self.armed = False
            self.low_since = self.gap_since = None
            self.support_us = 0
            self.phase = '冲击候选，检查后续运动'
        elif abs(a-9.80665) < 3 and g < 1:
            if self.wobble_since is None:
                self.wobble_since = t
            if t-self.wobble_since > 300_000:
                self.reject('晃动持续过久，重新等待静止')
            else:
                self.phase = '轻微晃动，保留击打准备'
        else:
            self.reject('普通移动，重新等待静止')
        return False


class BenchStrokeDetector:
    """Select independent profiles by the actual motion packet layout."""
    VERSION = 'bench-stroke-layout-v1-unvalidated'

    def __init__(self, sensor_layout=None):
        self.layout = sensor_layout
        self.detector = XiaoStrokeDetector() if sensor_layout == 'lsm6ds3tr-c-single' else LegacyStrokeDetector()

        self.VERSION = self.detector.VERSION

    def __getattr__(self, name):
        return getattr(self.detector, name)

    def reset(self):
        self.detector.reset()

    def feed(self, sample):
        layout = getattr(sample, 'sensor_layout', None)
        if layout != self.layout:
            self.__init__(layout)
        return self.detector.feed(sample)
