#!/usr/bin/env python3
"""One physical shadow trial with full raw history and the MCU event journal.
No flashing, image-confirm, score changes or cheating penalties are performed.
"""

from __future__ import annotations
import argparse, fcntl, hashlib, json, math, os, pathlib, sys, tempfile, time
from dataclasses import asdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from putttrack.tag import (
    TagCaptureSession,
    status_from_smp,
    motion_from_smp,
    frozen_history_metadata_from_smp,
    frozen_history_from_smp,
)
from putttrack.tag.stroke_pickup_shadow import decode_snapshot, summarize_episode
import watch_ball_motion_demo as transport
from capture_tag_smp import select_armed_window, run_countdown


def config_hash():
    obj = json.loads(
        (ROOT / "configs/research/stroke_pickup_shadow_v1.json").read_text()
    )
    return hashlib.sha256(
        json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ble-address", required=True)
    p.add_argument("--expected-device-id", required=True)
    p.add_argument(
        "--address-type",
        choices=("public", "random", "public-identity", "random-identity"),
        default="random",
    )
    p.add_argument("--hci-port", default="/dev/cu.usbmodem101")
    p.add_argument("--nrfutil", type=pathlib.Path)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--request-retries", type=int, default=3)
    p.add_argument("--seconds", type=float, default=12.0)
    p.add_argument("--scenario", required=True)
    p.add_argument("--notes", default="")
    p.add_argument("--output-dir", required=True, type=pathlib.Path)
    p.add_argument(
        "--ball-on-surface",
        action="store_true",
        help="operator confirms ball placed/released before new bench trial",
    )
    return p


def main():
    args = parser().parse_args()
    if not args.ball_on_surface:
        raise SystemExit(
            "Place/release Ball and pass --ball-on-surface. This is not automatic ground inference."
        )
    if not math.isfinite(args.seconds) or not 4 <= args.seconds <= 12:
        raise SystemExit("--seconds must be 4..12")
    if args.timeout <= 0 or args.request_retries <= 0:
        raise SystemExit("timeouts/retries must be positive")
    try:
        valid_id = len(bytes.fromhex(args.expected_device_id)) == 8
    except ValueError:
        valid_id = False
    if not valid_id:
        raise SystemExit("full 8-byte expected device ID required")
    if not pathlib.Path(args.hci_port).exists():
        raise SystemExit("HCI port missing: " + args.hci_port)
    if not args.scenario.strip():
        raise SystemExit("scenario must not be empty")
    nrf = transport.find_nrfutil(args.nrfutil)
    sha = config_hash()
    lockname = hashlib.sha256(os.path.realpath(args.hci_port).encode()).hexdigest()[:16]
    lock = open(
        pathlib.Path(tempfile.gettempdir()) / f"putttrack-shadow-{lockname}.lock", "a"
    )
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("another shadow trial is using this HCI port")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    raw_path = args.output_dir / "raw.jsonl"
    raw = raw_path.open("x")

    def emit(record):
        raw.write(
            json.dumps({"host_received_ns": time.time_ns(), **record}, sort_keys=True)
            + "\n"
        )
        raw.flush()

    def save(name, record):
        with (args.output_dir / name).open("x") as f:
            json.dump(record, f, sort_keys=True, indent=2)
            f.write("\n")

    def req(command, operation=0):
        return transport.request(nrf, args, operation=operation, command_id=command)

    initial = None
    restore = False
    exit_code = 0
    try:
        initial = status_from_smp(req(0))
        transport.validate_identity(initial, args.expected_device_id)
        transport.validate_continuity(initial, initial, require_active=False)
        # Read-only probe rejects a wrong image/model before any power write.
        decode_snapshot(
            req(25),
            device_id=initial.device_id,
            boot_id=initial.boot_id,
            config_sha256=sha,
            require_active=False,
        )
        restore = True
        req(21, 2)
        active = transport.wait_for_policy(nrf, args, "research")
        transport.validate_continuity(initial, active)
        reset = req(26, 2)
        if (
            reset.get("accepted") is not True
            or reset.get("authority") is not False
            or type(reset.get("generation")) is not int
        ):
            raise RuntimeError("new trial acknowledgement invalid")
        generation = reset["generation"]
        save(
            "preflight.json",
            {
                "source_status": asdict(active),
                "new_trial": reset,
                "config_sha256": sha,
                "authority": False,
            },
        )
        session = TagCaptureSession(expected_device_id=initial.device_id)
        session.start(active)
        emit(
            {
                "record_type": "tag_status",
                **active.to_dict(),
                "episode_label": args.scenario,
                "episode_notes": args.notes,
            }
        )
        print("保持球已放下、松手静止；等待 GO。测试结束后不要拿球。", flush=True)
        run_countdown(3.0)
        before = decode_snapshot(
            req(25),
            device_id=initial.device_id,
            boot_id=initial.boot_id,
            config_sha256=sha,
            generation=generation,
        )
        if not before["armed"] or before["state"] != 1:
            raise RuntimeError("no qualified quiet baseline")
        marker = motion_from_smp(req(1))
        emit(
            {
                "record_type": "tag_episode_marker",
                "marker_kind": "action_start",
                "source_monotonic_us": marker.source_monotonic_us,
                "source_sequence": marker.sequence,
            }
        )
        print(
            f"\aGO：进行 {args.scenario}，窗口 {args.seconds:g} 秒。最后两秒保持不动。",
            flush=True,
        )
        time.sleep(args.seconds)
        print("正在冻结数据和读取球端事件；请勿移动球。", flush=True)
        meta = frozen_history_metadata_from_smp(req(3))
        snapshot = decode_snapshot(
            req(25),
            device_id=initial.device_id,
            boot_id=initial.boot_id,
            config_sha256=sha,
            generation=generation,
            previous_latest=before["latest_event_id"],
        )
        save("mcu-snapshot.json", snapshot)
        chunks = [req(4 + i) for i in range(meta.chunk_count)]
        batch = select_armed_window(
            frozen_history_from_smp(meta, chunks),
            action_marker=marker,
            pre_roll_seconds=3.0,
            episode_seconds=args.seconds,
        )
        emit({"record_type": "tag_frozen_history", **meta.to_dict()})
        for r in batch:
            emit({"record_type": "tag_motion", **r.to_dict()})
            session.observe_motion(r)
        final = status_from_smp(req(0))
        transport.validate_continuity(initial, final)
        if snapshot["sensor_recovery_generation"] != final.sensor_recovery_generation:
            raise RuntimeError("sensor recovery changed")
        emit({"record_type": "tag_status_final", **final.to_dict()})
        report = session.finalize(final)
        emit({"record_type": "tag_capture_result", **report.to_dict()})
        if not report.passed:
            raise RuntimeError("raw continuity failed")
        result = summarize_episode(
            snapshot,
            go_us=marker.source_monotonic_us,
            end_us=batch[-1].source_monotonic_us,
        )
        result.update(
            raw_capture="raw.jsonl",
            raw_capture_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            scenario=args.scenario,
            config_sha256=sha,
            device_id=initial.device_id,
            boot_id=initial.boot_id,
            generation=generation,
            physical_truth="NOT_REVIEWED",
            source_firmware=initial.firmware_version,
        )
        save("trial-result.json", result)
        print(
            json.dumps(
                {k: v for k, v in result.items() if k != "events"},
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        print(
            "这是候选杆数和拿起嫌疑，不是确认计分。原始数据、事件及哈希已保存。",
            flush=True,
        )
        if result["journal_loss"]:
            exit_code = 2
    except BaseException as exc:
        emit(
            {
                "record_type": "shadow_trial_failure",
                "error": str(exc),
                "authority": False,
            }
        )
        raise
    finally:
        raw.close()
        try:
            if restore and initial is not None:
                now = status_from_smp(req(0))
                transport.validate_identity(now, initial.device_id)
                req(20, 2)
                auto = transport.wait_for_policy(nrf, args, "auto")
                save(
                    "cleanup.json",
                    {
                        "power_policy": auto.power_policy,
                        "source_status": asdict(auto),
                        "authority": False,
                    },
                )
                print("已恢复 auto 功耗策略。", flush=True)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
