"""微信通知器 - Server酱"""
from __future__ import annotations

import os
from typing import Optional

import httpx


class ServerChanNotifier:
    """通过 Server酱 推送到微信"""

    BASE_URL = "https://sctapi.ftqq.com"

    def __init__(self, send_key: Optional[str] = None):
        self.send_key = send_key or os.getenv("SERVERCHAN_KEY", "")

    def is_configured(self) -> bool:
        return bool(self.send_key)

    async def send(self, title: str, content: str) -> bool:
        if not self.is_configured():
            print("[通知] Server酱未配置，跳过推送")
            return False
        url = f"{self.BASE_URL}/{self.send_key}.send"
        payload = {"title": title[:150], "desp": content[:5000]}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, data=payload)
                result = resp.json()
                if result.get("code") == 0 or result.get("errno") == 0:
                    print(f"[通知] 推送成功")
                    return True
                else:
                    print(f"[通知] 推送失败: {result}")
                    return False
        except Exception as e:
            print(f"[通知] 推送异常: {e}")
            return False

    async def send_alert(self, name: str, old_value: float, new_value: float, unit: str = "", url: str = "") -> bool:
        drop = round((old_value - new_value) / old_value * 100, 1)
        title = f"📉 变化提醒：{name}"
        content = (
            f"## 📉 变化提醒\n\n"
            f"**项目**：{name}\n\n"
            f"**之前**：{old_value}{unit} → **现在**：{new_value}{unit}\n\n"
            f"**变化**：{drop:.1f}%\n\n"
        )
        if url:
            content += f"[🔗 查看链接]({url})\n\n"
        content += "*WatchDog 自动监控*"
        return await self.send(title, content)
