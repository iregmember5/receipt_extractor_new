"use client";

import { useRef, useState } from "react";

const LABELS = ["Date", "Description", "Amount"] as const;
type Label = typeof LABELS[number];

const LABEL_COLORS: Record<Label, string> = {
  Date: "#7c3aed",
  Description: "#0070f3",
  Amount: "#059669",
};

interface CropPreview {
  label: Label;
  dataUrl: string;
  filename: string;
  srcRect: { x: number; y: number; w: number; h: number };
  poly: { tl: [number,number]; tr: [number,number]; br: [number,number]; bl: [number,number] };
  displayRect: { left: number; top: number; width: number; height: number };
  compareResult?: { crop_text: string; original_text: string; match: boolean; similarity: number; crop_confidence: number | null } | null;
  comparing?: boolean;
}

interface DrawState {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  active: boolean;
}

export default function Home() {
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [layoutText, setLayoutText] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [cropPreviews, setCropPreviews] = useState<CropPreview[]>([]);
  const [activeLabel, setActiveLabel] = useState<Label | null>(null);
  const [draw, setDraw] = useState<DrawState | null>(null);
  const [originalOcr, setOriginalOcr] = useState<object | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setPreview(f ? URL.createObjectURL(f) : null);
    setLayoutText("");
    setError("");
    setCropPreviews([]);
    setActiveLabel(null);
    setDraw(null);
    setOriginalOcr(null);
  }

  async function handleProcess() {
    if (!file) { setError("No image selected."); return; }
    setLoading(true);
    setError("");
    setLayoutText("");
    const form = new FormData();
    form.append("receipt_image", file);
    try {
      const res = await fetch("/api/process", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) { setError(data.error ?? "Unknown error"); return; }
      setLayoutText(data.layoutText ?? "");
      setOriginalOcr(data.originalOcr ?? null);
    } catch (e) {
      setError(`Request failed: ${e}`);
    } finally {
      setLoading(false);
    }
  }

  function getRelativePos(e: React.MouseEvent) {
    const rect = containerRef.current!.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(e.clientX - rect.left, rect.width)),
      y: Math.max(0, Math.min(e.clientY - rect.top, rect.height)),
    };
  }

  function handleMouseDown(e: React.MouseEvent) {
    if (!activeLabel || e.button !== 0) return;
    e.preventDefault();
    const { x, y } = getRelativePos(e);
    setDraw({ startX: x, startY: y, currentX: x, currentY: y, active: true });
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!draw?.active) return;
    const { x, y } = getRelativePos(e);
    setDraw((d) => d ? { ...d, currentX: x, currentY: y } : d);
  }

  async function handleMouseUp(e: React.MouseEvent) {
    if (e.button !== 0) return;
    if (!draw?.active || !activeLabel || !imgRef.current) { setDraw(null); return; }
    const { x, y } = getRelativePos(e);

    const rectX = Math.min(draw.startX, x);
    const rectY = Math.min(draw.startY, y);
    const rectW = Math.abs(x - draw.startX);
    const rectH = Math.abs(y - draw.startY);

    if (rectW < 5 || rectH < 5) { setDraw(null); return; }

    const img = imgRef.current;
    const imgRect = img.getBoundingClientRect();
    const containerRect = containerRef.current!.getBoundingClientRect();
    const imgOffsetX = imgRect.left - containerRect.left;
    const imgOffsetY = imgRect.top - containerRect.top;

    const naturalAspect = img.naturalWidth / img.naturalHeight;
    const containerAspect = imgRect.width / imgRect.height;
    let renderedW: number, renderedH: number;
    if (naturalAspect > containerAspect) {
      renderedW = imgRect.width;
      renderedH = imgRect.width / naturalAspect;
    } else {
      renderedH = imgRect.height;
      renderedW = imgRect.height * naturalAspect;
    }
    const letterboxX = (imgRect.width - renderedW) / 2;
    const letterboxY = (imgRect.height - renderedH) / 2;
    const scaleX = img.naturalWidth / renderedW;
    const scaleY = img.naturalHeight / renderedH;

    const srcX = Math.round((rectX - imgOffsetX - letterboxX) * scaleX);
    const srcY = Math.round((rectY - imgOffsetY - letterboxY) * scaleY);
    const srcW = Math.round(rectW * scaleX);
    const srcH = Math.round(rectH * scaleY);

    const canvas = document.createElement("canvas");
    canvas.width = srcW;
    canvas.height = srcH;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(img, srcX, srcY, srcW, srcH, 0, 0, srcW, srcH);

    const dataUrl = canvas.toDataURL("image/png");

    const poly = {
      tl: [srcX,        srcY       ] as [number,number],
      tr: [srcX + srcW, srcY       ] as [number,number],
      br: [srcX + srcW, srcY + srcH] as [number,number],
      bl: [srcX,        srcY + srcH] as [number,number],
    };

    const filename = `${activeLabel.toLowerCase()}_${Date.now()}.png`;

    const blob = await (await fetch(dataUrl)).blob();
    const form = new FormData();
    form.append("crop", blob, filename);
    form.append("filename", filename);
    form.append("meta", JSON.stringify({ label: activeLabel, poly, srcRect: { x: srcX, y: srcY, w: srcW, h: srcH } }));
    await fetch("/api/crop/save", { method: "POST", body: form });

    setCropPreviews((prev) => [...prev, { label: activeLabel, dataUrl, filename, srcRect: { x: srcX, y: srcY, w: srcW, h: srcH }, poly, displayRect: { left: rectX, top: rectY, width: rectW, height: rectH } }]);
    setDraw(null);
    setActiveLabel(null);
  }

  async function handleCompare(index: number) {
    if (!originalOcr) { setError("Please click 'Process Receipt' first before comparing."); return; }
    const crop = cropPreviews[index];
    setCropPreviews((prev) => prev.map((c, i) => i === index ? { ...c, comparing: true } : c));

    const blob = await (await fetch(crop.dataUrl)).blob();
    const form = new FormData();
    form.append("crop_image", blob, crop.filename);
    form.append("crop_meta", JSON.stringify({ label: crop.label, srcRect: crop.srcRect, poly: crop.poly }));
    form.append("original_ocr", JSON.stringify(originalOcr));

    try {
      const res = await fetch("/api/compare", { method: "POST", body: form });
      const data = await res.json();
      setCropPreviews((prev) => prev.map((c, i) => i === index ? { ...c, comparing: false, compareResult: res.ok ? data : null } : c));
      if (!res.ok) setError(data.error ?? "Compare failed.");
    } catch (e) {
      setCropPreviews((prev) => prev.map((c, i) => i === index ? { ...c, comparing: false } : c));
      setError(`Compare failed: ${e}`);
    }
  }

  async function handleCancel(index: number) {
    const crop = cropPreviews[index];
    await fetch("/api/crop/delete", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: crop.filename }) });
    setCropPreviews((prev) => prev.filter((_, i) => i !== index));
  }

  function handleSave() {
    if (!layoutText.trim()) { setError("Nothing to save."); return; }
    const blob = new Blob([layoutText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "reconstructed_layout.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  const selectionRect = draw
    ? {
        left: Math.min(draw.startX, draw.currentX),
        top: Math.min(draw.startY, draw.currentY),
        width: Math.abs(draw.currentX - draw.startX),
        height: Math.abs(draw.currentY - draw.startY),
      }
    : null;

  return (
    <main style={styles.main}>
      <h1 style={styles.h1}>Receipt OCR — Layout Reconstruction</h1>
      <p style={styles.sub}>Upload a receipt image (PNG/JPEG) and click <strong>Process</strong>.</p>

      <div style={styles.card}>
        <input ref={inputRef} type="file" accept="image/png,image/jpeg" onChange={handleFileChange} style={{ display: "none" }} />
        <button style={styles.uploadBtn} onClick={() => inputRef.current?.click()}>
          {file ? `📎 ${file.name}` : "Choose Image"}
        </button>

        {preview && (
          <div>
            <p style={styles.hint}>
              {activeLabel
                ? `✏️ Now draw a box on the receipt to crop the "${activeLabel}" region`
                : "Select a label then draw a box on the receipt:"}
            </p>
            <div style={styles.labelBtns}>
              {LABELS.map((label) => (
                <button
                  key={label}
                  onClick={() => setActiveLabel(activeLabel === label ? null : label)}
                  style={{
                    ...styles.labelBtn,
                    background: LABEL_COLORS[label],
                    outline: activeLabel === label ? "3px solid #000" : "none",
                    outlineOffset: 2,
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            <div
              ref={containerRef}
              style={{ ...styles.imgContainer, cursor: activeLabel ? "crosshair" : "default" }}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={() => { if (draw?.active) setDraw(null); }}
              onContextMenu={(e) => e.preventDefault()}
            >
              <img
                ref={imgRef}
                src={preview}
                alt="Receipt preview"
                style={styles.preview}
                draggable={false}
              />
              {/* persistent bbox overlays */}
              {cropPreviews.map((c, i) => (
                <div key={i} style={{
                  position: "absolute",
                  left: c.displayRect.left, top: c.displayRect.top,
                  width: c.displayRect.width, height: c.displayRect.height,
                  border: `2px solid ${LABEL_COLORS[c.label]}`,
                  boxSizing: "border-box",
                  pointerEvents: "none",
                }}>
                  <span style={{ position: "absolute", top: -20, left: 0, background: LABEL_COLORS[c.label], color: "#fff", fontSize: "0.7rem", fontWeight: 700, padding: "1px 6px", borderRadius: 4, pointerEvents: "auto", cursor: "pointer", userSelect: "none" }}
                    onClick={() => handleCancel(i)}
                  >✕ {c.label}</span>
                </div>
              ))}

              {selectionRect && (
                <div
                  style={{
                    position: "absolute",
                    border: `2px solid ${activeLabel ? LABEL_COLORS[activeLabel] : "#000"}`,
                    background: activeLabel ? `${LABEL_COLORS[activeLabel]}22` : "transparent",
                    pointerEvents: "none",
                    ...selectionRect,
                  }}
                />
              )}
            </div>
          </div>
        )}

        <button style={{ ...styles.btn, ...styles.primary }} onClick={handleProcess} disabled={loading || !file}>
          {loading ? "Processing…" : "Process Receipt"}
        </button>
      </div>

      {cropPreviews.length > 0 && (
        <div style={styles.card}>
          <label style={styles.label}>Cropped Regions</label>
          <div style={styles.cropGrid}>
            {cropPreviews.map((c, i) => (
              <div key={i} style={styles.cropItem}>
                <span style={{ ...styles.cropTag, background: LABEL_COLORS[c.label] }}>{c.label}</span>
                <img src={c.dataUrl} alt={c.label} style={styles.cropImg} />
                <div style={styles.cropCoords}>
                  {([['tl','top-left'],['tr','top-right'],['br','bottom-right'],['bl','bottom-left']] as const).map(([key, name]) => (
                    <div key={key}><span style={styles.coordPoint}>[{c.poly[key][0]}, {c.poly[key][1]}]</span> {name}</div>
                  ))}
                </div>
                <button
                  style={{ ...styles.btn, background: "#f59e0b", color: "#fff", fontSize: "0.8rem", padding: "0.4rem 0.9rem" }}
                  onClick={() => handleCompare(i)}
                  disabled={c.comparing}
                >
                  {c.comparing ? "Comparing…" : "Compare"}
                </button>
                {c.compareResult && (
                  <div style={{ ...styles.cropCoords, background: c.compareResult.match ? "#d1fae5" : "#fee2e2" }}>
                    <div><strong>Crop text:</strong> {c.compareResult.crop_text || "—"}</div>
                    <div><strong>Original text:</strong> {c.compareResult.original_text || "—"}</div>
                    <div><strong>Similarity:</strong> {(c.compareResult.similarity * 100).toFixed(0)}%</div>
                    <div><strong>Match:</strong> {c.compareResult.match ? "✅ Yes" : "❌ No"}</div>
                    <div><strong>Crop confidence:</strong> {c.compareResult.crop_confidence != null ? `${(c.compareResult.crop_confidence * 100).toFixed(1)}%` : "—"}</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <p style={styles.error}>{error}</p>}

      {layoutText !== "" && (
        <div style={styles.card}>
          <label style={styles.label}>Reconstructed Layout Text (editable)</label>
          <textarea
            value={layoutText}
            onChange={(e) => setLayoutText(e.target.value)}
            style={styles.textarea}
            rows={25}
            spellCheck={false}
          />
          <button style={{ ...styles.btn, ...styles.secondary }} onClick={handleSave}>
            Save to File
          </button>
        </div>
      )}
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  main: { maxWidth: 800, margin: "0 auto", padding: "2rem 1rem" },
  h1: { fontSize: "1.6rem", marginBottom: "0.25rem" },
  sub: { color: "#555", marginBottom: "1.5rem" },
  card: { background: "#fff", borderRadius: 8, padding: "1.5rem", marginBottom: "1.5rem", boxShadow: "0 1px 4px rgba(0,0,0,0.1)", display: "flex", flexDirection: "column", gap: "1rem" },
  uploadBtn: { padding: "0.6rem 1.2rem", borderRadius: 6, border: "2px dashed #aaa", background: "#fafafa", cursor: "pointer", fontSize: "0.95rem", textAlign: "left" },
  hint: { fontSize: "0.85rem", color: "#555", margin: "0 0 0.5rem" },
  labelBtns: { display: "flex", gap: "0.75rem", marginBottom: "0.75rem" },
  labelBtn: { padding: "0.45rem 1rem", borderRadius: 20, color: "#fff", fontWeight: 700, fontSize: "0.85rem", cursor: "pointer", border: "none" },
  imgContainer: { position: "relative", display: "inline-block", width: "100%" },
  preview: { width: "100%", maxHeight: 500, objectFit: "contain", borderRadius: 6, display: "block", userSelect: "none" },
  btn: { padding: "0.6rem 1.4rem", borderRadius: 6, border: "none", cursor: "pointer", fontSize: "0.95rem", fontWeight: 600, alignSelf: "flex-start" },
  primary: { background: "#0070f3", color: "#fff" },
  secondary: { background: "#e5e7eb", color: "#111" },
  error: { color: "#c00", background: "#fff0f0", padding: "0.75rem 1rem", borderRadius: 6, border: "1px solid #fcc" },
  label: { fontWeight: 600, fontSize: "0.9rem", color: "#333" },
  textarea: { fontFamily: "monospace", whiteSpace: "pre", overflowX: "auto", fontSize: "0.82rem", padding: "0.75rem", borderRadius: 6, border: "1px solid #ddd", resize: "vertical", background: "#fafafa" },
  cropGrid: { display: "flex", flexWrap: "wrap", gap: "1rem" },
  cropItem: { display: "flex", flexDirection: "column", gap: "0.3rem" },
  cropTag: { display: "inline-block", padding: "0.2rem 0.6rem", borderRadius: 12, color: "#fff", fontSize: "0.75rem", fontWeight: 700, alignSelf: "flex-start" },
  cropImg: { border: "1px solid #ddd", borderRadius: 4, maxWidth: 260 },
  cropCoords: { fontSize: "0.75rem", color: "#374151", fontFamily: "monospace", background: "#f3f4f6", padding: "6px 10px", borderRadius: 4, display: "flex", flexDirection: "column", gap: 2 },
  coordPoint: { display: "inline-block", minWidth: 100, color: "#0070f3", fontWeight: 600 },
};
