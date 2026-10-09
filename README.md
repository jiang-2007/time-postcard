# 今日穿越明信片 · Time Postcard 📮

> 每天一张，从历史上的今天寄来的明信片。
> AIGC × 历史冷知识 × 飞书手账，把普通的一天过成一场跨越时空的小型仪式。

---

## 它是什么？

每天自动跑一条流水线：

```
历史上的今天（搜索）
      ↓
LLM 写一段第一人称穿越寄语
      ↓
文生图 画一张对应年代的明信片插画
      ↓
自动归档到飞书多维表格（带附件）
      ↓
每月底汇总成一份手账式飞书文档
```

第一张开张就是天选素材——**2026-10-09 这一天，正好是 1874 年 10 月 9 日《伯尔尼条约》签署 152 周年，而这一天本身就是"世界邮政日"**。于是第一张明信片，从 1874 年的瑞士伯尔尼寄来。

## 今天这张长这样

| 项目 | 内容 |
|---|---|
| 标题 | 从 1874 年伯尔尼寄来的明信片 |
| 年代 | 1874 · 维多利亚时代 |
| 地点 | 瑞士 · 伯尔尼 |
| 事件 | 22 国签署《伯尔尼条约》，成立邮政总联盟（万国邮政联盟前身） |
| 标签 | 维多利亚复古 |
| 评分 | ★★★★★ |

配套的飞书多维表格收藏夹和月度合集文档见本仓库 Release 里的链接。

## 项目结构

```
time-postcard/
├── main.py              # 主流水线
├── config.example.yaml  # 配置示例
├── requirements.txt
├── README.md
└── archive/             # 每天跑出来的本地归档（json + 图片）
```

## 快速开始

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 配环境变量（OpenAI 兼容协议即可，可指向 DeepSeek / 千帆 / Ollama）
export LLM_API_KEY="sk-xxx"
export LLM_BASE_URL="https://api.deepseek.com/v1"
export LLM_MODEL="deepseek-chat"
export LARK_BASE_TOKEN="你的飞书多维表格 token"
export LARK_TABLE_ID="你的 table_id"

# 3. 先本地 dry-run 看看效果
python main.py --dry-run

# 4. 真寄出一张
python main.py

# 5. 指定日期补寄
python main.py --date 10-09
```

前置条件：本机已登录 `lark-cli`（飞书官方 CLI）。

## 想自己跑成每日自动任务？

最简单的方式是 Windows 任务计划程序 /  Mac launchd / Linux cron 每天 21:00 执行一次 `python main.py`。
也可以挂在飞书多维表格自带的 Workflow 上，或者直接用豆包的定时任务。

## 为什么做这个？

- **好玩**：每天一张明信片，像在集邮。
- **有用**：顺便记住了一条历史冷知识。
- **新颖**：历史 × AIGC × 手账感，不是又一个聊天机器人 demo。
- **全栈**：搜索 → LLM → 文生图 → 飞书 Base → 飞书 Doc → Git 仓库，一条链走完。

## License

MIT. 寄信不贴邮票。
