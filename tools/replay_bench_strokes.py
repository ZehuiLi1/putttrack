#!/usr/bin/env python3
"""Replay existing labelled captures against the unvalidated bench stroke rule.

Episode trigger counts are diagnostics, not validated stroke precision/recall:
labels do not provide exact impact timestamps. No thresholds are fitted here.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from putttrack.motion.dataset import read_capture
from putttrack.venue.bench_stroke import BenchStrokeDetector


def replay(paths):
    results=[]
    groups=defaultdict(lambda: {'episodes':0,'triggered_episodes':0,'triggers':0})
    for path in sorted(set(paths)):
        try:
            capture=read_capture(path)
            detector=BenchStrokeDetector()
            events=[sample.source_monotonic_us for sample in capture.records if detector.feed(sample)]
            label=','.join(capture.embedded_labels) or 'unlabelled'
            group=groups[label]
            group['episodes']+=1
            group['triggered_episodes']+=bool(events)
            group['triggers']+=len(events)
            results.append({'path':str(path),'label':label,'samples':len(capture.records),
                'device_id':(capture.first_status or {}).get('device_id'),
                'triggers_us':events, 'model':detector.VERSION})
        except (ValueError,KeyError,TypeError) as exc:
            results.append({'path':str(path),'excluded':str(exc)})
    return {'model':BenchStrokeDetector.VERSION,'authority':False,
        'note':'Episode trigger counts only; no event-level ground truth and no fitted thresholds.',
        'by_label':dict(groups),'episodes':results}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures',nargs='+',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=replay(args.captures)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['by_label'],ensure_ascii=False,indent=2))
