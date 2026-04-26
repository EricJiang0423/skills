# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目本质

`trip-design` 是一个 **Claude Code skill**——一个被 agent 在用户对话里加载的目录。运行时由 `SKILL.md`（仓库根目录）担任硬指令，驱动一组 Python 脚本把旅行照片转成自包含旅行日记 HTML。

**Claude 既是开发者也是运行时**：你在维护的是"未来某个 Claude 会读取并执行的指令 + 工具"，不是普通应用。

## 入口文档（按需读）

| 想了解 | 读 |
|--------|-----|
| skill 整体协议（核心原则 / 工作流 / 检查点 / 异常表）| `../SKILL.md` |
| 用户怎么用它 | `../README.md` |
| 产品需求与边界 | `../PRD.md` |
| 触发词回归集 | `../test-prompts.json` |

## 仓库布局

```
trip-design/
├── SKILL.md              ← 主控文档（核心，运行时给 agent 的硬指令）
├── README.md             ← 用户首页
├── PRD.md                ← 产品需求文档
├── requirements.txt
├── test-prompts.json
├── scripts/              ← 流水线（check_deps / extract / geocode / cluster / build）
├── references/           ← 厚知识库（每个垂直主题一个 .md，含 HTML 必备元素 / 美学指南）
└── demos/                ← 示例输出占位
```

## 设计上的硬约束（改动前先确认是否破坏假设）

- **JSON 契约是脚本间唯一接口**——`raw_photos.json` → `geocoded_photos.json` → `diary_data.json`。脚本不互相 import
- **Claude 是策展人 + 前端设计师**：负责旅行标题、每日叙述、可选 caption、**HTML 设计**。EXIF / GPS / 聚类 / base64 / Leaflet 注入全部在 Python 一侧
- **没有 HTML 模板**：每次 Claude 现场写 HTML，按 `references/diary-html-essentials.md`（必备元素 + Token 协议）+ `references/diary-design-aesthetics.md`（美学方向 + 反前端 slop）走。`build_diary.py` 只做 token 后处理（base64 / Leaflet 注入 / JSON 数据注入）
- **HTML 必须自包含**：默认照片 base64 内嵌，Leaflet inline；地图底图 tile 是允许的唯一在线依赖；后处理脚本会验证无外部 src/href
- **隐私**：照片字节不离开本机；只 GPS 发往 Nominatim
- **macOS-only**：`osxphotos` 仅 macOS；不为 Windows/Linux 写兼容分支
- **NEVER converge on HTML design**：每次的 HTML 故意和上次不同——参考 frontend-design 的核心原则

## 常用命令

```bash
# 依赖检查
python3 scripts/check_deps.py

# 完整流水线（手动跑示例）
python3 scripts/extract_photos.py --folder /path/to/photos --out raw_photos.json
python3 scripts/geocode.py        --in  raw_photos.json     --out geocoded_photos.json
python3 scripts/cluster.py        --in  geocoded_photos.json --out diary_data.json
# ... Claude 回填 diary_data.json 的 title / narrative，并现场写一份 HTML（含 token 占位）...
python3 scripts/build_diary.py    --in  diary_data.json     --html output/trip.diary.draft.html \
                                  --out output/trip.diary.html

# 在 Claude Code 对话里测试 skill 的触发词命中：
#   见 test-prompts.json
```

## 设计来源

- **skill 整体结构**参考 [huashu-design](https://github.com/alchaincyf/huashu-design/)：主控文档优先；references/ 一个 `.md` 一个垂直主题，承载踩坑学问；核心原则编号 + 工作流 🛑 检查点 + 异常表 + 反 slop 速查
- **HTML 设计哲学**参考 [Claude Code frontend-design skill](https://github.com/anthropics/claude-code/tree/main/plugins/frontend-design/skills/frontend-design)：无 template，Claude 现场设计；BOLD 美学方向 + 反 AI slop 清单；NEVER converge on common choices
