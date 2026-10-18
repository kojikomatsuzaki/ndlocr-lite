# NDLOCR-Lite GitHub Actions Workflow

本リポジトリは、国立国会図書館が公開する
NDLOCR-LiteをGitHub Actions上で実行するための
独立したワークフローおよび関連ツールを提供します。

NDLOCR-Liteの公式リポジトリ：
https://github.com/ndl-lab/ndlocr-lite

本リポジトリは国立国会図書館の公式プロジェクトではなく、
国立国会図書館による開発・運営・保証を受けたものではありません。

## English

# NDLOCR-Lite GitHub Actions Workflow

This repository provides an independent GitHub Actions
workflow and supporting tools for running NDLOCR-Lite,
an OCR tool developed by the National Diet Library of Japan.

Official NDLOCR-Lite repository:
https://github.com/ndl-lab/ndlocr-lite

This is an independent project.
It is not an official repository of the National Diet Library
of Japan and is not developed, maintained, or endorsed by
the National Diet Library.

## 目的と責務

歴史的日本語資料に繰り返し使える、小規模なOCR実行基盤です。
OCRエンジンそのものや個別資料のデジタルアーカイブを開発するリポジトリではありません。
明治期の法令、太政官達、郷土史、民話、茶業史などに共通して利用できます。

- 原画像を再圧縮・回転・改名・上書きせず、同一バイト列の作業用コピーを渡します。
- 公式CLIが出したTXT・JSON・XMLを再生成・整形・推測補正せず、そのまま保存します。
- 旧字体、歴史的仮名遣い、句読点、文体を変更する処理は追加しません。
- 校正・翻刻は別工程です。`raw/`を編集せず、別の資料管理環境で校正履歴を持たせてください。
- 書誌情報と実行情報を区別し、メタデータの正本YAMLからJSONを生成します。
- 画像・OCR結果・エンジン・モデルは原則Git管理せず、成果物は7日間のArtifactsで受け渡します。

## NDLOCR-Liteと固定バージョン

NDLOCR-LiteはCPUで実行できるOCRです。レイアウト認識のDEIMv2、文字列認識のPARSeq、読み順整序を組み合わせます。[1]

| 項目 | 採用値・確認内容 |
| --- | --- |
| リリース | 1.3.1（調査日2026-10-18時点の最新の非プレリリース） |
| 固定コミット | `6feccb29e33c2467ea48894e66502a7788ae2b2d` |
| Python | 公式は3.10以上。本基盤はActionsで3.12 |
| OS | 公式確認環境はWindows 11、macOS Sequoia / Apple M4、Ubuntu 22.04。本基盤は`ubuntu-latest` |
| 実行デバイス | CPU（`--device cpu`）。APIキー・GPU不要 |
| 依存関係 | 固定コミットの公式`requirements.txt`をそのままインストール |
| モデル取得 | 固定コミットの`src/model/`にONNXモデル4点が含まれる。別サイトへのモデル取得処理は不要 |
| 入出力 | 本基盤はJPEG・PNG・それらを含むZIPを受け付け、TXT・JSON・XMLを保存 |

公式リリース名1.3.1に対し、同じコミットの`pyproject.toml`は1.3.0、`src/version.py`は0.0.0.dev0です。
これらを混同せずに記録し、エンジンの同一性はコミットSHAで確認します。[2][3]
モデルの正式な識別名・Git blob ID・実行時SHA-256はメタデータに保存します。

## 最初の実行

1. [Actions](https://github.com/kojikomatsuzaki/ndlocr-lite/actions) → **Run NDLOCR-Lite** → **Run workflow**を開きます。
2. `input_mode`を`sample`のまま実行します。
3. 完了した実行を開き、**Artifacts**の`ndlocr-実行ID-試行番号`をダウンロードします。

`sample`はこのプロジェクトが実行時に作る合成画像（JPEG 2枚・PNG 1枚）です。
歴史資料の代用品でも、文字認識精度の評価資料でもありません。
手動実行以外のトリガー、GitHub Pages、Webアップロード機能は設けていません。[4]

[検証済みの実行 #2](https://github.com/kojikomatsuzaki/ndlocr-lite/actions/runs/39114868552)では、合成画像3枚のCPU OCRと13件のテストが成功しています。詳しくは[検証記録](docs/validation.md)を参照してください。

実資料の入力方法とローカル実行は[使い方](docs/usage.md)を参照してください。

## Releaseに添付したZIPを処理する

原画像をGitにコミットせず、同じリポジトリのReleaseから取得できます。

1. JPEG・PNGだけを入れたZIPを作ります。サブフォルダ・日本語名・空白は利用できます。macOSの`__MACOSX`や`.DS_Store`は除いてください。
2. このリポジトリの **Releases → Draft a new release** でタグ（例：`materials-001`）を指定し、ZIP（例：`images.zip`）を添付してReleaseを公開します。ソースコードの自動生成ZIPは対象外です。
3. **Actions → Run NDLOCR-Lite → Run workflow** を開き、`input_mode`を`release`、`release_tag`を`materials-001`、`release_asset`を`images.zip`にして実行します。タグとアセット名は大文字小文字も含め完全一致です。
4. 必要に応じて`identifier`・`title`・`source`に資料情報を入力します。`input_path`はreleaseモードでは使いません。
5. 完了後、Artifactsの`ndlocr-実行ID-試行番号`をダウンロードします。

`sample`・`repository`の操作は従来どおりです。PRの変更を試す場合は、Run workflowのブランチ選択でPRのブランチを選んでください。
Release取得には既存の`contents: read`の`GITHUB_TOKEN`を使用し、追加のシークレットは不要です。別リポジトリのReleaseや任意URLは指定できません。

ZIPはダウンロード時にも最大500 MiB（`config/default.yaml`の`max_total_bytes`）に制限し、取得サイズの不一致を拒否します。
その後、既存のZIP検査で危険なパス、リンク・特殊ファイル、暗号化、重複名、画像以外、過大な展開量・圧縮率を拒否し、画像形式と寸法も検証します。
取得失敗・ZIP検査失敗はジョブ失敗になります。取得途中のZIPは削除します。

Artifactsには以下が残ります（ZIP・原画像自体は含めません）。

- `release-input.json`：リポジトリ、指定タグ・アセット名、Release ID・URL、アセットID・更新日時、ZIPのバイト数とSHA-256、取得結果。取得に失敗した場合も可能な範囲で保存します。
- `metadata.yaml` / `metadata.json`：既存のZIP SHA-256（取得時のローカル名は`input.zip`）と各画像のSHA-256、OCR処理結果。
- `raw/`・`workflow-status.json`：既存モードと同じ生出力・実行状況。

Releaseのタグやアセットは後から置き換えられるため、再現時は名前だけでなく保存されたSHA-256を比較してください。SHA-256の記録は出所の真正性を保証するものではありません。
Releaseへの添付はGit履歴に原画像を残しませんが、公開リポジトリのReleaseアセットは公開され、Artifactsの7日間保持とは別に残ります。公開できる資料だけを添付してください。

## 入力画像の仕様

JPEG（`.jpg` / `.jpeg`）とPNG（`.png`）に対応します。大文字拡張子も利用できます。
画像1枚、ディレクトリ（サブディレクトリを含む）、ZIPを指定できます。
名前は日本語・空白を含め保持します。危険なパスや制御文字、リンク、名前の衝突は拒否します。
ZIPは展開前検査と実際の展開量制限を実施します。

初期上限は100画像、1画像50 MiB、合計500 MiB、60メガピクセル、長辺12,000pxです。
公式のレイアウト認識が正方形の作業配列を作るため、細長い画像の過大なメモリ消費も長辺上限で抑えます。
上限は`config/default.yaml`にまとめています。
ZIP内の画像以外のファイル（`__MACOSX`、`.DS_Store`なども含む）は受け付けません。

## 出力ファイルとメタデータ

| 出力 | 内容 |
| --- | --- |
| `raw/<入力相対パス>/<元のstem>.txt` | 公式CLIの生テキスト、UTF-8 |
| `raw/<入力相対パス>/<元のstem>.json` | 生JSON。文字列、行の座標、方向、検出信頼度など |
| `raw/<入力相対パス>/<元のstem>.xml` | 生XML。レイアウト・読み順等の情報 |
| `raw/<入力相対パス>/engine.log` | 画像単位の公式CLI標準出力・エラー |
| `metadata.yaml` | 書誌情報・入力ハッシュ・モデル・環境・各画像の処理結果を持つ正本 |
| `metadata.json` | 正本YAMLから生成した同内容のJSON |
| `workflow-status.json` | Actionsの工程別結果。依存ライブラリ導入等の早い段階で失敗しても保存を試みる |

例えば`巻一/001.jpg`は`raw/巻一/001.jpg/001.txt`に対応します。
画像拡張子も出力ディレクトリに残すため、`001.jpg`と`001.png`で結果を上書きしません。
公式JSON内の一時作業パスは加工せず残します。永続的な対応づけには`metadata.yaml`の`input_file`を使ってください。
空のTXTは文字未検出の可能性があり、処理成功は認識精度を保証しません。

未取得の書誌情報は`null`です。仕様は[メタデータ定義](docs/metadata-schema.md)を参照してください。

## 制約・公開範囲

- 公開リポジトリのArtifactsは秘密の保管場所ではありません。GitHubにログインし、リポジトリの読み取り権限を持つ人が取得できます。[5]
- 原画像はArtifactsに含めませんが、生JSON、OCRテキスト、ファイル名、書誌情報、ログは含まれます。公開可能な資料だけを処理してください。
- `inputs/`と`results/`は`.gitignore`対象です。画像をコミットする場合は、利用条件と恒久公開の可否を別途確認し、対象ファイルだけを明示的に追加してください。
- 権利・公開可否が未確認の太政官達画像はコミットしていません。最初の実資料候補は「法令全書所収 太政官達 明治6年第413号」、資料識別子787953、出典は国立国会図書館デジタルコレクションです。実処理の状況は[検証記録](docs/validation.md)に記録します。
- 画像1枚につき最大600秒、ジョブ全体45分。途中失敗時は他の画像を続行し、全体を失敗として扱います。
- 1画像ずつ公式CLIを起動するため、その都度モデルを読み込みます。速度より対応関係・失敗の切り分けを優先しています。
- `ubuntu-latest`、Pythonのパッチ版、間接依存ライブラリは変わり得ます。実行環境の版を記録しますが、ビット単位で同一の認識結果を保証しません。
- 強制終了・ランナー障害では最終メタデータやArtifactsを残せないことがあります。実行中のメタデータは画像ごとに保存します。

## 構成と開発

```text
.github/workflows/ocr.yml
config/default.yaml
scripts/run_ocr.py
scripts/prepare_input.py
scripts/generate_metadata.py
scripts/create_sample.py
scripts/download_release.py
tests/test_pipeline.py
tests/test_release.py
docs/architecture.md
docs/usage.md
docs/metadata-schema.md
docs/validation.md
README.md
requirements.txt
LICENSE
.gitignore
```

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

エンジンの更新時は、公式リリースとCLIの変更を調査し、`config/default.yaml`のコミット・版表記・モデルを更新します。
同一SHA-256の入力画像で新旧を別の出力先に実行し、生出力とメタデータを比較してください。
元の結果を上書きしない設計の詳細は[構成・設計](docs/architecture.md)を参照してください。

## ライセンス

- **本リポジトリで独自に作成したコード・説明文：MIT License**。著作権表示はkojikomatsuzaki。[LICENSE](LICENSE)
- **NDLOCR-Lite本体：国立国会図書館、CC BY 4.0**。実行時に公式リポジトリから取得し、本リポジトリでは改変・再ライセンスしません。[公式LICENCE](https://github.com/ndl-lab/ndlocr-lite/blob/6feccb29e33c2467ea48894e66502a7788ae2b2d/LICENCE)
- 公式リポジトリに含まれるモデルと関連コードは、公式の表示・ライセンス条件に従います。本リポジトリのMITを適用しません。依存ソフトウェアについては[公式LICENCE_DEPENDENCEIES](https://github.com/ndl-lab/ndlocr-lite/blob/6feccb29e33c2467ea48894e66502a7788ae2b2d/LICENCE_DEPENDENCEIES)と各配布元のライセンスを確認してください。
- 入力資料とOCR結果に、本リポジトリのライセンスを一律に付与することはありません。

## References／参考文献・参照資料

以下は2026-10-18に確認した資料です。

1. 国立国会図書館「NDLOCR-Lite README」1.3.1の固定コミット。CPU、対応OS、Python、CLI、入出力仕様。https://github.com/ndl-lab/ndlocr-lite/blob/6feccb29e33c2467ea48894e66502a7788ae2b2d/README.md
2. 国立国会図書館「v1.3.1」2026-09-07公開。https://github.com/ndl-lab/ndlocr-lite/releases/tag/1.3.1
3. 国立国会図書館「ソースコード・依存関係・モデル」固定コミット。`src/ocr.py`、`src/deim.py`、`src/parseq.py`、`src/version.py`、`src/model/`、`requirements.txt`、`pyproject.toml`を確認。https://github.com/ndl-lab/ndlocr-lite/tree/6feccb29e33c2467ea48894e66502a7788ae2b2d
4. GitHub「Manually running a workflow」手動実行の画面・CLI。https://docs.github.com/actions/managing-workflow-runs/manually-running-a-workflow
5. GitHub「Downloading workflow artifacts」Artifactsの取得権限と操作。https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts

## 更新履歴

- 2026-10-18：初期実装。公式1.3.1のコミット固定、CPU手動実行、JPEG・PNG・ZIP検証、生TXT/JSON/XML、YAML正本メタデータ、Artifacts、単体テストを追加。実機の結果は[検証記録](docs/validation.md)に分けて記載。
