import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import numpy as np
from app.server import create_app, CHUNK
from app.records import new_register, validate_register, bitrate_for_limit, save
from app.payload import encode, assess_frames

PASSWORD = 'neutral-fixture-password-123'
HEADERS = {'X-Watermark-Request': '1'}


def register():
    return new_register('ab' * 32, 3, 'Test', dict(width=1280, height=720, fps='24'))


class PayloadTests(unittest.TestCase):
    def test_fresh_keys_and_unique_copies(self):
        a, b = register(), register()
        self.assertNotEqual(a['key_hex'], b['key_hex'])
        self.assertEqual(len(set(a['copy_tokens'].values())), 3)

    def test_authenticated_recovery_wrong_key_and_disagreement(self):
        s = register()
        tokens = list(s['copy_tokens'].values())
        def logits(token):
            return np.tile(encode(token, bytes.fromhex(s['key_hex']), s['source_sha256']).astype(float) * 2 - 1, (30, 1))
        a, b = logits(tokens[0]), logits(tokens[1])
        args = [bytes.fromhex(s['key_hex']), s['source_sha256'], set(tokens)]
        self.assertEqual(assess_frames(a, *args)['status'], 'registered_copy_recovered')
        self.assertEqual(assess_frames(a, b'x' * 32, *args[1:])['status'], 'inconclusive')
        self.assertEqual(assess_frames(np.concatenate([a, b]), *args)['status'], 'inconclusive')
        self.assertEqual(assess_frames(a[:12], *args)['status'], 'inconclusive')

    def test_bad_registers(self):
        for patch in [dict(key_hex='xx'), dict(checkpoint_sha256='00' * 32), dict(copy_tokens={'../escape': '12345678'}),
                      dict(copy_tokens={'A':'12345678', 'B':'12345678'})]:
            with self.assertRaises(ValueError):
                validate_register({**register(), **patch})

    def test_legacy_register_accepted_without_reissuing(self):
        state = register()
        state['schema'] = 'film-issued-copies-v1'
        self.assertEqual(validate_register(state)['copy_tokens'], state['copy_tokens'])

    def test_size_budget(self):
        self.assertLess(bitrate_for_limit(1.5, 1050, True) * 1050 / 8, 1.5e9)
        with self.assertRaises(ValueError):
            bitrate_for_limit(.01, 3600, True)
        with self.assertRaises(ValueError):
            bitrate_for_limit(float('nan'), 100, True)


class SetupTests(unittest.TestCase):
    def test_default_login_and_custom_override(self):
        for environment_value in (None, '', PASSWORD):
            with self.subTest(APP_PASSWORD=environment_value), tempfile.TemporaryDirectory() as directory:
                with patch.dict(os.environ):
                    if environment_value is None:
                        os.environ.pop('APP_PASSWORD', None)
                    else:
                        os.environ['APP_PASSWORD'] = environment_value
                    with TestClient(create_app(directory, launch=False), base_url='https://testserver') as client:
                        self.assertEqual(client.get('/api/state').status_code, 401)
                        self.assertIn('Default password:', client.get('/').text)
                        rejected = 'password' if environment_value else 'incorrect'
                        self.assertEqual(client.post('/api/login', headers=HEADERS,
                            json={'password': rejected}).status_code, 401)
                        self.assertEqual(client.post('/api/login', headers=HEADERS,
                            json={'password': environment_value or 'password'}).status_code, 200)
                        self.assertEqual(client.get('/api/state').status_code, 200)


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.client = TestClient(create_app(self.root, PASSWORD, launch=False), base_url='https://testserver')
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def login(self):
        r = self.client.post('/api/login', json={'password': PASSWORD}, headers=HEADERS)
        self.assertEqual(r.status_code, 200)

    def upload(self, content=b'neutral movie bytes', kind='video'):
        name = 'movie.mp4' if kind == 'video' else 'recovery.json'
        r = self.client.post('/api/uploads', headers=HEADERS, json=dict(name=name, size=len(content), kind=kind))
        self.assertEqual(r.status_code, 200, r.text)
        ident = r.json()['id']
        self.assertEqual(self.client.put(f'/api/uploads/{ident}/chunks', content=content,
            headers={**HEADERS, 'X-Upload-Offset':'0'}).status_code, 200)
        r = self.client.post(f'/api/uploads/{ident}/finish', headers=HEADERS)
        self.assertEqual(r.status_code, 200, r.text)
        return ident

    def test_password_and_csrf_required(self):
        self.assertEqual(self.client.get('/api/state').status_code, 401)
        self.assertEqual(self.client.post('/api/login', json={'password':PASSWORD}).status_code, 403)
        self.assertEqual(self.client.post('/api/login', headers=HEADERS, json={'password':'wrong'}).status_code, 401)
        self.login()
        self.assertEqual(self.client.get('/api/state').status_code, 200)
        self.client.post('/api/logout', headers=HEADERS)
        self.assertEqual(self.client.get('/api/state').status_code, 401)

    def test_login_size_limit(self):
        r = self.client.post('/api/login', content=b'x' * 9000, headers=HEADERS)
        self.assertEqual(r.status_code, 413)

    def test_resumable_upload_and_atomic_rejection(self):
        self.login()
        ident = self.client.post('/api/uploads', headers=HEADERS, json=dict(name='test.mp4', size=12, kind='video')).json()['id']
        url = f'/api/uploads/{ident}/chunks'
        self.assertEqual(self.client.put(url, content=b'first-', headers={**HEADERS, 'X-Upload-Offset':'0'}).status_code, 200)
        self.assertEqual(self.client.put(url, content=b'oops', headers={**HEADERS, 'X-Upload-Offset':'0'}).status_code, 409)
        self.assertEqual(self.client.post(f'/api/uploads/{ident}/finish', headers=HEADERS).status_code, 400)
        self.assertEqual(self.client.put(url, content=b'way-too-long', headers={**HEADERS, 'X-Upload-Offset':'6'}).status_code, 413)
        self.assertEqual(self.client.get(f'/api/uploads/{ident}').json()['offset'], 6)
        self.client.put(url, content=b'second', headers={**HEADERS, 'X-Upload-Offset':'6'})
        self.assertEqual(self.client.post(f'/api/uploads/{ident}/finish', headers=HEADERS).status_code, 200)
        self.assertEqual((self.root/'uploads'/ident/'content').read_bytes(), b'first-second')

    def test_no_secret_in_state_and_unreleased_download_denied(self):
        self.login()
        video = self.upload()
        recovery = register()
        key = self.upload(json.dumps(recovery).encode(), 'recovery')
        self.assertNotIn(recovery['key_hex'], self.client.get('/api/state').text)
        record = self.client.post('/api/jobs', headers=HEADERS, json=dict(kind='check', video=video, recovery=key)).json()
        ident = record['id']
        for name in ['request.json', 'status.json', 'PRIVATE-recovery.json', 'copy.pending.mp4']:
            self.assertEqual(self.client.get(f'/api/jobs/{ident}/files/{name}').status_code, 404)
        folder = self.root/'jobs'/ident
        (folder/'checked.mp4').write_bytes(b'checked')
        record['files'] = [dict(name='checked.mp4', label='Test', kind='video')]
        save(folder/'status.json', record)
        self.assertEqual(self.client.get(f'/api/jobs/{ident}/files/checked.mp4').content, b'checked')
        self.assertEqual(self.client.get('/api/uploads/../../server.py').status_code, 404)

    def test_reject_wrong_upload_kind_and_nonfinite_values(self):
        self.login()
        video = self.upload()
        r = self.client.post('/api/jobs', headers=HEADERS, json=dict(kind='check', video=video, recovery=video))
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/jobs', headers=HEADERS, json=dict(kind='create', video=video, copies=1.5))
        self.assertEqual(r.status_code, 422)

    def test_bad_recovery_and_external_playlist_rejected(self):
        self.login()
        r = self.client.post('/api/uploads', headers=HEADERS, json=dict(name='remote.m3u8', size=10, kind='video'))
        self.assertEqual(r.status_code, 400)
        ident = self.client.post('/api/uploads', headers=HEADERS, json=dict(name='key.json', size=2, kind='recovery')).json()['id']
        self.client.put(f'/api/uploads/{ident}/chunks', content=b'{}', headers={**HEADERS, 'X-Upload-Offset':'0'})
        self.assertEqual(self.client.post(f'/api/uploads/{ident}/finish', headers=HEADERS).status_code, 400)

    def test_restart_marks_job_interrupted_without_new_tokens(self):
        self.login()
        video = self.upload()
        ident = self.client.post('/api/jobs', headers=HEADERS, json=dict(kind='create', video=video)).json()['id']
        # Close the first instance before reusing the same data directory.
        self.client.__exit__(None, None, None)
        self.client = TestClient(create_app(self.root, PASSWORD, launch=False), base_url='https://testserver')
        self.client.__enter__()
        self.login()
        self.assertEqual(self.client.get('/api/state').json()['jobs'][0]['status'], 'interrupted')
        self.assertFalse((self.root/'jobs'/ident/'PRIVATE-recovery.json').exists())

    def test_batch_storage_preflight_checks_one_copy_before_creating_job(self):
        self.login()
        video = self.upload()
        with patch('app.storage.shutil.disk_usage', return_value=SimpleNamespace(free=4_999_999_999)):
            response = self.client.post('/api/jobs', headers=HEADERS,
                json=dict(kind='create', video=video, copies=50, max_gb=1.5))
            self.assertEqual(response.status_code, 400)
            self.assertIn('5.00 GB', response.json()['detail'])
            self.assertEqual(list((self.root/'jobs').iterdir()), [])
        with patch('app.storage.shutil.disk_usage', return_value=SimpleNamespace(free=5_000_000_000)):
            for copies in (50, 30, 20):
                response = self.client.post('/api/jobs', headers=HEADERS,
                    json=dict(kind='create', video=video, copies=copies, max_gb=1.5))
                self.assertEqual(response.status_code, 200, response.text)
            state = self.client.get('/api/state').json()
            self.assertEqual(state['storage']['free_bytes'], 5_000_000_000)

    def test_leak_check_does_not_reserve_batch_output_space(self):
        self.login()
        video = self.upload()
        recovery = self.upload(json.dumps(register()).encode(), 'recovery')
        with patch('app.storage.shutil.disk_usage', return_value=SimpleNamespace(free=1_000_000_000)):
            response = self.client.post('/api/jobs', headers=HEADERS,
                json=dict(kind='check', video=video, recovery=recovery))
            self.assertEqual(response.status_code, 200, response.text)

    def test_static_csp_and_no_directory_listing(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn("frame-ancestors 'none'", r.headers['content-security-policy'])
        self.assertEqual(self.client.get('/static/../app/server.py').status_code, 404)


if __name__ == '__main__':
    unittest.main()
