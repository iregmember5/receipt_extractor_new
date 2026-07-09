type Poly = [number, number][];

interface Item {
  text: string;
  x_center: number;
  y_center: number;
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
  poly: Poly;
  origIndex: number;
}

interface Row {
  y_center: number;
  items: Item[];
}

export interface TokenMapEntry {
  id: number;
  text: string;
  row: number;
  col_start: number;
  col_end: number;
  poly: Poly;
}

function median(values: number[]): number {
  if (!values.length) return 0;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 === 0 ? (s[mid - 1] + s[mid]) / 2 : s[mid];
}

function getBoxCenter(poly: Poly) {
  const xs = poly.map((p) => p[0]);
  const ys = poly.map((p) => p[1]);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  return { xc: (xmin + xmax) / 2, yc: (ymin + ymax) / 2, xmin, ymin, xmax, ymax };
}

function snapXminToColumns(items: Item[], imgWidth: number, tolRatio = 0.008, maxSnapRatio = 0.02) {
  if (!items.length) return;
  const xs = [...items.map((i) => i.x_min)].sort((a, b) => a - b);
  const clusters: number[] = [];
  let current = [xs[0]];
  for (const x of xs.slice(1)) {
    if (x - current[current.length - 1] <= imgWidth * tolRatio) {
      current.push(x);
    } else {
      clusters.push(current.reduce((a, b) => a + b, 0) / current.length);
      current = [x];
    }
  }
  clusters.push(current.reduce((a, b) => a + b, 0) / current.length);

  const maxSnap = imgWidth * maxSnapRatio;
  for (const item of items) {
    const nearest = clusters.reduce((a, b) => (Math.abs(b - item.x_min) < Math.abs(a - item.x_min) ? b : a));
    if (Math.abs(nearest - item.x_min) <= maxSnap) item.x_min = nearest;
  }
}

function groupIntoRows(items: Item[]): Row[] {
  const heights = items.map((i) => i.y_max - i.y_min);
  const medH = median(heights) || 1;
  const yTol = medH * 0.6;

  const sorted = [...items].sort((a, b) => a.y_center - b.y_center || a.x_center - b.x_center);
  const rows: Row[] = [];

  for (const item of sorted) {
    const row = rows.find((r) => Math.abs(item.y_center - r.y_center) <= yTol);
    if (row) {
      row.items.push(item);
      row.y_center = row.items.reduce((s, i) => s + i.y_center, 0) / row.items.length;
    } else {
      rows.push({ y_center: item.y_center, items: [item] });
    }
  }

  rows.sort((a, b) => a.y_center - b.y_center);
  for (const row of rows) row.items.sort((a, b) => a.x_center - b.x_center);
  return rows;
}

export function reconstructLayoutText(
  recTexts: string[],
  recPolys: Poly[],
  imgWidth: number,
  imgHeight: number
): { layoutText: string; tokenMap: TokenMapEntry[] } {
  const items: Item[] = [];
  for (let i = 0; i < recTexts.length; i++) {
    const text = recTexts[i];
    if (!text || i >= recPolys.length || recPolys[i].length < 4) continue;
    const { xc, yc, xmin, ymin, xmax, ymax } = getBoxCenter(recPolys[i]);
    items.push({ text, x_center: xc, y_center: yc, x_min: xmin, x_max: xmax, y_min: ymin, y_max: ymax, poly: recPolys[i], origIndex: i });
  }

  if (!items.length) return { layoutText: "", tokenMap: [] };

  snapXminToColumns(items, imgWidth);
  const rows = groupIntoRows(items);

  const charWidths: number[] = [];
  for (const item of items) {
    const n = item.text.length;
    if (n > 0) {
      const w = (item.x_max - item.x_min) / n;
      if (w > 0) charWidths.push(w);
    }
  }
  const pxPerChar = median(charWidths) || Math.max(imgWidth / 100, 1);

  const rowGaps: number[] = [];
  let prevYc: number | null = null;
  for (const row of rows) {
    if (prevYc !== null) rowGaps.push(row.y_center - prevYc);
    prevYc = row.y_center;
  }
  let lineHeight = rowGaps.length
    ? median(rowGaps)
    : median(items.map((i) => i.y_max - i.y_min));
  if (!lineHeight || lineHeight <= 0) lineHeight = 1;

  let outputWidth = 40;
  for (const item of items) {
    const col = Math.max(0, Math.round(item.x_min / pxPerChar));
    outputWidth = Math.max(outputWidth, col + item.text.length + 2);
  }

  const outLines: string[] = [];
  const tokenMap: TokenMapEntry[] = [];
  let prevY: number | null = null;
  let rowIndex = 0;

  for (const row of rows) {
    if (prevY !== null) {
      const gapLines = Math.round((row.y_center - prevY) / lineHeight) - 1;
      for (let g = 0; g < Math.max(0, gapLines); g++) {
        outLines.push("");
        rowIndex++;
      }
    }
    prevY = row.y_center;

    const line = Array(outputWidth).fill(" ");
    let cursor = 0;

    for (const item of row.items) {
      const col = Math.max(0, Math.round(item.x_min / pxPerChar));
      const start = Math.max(col, cursor);
      const needed = start + item.text.length + 2;
      while (line.length < needed) line.push(" ");
      for (let j = 0; j < item.text.length; j++) line[start + j] = item.text[j];

      tokenMap.push({
        id: item.origIndex,
        text: item.text,
        row: rowIndex,
        col_start: start,
        col_end: start + item.text.length,
        poly: item.poly,
      });

      cursor = start + item.text.length + 1;
    }

    outLines.push(line.join("").trimEnd());
    outputWidth = Math.max(outputWidth, line.length);
    rowIndex++;
  }

  return { layoutText: outLines.join("\n"), tokenMap };
}
