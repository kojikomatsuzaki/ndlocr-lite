"""原画像を再保存せず、検証済みのバイト列だけを作業領域へコピーする。"""

from __future__ import annotations

import shutil
import stat
import warnings
import zipfile
from pathlib import Path, PurePosixPath

from PIL import Image

from generate_metadata import sha256_file


def safe_relative_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '\\' in name or ':' in name
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
            or any(part in ('', '.', '..') for part in name.rstrip('/').split('/'))):
        raise ValueError('危険な入力パスを拒否しました')
    return path


def resolve_input(root: Path, relative: str) -> Path:
    parts = safe_relative_name(relative).parts
    path = root.resolve()
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('入力のシンボリックリンクは利用できません')
    if not path.exists():
        raise ValueError('入力ファイルまたはディレクトリが存在しません')
    return path


def validate_image(path: Path, settings: dict) -> dict:
    if path.suffix.lower() not in settings['extensions']:
        raise ValueError('対応形式はJPEG・PNGのみです')
    if path.stat().st_size > settings['max_file_bytes']:
        raise ValueError('画像のファイルサイズ上限を超えています')
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(path) as image:
            expected_format = 'PNG' if path.suffix.lower() == '.png' else 'JPEG'
            if image.format != expected_format:
                raise ValueError('拡張子と画像形式が一致しません')
            width, height = image.size
            if (width * height > settings['max_pixels']
                    or max(width, height) > settings['max_dimension']):
                raise ValueError('画像の寸法上限を超えています')
            if getattr(image, 'n_frames', 1) != 1:
                raise ValueError('複数フレーム画像は未対応です')
            image.verify()
        with Image.open(path) as image:
            image.load()
    return {'format': expected_format, 'width': width, 'height': height,
            'bytes': path.stat().st_size, 'sha256': sha256_file(path)}


def extract_zip(archive: Path, destination: Path, settings: dict) -> None:
    if archive.stat().st_size > settings['max_total_bytes']:
        raise ValueError('ZIPのサイズ上限を超えています')
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if len(members) > settings['max_zip_members']:
            raise ValueError('ZIP内の項目数上限を超えています')
        names = set()
        total_bytes = 0
        # 全エントリの検査を終えてから書き出す。extractallには任せない。
        for member in members:
            relative = safe_relative_name(member.filename)
            folded = str(relative).casefold()
            if folded in names:
                raise ValueError('ZIP内の重複パスを拒否しました')
            names.add(folded)
            mode = member.external_attr >> 16
            file_type = stat.S_IFMT(mode)
            if (file_type not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or member.flag_bits & 1):
                raise ValueError('リンク・特殊ファイル・暗号化ZIPは利用できません')
            if not member.is_dir():
                if relative.suffix.lower() not in settings['extensions']:
                    raise ValueError('ZIPにはJPEG・PNG以外を含めないでください')
                total_bytes += member.file_size
                if (member.file_size > settings['max_file_bytes']
                        or total_bytes > settings['max_total_bytes']
                        or member.file_size / max(member.compress_size, 1)
                        > settings['max_compression_ratio']):
                    raise ValueError('ZIPの展開量上限を超えています')
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.filename).parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open('xb') as output:
                copied = 0
                while chunk := source.read(1024 * 1024):
                    copied += len(chunk)
                    if copied > settings['max_file_bytes'] or copied > member.file_size:
                        raise ValueError('ZIPの実際の展開量が上限を超えています')
                    output.write(chunk)


def prepare_images(source: Path, staging: Path, settings: dict) -> list[dict]:
    expanded = staging / 'expanded'
    images_root = staging / 'images'
    images_root.mkdir()
    if source.is_file() and source.suffix.lower() == '.zip':
        expanded.mkdir()
        extract_zip(source, expanded, settings)
        source_root = expanded
    else:
        source_root = source if source.is_dir() else source.parent
    candidates = ([source] if source.is_file() and source.suffix.lower() != '.zip'
                  else sorted(source_root.rglob('*')))
    files = []
    for path in candidates:
        if path.is_symlink():
            raise ValueError('入力のシンボリックリンクは利用できません')
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('入力に通常ファイル以外が含まれています')
        files.append(path)
    if not files or len(files) > settings['max_files']:
        raise ValueError('入力画像がないか、画像数上限を超えています')
    if sum(path.stat().st_size for path in files) > settings['max_total_bytes']:
        raise ValueError('入力画像の合計サイズ上限を超えています')
    records = []
    normalized_names = set()
    for path in files:
        relative = path.relative_to(source_root)
        safe_relative_name(relative.as_posix())
        # macOS/Windowsへ戻しても同名衝突しないように大文字小文字を区別しない。
        key = relative.as_posix().casefold()
        if key in normalized_names:
            raise ValueError('大文字小文字のみ異なる入力名は利用できません')
        normalized_names.add(key)
        properties = validate_image(path, settings)
        target = images_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if sha256_file(target) != properties['sha256']:
            raise ValueError('入力のコピー中にSHA-256が変化しました')
        records.append({'input_file': relative.as_posix(), **properties,
                        'status': 'pending', 'error': None, 'outputs': []})
    return records
