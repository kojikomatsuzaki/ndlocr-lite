"""外部資料を同梱せず、実行時に独自の合成テスト画像を作る。"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_samples(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    # これは接続試験であり、歴史資料・日本語の認識精度評価ではない。
    font = ImageFont.load_default(size=48)
    for name, text in (
        ('sample-01.jpg', 'NDLOCR workflow test 2026'),
        ('sample-02.jpeg', 'Keep the original image unchanged.'),
        ('sample-03.png', 'Raw OCR output and metadata.'),
    ):
        image = Image.new('RGB', (1600, 500), 'white')
        ImageDraw.Draw(image).text((80, 200), text, fill='black', font=font)
        image.save(directory / name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    create_samples(parser.parse_args().directory)
