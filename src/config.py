"""产品配置加载器"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from src.fetchers.base import ProductConfig


def load_products(path: Optional[str] = None) -> List[ProductConfig]:
    """从 YAML 文件加载商品配置"""
    if path is None:
        # 默认路径：项目根目录下的 config/
        base = Path(__file__).resolve().parent.parent
        path = str(base / "config" / "products.yaml")

    if not os.path.exists(path):
        print(f"[配置] 文件不存在: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw or "products" not in raw:
        print("[配置] 未找到商品列表")
        return []

    products = []
    for item in raw["products"]:
        try:
            products.append(ProductConfig(**item))
        except Exception as e:
            print(f"[配置] 跳过无效项: {item.get('name', 'unknown')} — {e}")

    print(f"[配置] 加载 {len(products)} 个商品")
    return products
