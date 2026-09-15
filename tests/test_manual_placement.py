import unittest
from unittest.mock import patch
from putttrack.tag.recognition import Recognition
from test_nfc_recognition import tag, ID

class ManualPlacementTests(unittest.TestCase):
 def test_no_nfc_timeout_and_late_success_stays_timeout(self):
  with patch('putttrack.tag.recognition.time.monotonic',return_value=100) as c:
   r=Recognition();r.manual_action('start','a');c.return_value=110.1
   r.observe(tag());r.update(r.generation,'complete')
   m=r.snapshot()['manual_placement'];self.assertEqual(m['current']['outcome'],'timeout');self.assertEqual(m['resolved'],1);self.assertEqual(m['success'],0)
 def test_fresh_success_latched_and_duplicate_start_idempotent(self):
  with patch('putttrack.tag.recognition.time.monotonic',return_value=100) as c:
   r=Recognition();r.manual_action('start','a');r.manual_action('start','a')
   c.return_value=100.4;r.observe(tag());c.return_value=101.6;r.update(r.generation,'complete')
   c.return_value=110;r.snapshot();r.observe({'event':'disconnected'})
   m=r.snapshot()['manual_placement'];self.assertEqual(len(m['trials']),1);self.assertEqual(m['current']['outcome'],'success');self.assertEqual(m['current']['nfc_ms'],400);self.assertEqual(m['within_2s'],1)
   self.assertEqual(m['within_5s'],1)
 def test_old_result_wrong_ball_and_cancellation(self):
  with patch('putttrack.tag.recognition.time.monotonic',return_value=100) as c:
   r=Recognition();r.observe(tag());g=r.generation;r.update(g,'complete',address='test')
   with self.assertRaises(ValueError):r.manual_action('start','a')
   c.return_value=104;r.manual_action('start','a');self.assertFalse(r.update(g,'complete'))
   r.observe(tag('0123456789abcdef'));self.assertEqual(r.snapshot()['manual_placement']['current']['outcome'],'failure')
   c.return_value=108;r.manual_action('start','b');r.manual_action('cancel','c')
   m=r.snapshot()['manual_placement'];self.assertEqual(m['resolved'],1);self.assertEqual(m['cancelled'],1)
 def test_reader_failure_and_game_guard(self):
  with patch('putttrack.tag.recognition.time.monotonic',return_value=100):
   r=Recognition();r.pinned_identity=ID
   with self.assertRaises(ValueError):r.manual_action('start','a')
   r.pinned_identity=None;r.manual_action('start','a');r.observe({'event':'boot'})
   self.assertEqual(r.snapshot()['manual_placement']['current']['outcome'],'failure')
