import { NextRequest, NextResponse } from "next/server";
import { writeFile } from "fs/promises";
import path from "path";

const CROP_DIR = path.join(process.cwd(), "..", "crop_images");

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const file = form.get("crop") as File | null;
  const filename = form.get("filename") as string | null;
  const meta = form.get("meta") as string | null;
  if (!file || !filename) return NextResponse.json({ error: "Missing crop or filename" }, { status: 400 });

  const buffer = Buffer.from(await file.arrayBuffer());
  await writeFile(path.join(CROP_DIR, filename), buffer);

  if (meta) {
    const jsonFilename = filename.replace(/\.png$/, ".json");
    await writeFile(path.join(CROP_DIR, jsonFilename), meta, "utf-8");
  }

  return NextResponse.json({ ok: true, filename });
}
