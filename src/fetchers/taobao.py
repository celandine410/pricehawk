"""淘宝/天猫价格抓取器 — Playwright 浏览器渲染版"""
from __future__ import annotations

import re
from typing import Optional

from playwright.async_api import async_playwright

from .base import BaseFetcher, ProductInfo


class TaobaoFetcher(BaseFetcher):
    """淘宝/天猫价格抓取器"""

    PLATFORM = "taobao"

    async def fetch(self, url: str) -> Optional[ProductInfo]:
        """用 Playwright 渲染淘宝页面并提取价格"""
        sku_id = self._extract_sku_id(url)
        if not sku_id:
            print(f"[淘宝] 无法提取商品ID: {url[:50]}")
            return None

        print(f"  商品ID: {sku_id}")

        # 移动版页面更容易加载
        page_url = f"https://m.taobao.com/item.htm?id={sku_id}"

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Linux; Android 13) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Mobile Safari/537.36"
                    ),
                    viewport={"width": 375, "height": 812},
                    locale="zh-CN",
                )
                page = await context.new_page()

                # 导航到商品页
                print(f"  加载页面...")
                await page.goto(page_url, wait_until="networkidle", timeout=30000)

                # 额外等待渲染
                await page.wait_for_timeout(3000)

                # 提取标题
                title = await page.title()

                # 提取价格
                price = await self._extract_price(page)

                await browser.close()

                if price is None:
                    print(f"[淘宝] 页面加载完成但未找到价格")
                    return None

                # 标题清理
                if title:
                    for s in ["-淘宝", "-天猫", " - taobao", "-tmall", "-淘宝网"]:
                        if s in title:
                            title = title.split(s)[0].strip()
                    title = title[:80]

                return ProductInfo(
                    platform=self.PLATFORM,
                    url=url,
                    sku_id=sku_id,
                    title=title or sku_id,
                    current_price=price,
                    in_stock=True,
                )

        except Exception as e:
            print(f"[淘宝] Playwright 异常: {type(e).__name__}: {str(e)[:100]}")
            return None

    @staticmethod
    async def _extract_price(page) -> Optional[float]:
        """从渲染后的页面提取价格"""
        selectors = [
            # 淘宝/天猫移动版价格元素
            ".tm-price",
            ".price",
            ".tb-rmb-num",
            "[class*='price']",
            "[class*='Price']",
            ".J_originalPrice",
        ]

        for selector in selectors:
            try:
                el = await page.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    text = text.strip()
                    nums = re.findall(r'\d+\.?\d*', text.replace(",", ""))
                    for n in nums:
                        val = float(n)
                        if 1 < val < 99999:
                            print(f"  选择器 '{selector}' → ¥{val}")
                            return val
            except Exception:
                continue

        # 备用：全文正则
        body_text = await page.inner_text("body")
        patterns = [
            r'¥\s*(\d+\.?\d*)',
            r'￥\s*(\d+\.?\d*)',
            r'"price"\s*[:=]\s*["\']?(\d+\.?\d*)',
            r'"currentPrice"\s*[:=]\s*["\']?(\d+\.?\d*)',
        ]
        for pat in patterns:
            m = re.search(pat, body_text)
            if m:
                val = float(m.group(1))
                if 1 < val < 99999:
                    print(f"  正则 '{pat}' → ¥{val}")
                    return val

        return None

    @staticmethod
    def _extract_sku_id(url: str) -> Optional[str]:
        """从 URL 提取商品ID"""
        m = re.search(r'[?&]id=(\d+)', url)
        if m:
            return m.group(1)
        m = re.search(r'[?&]item_id=(\d+)', url)
        if m:
            return m.group(1)
        return None
