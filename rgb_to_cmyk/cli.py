"""RGB JPEG を CMYK JPEG に変換する CLI 本体。"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import cast

from PIL import Image, ImageCms, UnidentifiedImageError

DEFAULT_OUTPUT_PROFILE = (
    Path(__file__).resolve().parent.parent
    / "JapanColor2011Coated"
    / "JapanColor2011Coated.icc"
)
JPEG_EXTENSIONS = {".jpg", ".jpeg"}

EXIT_OK = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_INPUT_ERROR = 2
EXIT_PROFILE_ERROR = 3


class ConversionError(Exception):
    """変換処理全般で使う基底例外。"""

    pass


class InputValidationError(ConversionError):
    """入力パスや出力先指定に問題がある場合の例外。"""

    pass


class ProfileValidationError(ConversionError):
    """ICC プロファイルの解決や読込に失敗した場合の例外。"""

    pass


@dataclass(frozen=True)
class SourceItem:
    """入力ソースと、相対出力先を決める基準ディレクトリを束ねる。"""

    source: Path
    anchor: Path


def quality_value(raw_value: str) -> int:
    """JPEG 品質の引数を検証し、1 から 100 の整数へ正規化する。"""

    value = int(raw_value)
    if not 1 <= value <= 100:
        raise argparse.ArgumentTypeError("quality must be between 1 and 100")
    return value


def build_parser() -> argparse.ArgumentParser:
    """CLI の引数定義を組み立てる。"""

    parser = argparse.ArgumentParser(
        description="Convert RGB JPEG images to CMYK JPEG using simple or ICC-based conversion.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more JPEG files or directories containing JPEG files.",
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=("icc", "simple"),
        default="icc",
        help="Conversion mode. 'icc' preserves color intent with profiles; 'simple' uses Pillow's direct CMYK conversion.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path for a single resolved input image.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory where converted files are written. Directory structure is preserved for folder inputs.",
    )
    parser.add_argument(
        "--input-icc",
        help="Optional input ICC profile. If omitted, the image's embedded profile is used, otherwise sRGB is assumed.",
    )
    parser.add_argument(
        "--output-icc",
        default=str(DEFAULT_OUTPUT_PROFILE),
        help="Output ICC profile used in ICC mode.",
    )
    parser.add_argument(
        "-q",
        "--quality",
        type=quality_value,
        default=90,
        help="JPEG quality for converted files (1-100). Default: 90.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search directories for JPEG files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Re-open each output file and verify that it is CMYK. In ICC mode, also verify that an ICC profile is embedded.",
    )
    return parser


def is_jpeg_path(path: Path) -> bool:
    """対象ファイルが JPEG 拡張子かどうかを判定する。"""

    return path.suffix.lower() in JPEG_EXTENSIONS


def is_within_any(path: Path, parents: tuple[Path, ...]) -> bool:
    """path が除外対象ディレクトリ配下に含まれるかを返す。"""

    return any(path.is_relative_to(parent) for parent in parents)


def collect_sources(
    input_values: list[str],
    recursive: bool,
    excluded_dirs: tuple[Path, ...] = (),
) -> list[SourceItem]:
    """ファイル/ディレクトリ指定から変換対象の JPEG 一覧を収集する。"""

    collected: list[SourceItem] = []
    seen: set[Path] = set()

    for raw_input in input_values:
        path = Path(raw_input).expanduser().resolve()
        if not path.exists():
            raise InputValidationError(f"input path does not exist: {path}")

        if path.is_file():
            if not is_jpeg_path(path):
                raise InputValidationError(f"input file is not a JPEG: {path}")
            if path not in seen:
                seen.add(path)
                collected.append(SourceItem(source=path, anchor=path.parent))
            continue

        if not path.is_dir():
            raise InputValidationError(f"unsupported input path: {path}")

        # フォルダ入力では JPEG のみを抽出し、重複と除外パスを取り除く。
        iterator = path.rglob("*") if recursive else path.glob("*")
        for candidate in sorted(iterator):
            if not candidate.is_file() or not is_jpeg_path(candidate):
                continue
            resolved = candidate.resolve()
            if is_within_any(resolved, excluded_dirs):
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            collected.append(SourceItem(source=resolved, anchor=path))

    if not collected:
        raise InputValidationError("no JPEG files were found in the provided inputs")

    return collected


def resolve_output_path(
    item: SourceItem,
    output_path: Path | None,
    output_dir: Path | None,
) -> Path:
    """1 件分の変換結果を書き込む出力パスを決定する。"""

    if output_path is not None:
        return output_path

    if output_dir is not None:
        # ディレクトリ入力時は元の階層構造を保ちつつ、末尾に _cmyk を付ける。
        relative_path = item.source.relative_to(item.anchor)
        destination_dir = output_dir / relative_path.parent
        return destination_dir / f"{item.source.stem}_cmyk.jpg"

    return item.source.with_name(f"{item.source.stem}_cmyk.jpg")


def build_output_plan(
    items: list[SourceItem],
    output_path: Path | None,
    output_dir_path: Path | None,
) -> dict[Path, Path]:
    """収集済み入力に対して、競合のない出力先一覧を組み立てる。"""

    if output_path is not None and output_dir_path is not None:
        raise InputValidationError("--output and --output-dir cannot be used together")
    if output_path is not None and len(items) != 1:
        raise InputValidationError("--output can only be used when exactly one JPEG is resolved")

    plan: dict[Path, Path] = {}
    destinations: set[Path] = set()
    for item in items:
        destination = resolve_output_path(item, output_path, output_dir_path)
        if destination in destinations:
            raise InputValidationError(f"multiple inputs would write to the same output: {destination}")
        destinations.add(destination)
        plan[item.source] = destination
    return plan


def ensure_output_parent(destination: Path) -> None:
    """出力ファイルの親ディレクトリを事前に作成する。"""

    destination.parent.mkdir(parents=True, exist_ok=True)


def load_input_profile(source_image: Image.Image, input_icc_path: Path | None):
    """入力 ICC を解決する。

    優先順位は、明示指定された ICC、画像埋め込み ICC、最後に built-in sRGB。
    """

    if input_icc_path is not None:
        if not input_icc_path.is_file():
            raise ProfileValidationError(f"input ICC profile was not found: {input_icc_path}")
        return ImageCms.getOpenProfile(str(input_icc_path))

    embedded_profile = source_image.info.get("icc_profile")
    if embedded_profile:
        # Pillow は bytes のままでは使えないため、プロファイルオブジェクトへ包む。
        return ImageCms.ImageCmsProfile(BytesIO(embedded_profile))

    return ImageCms.createProfile("sRGB")


def convert_image(
    source: Path,
    destination: Path,
    mode: str,
    quality: int,
    overwrite: bool,
    verify: bool,
    input_icc_path: Path | None,
    output_icc_path: Path,
) -> None:
    """1 枚の JPEG を CMYK JPEG へ変換して保存する。"""

    if destination.exists() and not overwrite:
        raise InputValidationError(f"output already exists: {destination}")

    if mode == "icc" and not output_icc_path.is_file():
            # 変換処理は RGB 起点に揃えておくと simple/icc の双方で扱いやすい。
        raise ProfileValidationError(f"output ICC profile was not found: {output_icc_path}")

    ensure_output_parent(destination)

    try:
        with Image.open(source) as source_image:
            with source_image.convert("RGB") as rgb_image:
                if mode == "simple":
                    with rgb_image.convert("CMYK") as converted:
                # ICC 変換時は変換後 JPEG にも出力プロファイルを埋め込む。
                        converted.save(destination, format="JPEG", quality=quality)
                else:
                    input_profile = load_input_profile(source_image, input_icc_path)
                    output_profile = ImageCms.getOpenProfile(str(output_icc_path))
                    converted = cast(
                        Image.Image,
                        ImageCms.profileToProfile(
                            rgb_image,
                            input_profile,
                            output_profile,
                            outputMode="CMYK",
                        ),
                    )
                    with converted:
                        converted.save(
                            destination,
                            format="JPEG",
                            quality=quality,
                            icc_profile=output_icc_path.read_bytes(),
                        )
    except UnidentifiedImageError as exc:
        raise InputValidationError(f"failed to read image data from {source}: {exc}") from exc
    except OSError as exc:
        raise ConversionError(f"failed to convert {source}: {exc}") from exc

    if verify:
        verify_output(destination, expect_icc=(mode == "icc"))


def verify_output(destination: Path, expect_icc: bool) -> None:
    """保存後の画像を開き直し、モードと ICC 埋め込みを検証する。"""

    try:
        with Image.open(destination) as converted_image:
            if converted_image.mode != "CMYK":
                raise ConversionError(
                    f"verification failed for {destination}: expected CMYK but got {converted_image.mode}"
                )
            has_icc = bool(converted_image.info.get("icc_profile"))
            if expect_icc and not has_icc:
                raise ConversionError(
                    f"verification failed for {destination}: ICC profile is missing from the output"
                )
    except OSError as exc:
        raise ConversionError(f"failed to verify {destination}: {exc}") from exc


def print_error(message: str) -> None:
    """CLI 用のエラーメッセージを標準エラー出力へ送る。"""

    print(f"Error: {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント。

    引数の解決、対象列挙、各画像の変換、終了コードの決定までを担う。
    """

    parser = build_parser()
    args = parser.parse_args(argv)

    output_path = Path(args.output).expanduser().resolve() if args.output else None
    output_dir_path = Path(args.output_dir).expanduser().resolve() if args.output_dir else None

    try:
        # 出力先そのものを入力探索から外し、再変換のループを防ぐ。
        excluded_dirs = (output_dir_path,) if output_dir_path is not None else ()
        items = collect_sources(args.inputs, args.recursive, excluded_dirs=excluded_dirs)
        output_plan = build_output_plan(items, output_path, output_dir_path)
    except InputValidationError as exc:
        print_error(str(exc))
        return EXIT_INPUT_ERROR

    input_icc_path = Path(args.input_icc).expanduser().resolve() if args.input_icc else None
    output_icc_path = Path(args.output_icc).expanduser().resolve()

    successes = 0
    failures = 0
    saw_profile_error = False

    for item in items:
        destination = output_plan[item.source]
        try:
            convert_image(
                source=item.source,
                destination=destination,
                mode=args.mode,
                quality=args.quality,
                overwrite=args.overwrite,
                verify=args.verify,
                input_icc_path=input_icc_path,
                output_icc_path=output_icc_path,
            )
        except ProfileValidationError as exc:
            saw_profile_error = True
            failures += 1
            print_error(str(exc))
        except ConversionError as exc:
            failures += 1
            print_error(str(exc))
        else:
            successes += 1
            print(f"Converted: {item.source} -> {destination}")

    # バッチ変換では全件完了後に集計し、終了コードで状態を返す。
    print(f"Summary: {successes} succeeded, {failures} failed.")

    if failures == 0:
        return EXIT_OK
    if saw_profile_error:
        return EXIT_PROFILE_ERROR
    return EXIT_PARTIAL_FAILURE