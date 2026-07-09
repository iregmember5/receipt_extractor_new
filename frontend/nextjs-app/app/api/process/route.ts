import { NextRequest, NextResponse } from "next/server";
import { reconstructLayoutText } from "@/lib/layoutReconstruct";

const DJANGO_API = "http://127.0.0.1:8000/api/process-receipt-json/";

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const file = formData.get("receipt_image") as File | null;
  if (!file) return NextResponse.json({ error: "No image provided." }, { status: 400 });

  const upstream = new FormData();
  upstream.append("receipt_image", file);

  let res: Response;
  try {
    res = await fetch(DJANGO_API, { method: "POST", body: upstream });
  } catch {
    return NextResponse.json({ error: `Could not connect to ${DJANGO_API}. Is the Django server running?` }, { status: 502 });
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    return NextResponse.json({ error: body.error ?? `Server error (${res.status})` }, { status: res.status });
  }

  const data = await res.json();
  const { ocr_data, image_width, image_height } = data;
  if (!ocr_data) return NextResponse.json({ error: "No ocr_data in response." }, { status: 500 });

  const { layoutText, tokenMap } = reconstructLayoutText(
    ocr_data.rec_texts ?? [],
    ocr_data.rec_polys ?? [],
    image_width,
    image_height
  );

  return NextResponse.json({
    layoutText,
    tokenMap,
    ocrData: {
      rec_texts: ocr_data.rec_texts,
      rec_polys: ocr_data.rec_polys,
      rec_scores: ocr_data.rec_scores,
      image_width,
      image_height,
    },
  });
}
