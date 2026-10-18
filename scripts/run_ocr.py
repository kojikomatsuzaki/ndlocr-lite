"""公式CLIを1画像ずつ呼び、生出力と来歴を独立した実行ディレクトリへ保存。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ElementTree

import yaml

from generate_metadata import new_metadata, sha256_file, timestamp, write_metadata
from prepare_input import prepare_images, resolve_input


def verify_engine(engine_root: Path, configuration: dict) -> dict:
    expected = configuration['engine']
    commit = subprocess.check_output(
        ['git', '-C', str(engine_root), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != expected['commit']:
        raise ValueError('NDLOCR-LiteのコミットSHAが設定と一致しません')
    subprocess.run(['git', '-C', str(engine_root), 'diff', '--exit-code',
                    '--quiet', 'HEAD', '--'], check=True)
    models = []
    for model in expected['models']:
        path = engine_root / model['path']
        content = path.read_bytes()
        blob = hashlib.sha1(f'blob {len(content)}\0'.encode() + content).hexdigest()
        if blob != model['git_blob']:
            raise ValueError('モデルが公式の固定コミットと一致しません')
        models.append({**model, 'sha256': sha256_file(path), 'bytes': len(content)})
    resources = []
    for key in ('character_config', 'layout_config'):
        path = engine_root / expected[key]
        resources.append({'path': expected[key], 'sha256': sha256_file(path)})
    return {key: expected[key] for key in (
        'name', 'repository', 'release', 'commit',
        'source_package_version', 'source_version',
    )} | {'models': models, 'resources': resources, 'source_modified': False}


def command_for_image(engine_root: Path, image: Path, destination: Path,
                      configuration: dict) -> list[str]:
    engine = configuration['engine']
    command = [sys.executable, str(engine_root / 'src/ocr.py'),
               '--sourceimg', str(image), '--output', str(destination),
               '--device', configuration['execution']['device'],
               '--det-classes', str(engine_root / engine['layout_config']),
               '--rec-classes', str(engine_root / engine['character_config'])]
    for model in engine['models']:
        command.extend([model['argument'], str(engine_root / model['path'])])
    return command


def validate_outputs(directory: Path, stem: str, result_root: Path) -> list[dict]:
    outputs = []
    for suffix in ('.txt', '.json', '.xml'):
        path = directory / (stem + suffix)
        if not path.is_file():
            raise ValueError('公式CLIの必要な出力ファイルが生成されませんでした')
        text = path.read_text(encoding='utf-8')
        if suffix == '.json':
            parsed = json.loads(text)
            if 'contents' not in parsed or 'imginfo' not in parsed:
                raise ValueError('公式JSONの構造を確認できません')
        if suffix == '.xml':
            ElementTree.fromstring(text)
        outputs.append({'path': path.relative_to(result_root).as_posix(),
                        'sha256': sha256_file(path), 'bytes': path.stat().st_size})
    return outputs


def execute(arguments: argparse.Namespace) -> int:
    result_root = arguments.output.resolve()
    input_root = arguments.input_root.resolve()
    # 以前の成功結果と今回の失敗を取り違えないため、非空の出力先は拒否する。
    if result_root.exists() and any(result_root.iterdir()):
        raise ValueError('出力先は新規または空のディレクトリを指定してください')
    source = resolve_input(input_root, arguments.input)
    if (source == result_root or source in result_root.parents
            or result_root in source.parents):
        raise ValueError('入力と出力は重ならない場所を指定してください')
    result_root.mkdir(parents=True, exist_ok=True)
    metadata = new_metadata(arguments.identifier, arguments.title, arguments.source)
    processing = metadata['processing']
    write_metadata(metadata, result_root)
    try:
        processing['stage'] = 'configuration'
        configuration = yaml.safe_load(arguments.config.read_text(encoding='utf-8'))
        processing['configuration'] = {
            'sha256': sha256_file(arguments.config), 'values': configuration}
        engine_root = arguments.engine_root.resolve()
        processing['stage'] = 'engine_verification'
        processing['engine'] = verify_engine(engine_root, configuration)
        with tempfile.TemporaryDirectory(prefix='ndlocr-') as temporary:
            staging = Path(temporary)
            processing['stage'] = 'input_validation'
            if source.is_file() and source.suffix.lower() == '.zip':
                processing['input_archive'] = {
                    'filename': source.name, 'sha256': sha256_file(source)}
            metadata['images'] = prepare_images(source, staging, configuration['input'])
            processing['stage'] = 'ocr'
            failed = False
            for index, record in enumerate(metadata['images'], start=1):
                image = staging / 'images' / record['input_file']
                # 元の拡張子までディレクトリ名に含め、a.jpgとa.pngの上書きを防ぐ。
                destination = result_root / 'raw' / record['input_file']
                destination.mkdir(parents=True)
                record['started_at'] = timestamp()
                command = command_for_image(engine_root, image, destination, configuration)
                record['command'] = command
                record['status'] = 'running'
                write_metadata(metadata, result_root)
                print(f'[OCR] {index}/{len(metadata["images"])}', flush=True)
                log_path = destination / 'engine.log'
                try:
                    with log_path.open('w', encoding='utf-8') as log:
                        subprocess.run(command, cwd=engine_root / 'src', check=True,
                                       stdout=log, stderr=subprocess.STDOUT,
                                       timeout=configuration['execution']['timeout_seconds_per_image'],
                                       env={**os.environ, 'PYTHONUTF8': '1'})
                    if sha256_file(image) != record['sha256']:
                        raise ValueError('OCR中に入力画像が変化しました')
                    record['outputs'] = validate_outputs(destination, image.stem, result_root)
                    record['status'] = 'success'
                except Exception as error:
                    failed = True
                    record['status'] = 'failed'
                    record['error'] = {'type': type(error).__name__, 'message': str(error)}
                    # コマンド全文や入力文字列をActionsの制御命令として解釈させない。
                    print(f'[ERROR] image {index}: {type(error).__name__}; see engine.log',
                          file=sys.stderr, flush=True)
                    record['outputs'] = [
                        {'path': path.relative_to(result_root).as_posix(),
                         'sha256': sha256_file(path), 'bytes': path.stat().st_size}
                        for path in sorted(destination.iterdir()) if path.is_file()
                    ]
                record['log'] = log_path.relative_to(result_root).as_posix()
                record['finished_at'] = timestamp()
                write_metadata(metadata, result_root)
            processing['status'] = 'failed' if failed else 'success'
            processing['stage'] = 'complete'
    except Exception as error:
        processing['status'] = 'failed'
        processing['error'] = {'type': type(error).__name__, 'message': str(error)}
        print(f'[ERROR] {processing["stage"]}: {type(error).__name__}', file=sys.stderr)
    finally:
        processing['finished_at'] = timestamp()
        write_metadata(metadata, result_root)
    return 0 if processing['status'] == 'success' else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='入力ルートからの相対パス（画像・フォルダ・ZIP）')
    parser.add_argument('--input-root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--engine-root', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=Path('config/default.yaml'))
    parser.add_argument('--identifier')
    parser.add_argument('--title')
    parser.add_argument('--source')
    try:
        return execute(parser.parse_args())
    except Exception as error:
        print(f'[ERROR] initialization: {type(error).__name__}: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
