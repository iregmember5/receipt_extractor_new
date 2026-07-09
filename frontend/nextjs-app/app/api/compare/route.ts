import { NextRequest, NextResponse } from "next/server";

const DJANGO_API = "http://127.0.0.1:8000/api/compare-crop/";

export async function POST(req: NextRequest) {
  const form = await req.formData();

  let res: Response;
  try {
    res = await fetch(DJANGO_API, { method: "POST", body: form });
  } catch {
    return NextResponse.json({ error: "Could not connect to Django backend." }, { status: 502 });
  }

  const data = await res.json();
  if (!res.ok) return NextResponse.json({ error: data.error ?? "Unknown error" }, { status: res.status });
  return NextResponse.json(data);
}
