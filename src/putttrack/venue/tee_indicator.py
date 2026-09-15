"""Application feedback shared by the page and a future tee light driver."""
import time

class TeeIndicator:
    def __init__(self):
        self.pending_since = None

    def snapshot(self, *, ready, recognition, last_read, hole):
        stage = recognition.get('stage')
        connected = stage == 'complete' and recognition.get('security_level', 0) >= 2
        if not ready:
            self.pending_since = None
            mode, color, effect, title, hint = 'offline', 'red', 'steady', '发球垫未就绪', '请检查发球垫连接'
        elif hole.get('stage') == 'complete':
            self.pending_since = None
            mode, color, effect, title, hint = 'finished', 'green', 'steady', '本局完成', '查看杆数，准备下一局'
        elif connected:
            self.pending_since = None
            if hole.get('stage') in ('armed', 'playing'):
                mode, color, effect, title, hint = 'playing', 'green', 'steady', '本局已连接', '静止后推杆，页面会记录本局数据'
            else:
                mode, color, effect, title, hint = 'ready', 'green', 'steady', '小球识别完成', '可以点击“准备新一局”'
        else:
            manual = recognition.get('manual_placement', {}).get('current') or {}
            detected = bool(last_read.get('uid')) and last_read.get('age_s', 999) < 3
            pending = detected or stage not in (None, 'waiting') or manual.get('outcome') == 'pending'
            if pending:
                if self.pending_since is None:
                    self.pending_since = time.monotonic()
                if time.monotonic() - self.pending_since >= 10 or stage == 'error':
                    mode, color, effect, title, hint = 'retry', 'yellow', 'pulse', '暂未识别完成', '请轻轻转动小球；若仍未完成，查看下方连接提示'
                else:
                    mode, color, effect, title, hint = 'identifying', 'yellow', 'breathe', '正在识别小球', '请稍等，绿灯常亮后即可开始'
            else:
                self.pending_since = None
                mode, color, effect, title, hint = 'standby', 'yellow', 'steady', '等待放球', '把小球放到发球垫；长时间未变绿可轻轻转动小球'
        return dict(mode=mode, color=color, effect=effect, title=title, hint=hint,
                    hardware_connected=False, source='application_nfc_ble')
