"""产品信息数据模型与基础抓取接口"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProductInfo:
    """标准化产品价格信息"""
    platform: str          # 平台名称: taobao / jd / amazon
    url: str               # 商品链接
    sku_id: str            # 商品唯一标识
    title: str             # 商品标题
    current_price: float   # 当前价格（元）
    original_price: Optional[float] = None  # 原价/划线价
    discount: Optional[str] = None          # 促销标签 (如 "满300减50")
    in_stock: bool = True                   # 是否有货
    currency: str = "CNY"                   # 货币单位

    @property
    def price_change_percent(self) -> Optional[float]:
        """如果同时有原价和现价，返回折扣百分比"""
        if self.original_price and self.original_price > 0:
            return round((self.current_price - self.original_price) / self.original_price * 100, 1)
        return None


@dataclass
class ProductConfig:
    """用户配置：一个待监控商品"""
    id: str                         # 唯一标识符
    name: str                       # 商品显示名称
    taobao_url: Optional[str] = None
    jd_url: Optional[str] = None
    amazon_url: Optional[str] = None
    target_price: Optional[float] = None    # 目标价：低于此价告警
    drop_threshold: float = 5.0             # 跌幅百分比阈值（默认5%）
    arbitrage_threshold: float = 10.0       # 跨平台价差阈值（默认10元）


class BaseFetcher:
    """价格抓取器基类"""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def fetch(self, url: str) -> Optional[ProductInfo]:
        """抓取商品价格信息，失败返回 None"""
        raise NotImplementedError
