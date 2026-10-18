"""同一リポジトリのReleaseアセットを取得し、来歴をArtifacts用に記録する。"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yaml

from generate_metadata import sha256_file, timestamp


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise ValueError('HTTPS以外へのリダイレクトは拒否します')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and urlsplit(req.full_url).netloc != urlsplit(newurl).netloc:
            redirected.remove_header('Authorization')
        return redirected


def request(url: str, token: str, binary: bool = False):
    headers = {'Accept': 'application/octet-stream' if binary else 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'ndlocr-release-input'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    return build_opener(SafeRedirect()).open(Request(url, headers=headers), timeout=60)


def api_json(url: str, token: str):
    with request(url, token) as response:
        return json.load(response)


def download(repository: str, tag: str, asset_name: str, directory: Path,
             limit: int, token: str = '') -> Path:
    directory.mkdir(parents=True, exist_ok=False)
    archive = directory / 'input.zip'  # ユーザー入力をローカルパスに使わない。
    report = {'repository': repository, 'tag': tag, 'asset_name': asset_name,
              'started_at': timestamp(), 'status': 'failed'}
    try:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('リポジトリ名が不正です')
        if not tag.strip() or not asset_name.strip() or not asset_name.lower().endswith('.zip'):
            raise ValueError('ReleaseタグとZIPアセット名を指定してください')
        base = 'https://api.github.com/repos/' + repository
        release = api_json(base + '/releases/tags/' + quote(tag, safe=''), token)
        report.update(release_id=release['id'], release_url=release['html_url'])
        matches = []
        page = 1
        while True:
            assets = api_json(f"{base}/releases/{int(release['id'])}/assets?per_page=100&page={page}", token)
            matches.extend(asset for asset in assets if asset['name'] == asset_name)
            if len(assets) < 100:
                break
            page += 1
        if len(matches) != 1:
            raise ValueError('指定名のReleaseアセットが一意に見つかりません')
        asset = matches[0]
        report.update(asset_id=asset['id'], expected_bytes=asset['size'],
                      asset_updated_at=asset['updated_at'])
        if not 0 < asset['size'] <= limit:
            raise ValueError('ZIPのサイズ上限を超えているか空です')
        with request(f"{base}/releases/assets/{int(asset['id'])}", token, binary=True) as response, archive.open('xb') as output:
            copied = 0
            while chunk := response.read(1024 * 1024):
                copied += len(chunk)
                if copied > limit or copied > asset['size']:
                    raise ValueError('ダウンロードの実サイズが上限を超えています')
                output.write(chunk)
        if copied != asset['size']:
            raise ValueError('ダウンロードが不完全です')
        report.update(bytes=copied, sha256=sha256_file(archive), status='success')
        return archive
    except Exception as error:
        archive.unlink(missing_ok=True)
        report['error_type'] = type(error).__name__
        raise
    finally:
        report['finished_at'] = timestamp()
        (directory / 'release-input.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    try:
        settings = yaml.safe_load(Path('config/default.yaml').read_text(encoding='utf-8'))['input']
        download(os.environ['GITHUB_REPOSITORY'], os.environ.get('RELEASE_TAG', ''),
                 os.environ.get('RELEASE_ASSET', ''), Path(os.environ['RUNNER_TEMP']) / 'ndlocr-release',
                 settings['max_total_bytes'], os.environ.get('GH_TOKEN', ''))
        return 0
    except Exception as error:
        # 外部入力やHTTP例外をActions制御命令としてログに出さない。
        print(f'[ERROR] Release input: {type(error).__name__}; see release-input.json', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
