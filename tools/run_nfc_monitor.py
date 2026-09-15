#!/usr/bin/env python3
"""Local, read-only PN532 desktop monitor. Run with the hardware extra installed."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import threading
import time
import sys
import tkinter as tk
from tkinter import ttk

import serial
from serial.tools import list_ports

@dataclass
class ReadState:
    status: str = '正在连接读卡器'
    color: str = '#b7791f'
    connected: bool = False
    ready: bool = False
    present: bool = False
    consecutive: int = 0
    best: int = 0
    total: int = 0
    misses: int = 0
    target: int = 50
    last_seen: float = 0
    device: str = '—'
    firmware: str = '—'
    identity: str = '等待读取'
    passed: bool = False

    def apply(self, event: dict, now: float) -> None:
        kind = event.get('event')
        if kind == 'connected':
            self.connected = True
            self.status = '已连接 · 等待读卡器'
        elif kind == 'boot':
            self.ready = self.present = self.passed = False
            self.consecutive = 0
            self.status = '读卡器启动中'
            self.color = '#b7791f'
        elif kind == 'scan_ready':
            self.ready = True
            self.status = '等待小球'
            self.color = '#617067'
        elif kind == 'nfc_tag':
            self.ready = self.present = True
            self.total += 1
            self.last_seen = now
            self.consecutive = int(event.get('consecutive_reads', 0))
            self.best = max(self.best, self.consecutive)
            self.target = max(1, int(event.get('stable_target', 50)))
            self.passed = self.consecutive >= self.target
            self.device = event.get('device_id') or event.get('ball_id') or '—'
            self.firmware = event.get('firmware_version', '—')
            self.identity = ('球身份解析正常' if event.get('service_uri_ok') else
                             'NDEF 已读取' if event.get('ndef_ok') else
                             '仅识别到标签 · ' + event.get('ndef_error', '身份未解析'))
            self.status = '连续读取达标' if self.passed else '正在读取'
            self.color = '#126a45'
        elif kind in ('scan_miss', 'tag_removed'):
            self.consecutive = 0
            self.passed = False
            if kind == 'scan_miss':
                self.misses += 1
                self.status = '暂时漏读'
                self.color = '#b7791f'
            else:
                self.present = False
                self.status = '小球已移开 · 等待读取'
                self.color = '#617067'
        elif kind in ('disconnected', 'fatal'):
            self.present = self.ready = self.passed = False
            self.consecutive = 0
            if kind == 'disconnected':
                self.connected = False
            self.status = '连接中断' if kind == 'disconnected' else '读卡器故障'
            self.color = '#b53737'

    def display_status(self, now: float) -> tuple[str, str]:
        if self.connected and self.present and now - self.last_seen > 3:
            return '读取超时 · 等待新数据', '#b7791f'
        return self.status, self.color


class Monitor:
    def __init__(self, root: tk.Tk, port: str | None):
        self.root, self.port = root, port
        self.state = ReadState()
        self.events: queue.Queue = queue.Queue()
        self.stop = threading.Event()
        self.thread = None
        self.log_path = Path(__file__).resolve().parents[1] / 'runs' / ('nfc_monitor_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.jsonl')
        self.log_path.parent.mkdir(exist_ok=True)
        root.title('PuttTrack · NFC 读取状态')
        root.geometry('880x720')
        root.minsize(760, 650)
        root.configure(bg='#f3f6f1')
        self.values = {}
        panel = tk.Frame(root, bg='#f3f6f1', padx=32, pady=24)
        panel.pack(fill='both', expand=True)
        def label(text='', size=13, color='#617067', parent=panel):
            widget = tk.Label(parent, text=text, font=('Helvetica', size), bg=parent['bg'], fg=color, anchor='w')
            widget.pack(fill='x', pady=4)
            return widget
        label('PUTTTRACK  /  NFC 检查台', 14, '#126a45')
        self.headline = label('正在连接读卡器', 36, '#126a45')
        self.connection = label('连接中…')
        label('将球放在天线上方，保持位置不动；观察达标后再拿开、换角度。')
        card = tk.Frame(panel, bg='white', padx=20, pady=16)
        card.pack(fill='x', pady=16)
        row = tk.Frame(card, bg='white')
        row.pack(fill='x')
        for key, title in [('consecutive', '当前连续读取'), ('best', '本次最长连续'), ('total', '本次成功读取'), ('misses', '漏读事件')]:
            cell = tk.Frame(row, bg='white')
            cell.pack(side='left', expand=True, fill='x')
            label(title, 12, parent=cell)
            self.values[key] = label('0', 32, '#11251d', cell)
        self.progress = ttk.Progressbar(card, maximum=50)
        self.progress.pack(fill='x', pady=(16, 4))
        self.gate = label('连续读取目标：50 次', parent=card)
        self.identity = label('身份：等待读取', 16, '#11251d')
        self.detail = label('设备 —    固件 —')
        self.age = label('最近读取：—')
        label('最近事件', 14, '#11251d')
        self.history = tk.Text(panel, height=7, bg='#e8eee8', fg='#254332', relief='flat', font=('Menlo', 11), padx=12, pady=10, state='disabled')
        self.history.pack(fill='both', expand=True, pady=6)
        footer = tk.Frame(panel, bg=panel['bg'])
        footer.pack(fill='x', pady=(8, 0))
        self.retry = ttk.Button(footer, text='重新连接', command=self.connect)
        self.retry.pack(side='right')
        ttk.Button(footer, text='打开日志目录', command=self.open_logs).pack(side='right', padx=8)
        label('日志自动保存 · 漏读事件数不等于全部失败轮询次数', 11, parent=footer)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.connect()
        root.after(100, self.tick)

    def open_logs(self):
        import subprocess
        subprocess.Popen(['open', str(self.log_path.parent)])

    def connect(self):
        if self.thread and self.thread.is_alive():
            return
        self.state = ReadState()
        self.retry.configure(state='disabled')
        self.thread = threading.Thread(target=self.read_serial, daemon=True)
        self.thread.start()

    def read_serial(self):
        try:
            ports = [p.device for p in list_ports.comports() if p.vid == 0x303A]
            port = self.port
            if not port:
                if len(ports) != 1:
                    raise RuntimeError('未找到唯一的 ESP32，请检查 USB 连接；多块设备需用 --port 指定')
                port = ports[0]
            with serial.Serial(port=None, baudrate=115200, timeout=0.3, exclusive=True) as connection:
                connection.dtr = False
                connection.rts = False
                connection.port = port
                connection.open()
                self.events.put({'event': 'connected', 'port': port})
                with self.log_path.open('a', encoding='utf-8') as log:
                    while not self.stop.is_set():
                        raw = connection.readline()
                        if not raw:
                            continue
                        line = raw.decode(errors='replace').strip()
                        log.write(json.dumps({'time': datetime.now().astimezone().isoformat(), 'raw': line}, ensure_ascii=False) + '\n')
                        log.flush()
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(event, dict):
                            self.events.put(event)
        except Exception as error:
            self.events.put({'event': 'disconnected', 'message': str(error)})

    def tick(self):
        for _ in range(500):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            self.state.apply(event, time.monotonic())
            kind = event.get('event')
            if kind == 'connected':
                self.connection.configure(text='USB 已连接  ·  ' + event['port'])
            if kind in ('connected', 'pn532_ready', 'scan_ready', 'scan_miss', 'tag_removed', 'stability_pass', 'fatal', 'disconnected'):
                names = {'connected':'USB 已连接', 'pn532_ready':'PN532 初始化正常', 'scan_ready':'开始扫描 NFC-A', 'scan_miss':'出现漏读，连续计数归零', 'tag_removed':'标签已离开', 'stability_pass':'通过连续 50 次读取', 'fatal':'读卡器故障', 'disconnected':'连接中断'}
                self.history.configure(state='normal')
                self.history.insert('end', datetime.now().strftime('%H:%M:%S') + '  ' + names[kind] + '  ' + event.get('message', '') + '\n')
                if int(self.history.index('end-1c').split('.')[0]) > 100:
                    self.history.delete('1.0', '2.0')
                self.history.see('end')
                self.history.configure(state='disabled')
        s = self.state
        title, color = s.display_status(time.monotonic())
        self.headline.configure(text=title, fg=color)
        if not s.connected:
            self.connection.configure(text='USB 未连接 · 检查连接后点击“重新连接”')
        for key, widget in self.values.items():
            widget.configure(text=str(getattr(s, key)))
        self.progress.configure(maximum=s.target, value=min(s.consecutive, s.target))
        self.gate.configure(text=f'连续读取目标：{s.target} 次  ·  ' + ('当前连续计数已达标' if s.passed and title != '读取超时 · 等待新数据' else '等待稳定读取'))
        self.identity.configure(text='身份：' + s.identity)
        self.detail.configure(text=f'最近设备 {s.device}    固件 {s.firmware}')
        self.age.configure(text='最近读取：' + (f'{time.monotonic() - s.last_seen:.1f} 秒前' if s.last_seen else '—'))
        if self.thread and not self.thread.is_alive():
            self.retry.configure(state='normal')
        self.root.after(100, self.tick)

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', help='Optional explicit ESP32 serial port')
    args = parser.parse_args()
    # Relocated Nordic Python distributions retain Homebrew's original Tcl path.
    # Prefer the matching Tcl/Tk shipped alongside that Python installation.
    for parent in Path(sys.base_prefix).resolve().parents:
        library = parent / 'opt' / 'tcl-tk' / 'lib'
        if (library / 'tcl8.6' / 'init.tcl').is_file():
            os.environ.setdefault('TCL_LIBRARY', str(library / 'tcl8.6'))
            os.environ.setdefault('TK_LIBRARY', str(library / 'tk8.6'))
            break
    root = tk.Tk()
    Monitor(root, args.port)
    root.mainloop()


if __name__ == '__main__':
    main()
