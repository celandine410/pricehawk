"""京东价格抓取器 — Playwright API 拦截版"""
from __future__ import annotations

import json
import re
from typing import Optional

from playwright.async_api import async_playwright

from .base import BaseFetcher, ProductInfo


class JDFetcher(BaseFetcher):
    """京东价格抓取器"""

    PLATFORM = "jd"

    async def fetch(self, url: str) -> Optional[ProductInfo]:
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
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
                    viewport={"width": 1440, "height": 900},
                    locale="zh-CN",
                )
                page = await context.new_page()

                print(f"  加载页面...")
                await page.goto(url, wait_until="load", timeout=30000)

                # 从页面 JS 变量中提取价格
                price = await self._extract_price_from_js(page)

                # 如果 JS 取不到，等网络响应
                if price is None:
                    price = await self._wait_for_price_api(page, sku_id)

                # 如果还是没有，再等一会重试 JS
                if price is None:
                    await page.wait_for_timeout(5000)
                    price = await self._extract_price_from_js(page)

                title = await page.title()
                await browser.close()

                if price is None:
                    print(f"[京东] 所有方式都无法获取价格")
                    return None

                if title:
                    for s in ["【", " [", " - 京东"]:
                        if s in title:
                            title = title.split(s)[0].strip()
                    title = title[:80]

                print(f"  → ¥{price}")
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

    async def _extract_price_from_js(self, page) -> Optional[float]:
        """从页面 JS 变量中提取价格"""
        js_queries = [
            # pageConfig
            """() => { try {
                if (window.pageConfig?.price) return window.pageConfig.price;
            } catch(e) {} return null; }""",

            # 从 JSON script 中搜索
            """() => { try {
                const scripts = document.querySelectorAll('script');
                for (const s of scripts) {
                    const t = s.textContent || '';
                    const ms = t.match(/(?:jdPrice|price|salePrice)\s*[:=]\s*["']?(\d+\.?\d*)/gi);
                    if (ms) {
                        for (const m of ms) {
                            const n = m.match(/(\d+\.?\d*)/);
                            if (n) {
                                const v = parseFloat(n[1]);
                                if (v > 10 && v < 9999) return v;
                            }
                        }
                    }
                }
            } catch(e) {} return null; }""",

            # 搜索 HTML 内容中 ¥ 符号附近的价格
            """() => { try {
                const body = document.body.innerText;
                const ms = body.match(/[¥￥]\s*(\d+\.?\d*)/g);
                if (ms) {
                    for (const m of ms) {
                        const n = m.match(/(\d+\.?\d*)/);
                        if (n) {
                            const v = parseFloat(n[1]);
                            if (v > 10 && v < 9999) return v;
                        }
                    }
                }
            } catch(e) {} return null; }""",
        ]

        for i, js in enumerate(js_queries):
            try:
                result = await page.evaluate(js)
                if result is not None:
                    val = float(result)
                    if 10 <= val <= 9999:
                        print(f"  JS变量[{i}] → ¥{val}")
                        return val
            except Exception:
                continue
        return None

    async def _wait_for_price_api(self, page, sku_id: str) -> Optional[float]:
        """等待并拦截京东价格 API 响应"""
        # 京东的价格 API 模式
        api_patterns = [
            f"**/p.3.cn/prices/mgets**skuIds=J_{sku_id}**",
            f"**/p.3.cn/prices/mgets**{sku_id}**",
            "**/p.3.cn/prices/mgets**",
            "**/price/**",
            "**/getPrice**",
        ]

        for pattern in api_patterns:
            try:
                response = await page.wait_for_response(pattern, timeout=8000)
                if response and response.ok:
                    body = await response.text()
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError:
                        continue
                    # 解析 [{id: "J_xxx", p: "79.00"}, ...]
                    if isinstance(data, list):
                        for item in data:
                            for key in ["p", "price", "jdPrice"]:
                                val = item.get(key)
                                if val:
                                    v = float(val)
                                    if 10 <= v <= 9999:
                                        print(f"  API拦截 → ¥{v}")
                                        return v
            except Exception:
                continue
        return None

    @staticmethod
    def _extract_sku(url: str) -> Optional[str]:
        m = re.search(r'item\.jd\.com/(\d+)\.html', url)
        if m:
            return m.group(1)
        m = re.search(r'/(\d+)\.html', url)
        if m:
            return m.group(1)
        return None
