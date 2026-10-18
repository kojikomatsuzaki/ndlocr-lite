# 初期検証記録

確認日：2026-10-18

## 公式仕様の確認

公式README、実行コード、requirements、ライセンス、リリース1.3.1とモデルのGitツリーを確認しました。
固定エンジンコミットは `6feccb29e33c2467ea48894e66502a7788ae2b2d` です。
参照URLとバージョン表記の相違は[README](../README.md#ndlocr-liteと固定バージョン)に記録しています。

## 成功したActions実行

- 初回：[実行 #1](https://github.com/kojikomatsuzaki/ndlocr-lite/actions/runs/39114613812) — success。
- 現行の実行コード：[実行 #2](https://github.com/kojikomatsuzaki/ndlocr-lite/actions/runs/39114868552) — success、全体54秒。
- 検証対象コミット：`d0b67eb8acda732687b3e43c8f2eac8c01bdeddf`。
- 実環境：Ubuntu 24.04.5、ランナーイメージ20261012.334.1、Python 3.12.15、CPU、onnxruntime 1.26.0。
- 公式依存関係のインストール、固定モデルの照合、公式CLIによるJPEG2枚・PNG1枚の連続処理、メタデータ保存、Artifacts公開が成功しました。
- 入力は `scripts/create_sample.py` が生成した独自の合成画像です。歴史資料や日本語の認識精度を評価したものではありません。

Actions内で各画像のTXT・JSON・XMLの存在、UTF-8、JSON/XMLの構文を検査しています。
YAMLを保存して読み戻し、同じ内容のmetadata.jsonを生成しています。
成功時は15ファイルをArtifactsにアップロードしました。

| 出力 | 内容 |
| --- | --- |
| `raw/sample-01.jpg/sample-01.txt`、`.json`、`.xml` | JPEG1の公式生出力 |
| `raw/sample-02.jpeg/sample-02.txt`、`.json`、`.xml` | JPEG2の公式生出力 |
| `raw/sample-03.png/sample-03.txt`、`.json`、`.xml` | PNGの公式生出力 |
| 各画像の `engine.log` | 公式CLIログ3点 |
| `metadata.yaml` / `metadata.json` | 書誌情報、入力・モデル・出力のハッシュ、環境、時刻、結果 |
| `workflow-status.json` | Actions工程別結果 |

成果物名：`ndlocr-39114868552-1`、Artifact ID：`12131808494`、ZIPサイズ：11,421バイト。
GitHub記録のZIP SHA-256：`164f1be84632fa6e163003f7966bd0a7b7ea94c1da1987fd86753510d6ee776f`。
保存期限は2026-10-25 09:20:08 UTC（7日間）です。

GitHub連携のダウンロードAPIでZIP取得とファイル参照の返却まで成功しました。
一方、ブラウザから作業環境への保存は完了せず、取得後のZIP展開・全文内容の再検査は未実施です。
上記の生成・構文検証はActions内の実行結果に基づきます。OCR認識文字列の目視評価はしていません。

## 自動テスト

`python -m unittest discover -s tests -v`：13件すべて成功。
現行コードの成功実行では0.327秒でした。

- 入力不存在、空フォルダ、対応外形式、拡張子偽装、破損画像。
- 日本語・空白を含む名前、原画像のバイト列とSHA-256、サイズ・画素数上限。
- シンボリックリンク、パストラバーサル、ZIPの重複名・特殊ファイル・展開量上限。
- YAML正本とJSONの整合性、UTF-8、未補正の生出力検証。
- 同一stemのJPEG/PNGの分離、模擬CLIで一部失敗したバッチの継続と失敗報告、既存結果の保護。

ローカルではPython構文チェックを実施しました。単体テストと実エンジンの検証はActions上の結果です。

## 実際の異常系実行

[実行 #3](https://github.com/kojikomatsuzaki/ndlocr-lite/actions/runs/39116041650) は、
`repository`モードで存在しない `inputs/does-not-exist` を指定した意図的な失敗試験です。
同じコミット `d0b67eb8acda732687b3e43c8f2eac8c01bdeddf` を使用しました。

確認したログ：

```text
[ERROR] initialization: ValueError: 入力ファイルまたはディレクトリが存在しません
Process completed with exit code 1.
```

処理ステップがfailureとなり、後続の診断保存とArtifacts公開はsuccessでした。
診断Artifact `ndlocr-39116041650-1`（ID `12132347139`、407バイト）を確認しました。
入力の解決前に停止するため、このケースではOCRのmetadata.yamlは作られず、workflow-status.jsonで失敗工程を記録します。
この赤い実行結果は意図した入力検証の結果です。

## 未検証・実資料の状態

対象：法令全書所収 太政官達 明治6年第413号、国立国会図書館デジタルコレクション、資料識別子787953、JPEG4枚。
利用者の提供したZIPのファイル情報は確認しましたが、作業環境へのダウンロードが失敗し、原画像の取得・実OCRは未実施です。
別の歴史資料には置き換えていません。原画像の公開可否も未確認のため、画像をコミットしていません。
次の実資料検証には、元のZIPまたは4枚のJPEGを作業環境から読めるローカルパスで提供する必要があります。

高解像度の日本語歴史資料、上限付近の大規模バッチ、Ubuntu 26での動作、ダウンロードZIPのローカル再検査は未検証です。
`ubuntu-latest`は将来変わるため、実行時のOS・Python・依存関係の版をメタデータで比較してください。

## 次の改善候補

1. 対象4枚の実画像で、ファイル対応・ハッシュ・生出力を確認する。
2. 実資料のサイズ・処理時間に応じて上限を調整する。
3. 必要になった段階で間接依存関係も固定し、同一画像によるエンジン更新比較を整える。
4. 校正工程はraw出力を保持したまま、別管理として追加する。

## Release ZIP入力の追加検証（2026-10-18、PR #1）

検証した実装コミット：`ad1ea47dafe01d42012218846ff7b3fe85d38732`。
参考として既存sample実行 [#4](https://github.com/kojikomatsuzaki/ndlocr-lite/actions/runs/39118004055) のOCR・診断・Artifacts全工程成功も確認しました。

| 入力 | Actions実行 | 結果 |
| --- | --- | --- |
| release | [39118585003](https://github.com/kojikomatsuzaki/ndlocr-lite/actions/runs/39118585003) | 成功、実エンジンCPU OCR 3画像、Artifacts 16ファイル |
| sample | [39118586900](https://github.com/kojikomatsuzaki/ndlocr-lite/actions/runs/39118586900) | 成功、従来の3画像、Artifacts 15ファイル |
| repository | [39118629893](https://github.com/kojikomatsuzaki/ndlocr-lite/actions/runs/39118629893) | 成功、固定エンジンに含まれる公式縦書きPNG 1画像、Artifacts 7ファイル |
| release（存在しないアセット） | [39118588926](https://github.com/kojikomatsuzaki/ndlocr-lite/actions/runs/39118588926) | 意図した失敗、入力工程で停止、OCRはスキップ、診断Artifacts 2ファイル保存 |

Release試験は自作の合成画像のみを使用しました。検証用プレリリース
[`release-input-smoke-20261018`](https://github.com/kojikomatsuzaki/ndlocr-lite/releases/tag/release-input-smoke-20261018)
の `release-smoke.zip` に、`合成画像/`配下のJPEG2枚・PNG1枚を格納しています。
タグは検証対象コミットを指し、原画像をGitには追加していません。
ZIP SHA-256：`414759a098cf5182baadb81053bc20f5854a182bb8614755029928c3c9994453`。

今回は4実行すべてのArtifactsをローカルへダウンロードして再検査しました。
Release ZIPの元バイト列・release-input.json・metadata.yamlのSHA-256一致、各画像の元バイト列とのハッシュ一致、
全出力のSHA-256、YAML/JSONの一致、各画像の処理成功、ZIPと原画像がArtifactsに含まれないことを確認しました。
Releaseとsampleの生TXTはそれぞれ以下の3文字列でした。

- `NDLOCR workflow test 2026`
- `Keep the original image unchanged.`
- `Raw OCR output and metadata.`

repository試験の入力は `.upstream/ndlocr-lite/resource/tategaki2026-04-24-094138.png` です。
ジョブ内で取得する固定エンジンの公式サンプルを、既存のrepository入力経路に渡しました。
これは動作回帰試験であり、歴史資料の認識精度評価ではありません。
失敗試験のArtifactsには、`status: failed`のrelease-input.jsonと、入力工程failure・OCR skippedを示すworkflow-status.jsonが残りました。

自動テストは既存13件＋追加10件、計23件がローカルPython 3.14および各ActionsのPython 3.12で成功しました。
追加テストはタグ・アセット指定、完全一致、ページング、取得サイズ制限・不完全ダウンロード、
ZIPと画像のハッシュ、既存の不正ZIP拒否、別ホストへのリダイレクト時の認証ヘッダー除去、
模擬CLIによる取得→ZIP検査→OCR→生出力・メタデータの連携を確認します。
公式配布のactionlint 1.7.12（配布チェックサム一致）と `git diff --check` も成功しました。

太政官達の4画像や高解像度歴史資料の実OCRは今回も未実施です。
