"""万能自动化监控模板 - 主入口"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from src.config import load_config
from src.fetchers.base import ItemInfo, MonitorConfig
from src.storage.history import ValueHistory
from src.notifiers.serverchan import ServerChanNotifier


async def main():
    print("=" * 40)
    print("  WatchDog 万能监控 v1.0")
    print("  监控时间:", datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 40)

    # 加载配置
    items = load_config()
    if not items:
        print("[主] 没有配置任何监控项，退出")
        return

    # 初始化组件
    notifier = ServerChanNotifier()
    history = ValueHistory()

    # 逐个处理监控项
    for item in items:
        print(f"\n--- 检查: {item.name} ---")

        current_value = None

        # 1) 尝试手动值
        if item.manual_value is not None:
            current_value = item.manual_value
            print(f"  手动值: {current_value}")

        # 2) 如果没有手动值，从历史取上次值（仅跟踪不变化）
        if current_value is None:
            last = history.get_latest(item.id)
            if last is not None:
                current_value = last
                print(f"  使用上次值: {current_value}")
            else:
                print(f"  无数据，跳过")
                continue

        # 创建信息对象
        info = ItemInfo(
            id=item.id,
            name=item.name,
            current_value=current_value,
        )

        # 检查是否有历史记录
        if history.is_first(item.id):
            history.save(item.id, current_value)
            print(f"  首次记录: {current_value}")
            continue

        # 获取上次值
        last_value = history.get_latest(item.id)
        if last_value is None:
            history.save(item.id, current_value)
            continue

        # 保存本次值
        history.save(item.id, current_value)

        # 检测变化
        if last_value == current_value:
            print(f"  未变化: {current_value}")
            continue

        # 下降了
        if current_value < last_value:
            drop_pct = (last_value - current_value) / last_value * 100
            meets_target = (item.target_value is not None and current_value <= item.target_value)
            meets_drop = drop_pct >= item.drop_threshold

            if meets_target or meets_drop:
                print(f"  ↓ 下降 {drop_pct:.1f}% ({last_value}→{current_value})")
                await notifier.send_alert(
                    name=item.name,
                    old_value=last_value,
                    new_value=current_value,
                    unit="",
                    url=item.url or "",
                )
            else:
                print(f"  轻微下降: {drop_pct:.1f}%")
        else:
            print(f"  ↑ 上升: {last_value}→{current_value}")

    print(f"\n✅ 本轮检查完成 ({datetime.now().strftime('%H:%M')})")


if __name__ == "__main__":
    asyncio.run(main())
