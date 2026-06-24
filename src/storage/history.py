"""价格历史存储 — 使用 JSON 文件（Git 追踪，免费）"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from src.fetchers.base import ProductInfo


class PriceHistory:
    """价格历史管理器"""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            base = Path(__file__).resolve().parent.parent.parent
            data_dir = str(base / "data")
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    @property
    def _index_path(self) -> str:
        return os.path.join(self.data_dir, "_index.json")

    def _product_path(self, sku_id: str) -> str:
        return os.path.join(self.data_dir, f"{sku_id}.json")

    def load_index(self) -> Dict:
        """加载商品索引文件"""
        if os.path.exists(self._index_path):
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_index(self, index: Dict):
        """保存商品索引"""
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def load_history(self, sku_id: str) -> List[Dict]:
        """加载某个商品的价格历史"""
        path = self._product_path(sku_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_record(self, info: ProductInfo):
        """保存一条价格记录"""
        # 更新索引
        index = self.load_index()
        key = f"{info.platform}:{info.sku_id}"
        index[key] = {
            "name": info.title,
            "platform": info.platform,
            "sku_id": info.sku_id,
            "last_updated": info.url,
        }
        self.save_index(index)

        # 追加价格记录
        history = self.load_history(info.sku_id)
        record = {
            "price": info.current_price,
            "original_price": info.original_price,
            "title": info.title,
            "discount": info.discount,
        }
        history.append(record)

        # 最多保留 100 条
        if len(history) > 100:
            history = history[-100:]

        path = self._product_path(info.sku_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def get_latest_price(self, sku_id: str) -> Optional[float]:
        """获取某个商品的最新记录价格"""
        history = self.load_history(sku_id)
        if history:
            return history[-1].get("price")
        return None

    def get_latest_record(self, sku_id: str) -> Optional[Dict]:
        """获取某个商品的最新完整记录"""
        history = self.load_history(sku_id)
        if history:
            return history[-1]
        return None

    def has_no_history(self, sku_id: str) -> bool:
        """是否没有任何历史记录（首次监控）"""
        return len(self.load_history(sku_id)) == 0
