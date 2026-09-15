#!/usr/bin/env python3
"""Serve a local real-time PN532 status page for the PuttTrack Ball."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter, deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import statistics
import time
import webbrowser

import signal
import queue
import serial
from serial.tools import list_ports


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from putttrack.tag.recognition import Recognition, run_recognition
from putttrack.venue.single_hole_test import SingleHoleTest
from putttrack.venue.tee_indicator import TeeIndicator
from putttrack.service.nfc import parse_nfc_reader_event, ServiceTouchError


HTML = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PuttTrack NFC 状态</title>
<style>
:root{color-scheme:dark;--bg:#07130f;--panel:#10241c;--line:#244437;--text:#eef8f2;--muted:#91aa9e;--ok:#4ee09a;--warn:#ffc861;--bad:#ff7777}
*{box-sizing:border-box}button,select{padding:10px 14px;border-radius:10px;border:1px solid #244437;font:inherit}button{background:#4ee09a;color:#07130f;cursor:pointer}button:disabled{opacity:.4;cursor:default}body{margin:0;background:radial-gradient(circle at 15% 0,#173b2c 0,transparent 42%),var(--bg);color:var(--text);font:15px -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}
main{max-width:1050px;margin:auto;padding:34px 24px 56px}.eyebrow{color:var(--ok);font-weight:750;letter-spacing:.14em}.hero{display:flex;align-items:end;justify-content:space-between;gap:20px;margin:12px 0 26px}h1{font-size:clamp(34px,6vw,64px);line-height:1;margin:0}.hint{color:var(--muted);max-width:420px;line-height:1.6}
.banner,.card{background:color-mix(in srgb,var(--panel) 92%,transparent);border:1px solid var(--line);border-radius:20px}.banner{padding:24px 26px;display:flex;align-items:center;gap:18px;margin-bottom:18px}.dot{width:18px;height:18px;border-radius:50%;background:var(--warn);box-shadow:0 0 22px currentColor}.dot.ok{background:var(--ok)}.dot.bad{background:var(--bad)}#headline{font-size:25px;font-weight:760}.sub{color:var(--muted);margin-top:5px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card{padding:20px;min-width:0}.label{color:var(--muted);font-size:13px}.value{font-size:34px;font-weight:760;margin-top:8px}.wide{grid-column:span 2}.identity{font-size:19px;word-break:break-all;line-height:1.5}.oktext{color:var(--ok)}.warntext{color:var(--warn)}
.events{margin-top:18px}.event{display:grid;grid-template-columns:90px 150px 1fr;gap:12px;padding:12px 0;border-bottom:1px solid var(--line)}.event:last-child{border:0}.event code{color:#c8e8d8}.footer{color:var(--muted);margin-top:18px;font-size:13px}
@media(max-width:750px){.hero{display:block}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.wide{grid-column:span 2}.event{grid-template-columns:70px minmax(0,1fr)}.event code{grid-column:1/-1;overflow-wrap:anywhere}.value{font-size:25px}.footer,.sub{overflow-wrap:anywhere}}
.tee-light{width:56px;height:56px;flex-shrink:0;border-radius:50%;background:var(--warn);box-shadow:0 0 22px var(--warn)}
.tee-light.green{background:var(--ok);box-shadow:0 0 22px var(--ok)}.tee-light.red{background:var(--bad);box-shadow:0 0 22px var(--bad)}
.tee-light.breathe{animation:tee-breathe 1.8s ease-in-out infinite}.tee-light.pulse{animation:tee-breathe .7s ease-in-out infinite}
@keyframes tee-breathe{50%{opacity:.25;transform:scale(.9)}}
@media(prefers-reduced-motion:reduce){.tee-light{animation:none!important}}
</style></head><body><main>
<div class="eyebrow">PUTTTRACK / 单球单洞测试</div>
<section class="banner" style="margin-top:16px"><div id="tee-light" class="tee-light" aria-hidden="true"></div><div><div class="label">发球垫灯光预览 · 实体灯尚未接入</div><h2 id="tee-title" style="margin:6px 0">等待放球</h2><div id="tee-hint" class="sub">黄灯待机 → 呼吸识别 → 绿灯常亮</div></div></section>
<section class="card" style="margin:16px 0"><div class="label">放球验收 · 人工配合</div><div id="manual-result" class="value">等待开始</div><p>先拿离球 → 点击“开始本次放球” → 再把球放回垫子。计时包含人的操作时间；5 秒内只作为速度指标，10 秒内完成都判定成功。</p><div style="display:flex;gap:10px;flex-wrap:wrap"><button id="manual-start">开始本次放球</button><button id="manual-cancel">取消本次</button><a href="/api/recognition.json" download="placement-tests.json">导出测试记录</a></div><div id="manual-error" class="sub"></div><div id="manual-summary" class="sub"></div><div class="sub">成功 = 本次新的 NFC 身份 + BLE 核对完成。结果保留，后续 NFC 漏读不改判。拿离后再点按钮开始下一次，建议测 30 次。取消单独记录；刷新页面保留，服务重启另起一组，历史落盘。</div><div id="manual-history"></div></section><section class="card" style="margin:16px 0"><div class="label">第 1 洞 · 单光电原型</div><div id="hole-stage" class="value">等待开始</div><div id="hole-detail" class="sub">放球识别后创建本局</div><div style="display:flex;gap:10px;flex-wrap:wrap;margin:16px 0"><input id="player-name" aria-label="玩家名称" value="测试玩家" maxlength="30" style="padding:12px;border-radius:10px;max-width:100%"><select id="cup-mode" aria-label="入洞输入"><option value="simulation">模拟入洞（软件测试）</option><option value="optical">真实光电（待接线）</option></select><button id="round-start">准备新一局</button><button id="stroke">手动补记一杆</button><button id="simulate-cup">模拟入洞</button><button id="cancel-round">取消本局</button></div><div id="hole-error" class="sub" style="color:#ff7777"></div><div class="sub">顺序：放球识别 → 准备新一局 → IMU 实验自动记杆（可手动补记） → 光电/模拟入洞 → 结算。球留在垫上时识别持续有效；开局后本局会锁定这颗球，不依赖持续贴住 NFC，也不限制玩家起身时间。</div><div id="imu-state" class="sub"></div><div class="sub">IMU 实验规则按硬件区分：原版 Tag 保持原规则；XIAO 首次静止 0.6 秒，后续停稳后可更快准备，允许短暂轻晃。两版均需冲击后运动确认，仍可能误判拿放。建议每杆先停稳。</div><a href="/api/hole/results.json" download="single-hole-results.json">导出本局与最近结果</a><div id="hole-history"></div></section><div class="hero"><h1>NFC 读取状态</h1><div class="hint">保持小球与线圈不动，持续测试完整 UID + NDEF 读取。这里的频率来自实时串口数据，不是页面刷新率。</div></div>
<section class="card" style="margin-bottom:18px"><div class="label">放球识别 · NFC → BLE</div><div id="recognition" class="value">等待放球</div><div id="recognition-detail" class="sub">NFC 识别 → BLE 连接 → 身份核对 → 识别完成</div><div class="sub">完成表示同一颗球的 NFC / BLE 身份已核对，尚未关联玩家或激活球洞。</div><button id="system-off" style="margin-top:16px;padding:12px 18px;border:0;border-radius:12px;background:#4ee09a;color:#07130f;font:inherit;cursor:pointer" disabled>进入 System OFF</button><div id="off-result" class="sub">先完成识别，再拿离发球垫，等待 3 秒后点击；命令接受后再等至少 3 秒放回测试唤醒。</div><button id="ble-retry" disabled>重试 BLE</button><div id="ble-data" class="sub"></div><div id="off-data" class="sub"></div><div id="off-error" class="sub"></div></section>
<section class="card" style="margin-bottom:18px"><div class="label">本次放球测试 · 从有效 NFC 身份开始计时</div><div id="placement-summary" class="identity">暂无测试</div><div class="sub">成功率按已出结果的放球次数计算；拿走前未识别完成也计入分母。成功只表示首次身份核对完成，后续 BLE 中断单独记录。连续 3 秒没有任何有效 NFC 读数才确认球已拿走并结束本次统计；这不是玩家操作时限。开局后锁定本局球身份。</div><div id="placements"></div><a href="/api/recognition.json" download="putttrack-recognition.json" style="display:inline-block;margin-top:12px;color:#4ee09a">导出统计与最近 50 次记录</a></section>
<section class="card" style="margin-bottom:18px"><div class="label">最近 60 秒 · 按设备统计</div><div id="device-windows" class="sub">暂无读数</div><div class="sub">完整率只包含已发现 UID 的读取尝试，不代表全部寻卡成功率。不同设备分开统计。</div></section>
<section class="banner"><div id="dot" class="dot"></div><div><div id="headline">正在连接 PN532</div><div id="subtitle" class="sub">等待串口数据</div></div></section>
<section class="grid">
 <div class="card"><div class="label">完整读取 / 秒 · 最近 10 秒</div><div id="rate" class="value">—</div></div>
 <div class="card"><div class="label">读取间隔中位数 · 最近 10 秒</div><div id="interval" class="value">—</div></div>
 <div class="card"><div class="label">当前完整连读 / 本次最长</div><div id="streak" class="value">0</div></div>
 <div class="card"><div class="label">累计完整率 · 所有已发现标签</div><div id="ratio" class="value">—</div></div>
 <div class="card"><div class="label">累计完整读取 · 所有设备</div><div id="success" class="value">0</div></div>
 <div class="card"><div class="label">累计 NDEF 失败 / 中断</div><div id="misses" class="value">0</div></div>
 <div class="card"><div class="label">PN532</div><div id="reader" class="value" style="font-size:23px">连接中</div></div>
 <div class="card"><div class="label">最近读取</div><div id="age" class="value" style="font-size:23px">—</div></div>
 <div class="card wide"><div class="label">小球身份</div><div id="device" class="identity">—</div></div>
 <div class="card wide"><div class="label">UID / 固件</div><div id="detail" class="identity">—</div></div>
 <div class="card" style="grid-column:1/-1"><div class="label">最近 NDEF</div><div id="ndef" class="identity">等待读取</div></div>
</section>
<section class="card events"><div class="label">最近 60 秒 · 每秒完整读取次数</div><svg id="chart" viewBox="0 0 900 160" role="img" aria-label="最近60秒完整读取次数趋势" style="display:block;width:100%;height:180px"></svg><div id="config" class="sub"></div><div id="rf" class="sub"></div><div class="sub">7.86 次/秒是此前已测得的配置表现，并非硬件速度上限。解析成功率不包含未发现标签的轮询；中断事件也不等于全部失败轮询次数。</div></section>
<section class="card events"><div class="label">最近 NFC 事件</div><div id="events"></div></section>
<div id="footer" class="footer"></div>
</main><script>
const $=id=>document.getElementById(id); const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function batteryText(s){if(!s.battery_supported||!s.battery_sample_valid)return '暂无有效电压';return s.battery_presence_known===true?'电池 '+s.battery_voltage_mv+' mV · 估算 '+s.battery_soc_percent+'%':'BAT 端电压 '+s.battery_voltage_mv+' mV · 未确认电池接入，不显示电量百分比';}
let activeRound=null;
function render(s){
 const light=s.tee_indicator||{};
 $('tee-light').className='tee-light '+(light.color||'yellow')+' '+(light.effect||'steady');
 $('tee-title').textContent=light.title||'等待发球垫';$('tee-hint').textContent=light.hint||'';
 const rec=s.recognition||{};
 const h=s.hole_test||{},game=h.game||{},ps=game.player_hole_state?.player||{},phase=h.stage||'idle';activeRound=h.round_id;
 const phases={idle:'等待开始',armed:'准备完成，可以击球',playing:'本局进行中',complete:'入洞！本局结束',cancelled:'本局已取消'};
 $('hole-stage').textContent=phases[phase]||phase;
 $('hole-detail').textContent=h.round_id?((game.ranking?.[0]?.display_name||game.active_player?.display_name||'测试玩家')+' · '+(ps.strokes||0)+' 杆 · '+(h.mode==='simulation'?'模拟入洞模式':'真实单光电模式')):(rec.stage==='complete'?('已识别小球 '+rec.device_id+'，点击“准备新一局”创建游戏'):'尚未创建游戏 · 请先等待下方完成 NFC / BLE 识别');
 $('round-start').disabled=!['idle','complete','cancelled'].includes(phase)||s.recognition?.stage!=='complete';
 $('stroke').disabled=!['armed','playing'].includes(phase);$('simulate-cup').disabled=phase!=='playing'||h.mode!=='simulation';$('cancel-round').disabled=!['armed','playing'].includes(phase);
 const idleConnected=!['armed','playing'].includes(phase)&&s.recognition?.stage==='complete';
 const layout=h.imu?.sensor_layout||s.recognition?.sensor_layout;
 $('imu-state').textContent='IMU：'+(idleConnected?'BLE 已连接，开局后启用采样':h.imu?.phase||'等待数据')+' · '+(layout==='adxl367-bmi270'?'原版 Tag':layout==='lsm6ds3tr-c-single'?'XIAO':'等待硬件信息')+' · '+(h.imu?.model||'等待模型')+' · 本局 '+(h.imu?.samples||0)+' 帧 · '+(idleConnected?'当前未采集本局数据':h.imu?.age_s==null?'尚未收到':h.imu.age_s>2?'数据中断':'实时接收')+' · 光电：'+(!h.cup?.ready?'未就绪':h.cup.blocked?'遮挡':'畅通');
 $('hole-history').innerHTML=(h.history||[]).slice(0,5).map(r=>`<div class="event"><span>已完成</span><strong>${esc(r.player)} · ${r.strokes} 杆</strong><code>${esc(r.cup_source==='simulation'?'模拟入洞':'光电入洞')} · ${esc(r.device_id)}</code></div>`).join('');

 const names={waiting:'等待放球',nfc_identified:'NFC 已识别',scanning:'正在寻找这颗球的 BLE',connecting:'正在连接 BLE',verifying:'正在核对身份',complete:'识别完成',error:'识别未完成'};
 const m=rec.manual_placement||{}, mt=m.current, mn={pending:'请立即放球',success:'本次通过',timeout:'本次超时',failure:'本次失败',cancelled:'已取消'};
 $('manual-result').textContent=mt?(mn[mt.outcome]+' · '+((mt.elapsed_ms??m.elapsed_ms??0)/1000).toFixed(2)+' 秒'):(rec.stage==='complete'?('尚未开始人工计时 · 当前已识别 '+rec.device_id):'尚未开始人工计时');
 $('manual-start').disabled=mt?.outcome==='pending'; $('manual-cancel').disabled=mt?.outcome!=='pending';
 $('manual-summary').textContent='已完成 '+(m.resolved||0)+' / 建议 30 次 · 通过 '+(m.success||0)+' · 5 秒内 '+(m.within_5s||0)+' · 成功率 '+(m.success_rate==null?'—':m.success_rate.toFixed(1)+'%')+' · 取消 '+(m.cancelled||0);
 $('manual-history').innerHTML=(m.trials||[]).slice(0,30).map(t=>`<div class="event"><span>#${t.id}</span><strong>${esc(mn[t.outcome])}</strong><code>NFC ${t.nfc_ms==null?'未读到':(t.nfc_ms/1000).toFixed(2)+' 秒'} · 完成 ${t.elapsed_ms==null?'—':(t.elapsed_ms/1000).toFixed(2)+' 秒'} ${esc(t.reason||'')}</code></div>`).join('');
 const summary=rec.summary||{}, outcomes={pending:'识别中',success:'成功',failure:'失败',interrupted:'未完成即中断'};
 $('placement-summary').textContent='放球 '+(summary.placements||0)+' 次 · 成功 '+(summary.success||0)+' · 失败 '+(summary.failure||0)+' · 中断 '+(summary.interrupted||0)+' · 成功率 '+(summary.success_rate==null?'—':summary.success_rate.toFixed(1)+'%')+' · 平均 '+(summary.mean_ms==null?'—':(summary.mean_ms/1000).toFixed(2)+' 秒')+' · 最慢 '+(summary.max_ms==null?'—':(summary.max_ms/1000).toFixed(2)+' 秒');
 $('placements').innerHTML=(rec.trials||[]).slice(0,8).map(t=>`<div class="event"><span>#${t.id}</span><strong>${esc(outcomes[t.outcome])}</strong><code>${esc(t.device_id)} · ${t.recognition_ms==null?'—':(t.recognition_ms/1000).toFixed(2)+' 秒'} · ${t.attempts} 次连接尝试 · BLE 中断 ${t.ble_interruptions}${t.reason?' · '+esc(t.reason):''}</code></div>`).join('');
 $('recognition').textContent=names[rec.stage]||'等待放球'; $('recognition').className='value '+(rec.stage==='complete'?'oktext':'');
 $('recognition-detail').textContent=rec.device_id?(rec.device_id+' · '+(rec.sensor_layout==='adxl367-bmi270'?'原版 Tag':rec.sensor_layout==='lsm6ds3tr-c-single'?'XIAO':'')+' · 固件 '+(rec.firmware||'—')+' · '+(rec.stage==='complete'?'NFC / BLE 一致 · '+(rec.elapsed_ms/1000).toFixed(2)+' 秒':rec.error||'第 '+rec.attempts+' 次连接')):'请将已供电的小球放在发球垫上';
 $('ble-retry').disabled=rec.stage!=='error';
 $('system-off').disabled=!rec.last_verified||!!rec.device_id||rec.system_off?.stage==='sending';
 const live=rec.stage==='complete'?rec.wake_status:null; $('ble-data').textContent=live?('BLE 状态回读：'+batteryText(live)+' · 传感器 '+live.sensor_health+' · 加密等级 '+live.ble_security_level):'';
 const wake=rec.system_off?.status_after; $('off-data').textContent=wake?('唤醒数据：固件 '+wake.fw+' · 加密等级 '+wake.ble_security_level+' · '+batteryText(wake)+' · 传感器 '+wake.sensor_health+' · 首次 NDEF 至 BLE '+(rec.system_off.wake_to_ble_ms==null?'未计时':rec.system_off.wake_to_ble_ms+' ms')+' · 启动标识 '+rec.system_off.boot_id_before+' → '+rec.system_off.boot_id_after):'';
 if(rec.system_off?.stage) $('off-result').textContent=rec.system_off.message||(rec.system_off.stage==='sending'?'正在发送 System OFF 命令…':'');
 $('device-windows').innerHTML=(s.device_windows||[]).map(d=>`<div class="event"><span>${d.device_id==='4d53cd7b5c288607'?'XIAO':d.device_id==='f383571202836e6f'?'Tag':'未核对设备'}</span><strong>${d.success} 成功 / ${d.failures} 失败</strong><code>${esc(d.device_id||d.uid||'未知 UID')} · ${d.completion_percent.toFixed(1)}% · ${d.reads_per_second.toFixed(2)} 次/秒 · ${d.age_s.toFixed(1)} 秒前</code></div>`).join('')||'最近 60 秒没有读到标签';
 const last=s.last_read||{}; const fresh=last.age_s!=null&&last.age_s<3;
 $('success').textContent=s.successful_reads; $('misses').textContent=s.ndef_failures+' / '+s.miss_events;
 $('rate').textContent=s.rate_hz.toFixed(2); $('interval').textContent=s.interval_ms==null?'—':s.interval_ms.toFixed(0)+' ms';
 $('streak').textContent=s.consecutive+' / '+s.best; $('ratio').textContent=s.success_ratio==null?'—':s.success_ratio.toFixed(1)+'%';
 const bins=s.history,max=Math.max(10,...bins); $('chart').innerHTML=bins.map((v,i)=>`<rect x="${i*15}" y="${140-v/max*120}" width="11" height="${v/max*120}" rx="2" fill="#4ee09a"><title>${60-i} 秒前：${v} 次</title></rect>`).join('')+`<text x="0" y="158" fill="#91aa9e" font-size="12">60 秒前</text><text x="840" y="158" fill="#91aa9e" font-size="12">现在</text><text x="0" y="12" fill="#91aa9e" font-size="12">${max} 次/秒</text>`;
 const rf=s.rf_status||{}; $('rf').textContent=rf.ok?'实测寄存器：载波驱动 P '+rf.p_driver+'/63 · N '+rf.n_driver+'/15（驱动档位，不是天线功率测量）':'等待首次完整读取后获取射频驱动参数';
 const c=s.config||{}; $('config').textContent=Object.keys(c).length?'寻卡超时 '+c.scan_timeout_ms+' ms · 轮间隔 '+c.scan_gap_ms+' ms · 断场 '+c.field_off_ms+' ms · 迁移等待 '+c.command_window_ms+' ms':'等待固件报告扫描参数';
 $('reader').textContent=s.ready?'正常':s.connected?'初始化中':'未连接'; $('reader').className='value '+(s.ready?'oktext':'warntext');
 $('age').textContent=last.age_s==null?'—':last.age_s.toFixed(1)+' 秒前';
 $('device').textContent=last.device_id||'—'; $('detail').textContent=(last.uid||'—')+'  /  '+(last.firmware||'—');
 $('ndef').textContent=last.ndef_uri||last.error_message||last.error||'等待读取';
 let title='等待小球',sub='请将小球贴到 PN532 天线中央',cls='dot';
 if(!s.connected){title='PN532 串口未连接';sub=s.error||'检查 USB 连接';cls='dot bad'}
 else if(!s.ready){title='PN532 正在初始化';sub=s.serial_port;}
 else if(s.interrupted){title='读取中断';sub='保持小球不动，观察是否自动恢复';}
 else if(fresh&&last.ok){title='正在连续读取';sub='完整 UID + NDEF · 本次运行 '+Math.floor(s.uptime_s)+' 秒';cls='dot ok'}
 else if(fresh){title='NDEF 身份读取失败';sub=last.error_message||last.error||'身份未通过校验';cls='dot bad'}
 else if(last.age_s!=null){title='读取超时';sub='超过 3 秒没有新标签数据，等待自动恢复';}
 $('headline').textContent=title;$('subtitle').textContent=sub;$('dot').className=cls;
 $('events').innerHTML=(s.events||[]).map(e=>`<div class="event"><span>${esc(e.time)}</span><strong>${esc(e.label)}</strong><code>${esc(e.detail)}</code></div>`).join('')||'<div class="sub" style="padding-top:12px">暂无事件</div>';
 $('footer').textContent='串口 '+(s.serial_port||'—')+' · 页面每 0.4 秒刷新 · 日志 '+s.log_path;
}
async function holeAction(action){$('hole-error').textContent='';try{const r=await fetch('/api/hole/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-PuttTrack-Action':'hole-test'},body:JSON.stringify({action_id:crypto.randomUUID(),round_id:activeRound,player:$('player-name').value,mode:$('cup-mode').value})});const result=await r.json();if(!result.ok)throw Error(result.error);render(await(await fetch('/api/status')).json())}catch(e){$('hole-error').textContent=e.message}}
$('round-start').onclick=()=>holeAction('start');$('stroke').onclick=()=>holeAction('stroke');$('simulate-cup').onclick=()=>holeAction('simulate-cup');$('cancel-round').onclick=()=>holeAction('cancel');
async function manualAction(action){$('manual-error').textContent='';$('manual-start').disabled=true;try{const r=await fetch('/api/placement/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-PuttTrack-Action':'placement-test'},body:JSON.stringify({action_id:crypto.randomUUID()})});const d=await r.json();if(!d.ok)throw Error(d.error);render(await(await fetch('/api/status')).json());}catch(e){$('manual-error').textContent=e.message;}}
$('manual-start').onclick=()=>manualAction('start');$('manual-cancel').onclick=()=>manualAction('cancel');
$('ble-retry').onclick=async()=>{try{const r=await fetch('/api/recognition/retry',{method:'POST',headers:{'X-PuttTrack-Action':'recognition-retry'}});const s=await r.json();$('off-error').textContent=s.error||'已请求重试';}catch(e){$('off-error').textContent='请求失败';}};
$('system-off').onclick=async()=>{ $('off-error').textContent=''; $('ble-retry').disabled=rec.stage!=='error';
 $('system-off').disabled=true; try{const r=await fetch('/api/system-off',{method:'POST',headers:{'X-PuttTrack-Action':'system-off'}});const s=await r.json();if(!s.accepted)$('off-error').textContent=s.error;}catch(e){$('off-error').textContent='请求失败，请检查页面服务';}};
async function poll(){try{let r=await fetch('/api/status',{cache:'no-store'});render(await r.json())}catch(e){$('headline').textContent='页面连接中断';$('subtitle').textContent='正在重试连接本地服务';$('dot').className='dot bad';$('rate').textContent='—'}finally{setTimeout(poll,400)}}poll();
</script></body></html>"""


class NfcState:
    def __init__(self, serial_port: str, log_path: Path):
        self.lock = threading.Lock()
        self.serial_port, self.log_path = serial_port, log_path
        self.connected = self.ready = False
        self.error = ""
        self.events: deque[dict] = deque(maxlen=12)
        self.stop_event = threading.Event()
        self.commands = queue.Queue()
        self.hole = SingleHoleTest(log_path.with_suffix(".hole.jsonl"), log_path.parent.glob("nfc_web_*.hole.jsonl"))
        self.indicator = TeeIndicator()
        self.recognition = Recognition(log_path.with_suffix(".recognition.jsonl"))
        self.hole.command = self.commands.put
        self.recognition.game_target = self.hole.active_identity
        self.recognition.motion_callback = self.hole.observe_motion
        self.recognition.motion_disconnect = self.hole.motion_disconnected
        self.reset()

    def reset(self):
        self.started = time.monotonic()
        self.successful_reads = self.miss_events = self.ndef_failures = 0
        self.consecutive = self.best = 0
        self.interrupted = False
        self.last_read = {}
        self.config = {}
        self.rf_status = {}
        self.pending_apdu = None
        self.device_reads = deque(maxlen=20000)
        self.uid_identities = {}
        self.counts = Counter()
        self.samples = deque(maxlen=20000)

    def add_event(self, event: dict) -> None:
        self.hole.observe_cup(event)
        self.recognition.observe(event)
        kind = event.get("event")
        now = time.monotonic()
        stamp = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            label, detail = None, ""
            if kind == "boot":
                self.reset()
                self.events.clear()
                self.ready = False
                label = "读卡器重启 · 计数重置"
            self.counts[str(kind)] += 1
            if kind == "connected":
                self.connected = True
                self.error = ""
                label, detail = "USB 已连接", self.serial_port
            elif kind == "scan_ready":
                self.ready = True
                self.config = dict(event)
                label = "PN532 就绪"
            elif kind == "rf_status":
                self.rf_status = dict(event)
                label = "射频驱动读回" if event.get("ok") else "射频诊断失败"
                detail = (f"P {event.get('p_driver')}/63 · N {event.get('n_driver')}/15"
                          if event.get("ok") else "未取得有效寄存器响应")
            elif kind == "apdu_failure":
                self.pending_apdu = dict(event)
            elif kind == "nfc_tag":
                self.ready = True
                ok = bool(event.get("ndef_ok") and event.get("service_uri_ok"))
                identity = event.get("device_id") or event.get("uid")
                previous = self.last_read
                if previous and (now - previous["at"] > 3 or identity != previous.get("identity")):
                    self.consecutive = 0
                if ok:
                    self.successful_reads += 1
                    self.consecutive += 1
                    self.best = max(self.best, self.consecutive)
                    self.samples.append(now)
                else:
                    self.ndef_failures += 1
                    self.consecutive = 0
                self.interrupted = False
                error_message = event.get('ndef_error')
                if error_message == 'not_type4_ndef' and isinstance(event.get('sak'), int) and event['sak'] & 0x20:
                    error_message = 'Type 4 已识别，但 NDEF 会话选择失败'
                elif error_message == 'type4_ndef_unreadable':
                    error_message = 'Type 4 NDEF 数据读取中断'
                elif error_message == 'type4_nlen_unreadable':
                    error_message = 'Type 4 NDEF 长度读取失败'
                diagnostic = self.pending_apdu if not ok else None
                self.pending_apdu = None
                strict_ok = False
                try:
                    touch = parse_nfc_reader_event(event)
                    strict_ok = True
                    if touch.rf_uid:
                        self.uid_identities[touch.rf_uid] = touch.device_id
                except (ServiceTouchError, ValueError, TypeError):
                    pass
                self.device_reads.append((now, event.get('uid'), strict_ok,
                                          diagnostic.get('diagnostic') if diagnostic else None))
                if diagnostic:
                    reason = {1:'标签响应超时', 2:'无线 CRC 校验错误', 3:'无线奇偶校验错误',
                              6:'无线位冲突', 0x101:'主机命令或响应等待失败',
                              0x102:'主机响应等待超时', 0x103:'主机响应帧异常'}.get(diagnostic.get('diagnostic'))
                    if reason:
                        error_message = f'{error_message} · {reason}'
                self.last_read = {
                    "ok": ok, "at": now, "identity": identity,
                    "uid": event.get("uid"),
                    "device_id": event.get("device_id") or event.get("ball_id"),
                    "firmware": event.get("firmware_version"),
                    "ndef_uri": event.get("ndef_uri"), "error": event.get("ndef_error"), "error_message": error_message,
                    "apdu_diagnostic": diagnostic,
                }
                # Keep interruptions visible instead of flooding the event list.
                if not ok or self.consecutive == 1 or self.consecutive % 100 == 0:
                    label = "身份成功" if ok else "NDEF 失败"
                    detail = str(identity) + (f" · 连续 {self.consecutive} 次" if ok else " · " + str(error_message or "身份无效"))
            elif kind in ("scan_miss", "tag_removed", "rf_cycle_failed"):
                self.pending_apdu = None
                self.consecutive = 0
                self.interrupted = True
                if kind == "scan_miss":
                    self.miss_events += 1
                label = {"scan_miss": "读取中断", "tag_removed": "持续未读到标签", "rf_cycle_failed": "射频恢复失败"}[kind]
                detail = event.get("phase") or event.get("uid", "")
            elif kind in ("fatal", "disconnected"):
                self.ready = False
                self.consecutive = 0
                self.samples.clear()
                if kind == "disconnected":
                    self.connected = False
                self.error = event.get("message", "串口 / PN532 故障")
                label, detail = "连接故障", self.error
            if label:
                self.events.appendleft({"time": stamp, "label": label, "detail": detail})

    def snapshot(self) -> dict:
        now = time.monotonic()
        with self.lock:
            while self.samples and self.samples[0] < now - 60:
                self.samples.popleft()
            while self.device_reads and self.device_reads[0][0] < now - 60:
                self.device_reads.popleft()
            devices = {}
            window = min(60, max(1, now - self.started))
            for at, uid, ok, code in self.device_reads:
                identity = self.uid_identities.get(uid)
                key = identity or uid or 'unknown'
                d = devices.setdefault(key, {'device_id': identity, 'uid':uid,
                    'attempts':0, 'success':0, 'failures':0, 'apdu_errors':{}, 'last_at':at})
                d['attempts'] += 1
                d['success' if ok else 'failures'] += 1
                d['last_at'] = at
                if code is not None:
                    d['apdu_errors'][str(code)] = d['apdu_errors'].get(str(code), 0) + 1
            for d in devices.values():
                d['completion_percent'] = 100*d['success']/d['attempts']
                d['reads_per_second'] = d['success']/window
                d['age_s'] = round(now-d.pop('last_at'), 2)
            last = dict(self.last_read)
            if last:
                last["age_s"] = round(now - last.pop("at"), 2)
            fresh = bool(last) and last["age_s"] < 3
            recent = [t for t in self.samples if t > now - 10]
            intervals = sorted((b-a)*1000 for a,b in zip(recent, recent[1:]))
            history = [0] * 60
            for t in self.samples:
                history[max(0, min(59, 59-int(now-t)))] += 1
            total = self.successful_reads + self.ndef_failures
            hole_view, recognition_view = self.hole.snapshot(), self.recognition.snapshot()
            indicator = self.indicator.snapshot(ready=self.connected and self.ready,
                recognition=recognition_view, last_read=last, hole=hole_view)
            return {
                "tee_indicator": indicator,
                "hole_test": hole_view,
                "recognition": recognition_view,
                "device_windows": list(devices.values()),
                "connected": self.connected, "ready": self.ready, "error": self.error,
                "serial_port": self.serial_port, "successful_reads": self.successful_reads,
                "miss_events": self.miss_events, "ndef_failures": self.ndef_failures,
                "consecutive": self.consecutive if fresh and self.ready else 0, "best": self.best,
                "interrupted": self.interrupted,
                "rate_hz": len(recent)/min(10, max(1, now-self.started)) if self.ready else 0,
                "interval_ms": statistics.median(intervals) if intervals and fresh and self.ready else None,
                "success_ratio": 100*self.successful_reads/total if total else None,
                "history": history, "config": self.config, "rf_status": self.rf_status, "uptime_s": now-self.started,
                "last_read": last, "events": list(self.events), "event_counts": dict(self.counts),
                "log_path": str(self.log_path),
            }


def find_reader(explicit: str | None) -> str:
    if explicit:
        return explicit
    ports = [port.device for port in list_ports.comports() if port.vid == 0x303A]
    if len(ports) != 1:
        raise RuntimeError("未找到唯一的 ESP32 PN532 串口，请使用 --serial-port 指定")
    return ports[0]


def serial_worker(state: NfcState) -> None:
    try:
        with serial.Serial(port=None, baudrate=115200, timeout=0.3, exclusive=True) as connection:
            connection.dtr = False
            connection.rts = False
            connection.port = state.serial_port
            connection.open()
            # Start a fresh capture, not a burst of old USB-buffered reads.
            # Hold reset while discarding bytes, then capture the new boot.
            connection.rts = True
            time.sleep(0.2)
            connection.reset_input_buffer()
            connection.rts = False
            state.add_event({"event": "connected"})
            awaiting_boot = True
            with state.log_path.open("a", encoding="utf-8") as log:
                while not state.stop_event.is_set():
                    while not state.commands.empty():
                        connection.write((state.commands.get_nowait()+'\n').encode('ascii'))
                    raw = connection.readline()
                    if not raw:
                        continue
                    line = raw.decode(errors="replace").strip()
                    log.write(json.dumps({"time": datetime.now().astimezone().isoformat(), "raw": line}, ensure_ascii=False) + "\n")
                    log.flush()
                    try:
                        event = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    if isinstance(event, dict):
                        if awaiting_boot:
                            if event.get("event") != "boot":
                                continue
                            awaiting_boot = False
                        state.add_event(event)
    except Exception as exc:
        state.add_event({"event": "disconnected", "message": str(exc)})


def handler_for(state: NfcState):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path.startswith('/api/placement/'):
                self.placement_action()
                return
            if self.path.startswith('/api/hole/'):
                self.hole_action()
                return
            if self.path not in ('/api/system-off','/api/recognition/retry'):
                self.send_error(404)
                return
            # Only the local page may trigger hardware changes.
            expected = f"http://{self.headers.get('Host')}"
            if self.headers.get('Origin') != expected or self.headers.get('X-PuttTrack-Action') != ('recognition-retry' if self.path.endswith('/retry') else 'system-off'):
                self.send_error(403)
                return
            try:
                if self.path.endswith('/retry'):
                    state.recognition.request_retry()
                else:
                    state.recognition.request_system_off()
                result, code = {"accepted": True}, 202
            except ValueError as exc:
                result, code = {"accepted": False, "error": str(exc)}, 409
            body = json.dumps(result, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def placement_action(self):
            if self.headers.get('Origin') != f"http://{self.headers.get('Host')}" or self.headers.get('X-PuttTrack-Action') != 'placement-test':
                self.send_error(403)
                return
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 1024:
                    raise ValueError('无效请求长度')
                data = json.loads(self.rfile.read(length))
                action_id = data.get('action_id') if isinstance(data,dict) else None
                if not isinstance(action_id,str) or not 1<=len(action_id)<=80:
                    raise ValueError('无效操作标识')
                if not state.connected or not state.ready:
                    raise ValueError('读卡器尚未就绪')
                state.recognition.manual_action(self.path.removeprefix('/api/placement/'),action_id)
                result, code = {'ok':True}, 200
            except (ValueError,TypeError) as exc:
                result, code = {'ok':False,'error':str(exc)}, 409
            body = json.dumps(result,ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def hole_action(self):
            expected = f"http://{self.headers.get('Host')}"
            if self.headers.get('Origin') != expected or self.headers.get('X-PuttTrack-Action') != 'hole-test':
                self.send_error(403)
                return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 4096:
                    raise ValueError('无效请求长度')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):
                    raise ValueError('无效请求')
                action_id=data.get('action_id')
                if not isinstance(action_id,str) or not 1<=len(action_id)<=80:
                    raise ValueError('无效操作标识')
                action=self.path.removeprefix('/api/hole/')
                if action=='start':
                    state.hole.start(data.get('player'),state.recognition.snapshot(),data.get('mode'),action_id)
                    state.recognition.pinned_identity = state.hole.engine.state.players['player'].ball_id
                else:
                    state.hole.action(action,data.get('round_id'),action_id)
                body=json.dumps({'ok':True,'hole_test':state.hole.snapshot()},ensure_ascii=False).encode()
                code=200
            except (ValueError,TypeError) as exc:
                body=json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False).encode();code=400
            self.send_response(code)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/?"):
                body, content_type = HTML.encode(), "text/html; charset=utf-8"
            elif self.path == "/api/recognition.json":
                body = json.dumps(state.recognition.snapshot(), ensure_ascii=False, indent=2).encode()
                content_type = "application/json; charset=utf-8"
            elif self.path == "/api/hole/results.json":
                body = json.dumps(state.hole.snapshot(), ensure_ascii=False, indent=2).encode()
                content_type = "application/json; charset=utf-8"
            elif self.path == "/api/status":
                body = json.dumps(state.snapshot(), ensure_ascii=False).encode()
                content_type = "application/json; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial-port")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("NFC hardware status server must use a loopback host")
    serial_port = find_reader(args.serial_port)
    log_path = Path(__file__).resolve().parents[1] / "runs" / ("nfc_web_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".jsonl")
    log_path.parent.mkdir(exist_ok=True)
    state = NfcState(serial_port, log_path)
    server = ThreadingHTTPServer((args.host, args.http_port), handler_for(state))
    recognition_thread = threading.Thread(target=lambda: asyncio.run(run_recognition(state.recognition, stop_event=state.stop_event)), daemon=True)
    serial_thread = threading.Thread(target=serial_worker, args=(state,), daemon=True)
    recognition_thread.start()
    serial_thread.start()
    url = f"http://{args.host}:{server.server_port}/"
    print(json.dumps({"status": "ready", "url": url, "serial_port": serial_port, "log_path": str(log_path)}, ensure_ascii=False), flush=True)
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    def stop_server(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_server)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        state.hole.cancel_active('server_shutdown')
        state.stop_event.set()
        recognition_thread.join(timeout=15)
        serial_thread.join(timeout=2)
        server.server_close()


if __name__ == "__main__":
    main()
