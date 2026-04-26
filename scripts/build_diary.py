#!/usr/bin/env python3
"""Render diary_data.json + Jinja2 template → self-contained HTML.

Photo embedding modes:
- base64 (default): all photos inlined; HTML is fully self-contained
- relative: photos copied to <out>.assets/ next to the HTML; smaller HTML, ships with a folder
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

LEAFLET_VERSION = "1.9.4"
LEAFLET_CSS_URL = f"https://unpkg.com/leaflet@{LEAFLET_VERSION}/dist/leaflet.css"
LEAFLET_JS_URL = f"https://unpkg.com/leaflet@{LEAFLET_VERSION}/dist/leaflet.js"

MAX_W = 1600
JPEG_QUALITY = 85
WARN_BYTES = 200 * 1024 * 1024  # 200 MB


def fetch_leaflet(cache_dir: Path):
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for kind, url in (("css", LEAFLET_CSS_URL), ("js", LEAFLET_JS_URL)):
        cached = cache_dir / f"leaflet-{LEAFLET_VERSION}.{kind}"
        if not cached.exists():
            print(f"⬇ 下载 leaflet.{kind} ...", file=sys.stderr)
            req = urllib.request.Request(url, headers={"User-Agent": "trip-design/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                cached.write_bytes(resp.read())
        out[kind] = cached.read_text(encoding="utf-8")
    return out["css"], out["js"]


def process_image(src_path: Path):
    """Return (jpeg_bytes, mime). Resize to MAX_W, convert HEIC→JPEG, quality=85."""
    try:
        from PIL import Image
    except ImportError:
        sys.exit("缺 Pillow。先跑：python3 scripts/check_deps.py")

    suffix = src_path.suffix.lower()
    if suffix in (".heic", ".heif"):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            sys.exit(f"读取 {src_path} 需要 pillow-heif；安装：pip install pillow-heif "
                     f"（HEIC 解码还需 brew install libheif）")

    img = Image.open(src_path)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    if img.width > MAX_W:
        ratio = MAX_W / img.width
        img = img.resize((MAX_W, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue(), "image/jpeg"


def to_data_url(jpeg_bytes, mime="image/jpeg"):
    encoded = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def collect_photos(diary):
    """Yield (photo_dict, location_dict, day_dict) tuples in render order."""
    for day in diary["days"]:
        for loc in day["locations"]:
            for p in loc["photos"]:
                yield p, loc, day


def render(diary, template_path: Path, out_path: Path,
           embed_mode: str, leaflet_cache: Path):
    try:
        from jinja2 import Template
    except ImportError:
        sys.exit("缺 Jinja2。先跑：python3 scripts/check_deps.py")

    leaflet_css, leaflet_js = fetch_leaflet(leaflet_cache)

    photos_index = {}
    assets_dir = None
    if embed_mode == "relative":
        assets_dir = out_path.with_suffix("").with_name(out_path.stem + ".assets")
        if assets_dir.exists():
            shutil.rmtree(assets_dir)
        assets_dir.mkdir(parents=True)

    total_photo_bytes = 0
    for p, loc, day in collect_photos(diary):
        src_path = Path(p["path"])
        if not src_path.exists() or p.get("icloud_state") == "cloud_only":
            p["src"] = ""
            photos_index[p["id"]] = {
                "src": "",
                "caption": p.get("caption"),
                "datetime": p.get("datetime"),
            }
            continue

        try:
            jpeg, mime = process_image(src_path)
        except Exception as e:
            print(f"⚠ 跳过 {src_path}：{e}", file=sys.stderr)
            p["src"] = ""
            continue

        total_photo_bytes += len(jpeg)
        if embed_mode == "base64":
            p["src"] = to_data_url(jpeg, mime)
        else:
            asset_name = f"{p['id']}.jpg"
            (assets_dir / asset_name).write_bytes(jpeg)
            p["src"] = f"{assets_dir.name}/{asset_name}"

        photos_index[p["id"]] = {
            "src": p["src"],
            "caption": p.get("caption"),
            "datetime": p.get("datetime"),
        }

    location_count = sum(len(d["locations"]) for d in diary["days"])
    trip = dict(diary["trip_summary"])
    trip["title"] = trip.get("title") or "我的旅行"
    trip["location_count"] = location_count

    cover_id = trip.get("cover_photo_id")
    cover_src = photos_index.get(cover_id, {}).get("src") if cover_id else None

    context = {
        "trip": trip,
        "days": diary["days"],
        "cover_src": cover_src,
        "leaflet_css": leaflet_css,
        "leaflet_js": leaflet_js,
        "photos_index_json": json.dumps(photos_index, ensure_ascii=False),
        "track_json": json.dumps(diary["all_gps_points"], ensure_ascii=False),
        "build_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    template = Template(template_path.read_text(encoding="utf-8"))
    html = template.render(**context)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path.stat().st_size, total_photo_bytes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, default=Path("diary_data.json"))
    ap.add_argument("--template", type=Path, default=Path("assets/diary-template.html"))
    ap.add_argument("--out", type=Path, default=Path("output/trip.diary.html"))
    ap.add_argument("--embed-photos", choices=["base64", "relative"], default="base64",
                    help="base64=完全自包含；relative=照片放到 .assets/ 目录")
    ap.add_argument("--leaflet-cache", type=Path,
                    default=Path.home() / ".cache" / "trip-design")
    args = ap.parse_args()

    if not args.inp.exists():
        sys.exit(f"找不到输入：{args.inp}（先跑 cluster.py 并补完 title/narrative）")
    if not args.template.exists():
        sys.exit(f"找不到模板：{args.template}")

    diary = json.loads(args.inp.read_text(encoding="utf-8"))
    html_bytes, photo_bytes = render(
        diary, args.template, args.out,
        embed_mode=args.embed_photos,
        leaflet_cache=args.leaflet_cache,
    )

    summary = {
        "out": str(args.out),
        "embed_mode": args.embed_photos,
        "html_bytes": html_bytes,
        "html_mb": round(html_bytes / 1024 / 1024, 2),
        "photo_bytes_processed": photo_bytes,
        "photo_mb_processed": round(photo_bytes / 1024 / 1024, 2),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.embed_photos == "base64" and html_bytes > WARN_BYTES:
        print(f"\n⚠ HTML 体积 {summary['html_mb']} MB 超过 200 MB 阈值。",
              file=sys.stderr)
        print(f"   建议改用相对路径模式（HTML 约 1 MB + .assets/ 照片目录）：",
              file=sys.stderr)
        print(f"   python3 scripts/build_diary.py --in {args.inp} "
              f"--template {args.template} --out {args.out} --embed-photos relative",
              file=sys.stderr)


if __name__ == "__main__":
    main()
