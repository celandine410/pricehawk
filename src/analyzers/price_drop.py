"""降价检测分析器"""
from __future__ import annotations

from typing import Optional

from src.fetchers.base import ProductConfig, ProductInfo
from src.storage.history import PriceHistory
from src.notifiers.serverchan import ServerChanNotifier


class PriceDropAnalyzer:
    """检测商品是否降价并推送通知"""

    def __init__(self, history: PriceHistory, notifier: ServerChanNotifier):
        self.history = history
        self.notifier = notifier

    async def check(self, config: ProductConfig, info: ProductInfo) -> bool:
        """检查是否降价，如有则推送通知。返回 True 表示推送了告警"""
        sku_key = f"{info.platform}:{info.sku_id}"

        # 首次记录，没有历史对比
        if self.history.has_no_history(info.sku_id):
            self.history.save_record(info)
            return False

        last_record = self.history.get_latest_record(info.sku_id)
        if last_record is None:
            self.history.save_record(info)
            return False

        last_price = last_record.get("price", info.current_price)

        # 保存当前记录（在对比之后）
        self.history.save_record(info)

        # 价格没变
        if last_price == info.current_price:
            return False

        # 价格上涨了（涨价不告警，只记录）
        if info.current_price > last_price:
            print(f"[分析] {config.name} 涨价: ¥{last_price}→¥{info.current_price}")
            return False

        # 降价了
        drop_percent = (last_price - info.current_price) / last_price * 100

        # 检查是否满足目标价条件
        meets_target = False
        if config.target_price is not None and info.current_price <= config.target_price:
            meets_target = True

        # 检查是否满足跌幅阈值
        meets_drop = drop_percent >= config.drop_threshold

        if meets_target or meets_drop:
            print(f"[分析] {config.name} 降价 {drop_percent:.1f}%，推送告警")
            await self.notifier.send_price_drop(
                product_name=config.name,
                platform=info.platform,
                old_price=last_price,
                new_price=info.current_price,
                url=info.url,
            )
            return True

        return False
