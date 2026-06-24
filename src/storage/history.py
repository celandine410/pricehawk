"""数值历史存储 - JSON 文件"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class ValueHistory:
    """通用数值历史管理器"""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            base = Path(__file__).resolve().parent.parent.parent
            data_dir = str(base / "data")
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def _path(self, item_id: str) -> str:
        return os.path.join(self.data_dir, f"{item_id}.json")

    def is_first(self, item_id: str) -> bool:
        return not os.path.exists(self._path(item_id))

    def get_latest(self, item_id: str) -> Optional[float]:
        path = self._path(item_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
        if records:
            return records[-1].get("value")
        return None

    def save(self, item_id: str, value: float):
        records = []
        path = self._path(item_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                records = json.load(f)
        records.append({"value": value})
        if len(records) > 100:
            records = records[-100:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
