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
    DETAIL_API = "https://mdskip.taobao.com/core/initItemDetail.htm"

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

        # --- 解析价格: 多种策略 ---
        price = None

        # 策略1: 从页面 HTML 解析
        price = self._extract_price_from_page(soup, html)

        # 策略2: API 获取（如果页面解析失败）
        if price is None:
            async with httpx.AsyncClient(timeout=8.0) as client:
                price = await self._fetch_price_from_api(client, sku_id, headers)

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

    async def _fetch_price_from_api(
        self, client: httpx.AsyncClient, sku_id: str, headers: dict
    ) -> Optional[float]:
        """通过淘宝详情 API 获取价格"""
        try:
            api_url = f"{self.DETAIL_API}?itemId={sku_id}"
            resp = await client.get(api_url, headers=headers)
            if resp.status_code == 200:
                # API 返回 JSONP 格式: fn(jsonData)
                text = resp.text
                # 提取 JSON
                m = re.search(r'\{.*\}', text, re.DOTALL)
                if m:
                    data = json.loads(m.group())
                    # 尝试提取价格
                    price_str = None
                    for key in ["price", "currentPrice", "defPrice", "apiPrice"]:
                        val = data.get(key)
                        if val:
                            price_str = str(val)
                            break
                    # 也试试 itemInfoResult
                    item_info = data.get("itemInfoResult", {})
                    if not price_str:
                        price_str = item_info.get("price")
                    if not price_str:
                        price_result = data.get("priceResult", {})
                        price_str = price_result.get("price")
                    if price_str:
                        # 可能是 "89.00-129.00" 范围价格，取最低值
                        price_str = str(price_str).split("-")[0].split("~")[0]
                        return float(price_str)
        except Exception as e:
            print(f"[淘宝] API 异常: {e}")
        return None

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
        # 从页面 JS 变量
        m = re.search(r'"itemId"\s*:\s*"(\d+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'"skuId"\s*:\s*"(\d+)"', html)
        if m:
            return m.group(1)
        # 从 data- 属性
        m = re.search(r'data-id\s*=\s*["\'](\d+)', html)
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
            for suffix in ["-淘宝", "-天猫", " - taobao", "-tmall", "-淘宝网"]:
                if suffix in t:
                    t = t.split(suffix)[0].strip()
            if t:
                return t
        # 减价页面中也可能有 data-title
        m = re.search(r'data-title\s*=\s*["\']([^"\']+)', html)
        if m:
            return m.group(1).strip()
        return None

    @staticmethod
    def _extract_price_from_page(soup: BeautifulSoup, html: str) -> Optional[float]:
        """从页面 HTML 中提取价格"""
        # 方法1: JSON-LD 结构化数据
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    offers = data.get("offers", {})
                    price_str = offers.get("price")
                    if price_str:
                        return float(price_str)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # 方法2: 正则匹配各种 JS 变量名中的价格
        price_patterns = [
            r'"price"\s*:\s*["\']?(\d+\.?\d*)',
            r'"currentPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"discountPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"apiPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"defPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"reservePrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"priceText"\s*:\s*["\']?(\d+\.?\d*)',
            r'"promotionPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"realPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"salePrice"\s*:\s*["\']?(\d+\.?\d*)',
        ]
        for pattern in price_patterns:
            m = re.search(pattern, html)
            if m:
                # 排除无意义的小数值
                val = float(m.group(1))
                if val > 0.01:
                    return val

        # 方法3: DOM 选择器
        selectors = [
            ".tm-price", ".tb-rmb-num", ".price-current",
            "#J_StrPr498", ".tm-promo-price .tm-price",
            "span.price", "span.tm-price",
            ".J_originalPrice", ".J_%sPrice",
        ]
        for sel in selectors:
            try:
                el = soup.select_one(sel)
                if el and el.text.strip():
                    price_text = re.sub(r'[^\d.]', '', el.text.strip())
                    if price_text:
                        val = float(price_text)
                        if val > 0.01:
                            return val
            except Exception:
                pass

        # 方法4: data-* 属性
        data_attrs = re.findall(r'data-price\s*=\s*["\'](\d+\.?\d*)', html)
        if data_attrs:
            return float(data_attrs[0])

        return None

    @staticmethod
    def _extract_original_price(soup: BeautifulSoup, html: str) -> Optional[float]:
        """提取原价/划线价"""
        patterns = [
            r'"originalPrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"priceOrig"\s*:\s*["\']?(\d+\.?\d*)',
            r'"reservePrice"\s*:\s*["\']?(\d+\.?\d*)',
            r'"originPrice"\s*:\s*["\']?(\d+\.?\d*)',
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                return float(m.group(1))

        selectors = [
            ".tm-original-price .tm-price", ".tb-rmb-num-old",
            ".original-price", ".J_originalPrice",
        ]
        for sel in selectors:
            try:
                el = soup.select_one(sel)
                if el and el.text.strip():
                    price_text = re.sub(r'[^\d.]', '', el.text.strip())
                    if price_text:
                        return float(price_text)
            except Exception:
                pass
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
            try:
                el = soup.select_one(sel)
                if el and el.text.strip():
                    return el.text.strip()
            except Exception:
                pass
        return None
