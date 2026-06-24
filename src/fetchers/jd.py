"""京东价格抓取器 — Playwright 浏览器渲染版"""
from __future__ import annotations

import re
from typing import Optional

from playwright.async_api import async_playwright

from .base import BaseFetcher, ProductInfo


class JDFetcher(BaseFetcher):
    """京东价格抓取器"""

    PLATFORM = "jd"

    PRICE_SELECTORS = [
        ".p-price",
        "#jd-price",
        ".summary-price",
        ".sale-price",
        ".p-price span.price",
    ]

    async def fetch(self, url: str) -> Optional[ProductInfo]:
        """用 Playwright 渲染京东桌面页面并提取价格"""
        sku_id = self._extract_sku(url)
        if not sku_id:
            print(f"[京东] 无法提取 SKU: {url[:50]}")
            return None

        print(f"  SKU: {sku_id}")

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1440, "height": 900},
                    locale="zh-CN",
                )
                page = await context.new_page()

                print(f"  加载页面...")
                # 桌面版页面，用 load 不会被 XHR 拖死
                await page.goto(url, wait_until="load", timeout=30000)

                print(f"  等待价格渲染...")
                await page.wait_for_timeout(5000)

                price = await self._extract_price(page)

                title = await page.title()

                await browser.close()

                if price is None:
                    print(f"[京东] 页面加载完成但未找到价格")
                    return None

                if title:
                    for s in ["【", " [", " - 京东"]:
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
            print(f"[京东] Playwright 异常: {type(e).__name__}: {str(e)[:100]}")
            return None

    async def _extract_price(self, page) -> Optional[float]:
        """多层价格提取策略"""

        # 1) CSS 选择器
        for selector in self.PRICE_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    text = await el.inner_text()
                    text = text.strip()
                    if not text:
                        continue
                    nums = re.findall(r'\d+\.?\d*', text.replace(",", ""))
                    for n in nums:
                        val = float(n)
                        if 10 <= val <= 9999:
                            print(f"  选择器 '{selector}' → ¥{val}")
                            return val
            except Exception:
                continue

        # 2) HTML 源码正则
        html = await page.content()
        html_patterns = [
            r'"price"\s*[:=]\s*["\']?(\d+\.?\d*)',
            r'"p"\s*[:=]\s*["\']?(\d+\.?\d*)',
            r'"jdPrice"\s*[:=]\s*["\']?(\d+\.?\d*)',
            r'pageConfig\.price\s*=\s*(\d+\.?\d*)',
        ]
        for pat in html_patterns:
            m = re.search(pat, html)
            if m:
                val = float(m.group(1))
                if 10 <= val <= 9999:
                    print(f"  源码正则 → ¥{val}")
                    return val

        # 3) 页面正文正则
        body_text = await page.inner_text("body")
        body_patterns = [
            r'¥\s*(\d+\.?\d*)',
            r'￥\s*(\d+\.?\d*)',
        ]
        for pat in body_patterns:
            for m in re.finditer(pat, body_text):
                val = float(m.group(1))
                if 10 <= val <= 9999:
                    print(f"  正文正则 → ¥{val}")
                    return val

        # 4) 等2秒再试（延迟加载的价格）
        print(f"  等待延迟加载...")
        await page.wait_for_timeout(2000)
        for selector in self.PRICE_SELECTORS:
            try:
                el = await page.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    nums = re.findall(r'\d+\.?\d*', text.replace(",", ""))
                    for n in nums:
                        val = float(n)
                        if 10 <= val <= 9999:
                            print(f"  延时重试 → ¥{val}")
                            return val
            except Exception:
                continue

        return None

    @staticmethod
    def _extract_sku(url: str) -> Optional[str]:
        """提取京东商品 SKU ID"""
        m = re.search(r'item\.jd\.com/(\d+)\.html', url)
        if m:
            return m.group(1)
        m = re.search(r'/(\d+)\.html', url)
        if m:
            return m.group(1)
        return None
