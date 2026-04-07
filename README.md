# RGB to CMYK CLI

RGB カラーモードの JPEG を CMYK JPEG に変換する CLI です。Pillow を使った単純変換と、ICC プロファイルを使う色変換を切り替えられます。

既定では [JapanColor2011Coated/JapanColor2011Coated.icc](JapanColor2011Coated/JapanColor2011Coated.icc) を出力 ICC として使います。ICCファイルは同梱していないので、
[こちら](https://japancolor.jp/icc.html)からダウンロードして、プロジェクトルートの `JapanColor2011Coated` フォルダ内に置いてください。
## Setup

```bash
uv sync
```

## Basic usage

単一ファイルを ICC モードで変換します。

```bash
uv run rgb-to-cmyk input.jpg
```

出力先を指定します。

```bash
uv run rgb-to-cmyk input.jpg --output output_cmyk.jpg
```

フォルダ内の JPEG をまとめて変換します。

```bash
uv run rgb-to-cmyk images --output-dir converted
```

サブフォルダも含めて変換します。

```bash
uv run rgb-to-cmyk images --output-dir converted --recursive
```

単純変換に切り替えます。

```bash
uv run rgb-to-cmyk input.jpg --mode simple
```

入力 ICC を明示します。

```bash
uv run rgb-to-cmyk input.jpg --input-icc path/to/input.icc
```

## Options

- `inputs`: 単一または複数の JPEG ファイル、または JPEG を含むディレクトリ
- `--mode {icc,simple}`: 変換方式。既定は `icc`
- `--output`: 単一の変換結果を書き込むファイルパス
- `--output-dir`: 変換結果の出力先ディレクトリ
- `--input-icc`: 入力 ICC プロファイル。未指定時は埋め込み ICC を優先し、なければ sRGB を仮定
- `--output-icc`: 出力 ICC プロファイル。既定は Japan Color 2011 Coated
- `--quality`: JPEG 品質。既定は `90`
- `--recursive`: ディレクトリ入力時にサブディレクトリも探索
- `--overwrite`: 既存出力を上書き
- `--verify`: 出力 JPEG を再読込し、CMYK と ICC 埋め込みを検証

## Notes

- `simple` モードは `Image.convert("CMYK")` を使うため、鮮やかな色が沈みやすいです。
- `icc` モードでは出力 JPEG に ICC を埋め込みます。
- Windows の標準ビューアや一部ブラウザでは CMYK JPEG の見え方が不安定なことがあります。
- 対象形式は JPEG のみです。PNG などは初版では扱いません。
