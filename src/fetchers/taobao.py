"""淘宝/天猫价格抓取器 — Playwright JS 变量提取版"""
from __future__ import annotations

import json
import re
from typing import Optional

from playwright.async_api import async_playwright

from .base import BaseFetcher, ProductInfo


class TaobaoFetcher(BaseFetcher):
    """淘宝/天猫价格抓取器"""

    PLATFORM = "taobao"

    async def fetch(self, url: str) -> Optional[ProductInfo]:
        sku_id = self._extract_sku_id(url)
        if not sku_id:
            print(f"[淘宝] 无法提取商品ID: {url[:50]}")
            return None

        print(f"  商品ID: {sku_id}")

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile",
                    viewport={"width": 375, "height": 812},
                    locale="zh-CN",
                )
                page = await context.new_page()

                page_url = f"https://m.taobao.com/item.htm?id={sku_id}"
                print(f"  加载页面...")
                await page.goto(page_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)

                # 从 JS 变量中提取价格
                price = await self._extract_price_from_js(page)

                # 如果 JS 变量没有，尝试从网络响应中拦截
                if price is None:
                    price = await self._extract_price_from_api(page)

                title = await page.title()
                await browser.close()

                if price is None:
                    print(f"[淘宝] 无法从页面提取价格")
                    return None

                if title:
                    for s in ["-淘宝", "-天猫", " - taobao", "-tmall", "-淘宝网"]:
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
            print(f"[淘宝] Playwright 异常: {type(e).__name__}: {str(e)[:100]}")
            return None

    async def _extract_price_from_js(self, page) -> Optional[float]:
        """从页面 JavaScript 变量中提取价格"""
        js_queries = [
            # 淘宝 React 状态（Rax/SSR）
            """() => { try {
                const s = document.getElementById('__INITIAL_STATE__');
                if (s) {
                    const d = JSON.parse(s.textContent);
                    return d?.item?.price || d?.detail?.item?.price || d?.data?.item?.price;
                }
            } catch(e) {} return null; }""",

            # 淘宝 g_config / __g
            """() => { try {
                if (window.g_config?.price) return window.g_config.price;
                if (window.__g?.price) return window.__g.price;
                if (window.GLOBAL_CONFIG?.price) return window.GLOBAL_CONFIG.price;
            } catch(e) {} return null; }""",

            # 搜索页内嵌数据
            """() => { try {
                const scripts = document.querySelectorAll('script[type="application/json"]');
                for (const s of scripts) {
                    const d = JSON.parse(s.textContent);
                    const p = d?.price || d?.data?.price || d?.item?.price;
                    if (p && parseFloat(p) > 10) return p;
                }
            } catch(e) {} return null; }""",

            # 从所有 script 中搜索价格
            """() => { try {
                const scripts = document.querySelectorAll('script');
                for (const s of scripts) {
                    const t = s.textContent || '';
                    const m = t.match(/"(?:price|currentPrice|defPrice|salePrice)"\s*:\s*["']?(\d+\.?\d*)/);
                    if (m) {
                        const v = parseFloat(m[1]);
                        if (v > 10 && v < 99999) return v;
                    }
                }
            } catch(e) {} return null; }""",
        ]

        for i, js in enumerate(js_queries):
            try:
                result = await page.evaluate(js)
                if result is not None:
                    # 处理可能返回的字符串
                    val = float(str(result).split("-")[0].split("~")[0])
                    if 10 <= val <= 9999:
                        print(f"  JS变量[{i}] → ¥{val}")
                        return val
            except Exception as e:
                continue

        return None

    async def _extract_price_from_api(self, page) -> Optional[float]:
        """拦截淘宝价格 API 响应"""
        api_patterns = [
            "**/mtop.taobao.detail.getdetail/**",
            "**/h5/**",
            "**/api/**item**",
            "**/detail/**",
        ]

        for pattern in api_patterns:
            try:
                # 重新加载页面并等待 API
                response = await page.wait_for_response(pattern, timeout=8000)
                if response and response.ok:
                    try:
                        data = await response.json()
                        # 递归搜索 price 字段
                        val = self._find_price_in_json(data)
                        if val:
                            print(f"  API拦截 → ¥{val}")
                            return val
                    except Exception:
                        pass
            except Exception:
                continue
        return None

    @staticmethod
    def _find_price_in_json(data, depth=0) -> Optional[float]:
        """递归在 JSON 中寻找价格"""
        if depth > 5:
            return None
        if isinstance(data, dict):
            for key in ["price", "currentPrice", "defPrice", "salePrice", "reservePrice"]:
                val = data.get(key)
                if val:
                    try:
                        v = float(str(val).split("-")[0].split("~")[0])
                        if 10 <= v <= 9999:
                            return v
                    except (ValueError, TypeError):
                        pass
            for v in data.values():
                result = TaobaoFetcher._find_price_in_json(v, depth + 1)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data[:5]:
                result = TaobaoFetcher._find_price_in_json(item, depth + 1)
                if result:
                    return result
        return None

    @staticmethod
    def _extract_sku_id(url: str) -> Optional[str]:
        m = re.search(r'[?&]id=(\d+)', url)
        if m:
            return m.group(1)
        m = re.search(r'[?&]item_id=(\d+)', url)
        if m:
            return m.group(1)
        return None
