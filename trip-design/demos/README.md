# demos/

放置示例 `.diary.html` 文件，便于潜在用户在不真正跑流水线的情况下预览 trip-design 的输出风格。

## 命名约定

```
demos/
├── README.md                                ← 本文件
├── okinawa-2-days.diary.html                ← 体积小（4 张照片，<500 KB）
└── tokyo-7-days.diary.html                  ← 中等体积示例（可选，<10 MB）
```

## 当前状态

V1 暂不附带 demo 文件——避免污染仓库体积。

要本地生成一份小示例：

```bash
# 用 PIL 造 4 张测试图片
python3 -c "
from PIL import Image
import os
os.makedirs('/tmp/trip_demo', exist_ok=True)
for i, c in enumerate([(70,140,180),(232,112,74),(125,212,224),(232,154,74)], 1):
    Image.new('RGB', (1920, 1280), c).save(f'/tmp/trip_demo/photo_{i:04d}.jpg', quality=85)
"

# 走完整流水线（需要先把 diary_data.json 的 title/narrative 手动填一下）
# 详见 README.md「手动跑」一节
```

## 注意事项

- **不要**把含真实人物的照片放进 demos/ 公开仓库——隐私风险
- 体积 < 500 KB 的示例最适合（≤ 4 张照片）
- 复杂示例放外部（GitHub Pages / 私人 Gist），用 link 在 README 引用
