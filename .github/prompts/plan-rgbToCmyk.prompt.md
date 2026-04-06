## Plan: RGB to CMYK CLI

RGB JPEG を CMYK JPEG に変換する Python CLI を新規追加する。変換方式は単純変換と ICC プロファイル変換を切り替え可能にし、既定ではワークスペース内の JapanColor2011Coated ICC を使う。初版から単一ファイルだけでなく複数ファイル/フォルダ入力に対応し、実行方法が迷わないよう README と依存関係案内も含める。

**Steps**

1. Phase 1: CLI 仕様を確定する。入力として単一ファイル、複数ファイル、ディレクトリを受け取る方針を整理し、共通オプションを定義する。候補は conversion method 切替、output path or output directory、quality、overwrite、custom input ICC、custom output ICC、recursive、verify。ここで出力ファイル名規則も固定する。ディレクトリ入力時は元ファイル名に \_cmyk を付与し、出力先未指定なら入力元と同じ階層か専用出力ディレクトリに保存する。以降の実装はこの仕様に依存する。
2. Phase 2: コア変換処理を設計する。Pillow を使う共通ロード処理を作り、RGB 以外の入力は RGB に正規化してから変換する。simple モードでは Image.convert("CMYK")、icc モードでは ImageCms を使った profile-to-profile 変換を行う。入力画像に埋め込み ICC がない場合は sRGB を既定入力プロファイルとして扱う。出力時は CMYK JPEG 保存に加えて、ICC モードでは出力 ICC を明示的に埋め込む設計にする。Phase 1 に依存。
3. Phase 3: パス解決とバッチ処理を設計する。スクリプト位置基準で既定 ICC の絶対パスを解決し、カレントディレクトリに依存しないようにする。フォルダ入力時は JPEG 拡張子を列挙し、必要なら再帰探索を切り替えられるようにする。処理単位ごとに成功/失敗を収集し、最後に件数サマリを返す。Phase 2 と並行で詳細化できるが、実装は変換 API 確定後。
4. Phase 4: エラーハンドリングと終了コードを定義する。入力不存在、JPEG 以外、ICC ファイル不存在、Pillow/ImageCms 変換失敗、出力先競合を区別して扱う。単一ファイル時は即失敗、複数入力時は可能なものを継続処理して最終的に非ゼロ終了にする方針を採る。verify オプションでは出力画像を再オープンし、mode が CMYK であることと ICC 情報の有無を確認する。Phase 2 と Phase 3 に依存。
5. Phase 5: 配布しやすい構成にまとめる。CLI 本体をワークスペース直下に配置するか、将来の拡張を見据えて module 化するかを決める。現状はコードベースが空なので、初版は単一スクリプトでよいが、変換関数、入力列挙、CLI 引数処理は関数分離してテストしやすくする。README にはセットアップ、基本例、simple と ICC の違い、Windows での見え方の注意を記載する。requirements には Pillow を明記する。Phase 1 から Phase 4 の内容を反映。
6. Phase 6: 検証手順を用意する。単一 JPEG、複数 JPEG、フォルダ入力、カスタム ICC 指定、ICC 欠落、上書き拒否、simple/icc 切替を手動テストする。出力 JPEG を Pillow で再読込し mode と info を確認する。Windows 標準ビューアでの見え方は不安定なので、色の確認は ICC 対応ツールでも比較する。全フェーズ完了後に実施。
7. Phase 7: ドキュメントとコードの最終調整。README の内容を実装に合わせて更新し、誤字脱字や表現の不明瞭な部分を修正する。コード内に詳細なDocStringおよびコメントも追加して、処理の意図や注意点を明確にする。必要に応じて、CLI 引数のヘルプ文言も充実させる。全フェーズ完了後に実施。

**Relevant files**

- d:\programming\py_apps\RGB_to_CMYK_JPEGのRGBとCMYKの違い .md — simple 変換と ICC 変換の二系統、および色再現・ビューア互換性の注意点の参照元。
- d:\programming\py_apps\RGB_to_CMYK\JapanColor2011Coated\JapanColor2011Coated.icc — CLI の既定出力 ICC として使用するファイル。
- d:\programming\py_apps\RGB_to_CMYK\rgb_to_cmyk.py — 追加予定の CLI 本体。argparse、変換処理、入力列挙、終了コード管理を集約する想定。
- d:\programming\py_apps\RGB_to_CMYK\README.md — 追加予定の利用手順書。実行例と注意事項を記載する想定。
- d:\programming\py_apps\RGB_to_CMYK\requirements.txt — 追加予定の依存関係定義。Pillow を明記する想定。

**Verification**

1. 単一 RGB JPEG を simple モードで変換し、出力 JPEG が生成されること、再読込後の mode が CMYK であることを確認する。
2. 同じ入力を ICC モードで変換し、既定 ICC が解決されること、出力に ICC 情報が埋め込まれていることを確認する。
3. フォルダ入力で複数 JPEG をまとめて変換し、JPEG 以外が無視または明確に報告されること、失敗件数が終了コードやサマリに反映されることを確認する。
4. カスタム ICC 指定、存在しない ICC 指定、overwrite 未指定時の既存出力衝突を確認し、想定どおりのエラー文言と終了コードになることを確認する。
5. README 記載のコマンド例をそのまま実行して再現できることを確認する。

**Decisions**

- 初版から複数ファイル/フォルダ対応を含める。
- 変換方式は simple と icc の 2 モードを CLI オプションで切り替える。
- 既定出力 ICC は d:\programming\py_apps\RGB_to_CMYK\JapanColor2011Coated\JapanColor2011Coated.icc を使う。
- ドキュメント対象は README と requirements まで含める。
- 対象形式は JPEG を主対象とし、初版では PNG など他形式への一般化は含めない。

**Further Considerations**

1. 既定モードは icc を推奨する。理由はユーザー要件にある既定 ICC の活用意図と、simple 変換の色沈みリスクが明確だから。
2. フォルダ出力の既定先は専用出力ディレクトリの方が安全だが、元階層への \_cmyk 追記も簡便である。実装前に最終判断してもよい。
3. Pillow のバージョン差で ImageCms の built-in sRGB 取得方法が変わる場合があるため、実装時に利用可能 API を確認してフォールバックを設ける.
