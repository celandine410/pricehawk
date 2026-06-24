"""Server酱微信推送通知器"""
from __future__ import annotations

import os
from typing import Optional

import httpx


class ServerChanNotifier:
    """通过 Server酱 推送到微信"""

    BASE_URL = "https://sctapi.ftqq.com"

    def __init__(self, send_key: Optional[str] = None):
        self.send_key = send_key or os.getenv("SERVERCHAN_KEY", "")

    def is_configured(self) -> bool:
        return bool(self.send_key)

    async def send(
        self,
        title: str,
        content: str,
    ) -> bool:
        """发送微信推送，成功返回 True"""
        if not self.is_configured():
            print("[通知] Server酱未配置，跳过推送")
            return False

        url = f"{self.BASE_URL}/{self.send_key}.send"

        # Server酱内容最长有限制，分多个渠道
        payload = {
            "title": title[:150],
            "desp": content[:5000],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, data=payload)
                result = resp.json()
                if result.get("code") == 0 or result.get("errno") == 0:
                    print(f"[通知] 推送成功: {title[:30]}...")
                    return True
                else:
                    print(f"[通知] 推送失败: {result}")
                    return False
        except Exception as e:
            print(f"[通知] 推送异常: {e}")
            return False

    async def send_price_drop(self, product_name: str, platform: str,
                              old_price: float, new_price: float,
                              url: str) -> bool:
        """发送降价通知"""
        drop_percent = round((old_price - new_price) / old_price * 100, 1)
        symbol = "📉" if drop_percent > 0 else "📈"
        title = f"{symbol} 降价提醒：{product_name[:40]}"
        content = (
            f"## 🔔 降价提醒\n\n"
            f"**商品**：{product_name}\n\n"
            f"**平台**：{platform}\n\n"
            f"**原价**：¥{old_price:.2f}  →  **现价**：¥{new_price:.2f}\n\n"
            f"**降幅**：{drop_percent:.1f}%\n\n"
            f"---\n\n"
            f"[🔗 查看商品]({url})\n\n"
            f"*自动监控 · 比价鹰*"
        )
        return await self.send(title, content)

    async def send_arbitrage(self, product_name: str,
                             platform_a: str, price_a: float,
                             platform_b: str, price_b: float,
                             url_a: str, url_b: str) -> bool:
        """发送套利通知"""
        cheaper_platform = platform_a if price_a < price_b else platform_b
        expensive_platform = platform_b if price_a < price_b else platform_a
        cheaper_price = min(price_a, price_b)
        expensive_price = max(price_a, price_b)
        diff = expensive_price - cheaper_price
        diff_percent = round(diff / expensive_price * 100, 1)

        title = f"💰 套利机会：{product_name[:40]}"
        content = (
            f"## 💰 跨平台套利机会\n\n"
            f"**商品**：{product_name}\n\n"
            f"**{platform_a}**：¥{price_a:.2f}\n\n"
            f"**{platform_b}**：¥{price_b:.2f}\n\n"
            f"**差价**：¥{diff:.2f}（{diff_percent:.1f}%）\n\n"
            f"**便宜在**：{cheaper_platform}（¥{cheaper_price:.2f}）\n\n"
            f"---\n\n"
            f"[🔗 {platform_a}]({url_a})  |  [🔗 {platform_b}]({url_b})\n\n"
            f"*自动监控 · 比价鹰*"
        )
        return await self.send(title, content)
