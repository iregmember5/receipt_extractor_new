# Today Task — Implemented Features

## 1. Layout Reconstruction
- OCR result (`rec_texts`, `rec_polys`) is sent from Django backend to frontend
- Frontend `reconstructLayoutText()` (in `lib/layoutReconstruct.ts`) converts raw OCR data into a text representation that preserves the original spatial layout (columns aligned via polygon x-positions)
- Token map is generated, mapping each text token to its row/col position in the reconstructed layout and its original polygon coordinates

## 2. Image Overlay with Polygon Highlighting
- Receipt image is displayed with an SVG overlay showing detected text polygons
- Hovering over a polygon highlights it
- Clicking a polygon (when a label is active) tags that token as Date/Description/Amount

## 3. Text Selection & Tagging
- Text in the reconstructed layout textarea can be selected when a label (Date/Description/Amount) is active
- Selected text is matched back to tokens via the token map (row/col intersection)
- A tagged selection card is created showing: label badge, editable text input, matched polygon coordinates, and an Update button

## 4. Backend-Driven Text Update
- When "Update" is clicked on a tagged selection:
  - Frontend sends `{ ocr_data, updates: [{ tokenIds, newText }] }` to `POST /api/update-ocr/`
  - Next.js proxies to Django `POST /api/update-ocr/`
  - Django `update_ocr_texts()` service patches `rec_texts` (first tokenId gets newText, rest get blanked)
  - Returns updated `ocr_data` to frontend
- Frontend re-runs `reconstructLayoutText()` with the updated OCR data, producing a new layout with the edited text in the correct position
- The tagged selection card shows "✏ edited" badge and the new text is reflected in the reconstructed layout

## 5. Save to File
- "Save to File" button downloads the current reconstructed layout text as `reconstructed_layout.txt`
- "Save JSON" button downloads tagged selections as `tagged_selections.json` (grouped by Date/Description/Amount with polygon coordinates)

## Backend Endpoints
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/process-receipt-json/` | POST | Upload receipt image, run PaddleOCR, return OCR data |
| `/api/update-ocr/` | POST | Update OCR text by token IDs, return patched OCR data |

## Frontend Routes
| Route | Purpose |
|---|---|
| `/` | Main page: upload, process, tag, edit, update layout |
| `/api/process` | Next.js proxy → Django `/api/process-receipt-json/` |
| `/api/update-ocr` | Next.js proxy → Django `/api/update-ocr/` |
