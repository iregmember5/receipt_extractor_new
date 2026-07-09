import json
import re
from pathlib import Path


INPUT_JSON = r"output/recipt 5_res.json"   # change this to your PaddleOCR JSON file path
OUTPUT_TXT = r"output/receipt_text_ordered.txt"
OUTPUT_LAYOUT_TXT = r"output/receipt_text_layout.txt"


def clean_text(text: str) -> str:
    text = text or ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_box_info(poly):
    """
    poly example:
    [[133,47], [394,52], [393,76], [132,71]]
    """
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


def load_paddleocr_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    texts = data.get("rec_texts", [])
    scores = data.get("rec_scores", [])
    polys = data.get("rec_polys") or data.get("dt_polys", [])

    if not texts:
        raise ValueError("No rec_texts found in JSON.")

    if not polys:
        raise ValueError("No rec_polys or dt_polys found in JSON.")

    items = []

    for i, text in enumerate(texts):
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


def group_items_into_rows(items, y_tolerance=12):
    """
    Groups nearby OCR boxes into the same receipt row.
    y_tolerance controls how close two text boxes must be vertically
    to be considered part of the same line.
    """

    # Sort top-to-bottom first
    items = sorted(items, key=lambda x: (x["y_center"], x["x_min"]))

    rows = []

    for item in items:
        placed = False

        for row in rows:
            row_y = row["y_center"]

            if abs(item["y_center"] - row_y) <= y_tolerance:
                row["items"].append(item)

                # update average row center
                row["y_center"] = sum(x["y_center"] for x in row["items"]) / len(row["items"])
                placed = True
                break

        if not placed:
            rows.append({
                "y_center": item["y_center"],
                "items": [item],
            })

    # Sort rows top-to-bottom, and items inside each row left-to-right
    rows = sorted(rows, key=lambda r: r["y_center"])

    for row in rows:
        row["items"] = sorted(row["items"], key=lambda x: x["x_min"])

    return rows


def build_plain_text(rows):
    """
    Simple readable text.
    """
    lines = []

    for row in rows:
        line = " ".join(item["text"] for item in row["items"])
        lines.append(line)

    return "\n".join(lines)


def build_layout_text(rows, image_width=520, output_width=90):
    """
    Preserves approximate receipt columns using x position.
    Useful for receipts because Qty / Rate / Amount are columns.
    """
    lines = []

    scale = output_width / image_width

    for row in rows:
        line_chars = [" "] * output_width

        for item in row["items"]:
            start = int(item["x_min"] * scale)
            start = max(0, min(start, output_width - 1))

            text = item["text"]

            for i, ch in enumerate(text):
                pos = start + i

                if pos >= output_width:
                    break

                line_chars[pos] = ch

        line = "".join(line_chars).rstrip()
        lines.append(line)

    return "\n".join(lines)


def main():
    input_path = Path(INPUT_JSON)

    if not input_path.exists():
        raise FileNotFoundError(f"JSON file not found: {input_path}")

    items = load_paddleocr_json(input_path)

    rows = group_items_into_rows(items, y_tolerance=12)

    plain_text = build_plain_text(rows)
    layout_text = build_layout_text(rows)

    Path(OUTPUT_TXT).parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(plain_text)

    with open(OUTPUT_LAYOUT_TXT, "w", encoding="utf-8") as f:
        f.write(layout_text)

    print("\nORDERED RECEIPT TEXT")
    print("=" * 60)
    print(plain_text)

    print("\nSaved:")
    print(OUTPUT_TXT)
    print(OUTPUT_LAYOUT_TXT)


if __name__ == "__main__":
    main()