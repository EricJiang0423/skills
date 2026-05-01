# osxphotos-tips · Photos.app / iCloud 集成

`osxphotos` 直读 Photos.app 的 SQLite 库（`~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite`），**仅 macOS**。

## 三种 iCloud 状态识别

Photos.app 里同一张照片有三种"在不在本机"的状态：

| 状态 | osxphotos 字段判断 | 含义 | trip-design 动作 |
|------|-------------------|------|-----------------|
| `local` | `p.path` 存在且 `Path(p.path).exists()` | 完整原图在本机 | 直接处理 |
| `optimized` | `p.path` 存在但点击"在 Finder 中显示"是缩略图；或 `p.path` 是 `path_edited`／`path_derivatives` | 本机只有缩略图，原图在 iCloud | 询问下载 vs 用缩略图 |
| `cloud_only` | `p.iscloudasset and not p.path` | 本机完全没有，连缩略图都是按需加载 | 默认跳过；问用户要不要等 |

判断逻辑写进 `extract_photos.py:scan_photosapp()`。

## 触发 iCloud 下载

osxphotos 有 `--download-missing` 标志，但本质是后台请求 PhotoKit 下载——耗时取决于带宽（一张 4MB JPEG 约 5-15 秒；100 张 HEIC 可能 5-15 分钟）。

```bash
osxphotos export ./out --download-missing --uuid <uuid>
```

trip-design 不直接跑 export，而是：
1. 提示用户「需要下载 N 张，预计 X 分钟」
2. 用户同意后用 `PhotosDB().photos(uuid=[...])` 配合 `download_missing=True` 触发

## "完全磁盘访问" 授权

读 `Photos.sqlite` 需要授权 macOS 沙盒例外。**不授权时 osxphotos 会抛 sqlite OperationalError**，错误信息含 `unable to open database file`——见这条就跳到下面的指引：

```
osxphotos 读不到 Photos 库——需要给运行 trip-design 的程序「完全磁盘访问」权限：

1. 打开「系统设置」→「隐私与安全性」
2. 左侧选「完全磁盘访问」
3. 点 + 加入：
   · Terminal.app（如果你在 Terminal 跑）
   · iTerm.app（如果你在 iTerm 跑）
   · Cursor / VS Code（如果在 IDE 集成终端跑）
4. 重启上述程序，再跑一次

授权一次永久生效，跨 trip-design 的多次调用都有效。
```

## 相册名查询

```python
db = osxphotos.PhotosDB()
all_albums = [a.title for a in db.album_info]    # 列出所有相册名
photos = [p for p in db.photos()
          if "冲绳 2024" in (a.title for a in p.album_info)]
```

**注意**：相册名严格匹配（含空格/全半角字符）。用户告诉你「冲绳 2024」时**先列相册让 ta 确认**，避免拼写差异：

```
我在你的 Photos.app 里找到这些相册（共 N 个），最像「冲绳 2024」的是：
  1. 冲绳 2024
  2. 沖縄 2024（日文版）
  3. Okinawa 2024
你要哪个？
```

## 日期范围查询

```python
photos = [p for p in db.photos()
          if p.date and "2024-03-01" <= p.date.date().isoformat() <= "2024-03-07"]
```

`p.date` 已经是带时区的 datetime（拍摄地本地时间）。trip-design 取 `.date()` 转日期再字符串比较——避免时区计算。

## 原图字节数

`p.original_filesize` 是 iCloud 元数据里的字节数（即使本机没下载也能拿到）。`p.path` 不在时（cloud_only），用这个估算"下载需要多久"——按 5 MB/s 估带宽 + 总字节。

## 跨账户

osxphotos 默认读"主账户"的照片库。多账户用户用 `PhotosDB(library_path=...)` 显式指定。trip-design 不暴露这个参数（V1 假设主账户），用户问起再说。

## 按时间范围发现潜在旅行段的启发式

`extract_photos.py --list-recent-trips` 用一组阈值在用户的 Photos.app 库里**发现"看起来像旅行"的连续日期段**，输出供 Claude 给用户列候选。这是「一键时间范围模式」的入口。

### 算法

```
1. 取近 N 天（默认 90）所有有日期的照片
2. 按拍摄日期 group，得到每天的照片集合
3. 把日期排序后扫描，相邻日期间隔 ≤ 2 天就连成同一段，> 2 天断开
4. 段内 photos 数 < 10 → 丢弃
5. 段长度 < 2 天 或 > 14 天 → 丢弃
6. 按 start 倒序排（最近的旅行在前）
7. 给每段加 guess_label：首张有 GPS 的照片的 place.name 或 place.address.city，加 "N 天"
```

### 阈值由来

| 阈值 | 值 | 为什么 |
|------|-----|------|
| **回看天数** | 90 天 | 覆盖近 1 季度。再往前用户多半已经处理过；再短（30 天）会漏掉两个月前的一次旅行 |
| **段间隔断开** | > 2 天 | 旅行中可能有 1 天酒店休整、一整天阴雨没拍——但不会连续两天都不拍 |
| **段内最少照片** | ≥ 10 张 | 过滤 "周末郊游"（5-8 张）、"出差顺手拍"（2-3 张）。10 张是"专门为旅行拍照"的合理下限 |
| **段最短长度** | ≥ 2 天 | 1 天的不算"旅行"，算"出门一趟"——不需要 trip-design 这种重型工具 |
| **段最长长度** | ≤ 14 天 | > 14 天通常是"日常生活段"（连续两周每天拍咖啡、宠物）而非集中旅行；真长途旅行也罕见，遇到时用户会手动给精确范围 |

### 反例

| 反例 | 当前算法表现 | 备注 |
|------|-------------|------|
| 用户每天都拍咖啡早餐 | 整段被判定为旅行 | **正确处理**：长度会 > 14 天被过滤 |
| 用户连续 3 天周末爬山，10 张以下 | 不显示 | 数量门槛过滤掉 |
| 用户旅行 5 天但中间 2 天在酒店没拍 | 拆成 2 段（如果间隔 > 2 天）| 算法局限。用户在 🛑(b) 聚类检查点会察觉到，可手动给精确 `--date-range` |
| 用户旅行 20 天 | 不显示 | 算法局限。用户会自己说"3/1 到 3/20 的照片"显式给范围 |

阈值是模块顶部常量，未来如果发现某类用户（自驾长途/工作出差党）需要不同默认，再考虑预设。V1 不暴露 CLI flag。

### guess_label 取首张照片地点的原因

旅行的"第一张照片"通常是抵达瞬间——机场、车站、酒店窗外——地点最具代表性。中段照片可能在景区/餐厅/路上，难以代表整段旅行。末段照片在返程，也不代表"去了哪"。

osxphotos 的 `photo.place` 可能因为以下原因不可用：
- 照片无 GPS（室内、夜间）→ 算法 fallback 到下一张有 GPS 的
- iCloud 反向地理编码缓存未命中 → 此时 `place.name` 为 None；fallback 到只显示天数
- 照片来自第三方导入（无 EXIF GPS）→ 同上

`guess_label` 不可用时显示「N 天」是可接受的——用户看见日期范围 + 天数，仍能判断"这是不是我想分析的那次旅行"。

