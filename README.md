# trip-design

把一组旅行照片变成一份可以双击打开的旅行日记 HTML 网页。

> **形态**：Claude Code skill（也兼容 Codex / Cursor / Trae 等支持 markdown skill 的 agent）
> **平台**：macOS（osxphotos 限制）
> **隐私**：照片字节绝不离开本机；仅 GPS 坐标用于反向地理编码

---

## 它做什么

```
照片文件夹 / Photos.app 相册
        ↓
  EXIF 提取（时间 + GPS）
        ↓
  反向地理编码（OpenStreetMap）
        ↓
  按日期 + GPS 自动聚类
        ↓
  Claude 撰写旅行标题 + 每日叙述
        ↓
  Claude 现场设计 HTML（每次不同！没有固定模板）
        ↓
  build_diary.py 后处理（base64 + Leaflet 注入）
        ↓
  自包含 HTML 单文件
```

输出：一个可双击打开的 `.diary.html`，含 hero 封面、地图轨迹、按天的时间线、照片 grid 与灯箱。

---

## 怎么装

### 系统依赖（macOS）

```bash
brew install exiftool libheif
```

### Python 依赖

```bash
pip install -r requirements.txt
```

### 验证

```bash
python3 scripts/check_deps.py
```

输出 JSON；缺什么就照 `install_commands` 装。

### 注册为 Claude Code skill

把整个 `trip-design/` 目录放到你的 skills 路径（通常是 `~/.claude/skills/`），然后在 Claude Code 对话里说**触发词**：

> 「给我的冲绳旅行照片做一份旅行日记」

Claude Code 会加载 `SKILL.md` 接管对话流程。

---

## 触发词（让 Claude 进入 skill）

任意一句即可：

- 「整理我的旅行照片」
- 「生成旅行日记」
- 「把这次旅行做成网页」
- 「Photos 相册整理」
- 「我的 HEIC 旅行照片做成册」
- "Travel diary"
- "Make a trip recap page"

---

## 手动跑（不在 Claude Code 里）

也可以脱离 agent 单独跑流水线（叙述需要自己填进 `diary_data.json`）：

```bash
# 1. 检查依赖
python3 scripts/check_deps.py

# 2. 提取 EXIF（文件夹模式）
python3 scripts/extract_photos.py --folder /path/to/photos --out raw_photos.json

# 或：从 Photos.app 读
python3 scripts/extract_photos.py --album "冲绳 2024" --out raw_photos.json
python3 scripts/extract_photos.py --date-range 2024-03-01 2024-03-07 --out raw_photos.json

# 3. 反向地理编码（限速 1 req/s，100 张约 1-2 分钟）
python3 scripts/geocode.py --in raw_photos.json --out geocoded_photos.json

# 4. 聚类（按日期 + GPS 距离）
python3 scripts/cluster.py --in geocoded_photos.json --out diary_data.json

# 5. （可选）手动填 diary_data.json 的 title / narrative 字段
#    在 Claude Code 里这一步由 Claude 自动完成

# 6. （可选）手写一份 trip.diary.draft.html
#    - 用 src="trip-design://photo_NNNN" 引用照片
#    - 用 <style data-trip-design="leaflet-css"></style> 等留 token 占位
#    - 在 Claude Code 里这一步由 Claude 现场设计
#    详见 references/diary-html-essentials.md

# 7. 后处理（base64 / Leaflet / JSON 注入 + 自包含验证）
python3 scripts/build_diary.py --in diary_data.json \
        --html output/trip.diary.draft.html \
        --out output/trip.diary.html
```

体积 > 200MB 时改用 `--embed-photos relative`，会把照片放到 `output/trip.diary.assets/`。

---

## 项目结构

```
trip-design/
├── SKILL.md                ← agent 主控文档（核心）
├── README.md               ← 本文件
├── CLAUDE.md               ← Claude Code 项目说明（指向 SKILL.md）
├── requirements.txt
├── test-prompts.json       ← 触发词回归集
├── scripts/                ← Python 流水线（含 build_diary.py 做 token 后处理）
├── references/             ← 厚知识库（含 HTML 必备元素 + 美学指南）
└── demos/                  ← 示例输出
```

---

## 设计取舍

- **隐私优先**：仅 GPS 发往 Nominatim，照片字节本地处理
- **数据可追溯**：叙述基于真实 EXIF + 视觉采样，不虚构地点 / 活动 / 天气 / 人物
- **自包含**：HTML 单文件，base64 内嵌照片，Leaflet inline，地图 tile 走 OSM CDN
- **渐进确认**：iCloud 状态 / 行程聚类 / HTML 体积三个节点必停下让用户确认
- **没有 HTML 模板**：参考 [Claude Code frontend-design skill](https://github.com/anthropics/claude-code/tree/main/plugins/frontend-design/skills/frontend-design) 的范式——Claude 每次现场用前端能力设计，按 `references/diary-html-essentials.md`（必备元素 + Token 协议）+ `references/diary-design-aesthetics.md`（美学方向 + 反前端 slop）走，**每份日记的视觉指纹都不同**

详细设计与踩坑记录见 `references/`。

---

## 范围之外（V1 不做）

- 视频文件
- 多人协作 / 云同步
- Windows / Linux（osxphotos 仅 macOS）
- 天气 / 社交分享 / 旅行统计

---

## License

MIT
