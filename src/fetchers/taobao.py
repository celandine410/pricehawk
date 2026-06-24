"""淘宝/天猫价格抓取器"""
from __future__ import annotations

import json
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base import BaseFetcher, ProductInfo


class TaobaoFetcher(BaseFetcher):
    """淘宝/天猫价格抓取器"""

    PLATFORM = "taobao"

    async def fetch(self, url: str) -> Optional[ProductInfo]:
        """从淘宝商品页/API 抓取价格信息"""
        sku_id = self._extract_sku_id(url)
        if not sku_id:
            print(f"[淘宝] 无法提取商品ID: {url[:50]}")
            return None

        print(f"  商品ID: {sku_id}")

        title = None
        price = None

        # 策略1: 调用价格 API
        price = await self._try_price_apis(sku_id)

        # 策略2: 获取页面解析
        if price is None:
            page_data = await self._fetch_page(url)
            if page_data:
                html, soup = page_data
                title = self._extract_title(soup, html)
                price = self._extract_price_from_page(html)

        if price is None:
            print(f"[淘宝] 所有方式都无法获取价格")
            return None

        return ProductInfo(
            platform=self.PLATFORM,
            url=url,
            sku_id=sku_id,
            title=title or sku_id,
            current_price=price,
            in_stock=True,
        )

    async def _try_price_apis(self, sku_id: str) -> Optional[float]:
        """尝试多个淘宝价格 API"""
        api_list = [
            # 淘宝详情 API (JSONP)
            f"https://mdskip.taobao.com/core/initItemDetail.htm?itemId={sku_id}",
            # 淘宝客 API
            f"https://api.taobao.com/router/rest?method=taobao.tbk.item.info.get&item_id={sku_id}&format=json",
            # 简单价格查询
            f"https://item.taobao.com/item.htm?id={sku_id}",
        ]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
            "Accept": "text/html,application/json,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.taobao.com/",
        }

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            for i, api_url in enumerate(api_list):
                try:
                    resp = await client.get(api_url, headers=headers)
                    if resp.status_code != 200:
                        continue
                    text = resp.text

                    # 从 JSONP 中提取 JSON
                    m = re.search(r'\{.*\}', text, re.DOTALL)
                    if m:
                        try:
                            data = json.loads(m.group())
                            # 尝试各种字段
                            for key in ["price", "currentPrice", "defPrice", "apiPrice", "reservePrice"]:
                                val = data.get(key)
                                if val and str(val).replace(".", "").isdigit():
                                    p = float(str(val).split("-")[0].split("~")[0])
                                    if p > 1:
                                        print(f"  API[{i}] 成功: ¥{p}")
                                        return p
                            # 嵌套字段
                            for section in ["itemInfoResult", "priceResult", "data"]:
                                sect = data.get(section, {})
                                val = sect.get("price")
                                if val:
                                    p = float(str(val).split("-")[0].split("~")[0])
                                    if p > 1:
                                        print(f"  API[{i}] 成功: ¥{p}")
                                        return p
                        except json.JSONDecodeError:
                            pass

                    # 如果没解析到 JSON，检查页面中是否有价格
                    if "京东价" in text or "price" in text:
                        page_price = self._extract_price_from_page(text)
                        if page_price:
                            print(f"  API[{i}] 页面解析: ¥{page_price}")
                            return page_price

                except Exception as e:
                    err_type = type(e).__name__
                    print(f"  API[{i}] {err_type}: {str(e)[:60]}")
                    continue
        return None

    async def _fetch_page(self, url: str) -> Optional[tuple]:
        """获取商品页面"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                return resp.text, soup
        except Exception as e:
            print(f"  [淘宝] 页面请求失败: {e}")
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

    @staticmethod
    def _extract_title(soup: BeautifulSoup, html: str) -> Optional[str]:
        """提取商品标题"""
        title_tag = soup.find("title")
        if title_tag and title_tag.text.strip():
            t = title_tag.text.strip()
            for suffix in ["-淘宝", "-天猫", " - taobao", "-tmall", "-淘宝网"]:
                if suffix in t:
                    t = t.split(suffix)[0].strip()
            if t and len(t) > 3:
                return t[:80]
        return None

    @staticmethod
    def _extract_price_from_page(html: str) -> Optional[float]:
        """从页面 HTML 提取价格"""
        patterns = [
            r'"price"\s*:\s*["\']?(\d+\.?\d*)',
            r'"currentPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"discountPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"apiPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"defPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"reservePrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"realPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"salePrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"promotionPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"priceText"\s*:\s*["\']?(\d+\.?\d*)',
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, html, re.IGNORECASE):
                val = float(m.group(1))
                if 1 < val < 99999:
                    return val
        return None
