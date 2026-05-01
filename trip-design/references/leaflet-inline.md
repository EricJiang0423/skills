# leaflet-inline · 离线地图嵌入

trip-design HTML 的地图用 [Leaflet 1.9.4](https://leafletjs.com/) **inline**（库本身嵌入到 HTML 里），底图 tile 仍走 OpenStreetMap 在线。

## 为什么 Leaflet 1.9.4

- 最后一个稳定大版本（2024 年发布）
- 文件大小：CSS ~ 14 KB / JS ~ 142 KB（共 156 KB），完全可接受
- API 简单稳定，30 行 JS 能搞定地图 + 轨迹线 + 标记
- MIT license，可以无忧 inline

不要追新版本——2.x 还在测试，破坏性 API 改动会让模板 rewrite。

## 在线 vs 离线的边界

| 部分 | 离线 | 在线 |
|------|------|------|
| Leaflet JS 库 | ✓ inline 进 HTML | — |
| Leaflet CSS | ✓ inline 进 HTML | — |
| **地图 tile 图片** | — | OpenStreetMap CDN（https://*.tile.openstreetmap.org/）|
| 轨迹/标记数据 | ✓ 嵌入 JSON | — |

**为什么 tile 不离线**：

| 方案 | 代价 |
|------|------|
| Tile 在线（当前）| 需要联网才能看地图；HTML 体积小 |
| Tile 缓存到 base64 | 一份旅行的 tiles 约 5-50 MB；HTML 大幅膨胀，且只覆盖那一次旅行的 zoom 范围 |
| Tile 用 Vector tiles（PMTiles）| 需要额外 JS 库 + 全球数据 100MB+，不现实 |

trip-design 接受"看地图需联网"的限制。HTML 仍可双击打开，没网时地图区域显示为灰色 + "无法加载地图"，其余功能（照片、叙述、灯箱）完全可用。

## OpenStreetMap 使用规范

[OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/)：

| 规则 | trip-design 实现 |
|------|-----------------|
| 单用户偶发请求 OK | ✓ 一份日记打开几次 |
| 必须 attribution | ✓ HTML 里地图右下角"© OpenStreetMap" |
| 不可重型应用大量请求 | ✓ 单页静态地图，远未达限 |
| 用户应知道 tile 来源 | ✓ attribution 已显示 |

如果用户量级到了"我每周生成 100 份日记并且分享给 10000 人浏览" → OSM 不再是合适来源，应自托管 tile 或换商用服务（Mapbox / Stadia）。trip-design V1 不为这种规模设计。

## Token 注入协议（写 HTML 时如何引用）

trip-design 的 HTML 由 Claude 现场写、build_diary.py 后处理。Leaflet 字节不在 Claude 写 HTML 时手嵌——会爆 context。

写 HTML 时**留两个空标签**作为 token：

```html
<head>
  ...
  <style data-trip-design="leaflet-css"></style>   <!-- ← Leaflet CSS 注入点 -->
  ...
</head>
<body>
  ...
  <script data-trip-design="leaflet-js"></script>  <!-- ← Leaflet JS 注入点 -->
  <script>
    // 这里写你自己的地图初始化 JS
    const map = L.map('overview-map');
    L.tileLayer(...).addTo(map);
    ...
  </script>
</body>
```

build_diary.py 会把这两个空标签的 textContent 填上 Leaflet 1.9.4 的 CSS / JS 字节内容。

**位置硬约束**：
- `<style data-trip-design="leaflet-css">` 必须在 `<head>` 里——否则 `.leaflet-container` 等样式来不及生效
- `<script data-trip-design="leaflet-js">` 必须在你自己的地图初始化 JS **之前**——否则 `L` 全局变量未定义

**完整说明**见 `references/diary-html-essentials.md` 的 Token 协议章节。

## 关键 API 用法

### 初始化地图 + 自适应边界

```javascript
const map = L.map('overview-map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap',
  maxZoom: 18,
}).addTo(map);
map.fitBounds(L.latLngBounds(latlngs).pad(0.15));   // 0.15 = 留 15% 边距
```

不要 hardcode `setView([lat, lon], zoom)`——`fitBounds` 自动包住所有点。

### 轨迹线

```javascript
L.polyline(latlngs, {color: '#e8704a', weight: 3, opacity: 0.7}).addTo(map);
```

`latlngs` 是 `[[lat1, lon1], [lat2, lon2], ...]`，按时间排序（cluster.py 已经排好）。

### 标记 + tooltip

```javascript
L.circleMarker([lat, lon], {
  radius: 6, color: '#fff', weight: 2,
  fillColor: '#e8704a', fillOpacity: 0.95,
}).bindTooltip(placeName + ' · ' + time, {direction: 'top'}).addTo(map);
```

用 `circleMarker`（CSS 圆点）而不是默认的图钉 icon——后者需要额外 PNG 文件，破坏自包含。

### 无 GPS 的兜底

```javascript
if (!TRACK || TRACK.length === 0) {
  document.getElementById('overview-map').innerHTML =
    '<div style="...">无 GPS 数据</div>';
  return;
}
```

## 为什么不用其他地图库

| 库 | 不选的理由 |
|----|-----------|
| Mapbox GL JS | 需要 access token；商用授权；体积大（800 KB+）|
| Google Maps JS | 需要 API key；隐私差（每次打开都向 Google 打报告）|
| MapLibre GL | 矢量瓦片本地化复杂；trip-design 用不到 GPU 渲染 |
| OpenLayers | 体积大（500 KB+）；API 比 Leaflet 复杂 |

Leaflet + OSM tile 是 trip-design 这种"一次性自包含 HTML"的最优解。

## Tile fallback / 错误处理

OSM tile CDN 偶尔 503。Leaflet 默认会显示空白瓦片。当前不处理（无网/CDN 挂了不是 trip-design 的问题），用户能看出"地图没加载"自己判断。

未来如果需要 fallback，可加：

```javascript
const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {...});
const carto = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {...});
osm.on('tileerror', () => map.removeLayer(osm).addLayer(carto));
```

V1 不做。
