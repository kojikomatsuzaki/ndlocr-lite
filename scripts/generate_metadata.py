"""書誌情報と技術情報を分けた、加工していないOCRの処理記録。"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

import yaml


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def environment() -> dict:
    # 環境変数を丸ごと採録すると認証情報を混入させるため、許可リストのみ。
    return {
        'python': platform.python_version(),
        'platform': platform.platform(),
        'machine': platform.machine(),
        'packages': sorted(
            [{'name': package.metadata['Name'], 'version': package.version}
             for package in importlib.metadata.distributions()],
            key=lambda item: item['name'].lower(),
        ),
        'github': {key: os.getenv(key) for key in (
            'GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_RUN_ID',
            'GITHUB_RUN_ATTEMPT', 'RUNNER_OS', 'RUNNER_ARCH',
            'ImageOS', 'ImageVersion',
        )},
    }


def new_metadata(identifier: str | None, title: str | None, source: str | None) -> dict:
    return {
        'schema_version': '1.0',
        'bibliography': {'identifier': identifier or None, 'title': title or None,
                         'source': source or None},
        'processing': {
            'started_at': timestamp(), 'finished_at': None,
            'status': 'running', 'stage': 'initialization', 'error': None,
            'engine': None, 'environment': environment(),
            'text_policy': 'raw_engine_output_no_correction',
            'configuration': None, 'input_archive': None,
        },
        'images': [],
    }


def write_metadata(metadata: dict, directory: Path) -> None:
    # YAMLを正本とし、JSONは読み戻した正本から生成して分岐を防ぐ。
    yaml_path = directory / 'metadata.yaml'
    temporary = directory / 'metadata.yaml.tmp'
    temporary.write_text(yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False),
                         encoding='utf-8')
    temporary.replace(yaml_path)
    canonical = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
    (directory / 'metadata.json').write_text(
        json.dumps(canonical, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
