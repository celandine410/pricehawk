"""配置加载器"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import yaml

from src.fetchers.base import MonitorConfig


def load_config(path: Optional[str] = None) -> List[MonitorConfig]:
    """加载监控配置"""
    if path is None:
        base = Path(__file__).resolve().parent.parent
        path = str(base / "config" / "items.yaml")

    if not os.path.exists(path):
        print(f"[配置] 文件不存在: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw or "items" not in raw:
        print("[配置] 未找到监控列表")
        return []

    items = []
    for item in raw["items"]:
        try:
            items.append(MonitorConfig(**item))
        except Exception as e:
            print(f"[配置] 跳过无效项: {item.get('name', 'unknown')} — {e}")

    print(f"[配置] 加载 {len(items)} 个监控项")
    return items
