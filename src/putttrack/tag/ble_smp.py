"""Native BLE SMP transport (including macOS), with bounded frame reassembly.

Wire format: Zephyr services/device_mgmt/smp_protocol.html. Image upload uses
smp_groups/smp_group_1.html. The upload SHA hashes the file; image state uses the
MCUboot TLV hash instead. Callers must authenticate the device identity first.
"""
from __future__ import annotations

import asyncio
import hashlib
import struct
from typing import Any

import cbor2

SMP_CHARACTERISTIC_UUID = "da2e7828-fbce-4e01-ae9e-261174997c48"
HEADER = struct.Struct(">BBHHBB")


class BleSmp:
    def __init__(self, client: Any, *, timeout: float = 30) -> None:
        self.client = client
        self.timeout = timeout
        self.buffer = bytearray()
        self.replies: asyncio.Queue[bytes | Exception] = asyncio.Queue()
        self.sequence = 0
        self.lock = asyncio.Lock()

    def notification(self, _sender: Any, data: bytearray) -> None:
        self.buffer.extend(data)
        while len(self.buffer) >= HEADER.size:
            size = HEADER.size + int.from_bytes(self.buffer[2:4], "big")
            if size > 16384:
                self.buffer.clear()
                self.replies.put_nowait(ValueError("oversized SMP reply"))
                return
            if len(self.buffer) < size:
                return
            self.replies.put_nowait(bytes(self.buffer[:size]))
            del self.buffer[:size]

    async def __aenter__(self) -> BleSmp:
        await self.client.start_notify(SMP_CHARACTERISTIC_UUID, self.notification)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.client.is_connected:
            await self.client.stop_notify(SMP_CHARACTERISTIC_UUID)

    async def request(self, group: int, command: int, payload: dict | None = None,
                      *, write: bool = False) -> dict:
        async with self.lock:
            self.sequence = (self.sequence + 1) & 255
            body = cbor2.dumps({} if payload is None else payload)
            op = 2 if write else 0
            frame = HEADER.pack(op, 0, len(body), group, self.sequence, command) + body
            characteristic = self.client.services.get_characteristic(SMP_CHARACTERISTIC_UUID)
            size = characteristic.max_write_without_response_size
            for offset in range(0, len(frame), size):
                await self.client.write_gatt_char(characteristic, frame[offset:offset + size],
                                                  response=False)
            deadline = asyncio.get_running_loop().time() + self.timeout
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError
                reply = await asyncio.wait_for(self.replies.get(), remaining)
                if isinstance(reply, Exception):
                    raise reply
                response_op, flags, length, response_group, seq, cmd = HEADER.unpack(reply[:8])
                if seq != self.sequence:
                    # A response can arrive after its request timed out. Ignore
                    # that stale frame so a safe retry can use the same link.
                    continue
                if (response_op, flags, response_group, cmd) != (
                    op + 1, 0, group, command
                ):
                    raise ValueError("unexpected SMP reply header")
                break
            result = cbor2.loads(reply[8:])
            if not isinstance(result, dict):
                raise ValueError("SMP reply is not a map")
            if result.get("rc", 0) or result.get("err"):
                raise RuntimeError(f"SMP error: {result}")
            return result

    async def upload(self, data: bytes, *, progress: Any = None) -> dict:
        if not data:
            raise ValueError("empty OTA image")
        offset = 0
        resets = 0
        digest = hashlib.sha256(data).digest()
        while offset < len(data):
            payload = {"off": offset, "data": data[offset:offset + 1024]}
            if offset == 0:
                payload.update(len=len(data), sha=digest)
            for attempt in range(4):
                try:
                    reply = await self.request(1, 1, payload, write=True)
                    break
                except TimeoutError:
                    if attempt == 3 or not self.client.is_connected:
                        raise
                    await asyncio.sleep(0.25 * (attempt + 1))
            new_offset = reply.get("off")
            if type(new_offset) is not int or not 0 <= new_offset <= len(data):
                raise ValueError("invalid image upload offset")
            if new_offset <= offset:
                resets += 1
                if resets > 3:
                    raise RuntimeError("image upload stopped making progress")
            offset = new_offset
            if progress:
                progress(offset, len(data))
            if reply.get("match") is False:
                raise RuntimeError("uploaded image hash mismatch")
        return await self.request(1, 0)


async def find_tag_device(
    identity: str, *, address: str | None = None, timeout: float = 30
) -> Any:
    """Resolve an advertisement or an already-known macOS peripheral.

    macOS may retain a paired link after a client exits; that peripheral no
    longer advertises. CoreBluetooth's identifier lookup can reuse the link.
    The caller still MUST check the full ID from the encrypted status record.
    """
    import sys
    from bleak import BleakScanner

    if address and sys.platform == "darwin":
        from Foundation import NSUUID
        from bleak.backends.corebluetooth.CentralManagerDelegate import CentralManagerDelegate
        from bleak.backends.device import BLEDevice

        manager = CentralManagerDelegate()
        await manager.wait_until_ready()
        identifier = NSUUID.alloc().initWithUUIDString_(address)
        if identifier is None:
            raise ValueError("macOS address must be a peripheral UUID")
        peripherals = manager.central_manager.retrievePeripheralsWithIdentifiers_([identifier])
        if peripherals:
            peripheral = peripherals[0]
            return BLEDevice(address, peripheral.name(), (peripheral, manager))
    if address:
        return await BleakScanner.find_device_by_address(address, timeout=timeout)
    return await BleakScanner.find_device_by_filter(
        lambda d, a: (a.local_name or "") == f"PuttTrack-{identity[:8]}",
        timeout=timeout,
    )
