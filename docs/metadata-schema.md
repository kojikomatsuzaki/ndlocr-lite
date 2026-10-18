# メタデータ仕様 1.0

`metadata.yaml`を正本とし、書き出したYAMLを読み戻して`metadata.json`を生成します。
文字コードはUTF-8、日時はUTCオフセット付きISO 8601、未知の値は`null`です。
ファイル名の推測・資料名からの書誌補完はしません。

| フィールド | 意味 |
| --- | --- |
| `schema_version` | スキーマの版。文字列`1.0` |
| `bibliography.identifier` | 利用者が指定した資料識別子 |
| `bibliography.title` | 原資料名 |
| `bibliography.source` | 出典。URLまたは書誌情報の文字列 |
| `processing.started_at`, `finished_at` | 実行開始・終了時刻 |
| `processing.status` | `running` / `success` / `failed` |
| `processing.stage` | initialization / configuration / engine_verification / input_validation / ocr / complete |
| `processing.error` | 実行全体のエラー種別と説明、またはnull |
| `processing.text_policy` | `raw_engine_output_no_correction` |
| `processing.configuration` | 設定YAMLのSHA-256と全設定値 |
| `processing.input_archive` | ZIP入力時の名前とSHA-256、それ以外はnull |
| `processing.engine` | 実際に照合したOCRエンジン情報。確認失敗時はnull |
| `processing.engine.release` | 上流のリリースタグ名 |
| `processing.engine.commit` | 上流の完全なコミットSHA |
| `processing.engine.source_package_version`, `source_version` | 同じコミットの版表記。リリース名とは区別 |
| `processing.engine.models[]` | モデル名（path）、役割、CLI引数、Git blob ID、SHA-256、バイト数 |
| `processing.engine.resources[]` | 文字集合・レイアウト分類設定のパスとSHA-256 |
| `processing.environment` | Python、OS、CPUアーキテクチャ、インストール済み全パッケージと版 |
| `processing.environment.github` | 許可した実行環境変数のみ。実行ID、試行番号、ワークフローSHA、runner情報など |
| `images[].input_file` | 入力フォルダまたはZIP内の相対パス（ファイル名を保持） |
| `images[].sha256`, `bytes`, `format`, `width`, `height` | 入力画像のバイト列ハッシュ、サイズ、検出形式・寸法 |
| `images[].status` | pending / running / success / failed |
| `images[].error` | 画像単位のエラー種別またはnull。詳細はlog |
| `images[].started_at`, `finished_at` | 画像単位の開始・終了時刻。未開始ならフィールドなし |
| `images[].command` | 実際に渡した引数配列。一時作業パスを含む |
| `images[].outputs[]` | 出力の相対パス、SHA-256、バイト数 |
| `images[].log` | 公式CLIログの相対パス |

成功時の`outputs`はTXT・JSON・XMLの3点です。失敗時は存在する部分出力とログを列挙し、成功扱いにしません。
`error`がnullでも、まだrunning/pendingなら完了していません。
Artifactsには原画像は含めません。入力ハッシュと原画像を資料管理側で保持してください。

`workflow-status.json`はGitHub Actions自身の実行記録で、メタデータJSONとは別です。
`steps`に各工程のoutcome、`run_url`、`workflow_commit`、`run_attempt`、`input_mode`を保存します。
metadata.yaml作成前の失敗ではこのファイルとActionsログが診断情報になります。
