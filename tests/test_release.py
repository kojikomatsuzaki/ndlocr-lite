"""Release取得から既存のZIP検査まで、外部通信なしで境界条件を確認する。"""
import argparse
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from PIL import Image
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from download_release import download, SafeRedirect
from run_ocr import execute
from prepare_input import prepare_images

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / 'release'
        self.settings = yaml.safe_load((ROOT / 'config/default.yaml').read_text())['input']
        image = io.BytesIO()
        Image.new('RGB', (30, 20), 'white').save(image, 'PNG')
        self.image = image.getvalue()
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as bundle:
            bundle.writestr('資料/画像 01.PNG', self.image)
        self.payload = stream.getvalue()
        self.release = {'id': 123, 'html_url': 'https://github.com/owner/repo/releases/tag/data'}
        self.asset = {'id': 456, 'name': '資料.zip', 'size': len(self.payload), 'updated_at': '2026-10-18T00:00:00Z'}

    def fetch(self, **kwargs):
        return download('owner/repo', kwargs.pop('tag', 'data/一'),
                        kwargs.pop('name', '資料.zip'), self.target,
                        kwargs.pop('limit', 100000), 'test-token', **kwargs)

    def report(self):
        return json.loads((self.target / 'release-input.json').read_text())

    def test_download_hash_and_existing_image_validation(self):
        with patch('download_release.api_json', side_effect=[self.release, [self.asset]]) as api, patch(
                'download_release.request', return_value=io.BytesIO(self.payload)) as network:
            archive = self.fetch()
        self.assertIn('data%2F%E4%B8%80', api.call_args_list[0].args[0])
        self.assertEqual(network.call_args.args[0], 'https://api.github.com/repos/owner/repo/releases/assets/456')
        self.assertEqual(archive.read_bytes(), self.payload)
        self.assertEqual(self.report()['sha256'], hashlib.sha256(self.payload).hexdigest())
        staging = self.root / 'staging'
        staging.mkdir()
        images = prepare_images(archive, staging, self.settings)
        self.assertEqual(images[0]['input_file'], '資料/画像 01.PNG')
        self.assertEqual(images[0]['sha256'], hashlib.sha256(self.image).hexdigest())

    def test_download_to_ocr_metadata_and_raw_outputs(self):
        with patch('download_release.api_json', side_effect=[self.release, [self.asset]]), patch(
                'download_release.request', return_value=io.BytesIO(self.payload)):
            self.fetch()
        engine = self.root / 'engine'
        (engine / 'src').mkdir(parents=True)
        (engine / 'src/ocr.py').write_text("""
import argparse, json
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--sourceimg'); parser.add_argument('--output')
a, _ = parser.parse_known_args()
stem = Path(a.sourceimg).stem; out = Path(a.output)
(out / (stem + '.txt')).write_text('舊字體', encoding='utf-8')
(out / (stem + '.json')).write_text(json.dumps({'contents': [], 'imginfo': {}}))
(out / (stem + '.xml')).write_text('<OCRDATASET />')
""", encoding='utf-8')
        args = argparse.Namespace(input='input.zip', input_root=self.target,
            output=self.root / 'results', engine_root=engine,
            config=ROOT / 'config/default.yaml', identifier=None, title=None, source=None)
        with patch('run_ocr.verify_engine', return_value={'test_double': True}):
            self.assertEqual(execute(args), 0)
        metadata = yaml.safe_load((args.output / 'metadata.yaml').read_text())
        self.assertEqual(metadata['processing']['input_archive']['sha256'], self.report()['sha256'])
        self.assertEqual(metadata['images'][0]['sha256'], hashlib.sha256(self.image).hexdigest())
        self.assertEqual((args.output / 'raw/資料/画像 01.PNG/画像 01.txt').read_text(), '舊字體')
        self.assertEqual(metadata, json.loads((args.output / 'metadata.json').read_text()))

    def test_duplicate_asset_rejected(self):
        with patch('download_release.api_json', side_effect=[self.release, [self.asset, self.asset]]), patch('download_release.request') as network:
            with self.assertRaises(ValueError):
                self.fetch()
        network.assert_not_called()

    def test_required_inputs_and_zip_suffix(self):
        for tag, name in [('', 'a.zip'), ('x', ''), ('x', 'a.jpg')]:
            with self.subTest(tag=tag, name=name), tempfile.TemporaryDirectory() as tmp, patch('download_release.api_json') as api:
                with self.assertRaises(ValueError):
                    download('owner/repo', tag, name, Path(tmp) / 'input', 100)
                api.assert_not_called()

    def test_missing_tag_and_asset_record_failure(self):
        with patch('download_release.api_json', side_effect=HTTPError('url', 404, 'missing', {}, None)):
            with self.assertRaises(HTTPError):
                self.fetch()
        self.assertEqual(self.report()['status'], 'failed')
        self.assertNotIn('test-token', (self.target / 'release-input.json').read_text())
        self.target.rename(self.root / 'failed')
        with patch('download_release.api_json', side_effect=[self.release, []]):
            with self.assertRaises(ValueError):
                self.fetch()
        self.assertEqual(self.report()['error_type'], 'ValueError')

    def test_asset_pagination(self):
        others = [{**self.asset, 'name': 'other.zip'}] * 100
        with patch('download_release.api_json', side_effect=[self.release, others, [self.asset]]) as api, patch(
                'download_release.request', return_value=io.BytesIO(self.payload)):
            self.fetch()
        self.assertIn('page=2', api.call_args.args[0])

    def test_declared_download_limit(self):
        with patch('download_release.api_json', side_effect=[self.release, [self.asset]]), patch('download_release.request') as network:
            with self.assertRaises(ValueError):
                self.fetch(limit=10)
        network.assert_not_called()
        self.assertFalse((self.target / 'input.zip').exists())

    def test_actual_download_size_and_truncation(self):
        for payload in [self.payload + b'x', self.payload[:-1]]:
            with self.subTest(length=len(payload)), tempfile.TemporaryDirectory() as tmp, patch(
                    'download_release.api_json', side_effect=[self.release, [self.asset]]), patch(
                    'download_release.request', return_value=io.BytesIO(payload)):
                directory = Path(tmp) / 'input'
                with self.assertRaises(ValueError):
                    download('owner/repo', 'data', '資料.zip', directory, 100000)
                self.assertFalse((directory / 'input.zip').exists())
                self.assertEqual(json.loads((directory / 'release-input.json').read_text())['status'], 'failed')

    def test_release_zip_uses_existing_security_checks(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as bundle:
            bundle.writestr('../escape.png', self.image)
        payload = stream.getvalue()
        with patch('download_release.api_json', side_effect=[self.release, [{**self.asset, 'size': len(payload)}]]), patch(
                'download_release.request', return_value=io.BytesIO(payload)):
            archive = self.fetch()
        staging = self.root / 'staging'
        staging.mkdir()
        with self.assertRaises(ValueError):
            prepare_images(archive, staging, self.settings)
        self.assertFalse((self.root / 'escape.png').exists())

    def test_redirect_strips_credentials_and_rejects_http(self):
        req = Request('https://api.github.com/asset', headers={'Authorization': 'Bearer secret'})
        redirected = SafeRedirect().redirect_request(req, None, 302, 'Found', {}, 'https://release-assets.githubusercontent.com/file')
        self.assertFalse(redirected.has_header('Authorization'))
        same_host = SafeRedirect().redirect_request(req, None, 302, 'Found', {}, 'https://api.github.com/next')
        self.assertTrue(same_host.has_header('Authorization'))
        with self.assertRaises(ValueError):
            SafeRedirect().redirect_request(req, None, 302, 'Found', {}, 'http://example.com/file')


if __name__ == '__main__':
    unittest.main()
