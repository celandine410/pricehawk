"""京东价格抓取器 — CSS + JS + API拦截三合一"""
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
                    user_agent="Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile",
                    viewport={"width": 375, "height": 812},
                    locale="zh-CN",
                )
                page = await context.new_page()

                page_url = f"https://item.m.jd.com/product/{sku_id}.html"
                print(f"  加载页面...")
                await page.goto(page_url, wait_until="load", timeout=30000)
                await page.wait_for_timeout(5000)

                # 三合一提取
                price = await self._extract_price(page, sku_id)

                title = await page.title()

                # 调试信息
                if price is None:
                    html = await page.content()
                    print(f"  页面标题: {title[:60] if title else 'N/A'}")
                    print(f"  HTML长度: {len(html)}")
                    body = await page.inner_text("body")
                    for m in re.finditer(r'[¥￥]?\s*(\d+\.\d{2})', body):
                        print(f"  含¥数字: {m.group(0)}")

                await browser.close()

                if price is None:
                    print(f"[京东] 无法提取价格")
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

    async def _extract_price(self, page, sku_id: str) -> Optional[float]:
        """三合一提取：CSS选择器 → JS变量 → API拦截"""
        all_prices = []

        # 1) CSS选择器
        selectors = [
            ".p-price", "#jd-price", ".summary-price",
            ".sale-price", ".p-price span.price",
        ]
        for sel in selectors:
            try:
                elements = await page.query_selector_all(sel)
                for el in elements:
                    text = await el.inner_text()
                    nums = re.findall(r'\d+\.?\d*', text.replace(",", ""))
                    for n in nums:
                        v = float(n)
                        if 10 <= v <= 9999:
                            all_prices.append(("CSS", sel, v))
            except Exception:
                continue

        # 2) JS变量
        js_queries = [
            """() => { try {
                if(window.pageConfig?.price)return window.pageConfig.price
            }catch(e){}return null}""",
            """() => { try {
                const ss=document.querySelectorAll('script');
                for(const s of ss){
                    const m=s.textContent.match(/["'](?:price|jdPrice|salePrice|p)["']\s*[:=]\s*["']?(\d+\.?\d*)/);
                    if(m){const v=parseFloat(m[1]);if(v>10&&v<9999)return v}
                }
            }catch(e){}return null}""",
        ]
        for js in js_queries:
            try:
                result = await page.evaluate(js)
                if result is not None:
                    v = float(result)
                    if 10 <= v <= 9999:
                        all_prices.append(("JS", "js_var", v))
                        break
            except Exception:
                continue

        # 3) 拦截API
        try:
            resp = await page.wait_for_response(
                "**p.3.cn/prices/mgets**", timeout=5000
            )
            if resp and resp.ok:
                data = await resp.json()
                if isinstance(data, list):
                    for item in data:
                        for k in ["p", "price", "jdPrice"]:
                            val = item.get(k)
                            if val:
                                v = float(val)
                                if 10 <= v <= 9999:
                                    all_prices.append(("API", "p.3.cn", v))
        except Exception:
            pass

        # 4) 全文正则
        body = await page.inner_text("body")
        for m in re.finditer(r'[¥￥](\d+\.?\d*)', body):
            v = float(m.group(1))
            if 10 <= v <= 9999:
                all_prices.append(("TEXT", "regex", v))

        # 选最小价格
        if all_prices:
            seen = set()
            unique = []
            for src, sel, v in all_prices:
                if v not in seen:
                    seen.add(v)
                    unique.append((src, sel, v))
            best = min(unique, key=lambda x: x[2])
            print(f"  {best[0]}[{best[1]}] → ¥{best[2]} (共{len(unique)}个候选)")
            return best[2]

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
