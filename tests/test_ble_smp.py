import asyncio
import unittest
from types import SimpleNamespace
import cbor2
from putttrack.tag.ble_smp import BleSmp, HEADER


class SmpTests(unittest.IsolatedAsyncioTestCase):
    async def test_fragmented_and_coalesced_notifications(self):
        smp = BleSmp(None)
        body = cbor2.dumps({'off': 1024})
        frame = HEADER.pack(3, 0, len(body), 1, 7, 1) + body
        smp.notification(None, frame[:3])
        self.assertTrue(smp.replies.empty())
        smp.notification(None, frame[3:] + frame)
        self.assertEqual(await smp.replies.get(), frame)
        self.assertEqual(await smp.replies.get(), frame)
        self.assertEqual(smp.buffer, b'')

    async def test_oversized_frame_rejected(self):
        smp = BleSmp(None)
        smp.notification(None, HEADER.pack(1, 0, 65535, 64, 1, 0))
        self.assertIsInstance(await smp.replies.get(), ValueError)

    async def test_upload_resume_and_restart_send_initial_metadata(self):
        smp = BleSmp(None)
        requests = []
        offsets = iter([1024, 0, 2048, 3000])
        async def request(group, command, payload=None, **kwargs):
            if command == 0:
                return {'images': []}
            requests.append(payload)
            return {'off': next(offsets)}
        smp.request = request
        await smp.upload(b'x' * 3000)
        self.assertEqual([r['off'] for r in requests], [0, 1024, 0, 2048])
        self.assertIn('sha', requests[2])
        self.assertNotIn('sha', requests[1])

    async def test_stuck_upload_is_bounded(self):
        smp = BleSmp(None)
        async def request(*args, **kwargs):
            return {'off': 0}
        smp.request = request
        with self.assertRaisesRegex(RuntimeError, 'progress'):
            await smp.upload(b'x')

    async def test_upload_retries_a_lost_response(self):
        smp = BleSmp(SimpleNamespace(is_connected=True))
        requests = []

        async def request(group, command, payload=None, **kwargs):
            if command == 0:
                return {'images': []}
            requests.append(payload)
            if len(requests) == 1:
                raise TimeoutError
            return {'off': len(payload['data'])}

        smp.request = request
        await smp.upload(b'x' * 100)
        self.assertEqual([item['off'] for item in requests], [0, 0])
