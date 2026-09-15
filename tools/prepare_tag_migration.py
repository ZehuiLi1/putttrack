#!/usr/bin/env python3
"""Authorize a BLE-owner migration with one direct PN532 NFC command.

The NFC path proves physical proximity and clears the Tag's old bonds. The new
computer then establishes an encrypted BLE bond; firmware transfer remains on
signed MCUboot SMP over BLE.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import secrets
import sys
import time

import serial
from serial.tools import list_ports

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bleak import BleakClient
from putttrack.service.nfc import ServiceTouchError, parse_nfc_reader_event
from putttrack.tag.ble_smp import BleSmp, find_tag_device
from putttrack.tag.session import normalize_device_id
from putttrack.tag.recognition import check_ble_identity
from putttrack.tag.telemetry import STATUS_CHARACTERISTIC_UUID, parse_status


def find_reader_port(explicit: str | None) -> str:
    if explicit:
        return explicit
    candidates = [port.device for port in list_ports.comports() if port.vid == 0x303A]
    if len(candidates) != 1:
        raise RuntimeError("未找到唯一的 ESP32-C3 PN532 串口；请用 --port 指定")
    return candidates[0]


def read_event(connection: serial.Serial, deadline: float) -> dict:
    while time.monotonic() < deadline:
        raw = connection.readline()
        if not raw:
            continue
        try:
            event = json.loads(raw.decode(errors="replace"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(event, dict):
            continue
        if event.get("event") == "fatal":
            raise RuntimeError(f"PN532 故障：{event.get('message', 'unknown')}")
        return event
    raise TimeoutError("等待 PN532 事件超时")


def wait_for_expected_tag(
    connection: serial.Serial, device_id: str, deadline: float
) -> dict:
    while True:
        event = read_event(connection, deadline)
        if event.get("event") != "nfc_tag":
            continue
        if event.get("ndef_ok") is not True:
            # A partial RF transaction cannot authorize a write. Keep waiting
            # within the same bounded deadline for a complete identity.
            continue
        try:
            touch = parse_nfc_reader_event(event)
        except ServiceTouchError as exc:
            raise RuntimeError(f"NFC 身份无效：{exc}") from exc
        if touch.device_id != device_id:
            raise RuntimeError(
                f"读到其他小球 {touch.device_id}，目标是 {device_id}"
            )
        return event


def send_migration_command(
    connection: serial.Serial, device_id: str, nonce: str, deadline: float
) -> dict:
    command = f"nfc migrate {device_id} {nonce}\n".encode("ascii")
    connection.write(command)
    connection.flush()
    while True:
        event = read_event(connection, deadline)
        if event.get("event") != "nfc_migration_command":
            continue
        if event.get("device_id") != device_id or event.get("nonce") != nonce:
            continue
        if event.get("accepted") is not True:
            raise RuntimeError(
                f"PN532 未发送迁移命令：{event.get('reason', 'unknown')}"
            )
        return event


async def claim_over_ble(device_id: str, timeout: float) -> dict:
    device = await find_tag_device(device_id, timeout=timeout)
    if device is None:
        raise RuntimeError("NFC 迁移命令发送后未发现小球 BLE 广播")
    async with BleakClient(device, timeout=timeout) as client:
        status = parse_status(await client.read_gatt_char(STATUS_CHARACTERISTIC_UUID))
        if status.device_id != device_id:
            raise RuntimeError("BLE 设备身份与 NFC 身份不一致")
        async with BleSmp(client, timeout=timeout) as smp:
            result = await smp.request(64, 0)
    check_ble_identity(device_id, result)
    return result


def run(args: argparse.Namespace) -> dict:
    device_id = normalize_device_id(args.device_id)
    nonce = secrets.token_hex(16)
    port = find_reader_port(args.port)
    print(
        "此操作会清除小球内的全部旧 BLE 配对。完成后，新电脑将成为新的配对设备。",
        file=sys.stderr,
    )
    connection = serial.Serial(
        port=None,
        baudrate=115200,
        timeout=0.3,
        exclusive=True,
    )
    try:
        connection.dtr = False
        connection.rts = False
        connection.port = port
        connection.open()
        deadline = time.monotonic() + 45.0
        print("把目标小球放在 PN532 上并保持不动。", file=sys.stderr, flush=True)
        wait_for_expected_tag(connection, device_id, deadline)
        send_migration_command(
            connection, device_id, nonce, time.monotonic() + 10.0
        )
    finally:
        connection.close()

    if args.nfc_only:
        return {
            "status": "NFC_MIGRATION_COMMAND_SENT",
            "device_id": device_id,
            "reader_port": port,
            "nonce": nonce,
            "ble_claimed": False,
        }

    result = asyncio.run(claim_over_ble(device_id, args.ble_timeout))
    if result.get("nfc_migration_supported") is not True:
        raise RuntimeError("新配对已建立，但固件未报告 NFC 迁移能力")
    if result.get("nfc_migration_error") != 0:
        raise RuntimeError(
            f"小球报告配对迁移错误：{result.get('nfc_migration_error')}"
        )
    return {
        "status": "PASS",
        "device_id": device_id,
        "reader_port": port,
        "ble_claimed": True,
        "firmware_version": result.get("fw"),
        "security_level": result.get("ble_security_level"),
        "migration_count": result.get("nfc_migrations"),
        "migration_transport": result.get("nfc_migration_transport"),
        "status_after": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--port", help="ESP32-C3 PN532 串口；默认自动识别")
    parser.add_argument("--ble-timeout", type=float, default=45.0)
    parser.add_argument(
        "--nfc-only",
        action="store_true",
        help="只发送 NFC 迁移命令，不在本机建立新的 BLE 配对",
    )
    args = parser.parse_args()
    if args.ble_timeout <= 0:
        raise SystemExit("--ble-timeout 必须为正数")
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
