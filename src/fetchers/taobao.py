"""淘宝/天猫价格抓取器 — CSS + JS + 正则三合一"""
from __future__ import annotations

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
                await page.goto(page_url, wait_until="load", timeout=30000)
                await page.wait_for_timeout(5000)

                # CSS选择器 → JS变量 → 正则 三合一
                price = await self._extract_price(page)

                # 标题
                title = await page.title()

                # 调试：如果没拿到价格，打印部分页面信息
                if price is None:
                    html = await page.content()
                    title2 = await page.title()
                    print(f"  页面标题: {title2[:60]}")
                    print(f"  HTML长度: {len(html)}")
                    # 搜一下页面上有没有数字
                    body = await page.inner_text("body")
                    nums = re.findall(r'[¥￥]?\s*(\d+\.\d{2})', body)
                    if nums:
                        print(f"  页面上含¥的数字: {nums[:5]}")

                await browser.close()

                if price is None:
                    print(f"[淘宝] 无法提取价格")
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

    async def _extract_price(self, page) -> Optional[float]:
        """三合一价格提取：CSS选择器 → JS变量 → 全文正则"""
        all_prices = []

        # 1) CSS选择器
        selectors = [
            ".tm-price", ".tb-rmb-num", ".price-current",
            ".J_StrPr498", ".tm-promo-price .tm-price",
            "[class*='price']", "[class*='Price']",
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
                const s = document.getElementById('__INITIAL_STATE__');
                if(s){const d=JSON.parse(s.textContent);return d?.item?.price||d?.detail?.item?.price||d?.data?.item?.price}
            }catch(e){}return null}""",
            """() => { try {
                if(window.g_config?.price)return window.g_config.price;
                if(window.__g?.price)return window.__g.price;
            }catch(e){}return null}""",
            """() => { try {
                const ss=document.querySelectorAll('script');
                for(const s of ss){
                    const m=s.textContent.match(/["'](?:price|currentPrice|defPrice|salePrice|reservePrice)["']\\s*[:=]\\s*["']?(\\d+\\.?\\d*)/);
                    if(m){const v=parseFloat(m[1]);if(v>10&&v<9999)return v}
                }
            }catch(e){}return null}""",
        ]
        for js in js_queries:
            try:
                result = await page.evaluate(js)
                if result is not None:
                    v = float(str(result).split("-")[0].split("~")[0])
                    if 10 <= v <= 9999:
                        all_prices.append(("JS", "js_var", v))
                        break
            except Exception:
                continue

        # 3) 全文正则
        body = await page.inner_text("body")
        for m in re.finditer(r'[¥￥](\d+\.?\d*)', body):
            v = float(m.group(1))
            if 10 <= v <= 9999:
                all_prices.append(("TEXT", "regex_¥", v))

        # 从候选价格中选最小那个（通常是真实售价）
        if all_prices:
            # 去重
            seen = set()
            unique = []
            for src, sel, v in all_prices:
                if v not in seen:
                    seen.add(v)
                    unique.append((src, sel, v))
            # 选最小的（通常是最低售价）
            best = min(unique, key=lambda x: x[2])
            print(f"  {best[0]}[{best[1]}] → ¥{best[2]} (共{len(unique)}个候选)")
            return best[2]

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
