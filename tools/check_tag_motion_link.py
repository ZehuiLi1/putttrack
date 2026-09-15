#!/usr/bin/env python3
"""Check either Tag or XIAO over encrypted BLE, without pretending NFC activation.

Temporarily enables research sampling and restores the original power policy.
Records raw packets and reports transport health; does not create a game.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from bleak import BleakClient
from putttrack.tag.ble_smp import BleSmp, find_tag_device
from putttrack.tag.recognition import check_ble_identity
from putttrack.tag.telemetry import STATUS_CHARACTERISTIC_UUID, MOTION_CHARACTERISTIC_UUID, parse_status, parse_motion
from putttrack.venue.bench_stroke import BenchStrokeDetector


async def check(identity,address,duration,output):
    result={'device_id':identity,'authority':False,'passed':False}
    samples=[]
    errors=[]
    detector=BenchStrokeDetector()
    triggers=[]
    with output.with_suffix('.jsonl').open('w') as raw:
        def emit(event): raw.write(json.dumps({'host_time':time.time(),**event})+'\n');raw.flush()
        try:
            device=await find_tag_device(identity,address=address,timeout=15)
            if device is None: raise RuntimeError('Tag advertisement not found')
            result['address']=device.address
            async with BleakClient(device,timeout=10) as client:
                status=parse_status(await client.read_gatt_char(STATUS_CHARACTERISTIC_UUID))
                if status.device_id!=identity: raise RuntimeError('GATT identity mismatch')
                async with BleSmp(client,timeout=5) as smp:
                    before=await smp.request(64,0)
                    check_ble_identity(identity,before)
                    policy=before.get('power_policy')
                    if policy not in ('auto','idle','research'): raise RuntimeError('Unknown original power policy')
                    result.update(firmware=before.get('fw'),sensor_layout=status.sensor_layout,power_before=policy)
                    emit({'record_type':'before','status':before})
                    try:
                        ack=await smp.request(64,21,write=True)
                        if ack.get('accepted') is not True: raise RuntimeError('Research mode rejected')
                        for _ in range(20):
                            active=await smp.request(64,0)
                            if active.get('runtime_state')=='active': break
                            await asyncio.sleep(.1)
                        if active.get('runtime_state')!='active' or active.get('sensor_health') not in (None,'healthy'):
                            raise RuntimeError('IMU failed active/healthy preflight')
                        def notification(_,data):
                            try:
                                sample=parse_motion(data)
                                if sample.protocol_version!=status.protocol_version: raise ValueError('Protocol changed')
                                samples.append(sample)
                                emit({'record_type':'tag_motion',**sample.to_dict()})
                                if detector.feed(sample): triggers.append(sample.sequence)
                            except ValueError as exc: errors.append(str(exc))
                        await client.start_notify(MOTION_CHARACTERISTIC_UUID,notification)
                        await asyncio.sleep(duration)
                        await client.stop_notify(MOTION_CHARACTERISTIC_UUID)
                        end=await smp.request(64,0)
                        check_ble_identity(identity,end)
                        if end.get('boot_id')!=before.get('boot_id'): errors.append('Boot changed')
                    finally:
                        ack=await smp.request(64,{'auto':20,'research':21,'idle':22}[policy],write=True)
                        if ack.get('accepted') is not True: raise RuntimeError('Restore rejected')
                        restored=await smp.request(64,0)
                        result['power_after']=restored.get('power_policy')
                        emit({'record_type':'restored','status':restored})
                        if result['power_after']!=policy: raise RuntimeError('Original power policy not restored')
            span=(samples[-1].source_monotonic_us-samples[0].source_monotonic_us)/1e6 if len(samples)>1 else 0
            gaps=sum(b.sequence!=a.sequence+1 for a,b in zip(samples,samples[1:]))
            invalid=sum(not s.bmi270_valid or bool(s.sensor_error_bits) for s in samples)
            result.update(samples=len(samples),sequence_discontinuities=gaps,invalid_samples=invalid,
                measured_hz=(len(samples)-1)/span if span>0 else None,experimental_triggers=triggers,errors=errors)
            result['passed']=len(samples)>1 and span>0 and not gaps and not invalid and not errors
        except Exception as exc: result['error']=str(exc) or type(exc).__name__
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device-id',required=True)
    p.add_argument('--address')
    p.add_argument('--duration',type=float,default=20)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    if not 1<=args.duration<=60: p.error('duration must be 1–60 seconds')
    result=asyncio.run(check(args.device_id.lower(),args.address,args.duration,args.output))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
