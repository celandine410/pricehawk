"""数据模型"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ItemInfo:
    """监控条目信息"""
    id: str
    name: str
    current_value: float  # 当前值（价格/数量等）
    unit: str = "元"       # 单位


@dataclass
class MonitorConfig:
    """监控配置"""
    id: str
    name: str                    # 显示名称
    target_value: Optional[float] = None   # 目标值：低于此值通知
    drop_threshold: float = 5.0            # 变化百分比阈值
    manual_value: Optional[float] = None   # 手动填写当前值
    url: Optional[str] = None              # 监控链接（可选）
