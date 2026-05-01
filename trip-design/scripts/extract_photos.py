#!/usr/bin/env python3
"""Extract EXIF metadata from a folder or a Photos.app source.

Output JSON schema (raw_photos.json):
[
  {
    "id": "photo_001",
    "path": "/absolute/path/IMG_1234.jpg",
    "datetime": "2024-03-02T14:35:22",   // ISO 8601, naive (no tz suffix)
    "datetime_source": "DateTimeOriginal|CreateDate|FileModifyDate",
    "gps": {"lat": 26.33, "lon": 127.79, "available": true},
    "filesize": 4823910,                  // bytes
    "icloud_state": "local|optimized|cloud_only",
    "skip_reason": null
  },
  ...
]
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif",
                 ".dng", ".arw", ".cr2", ".cr3", ".nef", ".raf", ".rw2"}

DATE_KEYWORDS = {"today", "yesterday",
                 "this-week", "last-week",
                 "this-month", "last-month"}


def _parse_iso_date(s):
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise ValueError(f"不是合法日期：{s}") from e


def _resolve_keyword(kw, today):
    if kw == "today":
        return today, today
    if kw == "yesterday":
        d = today - timedelta(days=1)
        return d, d
    if kw == "this-week":
        monday = today - timedelta(days=today.weekday())
        return monday, today
    if kw == "last-week":
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(days=7)
        last_sunday = this_monday - timedelta(days=1)
        return last_monday, last_sunday
    if kw == "this-month":
        return today.replace(day=1), today
    if kw == "last-month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    raise ValueError(f"未知关键词：{kw}")


def normalize_date_range(values, today=None):
    """Resolve --date-range argument(s) to (start_iso, end_iso) date strings.

    Accepts:
      ['today']/['yesterday']/['this-week']/['last-week']/['this-month']/['last-month']
      ['YYYY-MM']           → first..last day of month
      ['YYYY-MM-DD']        → that single day
      ['YYYY-MM-DD','YYYY-MM-DD']  → unchanged after validation
    """
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError("date-range 至少需要一个值")
    today = today or date.today()

    if len(values) == 2:
        start = _parse_iso_date(values[0])
        end = _parse_iso_date(values[1])
        if start > end:
            raise ValueError(f"start ({start}) 晚于 end ({end})")
        return start.isoformat(), end.isoformat()

    if len(values) > 2:
        raise ValueError("date-range 只接受 1 或 2 个值")

    v = values[0].strip().lower()
    if v in DATE_KEYWORDS:
        s, e = _resolve_keyword(v, today)
        return s.isoformat(), e.isoformat()
    if re.fullmatch(r"\d{4}-\d{2}", v):
        y, m = map(int, v.split("-"))
        last = calendar.monthrange(y, m)[1]
        return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{last:02d}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        d = _parse_iso_date(v)
        return d.isoformat(), d.isoformat()
    raise ValueError(f"不识别的 date-range：{values[0]!r}（"
                     "支持 YYYY-MM-DD / YYYY-MM-DD YYYY-MM-DD / YYYY-MM / "
                     "today / yesterday / this-week / last-week / "
                     "this-month / last-month）")


def parse_exif_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    s = str(value).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y:%m:%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s.split("+")[0].split("-0")[0].strip(), fmt
                                     ).replace(microsecond=0).isoformat()
        except ValueError:
            continue
    return None


def gps_dms_to_dd(value, ref):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        dd = float(value)
    else:
        s = str(value)
        if " " in s:
            parts = [float(p.strip(" deg'\"")) for p in s.replace(",", " ").split()
                     if p.strip(" deg'\"")]
            if len(parts) >= 3:
                dd = parts[0] + parts[1] / 60 + parts[2] / 3600
            else:
                try:
                    dd = float(parts[0])
                except (ValueError, IndexError):
                    return None
        else:
            try:
                dd = float(s)
            except ValueError:
                return None
    if ref and ref.upper() in ("S", "W"):
        dd = -dd
    return round(dd, 6)


def extract_one(meta, file_path):
    dt_iso = None
    dt_source = None
    for key, source in (
        ("EXIF:DateTimeOriginal", "DateTimeOriginal"),
        ("XMP:DateTimeOriginal", "DateTimeOriginal"),
        ("EXIF:CreateDate", "CreateDate"),
        ("QuickTime:CreateDate", "CreateDate"),
        ("File:FileModifyDate", "FileModifyDate"),
    ):
        if key in meta:
            parsed = parse_exif_datetime(meta[key])
            if parsed:
                dt_iso = parsed
                dt_source = source
                break
    if not dt_iso:
        try:
            mtime = file_path.stat().st_mtime
            dt_iso = datetime.fromtimestamp(mtime).replace(microsecond=0).isoformat()
            dt_source = "FileModifyDate"
        except OSError:
            pass

    lat = gps_dms_to_dd(meta.get("EXIF:GPSLatitude") or meta.get("Composite:GPSLatitude"),
                        meta.get("EXIF:GPSLatitudeRef"))
    lon = gps_dms_to_dd(meta.get("EXIF:GPSLongitude") or meta.get("Composite:GPSLongitude"),
                        meta.get("EXIF:GPSLongitudeRef"))

    return {
        "datetime": dt_iso,
        "datetime_source": dt_source,
        "gps": {"lat": lat, "lon": lon, "available": lat is not None and lon is not None},
        "filesize": meta.get("File:FileSize") or meta.get("File:FileSizeNum"),
    }


def scan_folder(folder: Path):
    try:
        from exiftool import ExifToolHelper
    except ImportError:
        sys.exit("缺 PyExifTool。先跑：python3 scripts/check_deps.py")

    files = sorted(p for p in folder.rglob("*")
                   if p.is_file() and p.suffix.lower() in SUPPORTED_EXT
                   and not p.name.startswith("."))
    if not files:
        sys.exit(f"在 {folder} 没找到支持的照片文件")

    records = []
    with ExifToolHelper() as et:
        metas = et.get_metadata([str(f) for f in files])
        for idx, (f, meta) in enumerate(zip(files, metas), start=1):
            extracted = extract_one(meta, f)
            try:
                size = f.stat().st_size
            except OSError:
                size = extracted.get("filesize")
            records.append({
                "id": f"photo_{idx:04d}",
                "path": str(f.resolve()),
                "datetime": extracted["datetime"],
                "datetime_source": extracted["datetime_source"],
                "gps": extracted["gps"],
                "filesize": size,
                "icloud_state": "local",
                "skip_reason": None,
            })
    return records


def scan_photosapp(album=None, date_range=None):
    """Photos.app mode via osxphotos. Returns same schema as scan_folder.
    cloud_only photos are included with skip_reason='cloud_only' (default skip).
    """
    try:
        import osxphotos
    except ImportError:
        sys.exit("缺 osxphotos。先跑：python3 scripts/check_deps.py")

    db = osxphotos.PhotosDB()
    photos = db.photos()

    if album:
        photos = [p for p in photos if album in (a.title for a in p.album_info)]
    if date_range:
        start, end = date_range
        photos = [p for p in photos
                  if p.date and start <= p.date.date().isoformat() <= end]

    if not photos:
        sys.exit("Photos.app 里没匹配到照片。检查相册名或日期范围。")

    records = []
    for idx, p in enumerate(photos, start=1):
        if p.iscloudasset and not p.path:
            state = "cloud_only"
            file_path = None
        elif p.path and Path(p.path).exists():
            state = "local"
            file_path = p.path
        else:
            state = "optimized"
            file_path = p.path_edited or p.path

        gps_avail = p.latitude is not None and p.longitude is not None
        records.append({
            "id": f"photo_{idx:04d}",
            "path": str(Path(file_path).resolve()) if file_path else f"<icloud:{p.uuid}>",
            "datetime": p.date.replace(tzinfo=None, microsecond=0).isoformat()
                        if p.date else None,
            "datetime_source": "DateTimeOriginal",
            "gps": {
                "lat": round(p.latitude, 6) if gps_avail else None,
                "lon": round(p.longitude, 6) if gps_avail else None,
                "available": gps_avail,
            },
            "filesize": p.original_filesize,
            "icloud_state": state,
            "skip_reason": "cloud_only" if state == "cloud_only" else None,
        })
    return records


def list_albums():
    """List all Photos.app albums with photo count and date range. JSON to stdout."""
    try:
        import osxphotos
    except ImportError:
        sys.exit("缺 osxphotos。先跑：python3 scripts/check_deps.py")
    db = osxphotos.PhotosDB()
    albums = []
    for a in db.album_info:
        photos = a.photos
        if not photos:
            continue
        dates = sorted(p.date.date().isoformat() for p in photos if p.date)
        albums.append({
            "title": a.title,
            "photo_count": len(photos),
            "date_first": dates[0] if dates else None,
            "date_last": dates[-1] if dates else None,
        })
    albums.sort(key=lambda a: (a["date_last"] or "", a["title"]), reverse=True)
    return {"albums": albums}


def _trip_label(first_photo, span_days):
    span_str = f"{span_days} 天"
    if not first_photo:
        return span_str
    place = getattr(first_photo, "place", None)
    if place is not None:
        for attr in ("name", "city"):
            val = getattr(place, attr, None)
            if val:
                return f"{val} · {span_str}"
        addr = getattr(place, "address", None)
        if addr is not None:
            for attr in ("city", "country"):
                val = getattr(addr, attr, None)
                if val:
                    return f"{val} · {span_str}"
    return span_str


def list_recent_trips(days=90, today=None):
    """Heuristic: detect "potential trip segments" in last N days.

    Segment rules: continuous days (gap ≤ 2 days), span 2-14 days, ≥ 10 photos.
    Returns most-recent first.
    """
    try:
        import osxphotos
    except ImportError:
        sys.exit("缺 osxphotos。先跑：python3 scripts/check_deps.py")
    today = today or date.today()
    cutoff = (today - timedelta(days=days)).isoformat()

    db = osxphotos.PhotosDB()
    by_day = {}
    for p in db.photos():
        if not p.date:
            continue
        d = p.date.date().isoformat()
        if d < cutoff:
            continue
        by_day.setdefault(d, []).append(p)

    if not by_day:
        return {"trips": [], "lookback_days": days, "cutoff": cutoff}

    days_sorted = sorted(by_day.keys())
    segments = []
    cur_start = cur_end = days_sorted[0]
    for d in days_sorted[1:]:
        prev_dt = date.fromisoformat(cur_end)
        cur_dt = date.fromisoformat(d)
        if (cur_dt - prev_dt).days <= 2:
            cur_end = d
        else:
            segments.append((cur_start, cur_end))
            cur_start = cur_end = d
    segments.append((cur_start, cur_end))

    trips = []
    for start, end in segments:
        seg_days = [d for d in days_sorted if start <= d <= end]
        seg_photos = [p for d in seg_days for p in by_day[d]]
        photo_count = len(seg_photos)
        span_days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        if photo_count < 10 or span_days < 2 or span_days > 14:
            continue
        seg_photos.sort(key=lambda p: p.date)
        first_with_gps = next(
            (p for p in seg_photos if p.latitude and p.longitude), None)
        trips.append({
            "start": start, "end": end,
            "photo_count": photo_count,
            "span_days": span_days,
            "guess_label": _trip_label(first_with_gps or seg_photos[0], span_days),
        })

    trips.sort(key=lambda t: t["start"], reverse=True)
    return {"trips": trips, "lookback_days": days, "cutoff": cutoff}


def _build_summary(records):
    return {
        "total": len(records),
        "local": sum(1 for r in records if r["icloud_state"] == "local"),
        "optimized": sum(1 for r in records if r["icloud_state"] == "optimized"),
        "cloud_only": sum(1 for r in records if r["icloud_state"] == "cloud_only"),
        "with_gps": sum(1 for r in records if r["gps"]["available"]),
        "no_gps": sum(1 for r in records if not r["gps"]["available"]),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--folder", type=Path, help="本地照片文件夹（递归扫描）")
    src.add_argument("--album", type=str, help="Photos.app 相册名")
    src.add_argument(
        "--date-range", nargs="+", metavar="RANGE",
        help="日期范围。可用：'YYYY-MM-DD YYYY-MM-DD' / 'YYYY-MM-DD' / "
             "'YYYY-MM' / today / yesterday / this-week / last-week / "
             "this-month / last-month")
    src.add_argument("--list-albums", action="store_true",
                     help="列出 Photos.app 所有相册（JSON 到 stdout）")
    src.add_argument("--list-recent-trips", action="store_true",
                     help="启发式列出近 --days 天内的潜在旅行段（JSON 到 stdout）")
    ap.add_argument("--out", type=Path, default=Path("raw_photos.json"))
    ap.add_argument("--dry-run", action="store_true",
                    help="只输出预检报告（不写 --out 文件）")
    ap.add_argument("--days", type=int, default=90,
                    help="--list-recent-trips 的回看天数，默认 90")
    args = ap.parse_args()

    if args.list_albums:
        json.dump(list_albums(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    if args.list_recent_trips:
        json.dump(list_recent_trips(days=args.days),
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    normalized_range = None
    if args.date_range:
        try:
            normalized_range = normalize_date_range(args.date_range)
        except ValueError as e:
            sys.exit(f"date-range 格式错误：{e}")

    if args.folder:
        if not args.folder.exists():
            sys.exit(f"文件夹不存在：{args.folder}")
        records = scan_folder(args.folder)
    elif args.album:
        records = scan_photosapp(album=args.album)
    else:
        records = scan_photosapp(date_range=normalized_range)

    summary = _build_summary(records)
    payload = {
        "summary": summary,
        "date_range_resolved": list(normalized_range) if normalized_range else None,
    }

    if args.dry_run:
        payload["dry_run"] = True
        payload["would_write"] = str(args.out)
    else:
        args.out.write_text(json.dumps(records, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        payload["out"] = str(args.out)

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
