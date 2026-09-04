#!/usr/bin/env python3
"""Run a loopback-only web UI for operator-led Ball IMU capture."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import subprocess
import sys
import threading
from typing import Any, Callable
import webbrowser


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.capture_field_session import (  # noqa: E402
    ANALYZE_TOOL,
    PYTHON,
    PROFILES,
    build_capture_command,
    build_power_command,
    output_path,
    validate_args,
)


DEFAULT_DEVICE_ID = "f383571202836e6f"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


PAGE_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>PuttTrack IMU 采集台</title>
  <style>
    :root{color-scheme:light;--ink:#11251d;--muted:#617067;--line:#d9e3dc;--paper:#f4f7f3;--card:#fff;--green:#126a45;--green2:#0c5235;--lime:#dff35c;--warn:#9a5b06;--bad:#a52c2c;--shadow:0 18px 50px rgba(20,55,39,.12)}
    *{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"PingFang SC",sans-serif;background:radial-gradient(circle at 90% 5%,#dfeecb 0,transparent 35%),var(--paper);color:var(--ink);min-height:100vh}
    main{width:min(980px,calc(100% - 32px));margin:0 auto;padding:38px 0 64px}.top{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:28px}.eyebrow{font-size:12px;font-weight:800;letter-spacing:.16em;color:var(--green);text-transform:uppercase}h1{font-size:clamp(32px,6vw,58px);line-height:1;margin:8px 0 12px;letter-spacing:-.045em}.subtitle{color:var(--muted);max-width:620px;margin:0;line-height:1.6}.status-pill{white-space:nowrap;border:1px solid var(--line);background:#ffffffc7;padding:10px 14px;border-radius:999px;font-size:13px;font-weight:750}.status-pill.busy{color:var(--warn);border-color:#e6c483}.status-pill.good{color:var(--green);border-color:#9ccbb4}.status-pill.bad{color:var(--bad);border-color:#e4a1a1}
    .panel{background:var(--card);border:1px solid #e3eae5;border-radius:24px;box-shadow:var(--shadow);padding:24px;margin-bottom:18px}.panel h2{font-size:18px;margin:0 0 16px}.profiles{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.profile{position:relative}.profile input{position:absolute;opacity:0}.profile label{display:block;height:100%;padding:16px;border:1px solid var(--line);border-radius:15px;cursor:pointer;transition:.15s;background:#fbfdfb}.profile label:hover{border-color:#8ebb9f;transform:translateY(-1px)}.profile input:checked+label{border:2px solid var(--green);padding:15px;background:#eff8f2;box-shadow:0 0 0 3px #dff0e5}.profile strong{display:block;font-size:15px;margin-bottom:5px}.profile span{display:block;color:var(--muted);font-size:12px;line-height:1.45}
    .form-row{display:grid;grid-template-columns:1fr 130px;gap:12px;margin-top:18px}label.field{font-size:12px;font-weight:750;color:var(--muted)}input[type=text],select{display:block;width:100%;margin-top:7px;padding:12px 13px;border:1px solid var(--line);border-radius:11px;background:#fff;color:var(--ink);font:inherit}button{border:0;border-radius:14px;padding:15px 18px;font:inherit;font-weight:800;cursor:pointer;transition:.15s}button:hover:not(:disabled){transform:translateY(-1px)}button:disabled{cursor:not-allowed;opacity:.42}.primary{background:var(--green);color:white;width:100%;font-size:16px}.primary:hover:not(:disabled){background:var(--green2)}.go{background:var(--lime);color:#173016;width:100%;font-size:22px;padding:21px}.secondary{background:#edf2ee;color:var(--ink);width:100%;margin-top:9px}
    .capture{display:grid;grid-template-columns:1.35fr .65fr;gap:18px}.stage{min-height:245px;display:flex;flex-direction:column;justify-content:space-between}.stage-label{font-size:12px;color:var(--muted);font-weight:800;letter-spacing:.12em;text-transform:uppercase}.message{font-size:clamp(25px,4vw,42px);line-height:1.12;font-weight:850;letter-spacing:-.035em;margin:12px 0}.instruction{color:var(--muted);line-height:1.55}.progress{height:9px;border-radius:99px;background:#edf1ee;overflow:hidden;margin-top:20px}.progress div{height:100%;background:var(--green);width:0;transition:width .3s}.stats{display:grid;gap:10px}.stat{background:#f3f7f4;border-radius:15px;padding:15px}.stat small{display:block;color:var(--muted);margin-bottom:4px}.stat strong{font-size:20px}.result{margin-top:15px;padding:12px 14px;background:#f7faf8;border-radius:12px;color:var(--muted);font-size:13px;line-height:1.5;min-height:44px}
    .telemetry-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.telemetry-grid .panel{margin-bottom:0}.panel-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:16px}.panel-head h2{margin:0}.mini-pill{padding:6px 10px;border-radius:999px;background:#edf4ef;color:var(--green);font-size:11px;font-weight:800}.device-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:18px}.metric{border:1px solid #e5ebe7;background:#fbfdfb;border-radius:13px;padding:12px}.metric small{display:block;color:var(--muted);font-size:11px;margin-bottom:5px}.metric strong{font-size:17px;overflow-wrap:anywhere}.metric.wide{grid-column:1/-1}.chart-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:10px 2px 4px}.chart-title strong{font-size:13px}.legend{display:flex;gap:12px;color:var(--muted);font-size:11px}.legend span::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;background:var(--dot)}.chart-wrap{height:205px;width:100%}.chart-wrap canvas{display:block;width:100%;height:100%}.quality{border-radius:12px;background:#f3f7f4;padding:11px 13px;color:var(--muted);font-size:12px;line-height:1.5;margin-top:8px}.quality.warn{background:#fff7e8;color:var(--warn)}.quality.bad{background:#fff0f0;color:var(--bad)}.footer-note{text-align:center;color:var(--muted);font-size:12px;margin-top:22px}
    @media(max-width:720px){main{padding-top:24px}.top{display:block}.status-pill{display:inline-block;margin-top:16px}.profiles{grid-template-columns:1fr 1fr}.capture,.telemetry-grid{grid-template-columns:1fr}.form-row{grid-template-columns:1fr}.panel{padding:18px;border-radius:19px}}
    @media(max-width:440px){.profiles{grid-template-columns:1fr}}
  </style>
</head>
<body>
<main>
  <header class="top"><div><div class="eyebrow">PuttTrack Research</div><h1>IMU 数据采集台</h1><p class="subtitle">选择一种动作，准备好球后按一次开始。倒计时、采集、保存、检查和低功耗恢复全部自动完成。</p></div><div id="status-pill" class="status-pill">正在连接…</div></header>
  <section class="panel" id="setup-panel"><h2>1. 选择要采集的数据</h2><div id="profiles" class="profiles"></div><div class="form-row"><label class="field">批次名称<input id="session-id" type="text" maxlength="64"></label><label class="field">采集次数<select id="count"><option>1</option><option>5</option><option selected>10</option><option>20</option></select></label></div><label class="field" style="display:block;margin-top:12px">备注（可选）<input id="notes" type="text" maxlength="300" placeholder="例如：客厅短绒地毯、操作者 A"></label><button id="prepare" class="primary" style="margin-top:18px">准备这个批次</button></section>
  <section class="panel capture"><div class="stage"><div><div class="stage-label">当前步骤</div><div id="message" class="message">先选择动作并准备批次</div><div id="instruction" class="instruction">Ball 保持静止；程序准备完成后再开始动作。</div><div class="progress"><div id="progress"></div></div></div><div><button id="start" class="go" disabled>开始本组采集</button><button id="finish" class="secondary" disabled>结束批次并恢复低功耗</button></div></div><div class="stats"><div class="stat"><small>动作</small><strong id="active-profile">—</strong></div><div class="stat"><small>进度</small><strong id="counter">0 / 0</strong></div><div class="stat"><small>最近结果</small><strong id="last-state">—</strong></div><div id="result" class="result">还没有采集结果。</div></div></section>
  <section class="telemetry-grid">
    <article class="panel"><div class="panel-head"><h2>Ball 状态</h2><span id="device-link" class="mini-pill">未读取</span></div><div class="device-grid"><div class="metric"><small>电池电压</small><strong id="battery-voltage">—</strong></div><div class="metric"><small>剩余电量</small><strong id="battery-soc">—</strong></div><div class="metric"><small>功耗 / 运行状态</small><strong id="power-state">—</strong></div><div class="metric"><small>IMU 采样</small><strong id="stream-state">—</strong></div><div class="metric wide"><small>传感器 / 固件</small><strong id="sensor-state">—</strong></div></div><div class="chart-title"><strong>本批次电压趋势</strong><span id="battery-points" class="legend">0 个读数</span></div><div class="chart-wrap"><canvas id="battery-chart" role="img" aria-label="本批次电池电压趋势图">浏览器不支持图表。</canvas></div></article>
    <article class="panel"><div class="panel-head"><h2>每组 IMU 趋势</h2><span id="run-count" class="mini-pill">0 组</span></div><div class="chart-title"><strong>角速度（rad/s）</strong><div class="legend"><span style="--dot:#126a45">峰值</span><span style="--dot:#d68b1d">RMS</span></div></div><div class="chart-wrap"><canvas id="imu-chart" role="img" aria-label="每组 IMU 角速度峰值和均方根趋势图">浏览器不支持图表。</canvas></div><div id="quality" class="quality">完成第一组采集后，这里会显示连续性、丢包和量程饱和检查。</div></article>
  </section>
  <div class="footer-note">页面只在本机开放。采集期间不要关闭此窗口或拔下 XIAO nRF52840。</div>
</main>
<script>
const TOKEN=__TOKEN__;
let config=null,lastPhase=null,audioContext=null;
const $=s=>document.querySelector(s);
async function api(path,options={}){options.headers={...(options.headers||{}),'X-PuttTrack-Token':TOKEN};if(options.body)options.headers['Content-Type']='application/json';const r=await fetch(path,options);const j=await r.json();if(!r.ok)throw new Error(j.error||'请求失败');return j}
function profileTitle(id){return config?.profiles[id]?.title||id||'—'}
function renderProfiles(){const root=$('#profiles');root.textContent='';Object.entries(config.profiles).forEach(([id,p],i)=>{const d=document.createElement('div');d.className='profile';const input=document.createElement('input');input.type='radio';input.name='profile';input.id='p-'+id;input.value=id;input.checked=i===0;const label=document.createElement('label');label.htmlFor=input.id;const strong=document.createElement('strong');strong.textContent=p.title;const span=document.createElement('span');span.textContent=p.short;label.append(strong,span);d.append(input,label);root.append(d)})}
function setPill(phase){const p=$('#status-pill');p.className='status-pill';if(['ready','complete','idle'].includes(phase))p.classList.add('good');else if(phase==='error')p.classList.add('bad');else p.classList.add('busy');p.textContent=phase==='idle'?'auto / 未开始':phase==='ready'?'已准备好':phase==='complete'?'批次完成 / auto':phase==='error'?'出现错误':phase==='capturing'?'正在采集':'处理中'}
function beep(){try{audioContext=audioContext||new(window.AudioContext||window.webkitAudioContext)();const o=audioContext.createOscillator(),g=audioContext.createGain();o.frequency.value=880;g.gain.setValueAtTime(.15,audioContext.currentTime);g.gain.exponentialRampToValueAtTime(.001,audioContext.currentTime+.22);o.connect(g).connect(audioContext.destination);o.start();o.stop(audioContext.currentTime+.22)}catch(e){}}
function drawChart(canvas,series,labels,emptyText){const rect=canvas.getBoundingClientRect(),width=Math.max(280,Math.round(rect.width)),height=Math.max(180,Math.round(rect.height)),dpr=Math.min(window.devicePixelRatio||1,2);canvas.width=width*dpr;canvas.height=height*dpr;const c=canvas.getContext('2d');c.scale(dpr,dpr);c.clearRect(0,0,width,height);c.font='11px system-ui';c.fillStyle='#617067';if(!series.length||!series.some(x=>x.values.length)){c.textAlign='center';c.fillText(emptyText,width/2,height/2);return}const all=series.flatMap(x=>x.values).filter(Number.isFinite);if(!all.length)return;let lo=Math.min(...all),hi=Math.max(...all),pad=Math.max((hi-lo)*.18,series[0].minimumPad||.05);lo=Math.max(series[0].floor??-Infinity,lo-pad);hi+=pad;const left=46,right=12,top=14,bottom=28,w=width-left-right,h=height-top-bottom;c.strokeStyle='#e3eae5';c.fillStyle='#617067';c.textAlign='right';for(let i=0;i<4;i++){const y=top+h*i/3,value=hi-(hi-lo)*i/3;c.beginPath();c.moveTo(left,y);c.lineTo(width-right,y);c.stroke();c.fillText(value.toFixed(series[0].digits??2),left-7,y+4)}const n=Math.max(...series.map(x=>x.values.length));const xAt=i=>left+(n<=1?w/2:w*i/(n-1));c.textAlign='center';labels.forEach((label,i)=>{if(labels.length<=8||i===0||i===labels.length-1)c.fillText(label,xAt(i),height-8)});series.forEach(item=>{c.strokeStyle=item.color;c.lineWidth=2.5;c.lineJoin='round';c.beginPath();item.values.forEach((value,i)=>{const x=xAt(i),y=top+(hi-value)/(hi-lo)*h;i?c.lineTo(x,y):c.moveTo(x,y)});c.stroke();item.values.forEach((value,i)=>{c.fillStyle=item.color;c.beginPath();c.arc(xAt(i),top+(hi-value)/(hi-lo)*h,3,0,Math.PI*2);c.fill()})})}
function renderTelemetry(s){const d=s.device_status,b=s.battery_history||[],runs=s.result_history||[];$('#device-link').textContent=d?`已读取 · ${d.device_id.slice(-6)}`:'未读取';$('#battery-voltage').textContent=d?.battery_voltage_mv!=null?`${(d.battery_voltage_mv/1000).toFixed(3)} V`:'—';$('#battery-soc').textContent=d?.battery_soc_percent!=null?`${d.battery_soc_percent}%${d.battery_soc_estimated?'（估算）':''}`:'—';$('#power-state').textContent=d?`${d.mode} / ${d.runtime_state}`:'—';$('#stream-state').textContent=d?(d.stream_rate_hz?`${d.stream_rate_hz} Hz`:(d.bmi270_spi_suspended?'0 Hz · BMI270 休眠':'0 Hz')):'—';const health=d?.sensor_health==='healthy'?'正常':(d?.sensor_health||'—');$('#sensor-state').textContent=d?`${health} · FW ${d.firmware_version}`:'—';$('#battery-points').textContent=`${b.length} 个读数`;$('#run-count').textContent=`${runs.length} 组`;drawChart($('#battery-chart'),b.length?[{values:b.map(x=>x.voltage_mv/1000),color:'#126a45',digits:3,minimumPad:.01,floor:0}]:[],b.map(x=>x.source),'等待设备电压读数');drawChart($('#imu-chart'),runs.length?[{values:runs.map(x=>x.gyro_peak),color:'#126a45',digits:2,minimumPad:.1,floor:0},{values:runs.map(x=>x.gyro_rms),color:'#d68b1d'}]:[],runs.map(x=>String(x.index)),'完成采集后显示角速度趋势');const q=$('#quality');q.className='quality';if(!runs.length){q.textContent='完成第一组采集后，这里会显示连续性、丢包和量程饱和检查。';return}const last=runs[runs.length-1],problems=[];if(last.continuity!=='PASS')problems.push(`连续性 ${last.continuity}`);if(last.sequence_gaps)problems.push(`${last.sequence_gaps} 个序列缺口`);if(last.clip_samples)problems.push(`${last.clip_samples} 个饱和样本`);if(problems.length){q.classList.add(last.continuity==='FAIL'||last.sequence_gaps?'bad':'warn');q.textContent=`第 ${last.index} 组需检查：${problems.join(' · ')}`;}else{q.textContent=`第 ${last.index} 组数据完整：连续性 PASS，无序列缺口，无量程饱和。`}}
function render(s){if(s.phase==='capturing'&&lastPhase!=='capturing')beep();lastPhase=s.phase;setPill(s.phase);$('#message').textContent=s.message;$('#instruction').textContent=s.instruction||' ';$('#active-profile').textContent=profileTitle(s.profile);$('#counter').textContent=`${s.completed} / ${s.count}`;$('#progress').style.width=s.count?`${Math.min(100,s.completed/s.count*100)}%`:'0%';$('#start').disabled=s.phase!=='ready';$('#start').textContent=s.phase==='ready'?`开始第 ${s.completed+1} / ${s.count} 组`:'开始本组采集';$('#finish').disabled=!['ready','error'].includes(s.phase);$('#prepare').disabled=!['idle','complete'].includes(s.phase)&&(s.phase!=='error'||!s.low_power);if(s.last_result){$('#last-state').textContent=s.last_result.state||'已保存';$('#result').textContent=`${s.last_result.samples||0} 样本 · 陀螺峰值 ${Number(s.last_result.gyro_peak||0).toFixed(2)} rad/s · ${s.last_result.file}`}else{$('#last-state').textContent='—';$('#result').textContent='还没有采集结果。'}renderTelemetry(s)}
async function refresh(){try{render(await api('/api/state'))}catch(e){$('#status-pill').className='status-pill bad';$('#status-pill').textContent='服务连接失败'}}
$('#prepare').addEventListener('click',async()=>{const profile=document.querySelector('input[name=profile]:checked')?.value;try{await api('/api/session',{method:'POST',body:JSON.stringify({profile,count:Number($('#count').value),session_id:$('#session-id').value.trim(),notes:$('#notes').value.trim()})});refresh()}catch(e){alert(e.message)}});
$('#start').addEventListener('click',async()=>{try{audioContext=audioContext||new(window.AudioContext||window.webkitAudioContext)();await audioContext.resume();await api('/api/capture/start',{method:'POST',body:'{}'});refresh()}catch(e){alert(e.message)}});
$('#finish').addEventListener('click',async()=>{try{await api('/api/session/finish',{method:'POST',body:'{}'});refresh()}catch(e){alert(e.message)}});
(async()=>{config=await api('/api/config');$('#session-id').value=config.default_session_id;renderProfiles();await refresh();setInterval(refresh,500)})().catch(e=>alert(e.message));
</script>
</body></html>'''


PROFILE_COPY = {
    "pickup_carry": ("拿起、携带、放下", "拿起球，走几步，再放下"),
    "handling": ("触摸与重新摆球", "轻触、旋转或调整位置"),
    "putt_gentle": ("轻推杆", "轻推一次并自然停止"),
    "putt_normal": ("正常推杆", "正常力度推击一次"),
    "putt_firm": ("较重推杆", "较大力度推击一次"),
    "hand_roll": ("手推滚动", "不用球杆，手推一次"),
}


def completed_process(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def normalized_device_status(
    payload: dict[str, Any], expected_device_id: str
) -> dict[str, Any]:
    """Normalize status from a power command or a capture JSONL record."""

    device_id = str(payload.get("device_id", "")).lower()
    if device_id != expected_device_id.lower():
        raise ValueError(
            f"设备 ID 不匹配：期望 {expected_device_id}，实际 {device_id or '缺失'}"
        )
    mode = payload.get("mode", payload.get("power_policy"))
    if not isinstance(mode, str) or not mode:
        raise ValueError("设备状态缺少功耗策略")

    voltage = payload.get("battery_voltage_mv")
    soc = payload.get("battery_soc_percent")
    return {
        "device_id": device_id,
        "firmware_version": str(payload.get("firmware_version", "—")),
        "battery_voltage_mv": (
            int(voltage)
            if payload.get("battery_sample_valid") and isinstance(voltage, (int, float))
            else None
        ),
        "battery_soc_percent": (
            int(soc) if isinstance(soc, (int, float)) else None
        ),
        "battery_soc_estimated": bool(payload.get("battery_soc_estimated", False)),
        "battery_sample_valid": bool(payload.get("battery_sample_valid", False)),
        "sensor_health": str(payload.get("sensor_health", "unknown")),
        "capture_safe": bool(payload.get("capture_safe", False)),
        "mode": mode,
        "runtime_state": str(payload.get("runtime_state", "unknown")),
        "stream_rate_hz": int(payload.get("stream_rate_hz", 0) or 0),
        "bmi270_spi_suspended": bool(payload.get("bmi270_spi_suspended", False)),
        "adxl367_wakeup_mode_enabled": bool(
            payload.get("adxl367_wakeup_mode_enabled", False)
        ),
        "sensor_error_count": int(payload.get("sensor_error_count", 0) or 0),
    }


def power_status_from_result(
    result: subprocess.CompletedProcess[str],
    expected_device_id: str,
    expected_mode: str,
) -> dict[str, Any]:
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"exit {result.returncode}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("功耗命令没有返回有效的 JSON 状态") from exc
    if not isinstance(payload, dict):
        raise ValueError("功耗命令返回的状态不是 JSON 对象")
    status = normalized_device_status(payload, expected_device_id)
    if status["mode"] != expected_mode:
        raise ValueError(
            f"功耗策略未生效：期望 {expected_mode}，实际 {status['mode']}"
        )
    return status


def capture_telemetry(
    capture: Path, expected_device_id: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Read the final device status and continuity result from one capture."""

    if not capture.exists():
        return None, None
    final_status = None
    capture_result = None
    for line_number, line in enumerate(capture.read_text(encoding="utf-8").splitlines(), 1):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"采集文件第 {line_number} 行不是有效 JSON") from exc
        if not isinstance(payload, dict):
            continue
        if payload.get("record_type") == "tag_status_final":
            final_status = normalized_device_status(payload, expected_device_id)
        elif payload.get("record_type") == "tag_capture_result":
            capture_result = payload
    return final_status, capture_result


class FieldCaptureApp:
    def __init__(
        self,
        base_args: argparse.Namespace,
        *,
        command_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = completed_process,
        popen_factory: Callable[..., Any] = subprocess.Popen,
    ) -> None:
        self.base_args = base_args
        self.command_runner = command_runner
        self.popen_factory = popen_factory
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.RLock()
        self.current_process: Any | None = None
        self.session_args: argparse.Namespace | None = None
        self.ready_timer: threading.Timer | None = None
        self.state: dict[str, Any] = {
            "phase": "idle",
            "message": "先选择动作并准备批次",
            "instruction": "Ball 保持静止；程序准备完成后再开始动作。",
            "profile": None,
            "count": 0,
            "completed": 0,
            "last_result": None,
            "device_status": None,
            "battery_history": [],
            "result_history": [],
            "low_power": True,
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return copy.deepcopy(self.state)

    def config(self) -> dict[str, Any]:
        return {
            "default_session_id": datetime.now().strftime("%Y%m%d-%H%M%S"),
            "profiles": {
                key: {
                    "title": PROFILE_COPY[key][0],
                    "short": PROFILE_COPY[key][1],
                    "seconds": profile.episode_seconds,
                    "instruction": profile.instruction,
                }
                for key, profile in PROFILES.items()
            },
        }

    def _set(self, **changes: Any) -> None:
        with self.lock:
            self.state.update(changes)

    def _record_device_status(self, status: dict[str, Any], source: str) -> None:
        with self.lock:
            self.state["device_status"] = status
            voltage = status.get("battery_voltage_mv")
            if isinstance(voltage, int):
                self.state["battery_history"].append(
                    {
                        "source": source,
                        "voltage_mv": voltage,
                        "soc_percent": status.get("battery_soc_percent"),
                    }
                )

    def _set_power_mode(self, args: argparse.Namespace, mode: str, source: str) -> None:
        result = self.command_runner(build_power_command(args, mode))
        status = power_status_from_result(result, args.expected_device_id, mode)
        self._record_device_status(status, source)

    def _session_from_payload(self, payload: dict[str, Any]) -> argparse.Namespace:
        profile = str(payload.get("profile", ""))
        if profile not in PROFILES:
            raise ValueError("请选择有效的动作类型")
        try:
            count = int(payload.get("count", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("采集次数无效") from exc
        if not 1 <= count <= 100:
            raise ValueError("采集次数必须在 1 到 100 之间")
        notes = str(payload.get("notes", "")).strip()
        if len(notes) > 300:
            raise ValueError("备注不能超过 300 个字符")
        args = argparse.Namespace(
            profile=profile,
            count=count,
            start_index=1,
            session_id=str(payload.get("session_id", "")).strip(),
            output_dir=self.base_args.output_dir,
            hci_port=self.base_args.hci_port,
            expected_device_id=self.base_args.expected_device_id,
            device_name=self.base_args.device_name,
            ble_address=self.base_args.ble_address,
            address_type=self.base_args.address_type,
            notes=notes or None,
        )
        validate_args(args)
        collisions = [
            output_path(args, index)
            for index in range(1, count + 1)
            if output_path(args, index).exists()
        ]
        if collisions:
            raise ValueError(f"文件已存在，请更换批次名称：{collisions[0].name}")
        return args

    def prepare(self, payload: dict[str, Any]) -> None:
        with self.lock:
            if self.state["phase"] not in {"idle", "complete", "error"}:
                raise RuntimeError("当前批次尚未结束")
            if self.state["phase"] == "error" and not self.state["low_power"]:
                raise RuntimeError("请先恢复 Ball 低功耗，再开始新批次")
            args = self._session_from_payload(payload)
            args.output_dir.mkdir(parents=True, exist_ok=True)
            self.session_args = args
            self.state.update(
                phase="preparing",
                message="正在检查 Ball 并启动研究模式…",
                instruction="保持 Ball 静止，等待准备完成。",
                profile=args.profile,
                count=args.count,
                completed=0,
                last_result=None,
                device_status=None,
                battery_history=[],
                result_history=[],
                low_power=False,
            )
        threading.Thread(target=self._prepare_worker, daemon=True).start()

    def _prepare_worker(self) -> None:
        assert self.session_args is not None
        try:
            self._set_power_mode(self.session_args, "research", "准备")
        except (RuntimeError, ValueError) as exc:
            self._fail_and_restore("无法连接 Ball 或进入 research 模式", str(exc))
            return
        self._set(
            phase="ready",
            message="Ball 已准备好",
            instruction=PROFILES[self.session_args.profile].instruction,
            low_power=False,
        )
        self._arm_ready_timeout()

    def _arm_ready_timeout(self) -> None:
        with self.lock:
            if self.ready_timer is not None:
                self.ready_timer.cancel()
            self.ready_timer = threading.Timer(
                self.base_args.idle_timeout_seconds, self._ready_timeout
            )
            self.ready_timer.daemon = True
            self.ready_timer.start()

    def _cancel_ready_timeout(self) -> None:
        with self.lock:
            if self.ready_timer is not None:
                self.ready_timer.cancel()
                self.ready_timer = None

    def _ready_timeout(self) -> None:
        with self.lock:
            if self.state["phase"] != "ready":
                return
            self.state.update(
                phase="restoring",
                message="等待超时，正在自动恢复低功耗…",
            )
        self._restore_worker()

    def start_capture(self) -> None:
        with self.lock:
            if self.state["phase"] != "ready" or self.session_args is None:
                raise RuntimeError("Ball 尚未准备好，或当前正在采集")
            self._cancel_ready_timeout()
            repetition = int(self.state["completed"]) + 1
            self.state.update(
                phase="countdown",
                message="保持静止，3 秒后开始",
                instruction="看到并听到 GO 后再完成一次动作。",
            )
        threading.Thread(
            target=self._capture_worker, args=(repetition,), daemon=True
        ).start()

    def _capture_worker(self, repetition: int) -> None:
        assert self.session_args is not None
        command = build_capture_command(self.session_args, repetition)
        try:
            process = self.popen_factory(
                command,
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            with self.lock:
                self.current_process = process
            assert process.stderr is not None
            for raw_line in process.stderr:
                line = raw_line.lstrip("\a").strip()
                if line.startswith("ARMED: GO in"):
                    self._set(phase="countdown", message=line.replace("ARMED: ", ""))
                elif line.startswith("GO:"):
                    self._set(
                        phase="capturing",
                        message="GO — 现在完成一次动作",
                        instruction=PROFILES[self.session_args.profile].instruction,
                    )
                elif line.startswith("FREEZING:"):
                    self._set(
                        phase="freezing",
                        message="动作完成，正在保存数据…",
                        instruction="继续保持 Ball 静止。",
                    )
            returncode = process.wait()
        except Exception as exc:
            self._fail_and_restore("启动采集失败", str(exc))
            return
        finally:
            with self.lock:
                self.current_process = None

        if returncode != 0:
            self._fail_and_restore("本组采集失败，已停止批次", f"exit {returncode}")
            return

        capture = output_path(self.session_args, repetition)
        self._set(phase="analyzing", message="正在检查数据完整性…")
        analysis = self.command_runner(
            [PYTHON, str(ANALYZE_TOOL), str(capture)]
        )
        if analysis.returncode != 0:
            self._fail_and_restore("数据检查未通过，已停止批次", analysis.stderr)
            return
        try:
            payload = json.loads(analysis.stdout)
            features = payload["features"]
            diagnostic = payload["provisional_diagnostic"]
            final_status, continuity = capture_telemetry(
                capture, self.session_args.expected_device_id
            )
            continuity_status = (
                str(continuity.get("status", "UNKNOWN")) if continuity else "UNKNOWN"
            )
            clip_samples = sum(
                int(features.get(key, 0) or 0)
                for key in (
                    "adxl367_clip_samples",
                    "bmi270_accel_clip_samples",
                    "bmi270_gyro_clip_samples",
                )
            )
            last_result = {
                "file": capture.name,
                "samples": int(features["sample_count"]),
                "gyro_peak": float(features["gyro_norm_max_rads"]),
                "gyro_rms": float(features.get("gyro_norm_rms_rads", 0.0)),
                "accel_stdev": float(features.get("accel_norm_stdev_mps2", 0.0)),
                "sequence_gaps": int(features.get("sequence_gaps", 0) or 0),
                "clip_samples": clip_samples,
                "continuity": continuity_status,
                "state": str(diagnostic["state"]),
            }
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._fail_and_restore("分析结果格式无效", str(exc))
            return

        completed = repetition
        with self.lock:
            self.state["completed"] = completed
            self.state["last_result"] = last_result
            self.state["result_history"].append(
                {
                    "index": completed,
                    "gyro_peak": last_result["gyro_peak"],
                    "gyro_rms": last_result["gyro_rms"],
                    "accel_stdev": last_result["accel_stdev"],
                    "sequence_gaps": last_result["sequence_gaps"],
                    "clip_samples": last_result["clip_samples"],
                    "continuity": last_result["continuity"],
                }
            )
        if final_status is not None:
            self._record_device_status(final_status, f"第 {completed} 组")
        if completed >= self.session_args.count:
            self._restore_worker(completed=True)
        else:
            self._set(
                phase="ready",
                message="本组完成，可以重新摆球",
                instruction=PROFILES[self.session_args.profile].instruction,
            )
            self._arm_ready_timeout()

    def finish(self) -> None:
        with self.lock:
            if self.state["phase"] not in {"ready", "error"}:
                raise RuntimeError("当前正在采集，不能提前结束")
            self.state.update(phase="restoring", message="正在恢复低功耗…")
        self._cancel_ready_timeout()
        threading.Thread(target=self._restore_worker, daemon=True).start()

    def _restore_worker(self, *, completed: bool = False) -> None:
        self._cancel_ready_timeout()
        args = self.session_args
        if args is None:
            self._set(phase="idle", low_power=True)
            return
        self._set(phase="restoring", message="正在恢复 auto 低功耗模式…")
        try:
            self._set_power_mode(args, "auto", "结束")
        except (RuntimeError, ValueError):
            self._set(
                phase="error",
                message="无法确认低功耗恢复",
                instruction="请不要断开设备；在终端运行 set_tag_power_mode.py auto。",
                low_power=False,
            )
            return
        self._set(
            phase="complete" if completed else "idle",
            message=(
                "批次完成，Ball 已切回 auto"
                if completed
                else "批次已结束，Ball 已切回 auto"
            ),
            instruction="静止超时后会进入 idle；现在可以移动 Ball 或开始新批次。",
            low_power=True,
        )

    def _fail_and_restore(self, message: str, detail: str | None = None) -> None:
        self._cancel_ready_timeout()
        args = self.session_args
        restored = True
        if args is not None:
            try:
                self._set_power_mode(args, "auto", "异常恢复")
            except (RuntimeError, ValueError):
                restored = False
        instruction = detail or "请检查连接后重新准备批次"
        if not restored:
            instruction = f"{instruction}；低功耗恢复未确认，请点击结束批次重试"
        self._set(
            phase="error",
            message=message,
            instruction=instruction[-300:],
            low_power=restored,
        )

    def close(self) -> None:
        self._cancel_ready_timeout()
        with self.lock:
            process = self.current_process
            args = self.session_args
            needs_restore = not self.state.get("low_power", True)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        if needs_restore and args is not None:
            self.command_runner(build_power_command(args, "auto"))


def page_for_token(token: str) -> str:
    return PAGE_HTML.replace("__TOKEN__", json.dumps(token))


def make_handler(app: FieldCaptureApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "PuttTrackFieldCapture/1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _headers(self, status: int, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; connect-src 'self'; "
                "frame-ancestors 'none'; base-uri 'none'",
            )

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            return secrets.compare_digest(
                self.headers.get("X-PuttTrack-Token", ""), app.token
            )

        def _payload(self) -> dict[str, Any]:
            if self.headers.get_content_type() != "application/json":
                raise ValueError("请求必须使用 application/json")
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 4096:
                raise ValueError("请求内容过大")
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("请求必须是 JSON 对象")
            return payload

        def do_GET(self) -> None:
            if self.path == "/":
                body = page_for_token(app.token).encode("utf-8")
                self._headers(HTTPStatus.OK, "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if not self._authorized():
                self._json(HTTPStatus.FORBIDDEN, {"error": "unauthorized"})
                return
            if self.path == "/api/state":
                self._json(HTTPStatus.OK, app.snapshot())
            elif self.path == "/api/config":
                self._json(HTTPStatus.OK, app.config())
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:
            if not self._authorized():
                self._json(HTTPStatus.FORBIDDEN, {"error": "unauthorized"})
                return
            try:
                payload = self._payload()
                if self.path == "/api/session":
                    app.prepare(payload)
                elif self.path == "/api/capture/start":
                    app.start_capture()
                elif self.path == "/api/session/finish":
                    app.finish()
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
            except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
                return
            self._json(HTTPStatus.ACCEPTED, app.snapshot())

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--hci-port", default="/dev/cu.usbmodem101")
    parser.add_argument("--expected-device-id", default=DEFAULT_DEVICE_ID)
    parser.add_argument("--device-name", default="PuttTrack-")
    parser.add_argument("--ble-address")
    parser.add_argument(
        "--address-type",
        choices=("public", "random", "public-identity", "random-identity"),
    )
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "runs")
    parser.add_argument(
        "--idle-timeout-seconds",
        type=float,
        default=600.0,
        help="restore auto mode after this many seconds waiting between captures",
    )
    parser.add_argument("--no-browser", action="store_true")
    return parser


def validate_server_args(args: argparse.Namespace) -> None:
    if args.host not in LOOPBACK_HOSTS:
        raise ValueError("--host must be a loopback address; hardware control is local only")
    if not 1 <= args.port <= 65535:
        raise ValueError("--port must be between 1 and 65535")
    if args.address_type and not args.ble_address:
        raise ValueError("--address-type requires --ble-address")
    if args.idle_timeout_seconds <= 0:
        raise ValueError("--idle-timeout-seconds must be positive")


def main() -> int:
    args = build_parser().parse_args()
    try:
        validate_server_args(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    app = FieldCaptureApp(args)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(app))
    url = f"http://{args.host}:{server.server_port}/"
    print(f"PuttTrack IMU 采集台：{url}", flush=True)
    print("按 Ctrl-C 关闭；关闭时会尝试恢复 Ball 低功耗。", flush=True)
    if not args.no_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
