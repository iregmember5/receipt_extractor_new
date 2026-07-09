import { NextRequest, NextResponse } from "next/server";

const DJANGO_API = "http://127.0.0.1:8000/api/update-ocr/";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { ocr_data, updates } = body;
  if (!ocr_data || !updates) {
    return NextResponse.json({ error: "ocr_data and updates are required." }, { status: 400 });
  }

  let res: Response;
  try {
    res = await fetch(DJANGO_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ocr_data, updates }),
    });
  } catch {
    return NextResponse.json({ error: `Could not connect to ${DJANGO_API}.` }, { status: 502 });
  }

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    return NextResponse.json({ error: errBody.error ?? `Server error (${res.status})` }, { status: res.status });
  }

  const data = await res.json();
  return NextResponse.json(data);
}