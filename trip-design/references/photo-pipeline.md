# photo-pipeline · EXIF / HEIC / RAW 提取实战

## 时间字段优先级

数码相机/手机的 EXIF 里有多个时间字段，含义不同。trip-design 的优先级：

```
1. EXIF:DateTimeOriginal      ← 拍摄瞬间（按下快门时）
2. XMP:DateTimeOriginal       ← Lightroom/Photos 编辑时同步的副本
3. EXIF:CreateDate            ← 文件被相机写入时（≈ DateTimeOriginal，一般差零点几秒）
4. QuickTime:CreateDate       ← 视频/Live Photo 才有
5. File:FileModifyDate        ← 系统文件 mtime（**最后兜底**，不可靠）
```

**为什么这个顺序**：DateTimeOriginal 是拍摄时刻，绝大多数情况下唯一可信。FileModifyDate 在以下场景会"骗"你：
- 用户从硬盘 A 拷到硬盘 B → mtime 变成今天
- AirDrop 传输 → mtime 变成接收时刻
- iCloud 同步下载 → mtime 变成下载时刻

兜底用 mtime 时**必须**告诉用户「这张照片可能没有原始 EXIF 时间」。

## 时区处理

EXIF 里时间默认是 **naive**（不带时区）——拍摄设备的本地时间。少数新机器有 `EXIF:OffsetTime` 或 `EXIF:OffsetTimeOriginal` 标 UTC 偏移。

trip-design 的策略：
- 把所有时间当**拍摄地本地时间**用（不做时区转换）
- 跨时区旅行（东京 → 巴黎）EXIF 时间也是各地本地时间，按日期分组本就符合"按当地一天"的直觉
- 如果用户问"为什么时间显示 9:15 但我记得是 10:15"——99% 是 iPhone 在飞机上没换时区，answer is dst/手动改时区，不是脚本 bug

## HEIC 解码踩坑

iPhone 默认 HEIC（HEIF/HEVC）。Pillow 不原生支持，需要：

```bash
brew install libheif       # 系统库
pip install pillow-heif    # Python 绑定
```

代码里**必须**注册 opener：

```python
import pillow_heif
pillow_heif.register_heif_opener()
img = Image.open("IMG_1234.HEIC")  # 注册后才能用
```

不注册 → `UnidentifiedImageError`，错误信息不指向 HEIC 问题，容易误诊。

**RAW 也建议借道 exiftool**：直接用 Pillow 打开 .DNG/.ARW/.CR3 几乎不行，但这些格式的 EXIF 还是能用 exiftool 完整读出来。trip-design 只读 EXIF 不解码 RAW 像素——build_diary.py 处理 RAW 时会跳过并标 `skip_reason: 'raw_decode_unsupported'`。

## RAW 字段差异速查

| 厂商 | 后缀 | EXIF 标签命名特点 |
|------|------|-------------------|
| Adobe DNG | .dng | 标准 EXIF，与 JPEG 几乎一致 |
| Sony ARW | .arw | 多一组 `Sony:*` 标签，时间字段标准 |
| Canon CR2/CR3 | .cr2/.cr3 | `Canon:*` 私有标签多，标准时间字段在 |
| Nikon NEF | .nef | 标准 + `Nikon:*` 私有 |
| Fuji RAF | .raf | 标准 + `FujiFilm:*` |
| Panasonic RW2 | .rw2 | 标准 |

**实操**：只读标准 EXIF（`EXIF:*` / `Composite:*`）就够了，私有厂商标签不碰。

## GPS 坐标格式

EXIF GPS 是 DMS（度分秒）+ 方向 ref（N/S/E/W），需要转十进制：

```
lat_dms = 26 deg 12' 50.4"  +  ref = "N"
       → 26 + 12/60 + 50.4/3600  =  26.21400°
```

南半球（S）和西半球（W）需要 `* -1`。

PyExifTool 通常直接给 `Composite:GPSLatitude` 当浮点数，但**不要假设**——脚本里两种都处理。

## 为什么 GPS 缺失不丢弃

很多人在室内、夜间、相机省电模式下拍的照片没 GPS。直接丢掉等于把"那天晚上的酒店一夜"全删了。

trip-design 的规则：**无 GPS 照片继承前一张照片的地点**。这是合理近似——用户从外面回酒店，酒店附近 500m 内的可能性 > 90%。

## 文件 ID 命名

`raw_photos.json` 里 `id` 用 `photo_NNNN`（4 位零填充）而不是 UUID 或 hash：
- 短，可读
- 在 lightbox 里 debug 时一眼能找
- 跨脚本稳定（cluster / build_diary 都引用）

如果同一目录下扫描两次，ID 会变（按文件枚举顺序）——这是 OK 的，因为流水线一次性走完。
