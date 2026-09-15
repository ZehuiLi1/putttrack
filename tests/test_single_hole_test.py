import tempfile
import unittest
from pathlib import Path
from putttrack.venue.single_hole_test import SingleHoleTest
from putttrack.tag.telemetry import MotionRecord
from putttrack.tag.recognition import Recognition


class SingleHoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = SingleHoleTest(Path(self.tmp.name)/'hole.jsonl')
        self.rec = {'stage':'complete','device_id':'1234567812345678'}
        self.seq = 0

    def start(self, mode='simulation'):
        self.h.start('测试',self.rec,mode,'start')
        return self.h.round_id

    def samples(self,n,a=9.80665,g=0,identity=None):
        for _ in range(n):
            self.seq += 1
            sample=MotionRecord(1,self.seq,self.seq*20000,True,True,(0,0,9806650),
                (0,0,int(a*1e6)),(0,0,int(g*1e6)),0)
            self.h.observe_motion(identity or self.rec['device_id'],'boot1',sample)

    def test_simulation_closed_loop_and_dedup(self):
        r=self.start()
        with self.assertRaises(ValueError): self.h.action('simulate-cup',r,'early')
        self.h.action('stroke',r,'s1')
        self.h.action('stroke',r,'s1')
        self.h.action('simulate-cup',r,'cup')
        self.h.action('simulate-cup',r,'cup')
        self.assertEqual(self.h.snapshot()['stage'],'complete')
        self.assertEqual(self.h.history[0]['strokes'],1)
        self.assertEqual(len(self.h.history),1)
        with self.assertRaises(ValueError): self.h.action('stroke','old','s2')

    def test_identity_required(self):
        with self.assertRaises(ValueError): self.h.start('a',{},'simulation','x')

    def test_imu_stroke_rest_and_refractory(self):
        self.start()
        self.samples(40)
        self.samples(1,20,3)
        self.samples(12,10,3)
        self.assertEqual(self.h.snapshot()['game']['player_hole_state']['player']['strokes'],1)
        self.samples(100,20,8)  # rolling collisions must not add strokes
        self.assertEqual(self.h.snapshot()['game']['player_hole_state']['player']['strokes'],1)
        self.samples(40)
        self.samples(1,20,3)
        self.samples(12,10,3)
        self.assertEqual(self.h.snapshot()['game']['player_hole_state']['player']['strokes'],2)

    def test_gentle_handling_wrong_identity_and_gap(self):
        self.start()
        self.samples(40,identity='other')
        self.samples(1,20,3)
        self.samples(12,10,3)
        self.assertEqual(self.h.snapshot()['stage'],'armed')
        self.samples(40)
        self.samples(1,10,1)
        self.samples(12,20,3)
        self.assertEqual(self.h.snapshot()['stage'],'armed')
        self.samples(40)
        self.seq+=5
        self.samples(1,20,3)
        self.samples(12,10,3)
        self.assertEqual(self.h.snapshot()['stage'],'armed')

    def cup(self,seq,blocked,round_id=None,healthy=True):
        self.h.observe_cup({'event':'cup_sensor','sequence':seq,'boot_id':'reader1',
            'blocked':blocked,'healthy':healthy,'round_id':round_id or self.h.round_id})

    def test_optical_round_token_baseline_and_single_completion(self):
        r=self.start('optical')
        commands=[]
        self.h.command=commands.append
        self.cup(1,False)
        self.h.action('stroke',r,'stroke')
        self.assertEqual(commands,[f'cup arm {r}'])
        self.cup(2,True,round_id='old')
        self.cup(3,True)
        self.assertEqual(self.h.snapshot()['stage'],'playing')
        self.cup(4,False)
        self.cup(5,True)
        self.cup(5,True)
        self.assertEqual(self.h.snapshot()['stage'],'complete')
        self.assertEqual(len(self.h.history),1)

    def test_fault_aborts_optical(self):
        r=self.start('optical')
        self.h.action('stroke',r,'stroke')
        self.cup(1,False)
        self.h.observe_cup({'event':'cup_fault'})
        self.cup(2,True)
        self.assertEqual(self.h.snapshot()['stage'],'cancelled')
        self.assertEqual(len(self.h.history),0)

    def test_pinned_ble_survives_nfc_absence(self):
        rec=Recognition()
        rec.identity=self.rec['device_id']
        rec.pinned_identity=rec.identity
        rec.last_seen=0
        self.assertEqual(rec.snapshot()['device_id'],rec.identity)
        self.assertTrue(rec.update(rec.generation,'complete'))
        with self.assertRaises(ValueError): rec.request_system_off()
        rec.pinned_identity=None
        self.assertIsNone(rec.snapshot()['device_id'])

    def test_history_survives_restart_and_truncated_tail(self):
        r=self.start()
        self.h.action('stroke',r,'s')
        self.h.action('simulate-cup',r,'c')
        with self.h.log_path.open('a') as f: f.write('{incomplete')
        restored=SingleHoleTest(Path(self.tmp.name)/'next.jsonl',[self.h.log_path])
        self.assertEqual(restored.snapshot()['stage'],'idle')
        self.assertEqual(restored.history[0]['round_id'],r)
        self.assertEqual(restored.history[0]['strokes'],1)

    def test_reader_restart_cancels_simulated_round_too(self):
        self.start()
        self.h.observe_cup({'event':'boot'})
        self.assertEqual(self.h.snapshot()['stage'],'cancelled')
