#!/usr/bin/env python3
"""Extract PPTX slide text and native media assets for academic LaTeX rebuilds."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
}


def natural_key(value: str) -> tuple[int, str]:
    match = re.search(r"(\d+)", value)
    if not match:
        return (10**9, value)
    return (int(match.group(1)), value)


def slide_number(path: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", path)
    if not match:
        return 0
    return int(match.group(1))


def rels_path_for(xml_name: str) -> str:
    part = Path(xml_name)
    return f"{part.parent}/_rels/{part.name}.rels"


def normalize_target(base: str, target: str) -> str:
    base_path = Path(base).parent
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath((base_path / target).as_posix())


def text_from_slide(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    runs: list[str] = []
    for node in root.findall(".//a:t", NS):
        if node.text:
            text = re.sub(r"\s+", " ", node.text).strip()
            if text:
                runs.append(text)
    return runs


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _element_order(root: ET.Element, target: ET.Element) -> int:
    sp_tree = root.find(".//p:cSld/p:spTree", NS)
    if sp_tree is None:
        return 0
    order = 0
    for child in list(sp_tree):
        name = _local_name(child)
        if name in {"nvGrpSpPr", "grpSpPr"}:
            continue
        order += 1
        if child is target:
            return order
    return order


def _shape_identity(shape: ET.Element) -> tuple[str, str]:
    c_nv_pr = shape.find(".//p:cNvPr", NS)
    if c_nv_pr is None:
        return "", ""
    return c_nv_pr.attrib.get("id", ""), c_nv_pr.attrib.get("name", "")


def _placeholder(shape: ET.Element) -> str:
    ph = shape.find(".//p:nvSpPr/p:nvPr/p:ph", NS)
    if ph is None:
        return ""
    return ph.attrib.get("type") or "body"


def _bounds(shape: ET.Element) -> dict[str, int]:
    xfrm = shape.find(".//a:xfrm", NS)
    if xfrm is None:
        xfrm = shape.find(".//p:xfrm", NS)
    if xfrm is None:
        return {}
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None or ext is None:
        return {}
    return {
        "x": int(off.attrib.get("x", "0")),
        "y": int(off.attrib.get("y", "0")),
        "cx": int(ext.attrib.get("cx", "0")),
        "cy": int(ext.attrib.get("cy", "0")),
    }


def _paragraph_text(paragraph: ET.Element) -> str:
    pieces: list[str] = []
    for node in paragraph.findall(".//a:t", NS):
        if node.text:
            pieces.append(node.text)
    return re.sub(r"\s+", " ", "".join(pieces)).strip()


def _paragraph_level(paragraph: ET.Element) -> int:
    p_pr = paragraph.find("a:pPr", NS)
    if p_pr is None:
        return 0
    try:
        return int(p_pr.attrib.get("lvl", "0"))
    except ValueError:
        return 0


def structured_text_blocks_from_slide(xml_bytes: bytes) -> list[dict]:
    """Extract paragraph-level text blocks with source shape metadata.

    The older extractor returned every <a:t> run, which splits natural phrases
    across bullets and produces unusable LaTeX. This preserves the PowerPoint
    paragraph as the atomic text unit, along with enough layout metadata for the
    Code Agent to reconstruct prose faithfully.
    """
    root = ET.fromstring(xml_bytes)
    blocks: list[dict] = []
    for shape in root.findall(".//p:sp", NS):
        shape_id, shape_name = _shape_identity(shape)
        placeholder = _placeholder(shape)
        bounds = _bounds(shape)
        order = _element_order(root, shape)
        paragraphs = shape.findall(".//a:p", NS)
        for para_index, paragraph in enumerate(paragraphs, start=1):
            text = _paragraph_text(paragraph)
            if not text:
                continue
            blocks.append(
                {
                    "order": order,
                    "shape_id": shape_id,
                    "shape_name": shape_name,
                    "shape_type": "text",
                    "placeholder": placeholder,
                    "paragraph_index": para_index,
                    "paragraph_level": _paragraph_level(paragraph),
                    "bounds": bounds,
                    "text": text,
                }
            )
    return sorted(blocks, key=lambda b: (b["order"], b["paragraph_index"]))


def tables_from_slide(xml_bytes: bytes) -> list[dict]:
    """Extract native PPTX table cells from graphic frames."""
    root = ET.fromstring(xml_bytes)
    tables: list[dict] = []
    for frame in root.findall(".//p:graphicFrame", NS):
        table = frame.find(".//a:tbl", NS)
        if table is None:
            continue
        rows: list[list[str]] = []
        for tr in table.findall("a:tr", NS):
            row: list[str] = []
            for tc in tr.findall("a:tc", NS):
                cell_text = " ".join(
                    _paragraph_text(p) for p in tc.findall(".//a:p", NS)
                )
                row.append(re.sub(r"\s+", " ", cell_text).strip())
            if any(row):
                rows.append(row)
        if not rows:
            continue
        frame_id, frame_name = _shape_identity(frame)
        tables.append(
            {
                "order": _element_order(root, frame),
                "shape_id": frame_id,
                "shape_name": frame_name,
                "bounds": _bounds(frame),
                "rows": rows,
            }
        )
    return sorted(tables, key=lambda t: t["order"])


def chart_frame_metadata(xml_bytes: bytes) -> dict[str, dict]:
    """Map chart relationship ids to their visual order and bounds."""
    root = ET.fromstring(xml_bytes)
    chart_frames: dict[str, dict] = {}
    for frame in root.findall(".//p:graphicFrame", NS):
        chart = frame.find(".//c:chart", NS)
        if chart is None:
            continue
        rid = ""
        for key, value in chart.attrib.items():
            if key.endswith("}id"):
                rid = value
                break
        if not rid:
            continue
        frame_id, frame_name = _shape_identity(frame)
        chart_frames[rid] = {
            "order": _element_order(root, frame),
            "shape_id": frame_id,
            "shape_name": frame_name,
            "bounds": _bounds(frame),
        }
    return chart_frames


def title_text_from_slide(xml_bytes: bytes) -> str | None:
    """Extract text from the title placeholder shape (<p:ph type='title'|'ctrTitle'>)."""
    root = ET.fromstring(xml_bytes)
    for sp in root.findall(".//p:sp", NS):
        ph = sp.find(".//p:nvSpPr/p:nvPr/p:ph", NS)
        if ph is None:
            continue
        ph_type = ph.attrib.get("type", "")
        if ph_type not in ("title", "ctrTitle"):
            continue
        texts = []
        for t in sp.findall(".//a:t", NS):
            if t.text:
                texts.append(re.sub(r"\s+", " ", t.text).strip())
        title = " ".join(t for t in texts if t)
        if title:
            return title
    return None


def rels_from_xml(xml_bytes: bytes, owner_name: str) -> dict[str, dict[str, str]]:
    root = ET.fromstring(xml_bytes)
    rels: dict[str, dict[str, str]] = {}
    for rel in root.findall("rel:Relationship", NS):
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        rel_type = rel.attrib.get("Type", "")
        if not rid or not target:
            continue
        rels[rid] = {
            "target": normalize_target(owner_name, target),
            "type": rel_type,
        }
    return rels


def embedded_relationship_ids(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    ids: list[str] = []
    for element in root.iter():
        for key, value in element.attrib.items():
            if key.endswith("}embed") or key.endswith("}link"):
                ids.append(value)
    return ids


def background_rel_ids(xml_bytes: bytes) -> set[str]:
    """Return rIds referenced from <p:bg> (slide background fills)."""
    root = ET.fromstring(xml_bytes)
    ids: set[str] = set()
    for bg in root.findall(".//p:bg", NS):
        for element in bg.iter():
            for key, value in element.attrib.items():
                if key.endswith("}embed") or key.endswith("}link"):
                    ids.add(value)
    return ids


def figure_initial_status(file_path: Path) -> tuple[str, str]:
    """Return (status, drop_reason) applying hard filters in order.

    Stages (in order):
      1. File size < 5 KB        → drop  (icons, bullets, tiny decoratives)
      2. Dimensions < 80×80 px   → drop  (tiny decoratives)
      3. Aspect ratio > 8:1      → drop  (header/footer banner strips)
      4. ≥ 95 % near-white px    → drop  (gradient backgrounds, near-blank slides)
    Everything else              → review  (sent to AI classifier)
    """
    size = file_path.stat().st_size
    if size < 5_000:
        return "drop", "too_small"
    try:
        from PIL import Image  # noqa: PLC0415
        with Image.open(file_path) as img:
            w, h = img.size
            if w < 80 or h < 80:
                return "drop", "tiny_dimensions"
            if max(w, h) / max(min(w, h), 1) > 8:
                return "drop", "banner_strip"
            gray = img.convert("L")
            pixels = list(gray.getdata())
            n = len(pixels)
            if n > 0 and sum(1 for p in pixels if p > 230) / n >= 0.95:
                return "drop", "near_blank"
    except Exception:
        pass
    return "review", ""


def try_convert_to_png(file_path: Path) -> Path:
    """Convert an EMF/WMF file to PNG at extraction time.

    On success the original vector file is removed and the PNG path is
    returned. Otherwise the original path is returned unchanged.
    """
    if file_path.suffix.lower() not in {".emf", ".wmf"}:
        return file_path
    png_path = file_path.with_suffix(".png")
    converters = [
        ["convert", str(file_path), str(png_path)],
        [
            "libreoffice", "--headless", "--convert-to", "png",
            "--outdir", str(file_path.parent), str(file_path),
        ],
    ]
    for cmd in converters:
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=30)
            if r.returncode == 0 and png_path.exists():
                file_path.unlink(missing_ok=True)
                return png_path
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return file_path


def relationship_ids_by_type(rels: dict[str, dict[str, str]], suffix: str) -> list[str]:
    return [rid for rid, rel in rels.items() if rel.get("type", "").endswith(suffix)]


def parse_chart_xml(xml_bytes: bytes) -> dict | None:
    """Parse a chart*.xml file and return structured data for common chart types.

    Supports bar, line, scatter and pie charts. Returns:
      {
        "chart_type": "bar" | "line" | "scatter" | "pie" | "other",
        "title": str | None,
        "series": [{"name": str, "categories": [...], "values": [...]}, ...]
      }
    or None on parse failure.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    plot_area = root.find(".//c:plotArea", NS)
    if plot_area is None:
        return None

    type_map = {
        "barChart": "bar",
        "bar3DChart": "bar",
        "lineChart": "line",
        "line3DChart": "line",
        "scatterChart": "scatter",
        "pieChart": "pie",
        "pie3DChart": "pie",
        "doughnutChart": "pie",
        "areaChart": "line",
    }
    chart_type = "other"
    chart_node = None
    for child in plot_area:
        tag = child.tag.split("}", 1)[-1]
        if tag in type_map:
            chart_type = type_map[tag]
            chart_node = child
            break
    if chart_node is None:
        return None

    title_node = root.find(".//c:title//a:t", NS)
    title = title_node.text.strip() if title_node is not None and title_node.text else None

    def _cached_values(parent: ET.Element, ref_tags: tuple[str, ...]) -> list[str]:
        for ref_tag in ref_tags:
            ref = parent.find(f"c:{ref_tag}", NS)
            if ref is None:
                continue
            cache = ref.find(f"c:{ref_tag.replace('Ref', 'Cache')}", NS)
            if cache is None:
                continue
            pts = cache.findall("c:pt", NS)
            out = []
            for pt in pts:
                v = pt.find("c:v", NS)
                out.append(v.text.strip() if v is not None and v.text else "")
            return out
        return []

    series = []
    for ser in chart_node.findall("c:ser", NS):
        name_node = ser.find(".//c:tx//c:v", NS)
        if name_node is None:
            name_node = ser.find(".//c:tx//a:t", NS)
        name = (name_node.text or "").strip() if name_node is not None else ""

        cat_parent = ser.find("c:cat", NS)
        if cat_parent is None:
            cat_parent = ser.find("c:xVal", NS)
        val_parent = ser.find("c:val", NS)
        if val_parent is None:
            val_parent = ser.find("c:yVal", NS)
        categories = _cached_values(cat_parent, ("strRef", "numRef")) if cat_parent is not None else []
        values = _cached_values(val_parent, ("numRef", "strRef")) if val_parent is not None else []

        if not values:
            continue
        series.append({"name": name, "categories": categories, "values": values})

    if not series:
        return None

    return {"chart_type": chart_type, "title": title, "series": series}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("pptx", help="Input .pptx file.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument(
        "--figure-prefix",
        default="figure",
        help="Academic figure filename prefix.",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="First figure number to use when merging multiple sources.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Suppress per-slide progress output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pptx_path = Path(args.pptx).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    figures_dir = output_dir / "figures"
    manifest_dir = output_dir / "manifest"
    figures_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    if pptx_path.suffix.lower() != ".pptx":
        raise SystemExit(f"Input is not a .pptx file: {pptx_path}")
    if not pptx_path.exists():
        raise SystemExit(f"Input file does not exist: {pptx_path}")

    records = []
    extraction = {
        "source": str(pptx_path),
        "type": "pptx",
        "slides": [],
        "figures": [],
    }
    figure_index = args.start
    # Dedup: source target path -> figure record (within this deck)
    target_to_figure: dict[str, dict] = {}

    with zipfile.ZipFile(pptx_path) as archive:
        names = set(archive.namelist())
        slide_names = sorted(
            [name for name in names if re.match(r"ppt/slides/slide\d+\.xml$", name)],
            key=natural_key,
        )
        total_slides = len(slide_names)

        for i, slide_name in enumerate(slide_names, start=1):
            if not args.no_progress:
                print(
                    f"  [{i}/{total_slides}] {slide_name}",
                    end="\r",
                    file=sys.stderr,
                    flush=True,
                )
            s_num = slide_number(slide_name)
            xml_bytes = archive.read(slide_name)
            rels_name = rels_path_for(slide_name)
            rels = rels_from_xml(archive.read(rels_name), slide_name) if rels_name in names else {}
            bg_ids = background_rel_ids(xml_bytes)
            all_rel_ids = embedded_relationship_ids(xml_bytes)
            content_rel_ids = [rid for rid in all_rel_ids if rid not in bg_ids]
            chart_rel_ids = relationship_ids_by_type(rels, "/chart")
            chart_frames = chart_frame_metadata(xml_bytes)

            # Speaker notes (via slide.rels → notesSlide target → text)
            notes: list[str] = []
            notes_target = None
            for rel in rels.values():
                if rel.get("type", "").endswith("/notesSlide"):
                    notes_target = rel.get("target")
                    break
            if notes_target and notes_target in names:
                try:
                    notes = text_from_slide(archive.read(notes_target))
                    notes = [n for n in notes if not re.fullmatch(r"\d+", n)]
                except Exception:
                    notes = []

            slide_figures = []
            for rid in content_rel_ids:
                rel = rels.get(rid)
                if not rel:
                    continue
                target = rel["target"]
                if not target.startswith("ppt/media/") or target not in names:
                    continue

                # Dedup: same source target within this deck → reuse existing figure
                if target in target_to_figure:
                    slide_figures.append(target_to_figure[target])
                    continue

                suffix = Path(target).suffix.lower() or ".bin"
                target_name = f"{args.figure_prefix}-{figure_index:03d}{suffix}"
                target_path = figures_dir / target_name
                with archive.open(target) as source, target_path.open("wb") as dest:
                    shutil.copyfileobj(source, dest)

                target_path = try_convert_to_png(target_path)
                target_name = target_path.name

                status, drop_reason = figure_initial_status(target_path)
                figure_record = {
                    "figure_number": figure_index,
                    "path": f"figures/{target_name}",
                    "source_file": str(pptx_path),
                    "source_slide": s_num,
                    "source_rel_id": rid,
                    "source_target": target,
                    "status": status,
                    "drop_reason": drop_reason,
                    "caption": "",
                    "label": "",
                }
                extraction["figures"].append(figure_record)
                target_to_figure[target] = figure_record
                slide_figures.append(figure_record)
                figure_index += 1

            slide_charts = []
            for rid in chart_rel_ids:
                rel = rels.get(rid)
                if not rel:
                    continue
                chart_target = rel["target"]
                chart_data = None
                if chart_target in names:
                    try:
                        chart_data = parse_chart_xml(archive.read(chart_target))
                    except Exception:
                        chart_data = None
                slide_charts.append(
                    {
                        "source_file": str(pptx_path),
                        "source_slide": s_num,
                        "source_rel_id": rid,
                        "source_target": chart_target,
                        "status": "data_extracted" if chart_data else "redraw_or_crop",
                        "chart_data": chart_data,
                        "order": chart_frames.get(rid, {}).get("order", 0),
                        "shape_id": chart_frames.get(rid, {}).get("shape_id", ""),
                        "shape_name": chart_frames.get(rid, {}).get("shape_name", ""),
                        "bounds": chart_frames.get(rid, {}).get("bounds", {}),
                        "caption": "",
                        "label": "",
                    }
                )

            extraction["slides"].append(
                {
                    "source_file": str(pptx_path),
                    "slide": s_num,
                    "slide_title": title_text_from_slide(xml_bytes),
                    "text_blocks": structured_text_blocks_from_slide(xml_bytes),
                    "plain_text_blocks": text_from_slide(xml_bytes),
                    "tables": tables_from_slide(xml_bytes),
                    "speaker_notes": notes,
                    "figures": slide_figures,
                    "charts": slide_charts,
                    "relationships": rels,
                }
            )

    if not args.no_progress:
        print(" " * 80, end="\r", file=sys.stderr)  # clear progress line

    records.append(extraction)
    manifest_path = manifest_dir / f"{pptx_path.stem}-extraction.json"
    manifest_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    dup_saved = sum(
        max(0, sum(1 for s in extraction["slides"] for f in s["figures"] if f["source_target"] == t) - 1)
        for t in target_to_figure
    )
    print(
        f"Extracted {len(extraction['slides'])} slides, "
        f"{len(extraction['figures'])} unique figures "
        f"({dup_saved} duplicate reference(s) deduped)."
    )
    print(f"Next figure number: {figure_index}")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
