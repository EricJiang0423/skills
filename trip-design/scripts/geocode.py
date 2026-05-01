#!/usr/bin/env python3
"""Reverse geocode raw_photos.json via Nominatim. Adds `place` field per photo.

Cache key = GPS truncated to 3 decimals (~111m), satisfying Nominatim usage policy
of ≤ 1 req/s plus minimizing duplicate calls.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

USER_AGENT = "trip-design/0.1 (https://github.com/EricJiang0423/trip-design)"


def cache_key(lat, lon):
    return f"{round(lat, 3):.3f},{round(lon, 3):.3f}"


def load_cache(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(path: Path, cache: dict):
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def parse_address(raw):
    """Nominatim address dict → flat 4-level place."""
    if not raw:
        return None
    addr = raw.get("address", {})
    suburb = (addr.get("suburb") or addr.get("neighbourhood")
              or addr.get("quarter") or addr.get("hamlet")
              or addr.get("village") or addr.get("road"))
    city = (addr.get("city") or addr.get("town") or addr.get("municipality")
            or addr.get("county"))
    region = addr.get("state") or addr.get("region") or addr.get("province")
    country = addr.get("country")
    return {
        "suburb": suburb,
        "city": city,
        "region": region,
        "country": country,
        "display_name": raw.get("display_name"),
    }


def geocode_all(records, cache_path: Path, language="zh-CN"):
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
    except ImportError:
        sys.exit("缺 geopy。先跑：python3 scripts/check_deps.py")

    geocoder = Nominatim(user_agent=USER_AGENT, timeout=10)
    cache = load_cache(cache_path)
    last_request = 0.0
    new_lookups = 0

    total = sum(1 for r in records if r["gps"]["available"])
    done = 0

    for r in records:
        if not r["gps"]["available"]:
            r["place"] = None
            continue

        key = cache_key(r["gps"]["lat"], r["gps"]["lon"])
        if key in cache:
            r["place"] = cache[key]
            done += 1
            continue

        # Respect 1 req/s limit
        elapsed = time.time() - last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        attempts = 0
        result_raw = None
        while attempts < 3:
            try:
                location = geocoder.reverse(
                    (r["gps"]["lat"], r["gps"]["lon"]),
                    language=language,
                    addressdetails=True,
                    zoom=16,
                )
                result_raw = location.raw if location else None
                break
            except (GeocoderTimedOut, GeocoderUnavailable) as e:
                attempts += 1
                wait = 2 ** attempts
                print(f"  ⏳ Nominatim {type(e).__name__}，{wait}s 后重试 (attempt {attempts}/3)",
                      file=sys.stderr)
                time.sleep(wait)
        last_request = time.time()

        place = parse_address(result_raw)
        cache[key] = place
        r["place"] = place
        new_lookups += 1
        done += 1

        if new_lookups % 5 == 0:
            save_cache(cache_path, cache)

        print(f"  📍 {done}/{total}  {key} → "
              f"{place['display_name'][:60] if place and place.get('display_name') else 'unknown'}",
              file=sys.stderr)

    save_cache(cache_path, cache)
    return records, new_lookups


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, default=Path("raw_photos.json"))
    ap.add_argument("--out", type=Path, default=Path("geocoded_photos.json"))
    ap.add_argument("--cache", type=Path, default=Path("geocode_cache.json"))
    ap.add_argument("--language", default="zh-CN", help="Nominatim 返回地名语言")
    args = ap.parse_args()

    if not args.inp.exists():
        sys.exit(f"找不到输入：{args.inp}（先跑 extract_photos.py）")

    records = json.loads(args.inp.read_text(encoding="utf-8"))
    records, new_lookups = geocode_all(records, args.cache, language=args.language)
    args.out.write_text(json.dumps(records, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    print(json.dumps({
        "out": str(args.out),
        "cache": str(args.cache),
        "total": len(records),
        "with_gps": sum(1 for r in records if r["gps"]["available"]),
        "with_place": sum(1 for r in records if r.get("place")),
        "new_lookups": new_lookups,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
