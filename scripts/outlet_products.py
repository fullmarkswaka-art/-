# -*- coding: utf-8 -*-
"""互換ラッパー。本体は `python -m ads_manager meta catalog-attributes`。

サイトのカテゴリ巡回で brand / custom_label_0(outlet|regular) / custom_label_1(シリーズ)
を補完した補助フィード CSV を reports/catalog_attributes.csv に生成する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ads_manager.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["meta", "catalog-attributes", *sys.argv[1:]]))
