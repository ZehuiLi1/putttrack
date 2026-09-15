import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from putttrack.venue.bench_stroke import BenchStrokeDetector, LegacyStrokeDetector

class XiaoStrokeTests(unittest.TestCase):
 def setUp(self):
  self.d=BenchStrokeDetector('lsm6ds3tr-c-single');self.seq=0;self.hits=[]
 def send(self,n,a=9.80665,g=0,valid=True):
  for _ in range(n):
   self.seq+=1
   s=SimpleNamespace(sequence=self.seq,source_monotonic_us=self.seq*20000,
    sensor_layout='lsm6ds3tr-c-single',bmi270_valid=valid,sensor_error_bits=0,
    bmi270_accel_micro_ms2=(0,0,a*1e6),bmi270_gyro_micro_rads=(0,0,g*1e6))
   if self.d.feed(s):self.hits.append(self.seq)
 def test_six_labelled_strokes_replay(self):
  data=json.loads((Path(__file__).parent/'fixtures/xiao_six_strokes.json').read_text());hits=[];legacy=LegacyStrokeDetector();old=[]
  for seq,t,*axes in data['rows']:
   s=SimpleNamespace(sequence=seq,source_monotonic_us=t,sensor_layout='lsm6ds3tr-c-single',bmi270_valid=True,sensor_error_bits=0,bmi270_accel_micro_ms2=axes[:3],bmi270_gyro_micro_rads=axes[3:])
   if self.d.feed(s):hits.append(t)
   if legacy.feed(s):old.append(t)
  self.assertEqual(len(old),3);self.assertEqual(len(hits),6)
  origin=data['rows'][0][1]
  for t,onset in zip(hits,[3.08,6.48,10.86,14.22,17.70,19.56]):
   self.assertTrue(onset <= (t-origin)/1e6 <= onset+.7)
 def test_brief_dip_but_sustained_low_acceleration_rejected(self):
  self.send(40);self.send(1,20,4);self.send(3,10,4);self.send(2,1,4);self.send(8,10,4)
  self.assertEqual(len(self.hits),1)
  self.setUp();self.send(40);self.send(1,20,4);self.send(6,1,4);self.send(30,10,4)
  self.assertFalse(self.hits)
 def test_gentle_handling_sustained_wobble_and_bump_without_motion(self):
  self.send(40);self.send(8,10,1.5);self.send(1,25,5);self.send(30,10,5)
  self.assertFalse(self.hits)
  self.setUp();self.send(40);self.send(20,10,.7);self.send(1,25,5);self.send(30,10,5)
  self.assertFalse(self.hits)
  self.setUp();self.send(40);self.send(1,25,0);self.send(50)
  self.assertFalse(self.hits)
 def test_continuous_collision_and_short_rest_cannot_bypass_cooldown(self):
  self.send(40);self.send(1,25,4);self.send(10,10,4);self.assertEqual(len(self.hits),1)
  self.send(10);self.send(1,25,4);self.send(100,20,5)
  self.assertEqual(len(self.hits),1)
 def test_gap_invalid_data_reset_and_profile_isolation(self):
  self.send(40);self.seq+=2;self.send(1,25,4);self.send(20,10,4);self.assertFalse(self.hits)
  self.send(40);self.send(1,valid=False);self.send(1,25,4);self.send(20,10,4);self.assertFalse(self.hits)
  self.assertEqual(BenchStrokeDetector('adxl367-bmi270').VERSION,'bench-stroke-v0-unvalidated')
