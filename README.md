# 🦅 比价鹰 PriceHawk

> **零成本 · 全自动 · 电商比价监控**  
> 学生友好版 — 不花一分钱，7×24小时自动盯价，降价/套利微信通知

---

## ✨ 它能做什么

| 功能 | 说明 |
|---|---|
| 📉 **降价提醒** | 你关注的商品降价了 → 微信通知 |
| 💰 **套利发现** | 同一商品淘宝比京东便宜 → 微信通知 |
| 📊 **价格追踪** | 每次价格变化自动记录，历史可查 |
| 🤖 **全自动运行** | GitHub Actions 定时触发，无需你的设备 |

---

## 🚀 30 秒上手

### 1. Fork 这个仓库

点击右上角 **Fork** 按钮，把仓库复制到你的 GitHub 账号下。

### 2. 配置商品

编辑 [`config/products.yaml`](config/products.yaml)，填入你想监控的商品链接：

```yaml
products:
  - id: "my-item-1"
    name: "索尼 WH-1000XM5 耳机"
    taobao_url: "https://item.taobao.com/item.htm?id=xxxx"
    jd_url: "https://item.jd.com/xxxx.html"
    target_price: 1800          # 低于1800元时通知
    drop_threshold: 5.0         # 降价超5%时通知
    arbitrage_threshold: 20.0   # 跨平台差价超20元时通知
```

### 3. 配置微信通知

1. 打开 [Server酱](https://sct.ftqq.com) → 用微信扫码登录
2. 复制你的 **SendKey**
3. 回到你的 GitHub 仓库 → **Settings → Secrets and variables → Actions**
4. 点 **New repository secret** → 名称填 `SERVERCHAN_KEY` → 值填你的 SendKey

### 4. 启动监控

- 进入仓库 **Actions** 标签页
- 启用 GitHub Actions（第一次需要手动点 "I understand my workflows"）
- 点击 **比价鹰** → **Run workflow** → 绿色按钮手动跑一次测试

之后每 4 小时自动运行一次，价格变动会自动推送到你的微信。

---

## 📝 配置说明

| 配置项 | 说明 | 是否必填 |
|---|---|---|
| `id` | 商品唯一标识（英文/数字） | ✅ |
| `name` | 商品显示名称（微信通知里会看到） | ✅ |
| `taobao_url` | 淘宝商品链接 | 可选 |
| `jd_url` | 京东商品链接 | 可选 |
| `target_price` | 目标价：低于此价立刻通知 | 可选 |
| `drop_threshold` | 跌幅百分比阈值（默认5%） | 可选 |
| `arbitrage_threshold` | 跨平台价差阈值（元） | 可选 |

> 至少填一个平台的 URL，填两个平台会自动开启跨平台套利检测。

---

## 💸 成本

| 项目 | 费用 |
|---|---|
| GitHub Actions 免费额度 | ¥0/月（2000分钟，够用） |
| GitHub 仓库存储 | ¥0/月（1GB免费） |
| Server酱 基础版 | ¥0/月（每天5条，前期够用） |
| **总计** | **¥0/月** |

---

## 🧪 本地测试（可选）

```bash
pip install httpx beautifulsoup4 lxml pyyaml pydantic
python src/main.py
```

需要设置环境变量：`SERVERCHAN_KEY=你的Key`

---

## 🔧 故障排查

**收不到微信通知？**
- 检查 `SERVERCHAN_KEY` 是否在 GitHub Secrets 中配置正确
- 去 Actions 页面查看运行日志，是否有报错
- Server酱免费版每天5条，是否超限

**抓取不到价格？**
- 检查商品链接是否有效（手动打开试试）
- 某些商品页反爬较严，会偶发失败，下次自动重试

---

## 📋 路线图

- [x] 淘宝/京东价格抓取
- [x] 降价检测 + 微信通知
- [x] 跨平台套利检测
- [x] GitHub Actions 定时调度
- [ ] Amazon 支持
- [ ] 价格走势图（GitHub Pages）
- [ ] 拼多多支持
