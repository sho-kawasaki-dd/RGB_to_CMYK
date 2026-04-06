"""rgb_to_cmyk.cli の主要な振る舞いを検証するテスト。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from rgb_to_cmyk.cli import (
    EXIT_INPUT_ERROR,
    EXIT_OK,
    EXIT_PROFILE_ERROR,
    collect_sources,
    main,
)


def create_rgb_jpeg(path: Path, color: tuple[int, int, int]) -> Path:
    """テスト用の最小 RGB JPEG を指定パスへ生成する。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (16, 16), color)
    image.save(path, format="JPEG", quality=95)
    image.close()
    return path


def test_main_simple_conversion_creates_cmyk_output(tmp_path: Path, capsys) -> None:
    """simple モードでは CMYK JPEG が生成され、ICC は埋め込まれない。"""

    source = create_rgb_jpeg(tmp_path / "sample.jpg", (255, 64, 32))
    output = tmp_path / "simple_out" / "sample_cmyk.jpg"

    exit_code = main(
        [
            str(source),
            "--mode",
            "simple",
            "--output-dir",
            str(tmp_path / "simple_out"),
            "--verify",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert "1 succeeded, 0 failed" in captured.out
    assert output.exists()

    # simple モードは Pillow の直接変換なので、ICC 埋め込みまでは行わない。
    with Image.open(output) as converted:
        assert converted.mode == "CMYK"
        assert "icc_profile" not in converted.info


def test_main_icc_batch_conversion_embeds_icc_and_preserves_tree(tmp_path: Path, capsys) -> None:
    """icc モードのバッチ変換で階層構造と ICC 埋め込みが保たれる。"""

    source_dir = tmp_path / "images"
    create_rgb_jpeg(source_dir / "first.jpg", (240, 80, 20))
    create_rgb_jpeg(source_dir / "nested" / "second.jpg", (20, 120, 240))
    output_dir = tmp_path / "converted"

    exit_code = main(
        [
            str(source_dir),
            "--output-dir",
            str(output_dir),
            "--recursive",
            "--verify",
            "--overwrite",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert "2 succeeded, 0 failed" in captured.out

    # ディレクトリ入力ではネストした相対パスを保ったまま出力される。
    outputs = [
        output_dir / "first_cmyk.jpg",
        output_dir / "nested" / "second_cmyk.jpg",
    ]
    for output in outputs:
        assert output.exists()
        with Image.open(output) as converted:
            assert converted.mode == "CMYK"
            assert bool(converted.info.get("icc_profile"))


def test_collect_sources_excludes_output_directory(tmp_path: Path) -> None:
    """出力ディレクトリを除外すると、生成済み JPEG を再入力として拾わない。"""

    source_dir = tmp_path / "images"
    create_rgb_jpeg(source_dir / "original.jpg", (10, 20, 30))
    create_rgb_jpeg(source_dir / "out" / "generated.jpg", (30, 20, 10))

    items = collect_sources(
        [str(source_dir)],
        recursive=True,
        excluded_dirs=((source_dir / "out").resolve(),),
    )

    assert [item.source.name for item in items] == ["original.jpg"]


def test_main_returns_input_error_for_missing_path(tmp_path: Path, capsys) -> None:
    """存在しない入力パスでは入力エラー終了コードを返す。"""

    exit_code = main([str(tmp_path / "missing.jpg")])

    captured = capsys.readouterr()
    assert exit_code == EXIT_INPUT_ERROR
    assert "input path does not exist" in captured.err


def test_main_returns_profile_error_for_missing_output_icc(tmp_path: Path, capsys) -> None:
    """存在しない出力 ICC 指定ではプロファイルエラー終了コードを返す。"""

    source = create_rgb_jpeg(tmp_path / "sample.jpg", (200, 100, 50))

    exit_code = main(
        [
            str(source),
            "--output-dir",
            str(tmp_path / "out"),
            "--output-icc",
            str(tmp_path / "missing.icc"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == EXIT_PROFILE_ERROR
    assert "output ICC profile was not found" in captured.err