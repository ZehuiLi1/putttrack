#!/usr/bin/env python3
"""Run a reversible live IMU capture on the already NFC-verified ball.

Creates a named simulation round, records real IMU, then cancels it. No cup
result is fabricated. Keep the ball untouched to use this as a rest check.
"""
import argparse
import json
from pathlib import Path
import time
import urllib.request
import uuid


def check(base, duration):
    def get(): return json.load(urllib.request.urlopen(base+'/api/status', timeout=5))
    def post(action,**data):
        req=urllib.request.Request(base+'/api/hole/'+action,
            data=json.dumps({'action_id':uuid.uuid4().hex,**data}).encode(),
            headers={'Origin':base,'X-PuttTrack-Action':'hole-test','Content-Type':'application/json'})
        return json.load(urllib.request.urlopen(req,timeout=5))
    before=get()
    if before['hole_test']['stage'] in ('armed','playing'):
        raise RuntimeError('A user round is active; refused to interrupt it')
    if before['recognition']['stage']!='complete':
        raise RuntimeError('Place the selected ball on the NFC reader and wait for identification')
    round_id=post('start',player='自动链路检查（不计成绩）',mode='simulation')['hole_test']['round_id']
    samples=[]
    try:
        until=time.monotonic()+duration
        while time.monotonic()<until:
            time.sleep(min(1,max(0,until-time.monotonic())))
            current=get()
            if current['hole_test']['round_id']!=round_id:
                raise RuntimeError('Round was replaced during capture')
            samples.append({'imu':current['hole_test']['imu'],'stage':current['hole_test']['stage'],
                'strokes':current['hole_test']['game']['player_hole_state']['player']['strokes'],
                'recognition':current['recognition']['stage']})
    finally:
        current=get()
        if current['hole_test']['round_id']==round_id and current['hole_test']['stage'] in ('armed','playing'):
            post('cancel',round_id=round_id)
    deadline=time.monotonic()+5
    while True:
        after=get()
        if after['recognition'].get('power_policy')==before['recognition'].get('power_policy') or time.monotonic()>deadline: break
        time.sleep(.2)
    packets=[]
    for line in Path(before['log_path']).with_suffix('.hole.jsonl').read_text().splitlines():
        event=json.loads(line)
        if event.get('round_id')==round_id and event.get('kind')=='imu_sample': packets.append(event['sample'])
    gaps=sum(b['sequence']!=a['sequence']+1 for a,b in zip(packets,packets[1:]))
    span=(packets[-1]['source_monotonic_us']-packets[0]['source_monotonic_us'])/1e6 if len(packets)>1 else 0
    result={'device_id':before['recognition']['device_id'],'firmware':before['recognition'].get('firmware'),
        'sensor_layout':before['recognition'].get('sensor_layout'),'round_id':round_id,
        'samples':len(packets),'sequence_discontinuities':gaps,
        'invalid_samples':sum(bool(p['sensor_error_bits']) or not p['bmi270_valid'] for p in packets),
        'measured_hz':(len(packets)-1)/span if span>0 else None,
        'automatic_strokes':samples[-1]['strokes'] if samples else None,
        'power_before':before['recognition'].get('power_policy'),'power_after':after['recognition'].get('power_policy'),
        'snapshots':samples,'authority':False,'log_path':before['log_path']}
    result['transport_passed']=len(packets)>0 and gaps==0 and result['invalid_samples']==0 and result['power_before']==result['power_after']
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8765')
    parser.add_argument('--duration',type=float,default=20)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.duration<=300: parser.error('duration must be 1–300 seconds')
    result=check(args.url.rstrip('/'),args.duration)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='snapshots'},ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['transport_passed'] else 1)
