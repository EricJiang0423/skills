#!/usr/bin/env python3
"""Post-process Claude-authored HTML into a self-contained trip diary.

Pipeline:
  diary_data.json + Claude-authored HTML  →  build_diary.py  →  final HTML

Token protocol (see references/diary-html-essentials.md):

  src="trip-design://photo_NNNN"                       → base64 data URL or relative path
  background: url("trip-design://photo_NNNN")          → same
  <style data-trip-design="leaflet-css"></style>       → Leaflet 1.9.4 CSS bytes
  <script data-trip-design="leaflet-js"></script>      → Leaflet 1.9.4 JS bytes
  <script type="application/json" data-trip-design="photos-index"></script>
                                                       → photos dict JSON
  <script type="application/json" data-trip-design="track"></script>
                                                       → all_gps_points JSON

Photo embedding modes:
  base64 (default): all photos inlined; HTML is fully self-contained
  relative:         photos copied to <out>.assets/ next to the HTML
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

LEAFLET_VERSION = "1.9.4"
LEAFLET_CSS_URL = f"https://unpkg.com/leaflet@{LEAFLET_VERSION}/dist/leaflet.css"
LEAFLET_JS_URL = f"https://unpkg.com/leaflet@{LEAFLET_VERSION}/dist/leaflet.js"

MAX_W = 1600
JPEG_QUALITY = 85
WARN_BYTES = 200 * 1024 * 1024  # 200 MB

PHOTO_TOKEN_RE = re.compile(r'trip-design://(photo_\d+)')

# Match <style|<script ... data-trip-design="<key>" ...></style|</script>
# Captures empty-bodied tags; we'll inject content into the body
EMPTY_INJECT_TAG_RE = re.compile(
    r'<(?P<tag>style|script)\b'
    r'(?P<attrs>[^>]*?)\s*data-trip-design="(?P<key>[a-z_-]+)"'
    r'(?P<rest>[^>]*?)>\s*</(?P=tag)>',
    re.IGNORECASE,
)


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
    """Yield photo dicts in render order across days/locations."""
    for day in diary["days"]:
        for loc in day["locations"]:
            for p in loc["photos"]:
                yield p


def build_photo_assets(diary, embed_mode, out_path: Path):
    """Process every photo. Return (id→src dict, total_bytes)."""
    src_by_id = {}
    total = 0
    assets_dir = None
    if embed_mode == "relative":
        assets_dir = out_path.with_name(out_path.stem + ".assets")
        if assets_dir.exists():
            shutil.rmtree(assets_dir)
        assets_dir.mkdir(parents=True)

    for p in collect_photos(diary):
        pid = p["id"]
        src_path = Path(p["path"])
        if not src_path.exists() or p.get("icloud_state") == "cloud_only":
            src_by_id[pid] = ""
            continue
        try:
            jpeg, mime = process_image(src_path)
        except Exception as e:
            print(f"⚠ 跳过 {src_path}：{e}", file=sys.stderr)
            src_by_id[pid] = ""
            continue
        total += len(jpeg)
        if embed_mode == "base64":
            src_by_id[pid] = to_data_url(jpeg, mime)
        else:
            asset_name = f"{pid}.jpg"
            (assets_dir / asset_name).write_bytes(jpeg)
            src_by_id[pid] = f"{assets_dir.name}/{asset_name}"
    return src_by_id, total


def build_photos_index(diary, src_by_id):
    """Index for client-side lookup (lightbox etc.)."""
    index = {}
    for p in collect_photos(diary):
        pid = p["id"]
        index[pid] = {
            "src": src_by_id.get(pid, ""),
            "caption": p.get("caption"),
            "datetime": p.get("datetime"),
        }
    return index


def replace_photo_tokens(html, src_by_id):
    missing = set()

    def sub(match):
        pid = match.group(1)
        replacement = src_by_id.get(pid)
        if replacement is None or replacement == "":
            missing.add(pid)
            return ""
        return replacement

    new_html = PHOTO_TOKEN_RE.sub(sub, html)
    return new_html, missing


def inject_into_empty_tags(html, payloads):
    """Replace empty <style|script data-trip-design="<key>"></...> with body=payloads[key].

    payloads: dict[key → str (body content)]
    Unmatched keys: payload not used. Tags whose key isn't in payloads are left as-is.
    """
    used = set()

    def sub(match):
        key = match.group("key")
        if key not in payloads:
            return match.group(0)
        used.add(key)
        body = payloads[key]
        attrs = match.group("attrs") or ""
        rest = match.group("rest") or ""
        tag = match.group("tag")
        return f'<{tag}{attrs} data-trip-design="{key}"{rest}>{body}</{tag}>'

    new_html = EMPTY_INJECT_TAG_RE.sub(sub, html)
    return new_html, used


def verify_self_contained(html):
    """Return list of violations: external src/href references."""
    violations = []
    for pattern, label in (
        (r'<script\b[^>]*\bsrc\s*=\s*["\']https?://', "external <script src=>"),
        (r'<link\b[^>]*\bhref\s*=\s*["\']https?://', "external <link href=>"),
        (r'<img\b[^>]*\bsrc\s*=\s*["\']https?://', "external <img src=>"),
        (r'@import\s+url\s*\(\s*["\']?https?://', "@import url(http...)"),
    ):
        for m in re.finditer(pattern, html, re.IGNORECASE):
            ctx = html[max(0, m.start()-20):m.end()+60].replace("\n", " ")
            violations.append(f"{label}: ...{ctx}...")
    return violations


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", type=Path, default=Path("diary_data.json"),
                    help="cluster.py 输出（含 Claude 回填的叙述）")
    ap.add_argument("--html", type=Path, required=True,
                    help="Claude 写的 HTML 文件路径（含 token）")
    ap.add_argument("--out", type=Path, default=Path("output/trip.diary.html"))
    ap.add_argument("--embed-photos", choices=["base64", "relative"], default="base64",
                    help="base64=完全自包含；relative=照片放到 .assets/ 目录")
    ap.add_argument("--leaflet-cache", type=Path,
                    default=Path.home() / ".cache" / "trip-design")
    ap.add_argument("--strict-self-contained", action="store_true",
                    help="检测到外部 src/href 引用时退出失败（默认仅警告）")
    args = ap.parse_args()

    if not args.inp.exists():
        sys.exit(f"找不到输入：{args.inp}（先跑 cluster.py 并补完 title/narrative）")
    if not args.html.exists():
        sys.exit(f"找不到 Claude 写的 HTML：{args.html}")

    diary = json.loads(args.inp.read_text(encoding="utf-8"))
    html_in = args.html.read_text(encoding="utf-8")

    src_by_id, photo_bytes = build_photo_assets(diary, args.embed_photos, args.out)
    photos_index = build_photos_index(diary, src_by_id)

    html_step1, missing = replace_photo_tokens(html_in, src_by_id)
    if missing:
        print(f"⚠ {len(missing)} 个 trip-design://photo_NNN token 找不到对应照片：",
              file=sys.stderr)
        for pid in sorted(missing)[:10]:
            print(f"  · {pid}", file=sys.stderr)

    leaflet_css, leaflet_js = fetch_leaflet(args.leaflet_cache)

    payloads = {
        "leaflet-css": leaflet_css,
        "leaflet-js": leaflet_js,
        "photos-index": json.dumps(photos_index, ensure_ascii=False),
        "track": json.dumps(diary.get("all_gps_points", []), ensure_ascii=False),
    }
    html_final, used_keys = inject_into_empty_tags(html_step1, payloads)

    not_injected = set(payloads) - used_keys
    if not_injected:
        print(f"⚠ Claude 的 HTML 缺少这些注入点（功能可能不全）：", file=sys.stderr)
        for k in sorted(not_injected):
            print(f"  · <{'style' if 'css' in k else 'script'} data-trip-design=\"{k}\"></...>",
                  file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_final, encoding="utf-8")
    html_bytes = args.out.stat().st_size

    violations = verify_self_contained(html_final)
    if violations:
        print(f"⚠ 检测到 {len(violations)} 处外部资源引用（破坏自包含承诺）：",
              file=sys.stderr)
        for v in violations[:5]:
            print(f"  · {v}", file=sys.stderr)
        if args.strict_self_contained:
            sys.exit(1)

    summary = {
        "out": str(args.out),
        "embed_mode": args.embed_photos,
        "html_bytes": html_bytes,
        "html_mb": round(html_bytes / 1024 / 1024, 2),
        "photo_bytes_processed": photo_bytes,
        "photo_mb_processed": round(photo_bytes / 1024 / 1024, 2),
        "photo_tokens_replaced": len(src_by_id) - len(missing),
        "photo_tokens_missing": len(missing),
        "injection_points_used": sorted(used_keys),
        "injection_points_missing_in_html": sorted(not_injected),
        "self_contained_violations": len(violations),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.embed_photos == "base64" and html_bytes > WARN_BYTES:
        print(f"\n⚠ HTML 体积 {summary['html_mb']} MB 超过 200 MB 阈值。",
              file=sys.stderr)
        print(f"   建议改用相对路径模式（HTML 约 1 MB + .assets/ 照片目录）：",
              file=sys.stderr)
        print(f"   python3 scripts/build_diary.py --in {args.inp} "
              f"--html {args.html} --out {args.out} --embed-photos relative",
              file=sys.stderr)


if __name__ == "__main__":
    main()
