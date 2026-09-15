"""Exercise real session orchestration with a fake BLE peripheral, no radio."""
import asyncio
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from putttrack.tag.recognition import Recognition, identify
from putttrack.tag.telemetry import MOTION_CHARACTERISTIC_UUID

ID='f383571202836e6f'


class BenchBleSessionTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, version=1, lost_ack=False):
        state=Recognition()
        state.observe({'event':'nfc_tag','ndef_ok':True,'service_uri_ok':True,'device_id':ID,
            'ndef_uri':f'putttrack://service/tag/{ID}?fw=0.1.18','firmware_version':'0.1.18'})
        state.pinned_identity=ID
        state.last_verified={'device_id':ID,'address':'cached-peripheral'}
        received=[]
        state.motion_callback=lambda *args: received.append(args)
        state.motion_disconnect=MagicMock()
        client=MagicMock(is_connected=True)
        client.connect=AsyncMock();client.disconnect=AsyncMock();client.read_gatt_char=AsyncMock(return_value=b'fake')
        callbacks={}
        async def notify(uuid, callback): callbacks[uuid]=callback
        client.start_notify=AsyncMock(side_effect=notify)
        class Peripheral:
            policy='auto'
            commands=[]
            restored=asyncio.Event()
            applied=asyncio.Event()
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def request(self,group,command,*,write=False):
                if write:
                    self.commands.append(command)
                    self.policy={20:'auto',21:'research',22:'idle'}[command]
                    if command==21:
                        self.applied.set()
                        if lost_ack: raise TimeoutError('lost ack')
                    if command==20: self.restored.set()
                    return {'accepted':True}
                return {'device_id':ID,'ble_security_level':2,'boot_id':'boot',
                        'fw':'0.1.18','power_policy':self.policy}
        smp=Peripheral()
        status=SimpleNamespace(device_id=ID,boot_id='boot',protocol_version=version,
            sensor_layout={1:'adxl367-bmi270',2:'lsm6ds3tr-c-single'}[version])
        finder=AsyncMock(return_value=SimpleNamespace(address='cached-peripheral'))
        with patch('bleak.BleakClient',return_value=client),patch('putttrack.tag.ble_smp.BleSmp',return_value=smp),patch('putttrack.tag.ble_smp.find_tag_device',finder),patch('putttrack.tag.telemetry.parse_status',return_value=status):
            task=asyncio.create_task(identify(state,state.snapshot()))
            try:
                await asyncio.wait_for(smp.applied.wait(),1)
                if not lost_ack:
                    packet=struct.pack('<BBHIQ9iI',version,3,56,1,20000,*([0]*9),0)
                    callbacks[MOTION_CHARACTERISTIC_UUID](None,packet)
                    self.assertEqual(received[0][0],ID)
                    self.assertEqual(received[0][2].protocol_version,version)
                    wrong=bytearray(packet);wrong[0]=3-version
                    callbacks[MOTION_CHARACTERISTIC_UUID](None,wrong)
                    self.assertEqual(len(received),1)
                    state.pinned_identity=None
                await asyncio.wait_for(smp.restored.wait(),1)
                await asyncio.sleep(.01)
            finally:
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
        self.assertEqual(smp.commands,[21,20])
        self.assertFalse(state.power_restore)
        client.disconnect.assert_awaited()
        finder.assert_awaited_with(ID,address='cached-peripheral',timeout=10)

    async def test_tag_stream_and_restore(self): await self.exercise(1)
    async def test_xiao_stream_and_restore(self): await self.exercise(2)
    async def test_power_applied_but_ack_lost_still_restores(self): await self.exercise(lost_ack=True)
