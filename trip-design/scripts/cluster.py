#!/usr/bin/env python3
"""Cluster photos by date + GPS distance into a diary-data structure.

Rules:
1. Sort by datetime
2. Group by date → "day"
3. Within a day:
   - Adjacent photos < 500m → same location group
   - > 2km → new location
   - No-GPS photos inherit the previous photo's location
4. Cover photo per location/day = largest filesize (heuristic for richness)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SAME_LOC_M = 500
NEW_LOC_M = 2000


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def place_label(place):
    if not place:
        return "未知地点"
    return (place.get("suburb") or place.get("city")
            or place.get("region") or place.get("country") or "未知地点")


def place_detail(place):
    if not place:
        return None
    parts = [place.get(k) for k in ("suburb", "city", "region", "country")]
    return ", ".join(p for p in parts if p) or place.get("display_name")


def pick_cover(photos):
    sized = [p for p in photos if p.get("filesize")]
    if sized:
        return max(sized, key=lambda p: p["filesize"])["id"]
    return photos[0]["id"]


def cluster_day(photos):
    """Cluster a single day's photos into locations. Returns list of location dicts."""
    locations = []
    current = None
    last_gps = None

    for p in photos:
        gps = p["gps"] if p["gps"]["available"] else None

        if current is None:
            current = _new_location(p)
            if gps:
                last_gps = (gps["lat"], gps["lon"])
            continue

        if gps:
            ref = last_gps or (gps["lat"], gps["lon"])
            d = haversine_m(ref[0], ref[1], gps["lat"], gps["lon"])
            if d > NEW_LOC_M:
                locations.append(_finalize_location(current))
                current = _new_location(p)
                last_gps = (gps["lat"], gps["lon"])
            elif d <= SAME_LOC_M:
                current["photos"].append(p)
                last_gps = (gps["lat"], gps["lon"])
            else:
                # 500m..2km grey zone — stay in same location to avoid over-fragmenting
                current["photos"].append(p)
                last_gps = (gps["lat"], gps["lon"])
        else:
            current["photos"].append(p)

    if current is not None:
        locations.append(_finalize_location(current))
    return locations


def _new_location(first_photo):
    return {
        "place_name": place_label(first_photo.get("place")),
        "place_detail": place_detail(first_photo.get("place")),
        "photos": [first_photo],
    }


def _finalize_location(loc):
    photos = loc["photos"]
    times = [p["datetime"] for p in photos if p.get("datetime")]
    times.sort()
    gps_pts = [(p["gps"]["lat"], p["gps"]["lon"])
               for p in photos if p["gps"]["available"]]
    center = None
    if gps_pts:
        center = {
            "lat": round(sum(g[0] for g in gps_pts) / len(gps_pts), 6),
            "lon": round(sum(g[1] for g in gps_pts) / len(gps_pts), 6),
        }
    return {
        "place_name": loc["place_name"],
        "place_detail": loc["place_detail"],
        "arrival_time": times[0].split("T")[1][:5] if times else None,
        "departure_time": times[-1].split("T")[1][:5] if times else None,
        "center_gps": center,
        "cover_photo_id": pick_cover(photos),
        "photos": [
            {
                "id": p["id"],
                "path": p["path"],
                "datetime": p["datetime"],
                "gps": p["gps"],
                "filesize": p["filesize"],
                "icloud_state": p.get("icloud_state", "local"),
                "caption": None,
            }
            for p in photos
        ],
    }


def build_diary(records):
    usable = [r for r in records
              if r.get("datetime") and r.get("skip_reason") is None]
    usable.sort(key=lambda r: r["datetime"])

    by_day = defaultdict(list)
    for r in usable:
        date = r["datetime"][:10]
        by_day[date].append(r)

    days_sorted = sorted(by_day.keys())
    days = []
    map_track_global = []

    for idx, date in enumerate(days_sorted, start=1):
        photos = by_day[date]
        locations = cluster_day(photos)
        day_track = []
        for loc in locations:
            if loc["center_gps"]:
                day_track.append({
                    "lat": loc["center_gps"]["lat"],
                    "lon": loc["center_gps"]["lon"],
                    "time": loc["arrival_time"],
                    "place": loc["place_name"],
                })
        cover = locations[0]["cover_photo_id"] if locations else None
        days.append({
            "date": date,
            "day_number": idx,
            "title": None,
            "narrative": None,
            "cover_photo_id": cover,
            "locations": locations,
            "map_track": day_track,
        })
        map_track_global.extend(day_track)

    cities = []
    for day in days:
        for loc in day["locations"]:
            label = loc["place_name"]
            if label and label not in cities:
                cities.append(label)

    cover_photo_id = days[0]["cover_photo_id"] if days else None
    date_range = f"{days_sorted[0]} ~ {days_sorted[-1]}" if days_sorted else None

    return {
        "trip_summary": {
            "title": None,
            "date_range": date_range,
            "day_count": len(days),
            "photo_count": sum(len(loc["photos"])
                               for d in days for loc in d["locations"]),
            "cities": cities,
            "cover_photo_id": cover_photo_id,
        },
        "days": days,
        "all_gps_points": map_track_global,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, default=Path("geocoded_photos.json"))
    ap.add_argument("--out", type=Path, default=Path("diary_data.json"))
    args = ap.parse_args()

    if not args.inp.exists():
        sys.exit(f"找不到输入：{args.inp}（先跑 geocode.py）")

    records = json.loads(args.inp.read_text(encoding="utf-8"))
    diary = build_diary(records)
    args.out.write_text(json.dumps(diary, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    overview_lines = [f"📅 行程概览（共 {len(diary['days'])} 天，{diary['trip_summary']['photo_count']} 张照片）："]
    for day in diary["days"]:
        chain = " → ".join(loc["place_name"] for loc in day["locations"])
        overview_lines.append(f"  Day {day['day_number']} · {day['date']}  {chain}")
        for loc in day["locations"]:
            overview_lines.append(f"      └─ {loc['place_name']}  "
                                  f"{loc['arrival_time']}-{loc['departure_time']}  "
                                  f"({len(loc['photos'])} 张)")
    print("\n".join(overview_lines))
    print(f"\n→ {args.out}")


if __name__ == "__main__":
    main()
