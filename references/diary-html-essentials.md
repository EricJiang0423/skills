# diary-html-essentials · 必备元素清单与 Token 协议

trip-design **没有 HTML 模板**——每次生成时由 Claude 现场用前端能力设计。本文档定义两件事：

1. **必备元素清单**：哪些区块必须有（用户期望的"旅行日记"核心结构）
2. **Token 协议**：Claude 写的 HTML 如何与 `build_diary.py` 后处理器协作（base64 照片注入、Leaflet inline、JSON 数据注入）

设计风格 / 配色 / 字体 / 排版**完全由 Claude 自由发挥**——见 `references/diary-design-aesthetics.md`。

---

## 必备元素（缺一不可）

旅行日记 HTML 必须包含以下五个区块。**布局、视觉、动画、文案位置**全部由 Claude 决定，但**这些区块都要有**——它们是用户对"旅行日记"的最低期望。

### 1. Hero 区（封面）

- 全屏或半屏的视觉主图
- 旅行总标题（`trip_summary.title`）
- 日期范围（`trip_summary.date_range`）
- 至少一项摘要：照片数 / 城市 / 天数

### 2. 全程地图

- 地图容器（必须 id 或 class 让 Claude 自己的 JS 能初始化 Leaflet）
- 全程 GPS 轨迹线（来自 `all_gps_points`）
- 各地点标记（标记 placement 由 Claude 决定，但要点击/悬停能看见地名）

### 3. 时间线（按天）

每天至少展示：
- Day N 标识 / 日期
- 每日标题（`days[].title`）
- 每日叙述（`days[].narrative`）
- 当天的地点链路（`days[].locations[].place_name` 用 `→` 或其他视觉连接）
- 每个地点的照片网格（`days[].locations[].photos`）

### 4. 灯箱（点开大图）

- 点击照片打开大图视图
- **键盘约定**（不可省略）：
  - `←` / `→` 切换上一张 / 下一张
  - `Esc` 关闭
- 显示 caption（如有）与拍摄时间

### 5. 页脚（自包含承诺标记）

至少一行说明：
- 由 trip-design 生成
- 所有处理本地完成 / 仅 GPS 用于地名查询

---

## Token 协议（与 build_diary.py 协作）

Claude 写 HTML 时**不能**手嵌 base64 照片（context 装不下）、**不能**复制 Leaflet 字节（156 KB 浪费 token）。改用 **token 占位**，由 `build_diary.py` 后处理替换。

### Token 类型

#### A · 照片引用 → `src="trip-design://photo_NNNN"`

```html
<img src="trip-design://photo_0001" alt="清晨的国際通り">
<img src="trip-design://photo_0002" alt="">
```

后处理把 `trip-design://photo_NNNN` 替换为：
- 默认（base64 模式）：`data:image/jpeg;base64,...` 完整 data URL
- relative 模式：`<out>.assets/photo_NNNN.jpg`

**规则**：只在 `<img src=>` 与 CSS `background: url(...)` 里用这个 scheme。**不要**在 JS 里拼字符串引用——见下方"灯箱里如何用"。

#### B · Leaflet 库注入 → 空标签 + data 属性

```html
<style data-trip-design="leaflet-css"></style>
<script data-trip-design="leaflet-js"></script>
```

后处理把这两个空标签的 `textContent` 填为 Leaflet 1.9.4 的字节内容。

**位置约定**：
- `<style data-trip-design="leaflet-css">` 必须在 `<head>` 里（否则地图样式来不及生效）
- `<script data-trip-design="leaflet-js">` 必须在 `</body>` 之前 + 在你自己的地图初始化 JS **之前**

#### C · JSON 数据注入 → 空 script 标签

```html
<script type="application/json" data-trip-design="photos-index"></script>
<script type="application/json" data-trip-design="track"></script>
```

后处理把这两个空 script 的 `textContent` 填为：
- `photos-index`：`{ "photo_0001": {"src": "...", "caption": "...", "datetime": "..."}, ... }`
- `track`：`[ {"lat": 26.214, "lon": 127.681, "time": "10:23", "place": "..."}, ... ]`

Claude 自己写的 JS 这样读：

```javascript
const PHOTOS = JSON.parse(document.querySelector('[data-trip-design="photos-index"]').textContent);
const TRACK = JSON.parse(document.querySelector('[data-trip-design="track"]').textContent);
```

灯箱里要展示某张照片大图时，从 `PHOTOS[photo_id].src` 取 src（这个 src 已被后处理替换为 data URL 或相对路径），赋给 `<img>` 元素。**不要**自己拼 `trip-design://` 字符串。

### Token 一览表

| 用途 | 写法 | 后处理填什么 |
|------|------|-------------|
| 照片 src | `<img src="trip-design://photo_0001">` | `data:image/jpeg;base64,...` 或 relative path |
| 照片 CSS 背景 | `background: url("trip-design://photo_0001")` | 同上 |
| Leaflet CSS | `<style data-trip-design="leaflet-css"></style>` | Leaflet 1.9.4 CSS 字节 |
| Leaflet JS | `<script data-trip-design="leaflet-js"></script>` | Leaflet 1.9.4 JS 字节 |
| 照片索引 JSON | `<script type="application/json" data-trip-design="photos-index"></script>` | 完整 photos 字典 |
| GPS 轨迹 JSON | `<script type="application/json" data-trip-design="track"></script>` | `all_gps_points` 数组 |

---

## 数据契约（diary_data.json）

Claude 在 Step 6 已经回填好叙述，HTML 设计阶段直接读这个 JSON 用：

```json
{
  "trip_summary": {
    "title": "冲绳七日，珊瑚礁与春风",
    "date_range": "2024-03-01 ~ 2024-03-07",
    "day_count": 7,
    "photo_count": 120,
    "cities": ["那覇市", "本部町", ...],
    "cover_photo_id": "photo_0001"
  },
  "days": [
    {
      "date": "2024-03-01",
      "day_number": 1,
      "title": "那覇漫步",
      "narrative": "清晨的国際通り还很安静...",
      "cover_photo_id": "photo_0001",
      "locations": [
        {
          "place_name": "国際通り",
          "place_detail": "国際通り, 那覇市, 沖縄県, 日本",
          "arrival_time": "10:23",
          "departure_time": "13:45",
          "center_gps": {"lat": 26.214, "lon": 127.681},
          "cover_photo_id": "photo_0001",
          "photos": [
            {"id": "photo_0001", "datetime": "2024-03-01T10:23:00",
             "gps": {...}, "caption": "..." (可选)}
          ]
        }
      ],
      "map_track": [...]
    }
  ],
  "all_gps_points": [...]
}
```

**字段说明**：
- `caption` 仅在 ≤ 30 张时由 Claude 写；缺失时 Claude 设计 HTML 时不展示文字
- `cover_photo_id` 是该层级的"代表照"——hero 用 `trip_summary.cover_photo_id`、day 标签用 `days[].cover_photo_id`
- `map_track` 已按时间排序，可直接喂给 Leaflet polyline

---

## 自包含承诺（不可违反）

Claude 写的 HTML **必须**：

| 不允许 | 替代 |
|-------|------|
| `<script src="https://...">` | Token 注入 + 你自己的内联 `<script>` |
| `<link rel="stylesheet" href="https://...">` | Token 注入 + 你自己的内联 `<style>` |
| `<img src="https://...">` 引用网图 | 不需要——只用 `trip-design://` 引用真实照片 |
| `@import url(...)` 外部字体 | Web fonts 用 `data:` 编码或 system font stack |

**唯一允许的在线依赖**：地图底图 tile（Leaflet 默认 OSM tile 服务器）。这是 trip-design 的设计取舍——见 `references/leaflet-inline.md`。

后处理脚本会**最终验证**：搜索 `<script src="http`、`<link ... href="http`、`<img src="http`，命中即报错（这是双保险，不替代 Claude 的自律）。

---

## 灯箱实现的最小约定

灯箱可以用任何视觉风格，但 JS 行为必须：

```javascript
// 1. 点击 .photo-card / [data-photo-id] 等元素，打开灯箱
// 2. 显示 PHOTOS[id].src 对应的大图
// 3. 显示 caption 与 datetime
// 4. 监听 keydown：← → Esc

document.addEventListener('keydown', (e) => {
  if (!lightbox.classList.contains('open')) return;
  if (e.key === 'Escape') close();
  if (e.key === 'ArrowLeft') prev();
  if (e.key === 'ArrowRight') next();
});
```

切换上下一张时**全局有序**——所有照片按 day → location → 顺序串成一个数组。这样用户从第 50 张按 `→` 能到第 51 张，跨 location 不停顿。

---

## 后处理脚本如何使用

Claude 写完 HTML 后，跑：

```bash
python3 scripts/build_diary.py \
        --in diary_data.json \
        --html <Claude 写的 HTML 文件> \
        --out output/trip.diary.html
```

可选 `--embed-photos relative` 切换为相对路径模式（适合 > 200MB 时）。

build_diary.py 的职责（不做别的）：
1. 解析 Claude 的 HTML，找所有 token（`trip-design://...`、`data-trip-design=...`）
2. 处理照片（Pillow 缩放至 1600px、HEIC→JPEG q=85）
3. 替换 token：base64 / relative path / Leaflet 字节 / JSON 数据
4. 写出最终 HTML
5. 报告体积，> 200MB 建议切 relative
6. 验证自包含（搜外部 src/href）

它**不**做：HTML 解析、CSS 改写、JS 注入（除约定的注入点）。Claude 设计什么，它就吐什么。
