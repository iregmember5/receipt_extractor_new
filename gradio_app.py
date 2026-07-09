import os
import sys
import requests
from PIL import Image
import gradio as gr

API_URL = "http://127.0.0.1:8000/api/process-receipt-json/"


def log(msg):
    sys.stderr.write(f"[DEBUG] {msg}\n")
    sys.stderr.flush()


def get_box_center(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(xs), min(ys), max(xs), max(ys)


def median(values):
    """Simple median helper (avoids depending on statistics for one-liners)."""
    if not values:
        return 0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return s[mid]


def group_into_rows(items):
    """Group text items into horizontal rows based on vertical center proximity."""
    heights = [item["y_max"] - item["y_min"] for item in items]
    median_h = median(heights) or 1
    y_tol = median_h * 0.6

    items = sorted(items, key=lambda x: (x["y_center"], x["x_center"]))
    rows = []
    for item in items:
        placed = False
        for row in rows:
            if abs(item["y_center"] - row["y_center"]) <= y_tol:
                row["items"].append(item)
                row["y_center"] = sum(x["y_center"] for x in row["items"]) / len(row["items"])
                placed = True
                break
        if not placed:
            rows.append({"y_center": item["y_center"], "items": [item]})

    rows = sorted(rows, key=lambda r: r["y_center"])
    for row in rows:
        row["items"] = sorted(row["items"], key=lambda x: x["x_center"])
    return rows


def snap_xmin_to_columns(items, img_width, tol_ratio=0.008, max_snap_ratio=0.02):
    """
    Snap x_min values that are close to each other into shared 'columns' so that
    tabular data (item name / qty / price columns) lines up vertically.

    Unlike a naive nearest-cluster snap, this only pulls a value toward a cluster
    if it is genuinely close to it (within max_snap_ratio of the image width).
    Text that is far from every cluster — e.g. isolated header/footer phrases
    that don't belong to any real tabular column — is left untouched, so it
    doesn't get dragged sideways into an unrelated column.
    """
    if not items:
        return

    xs = sorted(item["x_min"] for item in items)
    clusters = []
    current = [xs[0]]
    for x in xs[1:]:
        if x - current[-1] <= img_width * tol_ratio:
            current.append(x)
        else:
            clusters.append(sum(current) / len(current))
            current = [x]
    clusters.append(sum(current) / len(current))

    max_snap_dist = img_width * max_snap_ratio
    for item in items:
        nearest = min(clusters, key=lambda c: abs(c - item["x_min"]))
        if abs(nearest - item["x_min"]) <= max_snap_dist:
            item["x_min"] = nearest


def reconstruct_layout_text(rec_texts, rec_polys, img_width, img_height):
    items = []
    for i, text in enumerate(rec_texts):
        if not text:
            continue
        if i >= len(rec_polys) or len(rec_polys[i]) < 4:
            continue
        poly = rec_polys[i]
        xc, yc, xmin, ymin, xmax, ymax = get_box_center(poly)
        items.append({
            "text": text,
            "x_center": xc,
            "y_center": yc,
            "x_min": xmin,
            "x_max": xmax,
            "y_min": ymin,
            "y_max": ymax,
        })

    if not items:
        return ""

    snap_xmin_to_columns(items, img_width)
    rows = group_into_rows(items)

    # Estimate the average pixel-width of a single character directly from the
    # detected boxes, instead of relying on an arbitrary constant tied to
    # img_width. This makes the scaling adapt automatically to receipts shot
    # at any resolution, zoom level, or font size.
    char_widths = []
    for item in items:
        n = len(item["text"])
        if n > 0:
            w = (item["x_max"] - item["x_min"]) / n
            if w > 0:
                char_widths.append(w)
    px_per_char = median(char_widths) or max(img_width / 100, 1)

    # Typical vertical spacing between consecutive rows, used to decide how
    # many blank lines to insert between rows that are far apart (paragraph
    # breaks, section dividers, decorative gaps in headers/footers, etc).
    # Using the image height / row count (as before) assumes rows are spread
    # evenly across the whole receipt, which is false — item lists are dense
    # while headers/footers are sparse. Deriving it from actual row-to-row
    # gaps fixes that.
    row_gaps = []
    prev_yc = None
    for row in rows:
        if prev_yc is not None:
            row_gaps.append(row["y_center"] - prev_yc)
        prev_yc = row["y_center"]
    line_height = median(row_gaps) if row_gaps else median(
        [item["y_max"] - item["y_min"] for item in items]
    )
    if not line_height or line_height <= 0:
        line_height = 1

    # Determine output width from the actual rightmost extent of text needed
    # (rather than a heuristic formula that can under/over-shoot).
    output_width = 40
    for item in items:
        col = max(0, int(round(item["x_min"] / px_per_char)))
        output_width = max(output_width, col + len(item["text"]) + 2)

    out_lines = []
    prev_y = None
    for row in rows:
        if prev_y is not None:
            gap_lines = int(round((row["y_center"] - prev_y) / line_height)) - 1
            for _ in range(max(0, gap_lines)):
                out_lines.append("")
        prev_y = row["y_center"]

        line = [" "] * output_width
        cursor = 0  # next free column, prevents two items overlapping
        for item in row["items"]:
            col = max(0, int(round(item["x_min"] / px_per_char)))
            start = max(col, cursor)

            needed_len = start + len(item["text"]) + 2
            if needed_len > len(line):
                line.extend([" "] * (needed_len - len(line)))

            for j, ch in enumerate(item["text"]):
                pos = start + j
                line[pos] = ch

            cursor = start + len(item["text"]) + 1  # keep >=1 space gap

        out_lines.append("".join(line).rstrip())
        output_width = max(output_width, len(line))

    log(f"Layout output — {len(out_lines)} lines, width={output_width} chars")
    return "\n".join(out_lines)


def process_receipt(image):
    if image is None:
        log("No image provided.")
        return None, "", "No image provided."

    temp_path = "/tmp/uploaded_receipt.png"
    image.save(temp_path)
    log(f"Image saved, size={image.size}")

    try:
        log(f"Sending POST to {API_URL} ...")
        with open(temp_path, "rb") as f:
            resp = requests.post(API_URL, files={"receipt_image": f}, timeout=120)

        log(f"Response status: {resp.status_code}")
        if resp.status_code != 200:
            err = resp.json().get("error", "Unknown error")
            log(f"Server error: {err}")
            return None, "", f"Server error ({resp.status_code}): {err}"

        data = resp.json()
        log(f"Response keys: {list(data.keys())}")

        ocr_data = data.get("ocr_data")
        img_width = data.get("image_width")
        img_height = data.get("image_height")
        log(f"Image dimensions from server: {img_width}x{img_height}")

        if not ocr_data:
            log("No ocr_data in response")
            return None, "", "No ocr_data in response."

        rec_texts = ocr_data.get("rec_texts", [])
        rec_polys = ocr_data.get("rec_polys", [])
        log(f"Found {len(rec_texts)} text items, {len(rec_polys)} polygons")

        # --- Layout text ---
        layout_text = reconstruct_layout_text(rec_texts, rec_polys, img_width, img_height)
        log(f"Layout text — {len(layout_text.splitlines())} lines")

        os.remove(temp_path)
        return layout_text, "", gr.File(visible=False)

    except requests.exceptions.ConnectionError:
        log(f"ConnectionError: could not reach {API_URL}")
        return "", f"Could not connect to {API_URL}. Is the Django server running?", gr.File(visible=False)
    except Exception as exc:
        log(f"Exception: {exc}")
        return "", f"Error: {exc}", gr.File(visible=False)


with gr.Blocks(title="Receipt OCR") as demo:
    gr.Markdown("# Receipt OCR — Layout Reconstruction")
    gr.Markdown("Upload a receipt image (PNG/JPEG) and click **Process**.")

    with gr.Column():
        image_input = gr.Image(type="pil", label="Receipt Image", height=500)
        process_btn = gr.Button("Process Receipt", variant="primary")

    layout_output = gr.Textbox(label="Reconstructed Layout Text (editable)", lines=20, max_lines=40, elem_id="layout-text")

    with gr.Row():
        save_btn = gr.Button("Save to File", variant="secondary")
        saved_file = gr.File(label="Download Saved File", visible=False)

    error_output = gr.Textbox(label="", visible=False)

    process_btn.click(
        fn=process_receipt,
        inputs=image_input,
        outputs=[layout_output, error_output, saved_file],
    )

    def save_text(text):
        if not text or not text.strip():
            return gr.File(visible=False), "Nothing to save."
        path = "/tmp/reconstructed_layout.txt"
        with open(path, "w") as f:
            f.write(text)
        return gr.File(value=path, visible=True), ""

    save_btn.click(
        fn=save_text,
        inputs=layout_output,
        outputs=[saved_file, error_output],
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, css="footer {visibility: hidden} #layout-text textarea {font-family: monospace !important; white-space: pre !important; overflow-x: auto !important;}")