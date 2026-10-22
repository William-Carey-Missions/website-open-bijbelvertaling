"""Bound certificate network traffic without delaying cached valid identities."""
import concurrent.futures
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from collaboration_api import FirebaseTokenVerifier, Unauthorized


class CertificateCacheTests(unittest.TestCase):
    def response(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"known": "certificate"}'
        response.headers = {'Cache-Control': 'max-age=3600'}
        return response

    def test_random_keys_share_one_refresh_and_recover_after_cooldown(self):
        verifier = FirebaseTokenVerifier()
        with patch('collaboration_api.urllib.request.urlopen', return_value=self.response()) as fetch:
            for index in range(40):
                with self.assertRaises(Unauthorized):
                    verifier._certificate(f'unknown-{index}')
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(verifier._certificate('known'), 'certificate')
            verifier.next_refresh_at = time.monotonic() - 1
            response = self.response()
            response.read.return_value = b'{"rotated":"new certificate"}'
            fetch.return_value = response
            self.assertEqual(verifier._certificate('rotated'), 'new certificate')
            self.assertEqual(fetch.call_count, 2)

    def test_failed_refresh_is_throttled_and_expired_keys_fail_closed(self):
        verifier = FirebaseTokenVerifier()
        verifier.certificates = {'known': 'expired certificate'}
        with patch('collaboration_api.urllib.request.urlopen', side_effect=OSError('offline')) as fetch:
            with self.assertLogs('openvertaling.collaboration', level='ERROR'):
                for _ in range(10):
                    with self.assertRaises(Unauthorized):
                        verifier._certificate('known')
            self.assertEqual(fetch.call_count, 1)

    def test_cached_key_does_not_wait_for_unknown_key_refresh(self):
        verifier = FirebaseTokenVerifier()
        verifier.certificates = {'known': 'certificate'}
        verifier.expires_at = time.time() + 3600
        entered, release = threading.Event(), threading.Event()

        def slow_fetch(*args, **kwargs):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('test refresh timed out')
            return self.response()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            with patch('collaboration_api.urllib.request.urlopen', side_effect=slow_fetch) as fetch:
                attacker = executor.submit(verifier._certificate, 'unknown')
                self.assertTrue(entered.wait(1))
                try:
                    cached = executor.submit(verifier._certificate, 'known')
                    self.assertEqual(cached.result(timeout=0.5), 'certificate')
                    unknown = executor.submit(verifier._certificate, 'another')
                    with self.assertRaises(Unauthorized):
                        unknown.result(timeout=0.5)
                    self.assertEqual(fetch.call_count, 1)
                finally:
                    release.set()
                with self.assertRaises(Unauthorized):
                    attacker.result(timeout=1)

    def test_concurrent_cold_start_shares_refresh_for_valid_key(self):
        verifier = FirebaseTokenVerifier()
        entered, release = threading.Event(), threading.Event()

        def slow_fetch(*args, **kwargs):
            entered.set()
            release.wait(2)
            return self.response()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            with patch('collaboration_api.urllib.request.urlopen', side_effect=slow_fetch) as fetch:
                first = executor.submit(verifier._certificate, 'known')
                self.assertTrue(entered.wait(1))
                others = [executor.submit(verifier._certificate, 'known') for _ in range(6)]
                release.set()
                self.assertEqual(first.result(timeout=1), 'certificate')
                self.assertEqual([f.result(timeout=1) for f in others], ['certificate'] * 6)
                self.assertEqual(fetch.call_count, 1)


if __name__ == '__main__':
    unittest.main()
