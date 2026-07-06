import json
import re
from pathlib import Path

from paddleocr import PaddleOCR


# Reuse one OCR engine per process to avoid reloading models on each request.
_OCR_ENGINE = None


def get_ocr_engine() -> PaddleOCR:
    global _OCR_ENGINE

    if _OCR_ENGINE is None:
        _OCR_ENGINE = PaddleOCR(
            ocr_version="PP-OCRv5",
            use_doc_orientation_classify=True,
            use_doc_unwarping=True,
            use_textline_orientation=True,
            device="cpu",
        )

    return _OCR_ENGINE


def clean_text(text: str) -> str:
    text = text or ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_box_info(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]

    x_min = min(xs)
    x_max = max(xs)
    y_min = min(ys)
    y_max = max(ys)

    return {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "x_center": (x_min + x_max) / 2,
        "y_center": (y_min + y_max) / 2,
        "height": y_max - y_min,
        "width": x_max - x_min,
    }


def group_items_into_rows(items, y_tolerance=12):
    items = sorted(items, key=lambda x: (x["y_center"], x["x_min"]))
    rows = []

    for item in items:
        placed = False

        for row in rows:
            if abs(item["y_center"] - row["y_center"]) <= y_tolerance:
                row["items"].append(item)
                row["y_center"] = sum(x["y_center"] for x in row["items"]) / len(row["items"])
                placed = True
                break

        if not placed:
            rows.append({"y_center": item["y_center"], "items": [item]})

    rows = sorted(rows, key=lambda r: r["y_center"])

    for row in rows:
        row["items"] = sorted(row["items"], key=lambda x: x["x_min"])

    return rows


def build_plain_text(rows):
    lines = []

    for row in rows:
        lines.append(" ".join(item["text"] for item in row["items"]))

    return "\n".join(lines)


def build_layout_text(rows, image_width=520, output_width=90):
    lines = []
    scale = output_width / image_width

    for row in rows:
        line_chars = [" "] * output_width

        for item in row["items"]:
            start = int(item["x_min"] * scale)
            start = max(0, min(start, output_width - 1))

            for i, ch in enumerate(item["text"]):
                pos = start + i
                if pos >= output_width:
                    break
                line_chars[pos] = ch

        lines.append("".join(line_chars).rstrip())

    return "\n".join(lines)


def normalize_ocr_result(result):
    candidates = []

    result_json = getattr(result, "json", None)
    if isinstance(result_json, dict):
        candidates.append(result_json)

    if hasattr(result, "to_dict"):
        candidates.append(result.to_dict())

    if isinstance(result, dict):
        candidates.append(dict(result))

    for candidate in candidates:
        data = candidate.get("res", candidate)
        if isinstance(data, dict) and data.get("rec_texts"):
            return data

    return {}


def extract_items_from_json_data(data):
    texts = data.get("rec_texts", [])
    scores = data.get("rec_scores", [])
    polys = data.get("rec_polys") or data.get("dt_polys", [])

    if not texts:
        raise ValueError("No rec_texts found in OCR JSON output.")

    if not polys:
        raise ValueError("No rec_polys or dt_polys found in OCR JSON output.")

    items = []

    for i, text in enumerate(texts):
        if i >= len(polys):
            continue

        text = clean_text(text)
        if not text:
            continue

        box = get_box_info(polys[i])
        score = scores[i] if i < len(scores) else None

        items.append({
            "text": text,
            "score": score,
            **box,
        })

    return items


def run_receipt_pipeline(image_path: Path, work_dir: Path):
    work_dir.mkdir(parents=True, exist_ok=True)

    ocr = get_ocr_engine()
    results = ocr.predict(str(image_path))

    rec_texts = []
    rec_scores = []
    rec_polys = []
    rec_boxes = []
    source_json = []

    for result in results:
        result_dict = normalize_ocr_result(result)
        source_json.append(result_dict)

        rec_texts.extend(result_dict.get("rec_texts", []))
        rec_scores.extend(result_dict.get("rec_scores", []))

        polys = result_dict.get("rec_polys") or result_dict.get("dt_polys", [])
        rec_polys.extend(polys)
        rec_boxes.extend(result_dict.get("rec_boxes", []))

    json_data = {
        "rec_texts": rec_texts,
        "rec_scores": rec_scores,
        "rec_polys": rec_polys,
        "rec_boxes": rec_boxes,
        "source_results": source_json,
    }

    base_name = image_path.stem
    json_path = work_dir / f"{base_name}_res.json"
    ordered_text_path = work_dir / f"{base_name}_text_ordered.txt"
    layout_text_path = work_dir / f"{base_name}_text_layout.txt"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    items = extract_items_from_json_data(json_data)
    rows = group_items_into_rows(items, y_tolerance=12)

    plain_text = build_plain_text(rows)
    image_width = max((item["x_max"] for item in items), default=520)
    layout_text = build_layout_text(rows, image_width=image_width)

    with open(ordered_text_path, "w", encoding="utf-8") as f:
        f.write(plain_text)

    with open(layout_text_path, "w", encoding="utf-8") as f:
        f.write(layout_text)

    return {
        "json_path": json_path,
        "ordered_text_path": ordered_text_path,
        "layout_text_path": layout_text_path,
    }
