"use client";

import { useRef, useState } from "react";
import { reconstructLayoutText } from "@/lib/layoutReconstruct";
import type { TokenMapEntry } from "@/lib/layoutReconstruct";

type LabelType = "Date" | "Description" | "Amount";
type Selection = { id: number; label: LabelType; text: string; polys: TokenMapEntry["poly"][]; tokenIds: number[]; edited: boolean };
type OcrData = { rec_texts: string[]; rec_polys: number[][][]; rec_scores: number[]; image_width: number; image_height: number };

let nextId = 0;

function scalePolys(
  polys: TokenMapEntry["poly"][],
  natural: { w: number; h: number },
  rendered: { w: number; h: number }
): TokenMapEntry["poly"][] {
  const scale = Math.min(rendered.w / natural.w, rendered.h / natural.h);
  const offX = (rendered.w - natural.w * scale) / 2;
  const offY = (rendered.h - natural.h * scale) / 2;
  return polys.map(poly => poly.map(([x, y]) => [x * scale + offX, y * scale + offY] as [number, number]));
}

export default function Home() {
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [layoutText, setLayoutText] = useState("");
  const [tokenMap, setTokenMap] = useState<TokenMapEntry[]>([]);
  const [ocrData, setOcrData] = useState<OcrData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeLabel, setActiveLabel] = useState<LabelType | null>(null);
  const [selections, setSelections] = useState<Selection[]>([]);
  const [editTexts, setEditTexts] = useState<Record<number, string>>({});
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [imgNatural, setImgNatural] = useState<{ w: number; h: number } | null>(null);
  const [imgRendered, setImgRendered] = useState<{ w: number; h: number } | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setPreview(f ? URL.createObjectURL(f) : null);
    setLayoutText("");
    setTokenMap([]);
    setOcrData(null);
    setSelections([]);
    setEditTexts({});
    setError("");
    setActiveLabel(null);
    setImgNatural(null);
    setImgRendered(null);
  }

  async function handleProcess() {
    if (!file) { setError("No image selected."); return; }
    setLoading(true);
    setError("");
    setLayoutText("");
    setTokenMap([]);
    setOcrData(null);
    setSelections([]);
    setEditTexts({});
    const form = new FormData();
    form.append("receipt_image", file);
    try {
      const res = await fetch("/api/process", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) { setError(data.error ?? "Unknown error"); return; }
      setLayoutText(data.layoutText ?? "");
      setTokenMap(data.tokenMap ?? []);
      setOcrData(data.ocrData ?? null);
    } catch (e) {
      setError(`Request failed: ${e}`);
    } finally {
      setLoading(false);
    }
  }

  function handleTextareaMouseUp() {
    if (!activeLabel || !tokenMap.length) return;
    const ta = textareaRef.current;
    if (!ta) return;
    const selStart = ta.selectionStart;
    const selEnd = ta.selectionEnd;
    if (selStart === selEnd) return;
    const selectedText = ta.value.substring(selStart, selEnd).trim();
    if (!selectedText) return;
    const toRowCol = (offset: number) => {
      const before = ta.value.substring(0, offset);
      const row = (before.match(/\n/g) ?? []).length;
      const col = offset - before.lastIndexOf("\n") - 1;
      return { row, col };
    };
    const start = toRowCol(selStart);
    const end = toRowCol(selEnd);
    const matched = tokenMap.filter(entry => {
      if (entry.row < start.row || entry.row > end.row) return false;
      if (entry.row === start.row && entry.col_end <= start.col) return false;
      if (entry.row === end.row && entry.col_start >= end.col) return false;
      return true;
    });
    const id = nextId++;
    setSelections([{
      id,
      label: activeLabel,
      text: selectedText,
      polys: matched.map(e => e.poly),
      tokenIds: matched.map(e => e.id),
      edited: false,
    }]);
    setEditTexts(prev => ({ ...prev, [id]: selectedText }));
  }

  function handlePolyClick(entry: TokenMapEntry) {
    if (!activeLabel) return;
    const id = nextId++;
    setSelections([{
      id,
      label: activeLabel,
      text: entry.text,
      polys: [entry.poly],
      tokenIds: [entry.id],
      edited: false,
    }]);
    setEditTexts(prev => ({ ...prev, [id]: entry.text }));
  }

  async function handleUpdate(s: Selection) {
    if (!ocrData) return;
    const newText = editTexts[s.id] ?? s.text;

    try {
      const res = await fetch("/api/update-ocr", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ocr_data: ocrData,
          updates: [{ tokenIds: s.tokenIds, newText }],
        }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error ?? "Update failed"); return; }

      const newOcrData = data.ocr_data;
      setOcrData(newOcrData);

      const { layoutText: newLayout, tokenMap: newTokenMap } = reconstructLayoutText(
        newOcrData.rec_texts,
        newOcrData.rec_polys ?? ocrData.rec_polys,
        ocrData.image_width,
        ocrData.image_height
      );
      setLayoutText(newLayout);
      setTokenMap(newTokenMap);

      setSelections(prev => prev.map(sel =>
        sel.id === s.id ? { ...sel, text: newText, edited: true } : sel
      ));
    } catch (e) {
      setError(`Update request failed: ${e}`);
    }
  }

  function removeSelection(id: number) {
    setSelections(prev => prev.filter(s => s.id !== id));
    setEditTexts(prev => { const n = { ...prev }; delete n[id]; return n; });
  }

  function handleSave() {
    if (!layoutText.trim()) { setError("Nothing to save."); return; }
    const blob = new Blob([layoutText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "reconstructed_layout.txt"; a.click();
    URL.revokeObjectURL(url);
  }

  function handleSaveJson() {
    if (!selections.length) { setError("No selections to save."); return; }
    const grouped: Record<LabelType, { text: string; polys: TokenMapEntry["poly"][] }[]> = { Date: [], Description: [], Amount: [] };
    for (const s of selections) grouped[s.label].push({ text: editTexts[s.id] ?? s.text, polys: s.polys });
    const blob = new Blob([JSON.stringify(grouped, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "tagged_selections.json"; a.click();
    URL.revokeObjectURL(url);
  }

  const labelColors: Record<LabelType, string> = {
    Date: "#0070f3",
    Description: "#7c3aed",
    Amount: "#059669",
  };

  function selectionColorForPoly(poly: TokenMapEntry["poly"]): string | null {
    const key = JSON.stringify(poly);
    for (const s of selections) {
      if (s.polys.some(p => JSON.stringify(p) === key)) return labelColors[s.label];
    }
    return null;
  }

  const showOverlay = preview && imgNatural && imgRendered && tokenMap.length > 0;

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
          <div style={styles.imgWrapper}>
            <img
              ref={imgRef}
              src={preview}
              alt="Receipt preview"
              style={styles.preview}
              onLoad={() => {
                if (imgRef.current) {
                  setImgNatural({ w: imgRef.current.naturalWidth, h: imgRef.current.naturalHeight });
                  setImgRendered({ w: imgRef.current.clientWidth, h: imgRef.current.clientHeight });
                }
              }}
            />
            {showOverlay && (
              <svg
                style={styles.svgOverlay}
                width={imgRendered!.w}
                height={imgRendered!.h}
                viewBox={`0 0 ${imgRendered!.w} ${imgRendered!.h}`}
              >
                {tokenMap.map(entry => {
                  const scaled = scalePolys([entry.poly], imgNatural!, imgRendered!)[0];
                  const pts = scaled.map(([x, y]) => `${x},${y}`).join(" ");
                  const selColor = selectionColorForPoly(entry.poly);
                  const isHovered = hoveredId === entry.id;
                  const fill = selColor
                    ? selColor + "33"
                    : isHovered
                    ? (activeLabel ? labelColors[activeLabel] + "44" : "#00000022")
                    : "transparent";
                  const stroke = selColor ?? (isHovered ? (activeLabel ? labelColors[activeLabel] : "#555") : "#aaaaaa88");
                  const strokeW = selColor || isHovered ? 2 : 1;
                  return (
                    <polygon
                      key={entry.id}
                      points={pts}
                      fill={fill}
                      stroke={stroke}
                      strokeWidth={strokeW}
                      style={{ cursor: activeLabel ? "pointer" : "default", transition: "fill 0.1s" }}
                      onMouseEnter={() => setHoveredId(entry.id)}
                      onMouseLeave={() => setHoveredId(null)}
                      onClick={() => handlePolyClick(entry)}
                    />
                  );
                })}
              </svg>
            )}
          </div>
        )}

        <button style={{ ...styles.btn, ...styles.primary }} onClick={handleProcess} disabled={loading || !file}>
          {loading ? "Processing…" : "Process Receipt"}
        </button>
      </div>

      {error && <p style={styles.error}>{error}</p>}

      {ocrData && (
        <details style={{ marginBottom: "1rem", fontSize: "0.75rem", color: "#555" }}>
          <summary>OCR State (debug)</summary>
          <pre style={{ maxHeight: 300, overflow: "auto", background: "#f5f5f5", padding: "0.5rem", borderRadius: 4, border: "1px solid #ddd" }}>
{JSON.stringify(ocrData.rec_texts, null, 2)}
          </pre>
        </details>
      )}

      {layoutText !== "" && (
        <div style={styles.card}>
          <label style={styles.label}>Reconstructed Layout Text</label>
          {tokenMap.length > 0 && (
            <div style={styles.labelRow}>
              <span style={styles.labelHint}>Tag selection as:</span>
              {(["Date", "Description", "Amount"] as LabelType[]).map(l => (
                <button
                  key={l}
                  style={{ ...styles.labelBtn, borderColor: labelColors[l], color: activeLabel === l ? "#fff" : labelColors[l], background: activeLabel === l ? labelColors[l] : "transparent" }}
                  onClick={() => setActiveLabel(prev => prev === l ? null : l)}
                >
                  {l}
                </button>
              ))}
              {activeLabel && <span style={styles.activeLabelHint}>Select text below or click a box on the image → tagged as <strong>{activeLabel}</strong></span>}
            </div>
          )}
          <textarea
            ref={textareaRef}
            value={layoutText}
            onChange={e => setLayoutText(e.target.value)}
            onMouseUp={handleTextareaMouseUp}
            style={styles.textarea}
            rows={25}
            spellCheck={false}
          />
          <button style={{ ...styles.btn, ...styles.secondary }} onClick={handleSave}>
            Save to File
          </button>
        </div>
      )}

      {selections.length > 0 && (
        <div style={styles.card}>
          <label style={styles.label}>Tagged Selections</label>
          <div style={styles.selectionList}>
            {selections.map(s => (
              <div key={s.id} style={{ ...styles.selCard, borderLeftColor: labelColors[s.label] }}>
                <div style={styles.selHeader}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ ...styles.selLabel, background: labelColors[s.label] }}>{s.label}</span>
                    {s.edited && <span style={styles.editedBadge}>✏ edited</span>}
                  </div>
                  <button style={styles.removeBtn} onClick={() => removeSelection(s.id)}>✕</button>
                </div>

                <textarea
                  style={{ ...styles.editInput, resize: "vertical", minHeight: 120 }}
                  value={editTexts[s.id] ?? s.text}
                  onChange={e => setEditTexts(prev => ({ ...prev, [s.id]: e.target.value }))}
                  rows={6}
                />

                {s.polys.length > 0 ? (
                  <div style={styles.polyBlock}>
                    {s.polys.map((poly, pi) => (
                      <div key={pi} style={styles.polyRow}>
                        <span style={styles.polyIndex}>#{pi + 1}</span>
                        <span style={styles.polyCoords}>
                          {poly.map(([x, y]) => `(${Math.round(x)}, ${Math.round(y)})`).join("  ")}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={styles.selMeta}>No polygons matched</p>
                )}

                <button
                  style={{ ...styles.btn, ...styles.secondary, fontSize: "0.8rem", padding: "0.3rem 0.8rem" }}
                  onClick={() => handleUpdate(s)}
                >
                  Update
                </button>
              </div>
            ))}
          </div>
          <button style={{ ...styles.btn, ...styles.primary }} onClick={handleSaveJson}>
            Save JSON
          </button>
        </div>
      )}
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  main:            { maxWidth: 800, margin: "0 auto", padding: "2rem 1rem" },
  h1:              { fontSize: "1.6rem", marginBottom: "0.25rem" },
  sub:             { color: "#555", marginBottom: "1.5rem" },
  card:            { background: "#fff", borderRadius: 8, padding: "1.5rem", marginBottom: "1.5rem", boxShadow: "0 1px 4px rgba(0,0,0,0.1)", display: "flex", flexDirection: "column", gap: "1rem" },
  uploadBtn:       { padding: "0.6rem 1.2rem", borderRadius: 6, border: "2px dashed #aaa", background: "#fafafa", cursor: "pointer", fontSize: "0.95rem", textAlign: "left" },
  imgWrapper:      { position: "relative", display: "inline-block", width: "100%" },
  preview:         { width: "100%", maxHeight: 500, objectFit: "contain", borderRadius: 6, display: "block" },
  svgOverlay:      { position: "absolute", top: 0, left: 0, pointerEvents: "auto" },
  btn:             { padding: "0.6rem 1.4rem", borderRadius: 6, border: "none", cursor: "pointer", fontSize: "0.95rem", fontWeight: 600, alignSelf: "flex-start" },
  primary:         { background: "#0070f3", color: "#fff" },
  secondary:       { background: "#e5e7eb", color: "#111" },
  error:           { color: "#c00", background: "#fff0f0", padding: "0.75rem 1rem", borderRadius: 6, border: "1px solid #fcc" },
  label:           { fontWeight: 600, fontSize: "0.9rem", color: "#333" },
  textarea:        { fontFamily: "monospace", whiteSpace: "pre", overflowX: "auto", fontSize: "0.82rem", padding: "0.75rem", borderRadius: 6, border: "1px solid #ddd", resize: "vertical", background: "#fafafa" },
  labelRow:        { display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" },
  labelHint:       { fontSize: "0.85rem", color: "#555" },
  labelBtn:        { padding: "0.3rem 0.9rem", borderRadius: 20, border: "2px solid", cursor: "pointer", fontSize: "0.85rem", fontWeight: 600, transition: "all 0.15s" },
  activeLabelHint: { fontSize: "0.8rem", color: "#555", marginLeft: "0.5rem" },
  selectionList:   { display: "flex", flexDirection: "column", gap: "0.75rem" },
  selCard:         { borderLeft: "4px solid", borderRadius: 6, padding: "0.75rem 1rem", background: "#f9fafb", display: "flex", flexDirection: "column", gap: "0.5rem" },
  selHeader:       { display: "flex", justifyContent: "space-between", alignItems: "center" },
  selLabel:        { color: "#fff", fontSize: "0.75rem", fontWeight: 700, padding: "0.15rem 0.6rem", borderRadius: 12 },
  editedBadge:     { fontSize: "0.72rem", color: "#92400e", background: "#fef3c7", padding: "0.1rem 0.5rem", borderRadius: 10, fontWeight: 600 },
  removeBtn:       { background: "none", border: "none", cursor: "pointer", fontSize: "1rem", color: "#888", lineHeight: 1 },
  editInput:       { fontFamily: "monospace", fontSize: "0.88rem", padding: "0.4rem 0.6rem", borderRadius: 6, border: "1px solid #ddd", background: "#fff", width: "100%", boxSizing: "border-box", whiteSpace: "pre-wrap", overflowWrap: "break-word" },
  selMeta:         { margin: 0, fontSize: "0.78rem", color: "#666" },
  polyBlock:       { display: "flex", flexDirection: "column", gap: "0.25rem" },
  polyRow:         { display: "flex", alignItems: "baseline", gap: "0.5rem" },
  polyIndex:       { fontSize: "0.72rem", fontWeight: 700, color: "#888", minWidth: 24 },
  polyCoords:      { fontSize: "0.75rem", fontFamily: "monospace", color: "#444", wordBreak: "break-all" },
};
