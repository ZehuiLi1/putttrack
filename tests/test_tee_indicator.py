import unittest
from unittest.mock import patch
from putttrack.venue.tee_indicator import TeeIndicator

class TeeIndicatorTests(unittest.TestCase):
 def view(self, indicator, rec=None, read=None, ready=True, hole=None):
  return indicator.snapshot(ready=ready,recognition=rec or {},last_read=read or {},hole=hole or {})
 def test_green_requires_encrypted_complete(self):
  i=TeeIndicator()
  self.assertEqual(self.view(i)['mode'],'standby')
  self.assertNotEqual(self.view(i,{'stage':'nfc_identified'})['color'],'green')
  self.assertNotEqual(self.view(i,{'stage':'complete','security_level':1})['color'],'green')
  self.assertEqual(self.view(i,{'stage':'complete','security_level':2})['mode'],'ready')
 def test_timeout_success_and_disconnect(self):
  i=TeeIndicator()
  with patch('putttrack.venue.tee_indicator.time.monotonic',return_value=100) as c:
   self.assertEqual(self.view(i,read={'uid':'a','age_s':0})['effect'],'breathe')
   c.return_value=111;self.assertEqual(self.view(i,read={'uid':'a','age_s':0})['mode'],'retry')
   self.assertEqual(self.view(i,{'stage':'complete','security_level':2})['effect'],'steady')
   self.assertEqual(self.view(i,ready=False)['mode'],'offline')
 def test_manual_previous_success_not_live_green(self):
  i=TeeIndicator()
  v=self.view(i,{'stage':'waiting','manual_placement':{'current':{'outcome':'success'}}})
  self.assertEqual(v['mode'],'standby');self.assertFalse(v['hardware_connected'])
