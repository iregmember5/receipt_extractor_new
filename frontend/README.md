# Frontend — Receipt OCR Layout Reconstruction

Two frontends are available: a **Gradio web app** (primary) and a **Tkinter desktop app** (legacy).

---

## Gradio Web App (`gradio_app.py`)

### How it works

1. User uploads a receipt image (PNG/JPEG).
2. Clicks **Process Receipt**.
3. Image is sent via `POST` to `http://127.0.0.1:8000/api/process-receipt-json/` as `multipart/form-data` with field name `receipt_image`.
4. Backend returns JSON with:
   - `ocr_data.rec_texts` — list of detected text strings
   - `ocr_data.rec_polys` — list of 4-corner polygons `[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]`
   - `image_width` / `image_height` — original image dimensions
5. Frontend reconstructs a spatial layout text file and displays it in an editable textbox.
6. User can edit the text, then click **Save to File** to download.

### Layout Reconstruction Pipeline

#### 1. Polygon → Item (`get_box_center`)
Each 4-corner polygon is converted to an item with:
- `x_min`, `y_min`, `x_max`, `y_max` — axis-aligned bounding box
- `x_center`, `y_center` — center point of the box
- `text` — the OCR-detected string

#### 2. Column Snapping (`snap_xmin_to_columns`)
All `x_min` values across every item are clustered. Values within 0.8% of image width are considered the same "column" and snapped to the cluster center. This ensures tabular data (dates, descriptions, prices) aligns vertically. A safety limit of 2% prevents isolated items from being dragged into wrong columns.

#### 3. Row Grouping (`group_into_rows`)
- Computes median text height across all detected items.
- Tolerance = 60% of median height (data-driven, adapts to any resolution).
- Items sorted by `(y_center, x_center)` — top-to-bottom, left-to-right.
- Each item is either added to an existing row (if within tolerance) or starts a new row.
- Rows sorted by `y_center`, items within each row sorted by `x_center`.

#### 4. Character Width Estimation (`reconstruct_layout_text`)
- Average pixel-width per character is computed from actual detected box widths: `(x_max - x_min) / len(text)`.
- Median across all items avoids outliers.
- This replaces any hardcoded scale tied to image width — adapts to any font size/resolution.

#### 5. Line Height Estimation
- Calculates vertical gaps between consecutive rows (median gap).
- Uses this to insert proportional blank lines between rows that are far apart (paragraph breaks, section dividers).

#### 6. Text Placement
- Output is a variable-width character grid.
- Each item is placed at `col = int(round(x_min / px_per_char))`.
- A `cursor` tracks the next free column to prevent overlapping text.
- The grid auto-expands horizontally as needed.

#### 7. Monospace Display
The textbox uses `font-family: monospace` and `white-space: pre` so spaces preserve column alignment visually. Horizontal scrolling is enabled for wide lines.

### UI Components
| Component | Description |
|-----------|-------------|
| Image input | Upload PNG/JPEG |
| Process button | Triggers OCR |
| Layout textbox | Editable reconstructed text |
| Save button | Saves textbox content to `/tmp/reconstructed_layout.txt` |
| Download link | Appears after save |

### Running
```bash
python gradio_app.py
# Opens at http://127.0.0.1:7860
```

---

## Tkinter Desktop App (`main.py`)

Legacy desktop version. Select an image, process it, and view OCR results with bounding boxes drawn on a canvas.

### Running
```bash
python main.py
```

---

## Dependencies
- `gradio` — web UI framework
- `Pillow` — image handling
- `requests` — HTTP client
