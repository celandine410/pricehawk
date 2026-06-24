"""淘宝/天猫价格抓取器"""
from __future__ import annotations

import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base import BaseFetcher, ProductInfo


class TaobaoFetcher(BaseFetcher):
    """淘宝/天猫价格抓取器"""

    PLATFORM = "taobao"

    async def fetch(self, url: str) -> Optional[ProductInfo]:
        """从淘宝商品页抓取价格信息"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
        except Exception as e:
            print(f"[淘宝] 请求失败: {url[:50]}... 错误: {e}")
            return None

        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        # --- 解析商品ID ---
        sku_id = self._extract_sku_id(url, html)

        # --- 解析标题 ---
        title = self._extract_title(soup, html)

        # --- 解析价格 ---
        price = self._extract_price(soup, html)
        if price is None:
            print(f"[淘宝] 无法解析价格: {url[:50]}...")
            return None

        # --- 解析原价 ---
        original_price = self._extract_original_price(soup, html)

        # --- 解析促销标签 ---
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
    def _extract_sku_id(url: str, html: str) -> str:
        """从 URL 或页面中提取商品ID"""
        # URL pattern: https://item.taobao.com/item.htm?id=123456
        m = re.search(r'[?&]id=(\d+)', url)
        if m:
            return m.group(1)
        # 天猫: https://detail.tmall.com/item.htm?id=123456
        m = re.search(r'[?&]item_id=(\d+)', url)
        if m:
            return m.group(1)
        # 从页面 data-id 属性
        m = re.search(r'"itemId"\s*:\s*"(\d+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'"skuId"\s*:\s*"(\d+)"', html)
        if m:
            return m.group(1)
        return url.split("?")[0].rsplit("/", 1)[-1]

    @staticmethod
    def _extract_title(soup: BeautifulSoup, html: str) -> Optional[str]:
        """提取商品标题"""
        # <title> 标签
        title_tag = soup.find("title")
        if title_tag and title_tag.text:
            t = title_tag.text.strip()
            # 淘宝标题常带后缀，截取有用部分
            for suffix in ["-淘宝", "-天猫", " - taobao", "-tmall", "-淘宝网"]:
                if suffix in t:
                    t = t.split(suffix)[0].strip()
            if t:
                return t
        return None

    @staticmethod
    def _extract_price(soup: BeautifulSoup, html: str) -> Optional[float]:
        """提取当前价格"""
        # 方法1: 从 JSON-LD 中提取
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            import json
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    offers = data.get("offers", {})
                    price_str = offers.get("price")
                    if price_str:
                        return float(price_str)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # 方法2: 正则匹配价格模式
        # 淘宝/TMALL 页面通常在 JS 变量中
        price_patterns = [
            r'"price"\s*:\s*["\']?(\d+\.?\d*)',
            r'"currentPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"discountPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"apiPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"defPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'price["\']?\s*:\s*["\']?(\d+\.?\d*)',
        ]
        for pattern in price_patterns:
            m = re.search(pattern, html)
            if m:
                return float(m.group(1))

        # 方法3: DOM 中价格元素
        selectors = [
            ".tm-price", ".tb-rmb-num", ".price-current",
            "#J_StrPr498", ".tm-promo-price .tm-price",
            "span.price", "span.tm-price",
        ]
        for sel in selectors:
            el = soup.select_one(sel)
            if el and el.text.strip():
                price_text = re.sub(r'[^\d.]', '', el.text.strip())
                if price_text:
                    return float(price_text)

        return None

    @staticmethod
    def _extract_original_price(soup: BeautifulSoup, html: str) -> Optional[float]:
        """提取原价/划线价"""
        patterns = [
            r'"originalPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"priceOrig"\s*:\s*["\']?(\d+\.?\d*)',
            r'"reservePrice"\s*:\s*["\']?(\d+\.?\d*)',
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                return float(m.group(1))

        selectors = [".tm-original-price .tm-price", ".tb-rmb-num-old"]
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
        patterns = [
            r'"promotionText"\s*:\s*"([^"]+)"',
            r'"discountText"\s*:\s*"([^"]+)"',
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                return m.group(1)

        selectors = [".tm-promo-tag", ".promo-tag", ".tb-promo-tag"]
        for sel in selectors:
            el = soup.select_one(sel)
            if el and el.text.strip():
                return el.text.strip()
        return None
