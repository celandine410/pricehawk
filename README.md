# 🐶 WatchDog 万能自动化监控模板

> **监控任何数字变化 · 微信自动通知 · 全云端运行 · ¥0 成本**

---

## 它能做什么？

这是一个**通用的数值监控框架**，你只需要告诉它要监控什么数字，它就会：

- ✅ **定时检查** — 每隔 6 小时自动运行一次
- ✅ **记录历史** — 所有变化自动保存
- ✅ **微信通知** — 数字变化时推送到你的微信
- ✅ **零成本** — 全部跑在 GitHub 免费服务器上

### 使用场景举例

| 场景 | 怎么用 |
|------|--------|
| 📉 **价格监控** | 每周手动更新一次商品价格，监控降价趋势 |
| 📊 **数据追踪** | 追踪你的网站流量、粉丝数、收益等指标 |
| 🔔 **阈值告警** | 设定目标值，一旦达标立刻通知你 |
| 📝 **定期记录** | 任何你想定期记录的数字（体重、学习时长等） |

---

## 🚀 3 分钟部署

### 第 1 步：Fork 这个仓库

点击右上角 **Fork**，把仓库复制到你的 GitHub 账号下。

### 第 2 步：配置你想要监控的内容

编辑 [`config/items.yaml`](config/items.yaml)：

```yaml
items:
  - id: "price-phone"
    name: "iPhone 15"
    manual_value: 5999       # 当前价格
    target_value: 4999       # 低于此价通知你
    drop_threshold: 10.0     # 降价超10%通知
    url: "https://example.com/product"  # 可选
```

### 第 3 步：配置微信通知

1. 打开 [Server酱](https://sct.ftqq.com) → 微信扫码登录
2. 复制你的 **SendKey**
3. 去你的 GitHub 仓库 → **Settings → Secrets and variables → Actions**
4. 点 **New repository secret**
   - Name: `SERVERCHAN_KEY`
   - Value: 粘贴你的 SendKey

### 第 4 步：启动

1. 进入仓库 **Actions** 标签页
2. 启用 GitHub Actions（点绿色按钮）
3. 左侧点 **WatchDog** → **Run workflow**

之后每 6 小时自动运行一次，微信会收到通知。

---

## 📝 配置说明

```yaml
items:
  - id: "唯一标识"           # 英文数字，不重复
    name: "显示名称"          # 微信通知里看到的
    manual_value: 100        # 当前值（改这个数字就更新了）
    target_value: 80         # 低于此值通知（可选）
    drop_threshold: 5.0      # 下降超此百分比通知
    url: "https://..."       # 相关链接（可选）
```

---

## 💸 成本

| 项目 | 费用 |
|------|------|
| GitHub Actions | ¥0/月（免费额度够用） |
| Server酱 基础版 | ¥0/月（每天5条推送） |
| **总计** | **¥0/月** |

---

## 🔧 常见问题

**怎么更新数值？**
编辑 `config/items.yaml` 里的 `manual_value`，提交到 GitHub 即可。

**收不到微信通知？**
- 检查 `SERVERCHAN_KEY` 是否配置正确
- 去 Actions 页面看运行日志

**想监控多个东西？**
在 `items.yaml` 里加多个条目就行。

---

## 🛠 技术栈

Python 3.11 · GitHub Actions · Server酱 · GitHub

> 由 celandine410 构建 · 学生友好版
