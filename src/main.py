"""比价鹰主入口 — GitHub Actions 调度入口"""
from __future__ import annotations

import asyncio
import sys
from typing import Dict, Optional

from src.config import load_products
from src.fetchers import TaobaoFetcher, JDFetcher, BaseFetcher
from src.fetchers.base import ProductConfig, ProductInfo
from src.storage.history import PriceHistory
from src.notifiers.serverchan import ServerChanNotifier
from src.analyzers import PriceDropAnalyzer, ArbitrageAnalyzer


async def main():
    """主流程：加载配置 → 抓取所有商品 → 价格对比 → 推送通知"""
    print("=" * 40)
    print("  比价鹰 PriceHawk v0.1")
    print("=" * 40)

    # 1. 加载配置
    products = load_products()
    if not products:
        print("[主] 没有配置任何商品，退出")
        return

    # 2. 初始化组件
    notifier = ServerChanNotifier()
    history = PriceHistory()
    drop_analyzer = PriceDropAnalyzer(history, notifier)
    arbitrage_analyzer = ArbitrageAnalyzer(notifier)

    # 3. 初始化抓取器
    fetchers: Dict[str, BaseFetcher] = {
        "taobao": TaobaoFetcher(),
        "jd": JDFetcher(),
    }

    # 4. 逐个商品处理
    for product in products:
        print(f"\n--- 检查: {product.name} ---")
        results: Dict[str, Optional[ProductInfo]] = {}

        # 获取该商品各平台的 URL 映射
        platform_urls = {
            "taobao": product.taobao_url,
            "jd": product.jd_url,
        }

        # 逐个平台抓取
        for platform, url in platform_urls.items():
            if not url:
                continue
            fetcher = fetchers.get(platform)
            if not fetcher:
                continue

            print(f"  抓取 [{platform}] ... ", end="")
            info = await fetcher.fetch(url)
            if info:
                print(f"¥{info.current_price}")
                results[platform] = info
            else:
                print("失败")

        # 没有成功抓取到任何数据
        if not results:
            print("  所有平台都失败了，跳过")
            continue

        # 5. 降价检测（对每个成功抓取的平台）
        for platform, info in results.items():
            if info:
                await drop_analyzer.check(product, info)

        # 6. 跨平台套利检测
        await arbitrage_analyzer.check(product, results)

    print("\n✅ 本轮检查完成")


if __name__ == "__main__":
    asyncio.run(main())
