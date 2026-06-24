"""跨平台套利检测分析器"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.fetchers.base import ProductConfig, ProductInfo
from src.notifiers.serverchan import ServerChanNotifier


class ArbitrageAnalyzer:
    """检测同一商品在不同平台的价差"""

    def __init__(self, notifier: ServerChanNotifier):
        self.notifier = notifier

    async def check(
        self,
        config: ProductConfig,
        results: Dict[str, ProductInfo],
    ) -> bool:
        """检查跨平台价差，通知套利机会。返回 True 表示推送了"""
        # 需要有至少两个平台的价格数据
        fetched = {k: v for k, v in results.items() if v is not None}
        if len(fetched) < 2:
            return False

        # 找出最低价和最高价
        prices: List[Tuple[str, float, str]] = []  # (platform, price, url)
        for platform, info in fetched.items():
            prices.append((platform, info.current_price, info.url))

        prices.sort(key=lambda x: x[1])
        cheapest = prices[0]
        most_expensive = prices[-1]

        diff = most_expensive[1] - cheapest[1]
        if diff < config.arbitrage_threshold:
            return False  # 差价不够大

        print(f"[套利] {config.name}: {cheapest[0]}¥{cheapest[1]} vs {most_expensive[0]}¥{most_expensive[1]}")
        await self.notifier.send_arbitrage(
            product_name=config.name,
            platform_a=cheapest[0],
            price_a=cheapest[1],
            platform_b=most_expensive[0],
            price_b=most_expensive[1],
            url_a=cheapest[2],
            url_b=most_expensive[2],
        )
        return True
