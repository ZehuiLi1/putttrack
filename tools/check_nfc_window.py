#!/usr/bin/env python3
"""Read-only NFC observation for controlled hardware comparisons.

Keep the dashboard running. This does not send RF, sleep, pairing or game
commands. Only detected-target attempts enter the NDEF completion ratio; scans
that find no UID cannot be attributed to a particular ball.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import time
import urllib.request


def summarize(rows, identity, start, end):
    uids = set()
    for at, event in rows:
        if at <= end and event.get('device_id') == identity and event.get('ndef_ok') and event.get('uid'):
            uids.add(event['uid'])
    outcomes, errors = Counter(), Counter()
    success_times = []
    pending = None
    restarts = 0
    for at, event in rows:
        if not start <= at <= end:
            continue
        kind = event.get('event')
        if kind in ('boot', 'scan_miss', 'tag_removed', 'rf_cycle_failed'):
            pending = None
            restarts += kind == 'boot'
        elif kind == 'apdu_failure':
            pending = event
        elif kind == 'nfc_tag':
            if event.get('device_id') == identity or event.get('uid') in uids:
                ok = event.get('ndef_ok') is True and event.get('service_uri_ok') is True
                outcomes['success' if ok else event.get('ndef_error', 'invalid_identity')] += 1
                if ok:
                    success_times.append(at)
                elif pending:
                    errors[str(pending.get('diagnostic'))] += 1
            pending = None
    attempts = sum(outcomes.values())
    duration = end - start
    return {'device_id': identity, 'uid_candidates': sorted(uids),
            'duration_s': round(duration, 3), 'detected_target_attempts': attempts,
            'successful_ndef': outcomes['success'], 'ndef_outcomes': dict(outcomes),
            'ndef_completion_percent': 100 * outcomes['success'] / attempts if attempts else None,
            'complete_reads_per_second': outcomes['success'] / duration if duration > 0 else None,
            'apdu_error_codes': dict(errors), 'reader_restarts': restarts,
            'first_success_after_window_start_s': success_times[0] - start if success_times else None,
            'note': 'Completion ratio excludes no-UID scans. First success is measured from observation start, not RF-on or placement. No data is not a pass.'}


def read_rows(path):
    rows = []
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
            event = json.loads(row['raw'])
            if isinstance(event, dict):
                rows.append((datetime.fromisoformat(row['time']).timestamp(), event))
        except (ValueError, KeyError, TypeError):
            continue
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device-id', required=True)
    p.add_argument('--condition', required=True, help='Recorded label, e.g. tag_220pf_fixed_position')
    p.add_argument('--duration', type=int, default=60)
    p.add_argument('--url', default='http://127.0.0.1:8765')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not 5 <= args.duration <= 300:
        p.error('duration must be 5–300 seconds')
    def status():
        with urllib.request.urlopen(args.url + '/api/status', timeout=5) as response:
            return json.load(response)
    before = status()
    if not before.get('connected') or not before.get('ready'):
        raise RuntimeError('Reader is not ready')
    start = time.time()
    print(f'Observing {args.device_id}: {args.condition} for {args.duration}s', flush=True)
    for _ in range(args.duration):
        time.sleep(1)
    end = time.time()
    after = status()
    report = summarize(read_rows(Path(before['log_path'])), args.device_id.lower(), start, end)
    report.update(condition=args.condition, started_at=start, finished_at=end,
                  config=before.get('config'), log_path=before['log_path'],
                  reader_session_unchanged=before['log_path'] == after['log_path'],
                  reader_ready_at_end=after.get('connected') and after.get('ready'))
    report['valid_observation'] = (report['detected_target_attempts'] > 0 and not report['reader_restarts']
                                   and report['reader_session_unchanged'] and bool(report['reader_ready_at_end'])
                                   and before.get('config') == after.get('config'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['valid_observation'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
