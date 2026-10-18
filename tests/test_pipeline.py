"""モデルを必要としない境界条件のテスト。実エンジン試験はActionsで別途行う。"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from generate_metadata import new_metadata, sha256_file, write_metadata
from prepare_input import prepare_images, resolve_input, extract_zip, validate_image
from run_ocr import execute, validate_outputs

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'input'
        self.source.mkdir()
        self.staging = self.root / 'staging'
        self.staging.mkdir()
        self.config = yaml.safe_load((PROJECT_ROOT / 'config/default.yaml').read_text())
        self.settings = self.config['input']

    def picture(self, name='画像 01.jpg', format='JPEG'):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (30, 20), 'white').save(path, format=format)
        return path

    def test_missing_input(self):
        with self.assertRaises(ValueError):
            resolve_input(self.root, 'missing')

    def test_empty_directory(self):
        with self.assertRaises(ValueError):
            prepare_images(self.source, self.staging, self.settings)

    def test_unsupported_and_disguised_images(self):
        for name, format in [('unsupported.gif', 'GIF'), ('disguised.jpg', 'PNG')]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_image(self.picture(name, format), self.settings)

    def test_corrupt_image(self):
        path = self.source / 'broken.jpg'
        path.write_bytes(b'not an image')
        with self.assertRaises(Exception):
            validate_image(path, self.settings)

    def test_filename_bytes_and_sha256_preserved(self):
        path = self.picture()
        original = path.read_bytes()
        records = prepare_images(self.source, self.staging, self.settings)
        self.assertEqual(records[0]['input_file'], path.name)
        self.assertEqual(records[0]['sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual((self.staging / 'images' / path.name).read_bytes(), original)
        self.assertEqual(path.read_bytes(), original)

    def test_file_and_pixel_limits(self):
        path = self.picture()
        for settings in ({**self.settings, 'max_file_bytes': 10},
                         {**self.settings, 'max_pixels': 10}):
            with self.assertRaises(ValueError):
                validate_image(path, settings)

    def test_symlink_and_traversal_rejected(self):
        (self.root / 'linked').symlink_to(self.source, target_is_directory=True)
        for name in ['linked', '../escape', '/absolute', 'input/../input', 'input\\a']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                resolve_input(self.root, name)

    def test_zip_preserves_filename_and_bytes(self):
        path = self.picture('nested/資料.jpg')
        archive = self.root / 'input.zip'
        with zipfile.ZipFile(archive, 'w') as bundle:
            bundle.write(path, 'nested/資料.jpg')
        records = prepare_images(archive, self.staging, self.settings)
        self.assertEqual(records[0]['input_file'], 'nested/資料.jpg')
        self.assertEqual(records[0]['sha256'], sha256_file(path))

    def test_zip_traversal_and_special_file_rejected(self):
        for filename in ['../escape.jpg', '/escape.jpg', 'C:/escape.jpg', 'a\\b.jpg']:
            with self.subTest(filename=filename):
                archive = self.root / 'bad.zip'
                with zipfile.ZipFile(archive, 'w') as bundle:
                    bundle.writestr(filename, b'x')
                with self.assertRaises(ValueError):
                    extract_zip(archive, self.staging, self.settings)
        archive = self.root / 'link.zip'
        with zipfile.ZipFile(archive, 'w') as bundle:
            entry = zipfile.ZipInfo('link.jpg')
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            bundle.writestr(entry, '/etc/passwd')
        with self.assertRaises(ValueError):
            extract_zip(archive, self.staging, self.settings)
        self.assertEqual(list(self.staging.iterdir()), [])

    def test_zip_expansion_limit_and_duplicate(self):
        archive = self.root / 'large.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr('large.jpg', b'x' * 10000)
        with self.assertRaises(ValueError):
            extract_zip(archive, self.staging, {**self.settings, 'max_compression_ratio': 2})
        with zipfile.ZipFile(archive, 'w') as bundle:
            bundle.writestr('A.jpg', b'x')
            bundle.writestr('a.jpg', b'x')
        with self.assertRaises(ValueError):
            extract_zip(archive, self.staging, self.settings)

    def test_metadata_yaml_is_canonical_and_utf8(self):
        metadata = new_metadata('787953', '太政官達', None)
        write_metadata(metadata, self.root)
        canonical = yaml.safe_load((self.root / 'metadata.yaml').read_text(encoding='utf-8'))
        derivative = json.loads((self.root / 'metadata.json').read_text(encoding='utf-8'))
        self.assertEqual(canonical, derivative)
        self.assertIsNone(canonical['bibliography']['source'])
        self.assertIn('太政官達', (self.root / 'metadata.yaml').read_text(encoding='utf-8'))

    def test_outputs_are_validated_without_correction(self):
        text = '舊字體\nけふ、讀ム。'
        (self.root / 'sample.txt').write_text(text, encoding='utf-8')
        (self.root / 'sample.json').write_text(
            json.dumps({'contents': [[{'text': text}]], 'imginfo': {}}, ensure_ascii=False),
            encoding='utf-8')
        (self.root / 'sample.xml').write_text('<OCRDATASET />', encoding='utf-8')
        self.assertEqual(len(validate_outputs(self.root, 'sample', self.root)), 3)
        self.assertEqual((self.root / 'sample.txt').read_text(encoding='utf-8'), text)
        (self.root / 'sample.txt').unlink()
        with self.assertRaises(ValueError):
            validate_outputs(self.root, 'sample', self.root)

    def test_batch_separates_same_stems_and_reports_partial_failure(self):
        self.picture('同名.jpg')
        self.picture('同名.png', 'PNG')
        engine = self.root / 'engine'
        (engine / 'src').mkdir(parents=True)
        # 実際に子プロセスを起動し、成功・異常終了時の処理記録を検証する。
        (engine / 'src/ocr.py').write_text('''
import argparse, json
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--sourceimg'); p.add_argument('--output')
a, _ = p.parse_known_args()
image = Path(a.sourceimg); output = Path(a.output)
if image.suffix == '.png':
    raise SystemExit(2)
(output / (image.stem + '.txt')).write_text('舊字體', encoding='utf-8')
(output / (image.stem + '.json')).write_text(json.dumps({'contents': [], 'imginfo': {}}), encoding='utf-8')
(output / (image.stem + '.xml')).write_text('<OCRDATASET />', encoding='utf-8')
''', encoding='utf-8')
        arguments = argparse.Namespace(input='input', input_root=self.root,
            output=self.root / 'result', engine_root=engine,
            config=PROJECT_ROOT / 'config/default.yaml', identifier=None, title=None, source=None)
        with patch('run_ocr.verify_engine', return_value={'test_double': True}):
            self.assertEqual(execute(arguments), 1)
        metadata = yaml.safe_load((arguments.output / 'metadata.yaml').read_text())
        self.assertEqual(metadata['processing']['status'], 'failed')
        self.assertEqual([r['status'] for r in metadata['images']], ['success', 'failed'])
        self.assertTrue((arguments.output / 'raw/同名.jpg/同名.txt').is_file())
        self.assertTrue((arguments.output / 'raw/同名.png/engine.log').is_file())
        with self.assertRaises(ValueError):
            execute(arguments)


if __name__ == '__main__':
    unittest.main()
