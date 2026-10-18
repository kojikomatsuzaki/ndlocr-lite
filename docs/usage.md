# 使い方

## Actionsで実資料を処理する

公開・恒久保存が可能と確認した画像だけを対象にする方式です。
Actionsの手動実行フォームにはファイル添付欄はありません。

1. リポジトリの`inputs/<資料ごとの名前>/`に画像を配置します。
2. `.gitignore`対象なので、公開可と確認した対象だけを`git add -f inputs/<資料名>/<画像名>`で追加してコミット・pushします。ディレクトリを無差別に追加しないでください。
3. Actions → Run NDLOCR-Lite → Run workflowで`input_mode=repository`を選びます。
4. `input_path=inputs/<資料ごとの名前>`と書誌情報を入力します。
5. 完了した実行のArtifactsから結果を取得します。保持期間は7日です。

`input_path`にはフォルダ、JPEG/PNG1枚、画像だけを含むZIPを指定できます。
ネストしたディレクトリを処理し、ファイル名と相対パスを記録します。
Git履歴に入った画像は、後でファイルを削除しても履歴に残ります。
公開可否が未確認なら、この方式へ投入せず次のローカル処理を利用してください。

初回検証資料に指定された太政官達の書誌情報は次のとおりです（利用者提供情報）。

| 入力欄 | 値 |
| --- | --- |
| identifier | `787953` |
| title | 法令全書所収 太政官達 明治6年第413号 |
| source | 国立国会図書館デジタルコレクション https://dl.ndl.go.jp/pid/787953 |

原画像を別資料に置き換えて検証済みと扱うことはありません。

## Git管理せずローカルで処理する

Python 3.10以上とGitが必要です。以下はリポジトリのルートで実行します。
`pip`が利用する間接依存もメタデータに記録されます。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
git clone https://github.com/ndl-lab/ndlocr-lite .upstream/ndlocr-lite
engine_commit=$(python -c "import yaml; print(yaml.safe_load(open('config/default.yaml'))['engine']['commit'])")
git -C .upstream/ndlocr-lite checkout --detach "$engine_commit"
python -m pip install -r .upstream/ndlocr-lite/requirements.txt
python -m unittest discover -s tests -v
```

例えば原画像を`/path/to/materials/787953/`に置く場合：

```bash
python scripts/run_ocr.py \
  --input-root /path/to/materials \
  --input 787953 \
  --engine-root .upstream/ndlocr-lite \
  --output results/787953-first-run \
  --identifier 787953 \
  --title '法令全書所収 太政官達 明治6年第413号' \
  --source '国立国会図書館デジタルコレクション https://dl.ndl.go.jp/pid/787953'
```

ZIPの場合は`--input '資料.zip'`とします。原本は画像のみのZIPにし、`.DS_Store`などを含めないでください。
失敗後の再実行は新しい出力先を指定します。既存の結果に混ぜることはできません。
書誌情報が不明なら対応する引数を省略すると`null`になります。

## 結果を読む

1. `metadata.yaml`の`processing.status`と各画像の`status`を確認します。
2. `input_file`と`sha256`で元画像を特定します。
3. `outputs`の相対パスから生TXT/JSON/XMLを開きます。
4. 校正する場合は、生データを残して別ファイルとして作成します。

エラーは実行画面で失敗したステップを開きます。画像処理中ならArtifacts内の`engine.log`も確認してください。
Artifactsが存在していても処理成功とは限りません。失敗時にも診断記録を保存する設計です。

## 将来の入力拡張

現状のActionsには外部URL、非公開ストレージ、ブラウザアップロードの入力経路はありません。
非公開資料をクラウドで扱う必要が生じた段階で、権限・一時保存・削除期限を定めた経路を追加します。
GitHub Pages、校正画面、校正履歴管理は今回の実装範囲に含めません。
