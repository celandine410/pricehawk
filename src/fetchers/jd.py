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
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.jd.com/",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
        except Exception as e:
            print(f"[京东] 请求失败: {url[:50]}... 错误: {e}")
            return None

        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        # --- 提取 SKU ---
        sku_id = self._extract_sku(url, html)

        # --- 标题 ---
        title = self._extract_title(soup, html)

        # --- 价格 ---
        # 京东价格通常通过 JS API 动态加载，我们尝试多种方式
        price = self._extract_price(soup, html, sku_id)
        if price is None:
            print(f"[京东] 无法解析价格: {url[:50]}...")
            return None

        # --- 原价 ---
        original_price = self._extract_original_price(soup, html)

        # --- 促销 ---
        discount = self._extract_discount(soup, html)

        return ProductInfo(
            platform=self.PLATFORM,
            url=url,
            sku_id=sku_id,
            title=title or sku_id,
            current_price=price,
            original_price=original_price,
            discount=discount,
            in_stock=True,
        )

    @staticmethod
    def _extract_sku(url: str, html: str) -> str:
        """提取京东商品 SKU ID"""
        # URL 中提取: https://item.jd.com/123456.html
        m = re.search(r'item\.jd\.com/(\d+)\.html', url)
        if m:
            return m.group(1)
        # 短链接: https://3.cn/xxxx
        # 页面中 JS 变量
        m = re.search(r'"skuId"\s*:\s*"(\d+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'sku:(\d+)', html)
        if m:
            return m.group(1)
        return url.rsplit("/", 1)[-1].replace(".html", "")

    @staticmethod
    def _extract_title(soup: BeautifulSoup, html: str) -> Optional[str]:
        """提取商品标题"""
        # <title>
        title_tag = soup.find("title")
        if title_tag and title_tag.text.strip():
            t = title_tag.text.strip()
            # 去掉 "【什么值得买】" 之类的后缀
            for suffix in ["【", " [", " - 京东"]:
                if suffix in t:
                    t = t.split(suffix)[0].strip()
            return t if t else None
        return None

    @staticmethod
    def _extract_price(soup: BeautifulSoup, html: str, sku_id: str) -> Optional[float]:
        """京东价格提取 — 尝试页面 JS 变量 + DOM"""
        # 方法1: 页面中的价格 JSON
        price_patterns = [
            r'"price"\s*:\s*["\']?(\d+\.?\d*)',
            r'"p"\s*:\s*["\']?(\d+\.?\d*)',
            r'pageConfig\.price\s*=\s*(\d+\.?\d*)',
        ]
        for pattern in price_patterns:
            m = re.search(pattern, html)
            if m:
                return float(m.group(1))

        # 方法2: DOM 元素
        selectors = [
            ".p-price span.price", ".p-price",
            "#jd-price", "span.price",
            ".summary-price .price",
        ]
        for sel in selectors:
            el = soup.select_one(sel)
            if el and el.text.strip():
                price_text = re.sub(r'[^\d.]', '', el.text.strip())
                if price_text:
                    return float(price_text)

        # 方法3: 尝试调用京东价格API（需要 sku_id）
        # 注意：这只是一个 fallback，实际可能被 CORS 限制，但在服务端没问题
        # 但我们用 httpx 来实现
        # 为简化，先跳过 API 方式，用页面解析为主
        return None

    @staticmethod
    def _extract_original_price(soup: BeautifulSoup, html: str) -> Optional[float]:
        """提取京东原价"""
        patterns = [
            r'"originalPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"marketPrice"\s*:\s*["\']?(\d+\.?\d*)',
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                return float(m.group(1))

        selectors = [".p-price .market-price", ".market-price"]
        for sel in selectors:
            el = soup.select_one(sel)
            if el and el.text.strip():
                price_text = re.sub(r'[^\d.]', '', el.text.strip())
                if price_text:
                    return float(price_text)
        return None

    @staticmethod
    def _extract_discount(soup: BeautifulSoup, html: str) -> Optional[str]:
        """提取促销标签"""
        selectors = [".promo-word", ".promo-tag", ".goods-promo"]
        for sel in selectors:
            el = soup.select_one(sel)
            if el and el.text.strip():
                return el.text.strip()
        # 正则匹配促销文案
        m = re.search(r'"promoDesc"\s*:\s*"([^"]+)"', html)
        if m:
            return m.group(1)
        return None
