"""python main.py からも CLI を起動できる薄いラッパー。"""

from rgb_to_cmyk.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
