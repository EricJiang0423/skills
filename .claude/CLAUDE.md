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
├── assets/               ← Jinja2 HTML 模板（视觉风格在此承载）
├── references/           ← 厚知识库（每个垂直主题一个 .md）
└── demos/                ← 示例输出占位
```

## 设计上的硬约束（改动前先确认是否破坏假设）

- **JSON 契约是脚本间唯一接口**——`raw_photos.json` → `geocoded_photos.json` → `diary_data.json`。脚本不互相 import
- **Claude 仅负责创意输出**（旅行标题、每日叙述、可选 caption）。EXIF / GPS / 聚类 / base64 全部在 Python 一侧，便于流水线无 LLM 时也能调试
- **HTML 必须自包含**：默认照片 base64 内嵌，Leaflet inline；地图底图 tile 是允许的唯一在线依赖
- **隐私**：照片字节不离开本机；只 GPS 发往 Nominatim
- **macOS-only**：`osxphotos` 仅 macOS；不为 Windows/Linux 写兼容分支
- **方法论 vs 风格分离**：SKILL.md 与 references/ 只谈方法论；视觉风格沉到 `assets/diary-template.html`

## 常用命令

```bash
# 依赖检查
python3 scripts/check_deps.py

# 完整流水线（手动跑示例）
python3 scripts/extract_photos.py --folder /path/to/photos --out raw_photos.json
python3 scripts/geocode.py        --in  raw_photos.json     --out geocoded_photos.json
python3 scripts/cluster.py        --in  geocoded_photos.json --out diary_data.json
# ... Claude 回填 diary_data.json 的 title / narrative ...
python3 scripts/build_diary.py    --in  diary_data.json     --template assets/diary-template.html \
                                  --out output/trip.diary.html

# 在 Claude Code 对话里测试 skill 的触发词命中：
#   见 test-prompts.json
```

## 设计来源

skill 整体结构参考 [huashu-design](https://github.com/alchaincyf/huashu-design/) 的 skill 创建模式：
- 主控文档优先（SKILL.md 是 agent 行为的核心，含核心原则编号 + 工作流 🛑 检查点 + 异常表 + references 路由表 + 反 slop 速查 + 跨 agent 适配）
- `references/` 一个 `.md` 一个垂直主题，承载踩坑学问而非 how-to
- 设计风格不进 SKILL.md，由 `assets/diary-template.html` 自身承载
