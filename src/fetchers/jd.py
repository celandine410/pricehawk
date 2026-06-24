"""京东价格抓取器"""
from __future__ import annotations

import json
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base import BaseFetcher, ProductInfo


class JDFetcher(BaseFetcher):
    """京东价格抓取器"""

    PLATFORM = "jd"

    async def fetch(self, url: str) -> Optional[ProductInfo]:
        """从京东商品页/API 抓取价格信息"""
        sku_id = self._extract_sku(url)
        if not sku_id:
            print(f"[京东] 无法提取 SKU: {url[:50]}")
            return None

        print(f"  SKU: {sku_id}")

        title = None
        price = None

        # 策略1: 调用价格 API
        price = await self._try_price_apis(sku_id)

        # 策略2: 获取页面并解析
        if price is None:
            page_data = await self._fetch_page(url)
            if page_data:
                html, soup = page_data
                title = self._extract_title(soup, html)
                price = self._extract_price_from_page(html)
                if price is None:
                    # 试试从页面标题提取商品名
                    title = title or self._extract_title(soup, html)

        if price is None:
            print(f"[京东] 所有方式都无法获取价格")
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
        """尝试多个价格 API 端点"""
        api_urls = [
            f"https://p.3.cn/prices/mgets?skuIds=J_{sku_id}&type=1",
            f"https://p.3.cn/prices/mgets?skuIds=J_{sku_id}",
            f"https://p.3.cn/prices/mgets?skuIds={sku_id}&type=1",
            f"https://p.3.cn/prices/mgets?skuIds={sku_id}",
            f"https://p.3.cn/prices/mgets?skuIds=J_{sku_id}&type=1&area=1_72_4137_0",
        ]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://item.jd.com/",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=8.0) as client:
            for i, api_url in enumerate(api_urls):
                try:
                    resp = await client.get(api_url, headers=headers)
                    if resp.status_code != 200:
                        print(f"  API[{i}] HTTP {resp.status_code}")
                        continue
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        # 尝试多个字段名
                        for key in ["p", "price", "jdPrice"]:
                            val = data[0].get(key)
                            if val:
                                price = float(val)
                                if price > 0:
                                    print(f"  API[{i}] 成功: ¥{price}")
                                    return price
                    print(f"  API[{i}] 返回空数据: {str(data)[:100]}")
                except Exception as e:
                    err_type = type(e).__name__
                    print(f"  API[{i}] {err_type}: {str(e)[:80]}")
                    continue
        return None

    async def _fetch_page(self, url: str) -> Optional[tuple]:
        """获取商品页面 HTML"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.jd.com/",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                return resp.text, soup
        except Exception as e:
            print(f"  [京东] 页面请求失败: {e}")
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

    @staticmethod
    def _extract_title(soup: BeautifulSoup, html: str) -> Optional[str]:
        """提取商品标题"""
        title_tag = soup.find("title")
        if title_tag and title_tag.text.strip():
            t = title_tag.text.strip()
            for suffix in ["【", " [", " - 京东"]:
                if suffix in t:
                    t = t.split(suffix)[0].strip()
            if t and len(t) > 3:
                return t[:80]
        return None

    @staticmethod
    def _extract_price_from_page(html: str) -> Optional[float]:
        """从页面正则提取价格"""
        patterns = [
            r'"price"\s*:\s*["\']?(\d+\.?\d*)',
            r'"p"\s*:\s*["\']?(\d+\.?\d*)',
            r'"jdPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'pageConfig\.price\s*=\s*(\d+\.?\d*)',
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                val = float(m.group(1))
                if val > 1:
                    return val
        return None
