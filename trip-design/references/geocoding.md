# geocoding · Nominatim 反向地理编码

trip-design 用 OpenStreetMap 的 [Nominatim](https://nominatim.org/) 服务做反向地理编码（GPS → 地名）。免费、无 API key、有规范要遵守。

## Nominatim 使用规范（[原文](https://operations.osmfoundation.org/policies/nominatim/)）

| 规则 | 实现 |
|------|------|
| **每秒最多 1 个请求** | `geocode.py` 在每次请求前 `time.sleep(1.0 - elapsed)` |
| **必须带可识别的 User-Agent** | `User-Agent: trip-design/0.1 (https://github.com/...)` 含联系方式 |
| **结果应缓存** | 磁盘 `geocode_cache.json`，键 = GPS 截断到小数点后 3 位 |
| **大批量请求建议自托管** | trip-design 单次旅行 < 200 个不同地点，远低于公共服务的合理范围 |
| **不可商用滥用** | 个人旅行日记是合理用途 |

违反这些规则会被临时封 IP（通常 24h）。100 张照片的旅行约 50-100 个不同区域，磁盘缓存命中后实际请求 ≤ 50 次，1 分钟内完成。

## 缓存键设计

```python
key = f"{round(lat, 3):.3f},{round(lon, 3):.3f}"   # 例如 "26.214,127.681"
```

**为什么是小数点后 3 位**：

| 小数位 | 经度 1° 距离 | 实际精度（赤道）|
|-------|-------------|----------------|
| 6 位 | 11 cm | 几乎不缓存命中 |
| 5 位 | 1.1 m | 室内不同房间 |
| 4 位 | 11 m | 同建筑不同楼层 |
| **3 位** | **111 m** | **同街区** ← trip-design |
| 2 位 | 1.1 km | 同小镇 |

3 位精度能让"在国際通り上走 200 米"的两张照片共用一次查询，但不会把"国際通り"和"那覇空港"（5 km 外）混为一谈。

## 地名层级提取

Nominatim 返回的 `address` dict 有几十个可能字段，trip-design 只取 4 层：

```python
suburb  = address.get("suburb") or address.get("neighbourhood")
        or address.get("quarter") or address.get("hamlet")
        or address.get("village") or address.get("road")
city    = address.get("city")    or address.get("town")
        or address.get("municipality") or address.get("county")
region  = address.get("state")   or address.get("region") or address.get("province")
country = address.get("country")
```

不同国家的行政层级差异巨大——日本有「県/市/町/字」，美国有「state/county/city/neighborhood」，中国有「省/市/区/街道」。多 fallback 链是为了在不同国家都能出可读的层级。

## 限速触发的处理

Nominatim 偶尔返回 429（rate limit）或超时。`geocode.py` 的策略：

```python
for attempt in range(3):
    try:
        location = geocoder.reverse(...)
        break
    except (GeocoderTimedOut, GeocoderUnavailable):
        time.sleep(2 ** attempt)   # 2s, 4s, 8s
```

3 次都失败 → 该照片 `place: null`，流水线继续。后续 cluster.py 把它归入"未知地点"组，不中断。

## 语言

`geocoder.reverse(..., language="zh-CN")` 让 Nominatim 优先返回中文地名（如果有）。trip-design 默认 `zh-CN`，可通过 `--language` 改：

| Lang | 适用 |
|------|------|
| `zh-CN` | 默认，中文用户 |
| `ja` | 日本旅行希望保留日文原名（"国際通り" 而非"国际通") |
| `en` | 英文用户 / 国际旅行 |

注意：Nominatim 不一定有所有语言的地名，没有时回落到本地语言（"那覇市" 没中文翻译就给"那覇市"原文）。

## 不要做的事

- ❌ **不要**把照片字节也发给 Nominatim 或任何地理服务——只发 GPS 坐标（违反隐私原则 #0）
- ❌ **不要**用付费服务（Google Maps Geocoding API）替换——用户没要求 API key 的负担
- ❌ **不要**自己拼 query 绕过 geopy——geopy 已经处理了 User-Agent / 限速 hint / 错误重试
- ❌ **不要**降频到 0.5 req/s 以下"为了保险"——Nominatim 明确说 1 req/s 是允许的，更慢只是浪费用户时间
