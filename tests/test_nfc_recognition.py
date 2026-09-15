import unittest
from unittest.mock import patch
from tools.run_nfc_status_web import Recognition
from putttrack.tag.recognition import check_ble_identity

ID='4d53cd7b5c288607'
def tag(identity=ID):
 return {'event':'nfc_tag','ndef_ok':True,'service_uri_ok':True,'device_id':identity,
         'ndef_uri':f'putttrack://service/tag/{identity}?fw=0.2.6','firmware_version':'0.2.6'}

class RecognitionTests(unittest.TestCase):
 def test_dedup_expiry_and_late_result(self):
  with patch('putttrack.tag.recognition.time.monotonic', return_value=1) as clock:
   s=Recognition();s.observe(tag()); g=s.snapshot()['generation']
   s.update(g,'scanning');s.observe(tag());self.assertEqual(s.snapshot()['generation'],g)
   self.assertEqual(s.snapshot()['attempts'],1)
   s.observe(tag('0123456789abcdef'))
   self.assertFalse(s.update(g,'complete'));self.assertNotEqual(s.snapshot()['stage'],'complete')
   clock.return_value=5;self.assertEqual(s.snapshot()['stage'],'waiting')
 def test_invalid_nfc_cannot_trigger_ble(self):
  s=Recognition();e=tag();e['device_id']='0123456789abcdef';s.observe(e)
  self.assertIsNone(s.snapshot()['device_id'])
 def test_ble_identity_and_security_required(self):
  for status in ({'device_id':'wrong','ble_security_level':2},{'device_id':ID,'ble_security_level':1}):
   with self.assertRaises(RuntimeError):check_ble_identity(ID,status)
 def test_system_off_and_wake_evidence(self):
  s=Recognition()
  with self.assertRaises(ValueError):s.request_system_off()
  s.observe(tag());g=s.snapshot()['generation'];s.update(g,'complete',boot_id='before')
  with self.assertRaises(ValueError):s.request_system_off()
  s.observe({'event':'tag_removed'});s.last_seen-=4;s.snapshot();s.request_system_off()
  with self.assertRaises(ValueError):s.request_system_off()
  s.off_request=False;s.off_result={'stage':'command_accepted','device_id':ID,'boot_id_before':'before'}
  s.observe(tag());g=s.snapshot()['generation'];s.update(g,'complete',boot_id='before',nfc_system_off_wake=True)
  self.assertEqual(s.snapshot()['system_off']['stage'],'command_accepted')
  s.update(g,'complete',boot_id='after',nfc_system_off_wake=False,reset_cause=32)
  self.assertEqual(s.snapshot()['system_off']['stage'],'wake_unverified')
  self.assertIn('调试接口',s.snapshot()['system_off']['message'])
  s.off_result={'stage':'command_accepted','device_id':ID,'boot_id_before':'before'}
  s.update(g,'complete',boot_id='after',nfc_system_off_wake=True)
  self.assertEqual(s.snapshot()['system_off']['stage'],'wake_verified')

class SystemOffTests(unittest.IsolatedAsyncioTestCase):
 async def exercise(self, field_present):
  from unittest.mock import AsyncMock, MagicMock
  from putttrack.tag.recognition import send_system_off
  s=Recognition();s.last_verified={'device_id':ID,'address':'known'}
  client=MagicMock();client.__aenter__=AsyncMock(return_value=client);client.__aexit__=AsyncMock(return_value=False)
  smp=MagicMock();smp.__aenter__=AsyncMock(return_value=smp);smp.__aexit__=AsyncMock(return_value=False)
  smp.request=AsyncMock(side_effect=[{'device_id':ID,'ble_security_level':2,
      'system_off_supported':True,'nfc_enabled':True,'nfc_setup_error':0,
      'nfc_field_present':field_present,'boot_id':'before'}, {'accepted':True}])
  with patch('bleak.BleakClient',return_value=client), patch('putttrack.tag.ble_smp.find_tag_device',new=AsyncMock(return_value=object())), patch('putttrack.tag.ble_smp.BleSmp',return_value=smp):
   await send_system_off(s)
  return s,smp
 async def test_field_present_never_sends_sleep(self):
  s,smp=await self.exercise(True)
  self.assertEqual(s.off_result['stage'],'error')
  self.assertEqual(smp.request.await_count,1)
 async def test_ack_is_not_wake_proof(self):
  s,smp=await self.exercise(False)
  self.assertEqual(s.off_result['stage'],'command_accepted')
  smp.request.assert_awaited_with(64,23,write=True)

class PlacementTests(unittest.TestCase):
 def test_short_dropout_keeps_placement_and_stale_result_cannot_finish_next(self):
  with patch('putttrack.tag.recognition.time.monotonic',return_value=10) as clock:
   s=Recognition();s.observe(tag());g=s.snapshot()['generation']
   s.observe({'event':'scan_miss'});s.observe({'event':'tag_removed'})
   clock.return_value=12;s.observe(tag());self.assertEqual(s.snapshot()['generation'],g)
   self.assertEqual(s.snapshot()['summary']['placements'],1)
   clock.return_value=16;s.snapshot();s.observe(tag());g2=s.snapshot()['generation']
   self.assertFalse(s.update(g,'complete'))
   self.assertEqual(s.snapshot()['summary']['interrupted'],1)
   clock.return_value=17;s.update(g2,'complete');s.update(g2,'complete')
   snap=s.snapshot();self.assertEqual(snap['summary']['success'],1)
   self.assertEqual(snap['summary']['success_rate'],50)
   self.assertEqual(snap['summary']['mean_ms'],1000)
 def test_ble_drop_does_not_erase_initial_success(self):
  s=Recognition();s.observe(tag());g=s.snapshot()['generation']
  s.update(g,'scanning');s.update(g,'complete');s.update(g,'error',error='link lost')
  s.update(g,'scanning');s.update(g,'complete')
  snap=s.snapshot();self.assertEqual(snap['summary']['success'],1)
  self.assertEqual(snap['trials'][0]['ble_interruptions'],1)
  self.assertEqual(snap['trials'][0]['attempts'],2)
 def test_thousand_placements_with_injected_failures(self):
  with patch('putttrack.tag.recognition.time.monotonic',return_value=10) as clock:
   s=Recognition()
   for i in range(1000):
    clock.return_value=10+i*10;s.observe(tag());g=s.snapshot()['generation']
    if i%4==0:
     for _ in range(3):s.update(g,'scanning');s.update(g,'error',error='timeout')
    elif i%4!=1:
     clock.return_value+=1;s.update(g,'complete');s.update(g,'complete')
    clock.return_value+=4;s.snapshot()
   snap=s.snapshot();summary=snap['summary']
   self.assertEqual((summary['placements'],summary['success'],summary['failure'],summary['interrupted']), (1000,500,250,250))
   self.assertEqual(summary['success_rate'],50)
   self.assertEqual(len(snap['trials']),50)
   self.assertEqual((summary['mean_ms'],summary['max_ms']),(1000,1000))

class RecognitionWorkerTests(unittest.IsolatedAsyncioTestCase):
 async def test_one_task_per_placement_and_cancel_on_swap(self):
  import asyncio
  from putttrack.tag.recognition import run_recognition
  calls=[];cancelled=[]
  async def identify(s,target):
   calls.append(target['device_id']);s.update(target['generation'],'scanning')
   try:await asyncio.Event().wait()
   finally:cancelled.append(target['device_id'])
  s=Recognition();s.observe(tag());worker=asyncio.create_task(run_recognition(s,identify,poll_interval=.001))
  try:
   await asyncio.sleep(.02)
   for _ in range(100):s.observe(tag())
   await asyncio.sleep(.02);self.assertEqual(calls,[ID])
   s.observe(tag('0123456789abcdef'));await asyncio.sleep(.02)
   self.assertEqual(calls,[ID,'0123456789abcdef']);self.assertEqual(cancelled,[ID])
  finally:
   worker.cancel()
   with self.assertRaises(asyncio.CancelledError):await worker
 async def test_retries_bounded_without_new_placement(self):
  import asyncio
  from putttrack.tag.recognition import run_recognition
  async def fail(s,target):
   s.update(target['generation'],'scanning');s.update(target['generation'],'error',error='timeout')
  s=Recognition();s.observe(tag());worker=asyncio.create_task(run_recognition(s,fail,retry_delay=.001,poll_interval=.001))
  try:
   await asyncio.sleep(.05);self.assertEqual(s.snapshot()['attempts'],3)
   self.assertEqual(s.snapshot()['summary']['failure'],1)
  finally:
   worker.cancel()
   with self.assertRaises(asyncio.CancelledError):await worker

class WakeDataTests(unittest.TestCase):
 def test_cached_identity_is_only_a_connection_hint(self):
  import tempfile,json
  from pathlib import Path
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   (root/'nfc_last_verified.json').write_text(json.dumps({'device_id':ID,'address':'known'}))
   state=Recognition(root/'session.jsonl')
   self.assertEqual(state.last_verified['device_id'],ID)
   self.assertIsNone(state.snapshot()['device_id'])
   self.assertEqual(state.snapshot()['stage'],'waiting')
 def test_wake_stores_exchanged_status(self):
  s=Recognition();s.observe(tag());g=s.snapshot()['generation']
  s.off_result={'stage':'command_accepted','device_id':ID,'boot_id_before':'before'}
  status={'battery_voltage_mv':2873,'sensor_health':'healthy','ble_security_level':2}
  s.update(g,'complete',boot_id='after',nfc_system_off_wake=True,wake_status=status)
  self.assertEqual(s.off_result['stage'],'wake_verified')
  self.assertEqual(s.off_result['status_after'],status)
  self.assertGreaterEqual(s.off_result['recognition_ms'],0)
  self.assertIsNone(s.off_result['wake_to_ble_ms'])

class ErrorDescriptionTests(unittest.TestCase):
 def test_encryption_error_is_not_claimed_to_be_stale_bond(self):
  from putttrack.tag.recognition import describe_ble_error
  message=describe_ble_error('Insufficient Encryption',ID)
  self.assertIn('0x0F',message)
  self.assertNotIn('失效',message)
  message=describe_ble_error('Peer removed pairing information',ID)
  self.assertIn('4d53cd7b',message)
  self.assertNotIn('Tag-v0.1',message)

class DisconnectCauseTests(unittest.IsolatedAsyncioTestCase):
 async def test_intentional_cleanup_preserves_verification_error(self):
  from unittest.mock import AsyncMock, MagicMock
  from putttrack.tag.recognition import identify
  state=Recognition();state.observe(tag());generation=state.generation
  client=MagicMock();client.connect=AsyncMock()
  client.read_gatt_char=AsyncMock(side_effect=RuntimeError('Insufficient Encryption'))
  callback=None
  def make_client(*args,**kwargs):
   nonlocal callback
   callback=kwargs['disconnected_callback']
   return client
  async def disconnect():callback(client)
  client.disconnect=AsyncMock(side_effect=disconnect)
  with patch('bleak.BleakClient',side_effect=make_client), patch('putttrack.tag.ble_smp.find_tag_device',new=AsyncMock(return_value=object())):
   await identify(state,{'generation':generation,'device_id':ID})
  self.assertIn('0x0F',state.snapshot()['error'])
  self.assertNotIn('BLE 连接已断开',state.snapshot()['error'])
